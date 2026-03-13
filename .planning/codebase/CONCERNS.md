# Codebase Concerns

**Analysis Date:** 2026-03-13

## Tech Debt

**Multi-threading Complexity in Services:**
- Issue: Services requiring both HTTP (Flask) and AMQP consumers must use daemon threads, creating potential race conditions and debugging complexity
- Files: `services/seat/app.py`, `services/waitlist/app.py`, `services/ticket/app.py`, `services/notification/app.py`
- Impact: Deadlocks possible between Flask request handler and AMQP consumer thread; graceful shutdown is non-trivial; thread safety of shared resources (database connections, Redis) must be manually enforced
- Fix approach: Implement proper thread-safe connection pooling; add explicit shutdown handlers; use queue-based communication between threads; consider moving to async/await pattern with asyncio instead of threading

**Payment Expiry Logic Coupling:**
- Issue: APScheduler running inside Booking Orchestrator checks every 30 seconds for expired payments; this creates centralized state that's hard to scale horizontally
- Files: `services/booking_orchestrator/app.py`
- Impact: If orchestrator crashes, no timeouts are processed until restart; if team scales to multiple orchestrator instances, duplicate timeout processing will occur; 30-second granularity means users may wait up to 30s before timeout notification
- Fix approach: Move payment timeout to event-driven architecture (time-based event from message queue); implement distributed locking with Redis if multi-instance needed; reduce polling interval or use message-based scheduling

**Service Fee Calculation Decentralization:**
- Issue: Charging Service calculates service fees and publishes adjusted amounts, but Payment Service must handle both scenarios: full refund (non-cancelled) and partial refund (cancelled with fee)
- Files: `services/charging/app.py`, `services/payment/app.py`
- Impact: Inconsistent fee calculations if Charging Service and Payment Service logic diverge; no single source of truth for fee structure; future changes require coordinated updates across two services
- Fix approach: Create a shared fee calculation library or API; implement feature flags for fee percentages; add comprehensive integration tests

## Known Bugs

**Payment Retry with Dead-Letter Queue Uncertainty:**
- Symptoms: Failed Stripe refunds are NACK'd with `requeue=True` up to 3 attempts, but no explicit dead-letter queue behavior is defined
- Files: `services/payment/app.py` (refund processing logic in AMQP consumer)
- Trigger: Stripe API returns 5xx error or network timeout during refund processing
- Workaround: Manually check `payments` table for `status='failed'` and retry; check RabbitMQ queue for stuck messages
- Risk: Messages may be lost, retried infinitely, or silently dropped; customers not notified of refund failure

**Seat Release Race Condition on Timeout:**
- Symptoms: When Booking Orchestrator timeout fires, it releases a seat via `PUT /seats/{seat_id}/release`, but Waitlist Service may simultaneously promote a user and try to reserve the same seat
- Files: `services/booking_orchestrator/app.py`, `services/seat/app.py`, `services/waitlist/app.py`
- Trigger: Timeout expires at exact moment a promoted waitlist user attempts reservation
- Workaround: Increase Redis TTL to reduce window; add manual seat cleanup jobs
- Risk: Seat may end up in inconsistent state (reserved in MySQL but lock expired in Redis) or double-booked

**WebSocket Connection Loss During Ticket Generation:**
- Symptoms: If UI disconnects between booking.confirmed event and Ticket Service WebSocket emit, e-ticket is generated but never delivered
- Files: `services/ticket/app.py`, `services/booking_orchestrator/app.py`
- Trigger: Network interruption or client-side crash after payment succeeded but before e-ticket received
- Workaround: Frontend polls for ticket availability; implement ticket storage endpoint
- Risk: User completes payment but never receives e-ticket; confusion over whether booking succeeded

## Security Considerations

**Environment Variable Exposure in Logs:**
- Risk: Database credentials, Stripe keys, Twilio tokens stored in `.env` could be logged if services log environment on startup
- Files: All services (config loading in `app.py`)
- Current mitigation: `.env` file should not be committed (in `.gitignore`); no explicit mention of scrubbing logs
- Recommendations:
  - Never log `os.environ` directly
  - Add sanitization layer to remove known secret patterns from logs
  - Use structured logging with explicit field allowlist
  - Implement secret rotation mechanism for long-lived keys

**No API Authentication Between Services:**
- Risk: Services communicate via HTTP without mTLS or shared secrets; Kong gateway only secures client → gateway, not gateway → services
- Files: All service-to-service HTTP calls in `services/booking_orchestrator/app.py`
- Current mitigation: Services run on internal Docker network; no external exposure
- Recommendations:
  - Implement service-to-service authentication (OAuth2 client credentials or mTLS)
  - Add request signing (HMAC-SHA256)
  - Use Kong consumer authentication with internal service principals
  - Add audit logging for inter-service calls

**Stripe Webhook Signature Validation Missing:**
- Risk: Payment Service may accept webhooks without validating Stripe signature
- Files: `services/payment/app.py` (if webhook endpoint exists)
- Current mitigation: Design document does not mention webhook validation
- Recommendations:
  - Always validate `Stripe-Signature` header using Stripe's public key
  - Reject unsigned webhooks immediately
  - Implement idempotency key tracking to prevent duplicate processing

**MySQL `CREATE TABLE IF NOT EXISTS` at Startup:**
- Risk: Every service creates tables on startup without validation; missing table corruption checks; no schema versioning
- Files: All services (database initialization in `app.py`)
- Current mitigation: None documented
- Recommendations:
  - Implement schema migration tool (Alembic for Python)
  - Add pre-flight checks for table integrity
  - Version schema and track migration history
  - Test rollback procedures

## Performance Bottlenecks

**Redis Lock Expiry for Seat Reservation:**
- Problem: Seats locked with 10-minute TTL via Redis; if payment takes > 10 minutes (slow Stripe API), lock expires and seat becomes double-bookable
- Files: `services/seat/app.py` (PUT /seats/{seat_id}/reserve endpoint)
- Cause: Fixed TTL doesn't account for payment processing time variance
- Improvement path:
  - Make TTL configurable and extend based on payment progress
  - Implement lock renewal mechanism: Booking Orchestrator extends TTL every 2 minutes during payment
  - Add watchdog: if payment takes > 15 minutes, auto-release and notify user
  - Consider using distributed lease system (Chubby-style) instead of simple TTL

**APScheduler 30-Second Polling:**
- Problem: Every 30 seconds, entire `bookings` table scanned for expired payments; scales poorly with millions of bookings
- Files: `services/booking_orchestrator/app.py`
- Cause: Polling approach instead of event-driven; no indexing strategy mentioned
- Improvement path:
  - Add database index on `created_at` and `status` columns
  - Implement binary search to find expired records
  - Consider time-series database for bookings with TTL
  - Batch expired records (e.g., process 100 at a time) to avoid locking entire table
  - Move to event-driven: publish `booking.reserved` event with TTL; consumer fires timeout event after delay

**AMQP Message Fanout Blocking Scenario 3:**
- Problem: When event is cancelled, `event.cancelled.*` fans out to 5 services (Charging, Payment, Booking, Seat, Waitlist, Notification) — if one service is slow, entire cascade delays
- Files: `services/event/app.py` (publishes to event_lifecycle exchange)
- Cause: Topic exchange fans to multiple queues; no backpressure mechanism; if Payment Service is slow, Notification won't send until Payment finishes (if synchronously awaited)
- Improvement path:
  - Ensure each consumer is truly independent (no orchestration of fanout)
  - Add message deduplication and idempotency keys
  - Implement priority queues for time-sensitive messages (SMS notifications)
  - Monitor queue depth and add alerts when backlogs form

**Seat Availability Query Without Pagination:**
- Problem: `GET /seats/<event_id>` returns ALL seats for an event; for large events (10k+ seats), response is massive and blocks UI
- Files: `services/seat/app.py` (GET endpoint)
- Cause: No pagination, filtering, or caching strategy mentioned
- Improvement path:
  - Add pagination (limit/offset or cursor-based)
  - Cache seat availability in Redis (10-second TTL)
  - Return only `available` seats, not full details
  - Add query parameters: `?section=A&status=available&limit=100`

## Fragile Areas

**Waitlist Promotion Cascading Without Idempotency:**
- Files: `services/waitlist/app.py`
- Why fragile: When seat.released event fires, Waitlist Service promotes user N, publishes `waitlist.promoted`, which triggers Notification Service to send SMS, which may trigger user to book. But if user N's booking fails (payment error), seat is released again, potentially triggering another promotion. No idempotency keys mean duplicate promotions/notifications.
- Safe modification:
  - Add unique idempotency keys to all AMQP messages
  - Track promotion ID in database to deduplicate
  - Add comprehensive integration test covering promotion failure + retry scenario
- Test coverage: Likely missing tests for double-promotion and cascading failures

**Saga State Machine Without Rollback Verification:**
- Files: `services/booking_orchestrator/app.py` (saga state tracking)
- Why fragile: Orchestrator transitions saga state (SEAT_RESERVED → PAYMENT_SUCCESS → BOOKING_CONFIRMED) but doesn't verify compensating transactions succeeded. If seat release fails silently, saga shows success but seat remains locked.
- Safe modification:
  - Add explicit rollback verification: after calling release endpoint, poll seat status to confirm
  - Implement saga compensation with retry logic
  - Log all state transitions with timestamps
  - Add dead-letter handling for failed compensations
- Test coverage: Need tests for failed compensations and partial rollbacks

**SocketIO Room Management Without Cleanup:**
- Files: `services/ticket/app.py` (join_room by booking_id)
- Why fragile: Clients join room by booking_id and receive e-ticket via `emit(f"ticket:{booking_id}")`, but no explicit room leave or cleanup. If client crashes, room persists; if booking_id is reused (soft-deleted bookings), old connections may receive new bookings' tickets.
- Safe modification:
  - Implement `@socketio.on('disconnect')` handler to track and clean up rooms
  - Use unique session tokens instead of just booking_id
  - Add room expiry: auto-close rooms after 1 hour
  - Log all room join/leave events for debugging
- Test coverage: Need E2E tests for disconnect scenarios and room isolation

**Charging Service Single Point of Truth for Fees:**
- Files: `services/charging/app.py`
- Why fragile: Charging Service publishes `refund.adjusted` with calculated service fee; if Charging Service is down when refunds process, refund amounts are undefined. Payment Service has no fallback fee calculation.
- Safe modification:
  - Add fallback fee calculation to Payment Service using configuration
  - Store service fee tier in Payment Service database at booking time
  - Add feature flag to skip Charging Service if unavailable (full refund fallback)
  - Implement compensation: if refund amount is 0 or negative (due to fee > refund), reject and alert admin
- Test coverage: Need tests for Charging Service failure paths

## Scaling Limits

**Single RabbitMQ Instance:**
- Current capacity: Single RabbitMQ container in docker-compose; no clustering or replication
- Limit: One failing queue blocks all downstream services; no failover; message persistence relies on single disk
- Scaling path:
  - Implement RabbitMQ clustering (3-node minimum for HA)
  - Add disk persistence configuration
  - Implement message acknowledgment tracking
  - Monitor queue depth and add backpressure monitoring

**Single MySQL Instance with No Replication:**
- Current capacity: Single MySQL container; no read replicas or backup strategy
- Limit: Single point of failure; no horizontal scaling for reads; 10+ concurrent seat reservations may cause lock contention
- Scaling path:
  - Implement MySQL replication (master-slave for reads)
  - Add connection pooling (max connections per service)
  - Consider sharding by event_id for seat service
  - Implement backup/restore procedures (daily snapshots)

**Redis as Bottleneck for Seat Locking:**
- Current capacity: Single Redis instance; all 8 services may write seat locks
- Limit: Network saturation during high-traffic events; no Redis persistence configured; crash loses all locks
- Scaling path:
  - Add Redis replication and Sentinel for failover
  - Implement connection pooling at application level
  - Consider Redis Cluster for horizontal scaling
  - Add RDB/AOF persistence

**Booking Orchestrator Cannot Horizontally Scale:**
- Current capacity: Single orchestrator instance with APScheduler
- Limit: Payment timeout processing is centralized; if scaled to N instances, duplicates process same timeout unless distributed locking added
- Scaling path:
  - Implement Redis-backed distributed lock for timeout processing
  - Use leader election (Consul, etcd) if available
  - Move timeout to time-series queue (Kafka, AWS SQS with delays)
  - Add graceful handoff when orchestrator instances start/stop

## Dependencies at Risk

**Flask-SocketIO with Eventlet Compatibility:**
- Risk: `eventlet.monkey_patch()` required before imports; incompatible with some libraries; eventlet is not actively maintained
- Impact: Upgrading dependencies may break SocketIO; WebSocket connection stability issues
- Migration plan: Migrate to FastAPI with WebSocket support or use `gevent` instead of `eventlet`; add integration tests for WebSocket reconnection

**Stripe API Rate Limiting:**
- Risk: Stripe enforces rate limits (100 requests/second); batch refunds may hit limit during event cancellation scenario
- Impact: Refund processing delayed; customers wait for refund notifications; transient failures cascade
- Migration plan: Implement exponential backoff + jitter; queue refund requests with priority; add Stripe webhook for refund status updates

**Twilio SMS Delivery Uncertainty:**
- Risk: Twilio may reject SMS (invalid phone numbers, regulatory blocks); delivery status not guaranteed
- Impact: Waitlist promotion SMS may not reach users; they miss time-limited seat offers
- Migration plan: Implement SMS delivery receipt tracking; fall back to email; add dashboard showing SMS delivery rates

**OutSystems Integration Point:**
- Risk: OutSystems exposes 1 atomic service for event management; if OutSystems is down, new events cannot be created
- Impact: Event creation blocked; whole platform unusable
- Migration plan: Implement Event Service as Python service independent of OutSystems; use OutSystems for admin UI only; add fallback admin interface

## Missing Critical Features

**No Distributed Tracing:**
- Problem: Multi-service architecture with no correlation IDs or tracing; debugging payment failures across 4 services is manual log searching
- Blocks: Diagnosing production issues; understanding request flow
- Recommendation: Add OpenTelemetry instrumentation; use Jaeger or Datadog for tracing

**No Rate Limiting at Kong Gateway:**
- Problem: No per-user or per-IP rate limiting defined; single user can spam seat reservation endpoint
- Blocks: DDoS protection; fair access during high-traffic events
- Recommendation: Add Kong rate-limit plugin; implement token bucket per user; add captcha for suspicious traffic

**No Seat Auto-Release on Booking Cancellation:**
- Problem: If user cancels booking after seat reservation but before payment, seat remains locked for 10 minutes
- Blocks: User can't immediately book different seat; wasted inventory
- Recommendation: Implement cancellation endpoint that calls seat.release; allow user to cancel within payment window

**No Event Pagination/Filtering:**
- Problem: No API design for event browsing mentioned; likely returns all events without pagination
- Blocks: Platform scales to 1000+ events; UI loads gigabytes of data
- Recommendation: Implement `/events?page=1&limit=20&status=active`; add search by name/date; cache frequently-viewed events

**No Webhook Retry Strategy:**
- Problem: Notification Service may send webhook to external systems (if needed); no retry logic if external service is down
- Blocks: Event creators' downstream systems unreliable
- Recommendation: Implement exponential backoff; store failed webhooks in table; add manual retry endpoint

## Test Coverage Gaps

**No Seat Double-Booking Tests:**
- What's not tested: Race condition where two users simultaneously attempt to reserve same seat
- Files: `services/seat/app.py` (PUT /seats/{seat_id}/reserve), `services/booking_orchestrator/app.py`
- Risk: Seat may be booked to both users; revenue loss or customer dispute
- Priority: High — affects core business logic

**No Payment Timeout Compensation Tests:**
- What's not tested: When payment times out, verify seat is released AND user is notified AND saga state is consistent
- Files: `services/booking_orchestrator/app.py`, `services/seat/app.py`, `services/notification/app.py`
- Risk: Orphaned seat locks or missing notifications
- Priority: High — affects payment flow

**No Waitlist Promotion Idempotency Tests:**
- What's not tested: If promotion event is redelivered (AMQP requeue), user not double-promoted and not sent duplicate SMS
- Files: `services/waitlist/app.py`, `services/notification/app.py`
- Risk: Duplicate charges or confused users
- Priority: High — affects fairness of waitlist

**No Event Cancellation Cascade Tests:**
- What's not tested: When event is cancelled, all 5 downstream services (Charging, Payment, Booking, Seat, Waitlist) receive message and reach consistent state
- Files: `services/event/app.py`, and all consumer services
- Risk: Partial state updates (some refunded, some not); customer support headache
- Priority: High — affects Scenario 3

**No SocketIO Reconnection Tests:**
- What's not tested: Client disconnects during e-ticket generation and reconnects; ticket still delivered
- Files: `services/ticket/app.py`
- Risk: Users don't receive e-tickets due to network flakiness
- Priority: Medium — affects UX but not business logic

**No Database Connection Pool Exhaustion Tests:**
- What's not tested: What happens when all MySQL connections exhausted (simulate 20 concurrent requests)
- Files: All services (database connection handling)
- Risk: Services crash or hang indefinitely under load
- Priority: Medium — affects production stability

---

*Concerns audit: 2026-03-13*
