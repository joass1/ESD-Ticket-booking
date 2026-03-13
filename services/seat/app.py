import sys
sys.path.insert(0, '/app')

import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from shared.response import success, error
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

                    seat_dict = seat.to_dict()
                    seat_dict['auto_assigned'] = False
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

                    seat_dict = candidate.to_dict()
                    seat_dict['auto_assigned'] = True
                    seat_dict['originally_requested'] = seat_id
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5003)), debug=False)
