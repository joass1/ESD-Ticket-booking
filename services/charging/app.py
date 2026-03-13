import sys
sys.path.insert(0, '/app')

import os
import json
import threading
from decimal import Decimal
from datetime import datetime
from flask import Flask, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from shared.response import success, error
from shared.amqp_lib import connect_with_retry, setup_exchange, publish_message, start_consumer

app = Flask(__name__)
CORS(app)

# Database configuration
db_host = os.environ.get('DB_HOST', 'mysql')
db_port = os.environ.get('DB_PORT', '3306')
db_user = os.environ.get('DB_USER', 'root')
db_password = os.environ.get('DB_PASSWORD', 'root')
db_name = os.environ.get('DB_NAME', 'charging_db')

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
# Model
# ============================================

class ServiceFee(db.Model):
    __tablename__ = 'service_fees'

    fee_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, nullable=False)
    booking_id = db.Column(db.Integer, nullable=False)
    original_amount = db.Column(db.Numeric(10, 2), nullable=False)
    service_fee = db.Column(db.Numeric(10, 2), nullable=False)
    refund_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='calculated')
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

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
# AMQP Publisher (dedicated connection, lazy reconnect)
# ============================================

amqp_channel = None


def publish_refund_process(payload):
    """Publish refund.process to refund_direct exchange."""
    global amqp_channel
    try:
        if amqp_channel is None or amqp_channel.is_closed:
            conn = connect_with_retry()
            amqp_channel = conn.channel()
            setup_exchange(amqp_channel, 'refund_direct', 'direct')
        publish_message(amqp_channel, 'refund_direct', 'refund.process', json.dumps(payload))
        print(f"[Charging] Published refund.process for booking {payload.get('booking_id')}")
    except Exception as e:
        print(f"[Charging] Failed to publish refund.process: {e}")
        amqp_channel = None


# ============================================
# AMQP Consumer Callback
# ============================================

def handle_refund_request(ch, method, properties, body):
    """Consume booking.refund.requested, calculate 10% service fee, publish refund.process."""
    try:
        data = json.loads(body)
        booking_id = data['booking_id']
        user_id = data['user_id']
        email = data['email']
        amount = data['amount']
        event_id = data['event_id']

        print(f"[Charging] Received refund request for booking {booking_id}, amount {amount}")

        with app.app_context():
            original_amount = Decimal(str(amount))
            service_fee = (original_amount * Decimal('0.10')).quantize(Decimal('0.01'))
            refund_amount = (original_amount - service_fee).quantize(Decimal('0.01'))

            # Create fee record
            fee_record = ServiceFee(
                event_id=event_id,
                booking_id=booking_id,
                original_amount=original_amount,
                service_fee=service_fee,
                refund_amount=refund_amount,
                status='calculated'
            )
            db.session.add(fee_record)
            db.session.commit()

            # Update status to refund_initiated
            fee_record.status = 'refund_initiated'
            db.session.commit()

            # Publish refund.process for Payment Service
            publish_refund_process({
                'booking_id': booking_id,
                'user_id': user_id,
                'email': email,
                'refund_amount': float(refund_amount),
                'original_amount': float(original_amount),
                'service_fee': float(service_fee),
                'event_id': event_id
            })

            print(f"[Charging] Processed refund for booking {booking_id}: "
                  f"original={original_amount}, fee={service_fee}, refund={refund_amount}")

    except Exception as e:
        print(f"[Charging] Error handling refund request: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


# ============================================
# REST Endpoints
# ============================================

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return success({"status": "healthy"})
    except Exception as e:
        return error(f"Database unreachable: {str(e)}", 503)


@app.route('/fees/event/<int:event_id>')
def get_fees_by_event(event_id):
    """Query all service fees for an event with summary totals."""
    try:
        fees = ServiceFee.query.filter_by(event_id=event_id).all()
        fee_list = [f.to_dict() for f in fees]

        total_fees = sum(f.service_fee for f in fees) if fees else Decimal('0')
        total_refunds = sum(f.refund_amount for f in fees) if fees else Decimal('0')

        return success({
            'event_id': event_id,
            'fees': fee_list,
            'summary': {
                'count': len(fee_list),
                'total_fees': float(total_fees),
                'total_refunds': float(total_refunds)
            }
        })
    except Exception as e:
        return error(f"Failed to fetch fees: {str(e)}", 500)


@app.route('/fees/booking/<int:booking_id>')
def get_fee_by_booking(booking_id):
    """Query service fee for a specific booking."""
    try:
        fee = ServiceFee.query.filter_by(booking_id=booking_id).first()
        if not fee:
            return error("Fee record not found", 404)
        return success(fee.to_dict())
    except Exception as e:
        return error(f"Failed to fetch fee: {str(e)}", 500)


# ============================================
# Consumer Startup
# ============================================

def start_charging_consumers():
    """Start AMQP consumer for booking.refund.requested."""
    threading.Thread(
        target=lambda: start_consumer(
            'charging_refund_queue', 'booking_topic',
            ['booking.refund.requested'], handle_refund_request
        ), daemon=True
    ).start()
    print("[Charging] AMQP consumers started")


if __name__ == '__main__':
    start_charging_consumers()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5008)), debug=False)
