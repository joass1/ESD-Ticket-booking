import sys
sys.path.insert(0, '/app')

import os
import json
import uuid
import time
import threading
from flask import Flask, request, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from shared.response import success, error
from shared.amqp_lib import connect_with_retry, setup_exchange, publish_message, start_consumer
from datetime import datetime
from decimal import Decimal
import stripe

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
db_name = os.environ.get('DB_NAME', 'payment_db')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    '?charset=utf8mb4'
)
app.config['SQLALCHEMY_POOL_SIZE'] = 5
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
app.config['SQLALCHEMY_POOL_PRE_PING'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


# ============================================
# Model
# ============================================

class Transaction(db.Model):
    __tablename__ = 'transactions'

    transaction_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='SGD')
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='pending')
    refund_amount = db.Column(db.Numeric(10, 2), nullable=True)
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


@app.route('/payments/create', methods=['POST'])
def create_payment():
    """Create a Stripe PaymentIntent and record a pending transaction."""
    data = request.get_json()
    if not data:
        return error("Invalid JSON", 400)

    required = ['booking_id', 'user_id', 'amount']
    for field in required:
        if field not in data:
            return error(f"Missing required field: {field}", 400)

    booking_id = data['booking_id']
    user_id = data['user_id']
    amount = data['amount']

    # Convert dollars to cents for Stripe (smallest currency unit)
    amount_cents = int(float(amount) * 100)

    try:
        # Create Stripe PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='sgd',
            metadata={
                'booking_id': str(booking_id),
                'user_id': str(user_id)
            }
        )

        # Save transaction record
        txn = Transaction(
            booking_id=booking_id,
            user_id=user_id,
            amount=amount,
            currency='SGD',
            stripe_payment_intent_id=intent.id,
            status='pending'
        )
        db.session.add(txn)
        db.session.commit()

        return success({
            'payment_intent_id': intent.id,
            'client_secret': intent.client_secret,
            'amount': float(amount)
        }, 201)

    except stripe.error.StripeError as e:
        db.session.rollback()
        return error(f"Stripe error: {str(e)}", 502)
    except Exception as e:
        db.session.rollback()
        return error(f"Payment creation failed: {str(e)}", 500)


@app.route('/payments/verify', methods=['POST'])
def verify_payment():
    """Verify a Stripe PaymentIntent and update transaction status."""
    data = request.get_json()
    if not data:
        return error("Invalid JSON", 400)

    payment_intent_id = data.get('payment_intent_id')
    if not payment_intent_id:
        return error("Missing required field: payment_intent_id", 400)

    try:
        # Retrieve PaymentIntent from Stripe
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        # Look up local transaction
        txn = db.session.execute(
            db.select(Transaction).where(
                Transaction.stripe_payment_intent_id == payment_intent_id
            )
        ).scalar_one_or_none()

        if not txn:
            return error("Transaction not found", 404)

        if intent.status == 'succeeded':
            txn.status = 'succeeded'
            db.session.commit()
            return success({
                'status': 'succeeded',
                'booking_id': txn.booking_id,
                'transaction_id': txn.transaction_id
            })
        else:
            txn.status = 'failed'
            db.session.commit()
            return error(f"Payment not succeeded. Stripe status: {intent.status}", 400)

    except stripe.error.StripeError as e:
        db.session.rollback()
        return error(f"Stripe error: {str(e)}", 502)
    except Exception as e:
        db.session.rollback()
        return error(f"Payment verification failed: {str(e)}", 500)


@app.route('/payments/transaction/<int:booking_id>')
def get_transaction_by_booking(booking_id):
    """Retrieve transaction by booking_id for status checks."""
    txn = db.session.execute(
        db.select(Transaction).where(Transaction.booking_id == booking_id)
        .order_by(Transaction.created_at.desc())
    ).scalars().first()

    if not txn:
        return error("Transaction not found", 404)

    return success(txn.to_dict())


# ============================================
# AMQP Publishers (dedicated connections, lazy reconnect)
# ============================================

refund_amqp_channel = None
dlq_amqp_channel = None


def publish_refund_completed(payload):
    """Publish refund.completed to refund_topic exchange (topic type)."""
    global refund_amqp_channel
    try:
        if refund_amqp_channel is None or refund_amqp_channel.is_closed:
            conn = connect_with_retry()
            refund_amqp_channel = conn.channel()
            setup_exchange(refund_amqp_channel, 'refund_topic', 'topic')
        publish_message(refund_amqp_channel, 'refund_topic', 'refund.completed', json.dumps(payload))
        print(f"[Payment] Published refund.completed for booking {payload.get('booking_id')}")
    except Exception as e:
        print(f"[Payment] Failed to publish refund.completed: {e}")
        refund_amqp_channel = None


def publish_to_dlq(payload):
    """Publish failed refund to refund_dlq exchange (direct type)."""
    global dlq_amqp_channel
    try:
        if dlq_amqp_channel is None or dlq_amqp_channel.is_closed:
            conn = connect_with_retry()
            dlq_amqp_channel = conn.channel()
            setup_exchange(dlq_amqp_channel, 'refund_dlq', 'direct')
        publish_message(dlq_amqp_channel, 'refund_dlq', 'refund.failed', json.dumps(payload))
        print(f"[Payment] Published to DLQ for booking {payload.get('booking_id')}")
    except Exception as e:
        print(f"[Payment] Failed to publish to DLQ: {e}")
        dlq_amqp_channel = None


# ============================================
# AMQP Consumer Callback
# ============================================

def handle_refund_process(ch, method, properties, body):
    """Consume refund.process, call Stripe refund with 3 retries, publish result."""
    try:
        data = json.loads(body)
        booking_id = data['booking_id']
        refund_amount = data['refund_amount']
        original_amount = data['original_amount']
        service_fee = data['service_fee']
        user_id = data['user_id']
        email = data['email']
        event_id = data['event_id']
        refund_type = data.get('refund_type', 'voluntary')

        print(f"[Payment] Processing refund for booking {booking_id}, amount {refund_amount}")

        with app.app_context():
            # Find the succeeded transaction for this booking
            txn = db.session.execute(
                db.select(Transaction).where(
                    Transaction.booking_id == booking_id,
                    Transaction.status == 'succeeded'
                )
            ).scalar_one_or_none()

            if not txn:
                print(f"[Payment] No succeeded transaction found for booking {booking_id}, skipping")
                return

            # Convert to cents for Stripe
            amount_cents = int(float(refund_amount) * 100)
            last_error = None

            # Retry loop: 3 attempts
            for attempt in range(3):
                try:
                    refund = stripe.Refund.create(
                        payment_intent=txn.stripe_payment_intent_id,
                        amount=amount_cents,
                        reason='requested_by_customer'
                    )
                    txn.status = 'refunded'
                    txn.refund_amount = Decimal(str(refund_amount))
                    db.session.commit()

                    publish_refund_completed({
                        'booking_id': booking_id,
                        'user_id': user_id,
                        'email': email,
                        'refund_amount': float(refund_amount),
                        'original_amount': float(original_amount),
                        'service_fee': float(service_fee),
                        'event_id': event_id,
                        'refund_type': refund_type
                    })
                    print(f"[Payment] Refund succeeded for booking {booking_id}")
                    return  # Success - exit
                except stripe.error.StripeError as e:
                    last_error = str(e)
                    print(f"[Payment] Stripe refund attempt {attempt + 1}/3 failed: {e}")
                    if attempt < 2:
                        time.sleep(1)

            # All 3 attempts failed - send to DLQ
            txn.status = 'refund_failed'
            db.session.commit()
            publish_to_dlq({
                'booking_id': booking_id,
                'error': last_error,
                'refund_amount': float(refund_amount),
                'event_id': event_id
            })
            print(f"[Payment] Refund failed after 3 attempts for booking {booking_id}")

    except Exception as e:
        print(f"[Payment] Error handling refund process: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


# ============================================
# Consumer Startup
# ============================================

def start_payment_consumers():
    """Start AMQP consumer for refund.process."""
    threading.Thread(
        target=lambda: start_consumer(
            'payment_refund_queue', 'refund_direct',
            ['refund.process'], handle_refund_process,
            exchange_type='direct'
        ), daemon=True
    ).start()
    print("[Payment] AMQP consumers started")


if __name__ == '__main__':
    start_payment_consumers()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5004)), debug=False)
