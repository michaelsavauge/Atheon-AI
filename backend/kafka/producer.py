"""
Kafka producer module for the Atheon AI system.

This module provides functions for producing messages to Kafka topics.
"""

import json
from typing import Any, Dict, Optional

from kafka import KafkaProducer
from loguru import logger


class AtheonKafkaProducer:
    """Kafka producer for the Atheon AI system."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic_prefix: str = "atheon",
        client_id: str = "atheon-producer",
    ) -> None:
        """
        Initialize the Kafka producer.

        Args:
            bootstrap_servers: Kafka bootstrap servers.
            topic_prefix: Prefix for Kafka topics.
            client_id: Client ID for the producer.
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic_prefix = topic_prefix
        self.client_id = client_id
        self.producer = None
        self._connect()

    def _connect(self) -> None:
        """Connect to Kafka."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
            raise

    def _get_topic(self, topic: str) -> str:
        """
        Get the full topic name with prefix.

        Args:
            topic: The topic name.

        Returns:
            str: The full topic name.
        """
        return f"{self.topic_prefix}.{topic}"

    async def kafka_produce_event(
        self, topic: str, value: Dict[str, Any], key: Optional[str] = None
    ) -> bool:
        """
        Produce an event to a Kafka topic.

        Args:
            topic: The topic name.
            value: The message value.
            key: Optional message key.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.producer:
            logger.error("Kafka producer not connected")
            return False

        full_topic = self._get_topic(topic)
        try:
            future = self.producer.send(full_topic, value=value, key=key)
            result = future.get(timeout=10)
            logger.debug(
                f"Produced message to {full_topic}: partition={result.partition}, offset={result.offset}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to produce message to {full_topic}: {str(e)}")
            return False

    def close(self) -> None:
        """Close the Kafka producer."""
        if self.producer:
            self.producer.close()
            logger.info("Kafka producer closed")


# Create a singleton instance
kafka_producer = None


def initialize_producer(
    bootstrap_servers: str, topic_prefix: str = "atheon"
) -> AtheonKafkaProducer:
    """
    Initialize the Kafka producer singleton.

    Args:
        bootstrap_servers: Kafka bootstrap servers.
        topic_prefix: Prefix for Kafka topics.

    Returns:
        AtheonKafkaProducer: The Kafka producer instance.
    """
    global kafka_producer
    if not kafka_producer:
        kafka_producer = AtheonKafkaProducer(
            bootstrap_servers=bootstrap_servers, topic_prefix=topic_prefix
        )
    return kafka_producer


def get_producer() -> Optional[AtheonKafkaProducer]:
    """
    Get the Kafka producer singleton.

    Returns:
        Optional[AtheonKafkaProducer]: The Kafka producer instance, if initialized.
    """
    return kafka_producer