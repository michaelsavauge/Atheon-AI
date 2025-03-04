#!/usr/bin/env python3
"""
Kafka Producer Module

This module provides an asynchronous Kafka producer for the Atheon AI system,
handling message serialization, topic management, error handling, and retries.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Union

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from loguru import logger

class AtheonKafkaProducer:
    """
    Asynchronous Kafka producer for the Atheon AI system.

    This class provides methods for sending messages to Kafka topics,
    with built-in error handling, retries, and proper serialization.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic_prefix: str = "atheon",
        client_id: str = "atheon-producer",
        acks: str = "all",
        max_retries: int = 3,
        retry_backoff_ms: int = 500,
    ):
        """
        Initialize the Kafka producer.

        Args:
            bootstrap_servers: Comma-separated list of Kafka broker addresses.
            topic_prefix: Prefix to add to all topic names.
            client_id: Client ID to use when connecting to Kafka.
            acks: Number of acknowledgments required from Kafka brokers.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff_ms: Backoff time between retries in milliseconds.
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic_prefix = topic_prefix
        self.client_id = client_id
        self.acks = acks
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms

        self.producer = None
        self._connected = False

    async def _connect(self) -> None:
        """
        Establish a connection to Kafka.

        This method initializes the AIOKafkaProducer and connects to the Kafka brokers.
        It handles any connection errors and logs the result.
        """
        if self._connected:
            return

        try:
            logger.info(f"Connecting to Kafka brokers: {self.bootstrap_servers}")
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                acks=self.acks,
                retry_backoff_ms=self.retry_backoff_ms,
                enable_idempotence=True,
                compression_type="gzip",
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
            )

            await self.producer.start()
            self._connected = True
            logger.info("Successfully connected to Kafka")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
            raise

    def _get_topic(self, topic_name: str) -> str:
        """
        Get the full topic name with prefix.

        Args:
            topic_name: The short topic name.

        Returns:
            str: The full topic name with prefix.
        """
        return f"{self.topic_prefix}.{topic_name}" if self.topic_prefix else topic_name

    async def kafka_produce_event(
        self,
        topic: str,
        message: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[List[tuple]] = None,
        partition: Optional[int] = None,
        timestamp_ms: Optional[int] = None,
        retries: int = None,
    ) -> bool:
        """
        Send a message to a Kafka topic.

        Args:
            topic: The topic to send the message to.
            message: The message payload as a dictionary.
            key: Optional message key for partitioning.
            headers: Optional message headers.
            partition: Optional specific partition to send to.
            timestamp_ms: Optional message timestamp in milliseconds.
            retries: Number of retries if sending fails (defaults to self.max_retries).

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        if not self._connected:
            await self._connect()

        full_topic = self._get_topic(topic)
        retries = self.max_retries if retries is None else retries

        for attempt in range(retries + 1):
            try:
                logger.debug(f"Sending message to topic {full_topic}")

                # Send the message
                await self.producer.send_and_wait(
                    topic=full_topic,
                    value=message,
                    key=key,
                    headers=headers,
                    partition=partition,
                    timestamp_ms=timestamp_ms,
                )

                logger.info(f"Successfully sent message to topic {full_topic}")
                return True

            except KafkaError as e:
                logger.warning(f"Kafka error on attempt {attempt + 1}/{retries + 1}: {str(e)}")

                if attempt < retries:
                    # Calculate backoff time with exponential increase
                    backoff = (self.retry_backoff_ms / 1000) * (2 ** attempt)
                    logger.info(f"Retrying in {backoff:.2f} seconds")
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"Failed to send message to topic {full_topic} after {retries + 1} attempts")
                    return False

            except Exception as e:
                logger.error(f"Unexpected error sending message to topic {full_topic}: {str(e)}")
                return False

    async def close(self) -> None:
        """
        Close the Kafka producer connection.

        This method ensures that all pending messages are sent and the connection is properly closed.
        """
        if self._connected and self.producer is not None:
            logger.info("Closing Kafka producer connection")
            await self.producer.stop()
            self._connected = False
            self.producer = None

# Create a singleton instance
_producer: Optional[AtheonKafkaProducer] = None

async def initialize_producer(
    bootstrap_servers: str,
    topic_prefix: str = "atheon",
    client_id: str = "atheon-producer",
) -> None:
    """
    Initialize the global Kafka producer.

    Args:
        bootstrap_servers: Comma-separated list of Kafka broker addresses.
        topic_prefix: Prefix to add to all topic names.
        client_id: Client ID to use when connecting to Kafka.
    """
    global _producer
    if _producer is None:
        _producer = AtheonKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            topic_prefix=topic_prefix,
            client_id=client_id,
        )
        await _producer._connect()

async def get_producer() -> AtheonKafkaProducer:
    """
    Get the global Kafka producer instance.

    Returns:
        AtheonKafkaProducer: The global producer instance.

    Raises:
        RuntimeError: If the producer has not been initialized.
    """
    if _producer is None:
        raise RuntimeError("Kafka producer has not been initialized. Call initialize_producer() first.")
    return _producer