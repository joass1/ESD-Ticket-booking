# Technology Stack

**Analysis Date:** 2026-03-13

## Languages

**Primary:**
- Python 3.11 - All microservices, backend APIs, business logic

**Frontend:**
- React - UI for event browsing, seat selection, booking flow

## Runtime

**Environment:**
- Python 3.11-slim (Docker base image)

**Package Manager:**
- pip (Python)
- Lockfile: `requirements.txt` per service (not a centralized lockfile)

## Frameworks

**Core Web:**
- Flask - HTTP REST API server for all 9 microservices
- Flask-CORS - CORS header support across all services

**Real-time Communication:**
- Flask-SocketIO - WebSocket server in Ticket Service for e-ticket delivery (port 5006)
- eventlet - WSGI event library required for SocketIO async support

**Messaging:**
- pika - RabbitMQ AMQP client library for all services using async messaging

**Task Scheduling:**
- APScheduler (BackgroundScheduler) - Payment expiry checks in Booking Orchestrator (every 30s) and waitlist promotion timeout checks

**Payment Processing:**
- Stripe Python SDK - Payment intent creation and refund processing in Payment Service

**Notifications:**
- Flask-Mail - Email sending via Gmail SMTP (Notification Service)
- Twilio Python SDK - SMS sending for time-sensitive waitlist promotions (Notification Service)

**QR Code Generation:**
- qrcode - QR code library for e-ticket generation (Ticket Service)
- Pillow (PIL) - Image processing for QR code PNG output

**Database:**
- mysql-connector-python - MySQL client for all services

**Testing/Development:**
- None specified in requirements (assumes manual testing or external test setup)

## Key Dependencies

**Critical Infrastructure:**
- pika - AMQP client for RabbitMQ connectivity; every service that performs async messaging depends on this
- mysql-connector-python - Database connectivity; every atomic service requires this
- requests - HTTP client for inter-service communication (Booking Orchestrator calling Seat/Payment services)
- redis - Used in Seat Service for distributed lock implementation (seat reservation TTL-based locking)

**Security & Configuration:**
- os.environ - All secrets read from environment variables: `STRIPE_SECRET_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE`, `SMTP_USER`, `SMTP_PASS`, `MYSQL_ROOT_PASSWORD`

**Database Drivers:**
- mysql-connector-python - Explicit MySQL driver (not SQLAlchemy ORM); direct SQL execution with connection pooling

## Configuration

**Environment Variables Required:**
```
MYSQL_ROOT_PASSWORD        # MySQL root password
MYSQL_HOST                 # MySQL container hostname (default: mysql)
RABBITMQ_HOST              # RabbitMQ container hostname (default: rabbitmq)
REDIS_HOST                 # Redis container hostname (default: redis)
STRIPE_SECRET_KEY          # Stripe test key (sk_test_*)
TWILIO_ACCOUNT_SID         # Twilio account SID
TWILIO_AUTH_TOKEN          # Twilio auth token
TWILIO_PHONE               # Twilio phone number for SMS
SMTP_USER                  # Gmail address for outgoing email
SMTP_PASS                  # Gmail app password (not regular password)
```

**Build:**
- Dockerfile per service (9 total): All use `python:3.11-slim` base, COPY requirements.txt, RUN pip install, COPY app code
- docker-compose.yml - Orchestrates 14 containers: MySQL, RabbitMQ, Redis, Kong API Gateway, 9 microservices
- .env.example - Template file with all required environment variable names

**Kong Configuration:**
- `kong/kong.yml` - Kong DB-less declarative configuration (YAML format)
- Routing: `/api/events/**` → Event Service, `/api/bookings/**` → Booking Orchestrator, `/api/seats/**` → Seat Service, `/api/payments/**` → Payment Service, `/api/tickets/**` → Ticket Service, `/api/waitlist/**` → Waitlist Service
- Rate limiting: 10 requests/second globally

## Platform Requirements

**Development:**
- Docker & Docker Compose
- MySQL 8.0 (containerized)
- RabbitMQ 3-management (containerized)
- Redis 7-alpine (containerized)
- Kong 3.6 API Gateway (containerized)
- Python 3.11

**Production:**
- Docker Container Orchestration (Kubernetes or Docker Swarm recommended)
- Managed MySQL 8.0 database (or self-hosted)
- Managed RabbitMQ cluster (or self-hosted)
- Managed Redis instance (or self-hosted)
- Kong 3.6 or similar API Gateway layer
- OutSystems instance (for admin dashboard, exposes Event Service endpoint)

## Service Port Mapping

| Service | Port | Framework |
|---------|------|-----------|
| Event Service | 5001 | Flask + AMQP |
| Booking Service | 5002 | Flask + AMQP |
| Seat Service | 5003 | Flask + AMQP + Redis |
| Payment Service | 5004 | Flask + AMQP + Stripe |
| Notification Service | 5005 | Flask + AMQP + Twilio + SMTP |
| Ticket Service | 5006 | Flask-SocketIO + AMQP + QRCode |
| Waitlist Service | 5007 | Flask + AMQP |
| Charging Service | 5008 | Flask + AMQP |
| Booking Orchestrator | 5010 | Flask + AMQP + APScheduler |
| Kong API Gateway | 8000 (proxy), 8001 (admin) | Kong |
| MySQL | 3306 | - |
| RabbitMQ | 5672 (AMQP), 15672 (admin) | - |
| Redis | 6379 | - |

## Database Architecture

**Database per Service Pattern:**
- `event_db` - Event Service (events, venues tables)
- `booking_db` - Booking Service (bookings table)
- `seat_db` - Seat Service (seats, venues tables)
- `payment_db` - Payment Service (transactions table)
- `notification_db` - Notification Service (notification_logs table)
- `ticket_db` - Ticket Service (tickets table)
- `waitlist_db` - Waitlist Service (waitlist_entries table)
- `charging_db` - Charging Service (service_fees table)
- `saga_log_db` - Booking Orchestrator (saga_log table for orchestration state)

**Connection Details:**
- Host: `mysql` (container name)
- Port: 3306
- All databases initialized via single `init.sql` script (mounted to MySQL init directory)
- Schema creation: `CREATE TABLE IF NOT EXISTS` pattern (idempotent)

## Message Broker Architecture

**RabbitMQ 3 with AMQP (pika):**
- Exchange: `booking_topic` (topic) - booking.confirmed, booking.cancelled, booking.timeout
- Exchange: `seat_topic` (topic) - seat.released.{event_id}, seat.reserved
- Exchange: `event_lifecycle` (topic) - event.cancelled.{event_id}
- Exchange: `ticket_direct` (direct) - ticket.generated
- Exchange: `refund_direct` (direct) - refund.process, refund.completed
- Exchange: `waitlist_topic` (topic) - waitlist.promoted, waitlist.joined, waitlist.expired

**Connection Details:**
- Host: `rabbitmq` (container name)
- AMQP Port: 5672
- Management UI: 15672
- All connections use pika with retry logic (12 retries, 5s delay per attempt)

## Redis Configuration

**Purpose:** Distributed seat locking and caching

**Connection Details:**
- Host: `redis` (container name)
- Port: 6379

**Usage Pattern:**
- Lock key: `seat:{event_id}:{seat_id}` with TTL of 600 seconds (10 minutes)
- Promotion cache: `waitlist_promotion:{entry_id}` with TTL of 600 seconds
- Lock type: SET NX (only set if key doesn't exist)

## API Gateway

**Kong 3.6 Gateway:**
- Mode: DB-less (declarative YAML configuration)
- Port: 8000 (proxy), 8001 (admin)
- Dependency: Declared config at `/kong/declarative/kong.yml`
- Rate limiting: Global 10 requests/second

---

*Stack analysis: 2026-03-13*
