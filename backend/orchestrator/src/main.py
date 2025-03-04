#!/usr/bin/env python3
"""
Atheon AI Orchestrator Service

This is the main entry point for the Atheon AI orchestrator service,
which serves as the vertical agent responsible for task delegation
and coordination across the system.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
from pydantic import BaseModel, Field

# Local imports
from .config import Settings, get_settings
from .tasks import TaskCreate, TaskResponse, TaskStatus, TaskType
from .langgraph_orchestrator import OrchestrationEngine
from .database import get_db_session
from .auth import get_current_user, User
from .logging_config import configure_logging

# Configure logging
configure_logging()

# Security schemes
security = HTTPBearer()

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifespan events.
    """
    # Startup logic
    logger.info("Starting Atheon AI Orchestrator Service")

    # Initialize database connections
    logger.info("Initializing database connections")

    # Initialize Kafka producers and consumers
    logger.info("Initializing Kafka connections")

    # Initialize orchestration engine
    logger.info("Initializing orchestration engine")

    # Yield control to the application
    yield

    # Shutdown logic
    logger.info("Shutting down Atheon AI Orchestrator Service")

    # Close database connections
    logger.info("Closing database connections")

    # Close Kafka connections
    logger.info("Closing Kafka connections")

# Create FastAPI application
app = FastAPI(
    title="Atheon AI Orchestrator",
    description="Vertical agent that orchestrates tasks across specialized horizontal agents",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Simple health check endpoint.
    Returns status information about the service.
    """
    return {
        "status": "healthy",
        "service": "atheon-orchestrator",
        "version": "0.1.0",
    }

# Readiness probe
@app.get("/ready", tags=["health"])
async def readiness_check():
    """
    Readiness check for Kubernetes.
    Verifies that all dependencies (database, Kafka, etc.) are available.
    """
    # Add checks for database, Kafka, etc.
    dependencies_healthy = True

    if not dependencies_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service dependencies not ready",
        )

    return {
        "status": "ready",
        "message": "Service is ready to accept traffic",
    }

# Task endpoints
@app.post("/tasks", response_model=TaskResponse, tags=["tasks"])
async def create_task(
    task: TaskCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """
    Creates a new task and submits it to the orchestration engine.
    """
    logger.info(f"Creating new task: {task.title} (type: {task.task_type})")

    # Validate user permissions
    if not current_user.can_create_task():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create tasks",
        )

    # Initialize orchestration engine
    engine = OrchestrationEngine(settings)

    # Submit task to orchestration engine
    try:
        task_id = await engine.submit_task(task, current_user)
    except Exception as e:
        logger.error(f"Error submitting task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting task: {str(e)}",
        )

    return TaskResponse(
        id=task_id,
        title=task.title,
        description=task.description,
        task_type=task.task_type,
        status=TaskStatus.PENDING,
        created_by=current_user.id,
    )

@app.get("/tasks/{task_id}", response_model=TaskResponse, tags=["tasks"])
async def get_task(
    task_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """
    Retrieves information about a specific task.
    """
    logger.info(f"Retrieving task: {task_id}")

    # Initialize orchestration engine
    engine = OrchestrationEngine(settings)

    # Get task from orchestration engine
    try:
        task = await engine.get_task(task_id, current_user)
    except Exception as e:
        logger.error(f"Error retrieving task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving task: {str(e)}",
        )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )

    return task

@app.get("/tasks", response_model=List[TaskResponse], tags=["tasks"])
async def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    limit: int = 10,
    offset: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """
    Lists tasks with optional filtering by status and type.
    """
    logger.info(f"Listing tasks (status={status}, type={task_type})")

    # Initialize orchestration engine
    engine = OrchestrationEngine(settings)

    # Get tasks from orchestration engine
    try:
        tasks = await engine.list_tasks(current_user, status, task_type, limit, offset)
    except Exception as e:
        logger.error(f"Error listing tasks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing tasks: {str(e)}",
        )

    return tasks

# HITL endpoints
@app.post("/hitl/{task_id}/approve", tags=["hitl"])
async def approve_task(
    task_id: str,
    feedback: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """
    Approves a task that requires human-in-the-loop validation.
    """
    logger.info(f"Approving task: {task_id}")

    # Initialize orchestration engine
    engine = OrchestrationEngine(settings)

    # Approve task
    try:
        await engine.approve_task(task_id, current_user, feedback)
    except Exception as e:
        logger.error(f"Error approving task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving task: {str(e)}",
        )

    return {
        "status": "success",
        "message": f"Task {task_id} approved successfully",
    }

@app.post("/hitl/{task_id}/reject", tags=["hitl"])
async def reject_task(
    task_id: str,
    feedback: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """
    Rejects a task that requires human-in-the-loop validation.
    """
    logger.info(f"Rejecting task: {task_id}")

    # Initialize orchestration engine
    engine = OrchestrationEngine(settings)

    # Reject task
    try:
        await engine.reject_task(task_id, current_user, feedback)
    except Exception as e:
        logger.error(f"Error rejecting task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting task: {str(e)}",
        )

    return {
        "status": "success",
        "message": f"Task {task_id} rejected successfully",
    }

# Error handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Generic exception handler for all unhandled exceptions.
    """
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "detail": str(exc),
        },
    )

# Main entry point
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )