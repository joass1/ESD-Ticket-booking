#!/bin/bash
set -e

# ============================================
# Health Endpoint Test Script
# Tests all 9 microservice /health endpoints
# Expected response: {"code": 200, "data": {"status": "healthy"}}
# ============================================

PASSED=0
FAILED=0
TOTAL=9

# Service name:port pairs
declare -a SERVICES=(
    "event:5001"
    "booking:5002"
    "seat:5003"
    "payment:5004"
    "notification:5005"
    "ticket:5006"
    "waitlist:5007"
    "charging:5008"
    "booking_orchestrator:5010"
)

echo "=========================================="
echo "Health Endpoint Tests"
echo "=========================================="
echo ""

for entry in "${SERVICES[@]}"; do
    SERVICE_NAME="${entry%%:*}"
    PORT="${entry##*:}"

    echo -n "Testing $SERVICE_NAME (port $PORT)... "

    # Curl the health endpoint and validate JSON response
    RESPONSE=$(curl -sf "http://localhost:${PORT}/health" 2>/dev/null) || {
        echo "FAIL (connection refused or timeout)"
        FAILED=$((FAILED + 1))
        continue
    }

    # Validate JSON structure: code == 200 and data.status == "healthy"
    echo "$RESPONSE" | python -c "
import json, sys
d = json.load(sys.stdin)
assert d['code'] == 200, f\"Expected code 200, got {d['code']}\"
assert d['data']['status'] == 'healthy', f\"Expected status 'healthy', got {d['data']['status']}\"
" 2>/dev/null && {
        echo "PASS"
        PASSED=$((PASSED + 1))
    } || {
        echo "FAIL (invalid response: $RESPONSE)"
        FAILED=$((FAILED + 1))
    }
done

echo ""
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "All ${PASSED}/${TOTAL} health checks passed"
    exit 0
else
    echo "${PASSED}/${TOTAL} passed, ${FAILED}/${TOTAL} failed"
    exit 1
fi
