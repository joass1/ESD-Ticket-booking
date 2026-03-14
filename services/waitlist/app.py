import sys
sys.path.insert(0, '/app')

import os
import json
import uuid
import threading
from flask import Flask, request, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from shared.response import success, error
from shared.amqp_lib import connect_with_retry, setup_exchange, publish_message, start_consumer
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
db_name = os.environ.get('DB_NAME', 'waitlist_db')

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


def publish_event(exchange, routing_key, payload):
    """Publish an event to the specified exchange."""
    global amqp_channel
    try:
        if amqp_channel is None or amqp_channel.is_closed:
            conn = connect_with_retry()
            amqp_channel = conn.channel()
            setup_exchange(amqp_channel, 'seat_topic', 'topic')
            setup_exchange(amqp_channel, 'waitlist_topic', 'topic')
            setup_exchange(amqp_channel, 'event_lifecycle', 'topic')
        publish_message(amqp_channel, exchange, routing_key, json.dumps(payload))
        print(f"[Waitlist] Published {routing_key}")
    except Exception as e:
        print(f"[Waitlist] Failed to publish {routing_key}: {e}")
        amqp_channel = None


# ============================================
# Model
# ============================================

class WaitlistEntry(db.Model):
    __tablename__ = 'waitlist_entries'

    entry_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    preferred_section = db.Column(db.String(100), nullable=True)
    position = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='waiting')
    promoted_seat_id = db.Column(db.Integer, nullable=True)
    promotion_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        result = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            if isinstance(val, Decimal):
                val = float(val)
            elif isinstance(val, datetime):
                val = val.isoformat()
            result[col.name] = val
        return result


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


@app.route('/waitlist/join', methods=['POST'])
def join_waitlist():
    """WAIT-01: Join the waitlist for a sold-out event."""
    data = request.get_json()
    if not data:
        return error("Request body is required", 400)

    event_id = data.get('event_id')
    user_id = data.get('user_id')
    email = data.get('email')
    phone = data.get('phone')
    preferred_section = data.get('preferred_section')

    if not all([event_id, user_id, email]):
        return error("event_id, user_id, and email are required", 400)

    try:
        # Check for duplicate
        existing = WaitlistEntry.query.filter_by(
            event_id=event_id, user_id=user_id, status='waiting'
        ).first()
        if existing:
            return error("Already on waitlist for this event", 409)

        # Calculate next position
        max_pos = db.session.query(db.func.max(WaitlistEntry.position)).filter_by(
            event_id=event_id
        ).scalar()
        next_position = (max_pos or 0) + 1

        entry = WaitlistEntry(
            event_id=event_id,
            user_id=str(user_id),
            email=email,
            phone=phone,
            preferred_section=preferred_section,
            position=next_position,
            status='waiting'
        )
        db.session.add(entry)
        db.session.commit()

        return success({
            'entry_id': entry.entry_id,
            'position': entry.position,
            'event_id': event_id
        }, 201)

    except Exception as e:
        db.session.rollback()
        return error(f"Failed to join waitlist: {str(e)}", 500)


@app.route('/waitlist/position/<int:event_id>/<user_id>')
def get_position(event_id, user_id):
    """WAIT-05: Get waitlist position for an event."""
    try:
        entry = WaitlistEntry.query.filter(
            WaitlistEntry.event_id == event_id,
            WaitlistEntry.user_id == str(user_id),
            WaitlistEntry.status.in_(['waiting', 'promoted'])
        ).first()

        if not entry:
            return error("Not on waitlist for this event", 404)

        return success({
            'entry_id': entry.entry_id,
            'position': entry.position,
            'status': entry.status,
            'promoted_seat_id': entry.promoted_seat_id,
            'promotion_expires_at': entry.promotion_expires_at.isoformat() if entry.promotion_expires_at else None
        })

    except Exception as e:
        return error(f"Failed to get position: {str(e)}", 500)


# ============================================
# AMQP Consumer #1: seat.released.* (WAIT-02)
# ============================================

def handle_seat_released(ch, method, properties, body):
    """Promote first-in-line waiting user when a seat is released."""
    try:
        msg = json.loads(body)
        event_id = msg['event_id']
        seat_id = msg['seat_id']
        section = msg.get('section')
        section_id = msg.get('section_id')
        seat_number = msg.get('seat_number')
        source = msg.get('source', 'unknown')

        print(f"[Waitlist] Seat released: event={event_id} seat={seat_id} source={source}")

        with app.app_context():
            # Find first waiting user for this event
            entry = WaitlistEntry.query.filter_by(
                event_id=event_id, status='waiting'
            ).order_by(WaitlistEntry.position.asc()).with_for_update().first()

            if not entry:
                print(f"[Waitlist] No waiting users for event {event_id}, seat stays available")
                return

            # Promote this user
            entry.status = 'promoted'
            entry.promoted_seat_id = seat_id
            entry.promotion_expires_at = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()

            # Request seat reservation via AMQP
            publish_event('seat_topic', 'seat.reserve.request', {
                'event_id': event_id,
                'seat_id': seat_id,
                'user_id': entry.user_id,
                'waitlist_entry_id': entry.entry_id
            })

            # Notify about promotion
            publish_event('waitlist_topic', 'waitlist.promoted', {
                'entry_id': entry.entry_id,
                'event_id': event_id,
                'user_id': entry.user_id,
                'email': entry.email,
                'phone': entry.phone,
                'seat_id': seat_id,
                'section': section,
                'promotion_expires_at': entry.promotion_expires_at.isoformat()
            })

            print(f"[Waitlist] Promoted user {entry.user_id} (entry {entry.entry_id}) for seat {seat_id}")

    except Exception as e:
        print(f"[Waitlist] Error handling seat released: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


# ============================================
# AMQP Consumer #2: seat.reserve.confirmed/failed
# ============================================

def handle_reserve_response(ch, method, properties, body):
    """Handle seat reservation confirmation or failure."""
    try:
        msg = json.loads(body)
        routing_key = method.routing_key
        waitlist_entry_id = msg.get('waitlist_entry_id')

        print(f"[Waitlist] Reserve response: {routing_key} entry={waitlist_entry_id}")

        with app.app_context():
            if 'confirmed' in routing_key:
                # Seat reserved successfully -- promotion complete, user has 10-min window
                print(f"[Waitlist] Seat reserved for entry {waitlist_entry_id}")

            elif 'failed' in routing_key:
                # Seat reservation failed -- revert to waiting, re-publish to try next user
                entry = WaitlistEntry.query.filter_by(
                    entry_id=waitlist_entry_id
                ).with_for_update().first()

                if entry and entry.status == 'promoted':
                    event_id = entry.event_id
                    seat_id = entry.promoted_seat_id

                    entry.status = 'waiting'
                    entry.promoted_seat_id = None
                    entry.promotion_expires_at = None
                    db.session.commit()

                    # Re-publish seat.released to try next waiting user
                    publish_event('seat_topic', f'seat.released.{event_id}', {
                        'event_id': event_id,
                        'seat_id': seat_id,
                        'section': entry.preferred_section,
                        'source': 'waitlist_retry'
                    })

                    print(f"[Waitlist] Reverted entry {waitlist_entry_id}, re-publishing seat.released")

    except Exception as e:
        print(f"[Waitlist] Error handling reserve response: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


# ============================================
# AMQP Consumer #3: event.cancelled.* (WAIT-06 stub)
# ============================================

def handle_cancel(ch, method, properties, body):
    """Cancel all waitlist entries when an event is cancelled (Phase 5 stub)."""
    try:
        msg = json.loads(body)
        event_id = msg.get('event_id')

        print(f"[Waitlist] Event cancelled: event={event_id}")

        with app.app_context():
            entries = WaitlistEntry.query.filter(
                WaitlistEntry.event_id == event_id,
                WaitlistEntry.status.in_(['waiting', 'promoted'])
            ).all()

            for entry in entries:
                entry.status = 'cancelled'

            db.session.commit()
            print(f"[Waitlist] Cancelled {len(entries)} waitlist entries for event {event_id}")

    except Exception as e:
        print(f"[Waitlist] Error handling event cancellation: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


# ============================================
# APScheduler: Promotion Expiry Check (WAIT-03, WAIT-04)
# ============================================

scheduler = BackgroundScheduler(misfire_grace_time=60)


def check_expired_promotions():
    """Check for expired promotions and cascade to next waiting user."""
    with app.app_context():
        try:
            expired_entries = WaitlistEntry.query.filter(
                WaitlistEntry.status == 'promoted',
                WaitlistEntry.promotion_expires_at <= datetime.utcnow()
            ).all()

            for entry in expired_entries:
                event_id = entry.event_id
                seat_id = entry.promoted_seat_id

                entry.status = 'expired'
                db.session.commit()

                # Request Seat service to actually release the seat (WAIT-04)
                publish_event('seat_topic', 'seat.release.request', {
                    'event_id': event_id,
                    'seat_id': seat_id,
                    'user_id': entry.user_id
                })

                # Notify about expiration
                publish_event('waitlist_topic', 'waitlist.expired', {
                    'entry_id': entry.entry_id,
                    'event_id': event_id,
                    'user_id': entry.user_id,
                    'email': entry.email
                })

                print(f"[Waitlist] Expired promotion for entry {entry.entry_id}, cascading seat {seat_id}")

        except Exception as e:
            print(f"[Waitlist] Error checking expired promotions: {e}")


scheduler.add_job(check_expired_promotions, 'interval', seconds=30, id='check_expired_promotions')


# ============================================
# Consumer Startup
# ============================================

def start_all_consumers():
    """Start all AMQP consumers in separate daemon threads."""
    threading.Thread(
        target=lambda: start_consumer(
            'waitlist_queue', 'seat_topic',
            ['seat.released.*'], handle_seat_released
        ), daemon=True
    ).start()

    threading.Thread(
        target=lambda: start_consumer(
            'waitlist_confirm_queue', 'seat_topic',
            ['seat.reserve.confirmed', 'seat.reserve.failed'], handle_reserve_response
        ), daemon=True
    ).start()

    threading.Thread(
        target=lambda: start_consumer(
            'waitlist_cancel_queue', 'event_lifecycle',
            ['event.cancelled.*'], handle_cancel
        ), daemon=True
    ).start()


if __name__ == '__main__':
    scheduler.start()
    start_all_consumers()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5007)), debug=False)
