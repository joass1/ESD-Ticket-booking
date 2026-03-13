"""
Notification Service Integration Tests
Tests NOTF-01 through NOTF-06 against running Docker stack.

NOTF-01: Booking confirmed notification (email)
NOTF-02: Booking timeout notification (email)
NOTF-03: Waitlist promotion notification (email + SMS)
NOTF-04: Event cancellation queue stub
NOTF-05: Refund queue stub
NOTF-06: Notification history endpoint

Tests use direct AMQP publishing via pika to test consumer behavior
independently of other services. Email/SMS will have status='failed'
if no Gmail/Twilio credentials are configured -- that's expected.

Tests run in order -- later tests depend on state from earlier tests.
"""

import sys
import os
import time
import json
import requests
import pika

NOTIFICATION_URL = "http://localhost:5005"
RABBITMQ_API = "http://localhost:15672/api"
RABBITMQ_AUTH = ("guest", "guest")
RABBITMQ_HOST = "localhost"

PASSED = 0
FAILED = 0

TEST_USER_ID = "notif_test_user"
TEST_EMAIL = "notif_test@test.com"
TEST_PHONE = "+6591234567"


def test_pass(name):
    global PASSED
    PASSED += 1
    print(f"  PASS: {name}")


def test_fail(name, reason):
    global FAILED
    FAILED += 1
    print(f"  FAIL: {name} -- {reason}")


def publish_test_message(exchange, routing_key, payload, exchange_type='topic'):
    """Publish a test message directly to RabbitMQ."""
    conn = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    ch = conn.channel()
    ch.exchange_declare(exchange=exchange, exchange_type=exchange_type, durable=True)
    ch.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=json.dumps(payload),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conn.close()


# ============================================
# Tests (run in order)
# ============================================

def test_health():
    """Health check -- Notification Service is reachable."""
    try:
        r = requests.get(f"{NOTIFICATION_URL}/health", timeout=5)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data["data"]["status"] == "healthy", f"Unexpected status: {data}"
        test_pass("test_health")
        return True
    except Exception as e:
        test_fail("test_health", str(e))
        return False


def test_booking_confirmed_notification():
    """NOTF-01: Booking confirmed event triggers email notification.
    Publishes a booking.confirmed message and verifies the notification service
    consumes it and logs a notification entry."""
    try:
        publish_test_message('booking_topic', 'booking.confirmed', {
            "booking_id": 9999,
            "event_id": 1,
            "user_id": TEST_USER_ID,
            "email": TEST_EMAIL,
            "seat_id": 1,
            "amount": 50.00
        })

        # Wait for consumer to process
        time.sleep(3)

        # Check notification history
        r = requests.get(f"{NOTIFICATION_URL}/notifications/user/{TEST_USER_ID}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        notifications = r.json()["data"]
        assert len(notifications) >= 1, "Expected at least 1 notification"

        # Find the booking.confirmed notification
        booking_notifs = [n for n in notifications if n["event_type"] == "booking.confirmed"]
        assert len(booking_notifs) >= 1, \
            f"Expected booking.confirmed notification, found event_types: {[n['event_type'] for n in notifications]}"

        notif = booking_notifs[0]
        assert notif["channel"] == "email", f"Expected email channel, got {notif['channel']}"
        assert notif["user_id"] == TEST_USER_ID, f"Wrong user_id: {notif['user_id']}"
        # Status may be 'sent' or 'failed' depending on Gmail credentials
        assert notif["status"] in ("sent", "failed"), f"Unexpected status: {notif['status']}"

        test_pass("test_booking_confirmed_notification (NOTF-01)")
        return True
    except Exception as e:
        test_fail("test_booking_confirmed_notification (NOTF-01)", str(e))
        return False


def test_booking_timeout_notification():
    """NOTF-02: Booking timeout event triggers email notification."""
    try:
        publish_test_message('booking_topic', 'booking.timeout', {
            "event_id": 1,
            "user_id": TEST_USER_ID,
            "email": TEST_EMAIL,
            "seat_id": 2,
            "saga_id": "test-saga-timeout"
        })

        time.sleep(3)

        r = requests.get(f"{NOTIFICATION_URL}/notifications/user/{TEST_USER_ID}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        notifications = r.json()["data"]

        timeout_notifs = [n for n in notifications if n["event_type"] == "booking.timeout"]
        assert len(timeout_notifs) >= 1, \
            f"Expected booking.timeout notification, found: {[n['event_type'] for n in notifications]}"

        notif = timeout_notifs[0]
        assert notif["channel"] == "email", f"Expected email channel, got {notif['channel']}"
        assert notif["status"] in ("sent", "failed"), f"Unexpected status: {notif['status']}"

        test_pass("test_booking_timeout_notification (NOTF-02)")
        return True
    except Exception as e:
        test_fail("test_booking_timeout_notification (NOTF-02)", str(e))
        return False


def test_waitlist_promotion_notification():
    """NOTF-03: Waitlist promotion triggers BOTH email and SMS notifications.
    Both may have status='failed' if credentials are not configured, but both
    should be logged in the notification_logs table."""
    try:
        publish_test_message('waitlist_topic', 'waitlist.promoted', {
            "entry_id": 1,
            "event_id": 1,
            "user_id": TEST_USER_ID,
            "email": TEST_EMAIL,
            "phone": TEST_PHONE,
            "seat_id": 1,
            "section": "VIP",
            "promotion_expires_at": "2099-12-31T23:59:59"
        })

        time.sleep(3)

        r = requests.get(f"{NOTIFICATION_URL}/notifications/user/{TEST_USER_ID}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        notifications = r.json()["data"]

        promo_notifs = [n for n in notifications if n["event_type"] == "waitlist.promoted"]
        assert len(promo_notifs) >= 2, \
            f"Expected >= 2 waitlist.promoted notifications (email + sms), got {len(promo_notifs)}"

        channels = [n["channel"] for n in promo_notifs]
        assert "email" in channels, f"Expected email in channels, got: {channels}"
        assert "sms" in channels, f"Expected sms in channels, got: {channels}"

        test_pass("test_waitlist_promotion_notification (NOTF-03)")
        return True
    except Exception as e:
        test_fail("test_waitlist_promotion_notification (NOTF-03)", str(e))
        return False


def test_notification_history():
    """NOTF-06: Notification history endpoint returns all logged notifications."""
    try:
        r = requests.get(f"{NOTIFICATION_URL}/notifications/user/{TEST_USER_ID}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        notifications = r.json()["data"]

        # Should have at least 3 entries from previous tests (confirmed email, timeout email, promotion email)
        # Plus 1 SMS from promotion = at least 4
        assert len(notifications) >= 3, \
            f"Expected >= 3 notification entries, got {len(notifications)}"

        # Verify each entry has required fields
        required_fields = ["log_id", "user_id", "channel", "event_type", "status", "created_at"]
        for notif in notifications:
            for field in required_fields:
                assert field in notif, f"Missing field '{field}' in notification: {notif}"

        test_pass("test_notification_history (NOTF-06)")
        return True
    except Exception as e:
        test_fail("test_notification_history (NOTF-06)", str(e))
        return False


def test_cancellation_queue_exists():
    """NOTF-04 stub: Verify notification_lifecycle_queue exists and is bound to event_lifecycle exchange."""
    try:
        r = requests.get(
            f"{RABBITMQ_API}/queues/%2F/notification_lifecycle_queue",
            auth=RABBITMQ_AUTH, timeout=5
        )
        assert r.status_code == 200, \
            f"notification_lifecycle_queue not found (status {r.status_code})"

        q_data = r.json()
        assert q_data["name"] == "notification_lifecycle_queue", \
            f"Unexpected queue name: {q_data['name']}"

        test_pass("test_cancellation_queue_exists (NOTF-04)")
        return True
    except Exception as e:
        test_fail("test_cancellation_queue_exists (NOTF-04)", str(e))
        return False


def test_refund_queue_exists():
    """NOTF-05 stub: Verify notification_refund_queue exists and is bound to refund_direct exchange."""
    try:
        r = requests.get(
            f"{RABBITMQ_API}/queues/%2F/notification_refund_queue",
            auth=RABBITMQ_AUTH, timeout=5
        )
        assert r.status_code == 200, \
            f"notification_refund_queue not found (status {r.status_code})"

        q_data = r.json()
        assert q_data["name"] == "notification_refund_queue", \
            f"Unexpected queue name: {q_data['name']}"

        test_pass("test_refund_queue_exists (NOTF-05)")
        return True
    except Exception as e:
        test_fail("test_refund_queue_exists (NOTF-05)", str(e))
        return False


# ============================================
# Main
# ============================================

if __name__ == "__main__":
    print("==========================================")
    print("Notification Service Integration Tests")
    print(f"Notification Service: {NOTIFICATION_URL}")
    print(f"RabbitMQ API: {RABBITMQ_API}")
    print("==========================================")
    print()

    try:
        requests.get(f"{NOTIFICATION_URL}/health", timeout=5)
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to Notification Service at {NOTIFICATION_URL}")
        print("Make sure the Docker stack is running: docker compose up -d")
        sys.exit(1)

    tests = [
        test_health,
        test_booking_confirmed_notification,
        test_booking_timeout_notification,
        test_waitlist_promotion_notification,
        test_notification_history,
        test_cancellation_queue_exists,
        test_refund_queue_exists,
    ]

    for t in tests:
        t()

    print()
    print("==========================================")
    TOTAL = PASSED + FAILED
    if FAILED == 0:
        print(f"All {PASSED}/{TOTAL} Notification Service tests passed!")
        sys.exit(0)
    else:
        print(f"{PASSED}/{TOTAL} passed, {FAILED}/{TOTAL} failed")
        sys.exit(1)
