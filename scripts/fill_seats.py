"""
Fill all seats EXCEPT 1 for an event so you can test waitlist promotion via the UI.
Leaves 1 seat free so you can book it manually as user1, then waitlist as user2.

Usage:
    python scripts/fill_seats.py           # lists events
    python scripts/fill_seats.py 30        # fills seats for event 30 (Taylor Swift)

Event IDs (from OutSystems):
    30 = Taylor Swift    20 = Ed Sheeran     22 = Coldplay
    23 = Jay Chou        24 = Blackpink      25 = Singapore GP
    26 = Phantom Opera   27 = Russell Peters  28 = Jazz Festival
    29 = Bruno Mars
"""

import sys
import requests

SEAT_SERVICE = "http://localhost:5003"

if len(sys.argv) < 2:
    print("=== Events with seats ===")
    print()
    print("  ID  | Event")
    print("  ----|------")
    print("  30  | Taylor Swift (130 seats: VIP/CAT1/CAT2)")
    print("  20  | Ed Sheeran (100 seats: VIP/CAT1/CAT2)")
    print("  22  | Coldplay (130 seats: VIP/CAT1/CAT2)")
    print("  23  | Jay Chou (105 seats: VIP/CAT1/CAT2)")
    print("  24  | Blackpink (130 seats: VIP/CAT1/CAT2)")
    print("  25  | Singapore Grand Prix")
    print("  26  | Phantom of the Opera")
    print("  27  | Russell Peters")
    print("  28  | Jazz Festival")
    print("  29  | Bruno Mars")
    print()
    print("Usage: python scripts/fill_seats.py <event_id>")
    sys.exit(0)

event_id = int(sys.argv[1])

print(f"=== Fetching seats for event {event_id} ===")

try:
    resp = requests.get(f"{SEAT_SERVICE}/seats/event/{event_id}")
    data = resp.json()
except Exception as e:
    print(f"ERROR: Could not reach seat service. Is it running?\n{e}")
    sys.exit(1)

all_seats = data.get("data", [])
available = [s for s in all_seats if s["status"] == "available"]

print(f"Found {len(available)} available seats ({len(all_seats)} total)")

if not available:
    if not all_seats:
        print(f"No seats for event {event_id}. Use OutSystems IDs (30, 20, 22...), not 1, 2, 3.")
    else:
        print("All seats already taken — event is full!")
    sys.exit(0)

# Leave the last seat free for manual booking
free_seat = available[-1]
to_book = available[:-1]

print(f"Booking {len(to_book)} seats, leaving 1 free ({free_seat['seat_number']})...")
print()

booked = 0
for seat in to_book:
    seat_id = seat["seat_id"]
    seat_num = seat["seat_number"]
    user_id = "filler"

    # Reserve
    res = requests.post(f"{SEAT_SERVICE}/seats/reserve", json={
        "event_id": event_id,
        "seat_id": seat_id,
        "user_id": user_id
    })
    r = res.json()

    if r.get("code") == 200:
        # Confirm so it doesn't expire
        requests.post(f"{SEAT_SERVICE}/seats/confirm", json={
            "event_id": event_id,
            "seat_id": seat_id,
            "user_id": user_id
        })
        booked += 1
        print(f"  Booked {seat_num} (seat_id={seat_id})")
    else:
        msg = r.get("message", "unknown error")
        print(f"  SKIP  {seat_num} (seat_id={seat_id}): {msg}")

# Show availability
print()
print("=== Final availability ===")
avail_resp = requests.get(f"{SEAT_SERVICE}/seats/availability/{event_id}")
avail_data = avail_resp.json().get("data", {})
print(f"  Total seats: {avail_data.get('total_seats', '?')}")
print(f"  Available:   {avail_data.get('total_available', '?')}")
for sec in avail_data.get("sections", []):
    print(f"    {sec['name']}: {sec['available_seats']}/{sec['total_seats']} available")

print()
print("=== READY TO TEST WAITLIST PROMOTION ===")
print()
print(f"  1 seat left: {free_seat['seat_number']} ({free_seat.get('section_name', '?')}, seat_id={free_seat['seat_id']})")
print()
print("  Test steps:")
print(f"    1. Log in as user1 in the UI -> book the last seat ({free_seat['seat_number']})")
print("    2. Log in as user2 in the UI -> try to book -> gets waitlisted")
print("    3. Log in as user1 in the UI -> cancel the booking")
print("    4. User2 gets promoted off the waitlist!")
