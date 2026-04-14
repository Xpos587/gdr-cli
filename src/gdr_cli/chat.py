"""Regular chat with Gemini via gemini_webapi."""

from __future__ import annotations

from gemini_webapi import GeminiClient

from gdr_cli.auth import AuthManager


async def send_message(
    prompt: str,
    profile: str = "default",
    timeout: float = 120,
) -> str:
    """Send a single message to Gemini and return the text response."""
    auth = AuthManager(profile)
    cookies = auth.get_cookies()

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=timeout)

    try:
        chat = client.start_chat()
        output = await chat.send_message(prompt)
        return output.text or ""
    finally:
        await client.close()
