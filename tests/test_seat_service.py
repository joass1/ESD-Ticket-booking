"""
Seat Service Integration Tests
Tests SEAT-01 through SEAT-06 against running Docker stack.
Validates dual-lock reservation, auto-assign, ownership release, and confirm.

Tests run in order -- later tests depend on state from earlier tests.
Dynamically selects available seats so tests are re-runnable.
"""

import sys
import requests

BASE_URL = "http://localhost:5003"

PASSED = 0
FAILED = 0

# Test context -- tracks state across ordered tests
ctx = {
    "target_seat_id": None,          # an available seat picked dynamically
    "target_seat_section": None,     # section_id of the target seat
    "reserved_seat_id": None,        # seat_id reserved in test_reserve_seat
    "auto_assigned_seat_id": None,   # seat_id auto-assigned in test_reserve_taken_seat
    "confirm_seat_id": None,         # seat_id used for confirm test
    "vip_available_before": None,    # VIP available count before any test reservations
}

TEST_USER_1 = "test-seat-user-001"
TEST_USER_2 = "test-seat-user-002"
TEST_USER_3 = "test-seat-user-003"
TEST_EVENT_ID = 1


def test_pass(name):
    global PASSED
    PASSED += 1
    print(f"  PASS: {name}")


def test_fail(name, reason):
    global FAILED
    FAILED += 1
    print(f"  FAIL: {name} -- {reason}")


def find_available_vip_seats():
    """Find available VIP seats for event 1 to use in tests."""
    r = requests.get(f"{BASE_URL}/seats/event/{TEST_EVENT_ID}")
    seats = r.json()["data"]
    # VIP section (section_id=1) seats that are available
    vip_available = [s for s in seats if s["section_name"] == "VIP" and s["status"] == "available"]
    return vip_available


# ============================================
# Tests (run in order)
# ============================================

def test_list_seats_for_event():
    """SEAT-01: GET /seats/event/1 returns 130 seats (30 VIP + 50 CAT1 + 50 CAT2) with section info."""
    try:
        r = requests.get(f"{BASE_URL}/seats/event/{TEST_EVENT_ID}")
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        seats = data["data"]
        assert isinstance(seats, list), "Expected list of seats"
        assert len(seats) == 130, f"Expected 130 seats, got {len(seats)}"
        # Verify section info is included
        first_seat = seats[0]
        assert "section_name" in first_seat, "Seat should include section_name"
        assert "section_price" in first_seat, "Seat should include section_price"
        test_pass("test_list_seats_for_event (SEAT-01)")
        return True
    except Exception as e:
        test_fail("test_list_seats_for_event (SEAT-01)", str(e))
        return False


def test_availability_per_section():
    """SEAT-02: GET /seats/availability/1 returns 3 sections with correct total counts."""
    try:
        r = requests.get(f"{BASE_URL}/seats/availability/{TEST_EVENT_ID}")
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        avail = data["data"]
        assert "sections" in avail, "Response should include sections"
        sections = avail["sections"]
        assert len(sections) == 3, f"Expected 3 sections, got {len(sections)}"

        # Build a lookup by section name
        by_name = {s["name"]: s for s in sections}
        assert "VIP" in by_name, "VIP section missing"
        assert "CAT1" in by_name, "CAT1 section missing"
        assert "CAT2" in by_name, "CAT2 section missing"
        assert by_name["VIP"]["total_seats"] == 30, f"VIP total should be 30, got {by_name['VIP']['total_seats']}"
        assert by_name["CAT1"]["total_seats"] == 50, f"CAT1 total should be 50"
        assert by_name["CAT2"]["total_seats"] == 50, f"CAT2 total should be 50"

        # Record current VIP availability for later comparisons
        ctx["vip_available_before"] = by_name["VIP"]["available_seats"]

        test_pass("test_availability_per_section (SEAT-02)")
        return True
    except Exception as e:
        test_fail("test_availability_per_section (SEAT-02)", str(e))
        return False


def test_reserve_seat():
    """SEAT-03: Reserve an available seat -> auto_assigned=false, status=reserved."""
    try:
        # Dynamically find an available VIP seat
        vip_seats = find_available_vip_seats()
        assert len(vip_seats) >= 3, f"Need at least 3 available VIP seats, got {len(vip_seats)}"

        target = vip_seats[0]
        ctx["target_seat_id"] = target["seat_id"]
        ctx["target_seat_section"] = target["section_id"]

        payload = {
            "event_id": TEST_EVENT_ID,
            "seat_id": target["seat_id"],
            "user_id": TEST_USER_1
        }
        r = requests.post(f"{BASE_URL}/seats/reserve", json=payload)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        seat = data["data"]
        assert seat["auto_assigned"] is False, f"Expected auto_assigned=false, got {seat['auto_assigned']}"
        assert seat["status"] == "reserved", f"Expected status='reserved', got {seat['status']}"
        assert seat["seat_id"] == target["seat_id"], f"Expected seat_id={target['seat_id']}, got {seat['seat_id']}"
        ctx["reserved_seat_id"] = seat["seat_id"]
        test_pass("test_reserve_seat (SEAT-03)")
        return True
    except Exception as e:
        test_fail("test_reserve_seat (SEAT-03)", str(e))
        return False


def test_availability_after_reserve():
    """SEAT-02 continued: VIP available_seats should decrease by 1 after reserving one seat."""
    try:
        r = requests.get(f"{BASE_URL}/seats/availability/{TEST_EVENT_ID}")
        data = r.json()
        sections = data["data"]["sections"]
        by_name = {s["name"]: s for s in sections}
        vip_available = by_name["VIP"]["available_seats"]
        expected = ctx["vip_available_before"] - 1
        assert vip_available == expected, f"Expected VIP available={expected}, got {vip_available}"
        test_pass("test_availability_after_reserve (SEAT-02)")
        return True
    except Exception as e:
        test_fail("test_availability_after_reserve (SEAT-02)", str(e))
        return False


def test_reserve_taken_seat_auto_assigns():
    """SEAT-04: Reserve same seat with different user -> auto_assigned=true, different seat."""
    try:
        payload = {
            "event_id": TEST_EVENT_ID,
            "seat_id": ctx["target_seat_id"],
            "user_id": TEST_USER_2
        }
        r = requests.post(f"{BASE_URL}/seats/reserve", json=payload)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        seat = data["data"]
        assert seat["auto_assigned"] is True, f"Expected auto_assigned=true, got {seat['auto_assigned']}"
        assert seat["seat_id"] != ctx["target_seat_id"], \
            f"Should have auto-assigned a different seat, got same seat_id={ctx['target_seat_id']}"
        assert seat["status"] == "reserved", f"Expected status='reserved', got {seat['status']}"
        ctx["auto_assigned_seat_id"] = seat["seat_id"]
        test_pass("test_reserve_taken_seat_auto_assigns (SEAT-04)")
        return True
    except Exception as e:
        test_fail("test_reserve_taken_seat_auto_assigns (SEAT-04)", str(e))
        return False


def test_release_seat():
    """SEAT-05: Release reserved seat by owner -> status back to available."""
    try:
        assert ctx["reserved_seat_id"] is not None, "No seat was reserved to release"
        payload = {
            "event_id": TEST_EVENT_ID,
            "seat_id": ctx["reserved_seat_id"],
            "user_id": TEST_USER_1
        }
        r = requests.post(f"{BASE_URL}/seats/release", json=payload)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        result = data["data"]
        assert result["status"] == "released", f"Expected status='released', got {result['status']}"
        test_pass("test_release_seat (SEAT-05)")
        return True
    except Exception as e:
        test_fail("test_release_seat (SEAT-05)", str(e))
        return False


def test_availability_after_release():
    """VIP available count should increase by 1 after releasing the reserved seat.
    auto-assigned seat still reserved, so net change from baseline is -1."""
    try:
        r = requests.get(f"{BASE_URL}/seats/availability/{TEST_EVENT_ID}")
        data = r.json()
        sections = data["data"]["sections"]
        by_name = {s["name"]: s for s in sections}
        vip_available = by_name["VIP"]["available_seats"]
        # Baseline was vip_available_before. We reserved 2 seats (reserve + auto-assign),
        # then released 1. So net = baseline - 1.
        expected = ctx["vip_available_before"] - 1
        assert vip_available == expected, \
            f"Expected VIP available={expected} (baseline {ctx['vip_available_before']} minus 1 still held), got {vip_available}"
        test_pass("test_availability_after_release")
        return True
    except Exception as e:
        test_fail("test_availability_after_release", str(e))
        return False


def test_release_wrong_owner():
    """SEAT-05 ownership: Release auto-assigned seat with wrong user_id returns 403."""
    try:
        assert ctx["auto_assigned_seat_id"] is not None, "No auto-assigned seat to test"
        payload = {
            "event_id": TEST_EVENT_ID,
            "seat_id": ctx["auto_assigned_seat_id"],
            "user_id": "wrong-user-id"
        }
        r = requests.post(f"{BASE_URL}/seats/release", json=payload)
        data = r.json()
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"
        assert data["code"] == 403, f"Expected code 403, got {data['code']}"
        test_pass("test_release_wrong_owner (SEAT-05)")
        return True
    except Exception as e:
        test_fail("test_release_wrong_owner (SEAT-05)", str(e))
        return False


def test_reserve_and_confirm():
    """SEAT-06: Reserve a seat, then confirm it -> status becomes 'booked'."""
    try:
        # Find a fresh available VIP seat
        vip_seats = find_available_vip_seats()
        assert len(vip_seats) >= 1, "Need at least 1 available VIP seat for confirm test"
        target = vip_seats[0]

        # Reserve the seat
        reserve_payload = {
            "event_id": TEST_EVENT_ID,
            "seat_id": target["seat_id"],
            "user_id": TEST_USER_3
        }
        r = requests.post(f"{BASE_URL}/seats/reserve", json=reserve_payload)
        data = r.json()
        assert r.status_code == 200, f"Reserve expected 200, got {r.status_code}"
        reserved_seat = data["data"]
        confirm_seat_id = reserved_seat["seat_id"]
        ctx["confirm_seat_id"] = confirm_seat_id

        # Confirm the reserved seat
        confirm_payload = {
            "event_id": TEST_EVENT_ID,
            "seat_id": confirm_seat_id,
            "user_id": TEST_USER_3
        }
        r = requests.post(f"{BASE_URL}/seats/confirm", json=confirm_payload)
        data = r.json()
        assert r.status_code == 200, f"Confirm expected 200, got {r.status_code}"
        seat = data["data"]
        assert seat["status"] == "booked", f"Expected status='booked', got {seat['status']}"
        test_pass("test_reserve_and_confirm (SEAT-06)")
        return True
    except Exception as e:
        test_fail("test_reserve_and_confirm (SEAT-06)", str(e))
        return False


def test_confirm_available_seat_fails():
    """Confirm on an available (not reserved) seat should fail with 409."""
    try:
        # Find a seat that's available
        r = requests.get(f"{BASE_URL}/seats/event/{TEST_EVENT_ID}")
        seats = r.json()["data"]
        available_seat = None
        for s in seats:
            if s["status"] == "available":
                available_seat = s
                break
        assert available_seat is not None, "No available seats to test with"

        payload = {
            "event_id": TEST_EVENT_ID,
            "seat_id": available_seat["seat_id"],
            "user_id": TEST_USER_1
        }
        r = requests.post(f"{BASE_URL}/seats/confirm", json=payload)
        data = r.json()
        assert r.status_code == 409, f"Expected 409, got {r.status_code}"
        test_pass("test_confirm_available_seat_fails")
        return True
    except Exception as e:
        test_fail("test_confirm_available_seat_fails", str(e))
        return False


# ============================================
# Cleanup
# ============================================

def cleanup():
    """Release/reset any test reservations to leave database clean."""
    print()
    print("  Cleanup:")
    cleaned = 0

    # Release auto-assigned seat (held by TEST_USER_2)
    if ctx["auto_assigned_seat_id"]:
        try:
            r = requests.post(f"{BASE_URL}/seats/release", json={
                "event_id": TEST_EVENT_ID,
                "seat_id": ctx["auto_assigned_seat_id"],
                "user_id": TEST_USER_2
            })
            if r.status_code == 200:
                cleaned += 1
                print(f"    Released auto-assigned seat {ctx['auto_assigned_seat_id']}")
            else:
                print(f"    Warning: Could not release seat {ctx['auto_assigned_seat_id']} (status {r.status_code})")
        except Exception as e:
            print(f"    Warning: Cleanup error for auto-assigned seat: {e}")

    # Note: confirmed seat (booked) cannot be released via the release endpoint,
    # but it's a permanent state change which is acceptable for test data.
    if ctx["confirm_seat_id"]:
        print(f"    Note: Seat {ctx['confirm_seat_id']} is in 'booked' state (permanent, as expected)")

    print(f"    Cleanup done ({cleaned} seats released)")


# ============================================
# Main
# ============================================

if __name__ == "__main__":
    print("==========================================")
    print("Seat Service Integration Tests")
    print(f"Target: {BASE_URL}")
    print("==========================================")
    print()

    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to Seat Service at {BASE_URL}")
        print("Make sure the Docker stack is running: docker compose up -d")
        sys.exit(1)

    tests = [
        test_list_seats_for_event,
        test_availability_per_section,
        test_reserve_seat,
        test_availability_after_reserve,
        test_reserve_taken_seat_auto_assigns,
        test_release_seat,
        test_availability_after_release,
        test_release_wrong_owner,
        test_reserve_and_confirm,
        test_confirm_available_seat_fails,
    ]

    for t in tests:
        t()

    cleanup()

    print()
    print("==========================================")
    TOTAL = PASSED + FAILED
    if FAILED == 0:
        print(f"All {PASSED}/{TOTAL} Seat Service tests passed!")
        sys.exit(0)
    else:
        print(f"{PASSED}/{TOTAL} passed, {FAILED}/{TOTAL} failed")
        sys.exit(1)
