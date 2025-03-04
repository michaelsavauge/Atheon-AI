#!/usr/bin/env python3
"""
LangGraph Orchestration Engine

This module implements the multi-agent orchestration system using LangGraph,
allowing for task routing, delegation, and human-in-the-loop integration.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field

from langchain_core.tools import Tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# Local imports
from .tasks import TaskCreate, TaskResponse, TaskStatus, TaskType
from .config import Settings
from .kafka_client import KafkaClient
from .humanlayer_client import HumanLayerClient
from .database import TaskRepository, AgentRepository

# Type definitions
State = Dict[str, Any]

class AgentState(BaseModel):
    """The state passed between agents in the orchestration graph."""
    task_id: str
    task_type: TaskType
    status: TaskStatus
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    requires_approval: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class OrchestrationEngine:
    """
    The orchestration engine that manages task routing, delegation,
    and human-in-the-loop integration using LangGraph.
    """

    def __init__(self, settings: Settings):
        """
        Initialize the orchestration engine with configuration settings.

        Args:
            settings: The application settings.
        """
        self.settings = settings
        self.task_repo = TaskRepository()
        self.agent_repo = AgentRepository()
        self.kafka_client = KafkaClient(settings.kafka_bootstrap_servers)

        # Initialize HumanLayer client for HITL
        self.humanlayer_client = HumanLayerClient(
            api_key=settings.humanlayer_api_key,
            project_id=settings.humanlayer_project_id
        )

        # Initialize LLM clients
        self.claude_llm = ChatAnthropic(
            model="claude-3-sonnet-20240229",
            temperature=0.1,
            api_key=settings.anthropic_api_key,
        )

        self.gpt4_llm = ChatOpenAI(
            model="gpt-4-turbo",
            temperature=0.1,
            api_key=settings.openai_api_key,
        )

        # Initialize the orchestration graph
        self.graph = self._build_orchestration_graph()

    def _build_orchestration_graph(self) -> StateGraph:
        """
        Build the LangGraph orchestration graph.

        Returns:
            StateGraph: The orchestration graph.
        """
        # Define the tools available to the agents
        tools = [
            Tool(
                name="summarize_text",
                description="Summarize a piece of text",
                func=self._route_to_summarization_agent,
            ),
            Tool(
                name="scrape_web",
                description="Scrape data from a webpage",
                func=self._route_to_scraper_agent,
            ),
            Tool(
                name="fetch_api_data",
                description="Fetch data from an external API",
                func=self._route_to_data_fetcher_agent,
            ),
            Tool(
                name="transcribe_audio",
                description="Transcribe audio content",
                func=self._route_to_transcription_agent,
            ),
            Tool(
                name="ask_human",
                description="Get human input on a task",
                func=self._route_to_human,
            ),
        ]

        # Create the tool execution node
        tools_node = ToolNode(tools)

        # Define state transitions
        def should_route_to_agent(state: AgentState) -> str:
            """Determine the next step based on task type and status."""
            if state.errors and len(state.errors) > 3:
                return "handle_error"

            if state.status == TaskStatus.REQUIRES_APPROVAL:
                return "wait_for_human"

            if state.status == TaskStatus.COMPLETED:
                return END

            # Route to the appropriate agent based on task type
            return "route_task"

        # Create the graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("route_task", self._route_task)
        workflow.add_node("execute_task", tools_node)
        workflow.add_node("wait_for_human", self._wait_for_human_approval)
        workflow.add_node("handle_error", self._handle_error)

        # Add edges
        workflow.add_conditional_edges(
            "route_task",
            should_route_to_agent,
            {
                "execute_task": "execute_task",
                "wait_for_human": "wait_for_human",
                "handle_error": "handle_error",
            }
        )
        workflow.add_edge("execute_task", "route_task")
        workflow.add_edge("wait_for_human", "route_task")
        workflow.add_edge("handle_error", "route_task")

        # Compile the graph
        return workflow.compile()

    def _route_task(self, state: AgentState) -> AgentState:
        """
        Route a task to the appropriate agent based on its type.

        Args:
            state: The current state of the task.

        Returns:
            AgentState: The updated state.
        """
        logger.info(f"Routing task {state.task_id} of type {state.task_type}")

        # For demonstration, simply update the state to indicate routing
        state.context["routing_timestamp"] = str(asyncio.get_event_loop().time())

        # Determine if the task requires human approval before processing
        if state.requires_approval and state.status != TaskStatus.APPROVED:
            state.status = TaskStatus.REQUIRES_APPROVAL
            logger.info(f"Task {state.task_id} requires human approval")
            return state

        # Route to the appropriate agent based on task type
        if state.task_type == TaskType.SUMMARIZATION:
            return self._prepare_summarization_task(state)
        elif state.task_type == TaskType.WEB_SCRAPING:
            return self._prepare_scraping_task(state)
        elif state.task_type == TaskType.API_FETCH:
            return self._prepare_api_fetch_task(state)
        elif state.task_type == TaskType.TRANSCRIPTION:
            return self._prepare_transcription_task(state)
        else:
            state.errors.append(f"Unsupported task type: {state.task_type}")
            return state

    def _prepare_summarization_task(self, state: AgentState) -> AgentState:
        """Prepare state for summarization task."""
        state.context["agent"] = "summarization"
        state.status = TaskStatus.IN_PROGRESS
        return state

    def _prepare_scraping_task(self, state: AgentState) -> AgentState:
        """Prepare state for web scraping task."""
        state.context["agent"] = "scraper"
        state.status = TaskStatus.IN_PROGRESS
        return state

    def _prepare_api_fetch_task(self, state: AgentState) -> AgentState:
        """Prepare state for API fetch task."""
        state.context["agent"] = "data_fetcher"
        state.status = TaskStatus.IN_PROGRESS
        return state

    def _prepare_transcription_task(self, state: AgentState) -> AgentState:
        """Prepare state for transcription task."""
        state.context["agent"] = "transcription"
        state.status = TaskStatus.IN_PROGRESS
        return state

    async def _route_to_summarization_agent(self, text: str) -> str:
        """Route a text summarization task to the summarization agent via Kafka."""
        try:
            topic = "summarization_requests"
            message = {
                "task_id": str(uuid.uuid4()),
                "text": text,
                "parameters": {
                    "max_length": 100,
                    "format": "bullet_points"
                }
            }

            await self.kafka_client.produce_message(topic, message)
            logger.info(f"Routed summarization task to Kafka topic: {topic}")

            # In a real implementation, we would wait for the result from a response topic
            return "Summarization task submitted for processing"
        except Exception as e:
            logger.error(f"Error routing to summarization agent: {str(e)}")
            raise

    async def _route_to_scraper_agent(self, url: str) -> str:
        """Route a web scraping task to the scraper agent via Kafka."""
        try:
            topic = "scrape_requests"
            message = {
                "task_id": str(uuid.uuid4()),
                "url": url,
                "parameters": {
                    "elements": ["h1", "p", "a"],
                    "max_depth": 1
                }
            }

            await self.kafka_client.produce_message(topic, message)
            logger.info(f"Routed scraping task to Kafka topic: {topic}")

            # In a real implementation, we would wait for the result from a response topic
            return "Scraping task submitted for processing"
        except Exception as e:
            logger.error(f"Error routing to scraper agent: {str(e)}")
            raise

    async def _route_to_data_fetcher_agent(self, api_endpoint: str) -> str:
        """Route an API fetch task to the data fetcher agent via Kafka."""
        try:
            topic = "data_fetch_requests"
            message = {
                "task_id": str(uuid.uuid4()),
                "endpoint": api_endpoint,
                "parameters": {
                    "method": "GET",
                    "headers": {"Accept": "application/json"}
                }
            }

            await self.kafka_client.produce_message(topic, message)
            logger.info(f"Routed API fetch task to Kafka topic: {topic}")

            # In a real implementation, we would wait for the result from a response topic
            return "API fetch task submitted for processing"
        except Exception as e:
            logger.error(f"Error routing to data fetcher agent: {str(e)}")
            raise

    async def _route_to_transcription_agent(self, audio_url: str) -> str:
        """Route a transcription task to the transcription agent via Kafka."""
        try:
            topic = "transcription_requests"
            message = {
                "task_id": str(uuid.uuid4()),
                "audio_url": audio_url,
                "parameters": {
                    "language": "en",
                    "model": "whisper-large-v3"
                }
            }

            await self.kafka_client.produce_message(topic, message)
            logger.info(f"Routed transcription task to Kafka topic: {topic}")

            # In a real implementation, we would wait for the result from a response topic
            return "Transcription task submitted for processing"
        except Exception as e:
            logger.error(f"Error routing to transcription agent: {str(e)}")
            raise

    async def _route_to_human(self, question: str) -> str:
        """Route a question to a human via HumanLayer."""
        try:
            # Submit the task to HumanLayer
            task_id = await self.humanlayer_client.create_task(
                task_type="question",
                content=question,
                metadata={"source": "atheon_orchestrator"}
            )

            logger.info(f"Routed question to human via HumanLayer: {task_id}")

            # In a real implementation, we would wait for the human response
            return f"Question submitted to human for response (task_id: {task_id})"
        except Exception as e:
            logger.error(f"Error routing to human: {str(e)}")
            raise

    def _wait_for_human_approval(self, state: AgentState) -> AgentState:
        """
        Wait for human approval on a task.

        Args:
            state: The current state of the task.

        Returns:
            AgentState: The updated state.
        """
        logger.info(f"Task {state.task_id} waiting for human approval")

        # In a real implementation, we would check if the task has been approved or rejected
        # For now, we'll just update the state to indicate it's waiting
        state.context["waiting_since"] = str(asyncio.get_event_loop().time())

        # The actual approval would come through an API endpoint
        # When approved, status would change to APPROVED
        # When rejected, status would change to REJECTED

        return state

    def _handle_error(self, state: AgentState) -> AgentState:
        """
        Handle errors in task processing.

        Args:
            state: The current state of the task.

        Returns:
            AgentState: The updated state.
        """
        logger.error(f"Handling errors for task {state.task_id}: {state.errors}")

        # Log the error
        error_message = "; ".join(state.errors)
        state.context["error_handling_timestamp"] = str(asyncio.get_event_loop().time())

        # Determine if we should retry or fail the task
        if len(state.errors) <= 3:
            # Retry the task
            logger.info(f"Retrying task {state.task_id}")
            state.status = TaskStatus.PENDING
            state.errors = []  # Clear errors for retry
        else:
            # Mark the task as failed
            logger.info(f"Task {state.task_id} failed after multiple retries")
            state.status = TaskStatus.FAILED
            state.result = {"error": error_message}

        return state

    async def submit_task(self, task: TaskCreate, user: Any) -> str:
        """
        Submit a new task to the orchestration engine.

        Args:
            task: The task to submit.
            user: The user submitting the task.

        Returns:
            str: The ID of the created task.
        """
        task_id = str(uuid.uuid4())
        logger.info(f"Submitting new task: {task_id}")

        # Create the initial state
        state = AgentState(
            task_id=task_id,
            task_type=task.task_type,
            status=TaskStatus.PENDING,
            parameters=task.parameters,
            requires_approval=task.requires_approval,
            metadata={
                "created_by": str(user.id),
                "created_at": str(asyncio.get_event_loop().time()),
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
            }
        )

        # Store the task in the database
        await self.task_repo.create_task(
            task_id=task_id,
            title=task.title,
            description=task.description,
            task_type=task.task_type,
            status=TaskStatus.PENDING,
            created_by=user.id,
            requires_approval=task.requires_approval,
            priority=task.priority,
            parameters=task.parameters,
        )

        # Start the task processing in the background
        asyncio.create_task(self._process_task(state))

        return task_id

    async def _process_task(self, state: AgentState) -> None:
        """
        Process a task using the orchestration graph.

        Args:
            state: The initial state of the task.
        """
        try:
            logger.info(f"Processing task {state.task_id}")

            # Execute the graph
            for output in self.graph.stream(state):
                # Update the task status in the database
                current_state = cast(AgentState, output)
                await self.task_repo.update_task_status(
                    task_id=current_state.task_id,
                    status=current_state.status,
                )

                # If the task is completed, update the result
                if current_state.status == TaskStatus.COMPLETED and current_state.result:
                    await self.task_repo.update_task_result(
                        task_id=current_state.task_id,
                        result=current_state.result,
                    )

                # If the task failed, update the error message
                if current_state.status == TaskStatus.FAILED and current_state.errors:
                    await self.task_repo.update_task_error(
                        task_id=current_state.task_id,
                        error_message="; ".join(current_state.errors),
                    )

            logger.info(f"Task {state.task_id} processing completed")
        except Exception as e:
            logger.error(f"Error processing task {state.task_id}: {str(e)}")
            await self.task_repo.update_task_status(
                task_id=state.task_id,
                status=TaskStatus.FAILED,
            )
            await self.task_repo.update_task_error(
                task_id=state.task_id,
                error_message=str(e),
            )

    async def get_task(self, task_id: str, user: Any) -> Optional[TaskResponse]:
        """
        Get information about a specific task.

        Args:
            task_id: The ID of the task to retrieve.
            user: The user requesting the task.

        Returns:
            Optional[TaskResponse]: The task information, or None if not found.
        """
        return await self.task_repo.get_task(task_id)

    async def list_tasks(
        self,
        user: Any,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[TaskResponse]:
        """
        List tasks with optional filtering.

        Args:
            user: The user requesting the tasks.
            status: Optional status filter.
            task_type: Optional task type filter.
            limit: Maximum number of tasks to return.
            offset: Number of tasks to skip.

        Returns:
            List[TaskResponse]: The matching tasks.
        """
        return await self.task_repo.list_tasks(
            created_by=user.id,
            status=status,
            task_type=task_type,
            limit=limit,
            offset=offset,
        )

    async def approve_task(self, task_id: str, user: Any, feedback: Optional[str] = None) -> None:
        """
        Approve a task that requires human validation.

        Args:
            task_id: The ID of the task to approve.
            user: The user approving the task.
            feedback: Optional feedback from the user.
        """
        logger.info(f"Approving task {task_id}")

        # Check if the task exists and requires approval
        task = await self.task_repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        if task.status != TaskStatus.REQUIRES_APPROVAL:
            raise ValueError(f"Task {task_id} does not require approval (status: {task.status})")

        # Update the task status
        await self.task_repo.update_task_status(
            task_id=task_id,
            status=TaskStatus.APPROVED,
        )

        # Record the approval
        await self.task_repo.record_approval(
            task_id=task_id,
            approved_by=user.id,
            feedback=feedback,
        )

        # Resume task processing in the background
        state = AgentState(
            task_id=task_id,
            task_type=task.task_type,
            status=TaskStatus.APPROVED,
            parameters=task.parameters or {},
            requires_approval=False,  # No longer requires approval
            metadata={
                "title": task.title,
                "description": task.description,
                "approved_by": str(user.id),
                "approved_at": str(asyncio.get_event_loop().time()),
            }
        )

        asyncio.create_task(self._process_task(state))

    async def reject_task(self, task_id: str, user: Any, feedback: str) -> None:
        """
        Reject a task that requires human validation.

        Args:
            task_id: The ID of the task to reject.
            user: The user rejecting the task.
            feedback: Feedback explaining the rejection.
        """
        logger.info(f"Rejecting task {task_id}")

        # Check if the task exists and requires approval
        task = await self.task_repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        if task.status != TaskStatus.REQUIRES_APPROVAL:
            raise ValueError(f"Task {task_id} does not require approval (status: {task.status})")

        # Update the task status
        await self.task_repo.update_task_status(
            task_id=task_id,
            status=TaskStatus.REJECTED,
        )

        # Record the rejection
        await self.task_repo.record_rejection(
            task_id=task_id,
            rejected_by=user.id,
            feedback=feedback,
        )

        # No need to resume processing for rejected tasks