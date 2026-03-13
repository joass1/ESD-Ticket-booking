# Feature Landscape

**Domain:** Event Ticketing Platform (University Microservices Project)
**Researched:** 2026-03-13
**Mode:** Ecosystem (Features Dimension)

## Table Stakes

Features users expect from any event ticketing platform. Missing = the demo feels incomplete or broken.

### Scenario 1: High-Demand Seat Booking (Orchestration Saga)

| Feature | Why Expected | Complexity | Service(s) | Notes |
|---------|--------------|------------|------------|-------|
| Event browsing and listing | Users need to discover events before booking | Low | Event Service, React Frontend | CRUD with search/filter |
| Interactive seat selection | Users expect to see available seats and pick one | Medium | Seat Service, React Frontend | Visual seat map in frontend; Seat Service tracks availability |
| Seat hold with timeout | Prevents double-booking; industry standard (5-10 min hold) | Medium | Booking Orchestrator, Seat Service | Professor mandates 30s APScheduler interval for payment expiry |
| Distributed seat locking | Concurrent users must not book same seat | Medium | Seat Service + Redis | Redis distributed lock is BTL feature; non-negotiable for concurrency |
| Payment processing | Cannot sell tickets without payment | Medium | Payment Service + Stripe | Stripe test mode; charge on booking confirmation |
| Booking confirmation | Users need proof their booking succeeded | Low | Booking Service | Status transitions: pending -> confirmed -> cancelled |
| Compensating transactions (rollback) | Failed payment must release seat; failed seat lock must not charge | High | Booking Orchestrator | Saga compensation: release seat, refund payment, cancel booking |
| Payment expiry handling | Held seats must release if user does not pay in time | Medium | Booking Orchestrator (APScheduler) | Professor requirement: expiry logic lives inside orchestrator |
| Order/booking history | Users expect to see past and current bookings | Low | Booking Service, React Frontend | Simple query by user ID |

### Scenario 2: Waitlist Management (Choreography via AMQP)

| Feature | Why Expected | Complexity | Service(s) | Notes |
|---------|--------------|------------|------------|-------|
| Join waitlist for sold-out events | Standard feature on Ticketmaster, Eventbrite, etc. | Low | Waitlist Service | User added to queue when no seats available |
| Automatic waitlist promotion | When a seat frees up, next waitlisted user gets offered it | High | Waitlist Service + Seat Service via RabbitMQ | Professor constraint: NO direct HTTP between Seat and Waitlist |
| Cascading promotions | If promoted user does not respond, promote next in line | High | Waitlist Service | Choreography chain via AMQP events |
| Waitlist position visibility | Users want to know where they stand in the queue | Low | Waitlist Service, React Frontend | Return position number on join |
| Notification on promotion | User must be told they have been promoted | Medium | Notification Service via AMQP | Email/SMS triggered by waitlist.promoted event |

### Scenario 3: Event Cancellation (Batch Refund + Fee Retention)

| Feature | Why Expected | Complexity | Service(s) | Notes |
|---------|--------------|------------|------------|-------|
| Event cancellation by organizer | Organizers must be able to cancel events | Low | Event Service (+ OutSystems admin) | Triggers event.cancelled on topic exchange |
| Batch refund processing | All ticket holders must be refunded | High | Charging Service + Payment Service | Must handle N refunds reliably; partial failures need retry |
| Service fee retention (10%) | Platform retains revenue; industry standard practice | Medium | Charging Service | Professor requirement: refund 90%, retain 10% |
| Cancellation notifications | All affected users must be notified | Medium | Notification Service via AMQP | Fan-out from topic exchange to notification queue |
| Booking status update on cancel | Bookings must reflect cancelled state | Low | Booking Service via AMQP | Listens to event.cancelled, updates all bookings for that event |
| Waitlist clearing on cancel | Waitlisted users must be removed and notified | Low | Waitlist Service via AMQP | Listens to event.cancelled, clears waitlist entries |

### Cross-Cutting Table Stakes

| Feature | Why Expected | Complexity | Service(s) | Notes |
|---------|--------------|------------|------------|-------|
| QR code e-ticket generation | Modern ticketing standard; replaces paper tickets | Medium | Ticket Service | Generate QR with booking data |
| Real-time e-ticket delivery | Users expect instant confirmation | Medium | Ticket Service + Flask-SocketIO | BTL feature; WebSocket push to frontend by booking_id room |
| Email notifications | Booking confirmation, cancellation, waitlist updates | Medium | Notification Service + Gmail SMTP | Triggered by AMQP events |
| SMS notifications | Secondary notification channel | Low | Notification Service + Twilio | Optional but expected in modern platforms |
| API Gateway | Single entry point, rate limiting, routing | Medium | Kong (DB-less) | BTL feature; declarative YAML config |
| Admin dashboard | Organizers need to manage events | Medium | OutSystems + Event Service REST | OutSystems integration is course requirement |

## Differentiators

Features that elevate the demo beyond "works correctly" into "impressive university project." Not expected, but valued by graders and demo audiences.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Visual saga state tracking | Show saga step progression in real-time on frontend | Medium | WebSocket updates as orchestrator progresses through steps; demonstrates understanding of saga pattern |
| Seat map with live availability | Real-time seat status updates across all connected clients | High | WebSocket broadcast when seats are locked/released; visually impressive |
| Graceful degradation dashboard | Show which services are up/down, circuit breaker status | Medium | Health check endpoints + frontend status page; demonstrates resilience awareness |
| Retry with exponential backoff | Transient failures auto-recover instead of hard-failing | Medium | In Booking Orchestrator for payment retries; shows production-grade thinking |
| Dead letter queue handling | Failed AMQP messages go to DLQ for inspection, not lost | Low | RabbitMQ DLQ config; shows operational maturity |
| Request tracing / correlation IDs | Trace a booking across all 9 services via a single ID | Medium | Pass correlation_id through HTTP headers and AMQP message properties; invaluable for debugging |
| Idempotent operations | Duplicate requests produce same result (safe retries) | Medium | Idempotency keys on payment and booking creation; prevents double-charge |
| Metrics and logging dashboard | Centralized view of system behavior | Medium | Could use simple logging aggregation; nice for demo |

## Anti-Features

Features to deliberately NOT build. Building these would waste limited time or violate project constraints.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real money payment processing | University project; liability risk; Stripe test mode mandated | Use Stripe test keys exclusively; document this clearly |
| OAuth / social login | Out of scope per PROJECT.md; adds complexity without demonstrating ESD concepts | Simple email/password or even hardcoded demo users |
| Dynamic pricing / price optimization | Massive complexity; not relevant to the 3 scenarios | Fixed ticket prices per event |
| Ticket resale / transfer marketplace | Entire separate domain; would dilute focus on saga/choreography patterns | Out of scope; mention as future work if asked |
| Multi-currency support | Unnecessary for Singapore university demo | Single currency (SGD or USD) |
| Seat category tiering (VIP, Standard, etc.) | Adds data model complexity without demonstrating new patterns | If time permits, simple category field; do not build pricing tiers |
| Full-text search / Elasticsearch | Overkill for event count in a demo; adds infrastructure complexity | Simple SQL LIKE queries or filter by category |
| Mobile app or PWA | Web-first per PROJECT.md; React SPA is sufficient | Responsive React frontend only |
| Real-time chat / support | Not core to ticketing; not relevant to any scenario | Out of scope |
| PDF ticket generation | QR code e-ticket via WebSocket is the BTL feature; PDF adds complexity | QR code image delivered via WebSocket is sufficient |
| Complex user roles / RBAC | University demo; two roles max (user, admin via OutSystems) | Simple role check; OutSystems handles admin separately |
| Rate limiting per user (advanced) | Kong basic rate limiting is BTL; per-user tracking is overkill | Kong global/route-level rate limiting is sufficient |

## Feature Dependencies

```
Event Service CRUD
  |-> Seat creation (seats belong to events)
  |-> Booking flow (must have event to book)
  |-> OutSystems admin dashboard (manages events)

Seat Service + Redis locking
  |-> Booking Orchestrator saga (needs seat lock/release)
  |-> Waitlist promotion (needs seat availability signal)

Payment Service (Stripe)
  |-> Booking Orchestrator saga (needs charge/refund)
  |-> Charging Service (calculates fee, calls Payment for refund)

Booking Orchestrator
  |-> Requires: Seat Service, Payment Service, Booking Service all operational
  |-> Produces: booking.confirmed / booking.failed events

Notification Service
  |-> Requires: RabbitMQ configured with queues
  |-> Consumes: booking.confirmed, waitlist.promoted, event.cancelled
  |-> Independent: can be built/tested last

Ticket Service (QR + WebSocket)
  |-> Requires: booking.confirmed event
  |-> Requires: React frontend WebSocket client

Waitlist Service
  |-> Requires: RabbitMQ (seat.released events from Seat Service)
  |-> Requires: Notification Service for promotion alerts
  |-> NO dependency on Seat Service HTTP (professor constraint)

Charging Service
  |-> Requires: event.cancelled trigger
  |-> Requires: Payment Service for refund execution
  |-> Requires: Booking Service for batch booking lookup

Topic Exchange (event.cancelled fan-out)
  |-> Requires: Event Service, Booking Service, Waitlist Service,
      Notification Service, Charging Service all subscribed
```

**Critical path for Scenario 1:** Event Service -> Seat Service (+ Redis) -> Payment Service -> Booking Orchestrator -> Booking Service -> Ticket Service -> React Frontend

**Critical path for Scenario 2:** Seat Service (seat.released event) -> RabbitMQ -> Waitlist Service -> RabbitMQ -> Notification Service

**Critical path for Scenario 3:** Event Service (event.cancelled) -> Topic Exchange -> [Booking Service, Charging Service, Waitlist Service, Notification Service] in parallel

## MVP Recommendation

Given the 2-week timeline and 5-person team, prioritize in this order:

### Phase 1: Foundation (Days 1-3)
1. **Docker Compose infrastructure** -- MySQL, RabbitMQ, Redis, Kong
2. **Event Service CRUD** -- base entity everything else depends on
3. **Seat Service with Redis locking** -- core concurrency feature
4. **Booking Service** -- booking record management
5. **Shared AMQP library** -- reused by every async service

### Phase 2: Scenario 1 - Booking Flow (Days 4-7)
6. **Payment Service (Stripe)** -- charge and refund capability
7. **Booking Orchestrator** -- saga with compensation + APScheduler expiry
8. **Ticket Service** -- QR generation + WebSocket delivery
9. **React frontend** -- event browse, seat select, booking flow, e-ticket display

### Phase 3: Scenario 2 + 3 (Days 8-11)
10. **Waitlist Service** -- choreography via AMQP
11. **Notification Service** -- email + SMS on events
12. **Charging Service** -- fee calculation + batch refund
13. **Topic exchange setup** -- event.cancelled fan-out

### Phase 4: Polish (Days 12-14)
14. **Kong API Gateway** -- declarative config, rate limiting
15. **OutSystems admin dashboard** -- event management
16. **End-to-end testing** -- all 3 scenarios working
17. **Demo preparation** -- happy path + failure demos

**Defer entirely:**
- Dynamic pricing: not relevant to any scenario
- Ticket transfer: separate domain
- Advanced search: unnecessary for demo scale
- Per-user rate limiting: global is sufficient

## Feature Prioritization Matrix

| Feature | User Impact | Demo Impact | Complexity | Priority |
|---------|-------------|-------------|------------|----------|
| Seat locking (Redis) | Critical | High (BTL) | Medium | P0 |
| Booking orchestration saga | Critical | High (course req) | High | P0 |
| Payment expiry (APScheduler) | Critical | High (prof req) | Medium | P0 |
| Compensating transactions | Critical | High (course req) | High | P0 |
| QR e-ticket + WebSocket | High | High (BTL) | Medium | P0 |
| Waitlist choreography (AMQP) | High | High (course req) | High | P0 |
| Event cancellation fan-out | High | High (course req) | Medium | P0 |
| Batch refund + 10% fee | High | High (prof req) | Medium | P0 |
| Email/SMS notifications | Medium | Medium | Medium | P1 |
| Kong API Gateway | Low | High (BTL) | Medium | P1 |
| OutSystems admin | Low | Medium (course req) | Medium | P1 |
| Interactive seat map UI | Medium | High (visual wow) | Medium | P1 |
| Saga state visualization | Low | High (visual wow) | Medium | P2 |
| Correlation ID tracing | Low | Medium | Low | P2 |
| Dead letter queues | Low | Medium | Low | P2 |
| Idempotent operations | Medium | Low | Medium | P2 |
| Health check dashboard | Low | Medium | Low | P3 |

**P0** = Must have for demo. Directly maps to the 3 required scenarios or professor constraints.
**P1** = Should have. Course requirements or significant demo value.
**P2** = Nice to have. Shows production-grade thinking.
**P3** = Only if time permits.

## Sources

- [Softjourn: Must-Have Ticketing Features](https://softjourn.com/insights/top-ticketing-features)
- [Bizzabo: Event Ticketing Platform Features](https://www.bizzabo.com/blog/event-ticketing-software-platform-features)
- [Design Gurus: Designing an E-Ticketing System](https://www.designgurus.io/blog/design-ticketing-system)
- [Hello Interview: Ticketmaster System Design](https://www.hellointerview.com/learn/system-design/problem-breakdowns/ticketmaster)
- [Arxiv: High-Concurrency Ticket Sales Microservice Framework](https://arxiv.org/html/2512.24941)
- [Temporal: Mastering Saga Patterns](https://temporal.io/blog/mastering-saga-patterns-for-distributed-transactions-in-microservices)
- [Microservices.io: Saga Pattern](https://microservices.io/patterns/data/saga.html)
- [SimpleTix: Cancellation Options](https://www.simpletix.com/event-ticketing-cancellation-options/)
- [Ticmint: Ticket Cancellation and Refund](https://support.ticmint.com/support/solutions/articles/150000202367-ticket-cancellation-and-refund)
- [Imagina: Managing Refunds and Cancellations](https://imagina.com/en/blog/article/online-ticketin-how-to-manage-refunds-and-cancellations/)
