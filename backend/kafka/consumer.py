#!/usr/bin/env python3
"""
Kafka Consumer Module

This module provides an asynchronous Kafka consumer for the Atheon AI system,
handling message deserialization, consumer group configuration, error handling,
and dead-letter queue management.
"""

import asyncio
import json
import traceback
from typing import Any, Callable, Dict, List, Optional, Union, Set

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError, ConsumerStoppedError
from loguru import logger

# Custom handler type for processing messages
MessageHandler = Callable[[str, Dict[str, Any], Dict[str, Any]], asyncio.Future]

class AtheonKafkaConsumer:
    """
    Asynchronous Kafka consumer for the Atheon AI system.

    This class provides methods for consuming messages from Kafka topics,
    with built-in error handling, deserialization, and dead-letter queue support.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topics: List[str],
        topic_prefix: str = "atheon",
        group_id: str = "atheon-consumer-group",
        client_id: str = "atheon-consumer",
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
        max_poll_interval_ms: int = 300000,  # 5 minutes
        session_timeout_ms: int = 30000,  # 30 seconds
        heartbeat_interval_ms: int = 10000,  # 10 seconds
    ):
        """
        Initialize the Kafka consumer.

        Args:
            bootstrap_servers: Comma-separated list of Kafka broker addresses.
            topics: List of topics to subscribe to.
            topic_prefix: Prefix to add to all topic names.
            group_id: Consumer group ID.
            client_id: Client ID to use when connecting to Kafka.
            auto_offset_reset: What to do when there is no initial offset (earliest/latest).
            enable_auto_commit: Whether to automatically commit offsets.
            max_poll_interval_ms: Maximum time between polls before consumer is considered dead.
            session_timeout_ms: Time after which a consumer is considered dead if no heartbeats.
            heartbeat_interval_ms: Interval between heartbeats to the broker.
        """
        self.bootstrap_servers = bootstrap_servers
        self.raw_topics = topics
        self.topic_prefix = topic_prefix
        self.prefixed_topics = [self._get_topic(topic) for topic in topics]
        self.group_id = group_id
        self.client_id = client_id
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.max_poll_interval_ms = max_poll_interval_ms
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms

        self.consumer = None
        self._connected = False
        self._running = False
        self._consume_task = None

        # Handlers for different topics
        self.handlers: Dict[str, MessageHandler] = {}

        # Dead-letter queue topic name
        self.dlq_topic = self._get_topic("dead_letter_queue")

    async def _connect(self) -> None:
        """
        Establish a connection to Kafka.

        This method initializes the AIOKafkaConsumer and connects to the Kafka brokers.
        It handles any connection errors and logs the result.
        """
        if self._connected:
            return

        try:
            logger.info(f"Connecting to Kafka brokers: {self.bootstrap_servers}")
            self.consumer = AIOKafkaConsumer(
                *self.prefixed_topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                client_id=self.client_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                max_poll_interval_ms=self.max_poll_interval_ms,
                session_timeout_ms=self.session_timeout_ms,
                heartbeat_interval_ms=self.heartbeat_interval_ms,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k is not None else None,
            )

            await self.consumer.start()
            self._connected = True

            logger.info(f"Successfully connected to Kafka")
            logger.info(f"Subscribed to topics: {self.prefixed_topics}")
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

    def _get_raw_topic(self, prefixed_topic: str) -> str:
        """
        Get the original topic name without prefix.

        Args:
            prefixed_topic: The full topic name with prefix.

        Returns:
            str: The original topic name.
        """
        if self.topic_prefix:
            prefix_len = len(self.topic_prefix) + 1  # +1 for the dot
            return prefixed_topic[prefix_len:] if prefixed_topic.startswith(f"{self.topic_prefix}.") else prefixed_topic
        return prefixed_topic

    def register_handler(self, topic: str, handler: MessageHandler) -> None:
        """
        Register a handler function for a specific topic.

        Args:
            topic: The topic to handle (without prefix).
            handler: The handler function to call when a message is received.
                    The handler must be an async function that takes topic, key, and value as parameters.
        """
        if not callable(handler):
            raise ValueError("Handler must be a callable")

        logger.info(f"Registering handler for topic {topic}")
        self.handlers[topic] = handler

    async def kafka_start_consumer(self) -> None:
        """
        Start consuming messages from the subscribed topics.

        This method initializes the connection if needed and starts a background task
        to continuously poll for messages and process them.
        """
        if not self._connected:
            await self._connect()

        if self._running:
            logger.warning("Consumer is already running")
            return

        self._running = True
        self._consume_task = asyncio.create_task(self._consume_loop())
        logger.info("Started Kafka consumer")

    async def _consume_loop(self) -> None:
        """
        Main consumption loop.

        This method continuously polls for messages, processes them using the registered handlers,
        and handles any errors that occur during processing.
        """
        try:
            while self._running:
                try:
                    async for message in self.consumer:
                        topic = message.topic
                        raw_topic = self._get_raw_topic(topic)

                        try:
                            # Get the handler for this topic
                            handler = self.handlers.get(raw_topic)

                            if handler:
                                logger.debug(f"Received message on topic {topic}, partition={message.partition}, offset={message.offset}")

                                # Process the message with the handler
                                await handler(raw_topic, message.key, message.value)

                                # If auto-commit is disabled, manually commit the offset
                                if not self.enable_auto_commit:
                                    await self.consumer.commit()
                            else:
                                logger.warning(f"No handler registered for topic {raw_topic}")

                        except Exception as e:
                            logger.error(f"Error processing message from {topic}: {str(e)}")
                            logger.error(traceback.format_exc())

                            # Send to dead-letter queue
                            await self._send_to_dlq(
                                raw_topic=raw_topic,
                                key=message.key,
                                value=message.value,
                                error=str(e),
                                traceback=traceback.format_exc()
                            )

                            # If auto-commit is disabled, manually commit the offset
                            # to avoid reprocessing the failed message
                            if not self.enable_auto_commit:
                                await self.consumer.commit()

                except ConsumerStoppedError:
                    if not self._running:
                        # This is expected when stopping the consumer
                        break
                    logger.error("Consumer stopped unexpectedly")
                    await asyncio.sleep(1)
                    await self._reconnect()

                except KafkaError as e:
                    logger.error(f"Kafka error in consumer loop: {str(e)}")
                    await asyncio.sleep(1)
                    await self._reconnect()

                except Exception as e:
                    logger.error(f"Unexpected error in consumer loop: {str(e)}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(1)

        finally:
            if self._connected and self.consumer is not None:
                await self.consumer.stop()
                self._connected = False
                logger.info("Kafka consumer stopped")

    async def _reconnect(self) -> None:
        """
        Attempt to reconnect to Kafka after a connection error.
        """
        logger.info("Attempting to reconnect to Kafka")

        if self._connected and self.consumer is not None:
            try:
                await self.consumer.stop()
            except Exception as e:
                logger.error(f"Error stopping consumer during reconnect: {str(e)}")

        self._connected = False
        self.consumer = None

        try:
            await self._connect()
        except Exception as e:
            logger.error(f"Failed to reconnect to Kafka: {str(e)}")

    async def _send_to_dlq(
        self,
        raw_topic: str,
        key: Any,
        value: Any,
        error: str,
        traceback: str
    ) -> None:
        """
        Send a failed message to the dead-letter queue.

        Args:
            raw_topic: The original topic (without prefix).
            key: The message key.
            value: The message value.
            error: The error message.
            traceback: The error traceback.
        """
        try:
            from .producer import get_producer

            producer = await get_producer()

            dlq_message = {
                "original_topic": raw_topic,
                "original_key": key,
                "original_value": value,
                "error": error,
                "traceback": traceback,
                "timestamp": asyncio.get_event_loop().time(),
            }

            await producer.kafka_produce_event(
                topic="dead_letter_queue",
                message=dlq_message,
                key=f"dlq-{raw_topic}",
            )

            logger.info(f"Sent failed message from topic {raw_topic} to dead-letter queue")
        except Exception as e:
            logger.error(f"Failed to send message to dead-letter queue: {str(e)}")

    async def kafka_stop_consumer(self) -> None:
        """
        Stop consuming messages and close the connection.

        This method gracefully shuts down the consumer and cleans up resources.
        """
        if not self._running:
            logger.warning("Consumer is not running")
            return

        logger.info("Stopping Kafka consumer")
        self._running = False

        if self._consume_task is not None:
            try:
                # Cancel the consumption task
                self._consume_task.cancel()
                await asyncio.gather(self._consume_task, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error cancelling consume task: {str(e)}")

            self._consume_task = None

        if self._connected and self.consumer is not None:
            try:
                await self.consumer.stop()
                self._connected = False
                self.consumer = None
                logger.info("Kafka consumer connection closed")
            except Exception as e:
                logger.error(f"Error stopping consumer: {str(e)}")

# Create a singleton instance
_consumer: Optional[AtheonKafkaConsumer] = None

async def initialize_consumer(
    bootstrap_servers: str,
    topics: List[str],
    topic_prefix: str = "atheon",
    group_id: str = "atheon-consumer-group",
    client_id: str = "atheon-consumer",
) -> None:
    """
    Initialize the global Kafka consumer.

    Args:
        bootstrap_servers: Comma-separated list of Kafka broker addresses.
        topics: List of topics to subscribe to.
        topic_prefix: Prefix to add to all topic names.
        group_id: Consumer group ID.
        client_id: Client ID to use when connecting to Kafka.
    """
    global _consumer
    if _consumer is None:
        _consumer = AtheonKafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            topics=topics,
            topic_prefix=topic_prefix,
            group_id=group_id,
            client_id=client_id,
        )
        await _consumer._connect()

async def get_consumer() -> AtheonKafkaConsumer:
    """
    Get the global Kafka consumer instance.

    Returns:
        AtheonKafkaConsumer: The global consumer instance.

    Raises:
        RuntimeError: If the consumer has not been initialized.
    """
    if _consumer is None:
        raise RuntimeError("Kafka consumer has not been initialized. Call initialize_consumer() first.")
    return _consumer