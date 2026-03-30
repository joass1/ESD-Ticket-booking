# OutSystems Migration Guide: Event Service

This document lists every issue found when replacing the Python Event microservice with an OutSystems-exposed REST API, and the fixes applied or still needed.

---

## Status Legend

- **FIXED** = Already patched in the codebase
- **NEEDS OUTSYSTEMS FIX** = Must be fixed inside OutSystems Service Studio
- **NEEDS CODE** = Requires new code to be written (Python or frontend)

---

## Architecture Overview After Migration

```
                         +--------------------------+
                         |      Frontend (React)    |
                         +-----------+--------------+
                                     |
                                     v
                         +-----------+--------------+
                         |     Kong API Gateway     |
                         +-----------+--------------+
                                     |
               +---------------------+---------------------+
               |                     |                     |
               v                     v                     v
  +------------+--------+  +--------+--------+  +---------+---------+
  | OutSystems Event    |  | Booking         |  | Other Atomic      |
  | Service (External)  |  | Orchestrator    |  | Services          |
  | - GET /events       |  | (Composite)     |  | (Seat, Payment,   |
  | - GET /events/:id   |  | - /bookings/*   |  |  Ticket, etc.)    |
  | - POST /events      |  | - /events/cancel|  |                   |
  | - PUT /events/:id   |  |                 |  |                   |
  | - POST /cancel      |  |                 |  |                   |
  +---------------------+  +--------+--------+  +-------------------+
                                     |
                                     v
                           +---------+---------+
                           |     RabbitMQ      |
                           | event_lifecycle   |
                           | booking_topic     |
                           | seat_topic        |
                           +-------------------+
                                     |
               +----------+----------+----------+-----------+
               v          v          v          v           v
           Booking     Seat      Ticket    Waitlist   Notification
           Service    Service   Service    Service     Service
```

**Key Design Rule (from CLAUDE.md):**
> Atomic microservices must NEVER call other atomic services directly via HTTP. Only composite microservices (e.g., Booking Orchestrator) may call atomic services. Atomic services communicate with each other exclusively through AMQP messaging.

The Booking Orchestrator (composite) is the **bridge** between OutSystems (HTTP-only, no AMQP) and the RabbitMQ messaging layer. This does not violate the architecture rule.

---

## Issues Already Fixed in Codebase

### 1. CORS / 301 Redirect on Kong Proxy (FIXED)

**Problem:** Kong proxied `GET /api/events` to the OutSystems URL without a trailing slash. OutSystems responded with a `301 Moved Permanently` redirect (adding a trailing slash). Kong passed this redirect back to the browser, which then tried to follow it directly to `outsystemscloud.com` — failing on CORS because OutSystems does not allow the `X-Correlation-ID` header.

**Fix Applied:** Added trailing slash to `kong/kong.yml` line 6:

```yaml
# Before
url: https://personal-fptjqc79.outsystemscloud.com/ESDTicketBookingServices/rest/EventService

# After
url: https://personal-fptjqc79.outsystemscloud.com/ESDTicketBookingServices/rest/EventService/
```

### 2. Booking Orchestrator Had Placeholder EVENT_SERVICE_URL (FIXED)

**Fix Applied** in `docker-compose.yml`:

```yaml
# Before
EVENT_SERVICE_URL: https://your-env.outsystemsenterprise.com/TB_EventService/rest/EventService

# After
EVENT_SERVICE_URL: https://personal-fptjqc79.outsystemscloud.com/ESDTicketBookingServices/rest/EventService/
```

### 3. PascalCase vs snake_case Field Names (FIXED)

**Fix Applied** in `frontend/src/api/client.js` (normalizeEvent function) and `services/booking_orchestrator/app.py` (dual-key lookups for `Status`/`status` and `EventDate`/`event_date`).

### 4. Missing .env Variables for Notification Service (FIXED)

**Fix Applied** — added `SMU_NOTI_BASE_URL` and `SMU_NOTI_API_KEY` to `.env`.

### 5. npm / eslint Peer Dependency Conflict (FIXED)

**Fix Applied** — downgraded `eslint` from `^10.1.0` to `^9.39.4` in `frontend/package.json`.

---

## Issues That Need OutSystems Fixes

### 6. GetEvents Endpoint Returns `{}` (NEEDS OUTSYSTEMS FIX)

**Problem:** Calling `GET /events` returns an empty object `{}` instead of `{ "code": 200, "data": [...] }`.

**Impact:** The Events page shows "No events found".

**Expected Response Format:**

```json
{
  "code": 200,
  "data": [
    {
      "Id": 1,
      "Name": "Taylor Swift Eras Tour SG",
      "Description": "The Eras Tour live in Singapore",
      "Category": "Concert",
      "EventDate": "2026-06-15T19:00:00Z",
      "Venue": "National Stadium",
      "Status": "upcoming",
      "TotalSeats": 500,
      "AvailableSeats": 500,
      "PriceMin": 88.00,
      "PriceMax": 348.00,
      "ImageUrl": "https://example.com/image.jpg",
      "CreatedAt": "2026-03-26T18:36:24Z",
      "UpdatedAt": "2026-03-26T18:36:24Z"
    }
  ]
}
```

#### Step-by-Step Fix in Service Studio

**Step 1:** Open your application in Service Studio.

**Step 2:** Navigate to **Logic** tab > **Integrations** > **REST** > **EventService**.

**Step 3:** Find and double-click the **GetEvents** method to open its server action flow.

**Step 4:** You should see a flow that looks something like:

```
Start → [Aggregate / SQL Query] → ... → End
```

**Step 5:** Check your **Aggregate** (the database query node). Click on it and verify:
- **Source:** It should be your `Event` entity
- **Filters:** Check what filters are applied

**Step 6 — Fix Filters:** If you have filters, they are likely the problem. Open the Aggregate and go to the **Filters** tab. You probably have something like:

```
Event.Status = GetEvents.Status
```

This means if the `Status` input parameter is `""` (empty, which is the default), it tries to find events where `Status = ""`. Since no events have an empty status (or they shouldn't), it returns nothing.

**Change the filter to be conditional:**

```
(GetEvents.Status = "" or Event.Status = GetEvents.Status)
and
(GetEvents.Category = "" or Event.Category = GetEvents.Category)
```

This way:
- When `Status` is empty → no filter applied → returns all events
- When `Status = "upcoming"` → only returns upcoming events

**Step 7 — Fix Output Assignment:** After the Aggregate, there must be an **Assign** node that maps the query results to the output. If it's missing, that's why you get `{}`.

Click on the flow line **between the Aggregate and the End node** and add an **Assign** node.

Set the assignments:

| Variable | Value |
|---|---|
| `Output.code` | `200` |
| `Output.data` | `GetEventsAggregate.List` |

(Replace `GetEventsAggregate` with whatever your Aggregate is actually named — you can see the name when you click on it.)

**Step 8:** Your final flow should look like:

```
Start → GetEventsAggregate → Assign → End
```

Where the Assign sets:
- `Output.code = 200`
- `Output.data = GetEventsAggregate.List`

**Step 9:** Click **1-Click Publish** (F5 or the green play button).

**Step 10:** Verify by opening a terminal and running:

```bash
curl -s https://personal-fptjqc79.outsystemscloud.com/ESDTicketBookingServices/rest/EventService/events | python3 -m json.tool
```

You should see the JSON response with `code: 200` and `data` as an array of events.

#### Troubleshooting

- **Still getting `{}`?** Check that the Assign node is actually connected in the flow. Sometimes nodes can be disconnected visually. Make sure there's an arrow from the Aggregate to the Assign, and from the Assign to the End.
- **Getting `{ "code": 200, "data": [] }`?** The query works but no events match. Check the Status fix in issue 7 below — your events may have empty Status values.
- **Getting an error?** Check that the Aggregate's output type matches the `data` field type. The `data` field should be a List of `Event` records.

---

### 7. Event Status Field Is Empty (NEEDS OUTSYSTEMS FIX)

**Problem:** Event ID 1 returns `"Status": ""`. The booking orchestrator rejects any event where status is not `upcoming` or `ongoing`:

```
"Event is not available for booking (status: )"
```

**Impact:** All booking attempts fail. The EventCard status badge shows blank.

#### Step-by-Step Fix in Service Studio

##### Part A — Set Default Value for New Records

**Step 1:** In Service Studio, go to the **Data** tab.

**Step 2:** Expand **Entities** > **Database** and find your **Event** entity.

**Step 3:** Click on the **Status** attribute.

**Step 4:** In the properties panel on the right, find **Default Value** and set it to:

```
"upcoming"
```

**Step 5:** This ensures any new event created without a Status will default to `"upcoming"`.

##### Part B — Fix the CreateEvent Endpoint

**Step 1:** Go to **Logic** > **Integrations** > **REST** > **EventService** > **CreateEvent**.

**Step 2:** Open the server action flow.

**Step 3:** Find where the Event record is created (there should be a **CreateEvent** entity action or an Assign that sets the fields before inserting).

**Step 4:** Add logic to handle the case when `status` is empty in the request body. Before the database insert, add an **If** node:

```
Condition: Request.status = ""
True branch:  Assign → EventRecord.Status = "upcoming"
False branch: Assign → EventRecord.Status = Request.status
```

Or simpler — in the Assign where you map request fields to the entity, use:

```
EventRecord.Status = If(Request.status = "", "upcoming", Request.status)
```

**Step 5:** 1-Click Publish.

##### Part C — Fix Existing Records

**Step 1:** Go to `https://personal-fptjqc79.outsystemscloud.com/ServiceCenter/` (your OutSystems Service Center).

**Step 2:** Log in with your OutSystems credentials.

**Step 3:** Go to **Factory** > **Modules** > find your module (e.g., `ESDTicketBookingServices`).

**Step 4:** Click on the module, then go to the **Entity** section and find the **Event** entity.

**Step 5:** Click **View Data** to see all records.

**Step 6:** For each event that has an empty Status, edit the record and set Status to `upcoming`.

**Alternative — Fix via API call:**

```bash
curl -X PUT "https://personal-fptjqc79.outsystemscloud.com/ESDTicketBookingServices/rest/EventService/events/1" \
  -H "Content-Type: application/json" \
  -d '{"status": "upcoming"}'
```

Run this for each event ID that has an empty status.

**Step 7:** Verify:

```bash
curl -s https://personal-fptjqc79.outsystemscloud.com/ESDTicketBookingServices/rest/EventService/events/1 | python3 -m json.tool
```

Should show `"Status": "upcoming"`.

---

## Issues That Need Code Changes

### 8. CancelEvent Does Not Publish to RabbitMQ (FIXED)

**Problem:** The old Python event service published `event.cancelled.{event_id}` to the `event_lifecycle` RabbitMQ exchange when cancelled. Five services depend on this:

| Service | Queue | What It Does When It Receives `event.cancelled.*` |
|---|---|---|
| **Booking** | `booking_cancel_queue` | Finds all `confirmed` bookings for that event, marks them `pending_refund`, publishes `booking.refund.requested` for each |
| **Seat** | `seat_cancel_queue` | Releases all `booked` and `reserved` seats back to `available` |
| **Ticket** | `ticket_cancel_queue` | Invalidates all tickets (sets status to `invalidated`) |
| **Waitlist** | `waitlist_cancel_queue` | Cancels all waitlist entries for that event |
| **Notification** | `notification_lifecycle_queue` | Sends cancellation email to all affected users |

OutSystems **cannot** publish to RabbitMQ. Without this, cancelling an event only changes the status in OutSystems — no refunds, no seat releases, no emails.

#### Complete Flow After Fix

```
Admin clicks "Cancel Event" on EventDetailPage
        |
        v
Frontend: POST /api/orchestrator/events/{id}/cancel
        |
        v
Kong routes to Booking Orchestrator
        |
        v
Orchestrator Step 1: GET OutSystems /events/{id}
  - Verify event exists
  - Verify status is 'upcoming' or 'ongoing' (can be cancelled)
        |
        v
Orchestrator Step 2: POST OutSystems /events/{id}/cancel
  - OutSystems updates Status to 'cancelled' in its DB
  - Returns { code: 200, data: { ... Status: "cancelled" } }
        |
        v
Orchestrator Step 3: Publish AMQP message
  - Exchange: event_lifecycle (topic)
  - Routing key: event.cancelled.{event_id}
  - Payload: { "event_id": 1, "event_name": "Taylor Swift Eras Tour SG" }
        |
        v
RabbitMQ fans out to 5 queues:
        |
        +---> booking_cancel_queue ---> Booking Service
        |       Marks confirmed bookings as pending_refund
        |       Publishes booking.refund.requested for each
        |
        +---> seat_cancel_queue ---> Seat Service
        |       Releases all seats back to available
        |
        +---> ticket_cancel_queue ---> Ticket Service
        |       Invalidates all tickets
        |
        +---> waitlist_cancel_queue ---> Waitlist Service
        |       Cancels all waitlist entries
        |
        +---> notification_lifecycle_queue ---> Notification Service
                Sends cancellation emails via OutSystems SMU Lab API
```

#### Changes Applied

1. **`services/booking_orchestrator/app.py`** — Added `cancel_event()` route at `/events/<int:event_id>/cancel`, `publish_event_lifecycle()` function, and `event_lifecycle` exchange setup
2. **`kong/kong.yml`** — No changes needed. The existing `/api/orchestrator` route with `strip_path: true` already routes `/api/orchestrator/events/1/cancel` to `http://booking_orchestrator:5010/events/1/cancel`
3. **`frontend/src/pages/EventDetailPage.jsx`** — Changed cancel API call from `/api/events/${eventId}/cancel` to `/api/orchestrator/events/${eventId}/cancel`

---

### 9. `seat.availability.updated` Consumer Is Lost (FIXED)

**Problem:** The old Python event service consumed `seat.availability.updated` from `seat_topic` and updated `available_seats` on the event record. OutSystems cannot consume AMQP.

**Impact:** `AvailableSeats` in OutSystems is frozen at the initial value forever. Currently medium impact because the frontend reads seat availability from the Seat service directly, not from the event record. But if you ever show "X seats left" on event cards, it will be wrong.

#### Complete Flow After Fix

```
Seat is booked/released/reserved
        |
        v
Seat Service calculates new total available seats
        |
        v
Seat Service publishes to seat_topic exchange:
  - Routing key: seat.availability.updated
  - Payload: { "event_id": 1, "available_seats": 487 }
        |
        v
RabbitMQ routes to event_availability_queue
        |
        v
Booking Orchestrator consumer thread receives message
        |
        v
Orchestrator calls OutSystems: PUT /events/1
  - Body: { "available_seats": 487 }
  - OutSystems updates the AvailableSeats field
        |
        v
Next time anyone calls GET /events/1, AvailableSeats = 487
```

#### Changes Applied

1. **`services/booking_orchestrator/app.py`** — Added `handle_availability_updated()` AMQP callback and `start_orchestrator_consumers()` which spawns a daemon thread consuming `seat.availability.updated` from `seat_topic`. On receiving a message, it calls OutSystems `PUT /events/{event_id}` with `{ "available_seats": N }`

---

## Low Priority / Optional Issues

### 10. Missing `date_from` / `date_to` Query Filters (LOW PRIORITY)

The old Python service supported 4 query filters: `status`, `category`, `date_from`, `date_to`. OutSystems only has `Status` and `Category`. The frontend does not use date filters (filters client-side), so no impact currently.

**Fix (if needed later in OutSystems):**
1. Open **GetEvents** method in Service Studio
2. Add two new Input Parameters: `DateFrom` (DateTime) and `DateTo` (DateTime)
3. Add filters to the Aggregate:
   - `(DateFrom = NullDate() or Event.EventDate >= DateFrom)`
   - `(DateTo = NullDate() or Event.EventDate <= DateTo)`
4. 1-Click Publish

### 11. OutSystems `event_db` in MySQL Is Now Unused (CLEANUP)

The `db/init.sql` script still creates `event_db`. Since events now live in OutSystems, this database is unused. You can remove the `event_db` section from `init.sql` to avoid confusion, or leave it as a reference.

---

## Summary Table

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | Kong trailing slash / CORS redirect | Critical | FIXED |
| 2 | Orchestrator placeholder EVENT_SERVICE_URL | Critical | FIXED |
| 3 | PascalCase vs snake_case field mapping | Critical | FIXED |
| 4 | Missing .env notification variables | High | FIXED |
| 5 | eslint peer dependency conflict | High | FIXED |
| 6 | GetEvents returns `{}` | Critical | NEEDS OUTSYSTEMS FIX |
| 7 | Event Status field is empty | Critical | NEEDS OUTSYSTEMS FIX |
| 8 | CancelEvent missing RabbitMQ publish | High | FIXED |
| 9 | seat.availability.updated consumer lost | Medium | FIXED |
| 10 | Missing date_from/date_to filters | Low | Optional |
| 11 | Unused event_db in MySQL | Low | Optional cleanup |

---

## Verification Checklist

After all fixes are applied, verify end-to-end:

```bash
# 1. GetEvents returns array of events
curl -s http://localhost:8000/api/events | python3 -m json.tool

# 2. GetEvent returns single event with Status = "upcoming"
curl -s http://localhost:8000/api/events/1 | python3 -m json.tool

# 3. Cancel event triggers downstream (check docker logs)
curl -X POST http://localhost:8000/api/orchestrator/events/1/cancel
docker logs booking     # should see "event.cancelled" handling
docker logs seat        # should see seat releases
docker logs ticket      # should see ticket invalidation
docker logs notification # should see email sending

# 4. Frontend loads events page
# Open http://localhost:5173 — events should display with images, dates, prices
```
