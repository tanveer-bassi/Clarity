"""
dependencies.py — Shared FastAPI dependencies.
"""

from __future__ import annotations

from fastapi import Header, HTTPException


async def get_thread_id(x_user_thread: str = Header(default=None)) -> str:
    """
    Extract the user's Backboard Thread ID from the X-User-Thread request header.
    Clients obtain this from POST /api/session/init and store it in localStorage.
    """
    if not x_user_thread:
        raise HTTPException(
            status_code=401,
            detail="Missing X-User-Thread header. Call POST /api/session/init first.",
        )
    return x_user_thread
