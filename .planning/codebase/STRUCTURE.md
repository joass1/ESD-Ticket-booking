# Codebase Structure

**Analysis Date:** 2026-03-13

## Directory Layout

```
event-ticketing-platform/
├── docker-compose.yml              # Infrastructure orchestration (MySQL, RabbitMQ, Redis, Kong, 9 services)
├── .env.example                    # Environment variables template
├── .gitignore                      # Standard Python + .env
├── kong/
│   └── kong.yml                    # Kong API Gateway declarative config (DB-less mode)
├── services/                       # Microservices implementation (9 total)
│   ├── event/                      # Event management service (atomic)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py                  # Flask: event CRUD, cancellation trigger
│   │   └── event.sql               # Schema: events, venues tables
│   ├── booking/                    # Booking records service (atomic)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py                  # Flask: booking CRUD, status tracking
│   │   └── booking.sql             # Schema: bookings table
│   ├── seat/                       # Seat inventory + locking (atomic)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py                  # Flask: seat CRUD, reserve/release/confirm, Redis locking
│   │   └── seat.sql                # Schema: venues, seats tables with status enum
│   ├── payment/                    # Stripe integration (atomic)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py                  # Flask: payment processing, refund handling via AMQP
│   │   └── payment.sql             # Schema: transactions table
│   ├── notification/               # Email/SMS service (atomic + AMQP consumer)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py                  # Flask-Mail (SMTP), Twilio SMS, multi-exchange consumer
│   │   └── notification.sql        # Schema: notification_logs table
│   ├── ticket/                     # QR code generation + WebSocket (atomic + SocketIO)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py                  # Flask-SocketIO: WebSocket server, QR generation, AMQP consumer
│   │   └── ticket.sql              # Schema: tickets table with qr_code_image BLOB
│   ├── waitlist/                   # Waitlist + promotion choreography (atomic + AMQP)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py                  # Flask: waitlist join/status, AMQP seat.released consumer
│   │   └── waitlist.sql            # Schema: waitlist_entries with position, promotion tracking
│   ├── charging/                   # Service fee calculation (atomic + AMQP consumer)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app.py                  # Flask: fee calculation, event cancellation listener
│   │   └── charging.sql            # Schema: service_fees table
│   └── booking_orchestrator/       # Saga orchestrator (composite, no domain DB)
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── app.py                  # Flask: main booking saga, payment expiry checker
│       └── saga_log.sql            # Schema: saga_log table only (no business data)
├── frontend/
│   ├── index.html                  # Event browsing + seat selection UI
│   ├── booking.html                # Booking form + payment flow page
│   └── js/
│       └── app.js                  # JavaScript: WebSocket client for ticket delivery
├── shared/
│   └── amqp_lib.py                 # Reusable AMQP helper (all services import)
└── .env                            # Git-ignored, contains Stripe/Twilio/Gmail secrets (local only)
```

## Directory Purposes

**docker-compose.yml:**
- Purpose: Define all infrastructure and application services with dependencies, volumes, health checks
- Contains: 4 infrastructure services (MySQL, RabbitMQ, Redis, Kong), 9 application services
- Key features: Named volume `mysql_data` for persistence, init.sql for database setup, healthchecks on all services
- Kong depends_on all microservices being healthy (ensures routing works)

**kong/:**
- Purpose: API Gateway configuration
- Contains: `kong.yml` declarative config defining routes (`/api/events/**` → event:5001, etc.), rate-limiting plugin
- Generated: No
- Committed: Yes (Kong in DB-less mode uses file, not database)

**services/:**
- Purpose: Microservices directory
- Contains: 8 atomic services + 1 composite (Booking Orchestrator), each with Dockerfile, requirements.txt, Flask app, SQL schema
- Naming: Lowercase service name matching port mapping and database name
- Key pattern: Each service independently creates its database schema on startup (CREATE TABLE IF NOT EXISTS)

**services/event/:**
- Purpose: Event management — list events, get details, trigger cancellation
- Key files: `services/event/app.py` (GET /events, PUT /events/{id}/cancel), `services/event/event.sql` (events, venues)
- Port: 5001
- Database: `event_db`

**services/booking/:**
- Purpose: Booking records — store confirmed bookings, track status
- Key files: `services/booking/app.py` (POST /bookings, GET /bookings?event_id), `services/booking/booking.sql`
- Port: 5002
- Database: `booking_db`
- Note: This is NOT the orchestrator (different from Booking Orchestrator)

**services/seat/:**
- Purpose: Seat inventory with Redis locking for high-concurrency protection
- Key files: `services/seat/app.py` (reserve/release/confirm endpoints, AMQP publisher for seat.released)
- Port: 5003
- Database: `seat_db`
- Redis usage: `seat:{event_id}:{seat_id}` locks with `nx=True` (exclusive), 10min TTL
- Critical: Implements 2-phase locking (Redis + MySQL FOR UPDATE + SKIP LOCKED for auto-assign)

**services/payment/:**
- Purpose: Stripe integration for charges and refunds
- Key files: `services/payment/app.py` (POST /payments for charges, AMQP consumer for refund.process)
- Port: 5004
- Database: `payment_db`
- External: Stripe API (via `stripe` library)
- AMQP: Consumes `refund_direct` exchange, publishes `refund.completed`

**services/notification/:**
- Purpose: Email/SMS notifications triggered by AMQP events
- Key files: `services/notification/app.py` (Flask-Mail for SMTP, Twilio for SMS, 4-exchange consumer)
- Port: 5005
- Database: `notification_db` (notification_logs for audit)
- External: Gmail SMTP, Twilio (SMS)
- AMQP: Consumes from 4 exchanges (booking_topic, waitlist_topic, event_lifecycle, refund_direct)
- Threading: AMQP consumer in daemon thread, Flask HTTP in main thread

**services/ticket/:**
- Purpose: QR code generation and real-time e-ticket delivery via WebSocket
- Key files: `services/ticket/app.py` (Flask-SocketIO, eventlet, QR code generation, AMQP consumer)
- Port: 5006
- Database: `ticket_db` (tickets with qr_code_image BLOB)
- Critical: Uses `eventlet.monkey_patch()` at top of file (required for SocketIO async mode, NOT threading)
- SocketIO: Room-based delivery keyed by `booking_id`
- AMQP: Consumes `booking.confirmed` from booking_topic, also listens to `event.cancelled.*` for invalidation

**services/waitlist/:**
- Purpose: Waitlist queue + automated promotion on seat release
- Key files: `services/waitlist/app.py` (join/status endpoints, AMQP seat.released consumer, APScheduler for promotion timeout)
- Port: 5007
- Database: `waitlist_db` (waitlist_entries with position, promotion expiry)
- Redis: `waitlist_promotion:{entry_id}` for 10min promotion TTL
- AMQP: Consumes `seat_topic` exchange, publishes `waitlist.promoted` and `waitlist.expired`
- Critical: Choreography-based — NO direct HTTP call to Seat Service
- Multi-threading: Flask main thread + AMQP daemon thread + APScheduler background jobs

**services/charging/:**
- Purpose: Calculate service fees during batch refund (Scenario 3)
- Key files: `services/charging/app.py` (POST /charging/calculate, AMQP event.cancelled consumer)
- Port: 5008
- Database: `charging_db` (service_fees table)
- AMQP: Consumes `event_lifecycle` exchange, publishes adjusted amounts to `refund_direct`
- Multi-threading: Flask main thread + AMQP daemon thread

**services/booking_orchestrator/:**
- Purpose: Saga orchestration — coordinate booking flow (Scenario 1)
- Key files: `services/booking_orchestrator/app.py` (POST /bookings main endpoint, APScheduler payment expiry checker)
- Port: 5010
- Database: `saga_log_db` (saga_log only — NO domain business data)
- Critical: This is the ONLY composite service — other services are atomic
- AMQP: Publishes `booking.confirmed` (async) and `booking.timeout` (expiry)
- Multi-threading: Flask main thread + APScheduler background scheduler (runs check_expired_sagas every 30s)
- Entry point for UI booking flow

**frontend/:**
- Purpose: Static UI for event browsing and booking
- Key files: `index.html` (event list + seat map), `booking.html` (checkout form), `js/app.js` (WebSocket client)
- WebSocket: Connects to `http://localhost:5006` after booking returns 201
- No backend code — pure HTML/CSS/JavaScript

**shared/:**
- Purpose: Shared library for AMQP operations
- Key files: `shared/amqp_lib.py` (connect_with_retry, setup_exchange, publish_message, start_consumer, run_with_amqp helper)
- Imported by: ALL services that use AMQP (Seat, Waitlist, Charging, Notification, Ticket, Payment, Booking Orchestrator)
- Critical: `run_with_amqp(flask_app, port, consumer_setup_fn)` starts AMQP consumer in daemon thread

## Key File Locations

**Entry Points:**

- `services/booking_orchestrator/app.py` : Main saga entry point — receives `POST /bookings` from UI
- `frontend/js/app.js` : UI-side WebSocket entry point — connects to Ticket Service after booking completes
- `docker-compose.yml` : Infrastructure entry point — starts all services in correct dependency order

**Configuration:**

- `.env.example` : Template for environment variables (STRIPE_SECRET_KEY, TWILIO_ACCOUNT_SID, SMTP credentials)
- `.env` : Actual credentials (git-ignored, local development only)
- `kong/kong.yml` : API Gateway routing and rate-limiting configuration
- Each `services/*/requirements.txt` : Python dependencies per service

**Core Logic:**

- `services/booking_orchestrator/app.py` : Saga state machine, compensation logic, APScheduler payment expiry
- `services/seat/app.py` : Redis locking mechanism, MySQL pessimistic locking, SKIP LOCKED for fallback
- `services/ticket/app.py` : QR code generation, SocketIO room management, WebSocket delivery
- `services/waitlist/app.py` : Promotion logic, cascading promotion on timeout, choreography patterns
- `services/payment/app.py` : Stripe integration (PaymentIntent creation, refund processing)
- `services/notification/app.py` : Multi-channel notification (email via SMTP, SMS via Twilio)

**Testing:**

- No test files found in repository (not yet implemented)
- Recommendation: Add `tests/` directory with pytest fixtures for saga steps, AMQP message validation, seat locking race conditions

**Database Schemas:**

- `services/*/\*.sql` : CREATE TABLE statements, indexes, constraints
- All created on startup via `docker-entrypoint-initdb.d/init.sql` (single init script that sources all .sql files)
- Key constraint: Seat status enum (available, reserved, booked, released), Saga status enum (STARTED, SEAT_RESERVED, PAYMENT_SUCCESS, CONFIRMED, TIMEOUT)

## Naming Conventions

**Files:**

- Service directories: lowercase, singular noun (`seat`, `payment`, `event`)
- Flask entry point: `app.py` (all services)
- Database schema: `{service_name}.sql` (matches database name)
- Configuration: `.env`, `.gitignore`, `docker-compose.yml`
- Documentation: `CLAUDE.md` (in repo root, project intelligence)

**Directories:**

- `services/{domain}/` : One directory per atomic/composite service
- `shared/` : Cross-cutting libraries
- `frontend/` : UI static files
- `kong/` : API Gateway config

**Database Names:**

- Pattern: `{service_name}_db` (e.g., `event_db`, `seat_db`, `booking_db`)
- Exception: `saga_log_db` (Booking Orchestrator)
- All lowercase with underscore separator

**Functions/Endpoints:**

- HTTP methods: `GET` (retrieve), `POST` (create), `PUT` (update), `DELETE` (remove)
- Paths: `/api/{resource}`, `/api/{resource}/{id}`, `/api/{resource}/{id}/{action}`
- Examples: `GET /api/seats/availability`, `PUT /seats/{seat_id}/reserve`, `POST /bookings`

**AMQP Exchanges & Routing Keys:**

- Exchanges: `{domain}_topic` or `{domain}_direct`
- Topic exchange naming: `booking_topic`, `seat_topic`, `event_lifecycle`, `waitlist_topic`, `refund_direct`, `ticket_direct`
- Routing keys: `{event_type}.{action}.{optional_id}` (e.g., `booking.confirmed`, `seat.released.{event_id}`, `event.cancelled.{event_id}`)

**Environment Variables:**

- Standard: `MYSQL_HOST`, `RABBITMQ_HOST`, `REDIS_HOST`
- Secret: `STRIPE_SECRET_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE`
- Email: `SMTP_USER`, `SMTP_PASS` (Gmail)

**Redis Keys:**

- Seat locks: `seat:{event_id}:{seat_id}` (string, TTL 600s)
- Waitlist promotion: `waitlist_promotion:{entry_id}` (string, TTL 600s)

## Where to Add New Code

**New Feature:**

- **Primary code**: Create feature in relevant atomic service (e.g., seat refund logic → `services/seat/app.py`)
- **Tests**: Add test file `tests/test_{feature}.py` (pattern not yet established, use pytest)
- **Database**: Extend `services/{service}/{service}.sql` schema if new tables needed
- **AMQP**: If event-driven, define new routing key in `shared/amqp_lib.py` or service's AMQP consumer

**New Component/Module:**

- **Implementation**: Create in service's `services/{service}/` directory (alongside `app.py`)
- **Example**: Payment Service needs card validation → create `services/payment/card_validator.py`, import in `app.py`
- **Reusable across services**: Add to `shared/` instead

**Utilities:**

- **Shared helpers**: `shared/amqp_lib.py` (AMQP operations — all services use this)
- **Database utils**: Create `shared/db_utils.py` if connection pooling, transaction helpers needed
- **Validators**: Create `shared/validators.py` for input schema validation across services

**New Service (Add 10th service):**

1. Create `services/{new_service}/` directory
2. Add `Dockerfile`, `requirements.txt`, `app.py`, `{new_service}.sql`
3. Update `docker-compose.yml` with service definition (port, depends_on, env vars)
4. If AMQP: import `shared/amqp_lib.py`, use `run_with_amqp()` in main block
5. Update `kong/kong.yml` with route definition
6. Update `.env.example` with new env vars if needed

## Special Directories

**`.git/`:**
- Purpose: Git version control
- Generated: Yes (git init on clone)
- Committed: No (metadata only)

**`.planning/`:**
- Purpose: GSD codebase mapping and phase planning
- Generated: Yes (by GSD orchestrator)
- Committed: Yes (design artifacts)
- Subdirectories: `.planning/codebase/` (ARCHITECTURE.md, STRUCTURE.md, etc.), `.planning/phases/` (execution plans)

**`docker-compose` generated volumes:**
- `mysql_data`: Named volume for MySQL persistence across container restarts
- `rabbitmq_data`: Named volume for RabbitMQ persistence (messages survive restart)
- Generated: Yes (created by Docker Compose)
- Committed: No (data store)

**Dockerfile context:**
- Each service has its own Dockerfile (multi-stage not necessary for simple Python apps)
- Base image: `python:3.11-slim`
- Build context: Service directory (COPY only that service's files)

---

*Structure analysis: 2026-03-13*
