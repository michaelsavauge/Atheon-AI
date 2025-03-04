#!/usr/bin/env python3
"""
Python Agent Template

This module provides a base template for creating horizontal agents in Python,
with built-in Kafka integration, async task processing, observability, and
error handling. Use this as a starting point for specialized agents.
"""

import asyncio
import json
import os
import signal
import sys
import time
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

import structlog
from loguru import logger
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field

# Assuming Kafka modules are at the project level or as a package
from atheon_ai.kafka.consumer import AtheonKafkaConsumer
from atheon_ai.kafka.producer import AtheonKafkaProducer
from atheon_ai.utils.config import Settings, get_settings

# Set up OpenTelemetry tracing
resource = Resource(attributes={"service.name": "python-agent-template"})
trace_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTLP_ENDPOINT", "localhost:4317"))
span_processor = BatchSpanProcessor(otlp_exporter)
trace_provider.add_span_processor(span_processor)
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(__name__)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

class TaskRequest(BaseModel):
    """Base model for task requests."""
    task_id: str = Field(..., description="Unique ID for the task")
    created_at: float = Field(default_factory=time.time, description="Timestamp when the task was created")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class TaskResponse(BaseModel):
    """Base model for task responses."""
    task_id: str = Field(..., description="Unique ID for the task")
    status: str = Field(..., description="Task status (success, error)")
    created_at: float = Field(default_factory=time.time, description="Timestamp when the response was created")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result data")
    error: Optional[str] = Field(None, description="Error message if task failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class BaseAgent:
    """
    Base class for horizontal agents in the Atheon AI system.

    This class provides common functionality for Kafka integration,
    task processing, observability, and error handling.
    """

    def __init__(
        self,
        agent_name: str,
        input_topic: str,
        output_topic: str,
        bootstrap_servers: str,
        group_id: Optional[str] = None,
        kafka_topic_prefix: str = "atheon",
        settings: Optional[Settings] = None,
    ):
        """
        Initialize the base agent.

        Args:
            agent_name: Name of the agent (used for metrics and logging).
            input_topic: Kafka topic to subscribe to for incoming tasks.
            output_topic: Kafka topic to publish task results to.
            bootstrap_servers: Kafka bootstrap servers.
            group_id: Kafka consumer group ID (defaults to agent_name).
            kafka_topic_prefix: Prefix for Kafka topics.
            settings: Application settings.
        """
        self.agent_name = agent_name
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id or f"{agent_name}-group"
        self.kafka_topic_prefix = kafka_topic_prefix
        self.settings = settings or get_settings()

        self.consumer = None
        self.producer = None
        self.running = False
        self.tasks_processed = 0
        self.successful_tasks = 0
        self.failed_tasks = 0

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        # Initialize metrics
        self._setup_metrics()

        log.info("Agent initialized",
                 agent_name=self.agent_name,
                 input_topic=self.input_topic,
                 output_topic=self.output_topic)

    def _setup_metrics(self) -> None:
        """Set up OpenTelemetry metrics for the agent."""
        meter = metrics.get_meter(__name__)

        # Create counter metrics
        self.task_counter = meter.create_counter(
            name=f"{self.agent_name}_tasks_processed",
            description=f"Number of tasks processed by the {self.agent_name}",
        )

        self.success_counter = meter.create_counter(
            name=f"{self.agent_name}_tasks_succeeded",
            description=f"Number of tasks successfully processed by the {self.agent_name}",
        )

        self.error_counter = meter.create_counter(
            name=f"{self.agent_name}_tasks_failed",
            description=f"Number of tasks that failed processing by the {self.agent_name}",
        )

        # Create histogram for processing time
        self.processing_time = meter.create_histogram(
            name=f"{self.agent_name}_processing_time",
            description=f"Time taken to process tasks by the {self.agent_name}",
            unit="ms",
        )

    async def connect(self) -> None:
        """Connect to Kafka."""
        log.info("Connecting to Kafka", bootstrap_servers=self.bootstrap_servers)

        # Initialize the producer
        self.producer = AtheonKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            topic_prefix=self.kafka_topic_prefix,
            client_id=f"{self.agent_name}-producer",
        )
        await self.producer._connect()

        # Initialize the consumer
        self.consumer = AtheonKafkaConsumer(
            bootstrap_servers=self.bootstrap_servers,
            topics=[self.input_topic],
            topic_prefix=self.kafka_topic_prefix,
            group_id=self.group_id,
            client_id=f"{self.agent_name}-consumer",
            auto_offset_reset="earliest",
        )

        # Register message handler
        self.consumer.register_handler(self.input_topic, self._handle_message)

        log.info("Connected to Kafka successfully")

    async def start(self) -> None:
        """Start the agent."""
        log.info("Starting agent", agent_name=self.agent_name)

        if not self.consumer:
            await self.connect()

        self.running = True

        # Start consuming messages
        await self.consumer.kafka_start_consumer()

        log.info("Agent started successfully")

    async def stop(self) -> None:
        """Stop the agent."""
        log.info("Stopping agent", agent_name=self.agent_name)

        self.running = False

        # Stop the consumer
        if self.consumer:
            await self.consumer.kafka_stop_consumer()

        # Close the producer
        if self.producer:
            await self.producer.close()

        log.info("Agent stopped successfully",
                 tasks_processed=self.tasks_processed,
                 successful_tasks=self.successful_tasks,
                 failed_tasks=self.failed_tasks)

    def _handle_signal(self, signum, frame) -> None:
        """Handle termination signals."""
        log.info("Received termination signal", signal=signum)

        # Create a task to stop the agent
        loop = asyncio.get_event_loop()
        loop.create_task(self.stop())

    async def _handle_message(self, topic: str, key: Optional[str], value: Dict[str, Any]) -> None:
        """
        Handle incoming messages from Kafka.

        Args:
            topic: The topic the message was received on.
            key: The message key.
            value: The message value.
        """
        with tracer.start_as_current_span(f"{self.agent_name}_process_task") as span:
            start_time = time.time()
            task_id = value.get("task_id", str(uuid.uuid4()))

            span.set_attribute("task_id", task_id)

            log_ctx = log.bind(task_id=task_id, agent=self.agent_name)
            log_ctx.info("Received task", topic=topic)

            self.tasks_processed += 1
            self.task_counter.add(1)

            try:
                # Parse the request
                request = TaskRequest(**value)

                # Process the task
                log_ctx.info("Processing task")
                result = await self.process_task(request)

                # Create the response
                response = TaskResponse(
                    task_id=task_id,
                    status="success",
                    result=result,
                    metadata={"agent": self.agent_name, "processed_at": time.time()},
                )

                # Send the response
                await self.producer.kafka_produce_event(
                    topic=self.output_topic,
                    message=response.dict(),
                    key=task_id,
                )

                self.successful_tasks += 1
                self.success_counter.add(1)
                log_ctx.info("Task processed successfully")

            except Exception as e:
                self.failed_tasks += 1
                self.error_counter.add(1)

                error_message = str(e)
                error_traceback = traceback.format_exc()

                log_ctx.error("Error processing task",
                             error=error_message,
                             traceback=error_traceback)

                span.record_exception(e)
                span.set_attribute("error", True)

                # Create error response
                try:
                    response = TaskResponse(
                        task_id=task_id,
                        status="error",
                        error=error_message,
                        metadata={
                            "agent": self.agent_name,
                            "traceback": error_traceback,
                            "processed_at": time.time(),
                        },
                    )

                    # Send the error response
                    await self.producer.kafka_produce_event(
                        topic=self.output_topic,
                        message=response.dict(),
                        key=task_id,
                    )

                    log_ctx.info("Error response sent")
                except Exception as send_error:
                    log_ctx.error("Failed to send error response",
                                 error=str(send_error))

            finally:
                # Record processing time
                processing_time_ms = (time.time() - start_time) * 1000
                self.processing_time.record(processing_time_ms)
                span.set_attribute("processing_time_ms", processing_time_ms)

                log_ctx.info("Task handling completed",
                            processing_time_ms=processing_time_ms)

    async def process_task(self, request: TaskRequest) -> Dict[str, Any]:
        """
        Process a task. This method should be overridden by child classes.

        Args:
            request: The task request.

        Returns:
            Dict[str, Any]: The task result.

        Raises:
            NotImplementedError: If not overridden by a child class.
        """
        raise NotImplementedError("Child classes must implement process_task()")

    @classmethod
    async def run(cls, *args, **kwargs) -> None:
        """
        Run the agent as a standalone service.

        Args:
            *args: Positional arguments to pass to the agent constructor.
            **kwargs: Keyword arguments to pass to the agent constructor.
        """
        agent = cls(*args, **kwargs)

        try:
            await agent.start()

            # Keep the agent running until stopped
            while agent.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            log.info("Agent interrupted by user")

        except Exception as e:
            log.error("Unhandled exception in agent", error=str(e), traceback=traceback.format_exc())

        finally:
            await agent.stop()

class ExampleAgent(BaseAgent):
    """
    Example implementation of a specialized agent.

    This class demonstrates how to extend the BaseAgent class
    to create a specialized agent for a specific task.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        *args,
        **kwargs,
    ):
        """
        Initialize the example agent.

        Args:
            bootstrap_servers: Kafka bootstrap servers.
            *args: Additional positional arguments to pass to the base class.
            **kwargs: Additional keyword arguments to pass to the base class.
        """
        super().__init__(
            agent_name="example-agent",
            input_topic="example_requests",
            output_topic="example_results",
            bootstrap_servers=bootstrap_servers,
            *args,
            **kwargs,
        )

        # Additional initialization specific to this agent
        self.model_loaded = False
        self.model = None

    async def connect(self) -> None:
        """Connect to Kafka and load the model."""
        await super().connect()

        # Load the model (simulated)
        log.info("Loading model")
        await asyncio.sleep(2)  # Simulate model loading
        self.model_loaded = True
        log.info("Model loaded successfully")

    async def process_task(self, request: TaskRequest) -> Dict[str, Any]:
        """
        Process a task using the example agent's capabilities.

        Args:
            request: The task request.

        Returns:
            Dict[str, Any]: The task result.
        """
        if not self.model_loaded:
            raise RuntimeError("Model not loaded")

        # Extract parameters from the request
        text = request.parameters.get("text", "")
        if not text:
            raise ValueError("Text parameter is required")

        # Simulate processing
        await asyncio.sleep(1)

        # Generate result
        return {
            "processed_text": text.upper(),  # Just a simple transformation for demo
            "length": len(text),
            "word_count": len(text.split()),
        }

if __name__ == "__main__":
    """
    Run the example agent as a standalone service.

    This code is executed when the module is run directly.
    """
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    # Run the example agent
    asyncio.run(ExampleAgent.run(bootstrap_servers=bootstrap_servers))