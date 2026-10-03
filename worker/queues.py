from worker.config import DLQ, MAIN_QUEUE, RETRY_DELAYS_SECONDS


def declare_topology(channel) -> None:
    """Declare durable queues; retry queues return expired messages to main."""
    channel.queue_declare(queue=MAIN_QUEUE, durable=True)
    channel.queue_declare(queue=DLQ, durable=True)
    for delay in RETRY_DELAYS_SECONDS:
        channel.queue_declare(
            queue=f"{MAIN_QUEUE}.retry.{delay}s",
            durable=True,
            arguments={
                "x-message-ttl": delay * 1000,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": MAIN_QUEUE,
            },
        )
