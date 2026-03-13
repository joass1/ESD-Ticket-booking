# Technology Stack

**Project:** ESD Event Ticketing Platform
**Researched:** 2026-03-13
**Overall Confidence:** HIGH (core stack is mandated; research focuses on library versions and compatibility)

## Constraints

The course mandates: Python 3.11, Flask, MySQL 8.0, RabbitMQ 3, Redis 7, Kong 3.6, Docker.
Team chose React for frontend. External APIs: Stripe, Twilio, Gmail SMTP.
This document specifies exact library versions, configuration, and compatibility notes.

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| Python | 3.11.x | Runtime | Mandated by course. Stable, well-supported. HIGH |
| Flask | 3.1.x (latest 3.1.2) | Web framework | Latest stable. Full Python 3.11 support. Requires Python >=3.9. HIGH |
| Werkzeug | (auto, ~3.1.x) | WSGI utilities | Bundled with Flask. Do not pin separately unless debugging. HIGH |

### Database

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| MySQL | 8.0 (Docker image) | Relational DB | Mandated. One DB per microservice. HIGH |
| SQLAlchemy | 2.0.x (latest 2.0.48) | ORM | Industry standard. 2.0 style is the current API. Do NOT use 1.4.x legacy mode. HIGH |
| Flask-SQLAlchemy | 3.1.x (latest 3.1.1) | Flask-SQLAlchemy integration | Simplifies Flask + SQLAlchemy setup. Supports Flask 3 and SQLAlchemy 2.0. HIGH |
| PyMySQL | 1.1.x (latest 1.1.2) | MySQL driver (pure Python) | Pure Python = no C compilation in Docker. Supports MySQL 8.0 auth (caching_sha2_password). Use `PyMySQL[rsa]` extra for MySQL 8 default auth. HIGH |

**Connection string format:**
```
mysql+pymysql://user:password@host:3306/dbname?charset=utf8mb4
```

**Critical:** Always specify `charset=utf8mb4`. MySQL 8.0 defaults to utf8mb4; PyMySQL matches this since v1.0.

### Message Broker

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| RabbitMQ | 3.x (Docker image) | AMQP message broker | Mandated. Supports topic exchanges for fan-out (Scenario 3). HIGH |
| pika | **1.3.2** | Python AMQP client | CRITICAL: Use 1.3.2, NOT 1.4.0. Version 1.4.0 requires Python 3.12+ and RabbitMQ 4.0+, which are incompatible with the mandated Python 3.11 / RabbitMQ 3.x. Pika 1.3.2 supports Python 3.7+ and all RabbitMQ versions. HIGH |

**Pika threading pattern (professor requirement):**
Each service needing both HTTP and AMQP must run Flask on the main thread and pika consumer on a daemon thread. Use `pika.BlockingConnection` in the consumer thread. Do NOT use `pika.SelectConnection` (async) -- it adds complexity with no benefit for this use case.

### Cache / Distributed Locking

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| Redis | 7.x (Docker image) | Cache + distributed locks | Mandated. Used for seat locking in Seat Service. HIGH |
| redis-py | 5.2.x | Python Redis client | Use 5.x series (supports Python 3.8+ and Redis 5.0-7.4). Do NOT use redis-py 6.x+ or 7.x which may require Redis 7.2+ minimum. The 5.x line is the safe choice for Redis 7.0. HIGH |

**Distributed lock pattern:**
```python
# Use redis-py's built-in lock
lock = redis_client.lock(f"seat:{seat_id}", timeout=30, blocking_timeout=5)
if lock.acquire():
    try:
        # Reserve seat
    finally:
        lock.release()
```

### API Gateway

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| Kong Gateway | 3.6.x (Docker: `kong:3.6`) | API gateway | Mandated. DB-less mode with declarative YAML config. HIGH |

**Kong DB-less config:**
```yaml
# docker-compose environment
KONG_DATABASE: "off"
KONG_DECLARATIVE_CONFIG: /etc/kong/kong.yml
KONG_PROXY_LISTEN: "0.0.0.0:8000"
KONG_ADMIN_LISTEN: "0.0.0.0:8001"
```

Use the official `kong:3.6` image (not `kong/kong-gateway` which is enterprise). Rate limiting plugin is built-in.

### WebSocket / Real-time

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| Flask-SocketIO | 5.6.x (latest 5.6.1) | WebSocket for e-ticket delivery | Professor requirement. Ticket Service delivers QR tickets via WebSocket. HIGH |
| python-socketio | (auto, pulled by Flask-SocketIO) | Engine.IO/Socket.IO server | Transitive dependency. Do not pin separately. HIGH |
| python-engineio | (auto, pulled by Flask-SocketIO) | Transport layer | Transitive dependency. HIGH |

**CRITICAL async_mode decision: Use `threading` mode.**

Eventlet is deprecated (maintenance-only since 2024, Python 3.10+ compatibility issues). Gevent has compatibility issues with pika and SQLAlchemy. Threading mode works out of the box with Flask's development server and is the recommended mode for new projects per Flask-SocketIO maintainer (Miguel Grinberg).

```python
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")
```

**Client-side:** Use `socket.io-client` v4.x on the React frontend. Flask-SocketIO 5.x requires Socket.IO protocol v5, which corresponds to `socket.io-client` 4.x+.

### External APIs

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| stripe | 14.x (latest 14.4.0) | Payment processing | Official Stripe Python SDK. Use test keys only. Actively maintained. HIGH |
| twilio | 9.x (latest 9.10.0) | SMS notifications | Official Twilio Python SDK. Use test credentials. HIGH |
| smtplib | (stdlib) | Gmail SMTP for email | Built into Python. No external library needed. Use Gmail App Password with TLS on port 587. HIGH |

### Scheduling

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| APScheduler | 3.10.x | Payment expiry scheduler | Used in Booking Orchestrator for 30-second payment timeout checks. Use APScheduler 3.x directly (NOT Flask-APScheduler wrapper -- unnecessary overhead for a single interval job). HIGH |

**Why APScheduler 3.x, not 4.x:** APScheduler 4.x is a complete rewrite with an async-first API. For a simple interval scheduler in a threading context, 3.10.x is simpler and battle-tested.

```python
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_expired_payments, 'interval', seconds=30)
scheduler.start()
```

### QR Code Generation

| Technology | Version | Purpose | Why / Confidence |
|------------|---------|---------|------------------|
| qrcode | 8.x (latest 8.0) | QR code generation | Standard Python QR library. Use with Pillow for image output. HIGH |
| Pillow | 12.x (latest 12.1.1) | Image processing for QR | Required by qrcode for PNG output. Supports Python 3.11. HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Flask-CORS | 6.0.x (latest 6.0.2) | CORS headers | Every microservice that React frontend calls directly (or just Kong if all traffic routes through gateway) |
| python-dotenv | 1.2.x (latest 1.2.2) | Environment variable loading | Every microservice for local dev. In Docker, use compose env vars instead. |
| requests | 2.32.x | HTTP client for inter-service calls | Orchestrator calling other services synchronously |
| gunicorn | 23.x | Production WSGI server | NOT needed for this project -- Flask dev server is fine for university demo. Include only if deploying. MEDIUM |

---

## Development Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | Latest stable | Container runtime |
| Docker Compose | v2 (bundled) | Multi-container orchestration |
| Node.js | 20.x LTS or 22.x | React frontend build |
| npm/yarn | Latest | Frontend package management |

### Frontend (React)

| Library | Version | Purpose |
|---------|---------|---------|
| React | 18.x or 19.x | UI framework |
| socket.io-client | 4.x | WebSocket client (must match Flask-SocketIO 5.x protocol) |
| axios | 1.x | HTTP client for API calls |
| react-router-dom | 6.x or 7.x | Client-side routing |
| @stripe/stripe-js | Latest | Stripe Elements for payment UI |

---

## Installation

### Per-microservice requirements.txt (base)

```
Flask==3.1.2
Flask-SQLAlchemy==3.1.1
SQLAlchemy==2.0.48
PyMySQL[rsa]==1.1.2
Flask-CORS==6.0.2
pika==1.3.2
python-dotenv==1.2.2
requests==2.32.3
```

### Seat Service (adds Redis)

```
redis==5.2.1
```

### Ticket Service (adds WebSocket + QR)

```
Flask-SocketIO==5.6.1
qrcode[pil]==8.0
Pillow==12.1.1
```

### Booking Orchestrator (adds scheduler)

```
APScheduler==3.10.4
```

### Payment Service (adds Stripe)

```
stripe==14.4.0
```

### Notification Service (adds Twilio)

```
twilio==9.10.0
```

### Frontend

```bash
npx create-react-app frontend
# or: npm create vite@latest frontend -- --template react
cd frontend
npm install socket.io-client axios react-router-dom @stripe/stripe-js
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| MySQL driver | PyMySQL | mysqlclient | mysqlclient requires C compilation and system libraries, painful in Docker Alpine images. PyMySQL is pure Python, works everywhere. |
| AMQP client | pika 1.3.2 | aio-pika, kombu | aio-pika is async (not needed). Kombu adds abstraction layer over pika with no benefit for direct AMQP usage. |
| Scheduler | APScheduler 3.x | Celery Beat, Flask-APScheduler | Celery is overkill for one interval job. Flask-APScheduler is a thin wrapper with no real added value. |
| WebSocket | Flask-SocketIO (threading) | Flask-Sock, plain WebSocket | Flask-SocketIO provides rooms (join by booking_id), which is exactly needed for e-ticket delivery. Flask-Sock lacks rooms/namespaces. |
| Redis client | redis-py 5.x | redis-py 7.x | redis-py 7.x targets Redis 7.2+; our Redis 7.0 image may have gaps. 5.x explicitly supports Redis 5.0-7.4 range. |
| ORM | SQLAlchemy 2.0 | Raw SQL, Peewee | SQLAlchemy is the industry standard. Raw SQL is error-prone. Peewee is less documented for Flask. |
| Frontend | React (Vite) | Next.js, Vue | SPA is sufficient; SSR adds complexity. Team already chose React. Use Vite over CRA -- CRA is deprecated. |
| QR library | qrcode | segno | qrcode is more popular, simpler API, well-documented. segno is faster but less commonly used. |
| Async mode | threading | eventlet, gevent | Eventlet is deprecated. Gevent has compatibility issues with pika and threading-based AMQP consumers. Threading is simple and sufficient for demo scale. |

---

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| **pika >= 1.4.0** | Requires Python 3.12+ and RabbitMQ 4.0+. Incompatible with mandated Python 3.11 / RabbitMQ 3.x. This is the single most dangerous version mismatch in the project. |
| **redis-py >= 6.0** | Version jump to 6.x/7.x targets newer Redis server versions. Stick with 5.x for Redis 7.0 compatibility. |
| **eventlet** | Deprecated since 2024. Causes monkey-patching issues with pika, SQLAlchemy, and standard library threading. |
| **gevent** | Monkey-patching conflicts with pika's BlockingConnection and threading-based AMQP consumers. |
| **Celery** | Massive overhead for a single scheduled task. APScheduler BackgroundScheduler is sufficient. |
| **mysqlclient** | Requires `libmysqlclient-dev` system package. Docker build headaches. PyMySQL is pure Python. |
| **Flask-RESTful / Flask-RESTX** | Adds abstraction over Flask routes with minimal benefit. Plain Flask routes with `jsonify()` are simpler for microservices. |
| **SQLAlchemy 1.4.x** | Legacy API. Use 2.0 style exclusively (`select()`, `Session.execute()`). |
| **Create React App (CRA)** | Deprecated. Use Vite for React frontend. |
| **APScheduler 4.x** | Complete async rewrite. Overkill for simple interval scheduling. Use 3.10.x. |
| **Flask-APScheduler** | Thin wrapper that adds Flask config integration but no real value. Use APScheduler directly. |

---

## Version Compatibility Matrix

This is the critical reference. Every version here has been verified against the mandated constraints.

| Component | Version | Python 3.11 | MySQL 8.0 | RabbitMQ 3.x | Redis 7.0 | Notes |
|-----------|---------|-------------|-----------|--------------|-----------|-------|
| Flask | 3.1.2 | YES | - | - | - | Requires Python >=3.9 |
| Flask-SQLAlchemy | 3.1.1 | YES | YES (via PyMySQL) | - | - | |
| SQLAlchemy | 2.0.48 | YES | YES | - | - | |
| PyMySQL[rsa] | 1.1.2 | YES | YES | - | - | `[rsa]` needed for MySQL 8 default auth |
| pika | **1.3.2** | YES | - | YES | - | **NOT 1.4.0** |
| redis-py | **5.2.x** | YES | - | - | YES | **NOT 6.x/7.x** |
| Flask-SocketIO | 5.6.1 | YES | - | - | - | Use async_mode='threading' |
| Flask-CORS | 6.0.2 | YES | - | - | - | Requires Python >=3.9 |
| APScheduler | 3.10.4 | YES | - | - | - | **NOT 4.x** |
| stripe | 14.4.0 | YES | - | - | - | |
| twilio | 9.10.0 | YES | - | - | - | |
| qrcode[pil] | 8.0 | YES | - | - | - | |
| Pillow | 12.1.1 | YES | - | - | - | |
| Kong | 3.6.x | - | - | - | - | Docker image: `kong:3.6` |

---

## Docker Base Images

| Service | Base Image | Why |
|---------|------------|-----|
| Python microservices | `python:3.11-slim` | Smaller than full image. Sufficient for pure-Python deps. |
| MySQL | `mysql:8.0` | Mandated version. |
| RabbitMQ | `rabbitmq:3-management` | Includes management UI on :15672 for debugging. |
| Redis | `redis:7` | Mandated version. |
| Kong | `kong:3.6` | OSS image. NOT `kong/kong-gateway` (enterprise). |
| Frontend | `node:20-alpine` (build) + `nginx:alpine` (serve) | Multi-stage build. |

---

## Configuration Best Practices

### MySQL 8.0 Authentication
MySQL 8.0 defaults to `caching_sha2_password` auth plugin. PyMySQL supports this with the `[rsa]` extra:
```bash
pip install PyMySQL[rsa]
```
Alternatively, set MySQL to use the older auth in Docker:
```yaml
command: --default-authentication-plugin=mysql_native_password
```
Recommendation: Use `PyMySQL[rsa]` rather than downgrading MySQL auth.

### RabbitMQ Connection Recovery
Pika 1.3.2 does NOT auto-reconnect. Wrap consumer connections with retry logic:
```python
while True:
    try:
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.basic_consume(queue=queue, on_message_callback=callback)
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError:
        time.sleep(5)  # Wait and retry
```

### Docker Compose Service Ordering
Use `depends_on` with `condition: service_healthy` for MySQL and RabbitMQ. Add healthchecks:
```yaml
mysql:
  healthcheck:
    test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
    interval: 10s
    timeout: 5s
    retries: 5
rabbitmq:
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "check_port_connectivity"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### Environment Variables
Use `.env` file for local dev, Docker Compose `environment:` block for containers. Never hardcode credentials. Key variables per service:
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`
- `STRIPE_SECRET_KEY` (test key)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- `GMAIL_USER`, `GMAIL_APP_PASSWORD`

---

## Sources

- [Flask PyPI](https://pypi.org/project/Flask/) - Version 3.1.2, Python >=3.9
- [Flask-SocketIO PyPI](https://pypi.org/project/Flask-SocketIO/) - Version 5.6.1
- [Flask-SocketIO async mode discussion](https://github.com/miguelgrinberg/Flask-SocketIO/discussions/2037) - Eventlet deprecation, threading recommendation
- [pika PyPI](https://pypi.org/project/pika/) - Version 1.3.2 vs 1.4.0 compatibility
- [pika 1.4.0 breaking changes](https://johal.in/rabbitmq-pika-1-4-0-python-amqp-heartbeat-retries-2025/) - Requires Python 3.12+, RabbitMQ 4.0+
- [redis-py PyPI](https://pypi.org/project/redis/) - Version compatibility matrix
- [redis-py server compatibility](https://github.com/redis/redis-py/issues/1925) - 5.x supports Redis 5.0-7.4
- [Flask-SQLAlchemy docs](https://flask-sqlalchemy.readthedocs.io/) - Version 3.1.x
- [SQLAlchemy MySQL dialect](https://docs.sqlalchemy.org/en/20/dialects/mysql.html) - PyMySQL + utf8mb4
- [PyMySQL PyPI](https://pypi.org/project/PyMySQL/) - Version 1.1.2, MySQL 8 auth support
- [Stripe Python SDK](https://pypi.org/project/stripe/) - Version 14.4.0
- [Twilio Python SDK](https://pypi.org/project/twilio/) - Version 9.10.0
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) - 3.x vs 4.x differences
- [Kong Docker Hub](https://hub.docker.com/_/kong) - OSS image tags
- [Flask-CORS PyPI](https://pypi.org/project/flask-cors/) - Version 6.0.2
