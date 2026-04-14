# Chat Session Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-turn chat, conversation history, and chat listing to gdr-cli using gemini_webapi's server-side chat session management.

**Architecture:** gemini_webapi stores all chat history server-side. We add a REPL mode for multi-turn conversations, a `chats` command group for listing/showing/deleting conversations, and the ability to continue previous chats by CID. No local history storage needed.

**Tech Stack:** Python 3.12+, gemini_webapi >= 2.0.0, typer, rich, prompt_toolkit (for REPL input with history)

---

## File Structure

```
src/gdr_cli/
├── chat.py          # Expand: multi-turn, list, history functions
├── repl.py          # NEW: interactive REPL loop with prompt_toolkit
├── cli.py           # Modify: chat command optional prompt, add chats group
tests/
├── test_chat.py     # Expand: multi-turn, list, history tests
├── test_repl.py     # NEW: REPL tests
```

---

### Task 1: Expand chat.py with Session Management Functions

**Files:**

- Modify: `src/gdr_cli/chat.py`
- Test: `tests/test_chat.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py` (keep existing tests):

```python
"""Tests for chat.py — session management, multi-turn, listing."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from gdr_cli.chat import list_recent_chats, read_chat_history, continue_chat
from gdr_cli.exceptions import GDRError


class TestListRecentChats:
    def test_returns_chat_info_list(self):
        mock_client = MagicMock()
        mock_chat_info = MagicMock()
        mock_chat_info.cid = "c_abc123"
        mock_chat_info.title = "Test Chat"
        mock_chat_info.is_pinned = False
        mock_chat_info.timestamp = 1745000000.0
        mock_client.list_chats.return_value = [mock_chat_info]

        with patch("gdr_cli.chat._create_client", return_value=mock_client):
            chats = list_recent_chats(profile="default")

        assert len(chats) == 1
        assert chats[0]["cid"] == "c_abc123"
        assert chats[0]["title"] == "Test Chat"

    def test_returns_empty_list_when_no_chats(self):
        mock_client = MagicMock()
        mock_client.list_chats.return_value = []

        with patch("gdr_cli.chat._create_client", return_value=mock_client):
            chats = list_recent_chats(profile="default")

        assert chats == []


class TestReadChatHistory:
    def test_returns_turns(self):
        mock_client = MagicMock()
        mock_turn = MagicMock()
        mock_turn.role = "user"
        mock_turn.text = "Hello"
        mock_history = MagicMock()
        mock_history.cid = "c_abc123"
        mock_history.turns = [mock_turn]
        mock_client.read_chat = AsyncMock(return_value=mock_history)

        with patch("gdr_cli.chat._create_client", return_value=mock_client):
            import asyncio
            history = asyncio.run(read_chat_history("c_abc123", profile="default"))

        assert history["cid"] == "c_abc123"
        assert len(history["turns"]) == 1
        assert history["turns"][0]["role"] == "user"

    def test_returns_none_when_chat_not_found(self):
        mock_client = MagicMock()
        mock_client.read_chat = AsyncMock(return_value=None)

        with patch("gdr_cli.chat._create_client", return_value=mock_client):
            import asyncio
            history = asyncio.run(read_chat_history("c_nonexistent", profile="default"))

        assert history is None


class TestContinueChat:
    def test_sends_followup_message(self):
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.metadata = ["c_abc", "r_def", "rc_ghi"]
        mock_session.cid = "c_abc"
        mock_session.rid = "r_def"
        mock_output = MagicMock()
        mock_output.text = "The capital is Berlin."
        mock_output.metadata = ["c_abc", "r_new", "rc_new"]
        mock_session.send_message = AsyncMock(return_value=mock_output)
        mock_client.start_chat.return_value = mock_session

        with patch("gdr_cli.chat._create_client", return_value=mock_client):
            import asyncio
            result = asyncio.run(continue_chat("What about Germany?", metadata=["c_abc", "r_def", "rc_ghi"], profile="default"))

        assert result == "The capital is Berlin."
        mock_client.start_chat.assert_called_once_with(metadata=["c_abc", "r_def", "rc_ghi"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/pytest tests/test_chat.py -v`
Expected: FAIL with `ImportError: cannot import name 'list_recent_chats'`

- [ ] **Step 3: Expand chat.py**

Replace `src/gdr_cli/chat.py` entirely:

```python
"""Chat session management via gemini_webapi.

All chat history is stored server-side by Google. We only manage
metadata references (cid, rid, rcid) for session continuity.
"""

from __future__ import annotations

from typing import Any

from gemini_webapi import GeminiClient

from gdr_cli.auth import AuthManager


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/pytest tests/test_chat.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/chat.py tests/test_chat.py
git commit -m "feat: add multi-turn chat, history, and listing functions"
```

---

### Task 2: Add prompt_toolkit Dependency

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Add prompt_toolkit**

Run: `cd /home/michael/Github/gdr-cli && uv add prompt-toolkit>=3.0.0`

This adds the dependency to pyproject.toml and uv.lock.

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/pytest -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add pyproject.toml uv.lock
git commit -m "build: add prompt_toolkit for REPL input"
```

---

### Task 3: Create Interactive REPL

**Files:**

- Create: `src/gdr_cli/repl.py`
- Create: `tests/test_repl.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_repl.py`:

```python
"""Tests for repl.py — interactive chat REPL."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from gdr_cli.repl import ChatRepl


class TestChatReplInit:
    def test_creates_repl_with_defaults(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default")
            mock_create.assert_called_once()
            mock_client.start_chat.assert_called_once()

    def test_creates_repl_with_metadata(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default", metadata=["c_abc", "r_def", "rc_ghi"])
            mock_client.start_chat.assert_called_once_with(metadata=["c_abc", "r_def", "rc_ghi"])


class TestChatReplSend:
    def test_send_message_updates_session(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_output = MagicMock()
            mock_output.text = "Hello!"
            mock_output.metadata = ["c_abc", "r_new", "rc_new"]
            mock_session.send_message = AsyncMock(return_value=mock_output)
            mock_session.cid = "c_abc"
            mock_session.rid = "r_new"
            mock_session.rcid = "rc_new"
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            import asyncio
            repl = ChatRepl(profile="default")
            text = asyncio.run(repl.send("Hi there"))

            assert text == "Hello!"
            assert repl.metadata == ["c_abc", "r_new", "rc_new"]

    def test_send_empty_message_raises(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_client.start_chat.return_value = MagicMock()
            mock_create.return_value = mock_client

            import asyncio
            repl = ChatRepl(profile="default")

            with pytest.raises(ValueError, match="empty"):
                asyncio.run(repl.send(""))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/pytest tests/test_repl.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gdr_cli.repl'`

- [ ] **Step 3: Create repl.py**

Create `src/gdr_cli/repl.py`:

```python
"""Interactive REPL for multi-turn Gemini chat."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text

from gdr_cli.auth import AuthManager
from gdr_cli.chat import _create_client

console = Console(stderr=True)

GEMINI_COLOR = "blue"
USER_COLOR = "green"

# REPL commands (prefix with /)
COMMANDS = {
    "/quit": "Exit the chat",
    "/history": "Show conversation history (current session)",
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
    ):
        self.profile = profile
        self.metadata: list[str] | None = None
        self._client = None
        self._session = None

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
        self._session = self._client.start_chat(**kwargs)

    async def send(self, prompt: str) -> str:
        """Send a message and return the response text.

        Updates self.metadata after each message for session continuity.
        """
        if not prompt.strip():
            raise ValueError("Cannot send empty message")

        output = await self._session.send_message(prompt)
        self.metadata = output.metadata

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
) -> None:
    """Run the interactive REPL loop."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory

    repl = ChatRepl(profile=profile, metadata=metadata)

    try:
        await repl.start()

        if repl.metadata:
            console.print(f"[dim]Resumed chat: {repl.cid}[/dim]")
        else:
            console.print("[dim]New chat started. Type /quit to exit.[/dim]")

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/pytest tests/test_repl.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/repl.py tests/test_repl.py
git commit -m "feat: add interactive REPL for multi-turn chat"
```

---

### Task 4: Update CLI — chat command + chats group

**Files:**

- Modify: `src/gdr_cli/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
class TestChatRepl:
    def test_chat_no_args_shows_help(self):
        # When no prompt given, should still work (enters REPL mode)
        # We can't test REPL interactively, but we can check it doesn't error on invocation
        pass  # REPL mode tested in test_repl.py

    def test_chats_list_help(self):
        result = runner.invoke(app, ["chats", "list", "--help"])
        assert result.exit_code == 0

    def test_chats_show_help(self):
        result = runner.invoke(app, ["chats", "show", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Update cli.py**

In `src/gdr_cli/cli.py`, make these changes:

**A) Make the `prompt` argument optional in the `chat` command.**

Find:
```python
@app.command()
def chat(
    prompt: str = typer.Argument(help="Message to send to Gemini"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
):
    """Send a message to Gemini and get a response (quick test)."""
    from gdr_cli.chat import send_message

    try:
        response = asyncio.run(send_message(prompt, profile=profile))
    except GDRError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(response)
```

Replace with:
```python
@app.command()
def chat(
    prompt: Optional[str] = typer.Argument(default=None, help="Message to send to Gemini"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
    continue_chat: Optional[str] = typer.Option(
        None, "--continue", "-c", help="Continue chat by CID (last chat if empty string)",
    ),
):
    """Chat with Gemini. No prompt enters interactive REPL mode."""
    from gdr_cli.repl import run_repl

    try:
        metadata = None
        if continue_chat is not None:
            if continue_chat:
                metadata = [continue_chat]
            else:
                # Empty -c means continue last chat
                from gdr_cli.chat import list_recent_chats
                chats = list_recent_chats(profile=profile)
                if chats:
                    metadata = [chats[0]["cid"]]

        asyncio.run(run_repl(profile=profile, metadata=metadata))
    except GDRError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
```

**B) Add `chats` command group.**

After the `chat` command function, add:

```python
chats_app = typer.Typer(help="Manage Gemini chat sessions", no_args_is_help=True)
app.add_typer(chats_app, name="chats")


@chats_app.command(name="list")
def chats_list(
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
):
    """List recent chat conversations."""
    from datetime import datetime
    from gdr_cli.chat import list_recent_chats

    try:
        chats = list_recent_chats(profile=profile)
    except GDRError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)

    if not chats:
        console.print("No recent chats found.")
        return

    from rich.table import Table

    table = Table(title="Recent Chats")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="bold", max_width=50)
    table.add_column("CID", style="dim", max_width=20)
    table.add_column("Date", style="dim")

    for i, c in enumerate(chats, 1):
        dt = datetime.fromtimestamp(c["timestamp"]).strftime("%Y-%m-%d %H:%M")
        pin = "📌 " if c.get("is_pinned") else ""
        table.add_row(str(i), f"{pin}{c['title']}", c["cid"][:16] + "...", dt)

    console.print(table)


@chats_app.command()
def chats_show(
    cid: str = typer.Argument(help="Chat ID to display"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of turns to show",
    ),
):
    """Show conversation history for a chat."""
    from gdr_cli.chat import read_chat_history

    try:
        history = asyncio.run(read_chat_history(cid, limit=limit, profile=profile))
    except GDRError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)

    if history is None:
        console.print(f"[yellow]Chat not found: {cid}[/yellow]")
        raise typer.Exit(1)

    console.print(f"[bold]Chat:[/bold] {cid}")
    console.print(f"[bold]Turns:[/bold] {len(history['turns'])}\n")

    for turn in history["turns"]:
        if turn["role"] == "user":
            console.print(f"[green]You:[/green] {turn['text']}")
        else:
            console.print(f"[blue]Gemini:[/blue] {turn['text']}")
        console.print()
```

**C) Update the imports at the top of cli.py.** Ensure `Optional` is already imported (it is).

- [ ] **Step 3: Run all tests**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/pytest -v`
Expected: All pass

- [ ] **Step 4: Verify CLI commands**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/gdr --help`
Expected: Shows `chat` and `chats` commands

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/gdr chats --help`
Expected: Shows `list` and `show` subcommands

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/gdr chats list --help`
Expected: Shows `--profile` option

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/cli.py tests/test_cli.py
git commit -m "feat: add REPL mode to chat, add chats list/show commands"
```

---

### Task 5: Update README

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Add chat session docs**

Add a new section after the existing Chat section in README.md. Find:

```markdown
### Chat

```bash
gdr chat "Explain the difference between TCP and UDP"
```
```

Replace with:

```markdown
### Chat

Single message:
```bash
gdr chat "Explain the difference between TCP and UDP"
```

Interactive REPL (multi-turn):
```bash
gdr chat
```

Continue last conversation:
```bash
gdr chat -c
```

Continue specific chat by ID:
```bash
gdr chat -c c_abc123...
```

REPL commands: `/quit`, `/cid`, `/help`

### Manage Chats

List recent conversations:
```bash
gdr chats list
```

Show conversation history:
```bash
gdr chats show c_abc123...
```
```

Also update the Commands table. Find:

```markdown
| `gdr chat <prompt>` | Send a message to Gemini |
```

Replace with:

```markdown
| `gdr chat [prompt]` | Chat with Gemini (no prompt = interactive REPL) |
| `gdr chat -c [cid]` | Continue a previous conversation |
| `gdr chats list` | List recent chat sessions |
| `gdr chats show <cid>` | Show conversation history |
```

- [ ] **Step 2: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add README.md
git commit -m "docs: add multi-turn chat and session management to README"
```

---

### Task 6: Final Integration Test

**Files:**

- None (testing only)

- [ ] **Step 1: Run full test suite**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/pytest -v`
Expected: All tests pass

- [ ] **Step 2: Verify CLI smoke tests**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/gdr --help`
Expected: Shows `chat` and `chats` commands

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/gdr chats list`
Expected: Lists recent chats from Gemini (requires auth)

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/gdr chats --help`
Expected: Shows `list` and `show` subcommands

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/gdr chat --help`
Expected: Shows `--continue` option, prompt is optional

- [ ] **Step 3: Test REPL mode manually**

Run: `cd /home/michael/Github/gdr-cli && .venv/bin/gdr chat`
Expected: Shows `You> ` prompt, accepts messages, `/quit` exits

- [ ] **Step 4: Final commit if any fixes needed**

```bash
cd /home/michael/Github/gdr-cli
git add -A
git commit -m "fix: integration test fixes for chat sessions"
```
