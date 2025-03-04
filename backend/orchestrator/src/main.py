"""
Main module for the Atheon AI Orchestrator.

This module initializes the FastAPI application and sets up routes,
middleware, and event handlers.
"""

import asyncio
import os
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.config import settings

# Initialize FastAPI app
app = FastAPI(
    title="Atheon AI Orchestrator",
    description="Vertical Agent for Task Orchestration and HITL Management",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure logging
logger.remove()
logger.add(
    "logs/orchestrator.log",
    rotation="10 MB",
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message} | {extra}",
)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on application startup."""
    logger.info("Starting Atheon AI Orchestrator")
    # Initialize database connection
    # Initialize Kafka producers/consumers
    # Initialize LLM clients


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up resources on application shutdown."""
    logger.info("Shutting down Atheon AI Orchestrator")
    # Close database connections
    # Close Kafka connections


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for the orchestrator service.

    Returns:
        Dict[str, str]: Health status of the service.
    """
    return {"status": "healthy", "service": "orchestrator"}


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint for the orchestrator service.

    Returns:
        Dict[str, str]: Welcome message.
    """
    return {"message": "Welcome to Atheon AI Orchestrator"}


# Import and include routers
# This should be done after the app is initialized to avoid circular imports
from src.routes import router as api_router

app.include_router(api_router, prefix="/api")