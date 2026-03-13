# Requirements: Event Ticketing Platform

**Defined:** 2026-03-13
**Core Value:** Users can reliably book seats under high concurrency with real-time e-ticket delivery, while the platform handles failures gracefully through compensating transactions and event-driven choreography.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Infrastructure

- [x] **INFRA-01**: Docker Compose orchestrates MySQL, RabbitMQ, Redis, Kong, and all 9 microservices with healthchecks
- [x] **INFRA-02**: Shared AMQP library supports connection retry, exchange setup, message publishing, and consumer startup
- [x] **INFRA-03**: Shared AMQP library provides `run_with_amqp()` for multi-threading (Flask main thread + AMQP daemon thread)
- [x] **INFRA-04**: Each microservice has a `/health` endpoint returning `{"status": "healthy"}`
- [x] **INFRA-05**: All services use consistent JSON response format: `{"code": 200, "data": {...}}` or `{"code": 4xx/5xx, "message": "..."}`
- [x] **INFRA-06**: Single `init.sql` creates all 9 databases and sources each service's schema on first boot

### Event Management

- [ ] **EVNT-01**: User can browse and filter events by status, category, and date
- [ ] **EVNT-02**: Admin can create, update, and manage events via OutSystems dashboard calling Event Service REST API
- [ ] **EVNT-03**: Admin can cancel an event, triggering `event.cancelled.{event_id}` on `event_lifecycle` topic exchange

### Seat Management

- [ ] **SEAT-01**: User can view all seats for an event with current availability status
- [ ] **SEAT-02**: User can view available seat count per section for an event
- [ ] **SEAT-03**: Seat reservation uses Redis distributed lock (SET NX EX, 10 min TTL) followed by MySQL pessimistic lock (`FOR UPDATE`)
- [ ] **SEAT-04**: If requested seat is taken, system auto-assigns next best available seat in same section using `SKIP LOCKED`
- [ ] **SEAT-05**: Seat release deletes Redis lock and resets MySQL status to available (compensating transaction)
- [ ] **SEAT-06**: Seat confirmation updates status to booked and removes Redis lock
- [ ] **SEAT-07**: Bulk seat release resets all seats for an event (used in event cancellation)
- [ ] **SEAT-08**: Seat release publishes `seat.released.{event_id}` to `seat_topic` exchange for waitlist choreography

### Booking & Orchestration

- [ ] **BOOK-01**: User can initiate a booking, triggering the orchestration saga (reserve seat -> process payment -> confirm booking)
- [ ] **BOOK-02**: Booking Orchestrator performs compensating transactions on failure (release seat on payment failure, refund on booking failure)
- [ ] **BOOK-03**: Booking Orchestrator detects payment expiry via APScheduler (30s interval) and releases held seats after 10 minutes
- [ ] **BOOK-04**: Booking Orchestrator publishes `booking.confirmed` to `booking_topic` exchange after successful booking
- [ ] **BOOK-05**: Booking Orchestrator publishes `booking.timeout` to `booking_topic` exchange on payment expiry
- [ ] **BOOK-06**: User can view booking status and history
- [ ] **BOOK-07**: Booking status updates to `pending_refund` on event cancellation and `refunded` after refund completion

### Payment

- [ ] **PAY-01**: Payment Service charges user via Stripe PaymentIntent (test mode, SGD currency)
- [ ] **PAY-02**: Payment Service processes refunds via Stripe Refund API with adjusted amount (after service fee deduction)
- [ ] **PAY-03**: Payment Service consumes `refund.process` from `refund_direct` exchange and publishes `refund.completed` after success
- [ ] **PAY-04**: Payment Service retries failed Stripe refunds up to 3 times before sending to dead letter queue

### Ticket

- [ ] **TICK-01**: Ticket Service consumes `booking.confirmed` and generates QR code containing booking validation data
- [ ] **TICK-02**: Ticket Service delivers e-ticket to user via Flask-SocketIO WebSocket (user joins room by booking_id)
- [ ] **TICK-03**: User can retrieve ticket via HTTP fallback if WebSocket delivery was missed
- [ ] **TICK-04**: Ticket Service bulk-invalidates tickets when event is cancelled

### Waitlist

- [ ] **WAIT-01**: User can join waitlist for a sold-out event with preferred section
- [ ] **WAIT-02**: Waitlist Service consumes `seat.released.*` from `seat_topic` exchange and promotes first-in-line user (NO direct HTTP to Seat Service)
- [ ] **WAIT-03**: Promoted user has 10-minute window to complete booking before promotion expires
- [ ] **WAIT-04**: Expired promotions cascade to next waitlisted user by re-publishing `seat.released` event
- [ ] **WAIT-05**: User can view their waitlist position
- [ ] **WAIT-06**: Waitlist is cleared when event is cancelled

### Charging

- [ ] **CHRG-01**: Charging Service consumes `event.cancelled.*` and calculates 10% service fee retention per booking
- [ ] **CHRG-02**: Charging Service publishes `refund.process` to `refund_direct` exchange with adjusted refund amount (original - 10% fee)
- [ ] **CHRG-03**: Admin can view fee breakdown per event and per booking

### Notification

- [ ] **NOTF-01**: Notification Service sends email on booking confirmation
- [ ] **NOTF-02**: Notification Service sends email on payment expiry/timeout
- [ ] **NOTF-03**: Notification Service sends SMS (Twilio) + email on waitlist promotion (time-sensitive)
- [ ] **NOTF-04**: Notification Service sends batch cancellation emails to all affected users
- [ ] **NOTF-05**: Notification Service sends refund confirmation email with fee breakdown
- [ ] **NOTF-06**: User can view notification history

### API Gateway

- [ ] **GATE-01**: Kong routes all API requests to correct microservices via declarative YAML config
- [ ] **GATE-02**: Kong applies global rate limiting (10 requests/second)

### Frontend

- [ ] **FRNT-01**: React SPA displays event listings with search and filter
- [ ] **FRNT-02**: React SPA shows seat map with real-time availability for selected event
- [ ] **FRNT-03**: React SPA handles booking flow (seat selection -> payment -> confirmation)
- [ ] **FRNT-04**: React SPA receives e-ticket via WebSocket and displays QR code
- [ ] **FRNT-05**: React SPA shows waitlist join and position tracking
- [ ] **FRNT-06**: React SPA shows booking history and status

### Observability

- [ ] **OBSV-01**: All services pass correlation ID through HTTP headers and AMQP message properties for cross-service tracing
- [ ] **OBSV-02**: Failed AMQP messages route to dead letter queues for inspection and debugging

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Differentiators

- **DIFF-01**: Visual saga state tracking on frontend (WebSocket updates as orchestrator progresses)
- **DIFF-02**: Idempotent operations on payment and booking creation (idempotency keys)
- **DIFF-03**: Health check dashboard showing service status
- **DIFF-04**: Retry with exponential backoff in Booking Orchestrator

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real money payments | University project; Stripe test mode only |
| OAuth / social login | Adds complexity without demonstrating ESD patterns |
| Dynamic pricing | Massive complexity; not relevant to 3 scenarios |
| Ticket resale / transfer | Separate domain; dilutes focus |
| Multi-currency | Unnecessary for Singapore demo |
| Full-text search / Elasticsearch | Overkill for demo event count |
| Mobile app / PWA | Web-first; React SPA is sufficient |
| Real-time chat | Not core to ticketing |
| PDF ticket generation | QR via WebSocket is the BTL feature |
| Complex RBAC | Two roles max (user + admin via OutSystems) |
| Per-user rate limiting | Kong global rate limiting is sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 1 | Complete |
| INFRA-05 | Phase 1 | Complete |
| INFRA-06 | Phase 1 | Complete |
| EVNT-01 | Phase 2 | Pending |
| EVNT-02 | Phase 2 | Pending |
| EVNT-03 | Phase 5 | Pending |
| SEAT-01 | Phase 2 | Pending |
| SEAT-02 | Phase 2 | Pending |
| SEAT-03 | Phase 2 | Pending |
| SEAT-04 | Phase 2 | Pending |
| SEAT-05 | Phase 2 | Pending |
| SEAT-06 | Phase 2 | Pending |
| SEAT-07 | Phase 5 | Pending |
| SEAT-08 | Phase 4 | Pending |
| BOOK-01 | Phase 3 | Pending |
| BOOK-02 | Phase 3 | Pending |
| BOOK-03 | Phase 3 | Pending |
| BOOK-04 | Phase 3 | Pending |
| BOOK-05 | Phase 3 | Pending |
| BOOK-06 | Phase 2 | Pending |
| BOOK-07 | Phase 5 | Pending |
| PAY-01 | Phase 3 | Pending |
| PAY-02 | Phase 5 | Pending |
| PAY-03 | Phase 5 | Pending |
| PAY-04 | Phase 5 | Pending |
| TICK-01 | Phase 3 | Pending |
| TICK-02 | Phase 3 | Pending |
| TICK-03 | Phase 3 | Pending |
| TICK-04 | Phase 5 | Pending |
| WAIT-01 | Phase 4 | Pending |
| WAIT-02 | Phase 4 | Pending |
| WAIT-03 | Phase 4 | Pending |
| WAIT-04 | Phase 4 | Pending |
| WAIT-05 | Phase 4 | Pending |
| WAIT-06 | Phase 4 | Pending |
| CHRG-01 | Phase 5 | Pending |
| CHRG-02 | Phase 5 | Pending |
| CHRG-03 | Phase 5 | Pending |
| NOTF-01 | Phase 4 | Pending |
| NOTF-02 | Phase 4 | Pending |
| NOTF-03 | Phase 4 | Pending |
| NOTF-04 | Phase 4 | Pending |
| NOTF-05 | Phase 4 | Pending |
| NOTF-06 | Phase 4 | Pending |
| GATE-01 | Phase 6 | Pending |
| GATE-02 | Phase 6 | Pending |
| FRNT-01 | Phase 6 | Pending |
| FRNT-02 | Phase 6 | Pending |
| FRNT-03 | Phase 6 | Pending |
| FRNT-04 | Phase 6 | Pending |
| FRNT-05 | Phase 6 | Pending |
| FRNT-06 | Phase 6 | Pending |
| OBSV-01 | Phase 6 | Pending |
| OBSV-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 57 total
- Mapped to phases: 57
- Unmapped: 0

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-13 after roadmap creation*
