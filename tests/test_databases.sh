#!/bin/bash
set -e

# ============================================
# Database Verification Test Script
# Verifies all 9 databases exist with expected tables
# and seed data is present
# ============================================

PASSED=0
FAILED=0
TOTAL=0

MYSQL_CMD="docker exec mysql mysql -uroot -proot -N -e"

echo "=========================================="
echo "Database Verification Tests"
echo "=========================================="
echo ""

# ---- Check all 9 databases exist ----
echo "--- Checking databases exist ---"
DATABASES_OUTPUT=$(docker exec mysql mysql -uroot -proot -N -e "SHOW DATABASES;" 2>/dev/null) || {
    echo "FAIL: Cannot connect to MySQL"
    exit 1
}

EXPECTED_DBS=(
    "event_db"
    "booking_db"
    "seat_db"
    "payment_db"
    "notification_db"
    "ticket_db"
    "waitlist_db"
    "charging_db"
    "saga_log_db"
)

for DB in "${EXPECTED_DBS[@]}"; do
    TOTAL=$((TOTAL + 1))
    echo -n "Database '$DB' exists... "
    if echo "$DATABASES_OUTPUT" | grep -qw "$DB"; then
        echo "PASS"
        PASSED=$((PASSED + 1))
    else
        echo "FAIL"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "--- Checking tables exist per database ---"

# ---- Check each database has at least 1 table ----
for DB in "${EXPECTED_DBS[@]}"; do
    TOTAL=$((TOTAL + 1))
    echo -n "Database '$DB' has tables... "
    TABLES_OUTPUT=$(docker exec mysql mysql -uroot -proot "$DB" -N -e "SHOW TABLES;" 2>/dev/null) || {
        echo "FAIL (cannot query)"
        FAILED=$((FAILED + 1))
        continue
    }
    TABLE_COUNT=$(echo "$TABLES_OUTPUT" | grep -c '.' 2>/dev/null || echo "0")
    if [ "$TABLE_COUNT" -ge 1 ]; then
        echo "PASS ($TABLE_COUNT tables)"
        PASSED=$((PASSED + 1))
    else
        echo "FAIL (0 tables)"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "--- Spot-checking specific tables ---"

# ---- Spot-check specific tables ----
declare -A SPOT_CHECKS=(
    ["event_db"]="events"
    ["booking_db"]="bookings"
    ["seat_db"]="seats"
    ["seat_db_sections"]="sections"
    ["saga_log_db"]="saga_log"
)

for KEY in "${!SPOT_CHECKS[@]}"; do
    DB="${KEY%%_sections}"
    # Handle the seat_db_sections special case
    if [[ "$KEY" == "seat_db_sections" ]]; then
        DB="seat_db"
    fi
    TABLE="${SPOT_CHECKS[$KEY]}"
    TOTAL=$((TOTAL + 1))
    echo -n "Table '$TABLE' in '$DB'... "
    TABLE_EXISTS=$(docker exec mysql mysql -uroot -proot "$DB" -N -e "SHOW TABLES LIKE '$TABLE';" 2>/dev/null)
    if [ -n "$TABLE_EXISTS" ]; then
        echo "PASS"
        PASSED=$((PASSED + 1))
    else
        echo "FAIL"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "--- Verifying seed data ---"

# ---- Verify seed data ----
TOTAL=$((TOTAL + 1))
echo -n "Seed data: events count >= 3... "
EVENT_COUNT=$(docker exec mysql mysql -uroot -proot event_db -N -e "SELECT COUNT(*) FROM events;" 2>/dev/null)
if [ "$EVENT_COUNT" -ge 3 ] 2>/dev/null; then
    echo "PASS ($EVENT_COUNT events)"
    PASSED=$((PASSED + 1))
else
    echo "FAIL (count: $EVENT_COUNT)"
    FAILED=$((FAILED + 1))
fi

TOTAL=$((TOTAL + 1))
echo -n "Seed data: sections count >= 3... "
SECTION_COUNT=$(docker exec mysql mysql -uroot -proot seat_db -N -e "SELECT COUNT(*) FROM sections;" 2>/dev/null)
if [ "$SECTION_COUNT" -ge 3 ] 2>/dev/null; then
    echo "PASS ($SECTION_COUNT sections)"
    PASSED=$((PASSED + 1))
else
    echo "FAIL (count: $SECTION_COUNT)"
    FAILED=$((FAILED + 1))
fi

TOTAL=$((TOTAL + 1))
echo -n "Seed data: seats count >= 10... "
SEAT_COUNT=$(docker exec mysql mysql -uroot -proot seat_db -N -e "SELECT COUNT(*) FROM seats;" 2>/dev/null)
if [ "$SEAT_COUNT" -ge 10 ] 2>/dev/null; then
    echo "PASS ($SEAT_COUNT seats)"
    PASSED=$((PASSED + 1))
else
    echo "FAIL (count: $SEAT_COUNT)"
    FAILED=$((FAILED + 1))
fi

echo ""
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "All ${PASSED}/${TOTAL} database checks passed"
    exit 0
else
    echo "${PASSED}/${TOTAL} passed, ${FAILED}/${TOTAL} failed"
    exit 1
fi
