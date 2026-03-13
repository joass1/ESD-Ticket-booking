import sys
sys.path.insert(0, '/app')

import os
import json
import hashlib
import base64
import threading
from io import BytesIO
from decimal import Decimal
from datetime import datetime

import qrcode
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room
from shared.response import success, error
from shared.amqp_lib import start_consumer

app = Flask(__name__)
CORS(app)

# Database configuration
db_host = os.environ.get('DB_HOST', 'mysql')
db_port = os.environ.get('DB_PORT', '3306')
db_user = os.environ.get('DB_USER', 'root')
db_password = os.environ.get('DB_PASSWORD', 'root')
db_name = os.environ.get('DB_NAME', 'ticket_db')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    '?charset=utf8mb4'
)
app.config['SQLALCHEMY_POOL_SIZE'] = 5
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
app.config['SQLALCHEMY_POOL_PRE_PING'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

PORT = int(os.environ.get('PORT', 5006))
QR_SECRET = os.environ.get('QR_SECRET', 'ticket-validation-secret')

db = SQLAlchemy(app)

# Flask-SocketIO: must use threading mode (eventlet breaks pika/PyMySQL)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


# ============================================
# Model
# ============================================

class Ticket(db.Model):
    __tablename__ = 'tickets'

    ticket_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column(db.Integer, nullable=False, unique=True)
    event_id = db.Column(db.Integer)
    user_id = db.Column(db.String(100))
    seat_id = db.Column(db.Integer)
    qr_code_data = db.Column(db.Text)
    qr_code_image = db.Column(db.LargeBinary)
    status = db.Column(db.String(20), default='valid')
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        """Column-iteration to_dict with Decimal/datetime serialization.
        Excludes qr_code_image (LONGBLOB) by default."""
        result = {}
        for col in self.__table__.columns:
            if col.name == 'qr_code_image':
                continue
            val = getattr(self, col.name)
            if isinstance(val, Decimal):
                val = float(val)
            elif isinstance(val, datetime):
                val = val.isoformat()
            result[col.name] = val
        return result


# ============================================
# WebSocket handlers
# ============================================

@socketio.on('join')
def handle_join(data):
    """Client joins a room identified by booking_id."""
    booking_id = str(data.get('booking_id', ''))
    if booking_id:
        join_room(booking_id)
        print(f"[WS] Client joined room: {booking_id}")


# ============================================
# AMQP consumer callback
# ============================================

def handle_booking_confirmed(ch, method, properties, body):
    """Process booking.confirmed messages: generate QR ticket and notify via WebSocket."""
    try:
        msg = json.loads(body)
        booking_id = msg['booking_id']
        event_id = msg.get('event_id')
        user_id = msg.get('user_id')
        seat_id = msg.get('seat_id')

        print(f"[AMQP] Received booking.confirmed for booking_id={booking_id}")

        # Generate validation hash
        validation_hash = hashlib.sha256(
            f"{booking_id}:{QR_SECRET}".encode()
        ).hexdigest()[:16]

        # QR data string
        qr_data = f"{booking_id}:{validation_hash}"

        # Generate QR code image
        qr_img = qrcode.make(qr_data)
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        qr_bytes = buffer.getvalue()

        # Insert ticket record (must use app context -- AMQP runs in daemon thread)
        with app.app_context():
            ticket = Ticket(
                booking_id=booking_id,
                event_id=event_id,
                user_id=user_id,
                seat_id=seat_id,
                qr_code_data=qr_data,
                qr_code_image=qr_bytes,
                status='valid'
            )
            db.session.add(ticket)
            db.session.commit()

            ticket_id = ticket.ticket_id
            print(f"[AMQP] Ticket {ticket_id} created for booking {booking_id}")

            # Emit WebSocket notification (lightweight -- no QR image)
            socketio.emit('ticket_ready', {
                'ticket_id': ticket_id,
                'booking_id': booking_id,
                'status': 'ready'
            }, to=str(booking_id))

    except Exception as e:
        print(f"[AMQP] Error processing booking.confirmed: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


# ============================================
# HTTP endpoints
# ============================================

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return success({"status": "healthy"})
    except Exception as e:
        return error(f"Database unreachable: {str(e)}", 503)


@app.route('/tickets/booking/<int:booking_id>')
def get_ticket_by_booking(booking_id):
    """HTTP fallback: retrieve ticket by booking_id with base64 QR image (TICK-03)."""
    ticket = Ticket.query.filter_by(booking_id=booking_id).first()
    if not ticket:
        return error("Ticket not found", 404)

    data = ticket.to_dict()
    if ticket.qr_code_image:
        data['qr_code_base64'] = base64.b64encode(ticket.qr_code_image).decode('utf-8')
    return success(data)


@app.route('/tickets/<int:ticket_id>')
def get_ticket_by_id(ticket_id):
    """Retrieve ticket by ticket_id with base64 QR image."""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return error("Ticket not found", 404)

    data = ticket.to_dict()
    if ticket.qr_code_image:
        data['qr_code_base64'] = base64.b64encode(ticket.qr_code_image).decode('utf-8')
    return success(data)


# ============================================
# AMQP consumer startup
# ============================================

def start_amqp_consumer():
    """Start consuming booking.confirmed messages from booking_topic exchange."""
    start_consumer(
        queue_name='ticket_queue',
        exchange_name='booking_topic',
        routing_keys=['booking.confirmed'],
        callback=handle_booking_confirmed
    )


# ============================================
# Main
# ============================================

if __name__ == '__main__':
    # Start AMQP consumer in daemon thread
    consumer_thread = threading.Thread(target=start_amqp_consumer, daemon=True)
    consumer_thread.start()

    # Use socketio.run() instead of app.run() for WebSocket support
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False, allow_unsafe_werkzeug=True)
