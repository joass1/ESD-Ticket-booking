import sys
sys.path.insert(0, '/app')

import os
import json
import threading
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from shared.response import success, error
from shared.amqp_lib import connect_with_retry, setup_exchange, publish_message, start_consumer, run_with_amqp
from datetime import datetime
from decimal import Decimal
import redis

app = Flask(__name__)
CORS(app)

# Database configuration
db_host = os.environ.get('DB_HOST', 'mysql')
db_port = os.environ.get('DB_PORT', '3306')
db_user = os.environ.get('DB_USER', 'root')
db_password = os.environ.get('DB_PASSWORD', 'root')
db_name = os.environ.get('DB_NAME', 'seat_db')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    '?charset=utf8mb4'
)
app.config['SQLALCHEMY_POOL_SIZE'] = 5
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
app.config['SQLALCHEMY_POOL_PRE_PING'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Redis client setup
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    decode_responses=True
)


# AMQP connection for publishing (dedicated connection, separate from consumer threads)
amqp_channel = None


def publish_seat_event(routing_key, payload):
    """Publish a seat event to seat_topic exchange."""
    global amqp_channel
    try:
        if amqp_channel is None or amqp_channel.is_closed:
            conn = connect_with_retry()
            amqp_channel = conn.channel()
            setup_exchange(amqp_channel, 'seat_topic', 'topic')
        publish_message(amqp_channel, 'seat_topic', routing_key, json.dumps(payload))
        print(f"[Seat] Published {routing_key}")
    except Exception as e:
        print(f"[Seat] Failed to publish {routing_key}: {e}")
        amqp_channel = None


def publish_availability_update(event_id):
    """Publish current total available seat count for an event to seat_topic.

    Consumed by the Event Service to keep its available_seats field accurate.
    """
    try:
        total_available = db.session.query(
            db.func.sum(Section.available_seats)
        ).filter_by(event_id=event_id).scalar() or 0
        publish_seat_event(f'seat.availability.updated.{event_id}', {
            'event_id': event_id,
            'available_seats': int(total_available)
        })
    except Exception as e:
        print(f"[Seat] Failed to publish availability update for event {event_id}: {e}")


# ============================================
# Models
# ============================================

class Section(db.Model):
    __tablename__ = 'sections'

    section_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            'section_id': self.section_id,
            'event_id': self.event_id,
            'name': self.name,
            'price': float(self.price) if isinstance(self.price, Decimal) else self.price,
            'total_seats': self.total_seats,
            'available_seats': self.available_seats
        }


class Seat(db.Model):
    __tablename__ = 'seats'

    seat_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, nullable=False)
    section_id = db.Column(db.Integer, nullable=False)
    seat_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='available')
    reserved_by = db.Column(db.String(100), nullable=True)
    reserved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        result = {
            'seat_id': self.seat_id,
            'event_id': self.event_id,
            'section_id': self.section_id,
            'seat_number': self.seat_number,
            'status': self.status,
            'reserved_by': self.reserved_by,
            'reserved_at': self.reserved_at.isoformat() if self.reserved_at else None
        }
        return result


# ============================================
# Helper Functions
# ============================================

def _extract_seat_num(seat_number):
    """Extract numeric part after hyphen: 'VIP-005' -> 5, 'A-025' -> 25."""
    return int(seat_number.split('-')[1])


# ============================================
# Redis Lock Functions
# ============================================

def acquire_seat_lock(event_id, seat_id, user_id, ttl=600):
    """Acquire a distributed lock on a seat using Redis SET NX EX.

    Returns True if lock acquired, None if already held by another user.
    """
    key = f"seat:{event_id}:{seat_id}"
    return redis_client.set(key, str(user_id), nx=True, ex=ttl)


def release_seat_lock(event_id, seat_id, user_id):
    """Release a seat lock only if the caller is the current owner.

    Returns True if released, False if not owner or no lock exists.
    """
    key = f"seat:{event_id}:{seat_id}"
    current = redis_client.get(key)
    if current == str(user_id):
        redis_client.delete(key)
        return True
    return False


def remove_seat_lock(event_id, seat_id):
    """Unconditionally remove a seat lock (used for cleanup after MySQL failure)."""
    redis_client.delete(f"seat:{event_id}:{seat_id}")


# ============================================
# Endpoints
# ============================================

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return success({"status": "healthy"})
    except Exception as e:
        return error(f"Database unreachable: {str(e)}", 503)


@app.route('/seats/event/<int:event_id>')
def get_seats_by_event(event_id):
    """SEAT-01: Get all seats for an event with section info."""
    try:
        seats = db.session.query(Seat, Section).join(
            Section,
            db.and_(Seat.section_id == Section.section_id, Seat.event_id == Section.event_id)
        ).filter(
            Seat.event_id == event_id
        ).order_by(
            Seat.section_id, Seat.seat_number
        ).all()

        result = []
        for seat, section in seats:
            seat_dict = seat.to_dict()
            seat_dict['section_name'] = section.name
            seat_dict['section_price'] = float(section.price) if isinstance(section.price, Decimal) else section.price
            result.append(seat_dict)

        return success(result)
    except Exception as e:
        return error(f"Failed to retrieve seats: {str(e)}", 500)


@app.route('/seats/availability/<int:event_id>')
def get_availability(event_id):
    """SEAT-02: Get available seat count per section for an event."""
    try:
        sections = Section.query.filter_by(event_id=event_id).all()

        if not sections:
            return error("No sections found for this event", 404)

        section_list = [s.to_dict() for s in sections]
        total_available = sum(s.available_seats for s in sections)
        total_seats = sum(s.total_seats for s in sections)

        return success({
            'event_id': event_id,
            'total_available': total_available,
            'total_seats': total_seats,
            'sections': section_list
        })
    except Exception as e:
        return error(f"Failed to retrieve availability: {str(e)}", 500)


@app.route('/seats/reserve', methods=['POST'])
def reserve_seat():
    """SEAT-03, SEAT-04: Reserve a seat with dual-lock and auto-assignment."""
    data = request.get_json()
    if not data:
        return error("Request body is required", 400)

    event_id = data.get('event_id')
    seat_id = data.get('seat_id')
    user_id = data.get('user_id')

    if not all([event_id, seat_id, user_id]):
        return error("event_id, seat_id, and user_id are required", 400)

    try:
        # Look up the requested seat to get section_id and seat_number
        requested_seat = Seat.query.filter_by(
            seat_id=seat_id, event_id=event_id
        ).first()

        if not requested_seat:
            return error("Seat not found", 404)

        target_section_id = requested_seat.section_id
        requested_num = _extract_seat_num(requested_seat.seat_number)

        # Step 1: Try to acquire Redis lock on requested seat
        lock_acquired = acquire_seat_lock(event_id, seat_id, user_id)

        if lock_acquired:
            # Step 2: MySQL SELECT FOR UPDATE on that seat
            try:
                seat = db.session.query(Seat).filter_by(
                    seat_id=seat_id, event_id=event_id
                ).with_for_update().first()

                if seat and seat.status == 'available':
                    # Reserve the seat
                    seat.status = 'reserved'
                    seat.reserved_by = str(user_id)
                    seat.reserved_at = datetime.utcnow()

                    # Decrement section available_seats
                    section = db.session.query(Section).filter_by(
                        section_id=target_section_id, event_id=event_id
                    ).with_for_update().first()

                    if section and section.available_seats > 0:
                        section.available_seats -= 1

                    db.session.commit()
                    publish_availability_update(event_id)

                    seat_dict = seat.to_dict()
                    seat_dict['auto_assigned'] = False
                    seat_dict['section_price'] = float(section.price) if section else None
                    return success(seat_dict, 200)
                else:
                    # Seat not available in MySQL (stale) -- release Redis lock, fall through
                    db.session.rollback()
                    remove_seat_lock(event_id, seat_id)
            except Exception:
                db.session.rollback()
                remove_seat_lock(event_id, seat_id)
                raise

        # Step 3: Auto-assign -- find nearest available seat in same section
        # Use FOR UPDATE SKIP LOCKED to avoid deadlocks with concurrent reservations
        available_seats = db.session.query(Seat).filter(
            Seat.event_id == event_id,
            Seat.section_id == target_section_id,
            Seat.status == 'available'
        ).with_for_update(skip_locked=True).all()

        if not available_seats:
            db.session.rollback()
            # No seats in this section -- suggest other sections
            other_sections = Section.query.filter(
                Section.event_id == event_id,
                Section.section_id != target_section_id,
                Section.available_seats > 0
            ).all()

            section = Section.query.filter_by(
                section_id=target_section_id, event_id=event_id
            ).first()
            section_name = section.name if section else f"Section {target_section_id}"

            response_data = {"message": f"No available seats in {section_name}"}
            if other_sections:
                response_data['other_sections'] = [s.to_dict() for s in other_sections]
            return make_response(jsonify({"code": 409, **response_data}), 409)

        # Sort by distance from requested seat number
        available_seats.sort(key=lambda s: abs(_extract_seat_num(s.seat_number) - requested_num))

        # Try each candidate seat
        for candidate in available_seats:
            candidate_lock = acquire_seat_lock(event_id, candidate.seat_id, user_id)
            if candidate_lock:
                try:
                    candidate.status = 'reserved'
                    candidate.reserved_by = str(user_id)
                    candidate.reserved_at = datetime.utcnow()

                    # Decrement section available_seats
                    section = db.session.query(Section).filter_by(
                        section_id=target_section_id, event_id=event_id
                    ).with_for_update().first()

                    if section and section.available_seats > 0:
                        section.available_seats -= 1

                    db.session.commit()
                    publish_availability_update(event_id)

                    seat_dict = candidate.to_dict()
                    seat_dict['auto_assigned'] = True
                    seat_dict['originally_requested'] = seat_id
                    seat_dict['section_price'] = float(section.price) if section else None
                    return success(seat_dict, 200)
                except Exception:
                    db.session.rollback()
                    remove_seat_lock(event_id, candidate.seat_id)
                    raise

        # All candidates had Redis locks held by others
        db.session.rollback()
        other_sections = Section.query.filter(
            Section.event_id == event_id,
            Section.section_id != target_section_id,
            Section.available_seats > 0
        ).all()

        section = Section.query.filter_by(
            section_id=target_section_id, event_id=event_id
        ).first()
        section_name = section.name if section else f"Section {target_section_id}"

        response_data = {"message": f"No available seats in {section_name}"}
        if other_sections:
            response_data['other_sections'] = [s.to_dict() for s in other_sections]

        return make_response(jsonify({"code": 409, **response_data}), 409)

    except Exception as e:
        db.session.rollback()
        return error(f"Reservation failed: {str(e)}", 500)


@app.route('/seats/release', methods=['POST'])
def release_seat():
    """SEAT-05: Release a reserved seat (verifies lock ownership)."""
    data = request.get_json()
    if not data:
        return error("Request body is required", 400)

    event_id = data.get('event_id')
    seat_id = data.get('seat_id')
    user_id = data.get('user_id')

    if not all([event_id, seat_id, user_id]):
        return error("event_id, seat_id, and user_id are required", 400)

    try:
        # Verify Redis lock ownership
        if not release_seat_lock(event_id, seat_id, user_id):
            return error("Not the lock owner", 403)

        # MySQL: reset seat to available
        seat = db.session.query(Seat).filter_by(
            seat_id=seat_id, event_id=event_id
        ).with_for_update().first()

        if not seat:
            return error("Seat not found", 404)

        section_id = seat.section_id

        seat.status = 'available'
        seat.reserved_by = None
        seat.reserved_at = None

        # Increment section available_seats
        section = db.session.query(Section).filter_by(
            section_id=section_id, event_id=event_id
        ).with_for_update().first()

        if section:
            section.available_seats += 1

        db.session.commit()
        publish_availability_update(event_id)

        # SEAT-08: Publish seat.released event for waitlist promotion
        publish_seat_event(f'seat.released.{event_id}', {
            'event_id': event_id,
            'seat_id': seat_id,
            'section': section.name if section else None,
            'section_id': section_id,
            'seat_number': seat.seat_number,
            'source': 'seat_release'
        })

        return success({'seat_id': seat_id, 'status': 'released'})

    except Exception as e:
        db.session.rollback()
        return error(f"Release failed: {str(e)}", 500)


@app.route('/seats/confirm', methods=['POST'])
def confirm_seat():
    """SEAT-06: Confirm a reserved seat (changes to booked, removes Redis lock)."""
    data = request.get_json()
    if not data:
        return error("Request body is required", 400)

    event_id = data.get('event_id')
    seat_id = data.get('seat_id')
    user_id = data.get('user_id')

    if not all([event_id, seat_id, user_id]):
        return error("event_id, seat_id, and user_id are required", 400)

    try:
        # MySQL: set status to booked WHERE currently reserved
        seat = db.session.query(Seat).filter_by(
            seat_id=seat_id, event_id=event_id
        ).with_for_update().first()

        if not seat:
            return error("Seat not found", 404)

        if seat.status != 'reserved':
            return error(
                f"Seat cannot be confirmed (current status: {seat.status})",
                409
            )

        seat.status = 'booked'
        db.session.commit()

        # Remove Redis lock -- reservation is now permanent
        remove_seat_lock(event_id, seat_id)

        return success(seat.to_dict())

    except Exception as e:
        db.session.rollback()
        return error(f"Confirmation failed: {str(e)}", 500)


# ============================================
# AMQP Consumer: seat.reserve.request
# ============================================

def handle_reserve_request(ch, method, properties, body):
    """Handle seat reservation requests from Waitlist Service via AMQP."""
    try:
        msg = json.loads(body)
        event_id = msg['event_id']
        seat_id = msg['seat_id']
        user_id = msg['user_id']
        waitlist_entry_id = msg.get('waitlist_entry_id')

        print(f"[Seat] Reserve request: event={event_id} seat={seat_id} user={user_id}")

        with app.app_context():
            # Try to acquire Redis lock
            lock_acquired = acquire_seat_lock(event_id, seat_id, user_id)
            if not lock_acquired:
                publish_seat_event('seat.reserve.failed', {
                    'waitlist_entry_id': waitlist_entry_id,
                    'event_id': event_id,
                    'seat_id': seat_id,
                    'reason': 'lock_unavailable'
                })
                return

            try:
                seat = db.session.query(Seat).filter_by(
                    seat_id=seat_id, event_id=event_id
                ).with_for_update().first()

                if seat and seat.status == 'available':
                    seat.status = 'reserved'
                    seat.reserved_by = str(user_id)
                    seat.reserved_at = datetime.utcnow()

                    section = db.session.query(Section).filter_by(
                        section_id=seat.section_id, event_id=event_id
                    ).with_for_update().first()

                    if section and section.available_seats > 0:
                        section.available_seats -= 1

                    db.session.commit()

                    publish_seat_event('seat.reserve.confirmed', {
                        'waitlist_entry_id': waitlist_entry_id,
                        'event_id': event_id,
                        'seat_id': seat_id,
                        'user_id': user_id,
                        'section_price': float(section.price) if section else None
                    })
                    print(f"[Seat] Reserve confirmed: seat={seat_id}")
                else:
                    db.session.rollback()
                    remove_seat_lock(event_id, seat_id)
                    publish_seat_event('seat.reserve.failed', {
                        'waitlist_entry_id': waitlist_entry_id,
                        'event_id': event_id,
                        'seat_id': seat_id,
                        'reason': 'seat_unavailable'
                    })
                    print(f"[Seat] Reserve failed: seat={seat_id} unavailable")
            except Exception as e:
                db.session.rollback()
                remove_seat_lock(event_id, seat_id)
                publish_seat_event('seat.reserve.failed', {
                    'waitlist_entry_id': waitlist_entry_id,
                    'event_id': event_id,
                    'seat_id': seat_id,
                    'reason': str(e)
                })
                print(f"[Seat] Reserve error: {e}")
    except Exception as e:
        print(f"[Seat] Error handling reserve request: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def handle_event_cancelled(ch, method, properties, body):
    """SEAT-07: Bulk-reset all reserved/booked seats and clear Redis locks when event is cancelled."""
    try:
        msg = json.loads(body)
        event_id = msg['event_id']

        print(f"[Seat] Event cancelled: event={event_id}")

        with app.app_context():
            # Find all reserved/booked seats for this event
            seats = Seat.query.filter(
                Seat.event_id == event_id,
                Seat.status.in_(['reserved', 'booked'])
            ).all()

            for seat in seats:
                seat.status = 'available'
                seat.reserved_by = None
                seat.reserved_at = None
                remove_seat_lock(event_id, seat.seat_id)

            # Recalculate section availability
            sections = Section.query.filter_by(event_id=event_id).all()
            for section in sections:
                available_count = Seat.query.filter_by(
                    event_id=event_id, section_id=section.section_id, status='available'
                ).count()
                section.available_seats = available_count

            db.session.commit()
            print(f"[Seat] Reset {len(seats)} seats to available for event {event_id}")

    except Exception as e:
        print(f"[Seat] Error handling event cancellation: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def handle_release_request(ch, method, properties, body):
    """Handle seat.release.request from Waitlist Service (waitlist expiry).

    Releases the seat in MySQL, clears the Redis lock, and publishes
    seat.released.{event_id} so the next waiting user can be promoted.
    """
    try:
        msg = json.loads(body)
        event_id = msg['event_id']
        seat_id = msg['seat_id']
        user_id = msg['user_id']

        print(f"[Seat] Release request (waitlist expiry): event={event_id} seat={seat_id} user={user_id}")

        with app.app_context():
            # Only release if currently reserved by this user
            seat = db.session.query(Seat).filter_by(
                seat_id=seat_id, event_id=event_id
            ).with_for_update().first()

            if not seat:
                print(f"[Seat] Release request: seat {seat_id} not found")
                return

            if seat.status != 'reserved' or seat.reserved_by != str(user_id):
                print(f"[Seat] Release request: seat {seat_id} not reserved by user {user_id}, skipping")
                return

            section_id = seat.section_id
            seat.status = 'available'
            seat.reserved_by = None
            seat.reserved_at = None

            section = db.session.query(Section).filter_by(
                section_id=section_id, event_id=event_id
            ).with_for_update().first()

            if section:
                section.available_seats += 1

            db.session.commit()
            remove_seat_lock(event_id, seat_id)

            # Publish seat.released so the next waiting user gets promoted
            publish_seat_event(f'seat.released.{event_id}', {
                'event_id': event_id,
                'seat_id': seat_id,
                'section': section.name if section else None,
                'section_id': section_id,
                'seat_number': seat.seat_number,
                'source': 'waitlist_expiry_release'
            })
            print(f"[Seat] Released seat {seat_id} for expired waitlist promotion")

    except Exception as e:
        print(f"[Seat] Error handling release request: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_seat_consumers():
    """Start AMQP consumers for seat reserve requests and event cancellation."""
    threading.Thread(
        target=lambda: start_consumer(
            'seat_reserve_queue', 'seat_topic',
            ['seat.reserve.request'], handle_reserve_request
        ), daemon=True
    ).start()

    threading.Thread(
        target=lambda: start_consumer(
            'seat_release_request_queue', 'seat_topic',
            ['seat.release.request'], handle_release_request
        ), daemon=True
    ).start()

    threading.Thread(
        target=lambda: start_consumer(
            'seat_cancel_queue', 'event_lifecycle',
            ['event.cancelled.*'], handle_event_cancelled
        ), daemon=True
    ).start()


if __name__ == '__main__':
    start_seat_consumers()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5003)), debug=False)
