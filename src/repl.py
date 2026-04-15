"""Interactive REPL for multi-turn Gemini chat."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from rich.console import Console
from rich.markdown import Markdown

from chat import _create_client

console = Console(stderr=True)

COMMANDS = {
    "/quit": "Exit the chat",
    "/history": "Show conversation history (current session turns)",
    "/help": "Show available commands",
    "/cid": "Show current chat ID",
}


class ChatRepl:
    """Interactive multi-turn chat session with Gemini."""

    def __init__(
        self,
        *,
        profile: str = "default",
        metadata: list[str] | None = None,
        model: str | None = None,
    ):
        self.profile = profile
        self.metadata = metadata
        self.model = model
        self._client = None
        self._session = None
        self._turn_count: int = 0

    @property
    def cid(self) -> str | None:
        if self._session:
            return self._session.cid
        return None

    @property
    def is_active(self) -> bool:
        return self._client is not None

    async def start(self) -> None:
        """Initialize the client and chat session."""
        self._client = await _create_client(self.profile)
        kwargs: dict[str, Any] = {}
        if self.metadata:
            kwargs["metadata"] = self.metadata
        if self.model:
            kwargs["model"] = self.model
        self._session = self._client.start_chat(**kwargs)

    async def send(self, prompt: str) -> str:
        """Send a message and return the response text."""
        if not prompt.strip():
            raise ValueError("Cannot send empty message")

        output = await self._session.send_message(prompt)
        self.metadata = output.metadata
        self._turn_count += 1

        return output.text or ""

    async def close(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.close()
            self._client = None
            self._session = None


def _format_response(text: str) -> None:
    """Print a Gemini response with Rich formatting."""
    console.print()
    console.print(Markdown(text))


async def run_repl(
    *,
    profile: str = "default",
    metadata: list[str] | None = None,
    model: str | None = None,
) -> None:
    """Run the interactive REPL loop."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory

    repl = ChatRepl(profile=profile, metadata=metadata, model=model)

    try:
        await repl.start()

        if repl.metadata:
            console.print(f"[dim]Resumed chat: {repl.cid}[/dim]")
        else:
            console.print("[dim]New chat started. Type /help for commands, /quit to exit.[/dim]")

        console.print()

        session = PromptSession(history=InMemoryHistory())

        while True:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: session.prompt(
                        [("class:prompt", "You> ")],
                    )
                )
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input.strip().lower()
                if cmd == "/quit":
                    break
                elif cmd == "/cid":
                    cid = repl.cid or "(none)"
                    console.print(f"  Chat ID: {cid}")
                    continue
                elif cmd == "/help":
                    for name, desc in COMMANDS.items():
                        console.print(f"  [bold]{name}[/bold] — {desc}")
                    continue
                elif cmd == "/history":
                    console.print(f"  Turns in this session: {repl._turn_count}")
                    continue
                else:
                    console.print(f"  [yellow]Unknown command: {cmd}[/yellow]")
                    console.print(f"  Type /help for available commands.")
                    continue

            # Send message
            try:
                response = await repl.send(user_input)
                _format_response(response)
            except ValueError as e:
                console.print(f"  [yellow]{e}[/yellow]")
            except Exception as e:
                console.print(f"  [red]Error:[/red] {e}")
                break

    finally:
        await repl.close()
        console.print("\n[dim]Chat ended.[/dim]")
