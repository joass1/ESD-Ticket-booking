# Domain Pitfalls

**Domain:** Microservices Event Ticketing Platform (Flask/Python, RabbitMQ, Redis, MySQL, Kong, Docker)
**Researched:** 2026-03-13
**Overall confidence:** HIGH (verified against official docs and known issue trackers)

---

## Critical Pitfalls

Mistakes that cause crashes, data corruption, or require rewrites.

### Pitfall 1: Pika Connections Are NOT Thread-Safe -- Shared Connection Across Flask + AMQP Threads

**What goes wrong:** The project requires every service to run Flask on the main thread and an AMQP consumer on a daemon thread (professor constraint #4). Developers share a single pika connection between both threads. This causes random `ConnectionClosed` exceptions, missed heartbeats, and silent message loss.

**Why it happens:** Pika's built-in connection adapters are explicitly not thread-safe. A connection created in one thread cannot safely be used from another thread. The AMQP heartbeat mechanism requires the I/O loop to run continuously; if the Flask thread blocks the connection, heartbeats are missed and RabbitMQ drops the connection.

**Consequences:**
- Random disconnections under load
- Messages silently lost (published on a dead connection)
- Heartbeat timeout kills the consumer, no messages processed until restart
- Extremely hard to debug -- works in dev, fails in demo

**Prevention:**
- Create ONE pika connection per thread. The Flask thread gets its own connection for publishing. The AMQP consumer thread gets its own connection for consuming.
- For publishing from Flask routes, use `BlockingConnection` created fresh or use a connection pool per thread.
- For the consumer thread, use `SelectConnection` or `BlockingConnection` with `basic_consume` in its own dedicated thread.
- Use `add_callback_threadsafe()` if you absolutely must cross threads with `SelectConnection`.
- Set heartbeat interval explicitly (e.g., `heartbeat=600`) and ensure the consumer thread's I/O loop is not blocked by long processing.

**Detection (warning signs):**
- `pika.exceptions.StreamLostError` or `ConnectionResetByPeer` in logs
- Consumer stops receiving messages after a few minutes
- "Missed heartbeats" warnings in RabbitMQ management UI

**Phase relevance:** Must be solved in the shared AMQP library (Phase 1 infrastructure). Every service inherits this pattern.

**Confidence:** HIGH -- verified via [pika FAQ](https://pika.readthedocs.io/en/stable/faq.html) and [pika GitHub](https://github.com/pika/pika)

---

### Pitfall 2: Redis Distributed Lock TTL Expiry Causes Double-Booking

**What goes wrong:** Seat Service uses Redis distributed locks for concurrency. If the lock TTL is too short and the Booking Orchestrator saga takes longer than expected (e.g., Stripe is slow), the lock expires while the seat is still being processed. Another user acquires the same seat. Both bookings succeed. Two tickets, one seat.

**Why it happens:** Developers set a short TTL (e.g., 5 seconds) without accounting for the full saga duration including network latency to Stripe, database writes, and AMQP message round-trips. Under load or when Stripe test mode is slow, the critical section exceeds the TTL.

**Consequences:**
- Double-booking of seats (data integrity violation)
- Compensating transactions needed retroactively
- User trust destroyed

**Prevention:**
- Set TTL to 2-3x the expected maximum saga duration (e.g., 30-60 seconds for a booking flow that normally takes 5-10 seconds).
- Use atomic SET with NX and EX (not separate SETNX + EXPIRE -- if the process crashes between them, the lock never expires).
- Store a unique token (UUID) as the lock value. On release, use a Lua script to check ownership before deleting: `if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end`
- Never release a lock you no longer own (the Lua script prevents this).
- Consider a lock extension/renewal mechanism for long-running operations.

**Detection:**
- Two bookings referencing the same seat_id in the database
- Lock acquisition succeeding when it should have been held
- Redis MONITOR showing rapid SET/DEL cycles on the same key

**Phase relevance:** Seat Service implementation. Must be correct before Scenario 1 integration testing.

**Confidence:** HIGH -- verified via [Redis distributed locks documentation](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)

---

### Pitfall 3: Saga Compensating Transactions Are Not Idempotent

**What goes wrong:** The Booking Orchestrator saga fails partway (e.g., payment fails after seat is locked). It triggers compensating transactions (unlock seat, cancel booking). The compensation message is delivered twice (RabbitMQ redelivery after network glitch). The seat is unlocked twice, or a refund is issued twice.

**Why it happens:** Developers write compensating transactions as simple "undo" operations without checking current state. Combined with RabbitMQ's at-least-once delivery, compensations execute multiple times.

**Consequences:**
- Double refunds via Stripe (real money lost, even in test mode this masks bugs)
- Seat unlocked when it was re-locked by a different booking
- Booking state machine enters impossible states

**Prevention:**
- Every compensating transaction MUST be idempotent. Check current state before acting:
  - "Unlock seat" should verify the seat is locked by THIS booking before unlocking
  - "Refund payment" should check if a refund already exists for this payment_intent_id
  - "Cancel booking" should only transition from specific states (not already cancelled)
- Store a `saga_id` or `correlation_id` on every operation. Compensations reference it to ensure they only undo their own saga's work.
- Use database status fields as guards: `UPDATE seats SET status='available' WHERE seat_id=? AND status='locked' AND locked_by_booking_id=?`
- Log every compensation with its correlation_id for debugging.

**Detection:**
- Stripe dashboard showing duplicate refunds for the same charge
- Seat status flip-flopping in logs
- Booking records in inconsistent states (e.g., cancelled but seat still locked)

**Phase relevance:** Booking Orchestrator implementation. Critical for Scenario 1 and Scenario 3.

**Confidence:** HIGH -- verified via [Microsoft Saga Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga) and [microservices.io Saga](https://microservices.io/patterns/data/saga.html)

---

### Pitfall 4: Flask-SocketIO Eventlet Monkey Patching Breaks Pika and MySQL Drivers

**What goes wrong:** Ticket Service uses Flask-SocketIO for WebSocket e-ticket delivery. Flask-SocketIO with eventlet requires `eventlet.monkey_patch()` at the top of the file. This monkey-patches Python's standard library threading and socket modules. Pika's `BlockingConnection` and MySQL drivers (PyMySQL, mysqlclient) break or hang indefinitely because their socket operations are now green-threaded.

**Why it happens:** Eventlet replaces real threads with cooperative green threads. Pika expects real OS-level sockets and threads. When monkey-patched, blocking calls in pika never yield to the event loop, causing deadlocks. Similarly, MySQL drivers may hang on connection.

**Consequences:**
- Ticket Service hangs on startup or after first message
- AMQP consumer thread never processes messages
- Database queries hang or timeout
- Service appears healthy (Flask responds) but WebSocket and AMQP are dead

**Prevention:**
- Use `eventlet.monkey_patch(thread=False)` for partial patching if you need real threads for pika. Test thoroughly.
- Better approach: Isolate the SocketIO concern. Run Flask-SocketIO in the Ticket Service ONLY. Other services do NOT use eventlet. The Ticket Service receives messages via AMQP (using a compatible approach) and emits via SocketIO.
- If using eventlet, consider using `kombu` or `amqp` libraries that have eventlet-compatible transports instead of raw pika.
- Test the Ticket Service in isolation first -- if AMQP consuming works alongside SocketIO emit, you are safe.

**Detection:**
- Service starts but AMQP callback never fires
- `greenlet.GreenletExit` exceptions in logs
- MySQL connection timeouts only in the Ticket Service (other services are fine)
- CPU at 0% but service is unresponsive

**Phase relevance:** Ticket Service implementation. Must be resolved before Scenario 1 e-ticket delivery.

**Confidence:** HIGH -- verified via [Flask-SocketIO monkey patching issues](https://github.com/miguelgrinberg/Flask-SocketIO/discussions/2048) and [deployment docs](https://flask-socketio.readthedocs.io/en/latest/deployment.html)

---

### Pitfall 5: Docker Compose `depends_on` Does Not Wait for Service Readiness

**What goes wrong:** Services start before MySQL, RabbitMQ, or Redis are actually ready to accept connections. The Flask services crash on startup because they try to connect to databases/queues that are still initializing. `depends_on` only waits for the container to START, not for the service inside to be READY.

**Why it happens:** MySQL takes 10-30 seconds to initialize (especially first run with schema creation). RabbitMQ takes 15-30 seconds. `depends_on` without `condition: service_healthy` just checks if the container process is running.

**Consequences:**
- `docker-compose up` fails intermittently -- works on fast machines, fails on slower ones
- Demo day disaster: "it worked on my machine"
- Students resort to manual restarts or `sleep` hacks in entrypoints

**Prevention:**
- Use `depends_on` with `condition: service_healthy` and define proper `healthcheck` blocks:

```yaml
services:
  mysql:
    image: mysql:8.0
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 30s

  rabbitmq:
    image: rabbitmq:3-management
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_port_connectivity"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 30s

  redis:
    image: redis:7
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  seat_service:
    depends_on:
      mysql:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
```

- Additionally, implement connection retry logic in each service's startup code (healthchecks help but are not bulletproof).

**Detection:**
- `Connection refused` errors on first `docker-compose up`
- Services restarting repeatedly in `docker-compose ps`
- Works on second `docker-compose up` but not the first

**Phase relevance:** Docker Compose infrastructure (Phase 1). Every other phase depends on this.

**Confidence:** HIGH -- verified via [Docker Compose startup order docs](https://docs.docker.com/compose/how-tos/startup-order/)

---

## Moderate Pitfalls

### Pitfall 6: APScheduler Duplicate Job Execution in Flask

**What goes wrong:** The Booking Orchestrator uses APScheduler for payment expiry (30-second interval checks). When Flask runs with `use_reloader=True` (the default in debug mode), Flask spawns two processes. APScheduler runs in both. Every expiry check fires twice, potentially cancelling bookings that just completed payment.

**Why it happens:** Flask's reloader forks a child process that also initializes APScheduler. In Docker with Gunicorn using multiple workers, each worker runs its own APScheduler instance.

**Prevention:**
- Use `use_reloader=False` in Flask development mode.
- In Docker, run with a single Gunicorn worker for the orchestrator: `gunicorn -w 1`.
- Better: use APScheduler's `replace_existing=True` flag when adding jobs and assign explicit `job_id` values to prevent duplicates.
- For the orchestrator specifically, consider running APScheduler in a dedicated background thread rather than relying on Flask's lifecycle.

**Detection:**
- Booking cancellation logs showing two cancellation attempts for the same booking
- Payment expiry firing before the 30-second window

**Phase relevance:** Booking Orchestrator implementation.

**Confidence:** HIGH -- verified via [APScheduler FAQ](https://apscheduler.readthedocs.io/en/3.x/faq.html) and [Flask-APScheduler tips](https://viniciuschiele.github.io/flask-apscheduler/rst/tips.html)

---

### Pitfall 7: RabbitMQ Unacknowledged Messages Cause Redelivery Storms

**What goes wrong:** A consumer crashes or throws an exception without acknowledging the message. RabbitMQ redelivers the message. If the message consistently causes an error (poison message), it is redelivered infinitely, consuming CPU and blocking the queue.

**Why it happens:** With `auto_ack=False` (which you should use for reliability), failing to call `basic_ack` or `basic_nack` leaves messages in "unacked" state. On consumer disconnect, all unacked messages are requeued to the HEAD of the queue, causing a redelivery storm.

**Prevention:**
- Always wrap message handling in try/except. In the except block, either `basic_nack(requeue=False)` to dead-letter the message, or `basic_nack(requeue=True)` with a retry counter.
- Implement a dead-letter exchange (DLX) for messages that fail repeatedly. After N retries, route to a dead-letter queue for manual inspection.
- Check the `redelivered` flag on incoming messages. If redelivered more than N times (track via headers), send to DLX.
- Set `prefetch_count` to a reasonable value (10-20) to prevent one consumer from hoarding unacked messages.
- Never use `auto_ack=True` for anything involving payments, bookings, or seat locks.

**Detection:**
- RabbitMQ management UI showing high "Unacked" count
- Same message appearing in consumer logs repeatedly
- High CPU on RabbitMQ server

**Phase relevance:** Shared AMQP library (Phase 1). Pattern must be established before any service uses it.

**Confidence:** HIGH -- verified via [RabbitMQ Consumer Acknowledgements docs](https://www.rabbitmq.com/docs/confirms)

---

### Pitfall 8: MySQL Connection Pool Exhaustion in Flask Microservices

**What goes wrong:** Each Flask microservice opens MySQL connections but does not properly return them to the pool. Under load (or after idle periods), connections are exhausted or stale. Services throw `OperationalError: (2006, 'MySQL server has gone away')` or `max_user_connections exceeded`.

**Why it happens:** MySQL drops idle connections after `wait_timeout` (default 8 hours). Flask-SQLAlchemy's default pool does not pre-ping connections. Stale connections from the pool fail on use. Additionally, if `db.session.remove()` is not called after each request (via `@app.teardown_appcontext`), connections leak.

**Prevention:**
- Configure Flask-SQLAlchemy properly:
```python
app.config['SQLALCHEMY_POOL_SIZE'] = 5
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800  # 30 min, well under MySQL's wait_timeout
app.config['SQLALCHEMY_POOL_PRE_PING'] = True  # Health check before use
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 10
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 2
```
- Ensure `db.session.remove()` is called via teardown (Flask-SQLAlchemy does this automatically if initialized correctly with `db.init_app(app)`).
- In Docker, set MySQL's `max_connections` high enough for all services combined (default 151 may not be enough with 8+ microservices).

**Detection:**
- `MySQL server has gone away` after periods of inactivity
- `QueuePool limit` warnings in SQLAlchemy logs
- Connections piling up in `SHOW PROCESSLIST` on MySQL

**Phase relevance:** Database setup (Phase 1). Configuration applies to every service with a database.

**Confidence:** HIGH -- verified via [Flask-SQLAlchemy config docs](https://flask-sqlalchemy.readthedocs.io/en/stable/config/)

---

### Pitfall 9: Kong Declarative Config Silent Failures

**What goes wrong:** Kong in DB-less mode loads a `kong.yml` declarative config. If the YAML has syntax errors or references nonexistent services/routes, Kong starts but silently ignores the broken entries. Requests return 404 and developers spend hours debugging their services when the problem is in the gateway config.

**Why it happens:** Kong validates the declarative config at load time but does not fail loudly for all error types. Typos in service names, incorrect upstream URLs (e.g., `http://seat_service:5000` vs `http://seat-service:5000` -- underscores vs hyphens in Docker service names), or missing plugins cause silent routing failures.

**Prevention:**
- Validate the config before loading: `kong config parse kong.yml` (run in the Kong container).
- Use Docker Compose service names EXACTLY as defined -- hyphens and underscores matter.
- Test every route individually after Kong starts: `curl http://localhost:8000/api/v1/seats` etc.
- Keep the declarative config in version control and review changes carefully.
- Do NOT embed secrets (Stripe keys, DB passwords) in `kong.yml` -- use environment variables.
- For rate limiting plugins, test that they actually activate (hit the endpoint rapidly and verify 429 responses).

**Detection:**
- All services work when accessed directly but return 404 through Kong
- Kong logs showing "no Route matched" errors
- Admin API (`GET :8001/routes`) shows fewer routes than expected

**Phase relevance:** Kong API Gateway setup. Should be validated as part of infrastructure phase.

**Confidence:** MEDIUM -- based on [Kong DB-less docs](https://developer.konghq.com/gateway/db-less-mode/) and community reports

---

### Pitfall 10: CORS Nightmares with React Frontend + Kong + Multiple Services

**What goes wrong:** React app on `localhost:3000` talks to Kong on `localhost:8000`. Preflight (OPTIONS) requests fail because CORS headers are not configured at the right layer. Developers add `flask-cors` to every service AND configure CORS on Kong, causing duplicate or conflicting headers. Some routes work, others do not.

**Why it happens:** CORS must be handled at exactly ONE layer. If Kong adds `Access-Control-Allow-Origin: *` and the Flask service also adds it, browsers receive duplicate headers and reject the response. Additionally, Kong must handle OPTIONS preflight requests before they reach backend services.

**Prevention:**
- Handle CORS at the Kong layer ONLY. Add the `cors` plugin globally in `kong.yml`:
```yaml
plugins:
  - name: cors
    config:
      origins:
        - "http://localhost:3000"
      methods:
        - GET
        - POST
        - PUT
        - DELETE
        - OPTIONS
      headers:
        - Content-Type
        - Authorization
      credentials: true
      max_age: 3600
```
- Remove `flask-cors` from all backend services (or at minimum, do not set `Access-Control-Allow-Origin` on both layers).
- During development without Kong, use React's proxy setting in `package.json`: `"proxy": "http://localhost:5000"`.

**Detection:**
- Browser console showing "CORS policy" errors on preflight
- Some endpoints work (simple GET) but POST/PUT fail (they trigger preflight)
- Response headers showing duplicate `Access-Control-Allow-Origin` values

**Phase relevance:** Frontend integration phase. Must be resolved before end-to-end testing.

**Confidence:** HIGH -- verified via [flask-cors GitHub issues](https://github.com/corydolphin/flask-cors/issues/292) and common patterns

---

## Minor Pitfalls

### Pitfall 11: Stripe Test Mode Clock Object Gotchas

**What goes wrong:** In test mode, Stripe does not send real webhook events automatically for payment timeouts. Developers assume their payment expiry logic works because they tested the happy path, but never tested what happens when a PaymentIntent expires or when the webhook fires out of order.

**Prevention:**
- Use Stripe CLI (`stripe listen --forward-to localhost:5000/webhook`) to forward test webhooks.
- Use `stripe trigger payment_intent.payment_failed` to test failure scenarios.
- Always verify webhook signatures using the raw request body (`request.get_data(as_text=True)`), not parsed JSON.
- Store processed `event.id` values to handle duplicate webhook deliveries idempotently.
- Respond to webhooks within 20 seconds or Stripe retries.

**Phase relevance:** Payment Service implementation.

**Confidence:** MEDIUM -- based on [Stripe webhook docs](https://docs.stripe.com/webhooks)

---

### Pitfall 12: Topic Exchange Fan-Out Missing Bindings

**What goes wrong:** Scenario 3 (event cancellation) uses a topic exchange to fan out `event.cancelled` to 5 services. If even one service has not yet started (and thus has not declared its queue and binding), it misses the cancellation message entirely. There is no retry -- the message is gone.

**Prevention:**
- Declare queues and bindings on BOTH sides (publisher and consumer). The publisher should ensure the exchange exists; each consumer declares its own queue and binding on startup.
- Alternatively, use durable queues with durable exchanges. Messages published to a durable exchange with a durable, bound queue will survive even if the consumer is temporarily down.
- For critical operations like cancellations, consider adding a database-backed "outbox" pattern: write the event to a database table, then publish. If a service missed it, it can query the outbox on startup.

**Detection:**
- One service processes the cancellation, others do not
- Queue count in RabbitMQ management UI is fewer than expected

**Phase relevance:** Scenario 3 implementation. Requires all 5 consuming services to be running.

**Confidence:** HIGH -- standard RabbitMQ behavior

---

### Pitfall 13: Waitlist Cascading Promotions Race Condition

**What goes wrong:** In Scenario 2, when a seat is released, the waitlist promotes the next person. If the promoted person's payment also fails and the seat is released again, a cascading promotion can trigger multiple simultaneous promotions for the same seat via AMQP messages arriving out of order.

**Prevention:**
- Use the Redis lock on the specific seat during promotion (same lock as booking).
- Make promotions idempotent: check seat status before promoting. If seat is already locked by another promotion, skip.
- Process waitlist promotions sequentially per event (use a single consumer with prefetch_count=1 for the waitlist queue).

**Phase relevance:** Scenario 2 implementation.

**Confidence:** MEDIUM -- architecture-specific reasoning

---

## Technical Debt Patterns

### Pattern: "Works in Dev, Fails in Docker"

Services tested locally with `flask run` behave differently in Docker because:
- Hostnames change (localhost vs Docker service names)
- Environment variables are missing or have different values
- File paths differ (especially for volume mounts)
- Network timing changes (services start in parallel)

**Prevention:** Develop and test INSIDE Docker from day one. Use `docker-compose up --build` as the primary run command, not `flask run`.

### Pattern: "Hardcoded URLs Everywhere"

Services hardcode `http://localhost:5001/api/booking` instead of using environment variables. When deployed in Docker, localhost does not resolve to other containers.

**Prevention:** Every service URL must come from environment variables:
```python
BOOKING_SERVICE_URL = os.environ.get('BOOKING_SERVICE_URL', 'http://booking_service:5001')
```

### Pattern: "No Error Handling in HTTP Calls"

Service A calls Service B via HTTP. Service B is down. Service A crashes with an unhandled `ConnectionError` instead of returning a meaningful error to the saga orchestrator.

**Prevention:** Wrap all inter-service HTTP calls in try/except with timeout:
```python
try:
    response = requests.post(url, json=data, timeout=5)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    return {"error": str(e), "service": "booking"}, 503
```

---

## Integration Gotchas

| Integration | Gotcha | Fix |
|-------------|--------|-----|
| React + Kong | WebSocket connections cannot go through Kong easily (needs explicit upstream) | Route SocketIO directly to Ticket Service, bypass Kong for WS |
| Stripe + Flask | Raw body needed for webhook verification, Flask parses it first | Use `request.get_data(as_text=True)` BEFORE `request.get_json()` |
| OutSystems + Event Service | OutSystems REST connector may not handle CORS or non-200 responses well | Ensure Event Service returns proper status codes and CORS headers for OutSystems domain |
| RabbitMQ + Docker | RabbitMQ management UI default credentials (guest/guest) only work from localhost | Set `RABBITMQ_DEFAULT_USER` and `RABBITMQ_DEFAULT_PASS` environment variables |
| Redis + Docker | Redis has no password by default in Docker -- fine for dev, but any service can flush the lock store | Set `--requirepass` if multiple teams share the environment |

---

## Performance Traps

| Trap | Impact | Mitigation |
|------|--------|------------|
| Synchronous Stripe calls inside saga | Stripe API calls take 1-3 seconds; blocks the orchestrator thread | Set reasonable timeouts (10s max), implement async payment with webhooks for confirmation |
| Large QR code generation blocking Flask | QR code generation with image encoding blocks the request thread | Generate QR codes in the AMQP consumer thread, not in HTTP request handlers |
| N+1 queries in seat listing | Loading 500 seats with individual queries per seat | Use eager loading or batch queries; return seat status from a single query with JOIN |
| No pagination on event listing | Loading all events on frontend renders slowly | Implement server-side pagination from Phase 1 |

---

## Security Mistakes

| Mistake | Risk | Fix |
|---------|------|-----|
| Stripe secret key in frontend code | Key exposed in browser, anyone can charge your account | Secret key stays on backend ONLY; frontend uses publishable key only |
| No webhook signature verification | Anyone can POST fake payment confirmations | Always verify with `stripe.Webhook.construct_event()` |
| Stripe keys committed to Git | Keys in version history even after removal | Use `.env` files, add to `.gitignore`, use Docker env_file |
| No rate limiting on booking endpoint | Bot can lock all seats instantly | Kong rate-limiting plugin on booking routes |
| WebSocket rooms not authenticated | Anyone can join a booking_id room and receive e-tickets | Validate booking ownership before joining SocketIO room |

---

## "Looks Done But Isn't" Checklist

| Item | Looks Done When... | Actually Done When... |
|------|-------------------|----------------------|
| Seat locking | Lock acquired, booking created | Lock has proper TTL, ownership check on release, handles TTL expiry gracefully |
| Payment flow | Stripe charge succeeds | Handles failures, timeouts, duplicate webhooks, refund path tested |
| Saga orchestration | Happy path works | All compensation paths tested, idempotent compensations, timeout handling |
| WebSocket tickets | QR code appears in browser | Works when user reconnects, works after page refresh, room cleanup on disconnect |
| Event cancellation | Cancellation triggers refunds | All 5 fan-out consumers process it, partial failures handled, service fee retained |
| Docker setup | `docker-compose up` works once | Works on fresh clone, healthchecks pass, handles restart, no hardcoded paths |
| Kong routing | Requests reach services | CORS works, rate limiting active, WebSocket route configured, error responses proper |
| Waitlist promotion | Next person notified | Cascading promotions work, concurrent promotions safe, handles declined payments |
| AMQP consumers | Messages received | Acknowledgment correct, dead-letter configured, handles poison messages, reconnects on failure |
| Database | Queries work | Connection pooling configured, pool_recycle set, migrations repeatable |

---

## Pitfall-to-Phase Mapping

| Phase / Topic | Likely Pitfall | Severity | Mitigation |
|---------------|---------------|----------|------------|
| Docker Compose Infrastructure | Startup ordering (Pitfall 5) | CRITICAL | Healthchecks with `service_healthy` condition |
| Shared AMQP Library | Thread safety (Pitfall 1), Ack handling (Pitfall 7) | CRITICAL | One connection per thread, try/except with nack |
| Database Setup | Connection pooling (Pitfall 8) | MODERATE | pool_recycle, pool_pre_ping, proper teardown |
| Seat Service | Double-booking via TTL (Pitfall 2) | CRITICAL | Atomic SET NX EX, Lua release script, proper TTL |
| Payment Service | Stripe webhook handling (Pitfall 11) | MODERATE | Signature verification, idempotent processing |
| Ticket Service | Eventlet monkey patching (Pitfall 4) | CRITICAL | Partial patching or isolated SocketIO process |
| Booking Orchestrator | Non-idempotent compensations (Pitfall 3), APScheduler duplicates (Pitfall 6) | CRITICAL | State guards, correlation IDs, single worker |
| Scenario 2 (Waitlist) | Cascading race condition (Pitfall 13) | MODERATE | Sequential processing, Redis lock per seat |
| Scenario 3 (Cancellation) | Missing fan-out bindings (Pitfall 12) | MODERATE | Durable queues, declare on both sides |
| Kong Gateway | Silent config failures (Pitfall 9) | MODERATE | Config validation, test every route |
| Frontend Integration | CORS conflicts (Pitfall 10) | MODERATE | Single CORS layer at Kong |

---

## Sources

- [Pika FAQ - Thread Safety](https://pika.readthedocs.io/en/stable/faq.html)
- [Redis Distributed Locks Documentation](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)
- [Redis Distributed Locks: 10 Common Mistakes](https://leapcell.io/blog/redis-distributed-locks-10-common-mistakes)
- [Microsoft Saga Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
- [microservices.io Saga Pattern](https://microservices.io/patterns/data/saga.html)
- [Flask-SocketIO Monkey Patching Discussion](https://github.com/miguelgrinberg/Flask-SocketIO/discussions/2048)
- [Flask-SocketIO Deployment Docs](https://flask-socketio.readthedocs.io/en/latest/deployment.html)
- [Docker Compose Startup Order](https://docs.docker.com/compose/how-tos/startup-order/)
- [APScheduler FAQ](https://apscheduler.readthedocs.io/en/3.x/faq.html)
- [RabbitMQ Consumer Acknowledgements](https://www.rabbitmq.com/docs/confirms)
- [RabbitMQ Redelivery Pitfalls](https://blog.forma-pro.com/rabbitmq-redelivery-pitfalls-440e0347f4e0)
- [Flask-SQLAlchemy Configuration](https://flask-sqlalchemy.readthedocs.io/en/stable/config/)
- [Kong DB-less Mode](https://developer.konghq.com/gateway/db-less-mode/)
- [Stripe Webhook Documentation](https://docs.stripe.com/webhooks)
- [Flask-CORS Issues](https://github.com/corydolphin/flask-cors/issues/292)
- [Flask-APScheduler Tips](https://viniciuschiele.github.io/flask-apscheduler/rst/tips.html)
