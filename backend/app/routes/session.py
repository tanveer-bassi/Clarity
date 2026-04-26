"""
session.py — Session initialization route.

POST /api/session/init  — creates a Backboard Thread for a new user session.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import backboard_service

router = APIRouter(prefix="/session", tags=["Session"])


class SessionResponse(BaseModel):
    thread_id: str
    is_backboard: bool


@router.post("/init", response_model=SessionResponse)
async def init_session():
    """
    Create a new user session.
    Returns a Backboard Thread ID, or a local UUID fallback if Backboard is not configured.
    Clients store this in localStorage and send it as the X-User-Thread header.
    """
    thread_id = await backboard_service.create_user_thread()
    if thread_id:
        return SessionResponse(thread_id=thread_id, is_backboard=True)
    return SessionResponse(thread_id=str(uuid.uuid4()), is_backboard=False)
