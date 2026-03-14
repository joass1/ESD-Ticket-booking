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
db_name = os.environ.get('DB_NAME', 'event_db')

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


def publish_event_lifecycle(routing_key, payload):
    """Publish an event lifecycle message to event_lifecycle exchange."""
    global amqp_channel
    try:
        if amqp_channel is None or amqp_channel.is_closed:
            conn = connect_with_retry()
            amqp_channel = conn.channel()
            setup_exchange(amqp_channel, 'event_lifecycle', 'topic')
        publish_message(amqp_channel, 'event_lifecycle', routing_key, json.dumps(payload))
        print(f"[Event] Published {routing_key}")
    except Exception as e:
        print(f"[Event] Failed to publish {routing_key}: {e}")
        amqp_channel = None


# ============================================
# Model
# ============================================

class Event(db.Model):
    __tablename__ = 'events'

    event_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    event_date = db.Column(db.DateTime, nullable=False)
    venue = db.Column(db.String(255))
    status = db.Column(db.String(20), default='upcoming')
    total_seats = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    price_min = db.Column(db.Numeric(10, 2))
    price_max = db.Column(db.Numeric(10, 2))
    image_url = db.Column(db.String(500))
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


@app.route('/events')
def get_events():
    """List events with optional filters: status, category, date_from, date_to."""
    query = db.select(Event)

    # Apply filters from query params
    status = request.args.get('status')
    if status:
        query = query.where(Event.status == status)

    category = request.args.get('category')
    if category:
        query = query.where(Event.category == category)

    date_from = request.args.get('date_from')
    if date_from:
        query = query.where(Event.event_date >= date_from)

    date_to = request.args.get('date_to')
    if date_to:
        query = query.where(Event.event_date <= date_to)

    # Default sort by event_date ascending
    query = query.order_by(Event.event_date.asc())

    events = db.session.execute(query).scalars().all()
    return success([e.to_dict() for e in events])


@app.route('/events/<int:event_id>')
def get_event(event_id):
    """Get a single event by ID."""
    event = db.session.execute(
        db.select(Event).where(Event.event_id == event_id)
    ).scalar_one_or_none()

    if not event:
        return error("Event not found", 404)

    return success(event.to_dict())


@app.route('/events', methods=['POST'])
def create_event():
    """Admin create event. Required fields: name, event_date, total_seats."""
    data = request.get_json()
    if not data:
        return error("Invalid JSON", 400)

    required = ['name', 'event_date', 'total_seats']
    for field in required:
        if field not in data:
            return error(f"Missing required field: {field}", 400)

    event = Event(
        name=data['name'],
        description=data.get('description'),
        category=data.get('category'),
        event_date=data['event_date'],
        venue=data.get('venue'),
        status=data.get('status', 'upcoming'),
        total_seats=data['total_seats'],
        available_seats=data['total_seats'],
        price_min=data.get('price_min'),
        price_max=data.get('price_max'),
        image_url=data.get('image_url')
    )

    try:
        db.session.add(event)
        db.session.commit()
        return success(event.to_dict(), 201)
    except Exception as e:
        db.session.rollback()
        return error(f"Failed to create event: {str(e)}", 500)


@app.route('/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    """Admin update event. Update only provided fields."""
    event = db.session.execute(
        db.select(Event).where(Event.event_id == event_id)
    ).scalar_one_or_none()

    if not event:
        return error("Event not found", 404)

    data = request.get_json()
    if not data:
        return error("Invalid JSON", 400)

    # Update only provided fields
    updatable_fields = [
        'name', 'description', 'category', 'event_date', 'venue',
        'status', 'total_seats', 'available_seats', 'price_min',
        'price_max', 'image_url'
    ]
    for field in updatable_fields:
        if field in data:
            setattr(event, field, data[field])

    try:
        db.session.commit()
        return success(event.to_dict())
    except Exception as e:
        db.session.rollback()
        return error(f"Failed to update event: {str(e)}", 500)


@app.route('/events/<int:event_id>/cancel', methods=['POST'])
def cancel_event(event_id):
    """EVNT-03: Cancel an event and publish event.cancelled to fan-out consumers."""
    event = db.session.execute(
        db.select(Event).where(Event.event_id == event_id)
    ).scalar_one_or_none()

    if not event:
        return error("Event not found", 404)

    if event.status not in ('upcoming', 'ongoing'):
        return error(f"Event cannot be cancelled (status: {event.status})", 409)

    try:
        event.status = 'cancelled'
        db.session.commit()

        publish_event_lifecycle(f'event.cancelled.{event_id}', {
            'event_id': event_id,
            'event_name': event.name
        })

        return success({'event_id': event_id, 'status': 'cancelled'})
    except Exception as e:
        db.session.rollback()
        return error(f"Failed to cancel event: {str(e)}", 500)


# ============================================
# AMQP Consumer: seat.availability.updated
# ============================================

def handle_availability_updated(ch, method, properties, body):
    """Sync event.available_seats when Seat service reports a change."""
    try:
        msg = json.loads(body)
        event_id = msg['event_id']
        available_seats = msg['available_seats']

        print(f"[Event] Availability update: event={event_id} available={available_seats}")

        with app.app_context():
            event = db.session.execute(
                db.select(Event).where(Event.event_id == event_id)
            ).scalar_one_or_none()

            if event:
                event.available_seats = available_seats
                db.session.commit()
                print(f"[Event] Updated available_seats={available_seats} for event {event_id}")
            else:
                print(f"[Event] Event {event_id} not found, skipping availability update")

    except Exception as e:
        print(f"[Event] Error handling availability update: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_event_consumers():
    """Start AMQP consumers for the Event service."""
    threading.Thread(
        target=lambda: start_consumer(
            'event_availability_queue', 'seat_topic',
            ['seat.availability.updated'], handle_availability_updated
        ), daemon=True
    ).start()


if __name__ == '__main__':
    start_event_consumers()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)
