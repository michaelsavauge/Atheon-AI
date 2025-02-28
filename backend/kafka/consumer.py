"""
Kafka consumer module for the Atheon AI system.

This module provides functions for consuming messages from Kafka topics.
"""

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

from kafka import KafkaConsumer
from loguru import logger


class AtheonKafkaConsumer:
    """Kafka consumer for the Atheon AI system."""

    def __init__(
        self,
        bootstrap_servers: str,
        topics: List[str],
        topic_prefix: str = "atheon",
        group_id: str = "atheon-consumer",
        client_id: str = "atheon-consumer",
        auto_offset_reset: str = "latest",
    ) -> None:
        """
        Initialize the Kafka consumer.

        Args:
            bootstrap_servers: Kafka bootstrap servers.
            topics: List of topics to consume.
            topic_prefix: Prefix for Kafka topics.
            group_id: Consumer group ID.
            client_id: Client ID for the consumer.
            auto_offset_reset: Auto offset reset strategy.
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic_prefix = topic_prefix
        self.topics = [f"{topic_prefix}.{topic}" for topic in topics]
        self.group_id = group_id
        self.client_id = client_id
        self.auto_offset_reset = auto_offset_reset
        self.consumer = None
        self.running = False
        self.handlers: Dict[str, Callable] = {}

    def _connect(self) -> None:
        """Connect to Kafka."""
        try:
            self.consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                client_id=self.client_id,
                auto_offset_reset=self.auto_offset_reset,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
            )
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
            logger.info(f"Subscribed to topics: {', '.join(self.topics)}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
            raise

    def register_handler(self, topic: str, handler: Callable) -> None:
        """
        Register a handler for a topic.

        Args:
            topic: The topic name (without prefix).
            handler: The handler function.
        """
        full_topic = f"{self.topic_prefix}.{topic}"
        self.handlers[full_topic] = handler
        logger.info(f"Registered handler for topic {full_topic}")

    async def kafka_start_consumer(self) -> None:
        """Start consuming messages."""
        if not self.consumer:
            self._connect()

        self.running = True
        logger.info("Starting Kafka consumer")

        # Start the consumer loop in a background task
        asyncio.create_task(self._consume_loop())

    async def _consume_loop(self) -> None:
        """Consume messages in a loop."""
        while self.running:
            try:
                # Non-blocking poll with a timeout
                message_batch = self.consumer.poll(timeout_ms=1000)

                if not message_batch:
                    # No messages, sleep briefly to avoid CPU spinning
                    await asyncio.sleep(0.1)
                    continue

                # Process messages
                for topic_partition, messages in message_batch.items():
                    topic = topic_partition.topic
                    handler = self.handlers.get(topic)

                    if handler:
                        for message in messages:
                            try:
                                # Call the handler asynchronously
                                await handler(message.value, message.key)
                            except Exception as e:
                                logger.error(
                                    f"Error processing message from {topic}: {str(e)}"
                                )
                    else:
                        logger.warning(f"No handler registered for topic {topic}")

                # Commit offsets
                self.consumer.commit()

            except Exception as e:
                logger.error(f"Error in consumer loop: {str(e)}")
                # Sleep briefly before retrying
                await asyncio.sleep(1)

    async def kafka_stop_consumer(self) -> None:
        """Stop consuming messages."""
        self.running = False
        logger.info("Stopping Kafka consumer")

        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")


# Create a singleton instance
kafka_consumer = None


def initialize_consumer(
    bootstrap_servers: str,
    topics: List[str],
    topic_prefix: str = "atheon",
    group_id: str = "atheon-consumer",
) -> AtheonKafkaConsumer:
    """
    Initialize the Kafka consumer singleton.

    Args:
        bootstrap_servers: Kafka bootstrap servers.
        topics: List of topics to consume.
        topic_prefix: Prefix for Kafka topics.
        group_id: Consumer group ID.

    Returns:
        AtheonKafkaConsumer: The Kafka consumer instance.
    """
    global kafka_consumer
    if not kafka_consumer:
        kafka_consumer = AtheonKafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            topics=topics,
            topic_prefix=topic_prefix,
            group_id=group_id,
        )
    return kafka_consumer


def get_consumer() -> Optional[AtheonKafkaConsumer]:
    """
    Get the Kafka consumer singleton.

    Returns:
        Optional[AtheonKafkaConsumer]: The Kafka consumer instance, if initialized.
    """
    return kafka_consumer