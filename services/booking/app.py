import sys
sys.path.insert(0, '/app')

import os
import json
import threading
from flask import Flask, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from shared.response import success, error
from shared.amqp_lib import connect_with_retry, setup_exchange, publish_message, start_consumer
from datetime import datetime
from decimal import Decimal

app = Flask(__name__)
CORS(app)

# Database configuration
db_host = os.environ.get('DB_HOST', 'mysql')
db_port = os.environ.get('DB_PORT', '3306')
db_user = os.environ.get('DB_USER', 'root')
db_password = os.environ.get('DB_PASSWORD', 'root')
db_name = os.environ.get('DB_NAME', 'booking_db')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    '?charset=utf8mb4'
)
app.config['SQLALCHEMY_POOL_SIZE'] = 5
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
app.config['SQLALCHEMY_POOL_PRE_PING'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ============================================
# AMQP Publisher (dedicated connection, lazy reconnect)
# ============================================

amqp_channel = None


def publish_booking_event(routing_key, payload):
    """Publish a booking event to booking_topic exchange."""
    global amqp_channel
    try:
        if amqp_channel is None or amqp_channel.is_closed:
            conn = connect_with_retry()
            amqp_channel = conn.channel()
            setup_exchange(amqp_channel, 'booking_topic', 'topic')
        publish_message(amqp_channel, 'booking_topic', routing_key, json.dumps(payload))
        print(f"[Booking] Published {routing_key}")
    except Exception as e:
        print(f"[Booking] Failed to publish {routing_key}: {e}")
        amqp_channel = None


# ============================================
# Model
# ============================================

class Booking(db.Model):
    __tablename__ = 'bookings'

    booking_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    event_id = db.Column(db.Integer, nullable=False)
    seat_id = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='pending')
    payment_intent_id = db.Column(db.String(255), nullable=True)
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
# Routes
# ============================================

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return success({"status": "healthy"})
    except Exception as e:
        return error(f"Database unreachable: {str(e)}", 503)


@app.route('/bookings/<int:booking_id>')
def get_booking(booking_id):
    """Get a single booking by ID."""
    booking = db.session.execute(
        db.select(Booking).where(Booking.booking_id == booking_id)
    ).scalar_one_or_none()

    if not booking:
        return error("Booking not found", 404)

    return success(booking.to_dict())


@app.route('/bookings/user/<string:user_id>')
def get_user_bookings(user_id):
    """Get all bookings for a user, sorted by newest first."""
    bookings = db.session.execute(
        db.select(Booking)
        .where(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
    ).scalars().all()
    return success([b.to_dict() for b in bookings])


@app.route('/bookings')
def get_bookings():
    """List bookings with optional filters: event_id, status."""
    query = db.select(Booking)

    event_id = request.args.get('event_id')
    if event_id:
        query = query.where(Booking.event_id == int(event_id))

    status = request.args.get('status')
    if status:
        query = query.where(Booking.status == status)

    # Sort by created_at descending (newest first)
    query = query.order_by(Booking.created_at.desc())

    bookings = db.session.execute(query).scalars().all()
    return success([b.to_dict() for b in bookings])


@app.route('/bookings', methods=['POST'])
def create_booking():
    """Create a booking. Called by Orchestrator in Phase 3.
    Required fields: user_id, event_id, seat_id, email, amount.
    Optional: status (default 'pending'), payment_intent_id.
    """
    data = request.get_json()
    if not data:
        return error("Invalid JSON", 400)

    required = ['user_id', 'event_id', 'seat_id', 'email', 'amount']
    for field in required:
        if field not in data:
            return error(f"Missing required field: {field}", 400)

    booking = Booking(
        user_id=data['user_id'],
        event_id=data['event_id'],
        seat_id=data['seat_id'],
        email=data['email'],
        amount=data['amount'],
        status=data.get('status', 'pending'),
        payment_intent_id=data.get('payment_intent_id')
    )

    try:
        db.session.add(booking)
        db.session.commit()
        return success(booking.to_dict(), 201)
    except Exception as e:
        db.session.rollback()
        return error(f"Failed to create booking: {str(e)}", 500)


@app.route('/bookings/<int:booking_id>', methods=['PUT'])
def update_booking(booking_id):
    """Update booking status. Called by Orchestrator in Phase 3.
    Updatable fields: status, payment_intent_id.
    """
    booking = db.session.execute(
        db.select(Booking).where(Booking.booking_id == booking_id)
    ).scalar_one_or_none()

    if not booking:
        return error("Booking not found", 404)

    data = request.get_json()
    if not data:
        return error("Invalid JSON", 400)

    # Update only provided fields
    updatable_fields = ['status', 'payment_intent_id']
    for field in updatable_fields:
        if field in data:
            setattr(booking, field, data[field])

    try:
        db.session.commit()
        return success(booking.to_dict())
    except Exception as e:
        db.session.rollback()
        return error(f"Failed to update booking: {str(e)}", 500)


# ============================================
# AMQP Consumers
# ============================================

def handle_event_cancelled(ch, method, properties, body):
    """Handle event.cancelled: update confirmed bookings to pending_refund and publish refund requests."""
    try:
        msg = json.loads(body)
        event_id = msg['event_id']

        print(f"[Booking] Event cancelled: event={event_id}")

        with app.app_context():
            bookings = Booking.query.filter_by(
                event_id=event_id, status='confirmed'
            ).all()

            for booking in bookings:
                booking.status = 'pending_refund'

            db.session.commit()

            for booking in bookings:
                publish_booking_event('booking.refund.requested', {
                    'booking_id': booking.booking_id,
                    'user_id': booking.user_id,
                    'email': booking.email,
                    'amount': float(booking.amount),
                    'event_id': event_id
                })

            print(f"[Booking] Updated {len(bookings)} bookings to pending_refund")

    except Exception as e:
        print(f"[Booking] Error handling event cancellation: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def handle_refund_completed(ch, method, properties, body):
    """Handle refund.completed: update booking status to refunded."""
    try:
        msg = json.loads(body)
        booking_id = msg['booking_id']

        print(f"[Booking] Refund completed: booking={booking_id}")

        with app.app_context():
            booking = Booking.query.filter_by(
                booking_id=booking_id, status='pending_refund'
            ).first()

            if booking:
                booking.status = 'refunded'
                db.session.commit()
                print(f"[Booking] Booking {booking_id} marked as refunded")
            else:
                print(f"[Booking] Booking {booking_id} not found or not pending_refund")

    except Exception as e:
        print(f"[Booking] Error handling refund completed: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_booking_consumers():
    """Start all AMQP consumers in separate daemon threads."""
    threading.Thread(
        target=lambda: start_consumer(
            'booking_cancel_queue', 'event_lifecycle',
            ['event.cancelled.*'], handle_event_cancelled
        ), daemon=True
    ).start()

    threading.Thread(
        target=lambda: start_consumer(
            'booking_refund_complete_queue', 'refund_topic',
            ['refund.completed'], handle_refund_completed
        ), daemon=True
    ).start()


if __name__ == '__main__':
    start_booking_consumers()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5002)), debug=False)
