"""
AMQP Integration Test Script
Tests the shared AMQP library against the running RabbitMQ container.
Runs OUTSIDE Docker against localhost.
"""

import sys
import os
import json
import time
import threading

# Add project root to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.amqp_lib import (
    connect_with_retry,
    setup_exchange,
    publish_message,
    start_consumer,
)

PASSED = 0
FAILED = 0


def test_pass(name):
    global PASSED
    PASSED += 1
    print(f"PASS: {name}")


def test_fail(name, error):
    global FAILED
    FAILED += 1
    print(f"FAIL: {name} -- {error}")


# ============================================
# Test 1: Connection
# ============================================
print("==========================================")
print("AMQP Integration Tests")
print("==========================================")
print("")

try:
    connection = connect_with_retry(host='localhost', max_retries=5, retry_delay=2)
    assert connection.is_open, "Connection is not open"
    connection.close()
    test_pass("connect_with_retry")
except Exception as e:
    test_fail("connect_with_retry", str(e))

# ============================================
# Test 2: Publish
# ============================================
try:
    connection = connect_with_retry(host='localhost')
    channel = connection.channel()
    setup_exchange(channel, 'test_exchange', 'topic')
    test_msg = json.dumps({"test": "hello", "timestamp": time.time()})
    publish_message(channel, 'test_exchange', 'test.message', test_msg)
    connection.close()
    test_pass("publish_message")
except Exception as e:
    test_fail("publish_message", str(e))

# ============================================
# Test 3: Consume (with timeout)
# ============================================
try:
    received = []

    def callback(ch, method, properties, body):
        received.append(json.loads(body))
        ch.basic_ack(delivery_tag=method.delivery_tag)
        ch.stop_consuming()  # Stop after first message

    # Start consumer in thread
    def run_consumer():
        start_consumer(
            'test_queue',
            'test_exchange',
            ['test.message'],
            callback,
            host='localhost'
        )

    consumer_thread = threading.Thread(target=run_consumer, daemon=True)
    consumer_thread.start()
    time.sleep(2)  # Wait for consumer to bind

    # Publish a message
    conn = connect_with_retry(host='localhost')
    ch = conn.channel()
    setup_exchange(ch, 'test_exchange', 'topic')
    publish_message(ch, 'test_exchange', 'test.message', json.dumps({"test": "consume_test"}))
    conn.close()

    # Wait for consumer to receive
    consumer_thread.join(timeout=10)
    assert len(received) == 1, f"Expected 1 message, got {len(received)}"
    assert received[0]["test"] == "consume_test", f"Expected 'consume_test', got {received[0].get('test')}"
    test_pass("start_consumer (publish/consume cycle)")
except Exception as e:
    test_fail("start_consumer (publish/consume cycle)", str(e))

# ============================================
# Test 4: Cleanup
# ============================================
try:
    conn = connect_with_retry(host='localhost')
    ch = conn.channel()
    ch.queue_delete(queue='test_queue')
    ch.exchange_delete(exchange='test_exchange')
    conn.close()
    test_pass("cleanup")
except Exception as e:
    test_fail("cleanup", str(e))

# ============================================
# Summary
# ============================================
print("")
print("==========================================")
TOTAL = PASSED + FAILED
if FAILED == 0:
    print(f"All {PASSED}/{TOTAL} AMQP tests passed!")
    sys.exit(0)
else:
    print(f"{PASSED}/{TOTAL} passed, {FAILED}/{TOTAL} failed")
    sys.exit(1)
