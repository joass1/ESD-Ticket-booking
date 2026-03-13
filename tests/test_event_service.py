"""
Event Service Integration Tests
Tests EVNT-01 (browse/filter events) and EVNT-02 (admin CRUD) against running Docker stack.
"""

import sys
import requests

BASE_URL = "http://localhost:5001"

PASSED = 0
FAILED = 0
CREATED_EVENT_ID = None  # Track for cleanup


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

def test_list_events():
    """EVNT-01: GET /events returns all 5 seeded events."""
    try:
        r = requests.get(f"{BASE_URL}/events")
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        assert data["code"] == 200, f"Expected code 200, got {data['code']}"
        events = data["data"]
        assert isinstance(events, list), "Expected list of events"
        assert len(events) == 5, f"Expected 5 seeded events, got {len(events)}"
        test_pass("test_list_events")
        return True
    except Exception as e:
        test_fail("test_list_events", str(e))
        return False


def test_filter_by_status():
    """EVNT-01: GET /events?status=upcoming returns 4 upcoming events (Jay Chou is 'ongoing')."""
    try:
        r = requests.get(f"{BASE_URL}/events", params={"status": "upcoming"})
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        events = data["data"]
        assert len(events) == 4, f"Expected 4 upcoming events, got {len(events)}"
        names = [e["name"] for e in events]
        assert all("Jay Chou" not in n for n in names), "Jay Chou should not be in upcoming"
        test_pass("test_filter_by_status")
        return True
    except Exception as e:
        test_fail("test_filter_by_status", str(e))
        return False


def test_filter_by_category():
    """EVNT-01: GET /events?category=Concert returns all 5 (all are Concert)."""
    try:
        r = requests.get(f"{BASE_URL}/events", params={"category": "Concert"})
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        events = data["data"]
        assert len(events) == 5, f"Expected 5 Concert events, got {len(events)}"
        test_pass("test_filter_by_category")
        return True
    except Exception as e:
        test_fail("test_filter_by_category", str(e))
        return False


def test_filter_by_date_range():
    """EVNT-01: GET /events?date_from=2026-07-01&date_to=2026-08-31 returns Ed Sheeran and Coldplay."""
    try:
        r = requests.get(f"{BASE_URL}/events", params={
            "date_from": "2026-07-01",
            "date_to": "2026-08-31"
        })
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        events = data["data"]
        assert len(events) == 2, f"Expected 2 events in Jul-Aug range, got {len(events)}"
        names = sorted([e["name"] for e in events])
        assert any("Coldplay" in n for n in names), "Coldplay should be in range"
        assert any("Ed Sheeran" in n for n in names), "Ed Sheeran should be in range"
        test_pass("test_filter_by_date_range")
        return True
    except Exception as e:
        test_fail("test_filter_by_date_range", str(e))
        return False


def test_get_event_by_id():
    """EVNT-01: GET /events/1 returns Taylor Swift event."""
    try:
        r = requests.get(f"{BASE_URL}/events/1")
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        event = data["data"]
        assert event["event_id"] == 1, f"Expected event_id 1, got {event['event_id']}"
        assert "Taylor Swift" in event["name"], f"Expected Taylor Swift, got {event['name']}"
        test_pass("test_get_event_by_id")
        return True
    except Exception as e:
        test_fail("test_get_event_by_id", str(e))
        return False


def test_get_event_not_found():
    """EVNT-01: GET /events/999 returns 404."""
    try:
        r = requests.get(f"{BASE_URL}/events/999")
        data = r.json()
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        assert data["code"] == 404, f"Expected code 404, got {data['code']}"
        test_pass("test_get_event_not_found")
        return True
    except Exception as e:
        test_fail("test_get_event_not_found", str(e))
        return False


def test_create_event():
    """EVNT-02: POST /events with valid JSON returns 201."""
    global CREATED_EVENT_ID
    try:
        payload = {
            "name": "Test Event - Integration",
            "event_date": "2026-12-25 20:00:00",
            "total_seats": 100,
            "category": "Test",
            "venue": "Test Venue",
            "description": "Integration test event"
        }
        r = requests.post(f"{BASE_URL}/events", json=payload)
        data = r.json()
        assert r.status_code == 201, f"Expected 201, got {r.status_code}"
        assert data["code"] == 201, f"Expected code 201, got {data['code']}"
        event = data["data"]
        assert "event_id" in event, "Response should include event_id"
        assert event["name"] == "Test Event - Integration", f"Name mismatch: {event['name']}"
        assert event["total_seats"] == 100, f"Expected 100 seats, got {event['total_seats']}"
        CREATED_EVENT_ID = event["event_id"]
        test_pass("test_create_event")
        return True
    except Exception as e:
        test_fail("test_create_event", str(e))
        return False


def test_create_event_missing_fields():
    """EVNT-02: POST /events without required fields returns 400."""
    try:
        payload = {
            "description": "Missing name, event_date, total_seats"
        }
        r = requests.post(f"{BASE_URL}/events", json=payload)
        data = r.json()
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        assert data["code"] == 400, f"Expected code 400, got {data['code']}"
        test_pass("test_create_event_missing_fields")
        return True
    except Exception as e:
        test_fail("test_create_event_missing_fields", str(e))
        return False


def test_update_event():
    """EVNT-02: PUT /events/{id} with new venue returns 200 with updated venue."""
    global CREATED_EVENT_ID
    try:
        target_id = CREATED_EVENT_ID if CREATED_EVENT_ID else 1
        new_venue = "Updated Test Venue"
        r = requests.put(f"{BASE_URL}/events/{target_id}", json={"venue": new_venue})
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        event = data["data"]
        assert event["venue"] == new_venue, f"Expected '{new_venue}', got '{event['venue']}'"
        test_pass("test_update_event")
        return True
    except Exception as e:
        test_fail("test_update_event", str(e))
        return False


# ============================================
# Main
# ============================================

if __name__ == "__main__":
    print("==========================================")
    print("Event Service Integration Tests")
    print(f"Target: {BASE_URL}")
    print("==========================================")
    print()

    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to Event Service at {BASE_URL}")
        print("Make sure the Docker stack is running: docker compose up -d")
        sys.exit(1)

    tests = [
        test_list_events,
        test_filter_by_status,
        test_filter_by_category,
        test_filter_by_date_range,
        test_get_event_by_id,
        test_get_event_not_found,
        test_create_event,
        test_create_event_missing_fields,
        test_update_event,
    ]

    for t in tests:
        t()

    print()
    print("==========================================")
    TOTAL = PASSED + FAILED
    if FAILED == 0:
        print(f"All {PASSED}/{TOTAL} Event Service tests passed!")
        sys.exit(0)
    else:
        print(f"{PASSED}/{TOTAL} passed, {FAILED}/{TOTAL} failed")
        sys.exit(1)
