"""
Utility functions for the Atheon AI Orchestrator.

This module provides utility functions for task management, LLM integration,
and other common operations.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from src.config import settings


def generate_task_id() -> str:
    """
    Generate a unique task ID.

    Returns:
        str: A unique task ID.
    """
    return f"task-{uuid.uuid4().hex[:8]}"


def generate_agent_id() -> str:
    """
    Generate a unique agent ID.

    Returns:
        str: A unique agent ID.
    """
    return f"agent-{uuid.uuid4().hex[:8]}"


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """
    Format a datetime object as an ISO 8601 string.

    Args:
        dt: The datetime object to format. Defaults to current time.

    Returns:
        str: The formatted timestamp.
    """
    if dt is None:
        dt = datetime.utcnow()
    return dt.isoformat() + "Z"


def select_llm_provider(task_type: str) -> Dict[str, str]:
    """
    Select the appropriate LLM provider based on task type.

    Args:
        task_type: The type of task to execute.

    Returns:
        Dict[str, str]: The selected LLM provider configuration.
    """
    # Map task types to LLM providers
    task_to_provider = {
        "code_generation": "anthropic",
        "summarization": "openai",
        "transcription": "whisper",
        "general": "openai",
        "fallback": "huggingface",
    }

    # Get the provider for the task type, or use default
    provider_name = task_to_provider.get(task_type, settings.default_llm_provider)
    provider_config = settings.llm_providers.get(provider_name, {})

    logger.debug(f"Selected LLM provider {provider_name} for task type {task_type}")
    return {
        "provider": provider_name,
        "model": provider_config.get("model", ""),
        "description": provider_config.get("description", ""),
    }


def serialize_for_kafka(data: Dict[str, Any]) -> str:
    """
    Serialize data for Kafka message.

    Args:
        data: The data to serialize.

    Returns:
        str: JSON-serialized data.
    """
    return json.dumps(data)


def deserialize_from_kafka(message: str) -> Dict[str, Any]:
    """
    Deserialize data from Kafka message.

    Args:
        message: The message to deserialize.

    Returns:
        Dict[str, Any]: The deserialized data.
    """
    return json.loads(message)


def get_task_status_color(status: str) -> str:
    """
    Get the color code for a task status.

    Args:
        status: The task status.

    Returns:
        str: The color code for the status.
    """
    status_colors = {
        "pending": "blue",
        "in_progress": "yellow",
        "completed": "green",
        "failed": "red",
        "cancelled": "gray",
        "waiting_approval": "purple",
        "approved": "teal",
        "rejected": "orange",
    }
    return status_colors.get(status, "blue")