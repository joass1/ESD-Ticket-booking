import sys
sys.path.insert(0, '/app')

import os
import json
import uuid
import requests
from flask import Flask, request, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from shared.response import success, error
from shared.amqp_lib import connect_with_retry, setup_exchange, publish_message
from datetime import datetime, timedelta
from decimal import Decimal
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
CORS(app)


@app.before_request
def set_correlation_id():
    g.correlation_id = request.headers.get('X-Correlation-ID') or str(uuid.uuid4())


@app.after_request
def add_correlation_header(response):
    response.headers['X-Correlation-ID'] = getattr(g, 'correlation_id', '')
    return response


# Database configuration
db_host = os.environ.get('DB_HOST', 'mysql')
db_port = os.environ.get('DB_PORT', '3306')
db_user = os.environ.get('DB_USER', 'root')
db_password = os.environ.get('DB_PASSWORD', 'root')
db_name = os.environ.get('DB_NAME', 'saga_log_db')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    '?charset=utf8mb4'
)
app.config['SQLALCHEMY_POOL_SIZE'] = 5
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
app.config['SQLALCHEMY_POOL_PRE_PING'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Service URLs (configurable via env vars)
SEAT_SERVICE_URL = os.environ.get('SEAT_SERVICE_URL', 'http://seat:5003')
PAYMENT_SERVICE_URL = os.environ.get('PAYMENT_SERVICE_URL', 'http://payment:5004')
BOOKING_SERVICE_URL = os.environ.get('BOOKING_SERVICE_URL', 'http://booking:5002')

# AMQP connection for publishing (dedicated connection, separate from consumer threads)
amqp_channel = None
try:
    amqp_connection = connect_with_retry()
    amqp_channel = amqp_connection.channel()
    setup_exchange(amqp_channel, 'booking_topic', 'topic')
    print("[Orchestrator] AMQP publishing channel ready")
except Exception as e:
    print(f"[Orchestrator] AMQP connection failed (will retry on publish): {e}")


def publish_booking_event(routing_key, payload):
    """Publish a booking event to booking_topic exchange."""
    global amqp_channel
    try:
        if amqp_channel is None or amqp_channel.is_closed:
            conn = connect_with_retry()
            amqp_channel = conn.channel()
            setup_exchange(amqp_channel, 'booking_topic', 'topic')
        publish_message(amqp_channel, 'booking_topic', routing_key, json.dumps(payload))
        print(f"[Orchestrator] Published {routing_key}: {payload.get('saga_id', 'unknown')}")
    except Exception as e:
        print(f"[Orchestrator] Failed to publish {routing_key}: {e}")


# ============================================
# Model
# ============================================

class SagaLog(db.Model):
    __tablename__ = 'saga_log'

    saga_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    event_id = db.Column(db.Integer, nullable=False)
    seat_id = db.Column(db.Integer, nullable=True)
    booking_id = db.Column(db.Integer, nullable=True)
    payment_intent_id = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(20), default='STARTED')
    error_message = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(),
                           onupdate=db.func.current_timestamp())

    def to_dict(self):
        d = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            if isinstance(val, datetime):
                d[col.name] = val.isoformat()
            elif isinstance(val, Decimal):
                d[col.name] = float(val)
            else:
                d[col.name] = val
        return d


# ============================================
# Compensation Helper
# ============================================

def compensate(saga):
    """Run compensating transactions to undo partial saga progress."""
    # Release seat
    if saga.seat_id and saga.event_id and saga.user_id:
        try:
            requests.post(
                f"{SEAT_SERVICE_URL}/seats/release",
                json={
                    'event_id': saga.event_id,
                    'seat_id': saga.seat_id,
                    'user_id': saga.user_id
                },
                timeout=10
            )
            print(f"[Compensate] Released seat {saga.seat_id} for saga {saga.saga_id}")
        except Exception as e:
            print(f"[Compensate] Failed to release seat for saga {saga.saga_id}: {e}")

    # Update booking status to failed/expired
    if saga.booking_id:
        try:
            status = 'expired' if saga.status == 'TIMEOUT' else 'failed'
            requests.put(
                f"{BOOKING_SERVICE_URL}/bookings/{saga.booking_id}",
                json={'status': status},
                timeout=10
            )
            print(f"[Compensate] Updated booking {saga.booking_id} to {status}")
        except Exception as e:
            print(f"[Compensate] Failed to update booking for saga {saga.saga_id}: {e}")


# ============================================
# Routes
# ============================================

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return success({"status": "healthy"})
    except Exception as e:
        return error(f"Database unreachable: {str(e)}", 503)


@app.route('/bookings/initiate', methods=['POST'])
def initiate_booking():
    """Saga entry point: reserve seat -> create booking -> create payment intent."""
    data = request.get_json()
    if not data:
        return error("Invalid JSON", 400)

    required = ['user_id', 'event_id', 'seat_id', 'email']
    for field in required:
        if field not in data:
            return error(f"Missing required field: {field}", 400)

    user_id = data['user_id']
    event_id = data['event_id']
    seat_id = data['seat_id']
    email = data['email']

    # Create saga log entry
    saga_id = str(uuid.uuid4())
    saga = SagaLog(
        saga_id=saga_id,
        user_id=user_id,
        event_id=event_id,
        seat_id=seat_id,
        email=email,
        status='STARTED',
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.session.add(saga)
    db.session.commit()

    # ---- Step 1: Reserve Seat ----
    try:
        seat_resp = requests.post(
            f"{SEAT_SERVICE_URL}/seats/reserve",
            json={'event_id': event_id, 'seat_id': seat_id, 'user_id': user_id},
            timeout=10
        )
        if seat_resp.status_code != 200:
            saga.status = 'FAILED'
            saga.error_message = f"Seat reservation failed: {seat_resp.text}"
            db.session.commit()
            return error(f"Seat reservation failed: {seat_resp.json().get('message', seat_resp.text)}", 409)

        seat_data = seat_resp.json().get('data', {})
        actual_seat_id = seat_data.get('seat_id', seat_id)
        section_price = seat_data.get('section_price')

        # If auto-assigned, the seat_id may differ
        saga.seat_id = actual_seat_id
        saga.amount = section_price
        saga.status = 'SEAT_RESERVED'
        db.session.commit()

    except requests.exceptions.RequestException as e:
        saga.status = 'FAILED'
        saga.error_message = f"Seat service unreachable: {str(e)}"
        db.session.commit()
        return error(f"Seat service unreachable: {str(e)}", 503)

    # ---- Step 2: Create Booking ----
    try:
        booking_resp = requests.post(
            f"{BOOKING_SERVICE_URL}/bookings",
            json={
                'user_id': user_id,
                'event_id': event_id,
                'seat_id': actual_seat_id,
                'email': email,
                'amount': float(section_price),
                'status': 'pending'
            },
            timeout=10
        )
        if booking_resp.status_code != 201:
            # Compensate: release seat
            compensate(saga)
            saga.status = 'FAILED'
            saga.error_message = f"Booking creation failed: {booking_resp.text}"
            db.session.commit()
            return error("Booking creation failed", 500)

        booking_data = booking_resp.json().get('data', {})
        saga.booking_id = booking_data.get('booking_id')
        db.session.commit()

    except requests.exceptions.RequestException as e:
        compensate(saga)
        saga.status = 'FAILED'
        saga.error_message = f"Booking service unreachable: {str(e)}"
        db.session.commit()
        return error(f"Booking service unreachable: {str(e)}", 503)

    # ---- Step 3: Create Payment Intent ----
    try:
        payment_resp = requests.post(
            f"{PAYMENT_SERVICE_URL}/payments/create",
            json={
                'booking_id': saga.booking_id,
                'user_id': user_id,
                'amount': float(section_price)
            },
            timeout=10
        )
        if payment_resp.status_code != 201:
            # Compensate: release seat + update booking to failed
            compensate(saga)
            saga.status = 'FAILED'
            saga.error_message = f"Payment creation failed: {payment_resp.text}"
            db.session.commit()
            return error("Payment creation failed", 502)

        payment_data = payment_resp.json().get('data', {})
        saga.payment_intent_id = payment_data.get('payment_intent_id')
        saga.status = 'PAYMENT_PENDING'
        db.session.commit()

    except requests.exceptions.RequestException as e:
        compensate(saga)
        saga.status = 'FAILED'
        saga.error_message = f"Payment service unreachable: {str(e)}"
        db.session.commit()
        return error(f"Payment service unreachable: {str(e)}", 503)

    # Return success with all data needed by frontend
    return success({
        'saga_id': saga_id,
        'booking_id': saga.booking_id,
        'seat_id': actual_seat_id,
        'seat_data': seat_data,
        'client_secret': payment_data.get('client_secret'),
        'payment_intent_id': saga.payment_intent_id,
        'amount': float(section_price),
        'expires_at': saga.expires_at.isoformat() + 'Z'
    }, 201)


@app.route('/bookings/confirm', methods=['POST'])
def confirm_booking():
    """Finalize the saga: verify payment -> confirm seat -> update booking -> publish event."""
    data = request.get_json()
    if not data:
        return error("Invalid JSON", 400)

    saga_id = data.get('saga_id')
    payment_intent_id = data.get('payment_intent_id')

    if not saga_id or not payment_intent_id:
        return error("saga_id and payment_intent_id are required", 400)

    # Load saga with optimistic locking guard
    saga = db.session.execute(
        db.select(SagaLog).where(SagaLog.saga_id == saga_id)
    ).scalar_one_or_none()

    if not saga:
        return error("Saga not found", 404)

    # Race condition guard: only proceed if still PAYMENT_PENDING
    if saga.status != 'PAYMENT_PENDING':
        return error(
            f"Cannot confirm saga in status '{saga.status}'. Expected PAYMENT_PENDING.",
            409
        )

    # ---- Verify Payment ----
    try:
        verify_resp = requests.post(
            f"{PAYMENT_SERVICE_URL}/payments/verify",
            json={'payment_intent_id': payment_intent_id},
            timeout=10
        )
        if verify_resp.status_code != 200:
            compensate(saga)
            saga.status = 'FAILED'
            saga.error_message = f"Payment verification failed: {verify_resp.text}"
            db.session.commit()
            return error("Payment verification failed", 402)

    except requests.exceptions.RequestException as e:
        compensate(saga)
        saga.status = 'FAILED'
        saga.error_message = f"Payment service unreachable: {str(e)}"
        db.session.commit()
        return error(f"Payment service unreachable: {str(e)}", 503)

    saga.status = 'PAYMENT_SUCCESS'
    db.session.commit()

    # ---- Confirm Seat ----
    try:
        requests.post(
            f"{SEAT_SERVICE_URL}/seats/confirm",
            json={
                'event_id': saga.event_id,
                'seat_id': saga.seat_id,
                'user_id': saga.user_id
            },
            timeout=10
        )
    except Exception as e:
        print(f"[Confirm] Seat confirm warning for saga {saga_id}: {e}")

    # ---- Update Booking ----
    try:
        requests.put(
            f"{BOOKING_SERVICE_URL}/bookings/{saga.booking_id}",
            json={
                'status': 'confirmed',
                'payment_intent_id': payment_intent_id
            },
            timeout=10
        )
    except Exception as e:
        print(f"[Confirm] Booking update warning for saga {saga_id}: {e}")

    # ---- Finalize Saga ----
    saga.payment_intent_id = payment_intent_id
    saga.status = 'CONFIRMED'
    db.session.commit()

    # ---- Publish booking.confirmed ----
    publish_booking_event('booking.confirmed', {
        'booking_id': saga.booking_id,
        'saga_id': saga.saga_id,
        'user_id': saga.user_id,
        'event_id': saga.event_id,
        'seat_id': saga.seat_id,
        'email': saga.email,
        'amount': float(saga.amount) if saga.amount else 0,
        'payment_intent_id': payment_intent_id
    })

    return success({
        'saga_id': saga_id,
        'status': 'confirmed',
        'booking_id': saga.booking_id
    })


@app.route('/sagas/<string:saga_id>')
def get_saga(saga_id):
    """Get saga status for polling."""
    saga = db.session.execute(
        db.select(SagaLog).where(SagaLog.saga_id == saga_id)
    ).scalar_one_or_none()

    if not saga:
        return error("Saga not found", 404)

    return success(saga.to_dict())


# ============================================
# APScheduler: Payment Expiry Detection
# ============================================

def check_expired_sagas():
    """Find PAYMENT_PENDING sagas past their 10-minute expiry and clean up."""
    with app.app_context():
        try:
            now = datetime.utcnow()
            expired_sagas = db.session.execute(
                db.select(SagaLog).where(
                    SagaLog.status == 'PAYMENT_PENDING',
                    SagaLog.expires_at <= now
                )
            ).scalars().all()

            for saga in expired_sagas:
                print(f"[Expiry] Timing out saga {saga.saga_id}")

                # Mark as TIMEOUT before compensating so compensate uses correct status
                saga.status = 'TIMEOUT'
                saga.error_message = 'Payment expired after 10 minutes'
                db.session.commit()

                # Compensate: release seat + update booking to expired
                compensate(saga)

                # Publish booking.timeout
                publish_booking_event('booking.timeout', {
                    'booking_id': saga.booking_id,
                    'saga_id': saga.saga_id,
                    'user_id': saga.user_id,
                    'event_id': saga.event_id,
                    'seat_id': saga.seat_id,
                    'reason': 'Payment expired after 10 minutes'
                })

            if expired_sagas:
                print(f"[Expiry] Processed {len(expired_sagas)} expired saga(s)")

        except Exception as e:
            print(f"[Expiry] Error checking expired sagas: {e}")
            db.session.rollback()


# Start the scheduler (guard against double-start in debug/reloader mode)
if os.environ.get('WERKZEUG_RUN_MAIN') != 'false':
    scheduler = BackgroundScheduler(misfire_grace_time=60)
    scheduler.add_job(
        check_expired_sagas,
        'interval',
        seconds=30,
        id='check_expired_sagas',
        replace_existing=True
    )
    scheduler.start()
    print("[Orchestrator] APScheduler started -- checking expired sagas every 30s")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5010)), debug=False)
