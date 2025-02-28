"""
Human-in-the-Loop (HITL) module for the Atheon AI Orchestrator.

This module provides functions for managing human approval workflows
and integrating with LangGraph for HITL decision points.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger
from pydantic import BaseModel, Field

from src.config import settings
from src.utils import format_timestamp


class ApprovalStatus(str, Enum):
    """Enum for approval status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ApprovalRequest(BaseModel):
    """Model for HITL approval requests."""

    request_id: str = Field(..., description="Unique request identifier")
    task_id: str = Field(..., description="Associated task identifier")
    title: str = Field(..., description="Request title")
    description: str = Field(..., description="Request description")
    data: Dict[str, Any] = Field(..., description="Data to be approved")
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING, description="Current approval status"
    )
    created_at: str = Field(..., description="Creation timestamp")
    expires_at: str = Field(..., description="Expiration timestamp")
    approved_at: Optional[str] = Field(
        default=None, description="Approval timestamp"
    )
    approved_by: Optional[str] = Field(
        default=None, description="User who approved/rejected"
    )
    feedback: Optional[str] = Field(
        default=None, description="Feedback for rejection"
    )


class HITLManager:
    """Manager for Human-in-the-Loop workflows."""

    def __init__(self) -> None:
        """Initialize the HITL manager."""
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._approval_timeout = settings.hitl_approval_timeout

    async def create_approval_request(
        self,
        task_id: str,
        title: str,
        description: str,
        data: Dict[str, Any],
    ) -> ApprovalRequest:
        """
        Create a new approval request.

        Args:
            task_id: The associated task ID.
            title: The request title.
            description: The request description.
            data: The data to be approved.

        Returns:
            ApprovalRequest: The created approval request.
        """
        request_id = f"req-{task_id}-{len(self._pending_approvals) + 1}"
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self._approval_timeout)

        request = ApprovalRequest(
            request_id=request_id,
            task_id=task_id,
            title=title,
            description=description,
            data=data,
            created_at=format_timestamp(now),
            expires_at=format_timestamp(expires_at),
        )

        self._pending_approvals[request_id] = request
        logger.info(f"Created approval request {request_id} for task {task_id}")

        # Start a background task to handle timeout
        asyncio.create_task(self._handle_approval_timeout(request_id))

        return request

    async def get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """
        Get an approval request by ID.

        Args:
            request_id: The request ID.

        Returns:
            Optional[ApprovalRequest]: The approval request, if found.
        """
        return self._pending_approvals.get(request_id)

    async def list_pending_approvals(self) -> List[ApprovalRequest]:
        """
        List all pending approval requests.

        Returns:
            List[ApprovalRequest]: List of pending approval requests.
        """
        return [
            req
            for req in self._pending_approvals.values()
            if req.status == ApprovalStatus.PENDING
        ]

    async def approve_request(
        self, request_id: str, user_id: str, feedback: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        """
        Approve a request.

        Args:
            request_id: The request ID.
            user_id: The user ID who approved.
            feedback: Optional feedback.

        Returns:
            Optional[ApprovalRequest]: The updated approval request, if found.
        """
        request = await self.get_approval_request(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return None

        request.status = ApprovalStatus.APPROVED
        request.approved_at = format_timestamp()
        request.approved_by = user_id
        request.feedback = feedback

        logger.info(f"Request {request_id} approved by user {user_id}")
        return request

    async def reject_request(
        self, request_id: str, user_id: str, feedback: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        """
        Reject a request.

        Args:
            request_id: The request ID.
            user_id: The user ID who rejected.
            feedback: Optional feedback.

        Returns:
            Optional[ApprovalRequest]: The updated approval request, if found.
        """
        request = await self.get_approval_request(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return None

        request.status = ApprovalStatus.REJECTED
        request.approved_at = format_timestamp()
        request.approved_by = user_id
        request.feedback = feedback

        logger.info(f"Request {request_id} rejected by user {user_id}")
        return request

    async def _handle_approval_timeout(self, request_id: str) -> None:
        """
        Handle approval timeout.

        Args:
            request_id: The request ID.
        """
        request = await self.get_approval_request(request_id)
        if not request:
            return

        # Parse the expiration timestamp
        expires_at = datetime.fromisoformat(request.expires_at.rstrip("Z"))
        now = datetime.utcnow()

        # Calculate seconds to wait
        wait_seconds = (expires_at - now).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        # Check if the request is still pending
        request = await self.get_approval_request(request_id)
        if request and request.status == ApprovalStatus.PENDING:
            request.status = ApprovalStatus.TIMEOUT
            logger.warning(f"Request {request_id} timed out")


# Create a global HITL manager instance
hitl_manager = HITLManager()