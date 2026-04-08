# Event Ticketing Platform

IS213 Enterprise Solution Development -- G3T1

A microservices-based event ticketing system that allows users to browse events, book seats with real-time concurrency protection, make payments via Stripe, receive QR-code e-tickets over WebSocket, join waitlists, and request refunds. Event management is handled through an OutSystems admin dashboard.

---

## Prerequisites

Install the following before running the project:

| Software | Version | Download |
|----------|---------|----------|
| Docker Desktop | 4.x+ | https://www.docker.com/products/docker-desktop |
| Node.js | 18+ | https://nodejs.org |
| npm | Comes with Node.js | -- |
| Git | Any | https://git-scm.com |

Docker Desktop must be **running** before you proceed.

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/joass1/ESD-Ticket-booking.git
cd ESD-Ticket-booking
```

### 2. Configure environment variables

A `.env` file is required in the project root with the following variables:

```env
MYSQL_ROOT_PASSWORD=root
RABBITMQ_USER=guest
RABBITMQ_PASS=guest
STRIPE_SECRET_KEY=<your-stripe-test-secret-key>
SMU_NOTI_BASE_URL=https://smuedu-dev.outsystemsenterprise.com/SMULab_Notification/rest/Notification
SMU_NOTI_API_KEY=<your-smu-notification-api-key>
```

**Where to get the keys:**
- **Stripe**: Sign up at https://dashboard.stripe.com, go to Developers > API Keys, copy the **Secret key** (starts with `sk_test_`)
- **SMU Notification API**: Provided by the IS213 teaching team

### 3. Build and start all services

```bash
docker compose up --build
```

This starts all infrastructure and backend services:
- MySQL 8.0 (port 3306)
- RabbitMQ 3 (port 5672, management UI at port 15672)
- Redis 7 (port 6379)
- Kong API Gateway (port 8000)
- 8 backend microservices (ports 5002-5010)

The database is automatically initialized with seed data on first boot via `db/init.sql`.

Wait until all containers are healthy (check with `docker compose ps`).

### 4. Start the frontend

In a **separate terminal**:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at **http://localhost:5173**.

---

## Accessing the Application

| Component | URL |
|-----------|-----|
| Frontend (React) | http://localhost:5173 |
| Kong API Gateway | http://localhost:8000 |
| RabbitMQ Management UI | http://localhost:15672 (guest/guest) |
| OutSystems Event Service | https://personal-fptjqc79.outsystemscloud.com/ESDTicketBookingServices/rest/EventService |

### Demo Users

The frontend provides a user selector in the header:

| User | Role | Can Do |
|------|------|--------|
| `user_001` | Regular user | Browse events, book seats, join waitlist, request refunds |
| `user_002` | Regular user | Same as above |
| `user_003` | Regular user | Same as above |
| `admin` | Administrator | Browse events, create events, cancel events, scan QR tickets (cannot purchase tickets) |

### Test Payment

Use Stripe test card: **4242 4242 4242 4242**
- Expiry: any future date
- CVC: any 3 digits
- ZIP: any 5 digits

---

## Architecture Overview

The platform uses 8 atomic microservices and 1 composite orchestrator:

| Service | Type | Port | Description |
|---------|------|------|-------------|
| Event Service | Atomic | External (OutSystems) | Event CRUD via OutSystems REST API |
| Booking Service | Atomic | 5002 | Booking record management |
| Seat Service | Atomic | 5003 | Seat inventory with Redis distributed locking |
| Payment Service | Atomic | 5004 | Stripe payment processing |
| Notification Service | Atomic | 5005 | Email/SMS via SMU Lab Notification API |
| Ticket Service | Atomic | 5006 | QR code e-ticket generation + WebSocket delivery |
| Waitlist Service | Atomic | 5007 | FIFO waitlist with choreography-based promotion |
| Charging Service | Atomic | 5008 | Service fee calculation for refunds |
| Booking Orchestrator | Composite | 5010 | Saga orchestration + OutSystems bridge |

**Key architecture rule:** Atomic services never call each other via HTTP. They communicate exclusively through RabbitMQ (AMQP). Only the Booking Orchestrator (composite) makes HTTP calls to atomic services.

### External Services

| Service | Purpose |
|---------|---------|
| Stripe API | Payment processing (create intents, verify, refund) |
| SMU Lab Notification API | Email, SMS, and OTP verification |
| OutSystems Cloud | Event Service hosting (REST API) |
| Redis | Distributed in-memory lock store for concurrent seat reservation |
| html5-qrcode (ZXing) | Client-side QR code scanning via WebRTC camera API |

### Beyond-the-Lectures (BTL) Features

- **Kong API Gateway** -- Centralized routing, rate limiting (10 req/s), CORS management
- **Redis Distributed Locking** -- Dual-lock pattern (SET NX EX + SELECT FOR UPDATE) for concurrent seat reservation
- **Flask-SocketIO WebSocket** -- Real-time e-ticket delivery to the browser
- **Multi-threading** -- Each service runs Flask HTTP and pika AMQP consumers concurrently using Python daemon threads
- **QR Code Ticket Validation** -- Client-side QR scanning via html5-qrcode (ZXing + WebRTC) with server-side SHA-256 hash verification; scanned tickets blocked from refunds

---

## API Documentation

### REST API (OpenAPI / Swagger)

The API specification is located at `docs/openapi.yaml` (OpenAPI 3.0) and `docs/apispec.json` (JSON export).

Interactive API documentation is available via Swagger UI:

```bash
npx swagger-ui-watcher docs/openapi.yaml -p 8081
```

Open **http://localhost:8081** to browse all endpoints with request/response schemas.

You can also import `docs/apispec.json` directly into https://editor.swagger.io.

To use the "Try it out" feature, make sure Docker services are running. Kong CORS is pre-configured to allow requests from `localhost:8081`.

### AMQP Messaging (AsyncAPI)

Message broker documentation for all RabbitMQ exchanges, queues, and message payloads:

```bash
npx @asyncapi/cli start studio docs/asyncapi.yaml
```

The URL will be shown in the terminal output (port is assigned dynamically).

### OutSystems Event Service API

The OutSystems-hosted Event Service has its own Swagger docs at:

https://personal-fptjqc79.outsystemscloud.com/ESDTicketBookingServices/rest/EventService

---

## User Scenarios

### Scenario 1: Seat Booking (Orchestration Saga)

User selects a seat and completes payment through a multi-step saga:

1. Frontend sends booking request through Kong to Booking Orchestrator
2. Orchestrator validates the event with OutSystems, reserves the seat (Redis + MySQL dual lock), creates a booking, and creates a Stripe PaymentIntent
3. User completes payment within 10 minutes via Stripe
4. Orchestrator verifies payment, confirms the seat, updates the booking, and publishes `booking.confirmed`
5. Ticket Service generates a QR code and pushes it to the frontend via WebSocket
6. Notification Service sends confirmation email + SMS
7. At the venue, admin scans the QR code via the Scanner page — Ticket Service validates the SHA-256 hash and marks the ticket as used (post-scan refund guard prevents refunds after entry)

If payment times out, APScheduler releases the seat, expires the booking, and notifies the user.

### Scenario 2: Waitlist Promotion (Choreography)

When a seat is released, the Waitlist Service promotes the next user via AMQP:

1. Seat Service publishes `seat.released` to RabbitMQ
2. Waitlist Service promotes the first waiting user in the matching section queue and requests a seat reservation via AMQP
3. Seat Service reserves the seat and confirms via AMQP
4. Notification Service sends SMS: "A Seat is Available, Book within 10 minutes!"
5. If the user doesn't book in time, APScheduler expires the promotion, sends expiry SMS, and cascades to the next user in the section queue

### Scenario 3: Event Cancellation (Fan-Out)

Admin cancels an event through the Orchestrator bridge:

1. Frontend calls Booking Orchestrator (since OutSystems cannot publish to RabbitMQ)
2. Orchestrator cancels the event in OutSystems and publishes `event.cancelled` to RabbitMQ
3. Five services react in parallel: Seat (releases all seats), Booking (marks as pending_refund), Ticket (invalidates all tickets), Waitlist (cancels entries), Notification (logs cancellation)
4. Refund chain: Charging calculates fees (0% for event cancellation) -> Payment processes Stripe refund with up to 3 retries -> Booking marks as refunded -> Notification sends refund email + SMS

---

## Project Structure

```
ESD-Ticket-booking/
├── frontend/                  # React 19 + Vite + TailwindCSS
│   └── src/
│       ├── api/client.js      # API client with OutSystems PascalCase normalization
│       ├── components/        # UI components (SeatMap, BookingWizard, etc.)
│       ├── hooks/useSocket.js # WebSocket hook for ticket delivery
│       └── pages/             # Route pages (Events, EventDetail, Booking, Waitlist, BookingHistory, Scanner)
├── scripts/
│   └── fill_seats.py          # Test utility: fill seats for waitlist testing
├── services/
│   ├── booking/               # Booking Service (Flask, port 5002)
│   ├── booking_orchestrator/  # Composite Orchestrator (Flask, port 5010)
│   ├── seat/                  # Seat Service with Redis locking (Flask, port 5003)
│   ├── payment/               # Stripe integration (Flask, port 5004)
│   ├── notification/          # SMU Lab Notification API (Flask, port 5005)
│   ├── ticket/                # QR + WebSocket (Flask-SocketIO, port 5006)
│   ├── waitlist/              # FIFO waitlist (Flask, port 5007)
│   ├── charging/              # Fee calculation (Flask, port 5008)
│   └── event/                 # Legacy Python event service (replaced by OutSystems)
├── shared/                    # Shared libraries (response.py, amqp_lib.py)
├── kong/kong.yml              # Kong API Gateway declarative config
├── db/init.sql                # Database initialization + seed data
├── docker-compose.yml         # All services orchestration
├── docs/
│   ├── openapi.yaml           # REST API documentation (OpenAPI 3.0)
│   ├── asyncapi.yaml          # AMQP messaging documentation (AsyncAPI 2.6)
│   ├── apispec.json           # Exported OpenAPI spec (JSON)
│   └── demo-script.md         # 3-minute demo recording script
├── overview.md                # Full technical overview
├── OUTSYSTEMS_MIGRATION_GUIDE.md  # OutSystems migration details
└── .env                       # Environment variables (not committed)
```

---

## Troubleshooting

### Services fail to start

```bash
# Check which containers are unhealthy
docker compose ps

# View logs for a specific service
docker logs <container-name>

# Restart a single service
docker compose restart <service-name>
```

### Database not initialized

`init.sql` only runs on first boot. To reset:

```bash
docker compose down -v
docker compose up --build
```

The `-v` flag removes the MySQL volume so seed data loads fresh.

### "No sections found" on event detail page

The event exists in OutSystems but has no seats in the local Seat Service database. Either:
- Create the event via the admin "Create Event" page (which sets up seats automatically)
- Or reset the database with `docker compose down -v && docker compose up --build`

### CORS errors in browser

Check that your origin is in `kong/kong.yml` under `plugins > cors > origins`. After editing, restart Kong:

```bash
docker compose restart kong
```

### Stripe payment fails

- Ensure `STRIPE_SECRET_KEY` in `.env` starts with `sk_test_`
- Use test card `4242 4242 4242 4242`
- Disable ad blockers (they block Stripe's `r.stripe.com` telemetry)

### WebSocket not connecting

The Ticket Service WebSocket runs on port 5006 directly (not through Kong). Ensure port 5006 is accessible and the ticket container is healthy.

---

## Stopping the Application

```bash
# Stop all containers
docker compose down

# Stop and remove all data (databases, queues)
docker compose down -v
```
