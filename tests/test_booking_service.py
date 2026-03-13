"""
Booking Service Integration Tests
Tests BOOK-06 (booking CRUD and query endpoints) against running Docker stack.
"""

import sys
import requests

BASE_URL = "http://localhost:5002"

PASSED = 0
FAILED = 0
CREATED_BOOKING_ID = None
TEST_USER_ID = "test-booking-user-001"
TEST_EVENT_ID = 1
TEST_SEAT_ID = 1


def test_pass(name):
    global PASSED
    PASSED += 1
    print(f"  PASS: {name}")


def test_fail(name, reason):
    global FAILED
    FAILED += 1
    print(f"  FAIL: {name} -- {reason}")


# ============================================
# Tests
# ============================================

def test_create_booking():
    """BOOK-06: POST /bookings with valid JSON returns 201."""
    global CREATED_BOOKING_ID
    try:
        payload = {
            "user_id": TEST_USER_ID,
            "event_id": TEST_EVENT_ID,
            "seat_id": TEST_SEAT_ID,
            "email": "testuser@example.com",
            "amount": 388.00
        }
        r = requests.post(f"{BASE_URL}/bookings", json=payload)
        data = r.json()
        assert r.status_code == 201, f"Expected 201, got {r.status_code}"
        assert data["code"] == 201, f"Expected code 201, got {data['code']}"
        booking = data["data"]
        assert "booking_id" in booking, "Response should include booking_id"
        assert booking["user_id"] == TEST_USER_ID, f"user_id mismatch: {booking['user_id']}"
        assert booking["status"] == "pending", f"Default status should be 'pending', got {booking['status']}"
        CREATED_BOOKING_ID = booking["booking_id"]
        test_pass("test_create_booking")
        return True
    except Exception as e:
        test_fail("test_create_booking", str(e))
        return False


def test_get_booking_by_id():
    """BOOK-06: GET /bookings/{id} returns the created booking."""
    try:
        assert CREATED_BOOKING_ID is not None, "No booking created yet"
        r = requests.get(f"{BASE_URL}/bookings/{CREATED_BOOKING_ID}")
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        booking = data["data"]
        assert booking["booking_id"] == CREATED_BOOKING_ID, f"booking_id mismatch"
        assert booking["user_id"] == TEST_USER_ID, f"user_id mismatch"
        assert booking["event_id"] == TEST_EVENT_ID, f"event_id mismatch"
        test_pass("test_get_booking_by_id")
        return True
    except Exception as e:
        test_fail("test_get_booking_by_id", str(e))
        return False


def test_get_user_bookings():
    """BOOK-06: GET /bookings/user/{user_id} returns list containing the booking."""
    try:
        r = requests.get(f"{BASE_URL}/bookings/user/{TEST_USER_ID}")
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        bookings = data["data"]
        assert isinstance(bookings, list), "Expected list of bookings"
        assert len(bookings) >= 1, f"Expected at least 1 booking, got {len(bookings)}"
        ids = [b["booking_id"] for b in bookings]
        assert CREATED_BOOKING_ID in ids, f"Created booking {CREATED_BOOKING_ID} not found in user bookings"
        test_pass("test_get_user_bookings")
        return True
    except Exception as e:
        test_fail("test_get_user_bookings", str(e))
        return False


def test_list_bookings_filter_event():
    """BOOK-06: GET /bookings?event_id={id} returns filtered results."""
    try:
        r = requests.get(f"{BASE_URL}/bookings", params={"event_id": TEST_EVENT_ID})
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        bookings = data["data"]
        assert isinstance(bookings, list), "Expected list of bookings"
        # All returned bookings should match the event_id filter
        for b in bookings:
            assert b["event_id"] == TEST_EVENT_ID, f"Expected event_id {TEST_EVENT_ID}, got {b['event_id']}"
        test_pass("test_list_bookings_filter_event")
        return True
    except Exception as e:
        test_fail("test_list_bookings_filter_event", str(e))
        return False


def test_get_booking_not_found():
    """BOOK-06: GET /bookings/999 returns 404."""
    try:
        r = requests.get(f"{BASE_URL}/bookings/999")
        data = r.json()
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        assert data["code"] == 404, f"Expected code 404, got {data['code']}"
        test_pass("test_get_booking_not_found")
        return True
    except Exception as e:
        test_fail("test_get_booking_not_found", str(e))
        return False


def test_update_booking_status():
    """BOOK-06: PUT /bookings/{id} with status=confirmed returns updated booking."""
    try:
        assert CREATED_BOOKING_ID is not None, "No booking created yet"
        r = requests.put(
            f"{BASE_URL}/bookings/{CREATED_BOOKING_ID}",
            json={"status": "confirmed"}
        )
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        booking = data["data"]
        assert booking["status"] == "confirmed", f"Expected 'confirmed', got '{booking['status']}'"
        test_pass("test_update_booking_status")
        return True
    except Exception as e:
        test_fail("test_update_booking_status", str(e))
        return False


# ============================================
# Main
# ============================================

if __name__ == "__main__":
    print("==========================================")
    print("Booking Service Integration Tests")
    print(f"Target: {BASE_URL}")
    print("==========================================")
    print()

    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to Booking Service at {BASE_URL}")
        print("Make sure the Docker stack is running: docker compose up -d")
        sys.exit(1)

    tests = [
        test_create_booking,
        test_get_booking_by_id,
        test_get_user_bookings,
        test_list_bookings_filter_event,
        test_get_booking_not_found,
        test_update_booking_status,
    ]

    for t in tests:
        t()

    print()
    print("==========================================")
    TOTAL = PASSED + FAILED
    if FAILED == 0:
        print(f"All {PASSED}/{TOTAL} Booking Service tests passed!")
        sys.exit(0)
    else:
        print(f"{PASSED}/{TOTAL} passed, {FAILED}/{TOTAL} failed")
        sys.exit(1)
