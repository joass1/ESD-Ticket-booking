import sys
sys.path.insert(0, '/app')

import os
import json
import uuid
import threading
import requests
from flask import Flask, request, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from shared.response import success, error
from shared.amqp_lib import start_consumer

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
db_name = os.environ.get('DB_NAME', 'notification_db')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    '?charset=utf8mb4'
)
app.config['SQLALCHEMY_POOL_SIZE'] = 5
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
app.config['SQLALCHEMY_POOL_PRE_PING'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# SMU Lab Notification API
NOTI_BASE_URL = os.environ['SMU_NOTI_BASE_URL']
NOTI_HEADERS = {
    "X-Contacts-Key": os.environ['SMU_NOTI_API_KEY'],
    "Content-Type": "application/json"
}


# ============================================
# Event-Channel Mapping
# ============================================

EVENT_CHANNEL_MAP = {
    'booking.confirmed': ['email', 'sms'],     # NOTF-01
    'booking.timeout': ['email'],             # NOTF-02
    'booking.refund.requested': ['email'],    # Cancellation email to user
    'waitlist.promoted': ['email', 'sms'],    # NOTF-03
    'waitlist.expired': ['email', 'sms'],     # Informational
    'event.cancelled': ['email'],             # NOTF-04 (Phase 5 stub)
    'refund.completed': ['email', 'sms'],     # NOTF-05
}


# ============================================
# SQLAlchemy Model
# ============================================

class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    channel = db.Column(db.Enum('email', 'sms'), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(255))
    body = db.Column(db.Text)
    status = db.Column(db.Enum('sent', 'failed', 'pending'), default='pending')
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        result = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            if hasattr(val, 'isoformat'):
                val = val.isoformat()
            result[col.name] = val
        return result


# ============================================
# Notification Templates
# ============================================

def get_email_template(event_type, data):
    """Return (subject, html_body) tuple for a given event type."""
    if event_type == 'booking.confirmed':
        booking_id = data.get('booking_id', 'N/A')
        event_id = data.get('event_id', 'N/A')
        seat_id = data.get('seat_id', 'N/A')
        amount = data.get('amount', 'N/A')
        subject = f"Booking Confirmed - #{booking_id}"
        body = f"""
        <h2>Booking Confirmed!</h2>
        <p>Your booking <strong>#{booking_id}</strong> has been confirmed.</p>
        <ul>
            <li><strong>Event ID:</strong> {event_id}</li>
            <li><strong>Seat ID:</strong> {seat_id}</li>
            <li><strong>Amount Paid:</strong> ${amount}</li>
        </ul>
        <p>Your e-ticket will be delivered shortly. Thank you for your purchase!</p>
        """
        return subject, body

    elif event_type == 'booking.timeout':
        event_id = data.get('event_id', 'N/A')
        seat_id = data.get('seat_id', 'N/A')
        subject = "Booking Expired"
        body = f"""
        <h2>Booking Expired</h2>
        <p>Your booking for Event #{event_id} (Seat {seat_id}) has expired because the payment window closed.</p>
        <p>The seat has been released back to the pool. You may try booking again.</p>
        """
        return subject, body

    elif event_type == 'booking.refund.requested':
        booking_id = data.get('booking_id', 'N/A')
        event_id = data.get('event_id', 'N/A')
        amount = data.get('amount', 'N/A')
        refund_type = data.get('refund_type', 'event_cancelled')

        if refund_type == 'voluntary':
            subject = f"Refund Requested - Booking #{booking_id}"
            body = f"""
            <h2>Refund Requested</h2>
            <p>Your refund request for booking <strong>#{booking_id}</strong> has been received.</p>
            <ul>
                <li><strong>Event ID:</strong> {event_id}</li>
                <li><strong>Original Amount:</strong> ${amount}</li>
            </ul>
            <p>A 10% service fee will be deducted from your refund. You will receive a confirmation once processing is complete.</p>
            """
        else:
            subject = f"Event Cancelled - Refund Incoming (Booking #{booking_id})"
            body = f"""
            <h2>Event Cancelled</h2>
            <p>We're sorry to inform you that Event #{event_id} has been cancelled.</p>
            <p>Your booking <strong>#{booking_id}</strong> will be fully refunded with no service fee.</p>
            <ul>
                <li><strong>Amount:</strong> ${amount}</li>
            </ul>
            <p>Your refund is being processed and you will receive a confirmation once it is complete.</p>
            """
        return subject, body

    elif event_type == 'waitlist.promoted':
        event_id = data.get('event_id', 'N/A')
        seat_id = data.get('seat_id', 'N/A')
        section = data.get('section', 'N/A')
        expires_at = data.get('promotion_expires_at', '10 minutes')
        subject = "Seat Available! Book within 10 minutes"
        body = f"""
        <h2>A Seat is Now Available!</h2>
        <p>Great news! A seat has opened up for Event #{event_id}.</p>
        <ul>
            <li><strong>Section:</strong> {section}</li>
            <li><strong>Seat ID:</strong> {seat_id}</li>
            <li><strong>Expires At:</strong> {expires_at}</li>
        </ul>
        <p><strong>Act fast!</strong> You have 10 minutes to complete your booking before this offer expires.</p>
        """
        return subject, body

    elif event_type == 'waitlist.expired':
        event_id = data.get('event_id', 'N/A')
        subject = "Waitlist Promotion Expired"
        body = f"""
        <h2>Promotion Expired</h2>
        <p>Your waitlist promotion for Event #{event_id} has expired as the booking window closed.</p>
        <p>You remain on the waitlist and will be notified if another seat becomes available.</p>
        """
        return subject, body

    elif event_type == 'event.cancelled':
        event_id = data.get('event_id', 'N/A')
        subject = "Event Cancelled - Refund Processing"
        body = f"""
        <h2>Event Cancelled</h2>
        <p>We regret to inform you that Event #{event_id} has been cancelled.</p>
        <p>A refund will be processed to your original payment method shortly.</p>
        """
        return subject, body

    elif event_type == 'refund.completed':
        booking_id = data.get('booking_id', 'N/A')
        original_amount = data.get('original_amount', 'N/A')
        service_fee = data.get('service_fee', 0)
        refund_amount = data.get('refund_amount', original_amount)
        refund_type = data.get('refund_type', 'voluntary')

        if refund_type == 'event_cancelled':
            subject = "Full Refund Processed"
            body = f"""
            <h2>Full Refund Processed</h2>
            <p>Your refund for booking <strong>#{booking_id}</strong> has been processed.</p>
            <ul>
                <li><strong>Full Refund:</strong> ${refund_amount}</li>
            </ul>
            <p>No service fee was charged as the event was cancelled by the organizer.</p>
            <p>Please allow 5-10 business days for the refund to appear on your statement.</p>
            """
        else:
            subject = "Refund Processed"
            body = f"""
            <h2>Refund Processed</h2>
            <p>Your refund for booking <strong>#{booking_id}</strong> has been processed.</p>
            <ul>
                <li><strong>Original Amount:</strong> ${original_amount}</li>
                <li><strong>Processing Fee (10%):</strong> ${service_fee}</li>
                <li><strong>Net Refund:</strong> ${refund_amount}</li>
            </ul>
            <p>Please allow 5-10 business days for the refund to appear on your statement.</p>
            """
        return subject, body

    else:
        subject = f"Notification - {event_type}"
        body = f"<p>Event: {event_type}</p><p>Details: {json.dumps(data)}</p>"
        return subject, body


def get_sms_template(event_type, data):
    """Return SMS body text for a given event type."""
    if event_type == 'booking.confirmed':
        booking_id = data.get('booking_id', 'N/A')
        event_id = data.get('event_id', 'N/A')
        seat_id = data.get('seat_id', 'N/A')
        amount = data.get('amount', 'N/A')
        return f"Booking #{booking_id} confirmed! Event #{event_id}, Seat #{seat_id}, ${amount}. Check your email for your e-ticket and QR code."
    elif event_type == 'waitlist.promoted':
        return "A Seat is Available, Book within 10 minutes!"
    elif event_type == 'waitlist.expired':
        return "Your promotion has expired. The seat has been released to the next person in the waitlist."
    elif event_type == 'refund.completed':
        amount = data.get('amount', 'N/A')
        return f"Full refund of ${amount} processed. Check your email for details."
    else:
        return f"Notification: {event_type}. Check your email for details."


# ============================================
# Email Sender
# ============================================

def send_email(to, subject, html_body, event_type, user_id):
    """Send email via SMU Lab Notification API."""
    with app.app_context():
        log = NotificationLog(
            user_id=user_id,
            email=to,
            channel='email',
            event_type=event_type,
            subject=subject,
            body=html_body,
            status='pending'
        )

        try:
            resp = requests.post(
                f"{NOTI_BASE_URL}/SendEmail",
                headers=NOTI_HEADERS,
                json={"emailAddress": to, "emailSubject": subject, "emailBody": html_body},
                timeout=10
            )
            if resp.ok:
                log.status = 'sent'
                print(f"[NOTIFICATION] Email sent: {event_type} -> {to}")
            else:
                log.status = 'failed'
                log.error_message = resp.text
                print(f"[NOTIFICATION] Email failed ({resp.status_code}): {event_type} -> {to}")
        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            print(f"[NOTIFICATION] Email failed: {event_type} -> {to}: {e}")

        db.session.add(log)
        db.session.commit()


# ============================================
# SMS Sender (SMU Lab API)
# ============================================

def send_sms(to, body, event_type, user_id):
    """Send SMS via SMU Lab Notification API."""
    with app.app_context():
        log = NotificationLog(
            user_id=user_id,
            phone=to,
            channel='sms',
            event_type=event_type,
            subject=None,
            body=body,
            status='pending'
        )

        try:
            resp = requests.post(
                f"{NOTI_BASE_URL}/SendSMS",
                headers=NOTI_HEADERS,
                json={"mobile": to, "message": body},
                timeout=10
            )
            if resp.ok:
                log.status = 'sent'
                print(f"[NOTIFICATION] SMS sent: {event_type} -> {to}")
            else:
                log.status = 'failed'
                log.error_message = resp.text
                print(f"[NOTIFICATION] SMS failed ({resp.status_code}): {event_type} -> {to}")
        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            print(f"[NOTIFICATION] SMS failed: {event_type} -> {to}: {e}")

        db.session.add(log)
        db.session.commit()


# ============================================
# AMQP Consumer Callbacks
# ============================================

def handle_booking_event(ch, method, properties, body):
    """Handle booking.confirmed (NOTF-01) and booking.timeout (NOTF-02) events."""
    try:
        data = json.loads(body)
        event_type = method.routing_key
        channels = EVENT_CHANNEL_MAP.get(event_type, ['email'])
        email_addr = data.get('email')
        user_id = data.get('user_id')

        print(f"[NOTIFICATION] Received {event_type}: {data}")

        with app.app_context():
            if 'email' in channels and email_addr:
                subject, html_body = get_email_template(event_type, data)
                send_email(email_addr, subject, html_body, event_type, user_id)

            if 'sms' in channels and data.get('phone'):
                sms_body = get_sms_template(event_type, data)
                send_sms(data['phone'], sms_body, event_type, user_id)

    except Exception as e:
        print(f"[NOTIFICATION] Error handling booking event: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def handle_waitlist_event(ch, method, properties, body):
    """Handle waitlist.promoted (NOTF-03) and waitlist.expired events."""
    try:
        data = json.loads(body)
        event_type = method.routing_key
        channels = EVENT_CHANNEL_MAP.get(event_type, ['email'])
        email_addr = data.get('email')
        phone = data.get('phone')
        user_id = data.get('user_id')

        print(f"[NOTIFICATION] Received {event_type}: {data}")

        with app.app_context():
            if 'email' in channels and email_addr:
                subject, html_body = get_email_template(event_type, data)
                send_email(email_addr, subject, html_body, event_type, user_id)

            if 'sms' in channels and phone:
                sms_body = get_sms_template(event_type, data)
                send_sms(phone, sms_body, event_type, user_id)

    except Exception as e:
        print(f"[NOTIFICATION] Error handling waitlist event: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def handle_lifecycle_event(ch, method, properties, body):
    """Handle event.cancelled (NOTF-04).
    The event.cancelled payload only contains event_id and event_name (no email).
    Per-user cancellation notifications arrive via the refund.completed chain which includes email.
    This handler logs the cancellation event for audit purposes.
    """
    try:
        data = json.loads(body)
        event_id = data.get('event_id', 'N/A')
        event_name = data.get('event_name', 'Unknown')

        print(f"[NOTIFICATION] Event cancelled: id={event_id}, name={event_name}")

        with app.app_context():
            # Log the cancellation event (no email to send - payload has no user info)
            log = NotificationLog(
                user_id=None,
                email=None,
                channel='email',
                event_type='event.cancelled',
                subject=f"Event Cancelled - {event_name}",
                body=f"Event {event_id} ({event_name}) has been cancelled. "
                     f"Individual refund notifications sent via refund.completed chain.",
                status='sent'
            )
            db.session.add(log)
            db.session.commit()

    except Exception as e:
        print(f"[NOTIFICATION] Error handling lifecycle event: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def handle_refund_event(ch, method, properties, body):
    """Handle refund.completed (NOTF-05) - Phase 5 stub."""
    try:
        data = json.loads(body)
        event_type = 'refund.completed'
        email_addr = data.get('email')
        user_id = data.get('user_id')

        print(f"[NOTIFICATION] Received refund event: {data}")

        with app.app_context():
            if email_addr:
                subject, html_body = get_email_template(event_type, data)
                send_email(email_addr, subject, html_body, event_type, user_id)

    except Exception as e:
        print(f"[NOTIFICATION] Error handling refund event: {e}")
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


@app.route('/notifications/user/<user_id>')
def get_user_notifications(user_id):
    """NOTF-06: Get notification history for a user."""
    try:
        limit = request.args.get('limit', 50, type=int)
        logs = NotificationLog.query.filter_by(user_id=user_id) \
            .order_by(NotificationLog.created_at.desc()) \
            .limit(limit) \
            .all()
        return success([log.to_dict() for log in logs])
    except Exception as e:
        return error(f"Failed to fetch notifications: {str(e)}", 500)


# ============================================
# OTP Endpoints (SMU Lab API)
# ============================================

@app.route('/notifications/otp/send', methods=['POST'])
def send_otp():
    """Send OTP to a mobile number via SMU Lab API."""
    data = request.get_json()
    mobile = data.get('mobile') if data else None
    if not mobile:
        return error("mobile is required", 400)
    try:
        resp = requests.post(
            f"{NOTI_BASE_URL}/SendOTP",
            headers=NOTI_HEADERS,
            json={"Mobile": mobile},
            timeout=10
        )
        result = resp.json()
        if resp.ok and result.get('Success'):
            return success({"verification_sid": result.get('VerificationSid')})
        else:
            return error(result.get('ErrorMessage', 'Failed to send OTP'), 502)
    except Exception as e:
        return error(f"OTP send failed: {str(e)}", 500)


@app.route('/notifications/otp/verify', methods=['POST'])
def verify_otp():
    """Verify OTP code via SMU Lab API."""
    data = request.get_json()
    if not data or not data.get('verification_sid') or not data.get('code'):
        return error("verification_sid and code are required", 400)
    try:
        resp = requests.post(
            f"{NOTI_BASE_URL}/VerifyOTP",
            headers=NOTI_HEADERS,
            json={"VerificationSid": data['verification_sid'], "Code": data['code']},
            timeout=10
        )
        result = resp.json()
        if resp.ok and result.get('Success'):
            return success({"status": result.get('Status', 'approved')})
        else:
            return error(result.get('ErrorMessage', 'Verification failed'), 400)
    except Exception as e:
        return error(f"OTP verify failed: {str(e)}", 500)


# ============================================
# AMQP Consumer Startup
# ============================================

def start_all_consumers():
    """Start all AMQP consumers in separate daemon threads."""
    threading.Thread(
        target=lambda: start_consumer(
            'notification_booking_queue', 'booking_topic',
            ['booking.confirmed', 'booking.timeout', 'booking.refund.requested'],
            handle_booking_event
        ), daemon=True
    ).start()

    threading.Thread(
        target=lambda: start_consumer(
            'notification_waitlist_queue', 'waitlist_topic',
            ['waitlist.promoted', 'waitlist.expired'],
            handle_waitlist_event
        ), daemon=True
    ).start()

    threading.Thread(
        target=lambda: start_consumer(
            'notification_lifecycle_queue', 'event_lifecycle',
            ['event.cancelled.*'],
            handle_lifecycle_event
        ), daemon=True
    ).start()

    threading.Thread(
        target=lambda: start_consumer(
            'notification_refund_queue', 'refund_topic',
            ['refund.completed'],
            handle_refund_event
        ), daemon=True
    ).start()

    print("[NOTIFICATION] All AMQP consumers started")


if __name__ == '__main__':
    start_all_consumers()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5005)), debug=False)
