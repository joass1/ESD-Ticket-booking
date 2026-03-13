# Architecture

**Analysis Date:** 2026-03-13

## Pattern Overview

**Overall:** Microservices with Hybrid Orchestration-Choreography Saga Pattern

**Key Characteristics:**
- **Atomic Services** (8): Event, Booking, Seat, Payment, Notification, Ticket, Waitlist, Charging — each owns its own MySQL database, exposed REST APIs
- **Composite Service** (1): Booking Orchestrator — owns only saga_log, orchestrates the booking workflow via sync HTTP
- **Dual Communication**: Synchronous HTTP for coordinated sagas, Asynchronous AMQP (RabbitMQ) for event-driven choreography
- **Real-Time Delivery**: WebSocket (Flask-SocketIO) from Ticket Service to UI for e-ticket delivery
- **Distributed Locking**: Redis for seat availability enforcement under high concurrency
- **API Gateway**: Kong 3.6 in DB-less mode for declarative routing and rate limiting

## Layers

**API Gateway Layer:**
- Purpose: Route external requests to services, enforce rate limits (10 req/sec globally), provide single entry point
- Location: `kong/kong.yml` (declarative YAML configuration)
- Contains: Route definitions, plugin configurations
- Depends on: All application services being healthy
- Used by: Frontend and external clients via `http://localhost:8000`

**Application Services Layer (HTTP):**
- Purpose: Expose REST endpoints for business logic (CRUD operations, state transitions)
- Location: `services/event/app.py`, `services/booking/app.py`, `services/seat/app.py`, `services/payment/app.py`, `services/notification/app.py`, `services/ticket/app.py`, `services/waitlist/app.py`, `services/charging/app.py`, `services/booking_orchestrator/app.py`
- Contains: Flask applications with business logic, database access, transaction handling
- Depends on: MySQL, Redis, RabbitMQ, external APIs (Stripe, Twilio, Gmail)
- Used by: Kong API Gateway, other services via HTTP

**Message Broker Layer (AMQP):**
- Purpose: Asynchronous event distribution across services, decouple publishers from consumers
- Location: RabbitMQ service (port 5672), exchanges defined across all services
- Contains: Topic and direct exchanges with routing keys for different event types
- Depends on: Services creating exchanges/queues idempotently
- Used by: All services for pub/sub communication

**Data Layer:**
- Purpose: Persistent storage for business entities and saga state
- Location: MySQL (port 3306), separate database per service: `event_db`, `booking_db`, `seat_db`, `payment_db`, `notification_db`, `ticket_db`, `waitlist_db`, `charging_db`, `saga_log_db`
- Contains: Tables with schema defined per service
- Depends on: Docker initialization script
- Used by: All services for state persistence

**Caching/Locking Layer:**
- Purpose: Distributed locks for seat availability, cache for frequently accessed data
- Location: Redis (port 6379)
- Contains: Seat locks (`seat:{event_id}:{seat_id}`), promotion timeouts (`waitlist_promotion:{entry_id}`)
- Depends on: Services implementing Redis connection with retry
- Used by: Seat Service (locking), Waitlist Service (promotion TTL)

**Real-Time Delivery Layer:**
- Purpose: Push e-tickets to UI in real-time via WebSocket
- Location: `services/ticket/app.py` (Flask-SocketIO server)
- Contains: SocketIO event handlers for join/emit
- Depends on: Eventlet monkey-patching, AMQP consumer for `booking.confirmed`
- Used by: Frontend JavaScript client

## Data Flow

**Scenario 1 — Seat Booking (Orchestration-based Saga):**

1. UI sends `POST /api/bookings` with `{user_id, event_id, seat_id, email}` → Kong → Booking Orchestrator
2. Booking Orchestrator (port 5010):
   - Generates `saga_id`, creates saga_log entry with `status=STARTED`, `expires_at=NOW()+10min`
   - Calls `PUT /seats/{seat_id}/reserve` (Seat Service) — reserves seat with Redis lock + MySQL pessimistic lock
   - On conflict: tries auto-assign via `GET /seats/next-best` with SKIP LOCKED
   - Calls `POST /payments` (Payment Service) — creates Stripe PaymentIntent
   - On payment success: calls `PUT /seats/{seat_id}/confirm` (Seat Service), `POST /bookings` (Booking Service)
   - Updates saga_log to `status=CONFIRMED`
   - **Publishes** `booking.confirmed` to `booking_topic` exchange with booking details
   - Returns 201 to UI with booking confirmation

3. UI opens WebSocket connection to Ticket Service (`http://localhost:5006`)
4. UI emits `join_booking` with `booking_id` → Ticket Service joins room
5. Meanwhile, Ticket Service AMQP consumer receives `booking.confirmed`
   - Generates QR code with booking metadata
   - Stores ticket in `ticket_db`
   - **Emits** `ticket_ready` via SocketIO to room `booking_id`
6. UI receives `ticket_ready` event, displays e-ticket with QR

**Background: Payment Expiry (APScheduler in Booking Orchestrator):**
- Every 30 seconds, checks `saga_log` for expired reservations (`status IN (STARTED, SEAT_RESERVED, PAYMENT_PENDING) AND expires_at < NOW()`)
- For each expired: calls `PUT /seats/{seat_id}/release` (compensating transaction)
- Updates saga to `status=TIMEOUT`
- **Publishes** `booking.timeout` to `booking_topic` exchange
- Notification Service consumes and emails user

**Scenario 2 — Waitlist Management (Choreography via AMQP):**

1. User `POST /api/waitlist` with `{event_id, user_id, email, phone, preferred_section}` → Waitlist Service
2. Waitlist Service inserts entry with calculated position
3. **Publishes** `waitlist.joined` to `waitlist_topic` exchange
4. Notification Service consumes `waitlist.joined`, sends email with position

5. When seat is released (manually or via Scenario 1/3), Seat Service:
   - Updates seat to `status=available`
   - **Publishes** `seat.released.{event_id}` to `seat_topic` exchange

6. Waitlist Service AMQP consumer receives `seat.released.{event_id}`
   - Queries next waiting user for that event (with `FOR UPDATE` lock)
   - Updates entry to `status=promoted`, stores `promoted_seat_id`
   - Sets Redis key `waitlist_promotion:{entry_id}` with 10min TTL
   - **Publishes** `waitlist.promoted` to `waitlist_topic` exchange

7. Notification Service consumes `waitlist.promoted`
   - **Sends SMS (Twilio)** — "Seat available! Book within 10 minutes"
   - Sends email with booking URL pre-filled with `seat_id`

8. Background check (APScheduler in Waitlist Service):
   - Every 30 seconds, finds promoted entries with `promotion_expires_at < NOW()`
   - Updates to `status=expired`
   - **Republishes** `seat.released.{event_id}` to trigger next user (cascading promotion)
   - **Publishes** `waitlist.expired` notification

**Scenario 3 — Event Cancellation with Batch Refund (Topic Exchange Fan-out):**

1. Admin calls `PUT /api/events/{event_id}/cancel` (Event Service)
2. Event Service:
   - Updates event to `status=CANCELLED`
   - Queries Booking Service for all confirmed bookings via `GET /api/bookings?event_id=X&status=confirmed`
   - **Publishes** `event.cancelled.{event_id}` to `event_lifecycle` exchange with booking array

3. Five services consume this single message simultaneously (fan-out):

   **Charging Service:**
   - For each booking: calculates `service_fee = amount * 0.10`, `refund_amount = amount - service_fee`
   - Inserts fee record into `service_fees` table
   - **Publishes** `refund.process` to `refund_direct` exchange with adjusted amounts

   **Booking Service:**
   - Updates all bookings to `status=PENDING_REFUND`

   **Seat Service:**
   - Calls bulk release logic: `UPDATE seats SET status='available' WHERE event_id=X`
   - Deletes all Redis locks matching `seat:{event_id}:*`
   - **Publishes** `seat.released.{event_id}` (triggers Scenario 2 waitlist if applicable)

   **Waitlist Service:**
   - Clears all waitlist entries for that event

   **Notification Service:**
   - Sends batch cancellation emails to all affected users

4. Payment Service AMQP consumer receives `refund.process` messages
   - Calls Stripe Refund API with `refund_amount` (NOT original amount)
   - On success: updates transaction to `status=refunded`, **publishes** `refund.completed`
   - On failure: NACKs message for retry

5. Booking Service & Notification Service consume `refund.completed`
   - Booking Service: updates booking to `status=REFUNDED`
   - Notification Service: sends email with breakdown: "Refund $X processed. Service fee $Y retained"

**State Management:**

- **Saga State**: Stored in `saga_log_db` (Booking Orchestrator), tracks saga transitions (STARTED → SEAT_RESERVED → PAYMENT_SUCCESS → CONFIRMED)
- **Booking State**: Stored in `booking_db`, status transitions (PENDING → CONFIRMED → REFUNDED/CANCELLED)
- **Seat State**: Stored in `seat_db`, status enum (available → reserved → booked → released)
- **Redis Transient State**: Seat locks (10min TTL), waitlist promotion timeouts (10min TTL) — auto-cleanup on expiry
- **AMQP Message Persistence**: All messages published with `delivery_mode=2` (persistent) — survive RabbitMQ restart

## Key Abstractions

**Saga (Orchestration):**
- Purpose: Represent a long-running booking transaction with multiple steps and compensating actions
- Examples: `services/booking_orchestrator/app.py` (saga_log table)
- Pattern: Compensating transactions (release seat on payment failure)

**Atomic Service:**
- Purpose: Self-contained business domain with its own DB, REST API, and optional AMQP consumer
- Examples: `services/seat/app.py`, `services/payment/app.py`, `services/booking/app.py`
- Pattern: Database-per-service, idempotent table creation, health endpoint

**Event (AMQP Message):**
- Purpose: Signal state changes across service boundaries without coupling
- Examples: `booking.confirmed`, `seat.released.{event_id}`, `event.cancelled.{event_id}`
- Pattern: Topic/direct exchanges, routing keys for selective consumption

**Distributed Lock (Redis):**
- Purpose: Prevent race conditions on shared resources (seats) under high concurrency
- Examples: `seat:{event_id}:{seat_id}` key with `nx=True`, 10min TTL
- Pattern: Optimistic + pessimistic locking (Redis first, then MySQL FOR UPDATE)

**Compensating Transaction:**
- Purpose: Rollback partial saga state on failure (e.g., release seat if payment fails)
- Examples: `PUT /seats/{seat_id}/release` called from Booking Orchestrator on payment failure
- Pattern: Explicit compensation, not auto-rollback

**WebSocket Room (SocketIO):**
- Purpose: Deliver real-time updates to specific clients (e-ticket delivery)
- Examples: Ticket Service room keyed by `booking_id`
- Pattern: Client joins room via `join_booking` event, server emits to room

## Entry Points

**API Gateway (Kong):**
- Location: `http://localhost:8000` (proxy port), `8001` (admin API)
- Triggers: External client requests (browser, Postman, OutSystems)
- Responsibilities: Route to services, enforce rate limits, CORS handling

**Booking Orchestrator:**
- Location: `services/booking_orchestrator/app.py`, `POST /bookings`
- Triggers: UI submits booking form
- Responsibilities: Orchestrate entire saga, handle payment expiry, emit saga state events

**WebSocket Entry (Ticket Service):**
- Location: `services/ticket/app.py`, SocketIO server on port 5006
- Triggers: UI opens connection after booking returns 201
- Responsibilities: Receive QR generation request from AMQP, deliver via WebSocket

**AMQP Consumers (All services with async logic):**
- Location: Daemon threads in Flask apps (using `run_with_amqp()` helper)
- Triggers: Messages published to exchanges
- Responsibilities: React to events, update local state, emit downstream events

**Background Schedulers:**
- Location: `services/booking_orchestrator/app.py` (APScheduler), `services/waitlist/app.py` (APScheduler)
- Triggers: Timer-based (every 30 seconds)
- Responsibilities: Check expired sagas/promotions, compensate or cascade

## Error Handling

**Strategy:** Explicit compensation with message acknowledgment

**Patterns:**

- **Saga Step Failure**: If Seat/Payment/Booking call fails, Booking Orchestrator explicitly calls compensating transaction (release seat) before updating saga to FAILED
- **AMQP Consumer Failure**: If message processing fails, NACK with requeue (RabbitMQ redelivers). Max 3 retries → send to dead-letter queue
- **Timeout-based Compensation**: APScheduler detects expired sagas/promotions and triggers cleanup
- **Database Transaction**: All multi-step operations use explicit `connection.commit()` / `connection.rollback()` with cursor context manager
- **HTTP 409 Conflict**: Seat Service returns 409 if Redis lock fails or MySQL status is not available (expected, not error)
- **HTTP 402 Payment Required**: Payment Service returns 402 on Stripe failure
- **Graceful Degradation**: If Notification Service is slow/down, saga still completes (notifications are async, not blocking)

## Cross-Cutting Concerns

**Logging:**
- No explicit logging framework specified; services use `print()` (standard Flask development)
- Recommendation: Add `logging` module or structured JSON logging for production

**Validation:**
- Request validation: Flask route handlers validate JSON schema (e.g., `{"user_id": ..., "event_id": ...}`)
- Database validation: MySQL constraints (UNIQUE, ENUM, NOT NULL, indexes)
- No OpenAPI/Swagger spec — API contracts defined in prompts

**Authentication:**
- Not yet implemented (auth layer assumed to be in Kong API Gateway)
- Recommendation: Add JWT verification in Kong, pass `user_id` header to services

**Idempotency:**
- Saga uses `saga_id` (UUID) as idempotency key in payment requests
- Services should accept duplicate messages with same message ID and return cached result

**Multi-threading:**
- Flask services with AMQP consumers use `threading.Thread` (daemon=True) + `run_with_amqp()` helper from `shared/amqp_lib.py`
- Ticket Service uses `eventlet.monkey_patch()` instead of threading (SocketIO async mode)
- Ensures Flask HTTP server (main thread) doesn't block AMQP consumer (daemon thread)

---

*Architecture analysis: 2026-03-13*
