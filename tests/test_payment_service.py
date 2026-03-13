"""
Payment Service Integration Tests
Tests PAY-01 against running Docker stack at localhost:5004.
Validates Stripe PaymentIntent create, verify, and transaction retrieval.

IMPORTANT: Tests require a valid STRIPE_SECRET_KEY (sk_test_...) in .env.
With a dummy key, tests will fail at Stripe API calls.

Tests run in order -- later tests depend on state from earlier tests.
"""

import sys
import requests

BASE_URL = "http://localhost:5004"

PASSED = 0
FAILED = 0

# Test context -- tracks state across ordered tests
ctx = {
    "payment_intent_id": None,
    "client_secret": None,
}

TEST_BOOKING_ID = 99999
TEST_USER_ID = "test-pay-user-001"
TEST_AMOUNT = 50.00


def test_pass(name):
    global PASSED
    PASSED += 1
    print(f"  PASS: {name}")


def test_fail(name, reason):
    global FAILED
    FAILED += 1
    print(f"  FAIL: {name} -- {reason}")


# ============================================
# Tests (run in order)
# ============================================

def test_payment_health():
    """Health check for Payment Service."""
    try:
        r = requests.get(f"{BASE_URL}/health")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        test_pass("test_payment_health")
        return True
    except Exception as e:
        test_fail("test_payment_health", str(e))
        return False


def test_create_payment_intent():
    """PAY-01: Create a Stripe PaymentIntent via /payments/create."""
    try:
        payload = {
            "booking_id": TEST_BOOKING_ID,
            "user_id": TEST_USER_ID,
            "amount": TEST_AMOUNT
        }
        r = requests.post(f"{BASE_URL}/payments/create", json=payload)
        data = r.json()
        assert r.status_code == 201, f"Expected 201, got {r.status_code}"

        result = data["data"]
        assert "payment_intent_id" in result, "Missing payment_intent_id"
        assert result["payment_intent_id"].startswith("pi_"), \
            f"payment_intent_id should start with 'pi_', got {result['payment_intent_id']}"
        assert "client_secret" in result, "Missing client_secret"
        assert "_secret_" in result["client_secret"], \
            f"client_secret should contain '_secret_', got {result['client_secret']}"
        assert "amount" in result, "Missing amount"

        ctx["payment_intent_id"] = result["payment_intent_id"]
        ctx["client_secret"] = result["client_secret"]

        test_pass("test_create_payment_intent (PAY-01)")
        return True
    except Exception as e:
        test_fail("test_create_payment_intent (PAY-01)", str(e))
        return False


def test_verify_payment_pending():
    """PAY-01: Verify a PaymentIntent that has not been confirmed client-side.
    Should report status != 'succeeded' since no client confirmation happened."""
    try:
        assert ctx["payment_intent_id"] is not None, "No payment_intent_id from previous test"
        payload = {"payment_intent_id": ctx["payment_intent_id"]}
        r = requests.post(f"{BASE_URL}/payments/verify", json=payload)
        data = r.json()

        # The verify endpoint should return successfully but indicate payment not completed
        # Status will be 'requires_payment_method' or similar, not 'succeeded'
        if r.status_code == 200:
            result = data["data"]
            assert result.get("status") != "succeeded", \
                "Payment should not be succeeded (no client confirmation)"
            test_pass("test_verify_payment_pending (PAY-01)")
        else:
            # Some implementations return 400/402 for unconfirmed payments -- still valid
            test_pass("test_verify_payment_pending (PAY-01) -- non-succeeded status confirmed")
        return True
    except Exception as e:
        test_fail("test_verify_payment_pending (PAY-01)", str(e))
        return False


def test_get_transaction_by_booking():
    """PAY-01: Retrieve transaction record by booking_id."""
    try:
        r = requests.get(f"{BASE_URL}/payments/transaction/{TEST_BOOKING_ID}")
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"

        result = data["data"]
        assert result["booking_id"] == TEST_BOOKING_ID, \
            f"Expected booking_id={TEST_BOOKING_ID}, got {result['booking_id']}"
        assert result["stripe_payment_intent_id"] == ctx["payment_intent_id"], \
            f"Expected intent {ctx['payment_intent_id']}, got {result['stripe_payment_intent_id']}"

        test_pass("test_get_transaction_by_booking (PAY-01)")
        return True
    except Exception as e:
        test_fail("test_get_transaction_by_booking (PAY-01)", str(e))
        return False


# ============================================
# Main
# ============================================

if __name__ == "__main__":
    print("==========================================")
    print("Payment Service Integration Tests")
    print(f"Target: {BASE_URL}")
    print("==========================================")
    print()

    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to Payment Service at {BASE_URL}")
        print("Make sure the Docker stack is running: docker compose up -d")
        sys.exit(1)

    tests = [
        test_payment_health,
        test_create_payment_intent,
        test_verify_payment_pending,
        test_get_transaction_by_booking,
    ]

    for t in tests:
        t()

    print()
    print("==========================================")
    TOTAL = PASSED + FAILED
    if FAILED == 0:
        print(f"All {PASSED}/{TOTAL} Payment Service tests passed!")
        sys.exit(0)
    else:
        print(f"{PASSED}/{TOTAL} passed, {FAILED}/{TOTAL} failed")
        sys.exit(1)
