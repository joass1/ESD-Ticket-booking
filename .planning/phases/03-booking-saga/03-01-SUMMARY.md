---
phase: 03-booking-saga
plan: 01
subsystem: payments, orchestration
tags: [stripe, saga, apscheduler, amqp, compensating-transactions]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: "Seat Service reserve/release/confirm, Booking Service CRUD, AMQP library"
provides:
  - "Payment Service with Stripe PaymentIntent create/verify"
  - "Booking Orchestrator with saga state machine and compensating transactions"
  - "APScheduler payment expiry detection (10min timeout)"
  - "AMQP publishing of booking.confirmed and booking.timeout events"
affects: [04-choreography, 05-fan-out, 06-integration]

# Tech tracking
tech-stack:
  added: [stripe, APScheduler]
  patterns: [saga-orchestration, compensating-transactions, payment-intent-flow, scheduled-expiry]

key-files:
  created: []
  modified:
    - services/payment/app.py
    - services/booking_orchestrator/app.py
    - services/seat/app.py
    - docker-compose.yml
    - db/init.sql

key-decisions:
  - "Saga uses optimistic locking on PAYMENT_PENDING status to prevent race between confirm and APScheduler timeout"
  - "AMQP publishing uses dedicated connection (pika not thread-safe) with lazy reconnection"
  - "Compensate function wraps each step in try/except to prevent cascading failures"

patterns-established:
  - "Saga state machine: STARTED -> SEAT_RESERVED -> PAYMENT_PENDING -> PAYMENT_SUCCESS -> CONFIRMED (or FAILED/TIMEOUT)"
  - "Compensating transactions: release seat + update booking on any saga failure"
  - "APScheduler interval job for background cleanup of expired sagas"

requirements-completed: [BOOK-01, BOOK-02, BOOK-03, BOOK-04, BOOK-05, PAY-01]

# Metrics
duration: 3min
completed: 2026-03-13
---

# Phase 3 Plan 1: Payment Service and Booking Orchestrator Summary

**Stripe PaymentIntent integration with saga orchestrator coordinating seat reservation, booking creation, payment, and compensating transactions with APScheduler expiry**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-13T15:35:13Z
- **Completed:** 2026-03-13T15:38:26Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Payment Service with Stripe PaymentIntent create/verify endpoints and Transaction model
- Booking Orchestrator implementing full saga state machine across Seat, Booking, and Payment services
- Compensating transactions that release seats and update bookings on any failure step
- APScheduler background job polling every 30s for expired PAYMENT_PENDING sagas
- AMQP event publishing for booking.confirmed and booking.timeout to booking_topic exchange

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement Payment Service with Stripe PaymentIntent** - `a0f08d6` (feat)
2. **Task 2: Implement Booking Orchestrator with saga state machine** - `839cdf1` (feat)

## Files Created/Modified
- `services/payment/app.py` - Full Payment Service with Transaction model, Stripe create/verify endpoints
- `services/booking_orchestrator/app.py` - Saga orchestrator with initiate/confirm endpoints, APScheduler, AMQP publishing
- `services/seat/app.py` - Added section_price to reserve response (deviation fix)
- `docker-compose.yml` - Added STRIPE_SECRET_KEY env var to payment service
- `db/init.sql` - Added 'failed' and 'expired' to booking status ENUM

## Decisions Made
- Saga uses optimistic locking: confirm endpoint only proceeds if status is PAYMENT_PENDING (race guard with APScheduler)
- AMQP publishing uses a dedicated pika connection with lazy reconnection on failure
- Compensate function wraps each compensation call in try/except to avoid cascading failures
- APScheduler sets saga to TIMEOUT before compensating so booking gets 'expired' status (not 'failed')

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added section_price to seat reserve response**
- **Found during:** Task 2 (Booking Orchestrator implementation)
- **Issue:** Orchestrator needs section_price from seat reserve response to set booking amount, but reserve endpoint did not include it
- **Fix:** Added section_price field to both direct and auto-assigned reserve response paths in seat service
- **Files modified:** services/seat/app.py
- **Verification:** Code review confirms section object is already queried in reserve flow
- **Committed in:** `4beec31`

**2. [Rule 3 - Blocking] Added failed/expired to booking status ENUM**
- **Found during:** Task 2 (Booking Orchestrator implementation)
- **Issue:** Compensating transactions set booking status to 'failed' or 'expired' but the DB ENUM only had pending/confirmed/cancelled/pending_refund/refunded
- **Fix:** Added 'failed' and 'expired' to the bookings table status ENUM in init.sql
- **Files modified:** db/init.sql
- **Verification:** Schema now supports all status values used by orchestrator
- **Committed in:** `3b90b25`

---

**Total deviations:** 2 auto-fixed (2 blocking issues)
**Impact on plan:** Both fixes required for orchestrator to function correctly. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required

**External services require manual configuration:**
- STRIPE_SECRET_KEY environment variable must be set (from Stripe Dashboard -> Developers -> API keys -> Secret key starting with sk_test_)
- Add to .env file: `STRIPE_SECRET_KEY=sk_test_your_key_here`

## Next Phase Readiness
- Payment and Orchestrator services complete, ready for choreography consumers (notification, ticket generation)
- booking.confirmed and booking.timeout events are being published to booking_topic exchange
- Next plans can subscribe to these events for downstream processing

---
*Phase: 03-booking-saga*
*Completed: 2026-03-13*
