#!/bin/bash
# Fill all seats EXCEPT 1 for an event so you can test waitlist promotion via the UI.
# Leaves 1 seat free so you can book it manually as user1, then waitlist as user2.
#
# Usage:
#   bash scripts/fill_seats.sh           # lists events, then asks which to fill
#   bash scripts/fill_seats.sh 30        # fills seats for event 30 (Taylor Swift), leaves 1 free
#
# Event IDs (from OutSystems — NOT 1,2,3):
#   30 = Taylor Swift    20 = Ed Sheeran     22 = Coldplay
#   23 = Jay Chou        24 = Blackpink      25 = Singapore GP
#   26 = Phantom Opera   27 = Russell Peters  28 = Jazz Festival
#   29 = Bruno Mars
#
# After running, any real user trying to book through the UI will hit
# the waitlist flow instead.

SEAT_SERVICE="http://localhost:5003"

# If no event_id provided, list events with seats and let user pick
if [ -z "$1" ]; then
  echo "=== Events with seats ==="
  echo ""
  echo "  ID  | Event"
  echo "  ----|------"
  echo "  30  | Taylor Swift (130 seats: VIP/CAT1/CAT2)"
  echo "  20  | Ed Sheeran (100 seats: VIP/CAT1/CAT2)"
  echo "  22  | Coldplay (130 seats: VIP/CAT1/CAT2)"
  echo "  23  | Jay Chou (105 seats: VIP/CAT1/CAT2)"
  echo "  24  | Blackpink (130 seats: VIP/CAT1/CAT2)"
  echo "  25  | Singapore Grand Prix"
  echo "  26  | Phantom of the Opera"
  echo "  27  | Russell Peters"
  echo "  28  | Jazz Festival"
  echo "  29  | Bruno Mars"
  echo ""
  echo "Usage: bash scripts/fill_seats.sh <event_id>"
  echo "Example: bash scripts/fill_seats.sh 30"
  exit 0
fi

EVENT_ID="$1"

echo "=== Fetching seats for event ${EVENT_ID} ==="

# Get all seats for the event
SEATS_JSON=$(curl -s "${SEAT_SERVICE}/seats/event/${EVENT_ID}")

# Check if we got a valid response (curl failure = empty or no JSON)
if [ -z "$SEATS_JSON" ]; then
  echo "ERROR: Could not reach seat service. Is it running?"
  exit 1
fi

# Filter to only available seats
AVAILABLE=$(echo "$SEATS_JSON" | jq '[.data[] | select(.status == "available")]')
COUNT=$(echo "$AVAILABLE" | jq 'length')
TOTAL=$(echo "$SEATS_JSON" | jq '.data | length')

echo "Found ${COUNT} available seats (${TOTAL} total)"

if [ "$COUNT" -eq 0 ]; then
  if [ "$TOTAL" -eq 0 ]; then
    echo "No seats found for event ${EVENT_ID}. Check the event ID — use OutSystems IDs (e.g. 30, 20, 22), not 1, 2, 3."
    echo "Run without args to see the list: bash scripts/fill_seats.sh"
  else
    echo "All seats already taken — event is full!"
  fi
  exit 0
fi

LEAVE_FREE=1
BOOK_COUNT=$((COUNT - LEAVE_FREE))

echo "Reserving ${BOOK_COUNT} seats (leaving ${LEAVE_FREE} free for you to book manually)..."
echo ""

# Reserve and confirm each seat, skip the last one
echo "$AVAILABLE" | jq -c '.[:-1] | .[]' | while read -r seat; do
  SEAT_ID=$(echo "$seat" | jq -r '.seat_id')
  SEAT_NUM=$(echo "$seat" | jq -r '.seat_number')
  USER_ID="user1"

  # Reserve
  RES=$(curl -s -X POST "${SEAT_SERVICE}/seats/reserve" \
    -H "Content-Type: application/json" \
    -d "{\"event_id\": ${EVENT_ID}, \"seat_id\": ${SEAT_ID}, \"user_id\": \"${USER_ID}\"}")

  RES_CODE=$(echo "$RES" | jq -r '.code')

  if [ "$RES_CODE" = "200" ]; then
    # Confirm so it doesn't expire
    curl -s -X POST "${SEAT_SERVICE}/seats/confirm" \
      -H "Content-Type: application/json" \
      -d "{\"event_id\": ${EVENT_ID}, \"seat_id\": ${SEAT_ID}, \"user_id\": \"${USER_ID}\"}" > /dev/null

    echo "  Booked ${SEAT_NUM} (seat_id=${SEAT_ID})"
  else
    MSG=$(echo "$RES" | jq -r '.message // "unknown error"')
    echo "  SKIP  ${SEAT_NUM} (seat_id=${SEAT_ID}): ${MSG}"
  fi
done

echo ""
echo "=== Final availability ==="
curl -s "${SEAT_SERVICE}/seats/availability/${EVENT_ID}" | jq '{
  event_id: .data.event_id,
  total_seats: .data.total_seats,
  total_available: .data.total_available,
  sections: [.data.sections[] | {name, total_seats, available_seats}]
}'

# Show the remaining free seat
FREE_SEAT=$(echo "$AVAILABLE" | jq -c '.[-1]')
FREE_SEAT_ID=$(echo "$FREE_SEAT" | jq -r '.seat_id')
FREE_SEAT_NUM=$(echo "$FREE_SEAT" | jq -r '.seat_number')
FREE_SECTION=$(echo "$FREE_SEAT" | jq -r '.section_name')

echo ""
echo "=== READY TO TEST WAITLIST PROMOTION ==="
echo ""
echo "1 seat left: ${FREE_SEAT_NUM} (${FREE_SECTION}, seat_id=${FREE_SEAT_ID})"
echo ""
echo "Test steps:"
echo "  1. Log in as user1 in the UI -> book the last seat (${FREE_SEAT_NUM})"
echo "  2. Log in as user2 in the UI -> try to book -> gets waitlisted"
echo "  3. Log in as user1 in the UI -> cancel the booking"
echo "  4. User2 gets promoted off the waitlist!"
