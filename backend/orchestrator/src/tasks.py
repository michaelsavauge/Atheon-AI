#!/usr/bin/env python3
"""
Task Management Module

This module defines the core data models and logic for task management
in the Atheon AI system, including task definition, decomposition,
priority handling, and status tracking.
"""

import enum
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator, field_validator
from loguru import logger

class TaskType(str, enum.Enum):
    """Types of tasks supported by the system."""
    SUMMARIZATION = "summarization"
    WEB_SCRAPING = "web_scraping"
    API_FETCH = "api_fetch"
    TRANSCRIPTION = "transcription"
    CUSTOM = "custom"

class TaskStatus(str, enum.Enum):
    """Possible states of a task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REQUIRES_APPROVAL = "requires_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(str, enum.Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TaskCreate(BaseModel):
    """Model for creating a new task."""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    task_type: TaskType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = Field(default=False)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: Dict[str, Any], info: Any) -> Dict[str, Any]:
        """Validate that the parameters match the expected format for the task type."""
        task_type = info.data.get("task_type")

        if task_type == TaskType.SUMMARIZATION:
            # Check for required parameters for summarization tasks
            required_params = ["text"]
            for param in required_params:
                if param not in v:
                    raise ValueError(f"Missing required parameter '{param}' for {task_type} task")

        elif task_type == TaskType.WEB_SCRAPING:
            # Check for required parameters for web scraping tasks
            required_params = ["url"]
            for param in required_params:
                if param not in v:
                    raise ValueError(f"Missing required parameter '{param}' for {task_type} task")

        elif task_type == TaskType.API_FETCH:
            # Check for required parameters for API fetch tasks
            required_params = ["endpoint"]
            for param in required_params:
                if param not in v:
                    raise ValueError(f"Missing required parameter '{param}' for {task_type} task")

        elif task_type == TaskType.TRANSCRIPTION:
            # Check for required parameters for transcription tasks
            required_params = ["audio_url"]
            for param in required_params:
                if param not in v:
                    raise ValueError(f"Missing required parameter '{param}' for {task_type} task")

        return v

class TaskResponse(BaseModel):
    """Model for task information in responses."""
    id: str
    title: str
    description: str
    task_type: TaskType
    status: TaskStatus
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    requires_approval: bool = False
    priority: TaskPriority = TaskPriority.MEDIUM
    parameters: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    class Config:
        """Pydantic configuration."""
        from_attributes = True

class SubTask(BaseModel):
    """Model for a sub-task created through task decomposition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_task_id: str
    title: str
    description: str
    task_type: TaskType
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    order: int = 0  # For sequential execution ordering

class TaskDecomposition:
    """
    Service for decomposing complex tasks into smaller subtasks.
    """

    @staticmethod
    async def decompose_task(task: TaskResponse) -> List[SubTask]:
        """
        Decompose a complex task into smaller subtasks.

        Args:
            task: The task to decompose.

        Returns:
            List[SubTask]: The list of subtasks.
        """
        logger.info(f"Decomposing task {task.id}")

        # This is a simplistic implementation
        # In a real system, this would likely use an LLM to analyze the task
        # and determine the appropriate decomposition strategy

        subtasks = []

        # Example decomposition strategies based on task type
        if task.task_type == TaskType.SUMMARIZATION and task.parameters:
            # If the text is very long, split it into chunks
            text = task.parameters.get("text", "")
            if len(text) > 10000:  # Arbitrary threshold
                chunk_size = 5000
                chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

                # Create a subtask for each chunk
                for i, chunk in enumerate(chunks):
                    subtasks.append(
                        SubTask(
                            parent_task_id=task.id,
                            title=f"{task.title} - Part {i+1}",
                            description=f"Summarize part {i+1} of {len(chunks)}",
                            task_type=TaskType.SUMMARIZATION,
                            parameters={"text": chunk},
                            order=i,
                        )
                    )

                # Add a final subtask to combine the summaries
                subtasks.append(
                    SubTask(
                        parent_task_id=task.id,
                        title=f"{task.title} - Final Compilation",
                        description="Combine the summaries of all parts",
                        task_type=TaskType.SUMMARIZATION,
                        parameters={"operation": "combine"},
                        order=len(chunks),
                    )
                )

        elif task.task_type == TaskType.WEB_SCRAPING and task.parameters:
            # For web scraping, create subtasks for different aspects
            url = task.parameters.get("url", "")

            # Subtask for metadata extraction
            subtasks.append(
                SubTask(
                    parent_task_id=task.id,
                    title=f"Extract metadata from {url}",
                    description="Extract title, meta tags, and other metadata",
                    task_type=TaskType.WEB_SCRAPING,
                    parameters={"url": url, "extract": "metadata"},
                    order=0,
                )
            )

            # Subtask for content extraction
            subtasks.append(
                SubTask(
                    parent_task_id=task.id,
                    title=f"Extract main content from {url}",
                    description="Extract the main content of the page",
                    task_type=TaskType.WEB_SCRAPING,
                    parameters={"url": url, "extract": "content"},
                    order=1,
                )
            )

            # Subtask for link extraction
            subtasks.append(
                SubTask(
                    parent_task_id=task.id,
                    title=f"Extract links from {url}",
                    description="Extract all links from the page",
                    task_type=TaskType.WEB_SCRAPING,
                    parameters={"url": url, "extract": "links"},
                    order=2,
                )
            )

        # If no specific decomposition strategy is implemented, return an empty list
        logger.info(f"Task {task.id} decomposed into {len(subtasks)} subtasks")
        return subtasks

class TaskPriorityQueue:
    """
    Service for handling task priorities and scheduling.
    """

    def __init__(self):
        """Initialize the task priority queue."""
        self.tasks: Dict[str, Dict[str, Any]] = {}

    async def add_task(self, task_id: str, priority: TaskPriority, created_at: datetime) -> None:
        """
        Add a task to the priority queue.

        Args:
            task_id: The ID of the task.
            priority: The priority of the task.
            created_at: When the task was created.
        """
        logger.info(f"Adding task {task_id} to priority queue with priority {priority}")

        self.tasks[task_id] = {
            "priority": priority,
            "created_at": created_at,
            "scheduled_at": None,
        }

    async def update_priority(self, task_id: str, priority: TaskPriority) -> None:
        """
        Update the priority of a task.

        Args:
            task_id: The ID of the task.
            priority: The new priority of the task.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found in priority queue")

        logger.info(f"Updating task {task_id} priority from {self.tasks[task_id]['priority']} to {priority}")
        self.tasks[task_id]["priority"] = priority

    async def get_next_task(self) -> Optional[str]:
        """
        Get the ID of the next task to process based on priority and creation time.

        Returns:
            Optional[str]: The ID of the next task, or None if there are no tasks.
        """
        if not self.tasks:
            return None

        # Sort tasks by priority (higher priority first) and then by creation time (older first)
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3,
        }

        # Filter out tasks that have already been scheduled
        available_tasks = {
            task_id: data for task_id, data in self.tasks.items()
            if data["scheduled_at"] is None
        }

        if not available_tasks:
            return None

        # Sort by priority and creation time
        sorted_tasks = sorted(
            available_tasks.items(),
            key=lambda x: (
                priority_order[x[1]["priority"]],
                x[1]["created_at"]
            )
        )

        # Return the first task ID
        next_task_id = sorted_tasks[0][0]

        # Mark the task as scheduled
        self.tasks[next_task_id]["scheduled_at"] = datetime.now()

        logger.info(f"Selected task {next_task_id} with priority {self.tasks[next_task_id]['priority']} for processing")
        return next_task_id

    async def remove_task(self, task_id: str) -> None:
        """
        Remove a task from the priority queue.

        Args:
            task_id: The ID of the task to remove.
        """
        if task_id in self.tasks:
            logger.info(f"Removing task {task_id} from priority queue")
            del self.tasks[task_id]
        else:
            logger.warning(f"Attempted to remove non-existent task {task_id} from priority queue")

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current queue.

        Returns:
            Dict[str, Any]: Statistics about the queue.
        """
        total_tasks = len(self.tasks)
        scheduled_tasks = sum(1 for data in self.tasks.values() if data["scheduled_at"] is not None)
        unscheduled_tasks = total_tasks - scheduled_tasks

        priority_counts = {
            TaskPriority.CRITICAL: sum(1 for data in self.tasks.values() if data["priority"] == TaskPriority.CRITICAL),
            TaskPriority.HIGH: sum(1 for data in self.tasks.values() if data["priority"] == TaskPriority.HIGH),
            TaskPriority.MEDIUM: sum(1 for data in self.tasks.values() if data["priority"] == TaskPriority.MEDIUM),
            TaskPriority.LOW: sum(1 for data in self.tasks.values() if data["priority"] == TaskPriority.LOW),
        }

        return {
            "total_tasks": total_tasks,
            "scheduled_tasks": scheduled_tasks,
            "unscheduled_tasks": unscheduled_tasks,
            "priority_counts": priority_counts,
        }

class TaskStatusTracker:
    """
    Service for tracking task status and updates.
    """

    def __init__(self):
        """Initialize the task status tracker."""
        self.tasks: Dict[str, Dict[str, Any]] = {}

    async def register_task(self, task_id: str, status: TaskStatus) -> None:
        """
        Register a new task for status tracking.

        Args:
            task_id: The ID of the task.
            status: The initial status of the task.
        """
        logger.info(f"Registering task {task_id} with status {status}")

        self.tasks[task_id] = {
            "status": status,
            "history": [
                {
                    "status": status,
                    "timestamp": datetime.now(),
                    "details": "Task registered",
                }
            ],
            "last_updated": datetime.now(),
        }

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        details: Optional[str] = None
    ) -> None:
        """
        Update the status of a task.

        Args:
            task_id: The ID of the task.
            status: The new status of the task.
            details: Optional details about the status update.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not registered for status tracking")

        current_status = self.tasks[task_id]["status"]
        if current_status == status:
            logger.debug(f"Task {task_id} status unchanged: {status}")
            return

        logger.info(f"Updating task {task_id} status from {current_status} to {status}")

        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["last_updated"] = datetime.now()

        # Add to history
        self.tasks[task_id]["history"].append({
            "status": status,
            "timestamp": datetime.now(),
            "details": details or f"Status changed from {current_status} to {status}",
        })

    async def get_status(self, task_id: str) -> TaskStatus:
        """
        Get the current status of a task.

        Args:
            task_id: The ID of the task.

        Returns:
            TaskStatus: The current status of the task.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not registered for status tracking")

        return self.tasks[task_id]["status"]

    async def get_status_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get the status history of a task.

        Args:
            task_id: The ID of the task.

        Returns:
            List[Dict[str, Any]]: The status history of the task.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not registered for status tracking")

        return self.tasks[task_id]["history"]

    async def is_task_completed(self, task_id: str) -> bool:
        """
        Check if a task is completed.

        Args:
            task_id: The ID of the task.

        Returns:
            bool: True if the task is completed, False otherwise.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not registered for status tracking")

        return self.tasks[task_id]["status"] == TaskStatus.COMPLETED

    async def is_task_failed(self, task_id: str) -> bool:
        """
        Check if a task has failed.

        Args:
            task_id: The ID of the task.

        Returns:
            bool: True if the task has failed, False otherwise.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not registered for status tracking")

        return self.tasks[task_id]["status"] == TaskStatus.FAILED