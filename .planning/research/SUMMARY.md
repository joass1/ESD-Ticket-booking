# Project Research Summary

**Project:** ESD Event Ticketing Platform (IS213 SMU)
**Domain:** Microservices event ticketing — saga orchestration, AMQP choreography, fan-out cancellation
**Researched:** 2026-03-13
**Confidence:** HIGH

## Executive Summary

This is a university microservices project structured around three mandatory scenarios: a booking saga (orchestration), a waitlist promotion chain (choreography), and an event cancellation fan-out (pub/sub). The stack is almost entirely mandated by the course — Python 3.11, Flask, MySQL 8.0, RabbitMQ 3, Redis 7, Kong 3.6, Docker Compose — leaving library version selection and architectural pattern decisions as the key research questions. The recommended approach is to build in strict dependency order: shared infrastructure and AMQP library first, then foundational atomic services, then the Booking Orchestrator saga, then event-driven consumers, and finally the Waitlist Service and frontend. Attempting to build services out of this order (e.g., the Orchestrator before Seat/Payment/Booking, or the frontend before Kong) leads to blocked work and integration failures.

The most important architectural insight from research is that the three scenarios map cleanly onto three distinct distributed systems patterns, each with its own failure modes. Scenario 1 (orchestration saga) requires explicit compensating transactions with idempotency guards and correct Redis lock TTL sizing. Scenario 2 (choreography) depends on a self-referencing cascading promotion loop in the Waitlist Service, which must use sequential AMQP processing and per-seat Redis locks to prevent race conditions. Scenario 3 (topic exchange fan-out) requires all five consumer services to have declared their queues and bindings before the first `event.cancelled` message is published, or events are silently lost.

The single highest-risk version constraint in the entire stack is `pika==1.3.2`. Upgrading to 1.4.0 (the latest release) breaks the project completely because it requires Python 3.12+ and RabbitMQ 4.x, neither of which is available in this environment. The second-highest risk is Flask-SocketIO's async mode: eventlet is deprecated and monkey-patches PyMySQL and pika into deadlock; `async_mode='threading'` is the correct and only safe choice. These two decisions must be locked in before any service is built.

## Key Findings

### Recommended Stack

The course mandates the runtime and infrastructure stack. Research focused on library versions and compatibility within those constraints. Every version choice below was verified against the mandated Python 3.11 / MySQL 8.0 / RabbitMQ 3.x / Redis 7.0 combination.

**Core technologies:**
- **Flask 3.1.2** — web framework; latest stable, full Python 3.11 support
- **pika 1.3.2** — AMQP client; CRITICAL: do NOT use 1.4.0 (requires Python 3.12+ and RabbitMQ 4.x)
- **redis-py 5.2.x** — Redis client; use 5.x series (NOT 6.x/7.x which target Redis 7.2+)
- **Flask-SocketIO 5.6.1 (threading mode)** — WebSocket e-ticket delivery; eventlet is deprecated and breaks pika/SQLAlchemy
- **SQLAlchemy 2.0.x + Flask-SQLAlchemy 3.1.x** — ORM; use 2.0 style API exclusively
- **PyMySQL[rsa] 1.1.2** — MySQL driver; pure Python, no C compilation, `[rsa]` extra required for MySQL 8.0 default auth
- **APScheduler 3.10.4** — payment expiry scheduler; do NOT use 4.x (async rewrite, incompatible) or Flask-APScheduler (unnecessary wrapper)
- **stripe 14.4.0 / twilio 9.10.0** — payment and SMS; official SDKs, test credentials only
- **Kong 3.6 (DB-less)** — API gateway; use `kong:3.6` OSS image (not enterprise), declarative YAML config
- **socket.io-client 4.x** — React WebSocket client; must match Flask-SocketIO 5.x protocol (Socket.IO v5)

See `.planning/research/STACK.md` for the full version compatibility matrix and per-service `requirements.txt` templates.

### Expected Features

All three scenarios are P0 (non-negotiable for demo). Research cross-referenced against industry ticketing platforms (Ticketmaster, Eventbrite) to identify which features users expect and which are demo differentiators.

**Must have (table stakes — all P0):**
- Distributed seat locking with Redis — prevents double-booking under concurrency
- Booking orchestration saga with compensating transactions — core of Scenario 1
- Payment expiry via APScheduler (30s interval) — professor requirement
- Waitlist choreography via AMQP — no direct HTTP between Seat and Waitlist (professor constraint)
- Cascading waitlist promotions on seat release — core of Scenario 2
- Event cancellation fan-out to 5 consumers — core of Scenario 3
- 10% service fee retention on refunds — professor requirement
- QR code e-ticket via WebSocket (Flask-SocketIO rooms by `booking_id`) — BTL feature
- Kong API Gateway with rate limiting — BTL feature

**Should have (P1 — course requirements or significant demo value):**
- Email/SMS notifications via Notification Service (AMQP-driven)
- Interactive seat map in React frontend
- OutSystems admin dashboard for event management
- Booking history for users

**Defer entirely (anti-features):**
- OAuth / social login — not relevant to ESD concepts
- Dynamic pricing, ticket resale, multi-currency — out of scope for all 3 scenarios
- PDF ticket generation — QR via WebSocket is sufficient
- Per-user rate limiting — global Kong rate limiting is sufficient
- Full-text search, mobile app, real-time chat

See `.planning/research/FEATURES.md` for the full prioritization matrix and feature dependency graph.

### Architecture Approach

The system has one composite service (Booking Orchestrator) that coordinates Scenario 1 via synchronous HTTP, and eight atomic services that each own exactly one MySQL database. Scenarios 2 and 3 are fully event-driven: services communicate only via RabbitMQ topic/direct exchanges, never via HTTP between each other. The Notification Service is pure fire-and-forget — it must never block a saga. The Ticket Service is the only service using Flask-SocketIO; all others use `threading.Thread(daemon=True)` for AMQP consumers.

**Major components:**
1. **Kong API Gateway (8000)** — single entry point, DB-less declarative YAML, rate limiting, CORS (handle at Kong only — not in Flask services)
2. **Booking Orchestrator (5010)** — saga coordination: reserve seat → charge payment → confirm seat → create booking; APScheduler payment expiry; compensating transactions
3. **Seat Service (5003)** — seat inventory; Redis SET NX + MySQL FOR UPDATE two-phase locking; publishes `seat.released` on seat freeing
4. **Event Service (5001)** — event CRUD; publishes `event.cancelled.{event_id}` to topic exchange on cancellation
5. **Payment Service (5004)** — Stripe PaymentIntent creation and refunds; consumes `refund.process` from Charging Service
6. **Waitlist Service (5007)** — AMQP-only relationship with Seat Service; self-referencing cascade loop on promotion expiry; Redis TTL for promotion window
7. **Charging Service (5008)** — computes 10% service fee on cancellation refunds; triggers batch refund via `refund_direct` exchange
8. **Ticket Service (5006)** — Flask-SocketIO rooms; QR code generation (qrcode + Pillow); emits e-ticket to room keyed by `booking_id`
9. **Notification Service (5005)** — pure AMQP consumer; Gmail SMTP + Twilio SMS; subscribes to 4 exchanges
10. **Booking Service (5002)** — booking record management; consumes `event.cancelled` and `refund.completed` for status updates

**Critical constraint:** Seat Service and Waitlist Service must NEVER communicate via HTTP. This is a professor-enforced architectural rule.

See `.planning/research/ARCHITECTURE.md` for full data flows, AMQP exchange/routing key matrix, and dependency graph.

### Critical Pitfalls

5 critical pitfalls (crash / data corruption / rewrite risk) and 8 moderate/minor pitfalls were identified. The top 5 to address before any service is coded:

1. **Pika thread safety** — pika connections are NOT thread-safe. Each thread (Flask HTTP and AMQP consumer) must have its own separate `BlockingConnection`. Sharing a connection between threads causes silent message loss and random disconnections. Solve this once in `shared/amqp_lib.py` — all services inherit it.

2. **Redis lock TTL too short = double-booking** — set lock TTL to 60 seconds (2-3x the worst-case saga duration). Use atomic `SET NX EX` in a single command. Use a Lua script for ownership-checking release: verify the lock value (UUID) before deleting. Never release a lock you do not own.

3. **Non-idempotent compensating transactions** — saga compensations must check current state before acting. "Release seat" must verify `locked_by_booking_id` matches. "Issue refund" must check if refund already exists for this `payment_intent_id`. Use `correlation_id` on every operation for audit trail.

4. **Flask-SocketIO eventlet monkey-patching** — eventlet breaks pika and PyMySQL in the Ticket Service. Use `async_mode='threading'` in Flask-SocketIO. Do not import or call `eventlet.monkey_patch()` anywhere. This decision must be set before building Ticket Service.

5. **Docker Compose `depends_on` without healthchecks** — `depends_on` alone only waits for container start, not service readiness. MySQL takes 10-30 seconds to initialize. Always use `condition: service_healthy` with proper `healthcheck` blocks for MySQL, RabbitMQ, and Redis. Must be in docker-compose.yml before any service is coded.

Additional important pitfalls: APScheduler duplicate job execution with Flask reloader (use `use_reloader=False`), CORS conflicts between Kong and Flask-CORS (handle at Kong only), topic exchange fan-out missing bindings if a consumer is not yet running (use durable queues), and WebSocket connections bypassing Kong (route SocketIO directly to Ticket Service).

See `.planning/research/PITFALLS.md` for detection signals and the full pitfall-to-phase mapping table.

## Implications for Roadmap

Research strongly supports a 6-phase build order driven by service dependencies. The order is non-negotiable: each layer enables the next. Attempting to build in parallel beyond what the dependency graph allows wastes time on integration errors.

### Phase 1: Infrastructure and Shared Foundation

**Rationale:** Every service depends on Docker Compose being correct and `shared/amqp_lib.py` existing. The two most critical pitfalls (Docker startup ordering and pika thread safety) must be solved here, once, before any service is written. This phase has no dependencies itself.

**Delivers:** Working `docker-compose.yml` with healthchecks for MySQL/RabbitMQ/Redis/Kong; `shared/amqp_lib.py` with per-thread connection management and ack/nack error handling; `.env.example`; database initialization; Kong skeleton config.

**Addresses:** Event browsing infrastructure dependency, all service database connectivity.

**Avoids:** Pitfall 5 (Docker startup ordering), Pitfall 1 (pika thread safety), Pitfall 7 (unacked message redelivery), Pitfall 8 (MySQL connection pooling — configure `SQLALCHEMY_POOL_PRE_PING` and `SQLALCHEMY_POOL_RECYCLE` in shared config template).

**Research flag:** No deeper research needed — Docker Compose healthcheck and pika threading patterns are well-documented and the solution is explicit in STACK.md/PITFALLS.md.

### Phase 2: Atomic Foundation Services

**Rationale:** Event, Booking, and Seat are pure data services with no upstream HTTP dependencies. They must exist before the Orchestrator can call them. Seat Service with Redis locking is on the critical path for Scenario 1. These three can be built in parallel within the team.

**Delivers:** Event Service CRUD (port 5001), Booking Service record management (5002), Seat Service with Redis two-phase locking (5003). All three have working HTTP endpoints, databases, and AMQP publishing stubs.

**Addresses:** Event browsing, seat availability, booking records, seat locking (Redis distributed lock).

**Avoids:** Pitfall 2 (Redis lock TTL and Lua release script — must be correct here, not as a fix later).

**Research flag:** No deeper research needed — Redis locking pattern is explicit in ARCHITECTURE.md and PITFALLS.md with code examples.

### Phase 3: Scenario 1 — Booking Saga (Orchestration)

**Rationale:** Payment Service and Booking Orchestrator can only be built after Phase 2 services are testable via HTTP. This phase delivers the end-to-end happy path for Scenario 1 plus all compensation paths. It is the most complex phase and must be treated as a block of work.

**Delivers:** Payment Service with Stripe (5004), Booking Orchestrator with saga + APScheduler expiry (5010), Ticket Service with QR generation + Flask-SocketIO rooms (5006). End-to-end Scenario 1: seat selection → payment → e-ticket delivery via WebSocket.

**Addresses:** Seat hold with timeout, payment processing, compensating transactions, payment expiry handling, QR e-ticket + real-time WebSocket delivery.

**Avoids:** Pitfall 3 (non-idempotent compensations — use `locked_by_booking_id` guards and `correlation_id`), Pitfall 4 (eventlet — use `async_mode='threading'`), Pitfall 6 (APScheduler duplicate jobs — use `use_reloader=False`), Pitfall 11 (Stripe webhook handling).

**Research flag:** Stripe webhook signature verification and test-mode PaymentIntent behavior may need validation during implementation (MEDIUM confidence in Pitfall 11).

### Phase 4: Scenario 2 — Waitlist Choreography

**Rationale:** Waitlist Service depends on `seat.released` events from Seat Service (Phase 2) and Notification Service for promotion alerts. It cannot be fully tested until both are available. The cascading promotion loop is architecturally the most delicate component.

**Delivers:** Waitlist Service (5007) with join, automatic promotion, cascade on expiry, Redis TTL for promotion window. Notification Service (5005) with Gmail SMTP + Twilio SMS, consuming from 4 exchanges. End-to-end Scenario 2: sold-out event → join waitlist → seat releases → promotion → notification.

**Addresses:** Waitlist join, automatic promotion, cascading promotions, waitlist position visibility, notification on promotion.

**Avoids:** Pitfall 13 (cascading promotion race condition — sequential processing with `prefetch_count=1`, per-seat Redis lock during promotion).

**Research flag:** No deeper research needed — choreography loop pattern is fully specified in ARCHITECTURE.md. The self-referencing cascade is unusual but the mitigation (empty-waitlist guard before re-publishing) is clear.

### Phase 5: Scenario 3 — Event Cancellation Fan-out

**Rationale:** Charging Service (Scenario 3) depends on Payment Service (Phase 3) for refund execution and all five fan-out consumers must be built. This phase cannot start until Phases 2-4 services exist, since the fan-out must reach them.

**Delivers:** Charging Service (5008) with 10% fee calculation and batch refund triggering via `refund_direct` exchange. Topic exchange `event_lifecycle` wiring to Booking Service, Seat Service, Waitlist Service, Notification Service, and Charging Service. End-to-end Scenario 3: admin cancels event → fan-out → 90% refunds processed → users notified.

**Addresses:** Event cancellation, batch refund processing, 10% service fee retention, booking status update on cancel, waitlist clearing on cancel, cancellation notifications.

**Avoids:** Pitfall 12 (missing fan-out bindings — declare durable queues in each consumer before testing, ensure all 5 consumers are running before the first cancellation test).

**Research flag:** No deeper research needed — topic exchange fan-out is standard RabbitMQ. The only risk is operational (all consumers up at test time), not architectural.

### Phase 6: Integration, Gateway, and Frontend

**Rationale:** Kong routing and the React frontend are the integration layer. They require all backend services to be working and their ports to be known. CORS must be handled at Kong (not in Flask services) to avoid conflicting headers.

**Delivers:** Kong declarative YAML with all routes, rate limiting on booking endpoints, CORS plugin (handle here only). React frontend: event listing, seat selection, booking flow, WebSocket e-ticket display. OutSystems admin dashboard integration with Event Service. End-to-end testing of all 3 scenarios through the full stack.

**Addresses:** API Gateway, admin dashboard (OutSystems), interactive seat map UI, all frontend flows.

**Avoids:** Pitfall 9 (Kong silent config failures — validate with `kong config parse`, test every route individually), Pitfall 10 (CORS conflicts — Kong plugin only, remove Flask-CORS from services), WebSocket bypass (route SocketIO directly to Ticket Service, not through Kong proxy for WS).

**Research flag:** OutSystems REST connector integration with Event Service may need validation — OutSystems domain CORS handling is flagged as a gotcha in PITFALLS.md.

### Phase Ordering Rationale

- **Layers are hard dependencies, not preferences.** You cannot test Booking Orchestrator without Seat + Payment + Booking all reachable via HTTP. You cannot test Waitlist choreography without `seat.released` being published from a working Seat Service.
- **The shared AMQP library must be written once and correctly.** 7 of 9 services import it. Fixing pika thread safety in 7 places after the fact is much worse than getting it right in Phase 1.
- **Scenarios 2 and 3 require Notification Service**, which is a Phase 4 dependency. Building it during Phase 4 (not Phase 3) is deliberate — it can be tested in isolation once booking events exist from Phase 3.
- **Kong and the frontend are integration, not foundation.** Attempting to add Kong routing before backend services are stable wastes time debugging whether the problem is in the service or the gateway.

### Research Flags

Phases needing deeper validation during implementation:
- **Phase 3 (Booking Saga):** Stripe webhook test-mode behavior needs hands-on validation. Use `stripe listen --forward-to` CLI during development. Idempotency key design for double-charge prevention.
- **Phase 6 (OutSystems):** OutSystems REST connector CORS and non-200 response handling is a known gotcha. Validate early with a stub endpoint before building full integration.

Phases with standard patterns (can proceed without additional research):
- **Phase 1 (Infrastructure):** Docker healthcheck and pika threading patterns are fully specified.
- **Phase 2 (Foundation Services):** Redis SET NX EX + Lua release script is documented with code examples.
- **Phase 4 (Waitlist):** Choreography loop pattern is fully specified in ARCHITECTURE.md.
- **Phase 5 (Cancellation):** Topic exchange fan-out is standard RabbitMQ.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core stack is mandated; library versions verified against official PyPI, GitHub, and compatibility matrices. pika 1.3.2 constraint verified against upstream changelog. |
| Features | HIGH | All three scenarios are explicitly defined by the course. Feature prioritization cross-referenced against industry platforms. Anti-features are clearly scoped. |
| Architecture | HIGH | Architecture is professor-mandated with explicit constraints (no HTTP between Seat and Waitlist, Notification is fire-and-forget, single composite service). Patterns are well-established (saga, choreography, topic exchange). |
| Pitfalls | HIGH | 5 critical pitfalls all verified against official documentation (pika FAQ, Redis docs, Microsoft Saga pattern, Flask-SocketIO maintainer, Docker Compose docs). 2 moderate pitfalls rated MEDIUM (Stripe webhooks, cascading race condition) due to implementation-specific reasoning. |

**Overall confidence:** HIGH

### Gaps to Address

- **Stripe webhook integration in test mode:** The exact sequence for testing payment failure scenarios (PaymentIntent expiry, webhook ordering) requires hands-on Stripe CLI testing during Phase 3. Reference PITFALLS.md Pitfall 11 and use `stripe trigger` commands.
- **OutSystems REST connector behavior:** How OutSystems handles non-200 HTTP responses and CORS from a local Docker service is not well-documented. Validate with a stub endpoint at the start of Phase 6.
- **Redis eviction under memory pressure:** If the Docker host runs low on memory, Redis may evict seat lock keys. This is not a risk for a university demo environment but should be noted if the environment is shared. Set `maxmemory-policy noeviction` in the Redis Docker config to be safe.
- **Kong WebSocket proxying:** WebSocket upgrade requests require explicit Kong upstream configuration. The recommended approach (bypass Kong for SocketIO) sidesteps this entirely — confirm the React frontend connects directly to Ticket Service for WebSocket, and through Kong for all REST calls.

## Sources

### Primary (HIGH confidence)
- Flask PyPI (3.1.2) — Python >=3.9 requirement, version compatibility
- pika PyPI (1.3.2 vs 1.4.0 breaking changes) — Python 3.12+ requirement in 1.4.0
- redis-py PyPI (5.x server compatibility matrix) — Redis 5.0-7.4 support window
- Flask-SocketIO PyPI + maintainer discussion — eventlet deprecation, threading mode recommendation
- Redis distributed locks official documentation — SET NX EX atomic, Lua release script
- Microsoft Saga Pattern docs — compensating transaction idempotency
- microservices.io Saga Pattern — orchestration vs choreography
- Docker Compose startup order docs — `condition: service_healthy` requirement
- RabbitMQ Consumer Acknowledgements docs — ack/nack patterns, DLX
- Flask-SQLAlchemy config docs — pool_recycle, pool_pre_ping
- Kong DB-less mode docs — declarative YAML, DB-less limitations
- APScheduler FAQ — duplicate job execution with Flask reloader
- Stripe webhook documentation — signature verification, idempotency
- Existing codebase analysis (`.planning/codebase/`) — professor constraints as primary source

### Secondary (MEDIUM confidence)
- Flask-SocketIO monkey patching GitHub discussion — eventlet + pika deadlock specifics
- Flask-CORS GitHub issues — CORS duplicate header behavior with Kong
- Softjourn / Bizzabo / Design Gurus ticketing platform analyses — feature expectations
- Hello Interview Ticketmaster system design — concurrency patterns
- APScheduler Flask-APScheduler tips — duplicate scheduler mitigation

### Tertiary (LOW confidence — implementation-specific, needs validation)
- Cascading waitlist race condition analysis — architecture-specific reasoning, not found in documentation
- OutSystems REST connector CORS behavior — based on integration gotcha table, not primary source

---
*Research completed: 2026-03-13*
*Ready for roadmap: yes*
