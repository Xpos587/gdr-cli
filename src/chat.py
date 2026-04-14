"""Chat session management via gemini_webapi.

All chat history is stored server-side by Google. We only manage
metadata references (cid, rid, rcid) for session continuity.
"""

from __future__ import annotations

from typing import Any

from gemini_webapi import GeminiClient

from auth import AuthManager


async def _create_client(profile: str = "default", timeout: float = 120) -> GeminiClient:
    """Create and initialize a GeminiClient from profile cookies."""
    auth = AuthManager(profile)
    cookies = auth.get_cookies()

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=timeout)
    return client


async def send_message(
    prompt: str,
    profile: str = "default",
    timeout: float = 120,
) -> str:
    """Send a single message to Gemini and return the text response."""
    client = await _create_client(profile, timeout)
    try:
        chat = client.start_chat()
        output = await chat.send_message(prompt)
        return output.text or ""
    finally:
        await client.close()


async def continue_chat(
    prompt: str,
    *,
    metadata: list[str] | None = None,
    profile: str = "default",
    timeout: float = 120,
) -> str:
    """Send a follow-up message in an existing conversation.

    Args:
        prompt: Message to send.
        metadata: Previous session's [cid, rid, rcid] to continue.
        profile: Auth profile name.
        timeout: Client initialization timeout.

    Returns:
        Response text.
    """
    client = await _create_client(profile, timeout)
    try:
        kwargs: dict[str, Any] = {}
        if metadata:
            kwargs["metadata"] = metadata
        chat = client.start_chat(**kwargs)
        output = await chat.send_message(prompt)
        return output.text or ""
    finally:
        await client.close()


def list_recent_chats(
    profile: str = "default",
    timeout: float = 30,
) -> list[dict[str, Any]]:
    """List recent conversations from Gemini server.

    Returns list of dicts with keys: cid, title, is_pinned, timestamp.
    """
    import asyncio
    client = asyncio.run(_create_client(profile, timeout))

    try:
        chats = client.list_chats()
        if not chats:
            return []

        return [
            {
                "cid": c.cid,
                "title": c.title,
                "is_pinned": c.is_pinned,
                "timestamp": c.timestamp,
            }
            for c in chats
        ]
    finally:
        asyncio.run(client.close())


async def read_chat_history(
    cid: str,
    *,
    limit: int = 20,
    profile: str = "default",
    timeout: float = 30,
) -> dict[str, Any] | None:
    """Read conversation history for a given chat ID.

    Returns dict with keys: cid, turns (list of {role, text}).
    Returns None if chat not found.
    """
    client = await _create_client(profile, timeout)

    try:
        history = await client.read_chat(cid, limit=limit)
        if history is None:
            return None

        return {
            "cid": history.cid,
            "turns": [
                {
                    "role": turn.role,
                    "text": turn.text,
                }
                for turn in history.turns
            ],
        }
    finally:
        await client.close()


async def delete_chat(
    cid: str,
    *,
    profile: str = "default",
    timeout: float = 30,
) -> None:
    """Delete a conversation from Gemini server."""
    client = await _create_client(profile, timeout)

    try:
        await client.delete_chat(cid)
    finally:
        await client.close()
