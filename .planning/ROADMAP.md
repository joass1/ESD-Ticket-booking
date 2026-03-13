# Roadmap: Event Ticketing Platform

## Overview

This roadmap delivers a microservices event ticketing platform across 6 phases, structured around the 3 mandatory demo scenarios. Each phase builds on the previous: shared infrastructure first, then atomic data services, then the orchestration saga (Scenario 1), choreography-based waitlist (Scenario 2), fan-out event cancellation (Scenario 3), and finally the API gateway and React frontend that tie everything together. The dependency order is non-negotiable -- each layer enables the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Infrastructure Foundation** - Docker Compose, shared AMQP library, database init, healthchecks, and response conventions
- [ ] **Phase 2: Foundation Services** - Event, Seat, and Booking data services with Redis distributed locking
- [ ] **Phase 3: Booking Saga** - Orchestrator, Payment, and Ticket services delivering end-to-end Scenario 1
- [ ] **Phase 4: Waitlist and Notifications** - Waitlist choreography (Scenario 2) and Notification Service across all exchanges
- [ ] **Phase 5: Event Cancellation** - Fan-out cancellation with charging, batch refunds, and ticket invalidation (Scenario 3)
- [ ] **Phase 6: Gateway and Frontend** - Kong API Gateway, React SPA, and full-stack integration of all 3 scenarios

## Phase Details

### Phase 1: Infrastructure Foundation
**Goal**: All services can boot, connect to their databases, publish/consume AMQP messages with thread safety, and respond with consistent formats
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06
**Success Criteria** (what must be TRUE):
  1. Running `docker compose up` starts MySQL, RabbitMQ, Redis, and Kong with all healthchecks passing
  2. A test service can publish a message to RabbitMQ and a consumer on a separate thread receives it using the shared AMQP library
  3. Every running service responds to GET /health with `{"status": "healthy"}`
  4. All 9 databases are created and schemas loaded on first boot from a single init.sql
  5. Services return consistent JSON format: `{"code": 200, "data": {...}}` for success and `{"code": 4xx/5xx, "message": "..."}` for errors
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md -- Docker Compose infrastructure, database init.sql with all 9 schemas and seed data, Kong declarative config, env template
- [ ] 01-02-PLAN.md -- Shared AMQP library, shared response helper, all 9 minimal service scaffolds with /health endpoints
- [ ] 01-03-PLAN.md -- Integration verification: boot stack, test health endpoints, test databases, test AMQP publish/consume

### Phase 2: Foundation Services
**Goal**: Users can browse events, view seat availability with real-time locking, and the booking record layer is ready for orchestration
**Depends on**: Phase 1
**Requirements**: EVNT-01, EVNT-02, SEAT-01, SEAT-02, SEAT-03, SEAT-04, SEAT-05, SEAT-06, BOOK-06
**Success Criteria** (what must be TRUE):
  1. User can browse events and filter by status, category, and date via Event Service API
  2. Admin can create and update events via REST endpoints (OutSystems integration point ready)
  3. User can view all seats for an event and see available count per section
  4. Requesting a taken seat auto-assigns the next best available seat in the same section
  5. Seat reservation acquires a Redis distributed lock (SET NX EX) and MySQL pessimistic lock, and seat release correctly reverses both
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD
- [ ] 02-03: TBD

### Phase 3: Booking Saga
**Goal**: Users can complete end-to-end seat booking with payment, receive QR e-tickets via WebSocket, and the system compensates on any failure
**Depends on**: Phase 2
**Requirements**: BOOK-01, BOOK-02, BOOK-03, BOOK-04, BOOK-05, PAY-01, TICK-01, TICK-02, TICK-03
**Success Criteria** (what must be TRUE):
  1. User can book a seat end-to-end: select seat, pay via Stripe, and receive a confirmed booking
  2. On payment failure, the orchestrator releases the held seat (compensating transaction)
  3. If payment is not completed within 10 minutes, APScheduler detects expiry and releases the seat automatically
  4. After booking confirmation, a QR code e-ticket is delivered to the user via WebSocket in real time
  5. User can retrieve their e-ticket via HTTP fallback if the WebSocket delivery was missed
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Waitlist and Notifications
**Goal**: Users can join waitlists for sold-out events and get automatically promoted when seats free up, with email/SMS notifications across all booking lifecycle events
**Depends on**: Phase 3
**Requirements**: WAIT-01, WAIT-02, WAIT-03, WAIT-04, WAIT-05, WAIT-06, SEAT-08, NOTF-01, NOTF-02, NOTF-03, NOTF-04, NOTF-05, NOTF-06
**Success Criteria** (what must be TRUE):
  1. User can join a waitlist for a sold-out event and see their position in the queue
  2. When a seat is released, the first-in-line waitlisted user is automatically promoted via AMQP (no direct HTTP between Seat and Waitlist services)
  3. Promoted user has a 10-minute window; if expired, promotion cascades to the next waitlisted user
  4. User receives email on booking confirmation, payment timeout, and refund completion
  5. User receives SMS and email on waitlist promotion (time-sensitive notification)
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD

### Phase 5: Event Cancellation
**Goal**: Admin can cancel an event, triggering parallel fan-out to all affected services with 90% refunds, ticket invalidation, and status updates
**Depends on**: Phase 4
**Requirements**: EVNT-03, SEAT-07, BOOK-07, PAY-02, PAY-03, PAY-04, TICK-04, CHRG-01, CHRG-02, CHRG-03
**Success Criteria** (what must be TRUE):
  1. Admin cancels an event and all five consumer services (Booking, Seat, Waitlist, Notification, Charging) react via topic exchange fan-out
  2. Charging Service calculates 10% service fee and triggers batch refunds at 90% of original amount
  3. Payment Service processes Stripe refunds with up to 3 retries, routing failures to dead letter queue
  4. All bookings for the cancelled event update to refunded status, all seats reset to available, all tickets are invalidated, and the waitlist is cleared
  5. All affected users receive cancellation notification emails with fee breakdown
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD

### Phase 6: Gateway and Frontend
**Goal**: Users interact with the full platform through a React SPA routed via Kong API Gateway, with all 3 scenarios working end-to-end
**Depends on**: Phase 5
**Requirements**: GATE-01, GATE-02, FRNT-01, FRNT-02, FRNT-03, FRNT-04, FRNT-05, FRNT-06, OBSV-01, OBSV-02
**Success Criteria** (what must be TRUE):
  1. All API requests route through Kong to the correct microservice via declarative YAML config
  2. Kong applies rate limiting (10 req/s) and handles CORS (no CORS in individual Flask services)
  3. User can browse events, select seats on a seat map, complete booking, and see QR e-ticket -- all in the React SPA
  4. User can join a waitlist and track position in the React SPA
  5. Correlation IDs propagate across HTTP and AMQP calls, and failed messages land in dead letter queues for debugging
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure Foundation | 1/3 | In Progress | - |
| 2. Foundation Services | 0/3 | Not started | - |
| 3. Booking Saga | 0/3 | Not started | - |
| 4. Waitlist and Notifications | 0/3 | Not started | - |
| 5. Event Cancellation | 0/3 | Not started | - |
| 6. Gateway and Frontend | 0/3 | Not started | - |
