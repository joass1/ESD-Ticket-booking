import pika
import time
import threading
import os

DEFAULT_DLX = 'dlx_exchange'


def connect_with_retry(host=None, max_retries=12, retry_delay=5):
    """Connect to RabbitMQ with retry logic. Returns pika.BlockingConnection."""
    host = host or os.environ.get('RABBITMQ_HOST', 'rabbitmq')
    for attempt in range(max_retries):
        try:
            params = pika.ConnectionParameters(
                host=host,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            connection = pika.BlockingConnection(params)
            print(f"[AMQP] Connected to RabbitMQ at {host}")
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[AMQP] Connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    raise Exception(f"[AMQP] Failed to connect after {max_retries} attempts")


def setup_exchange(channel, exchange_name, exchange_type='topic'):
    """Declare an exchange idempotently."""
    channel.exchange_declare(
        exchange=exchange_name,
        exchange_type=exchange_type,
        durable=True
    )


def publish_message(channel, exchange, routing_key, body, properties=None, correlation_id=None):
    """Publish a message to an exchange with persistent delivery and optional correlation ID."""
    if properties is None:
        # Try to get correlation_id from Flask request context if not provided
        if correlation_id is None:
            try:
                from flask import g
                correlation_id = getattr(g, 'correlation_id', None)
            except (ImportError, RuntimeError):
                pass
        properties = pika.BasicProperties(
            delivery_mode=2,
            correlation_id=correlation_id
        )
    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=body,
        properties=properties,
    )


def start_consumer(queue_name, exchange_name, routing_keys, callback,
                   exchange_type='topic', host=None):
    """Start consuming messages. Runs in a loop with reconnection.
    MUST be called from its own dedicated thread (pika is not thread-safe).
    """
    while True:
        try:
            connection = connect_with_retry(host)
            channel = connection.channel()
            setup_exchange(channel, exchange_name, exchange_type)
            channel.queue_declare(queue=queue_name, durable=True)
            for key in routing_keys:
                channel.queue_bind(
                    exchange=exchange_name,
                    queue=queue_name,
                    routing_key=key
                )
            channel.basic_qos(prefetch_count=10)
            channel.basic_consume(
                queue=queue_name,
                on_message_callback=callback,
                auto_ack=False
            )
            print(f"[AMQP] Consumer started on queue: {queue_name}")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print("[AMQP] Connection lost. Reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"[AMQP] Consumer error: {e}. Reconnecting in 5s...")
            time.sleep(5)


def setup_queue_with_dlq(channel, queue_name, exchange, routing_key, dlx_exchange=None):
    """Declare a queue with dead letter exchange arguments.

    Creates the DLX exchange (fanout) and a DLQ queue, then declares the
    main queue with x-dead-letter-exchange pointing to the DLX.
    """
    dlx = dlx_exchange or DEFAULT_DLX
    dlq_name = f"{queue_name}_dlq"

    # Declare the dead letter exchange (fanout so all DLQ consumers get messages)
    channel.exchange_declare(exchange=dlx, exchange_type='fanout', durable=True)

    # Declare the dead letter queue
    channel.queue_declare(queue=dlq_name, durable=True)
    channel.queue_bind(exchange=dlx, queue=dlq_name)

    # Declare main queue with DLX argument
    channel.queue_declare(
        queue=queue_name,
        durable=True,
        arguments={'x-dead-letter-exchange': dlx}
    )
    channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=routing_key)


def run_with_amqp(flask_app, port, consumer_setup_fn):
    """Start AMQP consumer in daemon thread, then run Flask on main thread.
    consumer_setup_fn should call start_consumer() -- it runs in its own thread.
    """
    consumer_thread = threading.Thread(target=consumer_setup_fn, daemon=True)
    consumer_thread.start()
    flask_app.run(host='0.0.0.0', port=port, debug=False)
