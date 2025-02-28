"""
Task management module for the Atheon AI Orchestrator.

This module provides functions for task creation, routing, and execution
using LangGraph for orchestration.
"""

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from langgraph.graph import END, StateGraph
from loguru import logger
from pydantic import BaseModel, Field

from src.ai_agent import llm_generate_text
from src.config import settings
from src.hitl import hitl_manager
from src.utils import format_timestamp, generate_task_id


class TaskStatus(str, Enum):
    """Enum for task status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class TaskType(str, Enum):
    """Enum for task types."""

    SUMMARIZATION = "summarization"
    WEB_SCRAPING = "web_scraping"
    TRANSCRIPTION = "transcription"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    GENERAL = "general"


class Task(BaseModel):
    """Model for task information."""

    task_id: str = Field(..., description="Unique task identifier")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    task_type: TaskType = Field(..., description="Type of task")
    status: TaskStatus = Field(
        default=TaskStatus.PENDING, description="Current task status"
    )
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    completed_at: Optional[str] = Field(
        default=None, description="Completion timestamp"
    )
    priority: int = Field(default=1, description="Task priority (1-5)")
    require_hitl: bool = Field(
        default=True, description="Whether human approval is required"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Task-specific parameters"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Task result"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")


class TaskManager:
    """Manager for task orchestration."""

    def __init__(self) -> None:
        """Initialize the task manager."""
        self._tasks: Dict[str, Task] = {}
        self._setup_workflow_graph()

    def _setup_workflow_graph(self) -> None:
        """Set up the LangGraph workflow graph."""
        # Define the state schema
        class GraphState(BaseModel):
            """State for the workflow graph."""

            task: Task
            context: Dict[str, Any] = Field(default_factory=dict)
            messages: List[Dict[str, str]] = Field(default_factory=list)

        # Define the nodes in the graph
        def analyze_task(state: GraphState) -> GraphState:
            """Analyze the task and determine next steps."""
            task = state.task
            logger.info(f"Analyzing task {task.task_id}")

            # Update task status
            task.status = TaskStatus.IN_PROGRESS
            task.updated_at = format_timestamp()

            # Add analysis to context
            state.context["analysis"] = {
                "task_type": task.task_type,
                "complexity": "medium",  # This would be determined by LLM
                "estimated_time": "5 minutes",  # This would be determined by LLM
            }

            # Add a message
            state.messages.append({
                "role": "system",
                "content": f"Task {task.task_id} analysis completed."
            })

            return state

        def route_task(state: GraphState) -> str:
            """Route the task to the appropriate agent."""
            task = state.task
            logger.info(f"Routing task {task.task_id}")

            # Determine the next step based on task type
            if task.require_hitl:
                return "request_approval"
            else:
                return "execute_task"

        async def execute_task(state: GraphState) -> GraphState:
            """Execute the task using the appropriate agent."""
            task = state.task
            logger.info(f"Executing task {task.task_id}")

            # This would call the appropriate horizontal agent via Kafka
            # For now, we'll simulate execution with a delay
            await asyncio.sleep(2)

            # Update task with result
            task.status = TaskStatus.COMPLETED
            task.updated_at = format_timestamp()
            task.completed_at = format_timestamp()
            task.result = {
                "output": f"Simulated result for task {task.task_id}",
                "confidence": 0.95,
            }

            # Add a message
            state.messages.append({
                "role": "system",
                "content": f"Task {task.task_id} execution completed."
            })

            return state

        async def request_approval(state: GraphState) -> GraphState:
            """Request human approval for the task."""
            task = state.task
            logger.info(f"Requesting approval for task {task.task_id}")

            # Update task status
            task.status = TaskStatus.WAITING_APPROVAL
            task.updated_at = format_timestamp()

            # Create an approval request
            approval_request = await hitl_manager.create_approval_request(
                task_id=task.task_id,
                title=f"Approval for {task.title}",
                description=f"Please review and approve the task: {task.description}",
                data={
                    "task_type": task.task_type,
                    "parameters": task.parameters,
                    "analysis": state.context.get("analysis", {}),
                },
            )

            # Store the request ID in context
            state.context["approval_request_id"] = approval_request.request_id

            # Add a message
            state.messages.append({
                "role": "system",
                "content": f"Approval requested for task {task.task_id}."
            })

            return state

        async def check_approval(state: GraphState) -> str:
            """Check if the task has been approved."""
            task = state.task
            request_id = state.context.get("approval_request_id")

            if not request_id:
                logger.error(f"No approval request ID found for task {task.task_id}")
                return "handle_error"

            # Get the approval request
            approval_request = await hitl_manager.get_approval_request(request_id)

            if not approval_request:
                logger.error(f"Approval request {request_id} not found")
                return "handle_error"

            # Check the status
            if approval_request.status == "approved":
                logger.info(f"Task {task.task_id} approved")
                task.status = TaskStatus.APPROVED
                task.updated_at = format_timestamp()
                return "execute_task"
            elif approval_request.status == "rejected":
                logger.info(f"Task {task.task_id} rejected")
                task.status = TaskStatus.REJECTED
                task.updated_at = format_timestamp()
                task.error = approval_request.feedback or "Task rejected by user"
                return "handle_rejection"
            elif approval_request.status == "timeout":
                logger.warning(f"Approval for task {task.task_id} timed out")
                task.status = TaskStatus.FAILED
                task.updated_at = format_timestamp()
                task.error = "Approval request timed out"
                return "handle_error"
            else:
                # Still pending, wait and check again
                logger.info(f"Approval for task {task.task_id} still pending")
                return "wait_for_approval"

        async def wait_for_approval(state: GraphState) -> GraphState:
            """Wait for approval and check again."""
            # Wait for a short time before checking again
            await asyncio.sleep(5)
            return state

        async def handle_rejection(state: GraphState) -> GraphState:
            """Handle task rejection."""
            task = state.task
            logger.info(f"Handling rejection for task {task.task_id}")

            # Add a message
            state.messages.append({
                "role": "system",
                "content": f"Task {task.task_id} was rejected: {task.error}"
            })

            return state

        async def handle_error(state: GraphState) -> GraphState:
            """Handle task error."""
            task = state.task
            logger.error(f"Handling error for task {task.task_id}: {task.error}")

            # Update task status
            task.status = TaskStatus.FAILED
            task.updated_at = format_timestamp()

            # Add a message
            state.messages.append({
                "role": "system",
                "content": f"Task {task.task_id} failed: {task.error}"
            })

            return state

        # Create the graph
        self.workflow = StateGraph(GraphState)

        # Add nodes
        self.workflow.add_node("analyze_task", analyze_task)
        self.workflow.add_node("route_task", route_task)
        self.workflow.add_node("execute_task", execute_task)
        self.workflow.add_node("request_approval", request_approval)
        self.workflow.add_node("check_approval", check_approval)
        self.workflow.add_node("wait_for_approval", wait_for_approval)
        self.workflow.add_node("handle_rejection", handle_rejection)
        self.workflow.add_node("handle_error", handle_error)

        # Add edges
        self.workflow.add_edge("analyze_task", "route_task")
        self.workflow.add_edge("route_task", "execute_task")
        self.workflow.add_edge("route_task", "request_approval")
        self.workflow.add_edge("request_approval", "check_approval")
        self.workflow.add_edge("check_approval", "execute_task")
        self.workflow.add_edge("check_approval", "wait_for_approval")
        self.workflow.add_edge("check_approval", "handle_rejection")
        self.workflow.add_edge("check_approval", "handle_error")
        self.workflow.add_edge("wait_for_approval", "check_approval")
        self.workflow.add_edge("execute_task", END)
        self.workflow.add_edge("handle_rejection", END)
        self.workflow.add_edge("handle_error", END)

        # Set the entry point
        self.workflow.set_entry_point("analyze_task")

        # Compile the graph
        self.compiled_workflow = self.workflow.compile()

    async def create_task(
        self,
        title: str,
        description: str,
        task_type: str,
        priority: int = 1,
        require_hitl: bool = True,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Create a new task.

        Args:
            title: The task title.
            description: The task description.
            task_type: The type of task.
            priority: The task priority (1-5).
            require_hitl: Whether human approval is required.
            parameters: Task-specific parameters.

        Returns:
            Task: The created task.
        """
        task_id = generate_task_id()
        now = format_timestamp()

        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            priority=priority,
            require_hitl=require_hitl,
            parameters=parameters or {},
        )

        self._tasks[task_id] = task
        logger.info(f"Created task {task_id}: {title}")

        # Start the workflow in a background task
        asyncio.create_task(self._run_workflow(task))

        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.

        Args:
            task_id: The task ID.

        Returns:
            Optional[Task]: The task, if found.
        """
        return self._tasks.get(task_id)

    async def list_tasks(
        self, status: Optional[str] = None, limit: int = 10, offset: int = 0
    ) -> List[Task]:
        """
        List tasks with optional filtering.

        Args:
            status: Optional status filter.
            limit: Maximum number of tasks to return.
            offset: Number of tasks to skip.

        Returns:
            List[Task]: List of tasks.
        """
        tasks = list(self._tasks.values())

        # Apply status filter if provided
        if status:
            tasks = [task for task in tasks if task.status == status]

        # Sort by created_at (newest first)
        tasks.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        return tasks[offset:offset + limit]

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """
        Cancel a task.

        Args:
            task_id: The task ID.

        Returns:
            Optional[Task]: The cancelled task, if found.
        """
        task = await self.get_task(task_id)
        if not task:
            return None

        # Only cancel if not already completed or failed
        if task.status not in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ]:
            task.status = TaskStatus.CANCELLED
            task.updated_at = format_timestamp()
            logger.info(f"Cancelled task {task_id}")

        return task

    async def _run_workflow(self, task: Task) -> None:
        """
        Run the workflow for a task.

        Args:
            task: The task to process.
        """
        try:
            # Initialize the graph state
            state = {
                "task": task,
                "context": {},
                "messages": [],
            }

            # Run the workflow
            logger.info(f"Starting workflow for task {task.task_id}")
            result = await self.compiled_workflow.ainvoke(state)

            # Update the task with the final state
            final_task = result["task"]
            self._tasks[task.task_id] = final_task

            logger.info(
                f"Workflow completed for task {task.task_id} with status {final_task.status}"
            )
        except Exception as e:
            logger.error(f"Error running workflow for task {task.task_id}: {str(e)}")
            # Update task status to failed
            task.status = TaskStatus.FAILED
            task.updated_at = format_timestamp()
            task.error = str(e)
            self._tasks[task.task_id] = task


# Create a global task manager instance
task_manager = TaskManager()