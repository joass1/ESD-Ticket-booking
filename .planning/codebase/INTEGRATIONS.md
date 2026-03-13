# External Integrations

**Analysis Date:** 2026-03-13

## APIs & External Services

**Payment Processing:**
- Stripe - Online payment platform for ticket purchases and refunds
  - SDK/Client: `stripe` Python package
  - Auth: Environment variable `STRIPE_SECRET_KEY` (test key: `sk_test_...`)
  - Integration point: `services/payment/app.py` - Payment Service
  - Operations: PaymentIntent creation (charge), Refund creation
  - Test mode: Uses test card `pm_card_visa` for success, `pm_card_chargeCustomerFail` for decline

**SMS Notifications:**
- Twilio - Time-sensitive SMS delivery for waitlist promotions
  - SDK/Client: `twilio` Python package
  - Auth: Environment variables `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE`
  - Integration point: `services/notification/app.py` - Notification Service
  - Operations: SMS message sending (high-priority waitlist promotions only)
  - Rate limit: ~50 SMS/day on free trial (unverified numbers)

## Data Storage

**Databases:**
- MySQL 8.0 (containerized, port 3306)
  - Connection: Environment variable `MYSQL_HOST` (container name `mysql`)
  - Client: `mysql-connector-python` (direct SQL execution, no ORM)
  - Databases: 9 databases (one per service + one for saga logs)

  | Service | Database | Tables |
  |---------|----------|--------|
  | Event Service | `event_db` | events, venues |
  | Booking Service | `booking_db` | bookings |
  | Seat Service | `seat_db` | seats, venues |
  | Payment Service | `payment_db` | transactions |
  | Notification Service | `notification_db` | notification_logs |
  | Ticket Service | `ticket_db` | tickets |
  | Waitlist Service | `waitlist_db` | waitlist_entries |
  | Charging Service | `charging_db` | service_fees |
  | Booking Orchestrator | `saga_log_db` | saga_log |

**Message Broker:**
- RabbitMQ 3 (containerized, AMQP port 5672, admin UI 15672)
  - Connection: Environment variable `RABBITMQ_HOST` (container name `rabbitmq`)
  - Client: `pika` (AMQP library)
  - Connection retry: 12 attempts with 5-second delay between retries
  - All messages: Persistent delivery mode (delivery_mode=2)

  Exchanges and routing:
  ```
  booking_topic (topic exchange)
    - booking.confirmed → Ticket Service, Notification Service
    - booking.cancelled → Booking Service, Notification Service
    - booking.timeout → Notification Service, Booking Orchestrator

  seat_topic (topic exchange)
    - seat.released.{event_id} → Waitlist Service (triggers promotion logic)
    - seat.reserved → (optional future use)

  event_lifecycle (topic exchange)
    - event.cancelled.{event_id} → Charging Service, Booking Service, Seat Service, Waitlist Service, Notification Service (fan-out)

  waitlist_topic (topic exchange)
    - waitlist.promoted → Notification Service (SMS + email)
    - waitlist.joined → Notification Service (email)
    - waitlist.expired → Notification Service (email)

  refund_direct (direct exchange)
    - refund.process → Payment Service
    - refund.completed → Booking Service, Notification Service

  ticket_direct (direct exchange)
    - ticket.generated → (optional tracking)
  ```

**Caching & Distributed Locking:**
- Redis 7-alpine (containerized, port 6379)
  - Connection: Environment variable `REDIS_HOST` (container name `redis`)
  - Usage: Distributed seat reservation locking with TTL
  - Lock pattern: `seat:{event_id}:{seat_id}` (600s TTL)
  - Promotion cache: `waitlist_promotion:{entry_id}` (600s TTL)

**File Storage:**
- Local container filesystem only - No external storage service
- QR codes stored as: Base64-encoded BLOB in `tickets.qr_code_image` column (MySQL)

## Authentication & Identity

**Auth Provider:**
- Custom - No centralized auth service; user_id passed as request parameter
- Implementation: Simple user_id string (e.g., "user123") in request bodies/params
- Security: Expected to be secured by Kong API Gateway rate limiting; no JWT/OAuth in scope

**OutSystems Integration:**
- OutSystems Low-Code Platform - Admin dashboard for event organizers
- Exposed endpoint: Event Service REST API (`services/event/app.py`)
  - `GET /events` - List events
  - `POST /events` - Create event
  - `PUT /events/<event_id>` - Update event
  - `PUT /events/<event_id>/cancel` - Cancel event (triggers Scenario 3 refund flow)
- Authentication: OutSystems handles authentication; services assume trusted internal calls

## Monitoring & Observability

**Error Tracking:**
- None detected - No Sentry, DataDog, or similar integration

**Logs:**
- Local console logging via `print()` or Flask logger
- Notification logs stored in `notification_db.notification_logs` table (with status: sent/failed/queued)
- Transaction/payment logs in `payment_db.transactions` table
- Saga logs in `saga_log_db.saga_log` table (orchestration state machine)

## CI/CD & Deployment

**Hosting:**
- Docker containers (containerized locally)
- Target production: Kubernetes cluster or Docker Swarm (not specified in spec)

**CI Pipeline:**
- None detected - No GitHub Actions, GitLab CI, or Jenkins configuration specified

**Container Orchestration:**
- Docker Compose (local development and testing)
- docker-compose.yml defines all 14 services (MySQL, RabbitMQ, Redis, Kong, 9 microservices)
- Port mapping: Micro services 5001-5008, 5010; Kong 8000-8001; infrastructure 3306, 5672, 15672, 6379

## Environment Configuration

**Required Env Vars (Production):**
```
MYSQL_ROOT_PASSWORD=<password>
MYSQL_HOST=<mysql-container-or-hostname>
RABBITMQ_HOST=<rabbitmq-container-or-hostname>
REDIS_HOST=<redis-container-or-hostname>
STRIPE_SECRET_KEY=sk_test_<key>
TWILIO_ACCOUNT_SID=<sid>
TWILIO_AUTH_TOKEN=<token>
TWILIO_PHONE=+<country_code><number>
SMTP_USER=<gmail_address>
SMTP_PASS=<gmail_app_password>
```

**Secrets Location:**
- `.env` file (committed via .env.example template, actual .env excluded from git)
- Docker Compose reads .env file and injects into containers
- No secrets manager integration (Vault, AWS Secrets Manager, etc.)

**Default Values (for local development):**
- MYSQL_HOST: mysql
- RABBITMQ_HOST: rabbitmq
- REDIS_HOST: redis
- (Others require explicit configuration)

## Webhooks & Callbacks

**Incoming:**
- None detected - No external services calling back into platform

**Outgoing:**
- Stripe Webhook: NOT IMPLEMENTED - Platform uses synchronous Stripe API calls only
- SMS callbacks: NOT IMPLEMENTED - Twilio webhooks for delivery receipts not configured
- Email read receipts: NOT IMPLEMENTED - Flask-Mail (Gmail SMTP) not configured for receipts

**Real-time Callbacks:**
- WebSocket SocketIO: Ticket Service emits `ticket_ready` to UI via SocketIO room after consuming `booking.confirmed` from RabbitMQ
  - Connection: UI connects to `http://localhost:5006` (Ticket Service)
  - Room: Named by `booking_id`
  - Event: `ticket_ready` with QR code data

## Inter-Service Communication

**Synchronous (HTTP REST):**
- Booking Orchestrator → Seat Service: Reserve/release/confirm seats
  - Endpoints: `PUT /seats/<seat_id>/reserve`, `PUT /seats/<seat_id>/release`, `PUT /seats/<seat_id>/confirm`
- Booking Orchestrator → Payment Service: Process payment
  - Endpoint: `POST /payments`
- Booking Orchestrator → Booking Service: Create booking record
  - Endpoint: `POST /bookings`
- Event Service → Booking Service: Query confirmed bookings for cancellation
  - Endpoint: `GET /bookings?event_id=<id>&status=confirmed`
- Seat Service → Payment Service: NOT USED - All payments go through Booking Orchestrator only

**Asynchronous (AMQP RabbitMQ):**
- 6 distinct message flows (see Exchanges section above)
- All messages use JSON serialization
- Durable queue declarations (survives RabbitMQ restarts)
- QoS: prefetch_count=1 (process one message at a time per consumer)

---

*Integration audit: 2026-03-13*
