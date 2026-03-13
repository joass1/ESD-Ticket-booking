# Architecture Patterns

**Domain:** Event Ticketing Microservices Platform
**Researched:** 2026-03-13
**Confidence:** HIGH (architecture is professor-mandated with clear constraints)

## System Overview

```
                          +-------------------+
                          |   React Frontend  |
                          | (SPA, port 3000)  |
                          +--------+----------+
                                   |
                          HTTP + WebSocket (SocketIO)
                                   |
                          +--------v----------+
                          |   Kong Gateway    |
                          |  (DB-less, 8000)  |
                          +--------+----------+
                                   |
              +--------------------+--------------------+
              |                    |                     |
   +----------v-----+   +---------v--------+   +--------v---------+
   | Event Service   |   | Booking          |   | Waitlist Service  |
   | (5001, atomic)  |   | Orchestrator     |   | (5007, atomic)    |
   |                 |   | (5010, composite)|   |                   |
   | event_db        |   | saga_log_db      |   | waitlist_db       |
   +---------+-------+   +--+---+---+-------+   +-------+----------+
             |               |   |   |                   ^
             |          HTTP |   |   | HTTP              | AMQP only
             |               v   v   v                   | (seat.released)
             |     +---------++ +v---------+ +-----------v---------+
             |     | Seat     | | Payment  | | (no direct HTTP)    |
             |     | Service  | | Service  | +---------------------+
             |     | (5003)   | | (5004)   |
             |     | seat_db  | | pay_db   |
             |     | + Redis  | | + Stripe |
             |     +----------+ +----------+
             |
   +---------v------ RabbitMQ (6 exchanges) --------+
   |                                                  |
   |  booking_topic    seat_topic    event_lifecycle   |
   |  waitlist_topic   refund_direct ticket_direct     |
   |                                                  |
   +-----+--------+--------+--------+--------+-------+
         |        |        |        |        |
   +-----v--+ +---v----+ +v------+ +v------+v--------+
   | Ticket  | |Charging| |Booking| |Notif. | Payment |
   | Service | |Service | |Service| |Service| (refund |
   | (5006)  | |(5008)  | |(5002) | |(5005) |  path)  |
   | +SocketIO|         | |       | |+SMTP  |         |
   +---------+ +--------+ +-------+ |+Twilio|         |
                                     +-------+---------+
```

## Component Responsibilities

### Tier 1: Entry Points

| Component | Port | Type | Responsibility | Owns |
|-----------|------|------|---------------|------|
| Kong API Gateway | 8000 | Infrastructure | Route requests, rate limit (10 req/s), CORS | `kong.yml` (no DB) |
| React Frontend | 3000 | UI | Event browsing, seat selection, booking form, WebSocket e-ticket display | No backend state |

### Tier 2: Orchestration

| Component | Port | Type | Responsibility | Owns |
|-----------|------|------|---------------|------|
| Booking Orchestrator | 5010 | Composite | Saga coordination: reserve seat -> charge payment -> create booking. Payment expiry via APScheduler (30s). | `saga_log_db` (saga state only) |

### Tier 3: Atomic Domain Services

| Component | Port | Type | Responsibility | Owns |
|-----------|------|------|---------------|------|
| Event Service | 5001 | Atomic | Event CRUD, cancellation trigger (publishes to `event_lifecycle`) | `event_db` |
| Booking Service | 5002 | Atomic | Booking records, status tracking. Consumes AMQP for status updates. | `booking_db` |
| Seat Service | 5003 | Atomic | Seat inventory, Redis distributed locking, 2-phase locking (Redis + MySQL FOR UPDATE + SKIP LOCKED) | `seat_db` + Redis locks |
| Payment Service | 5004 | Atomic | Stripe PaymentIntent creation, refund processing via AMQP | `payment_db` |
| Notification Service | 5005 | Atomic | Email (Gmail SMTP) and SMS (Twilio). Pure consumer -- 4 exchanges. | `notification_db` |
| Ticket Service | 5006 | Atomic | QR code generation, WebSocket delivery via Flask-SocketIO rooms | `ticket_db` |
| Waitlist Service | 5007 | Atomic | Waitlist queue, automated promotion on seat release, cascading promotion timeout | `waitlist_db` + Redis TTL |
| Charging Service | 5008 | Atomic | Service fee calculation (10% retention on refunds) | `charging_db` |

### Component Boundaries -- Critical Rules

1. **Booking Orchestrator is the ONLY composite service.** It coordinates via sync HTTP but owns NO domain data (only saga_log).
2. **Every atomic service owns exactly one MySQL database.** No shared databases, ever.
3. **Seat Service and Waitlist Service NEVER call each other via HTTP.** They communicate exclusively through RabbitMQ (`seat.released.{event_id}` on `seat_topic` exchange).
4. **Notification Service is fire-and-forget.** If it is down, no saga fails. It consumes from 4 exchanges asynchronously.
5. **Ticket Service uses eventlet, NOT threading.** Flask-SocketIO requires eventlet monkey-patching. All other services use `threading.Thread(daemon=True)` for AMQP consumers.

## Data Flow

### Scenario 1: Seat Booking (Orchestration Saga)

```
UI ──POST /api/bookings──> Kong ──> Booking Orchestrator
                                        |
                                  1. Create saga_log (STARTED, expires_at=+10min)
                                        |
                                  2. PUT /seats/{id}/reserve ──> Seat Service
                                     (Redis lock + MySQL FOR UPDATE)
                                     On 409: GET /seats/next-best (SKIP LOCKED)
                                        |
                                  3. POST /payments ──> Payment Service
                                     (Stripe PaymentIntent)
                                        |
                                  4. PUT /seats/{id}/confirm ──> Seat Service
                                  5. POST /bookings ──> Booking Service
                                  6. saga_log → CONFIRMED
                                        |
                                  7. PUBLISH booking.confirmed ──> booking_topic
                                        |
                          +-------------+-------------+
                          |                           |
                    Ticket Service              Notification Service
                    (AMQP consumer)             (AMQP consumer)
                          |                           |
                    Generate QR code            Send confirmation email
                    Store in ticket_db
                          |
                    EMIT ticket_ready ──> SocketIO room(booking_id)
                          |
                    UI receives e-ticket
```

**Compensation flow (payment fails):**
```
Booking Orchestrator detects payment failure
  → PUT /seats/{id}/release (Seat Service)
  → saga_log → FAILED
  → PUBLISH booking.cancelled → booking_topic
  → Notification Service sends failure email
```

**Payment expiry (APScheduler, every 30s):**
```
Booking Orchestrator checks: saga_log WHERE status IN (STARTED, SEAT_RESERVED, PAYMENT_PENDING) AND expires_at < NOW()
  → PUT /seats/{id}/release (compensating transaction)
  → saga_log → TIMEOUT
  → PUBLISH booking.timeout → booking_topic
```

### Scenario 2: Waitlist Management (Choreography)

```
UI ──POST /api/waitlist──> Waitlist Service
                               |
                         Insert entry (position calculated)
                         PUBLISH waitlist.joined ──> waitlist_topic
                               |
                         Notification Service: email with position

--- Later, when seat released (from Scenario 1 timeout or Scenario 3) ---

Seat Service: seat status → available
  PUBLISH seat.released.{event_id} ──> seat_topic
                               |
Waitlist Service (AMQP consumer, daemon thread):
  Query next waiting user (FOR UPDATE lock)
  Update entry → promoted, set promoted_seat_id
  Set Redis TTL: waitlist_promotion:{entry_id} (10min)
  PUBLISH waitlist.promoted ──> waitlist_topic
                               |
Notification Service:
  Send SMS (Twilio) -- "Book within 10 minutes!"
  Send email with pre-filled booking URL

--- If promotion expires (APScheduler in Waitlist Service, every 30s) ---

Waitlist Service:
  Find promoted entries with promotion_expires_at < NOW()
  Update → expired
  RE-PUBLISH seat.released.{event_id} ──> seat_topic (cascade!)
  PUBLISH waitlist.expired ──> waitlist_topic
```

**Key architectural insight:** The cascading promotion is elegant -- expired promotions re-publish `seat.released`, which the same Waitlist Service consumer picks up again to promote the next person. This is a self-referencing choreography loop.

### Scenario 3: Event Cancellation (Topic Exchange Fan-out)

```
Admin (OutSystems) ──PUT /api/events/{id}/cancel──> Event Service
                                                       |
                                                 Update event → CANCELLED
                                                 GET /bookings?event_id=X&status=confirmed (from Booking Service)
                                                 PUBLISH event.cancelled.{event_id} ──> event_lifecycle
                                                       |
                    +----------+----------+----------+-+---------+
                    |          |          |          |            |
              Charging    Booking     Seat      Waitlist    Notification
              Service     Service     Service   Service     Service
                 |          |          |          |            |
           Calc 10%    Set status   Bulk      Clear all   Batch cancel
           service     PENDING_    release    entries     emails
           fee         REFUND      seats
                 |                    |
           PUBLISH             PUBLISH
           refund.process      seat.released.{event_id}
           ──> refund_direct   ──> seat_topic
                 |                    |
           Payment Service     (could trigger Scenario 2
           Stripe refund       for a different event's
           (90% amount)        waitlist -- but event is
                 |              cancelled, so waitlist
           PUBLISH              already cleared)
           refund.completed
           ──> refund_direct
                 |
          +------+------+
          |             |
     Booking       Notification
     Service       Service
     status →      "Refund $X
     REFUNDED      processed.
                   Fee $Y retained"
```

## Communication Matrix

| From \ To | Event | Booking | Seat | Payment | Notification | Ticket | Waitlist | Charging | Orchestrator |
|-----------|-------|---------|------|---------|-------------|--------|----------|----------|-------------|
| **Orchestrator** | -- | HTTP | HTTP | HTTP | -- | -- | -- | -- | -- |
| **Event** | -- | HTTP(read) | -- | -- | -- | -- | -- | -- | -- |
| **Seat** | -- | -- | -- | -- | -- | -- | AMQP | -- | -- |
| **Charging** | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| **Payment** | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| **Waitlist** | -- | -- | -- | -- | -- | -- | -- | -- | -- |

**AMQP Publishing Matrix (who publishes to which exchange):**

| Service | Publishes To | Routing Keys |
|---------|-------------|--------------|
| Booking Orchestrator | booking_topic | booking.confirmed, booking.timeout, booking.cancelled |
| Event Service | event_lifecycle | event.cancelled.{event_id} |
| Seat Service | seat_topic | seat.released.{event_id} |
| Waitlist Service | waitlist_topic, seat_topic | waitlist.promoted, waitlist.joined, waitlist.expired, seat.released.{event_id} (re-publish on cascade) |
| Charging Service | refund_direct | refund.process |
| Payment Service | refund_direct | refund.completed |

**AMQP Consuming Matrix (who listens to which exchange):**

| Service | Consumes From | Routing Keys |
|---------|--------------|--------------|
| Ticket Service | booking_topic | booking.confirmed |
| Notification Service | booking_topic, waitlist_topic, event_lifecycle, refund_direct | (nearly all events) |
| Booking Service | event_lifecycle, refund_direct | event.cancelled.*, refund.completed |
| Seat Service | event_lifecycle | event.cancelled.* |
| Waitlist Service | seat_topic, event_lifecycle | seat.released.*, event.cancelled.* |
| Charging Service | event_lifecycle | event.cancelled.* |
| Payment Service | refund_direct | refund.process |

## Patterns to Follow

### Pattern 1: Multi-threaded Flask + AMQP

**What:** Every service that consumes AMQP runs Flask HTTP in the main thread and an AMQP consumer in a daemon thread using `run_with_amqp()` from `shared/amqp_lib.py`.

**When:** Any service that both exposes REST endpoints AND reacts to AMQP events.

**Example:**
```python
# services/notification/app.py
from shared.amqp_lib import run_with_amqp

def setup_consumers(channel):
    # Declare exchanges, bind queues, set callbacks
    channel.basic_consume(queue='notification_booking_queue', on_message_callback=handle_booking)

if __name__ == '__main__':
    run_with_amqp(app, port=5005, consumer_setup_fn=setup_consumers)
    # Main thread: Flask HTTP
    # Daemon thread: AMQP consumer
```

**Exception:** Ticket Service uses `eventlet.monkey_patch()` instead -- SocketIO requires eventlet's async model, not OS threads.

### Pattern 2: Database-per-Service with Startup Schema Creation

**What:** Each service creates its own database and tables on startup using `CREATE DATABASE IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS`.

**When:** Every service.

**Why:** Zero-migration simplicity. Docker Compose can start everything from scratch with no manual DB setup. Idempotent -- safe to restart.

### Pattern 3: Redis + MySQL Two-Phase Locking

**What:** Seat reservation uses Redis `SET NX` as a fast distributed lock (immediate conflict detection), then MySQL `SELECT ... FOR UPDATE` as a durable state transition.

**When:** Seat Service reserve/release/confirm operations.

**Why:** Redis alone is not durable (crashes lose locks). MySQL alone is too slow under high concurrency. The combination gives speed + durability.

```
1. Redis SET seat:{event_id}:{seat_id} NX (TTL 600s) → fast lock
2. MySQL SELECT ... FOR UPDATE WHERE status='available' → durable check
3. MySQL UPDATE status='reserved' → state transition
4. On failure: Redis DEL seat:{event_id}:{seat_id} → release lock
```

### Pattern 4: Saga with Compensating Transactions

**What:** The Booking Orchestrator executes a sequence of HTTP calls. On any step failure, it calls compensating endpoints to undo previous steps.

**When:** Scenario 1 booking flow (multi-service transaction).

**Why:** Distributed transactions (2PC) don't work across microservices. Sagas with explicit compensation are the standard pattern.

```
Forward:  reserve_seat → charge_payment → confirm_seat → create_booking
Compensate: ←←←←←←←←← release_seat ←←←←←←←←←←←←←←←←←←←←←←←←←←←←
```

### Pattern 5: Choreography via Topic Exchange

**What:** Services publish events. Other services subscribe. No central coordinator.

**When:** Scenario 2 (waitlist) and Scenario 3 (cancellation fan-out).

**Why:** Decouples publishers from consumers. Adding a new consumer (e.g., analytics) requires zero changes to the publisher.

### Pattern 6: Self-Referencing Choreography Loop

**What:** Waitlist Service consumes `seat.released`, promotes a user, sets a TTL. On expiry, it re-publishes `seat.released` to promote the next user.

**When:** Cascading waitlist promotions.

**Why:** Avoids a central coordinator for the waitlist chain. Each promotion is independent.

**Risk:** Infinite loop if no users remain. Mitigation: check if waitlist is empty before re-publishing.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Shared Database

**What:** Two services reading/writing the same database.

**Why bad:** Tight coupling, schema changes break multiple services, no independent deployment.

**Instead:** Each service owns its data. Cross-service data access goes through REST APIs or AMQP events.

### Anti-Pattern 2: Synchronous Chains

**What:** Service A calls B, B calls C, C calls D -- all synchronous HTTP.

**Why bad:** Latency compounds. Any failure in the chain fails the whole request. Tight temporal coupling.

**Instead:** Keep sync chains short (Orchestrator -> Seat/Payment/Booking is the max depth = 2 hops). Everything else is async AMQP.

### Anti-Pattern 3: Direct HTTP Between Seat and Waitlist

**What:** Seat Service calling Waitlist Service directly (or vice versa) via HTTP.

**Why bad:** Professor explicitly forbids this. These services should be decoupled.

**Instead:** Seat publishes `seat.released.{event_id}` to `seat_topic`. Waitlist consumes it. No coupling.

### Anti-Pattern 4: Blocking on Notifications

**What:** Making the booking saga wait for email/SMS to send before returning to the user.

**Why bad:** SMTP and Twilio are slow (seconds). User doesn't need to wait.

**Instead:** Notification Service is async-only. Saga publishes event, returns immediately. Notification happens in background.

### Anti-Pattern 5: Storing Secrets in Code

**What:** Hardcoding Stripe keys, Twilio credentials in app.py.

**Instead:** All secrets in `.env` file, injected via Docker Compose environment variables.

## Project Structure (Recommended Directory Layout)

```
ESD Ticket booking/
├── docker-compose.yml
├── .env.example
├── .env                          (git-ignored)
├── kong/
│   └── kong.yml
├── services/
│   ├── event/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py
│   │   └── event.sql
│   ├── booking/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py
│   │   └── booking.sql
│   ├── seat/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py
│   │   └── seat.sql
│   ├── payment/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py
│   │   └── payment.sql
│   ├── notification/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py
│   │   └── notification.sql
│   ├── ticket/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py
│   │   └── ticket.sql
│   ├── waitlist/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py
│   │   └── waitlist.sql
│   ├── charging/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py
│   │   └── charging.sql
│   └── booking_orchestrator/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── app.py
│       └── saga_log.sql
├── shared/
│   └── amqp_lib.py
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── EventList.jsx
│   │   │   ├── EventDetail.jsx
│   │   │   ├── SeatSelection.jsx
│   │   │   ├── Booking.jsx
│   │   │   └── Ticket.jsx
│   │   └── components/
│   │       ├── SeatMap.jsx
│   │       ├── BookingForm.jsx
│   │       └── QRTicket.jsx
│   └── Dockerfile
├── init.sql                      (sources all service .sql files)
└── .planning/
```

## Suggested Build Order (Dependency-Driven)

Build order matters because services depend on each other. The right order minimizes blocked work.

### Layer 0: Infrastructure (must be first)
- `docker-compose.yml` (MySQL, RabbitMQ, Redis, Kong skeleton)
- `shared/amqp_lib.py` (every AMQP service imports this)
- `.env.example`
- `init.sql` (database initialization)

**Rationale:** Everything depends on infrastructure. The shared AMQP library is imported by 7 of 9 services.

### Layer 1: Foundation Services (no upstream dependencies)
Build these in parallel -- they depend on nothing except infrastructure:

- **Event Service** -- standalone CRUD, no AMQP consumption
- **Booking Service** -- standalone CRUD, AMQP consumption is additive
- **Seat Service** -- standalone CRUD + Redis locking, AMQP publishing is additive

**Rationale:** These three are pure data services. They work with just HTTP. AMQP consumers can be added after Layer 2.

### Layer 2: Orchestration (depends on Layer 1)
- **Booking Orchestrator** -- calls Seat, Payment, Booking via HTTP
- **Payment Service** -- called by Orchestrator, needs Stripe

**Rationale:** The Orchestrator needs Seat + Booking + Payment to exist. Payment needs Stripe keys configured. Build these together.

### Layer 3: Event-Driven Services (depends on Layer 1-2 AMQP publishing)
Build these in parallel -- they consume AMQP events from Layer 1-2:

- **Ticket Service** -- consumes `booking.confirmed`, needs SocketIO setup
- **Notification Service** -- consumes from 4 exchanges, needs SMTP + Twilio
- **Charging Service** -- consumes `event.cancelled`, publishes to `refund_direct`

**Rationale:** These services react to events published by Layers 1-2. They can't be tested until publishers exist.

### Layer 4: Choreography (depends on Seat Service AMQP + Notification)
- **Waitlist Service** -- consumes `seat.released` from Seat Service, publishes to `waitlist_topic`

**Rationale:** Waitlist depends on the choreography loop with Seat Service. It also needs Notification Service for promotion alerts.

### Layer 5: Integration & Gateway
- **Kong API Gateway** -- routes to all services, needs all service ports known
- **React Frontend** -- calls Kong, connects to Ticket Service WebSocket

**Rationale:** Gateway and frontend are the integration layer. They need all backend services working.

### Layer 6: Scenario Integration Testing
- End-to-end Scenario 1 (booking saga)
- End-to-end Scenario 2 (waitlist choreography)
- End-to-end Scenario 3 (event cancellation fan-out)

### Dependency Graph Summary

```
Layer 0: Infrastructure + shared/amqp_lib.py
    |
Layer 1: Event + Booking + Seat (parallel, HTTP only)
    |
Layer 2: Booking Orchestrator + Payment (saga HTTP chain)
    |
Layer 3: Ticket + Notification + Charging (AMQP consumers, parallel)
    |
Layer 4: Waitlist (choreography with Seat via AMQP)
    |
Layer 5: Kong + React Frontend (integration)
    |
Layer 6: E2E scenario testing
```

## Scalability Considerations

| Concern | Demo (5 users) | Mid-scale (500 users) | Production (50K users) |
|---------|---------------|----------------------|----------------------|
| Seat locking | Redis single instance fine | Redis single instance still fine | Redis cluster, shorter TTLs |
| AMQP throughput | Single RabbitMQ node | Single node with tuned prefetch | RabbitMQ cluster, multiple consumers per queue |
| Database | Single MySQL, 9 databases | Single MySQL with connection pooling | Separate MySQL instances per service |
| API Gateway | Kong DB-less, single instance | Kong DB-less, single instance | Kong with PostgreSQL, multiple nodes |
| WebSocket | Single Ticket Service instance | Single instance (SocketIO handles ~10K connections) | SocketIO with Redis adapter for multi-instance |

**For this project (university demo):** Single-instance everything is correct. Docker Compose is the right orchestration tool. No need for Kubernetes.

## Sources

- Professor constraints and feedback (PRIMARY -- these are non-negotiable)
- Existing codebase analysis (`.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, `INTEGRATIONS.md`)
- Saga pattern: standard microservices pattern (Chris Richardson, microservices.io)
- Choreography vs orchestration: well-established EDA patterns
- Redis distributed locking: Redis official documentation (SET NX with TTL)

---

*Architecture research: 2026-03-13*
