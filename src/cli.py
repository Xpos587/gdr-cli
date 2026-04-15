"""GDR CLI — Gemini Deep Research via HTTP, shared auth with nlm."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

__version__ = "0.1.0"
from exceptions import GDRError, AuthError

_CID_PREFIX = "c_"


async def _probe_models(profile: str = "default") -> dict:
    """Probe which models are available for the account via RPC."""
    from gemini_webapi.constants import GRPC, Model
    from gemini_webapi.types import RPCData
    from gemini_webapi.utils import extract_json_from_response, get_nested_value

    from auth import AuthManager

    auth = AuthManager(profile)
    cookies = auth.get_cookies()

    from gemini_webapi import GeminiClient
    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init()

    try:
        snapshot = await client.inspect_account_status()

        # Collect available model names from caps/bootstrap probes
        available: set[str] = set()
        dr_available = snapshot["summary"].get("deep_research_feature_present", False)

        # All models if DR is available
        if dr_available:
            for m in Model:
                if m.name != "UNSPECIFIED":
                    available.add(m.value[0])  # real_name

        # Infer tier from model access
        tier = "unknown"
        if dr_available:
            tier = "advanced"
        elif not dr_available:
            # Check if basic models work by testing bootstrap rejection
            bootstrap = snapshot["rpc"].get("bootstrap", {})
            if bootstrap.get("ok", False):
                tier = "plus"
            else:
                tier = "free"

        return {"available_models": available, "tier": tier}
    finally:
        await client.close()


def _display_cid(cid: str) -> str:
    """Strip c_ prefix for user-facing display."""
    return cid.removeprefix(_CID_PREFIX)


def _normalize_cid(cid: str) -> str:
    """Ensure c_ prefix for API calls."""
    if cid and not cid.startswith(_CID_PREFIX):
        return _CID_PREFIX + cid
    return cid


def _handle_api_error(e: Exception) -> int | None:
    """Handle known gemini_webapi exceptions. Returns exit code or None if unhandled."""
    from gemini_webapi.exceptions import UsageLimitExceeded, TemporarilyBlocked

    if isinstance(e, UsageLimitExceeded):
        console.print("[red]Error:[/red] Deep Research usage limit exceeded.")
        console.print("Wait a while or check your Gemini Advanced subscription.")
        return 3
    if isinstance(e, TemporarilyBlocked):
        console.print("[red]Error:[/red] IP temporarily blocked by Google (429).")
        console.print("Try again in a few minutes, use a different proxy, or switch networks.")
        return 3
    return None

app = typer.Typer(
    name="gdr",
    help="Gemini Deep Research CLI — chat and deep research via HTTP, shares auth with nlm",
    no_args_is_help=True,
    add_completion=False,
)
console = Console(stderr=True)


def version_callback(value: bool):
    if value:
        console.print(f"gdr-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit",
    ),
    debug: bool = typer.Option(
        False, "--debug", "-d", help="Enable debug logging from gemini_webapi",
    ),
):
    if not debug:
        from loguru import logger
        logger.remove()
    else:
        from gemini_webapi import set_log_level
        set_log_level("DEBUG")


@app.command()
def chat(
    prompt: Optional[str] = typer.Argument(default=None, help="Message to send to Gemini"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
    continue_chat: Optional[str] = typer.Option(
        None, "--continue", "-c", help="Continue chat by CID, e.g. 1975e4a9e33a362 (omit for last chat)",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Model name, e.g. gemini-3-pro-advanced (default: auto)",
    ),
):
    """Chat with Gemini. No prompt enters interactive mode."""
    import chat as _chat_mod
    from rich.markdown import Markdown

    try:
        metadata = None
        if continue_chat is not None:
            if continue_chat:
                metadata = [_normalize_cid(continue_chat)]
            else:
                chats = asyncio.run(_chat_mod.list_recent_chats(profile=profile))
                if chats:
                    metadata = [chats[0]["cid"]]

        if prompt:
            if metadata:
                response = asyncio.run(_chat_mod.continue_chat(prompt, metadata=metadata, profile=profile, model=model))
            else:
                response = asyncio.run(_chat_mod.send_message(prompt, profile=profile, model=model))
            console.print(Markdown(response))
        else:
            from repl import run_repl
            asyncio.run(run_repl(profile=profile, metadata=metadata, model=model))
    except GDRError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)
    except Exception as e:
        code = _handle_api_error(e)
        if code is not None:
            raise typer.Exit(code)
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


chats_app = typer.Typer(help="Manage Gemini chat sessions", no_args_is_help=True)
app.add_typer(chats_app, name="chats")


@app.command()
def models(
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
):
    """List available Gemini models. Checks which models your account can use."""
    from rich.table import Table
    from gemini_webapi.constants import Model

    table = Table(title="Gemini Models", show_header=True, header_style="bold")
    table.add_column("Model Name", style="cyan")
    table.add_column("Advanced", justify="center")
    table.add_column("Available", justify="center")

    try:
        snapshot = asyncio.run(_probe_models(profile))
        available = snapshot.get("available_models", set())
        tier = snapshot.get("tier", "unknown")
    except Exception as e:
        available = set()
        tier = "unknown"
        console.print(f"[dim]Could not probe models: {e}[/dim]\n")

    for m in Model:
        if m.name == "UNSPECIFIED":
            continue
        real_name, _, thinking = m.value
        status = "[green]Yes[/green]" if real_name in available else "[dim]No[/dim]"
        table.add_row(real_name, "Yes" if thinking else "", status)
    console.print(table)
    if tier != "unknown":
        console.print(f"\n  Detected tier: [bold]{tier}[/bold]")


@chats_app.command(name="list")
def chats_list(
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
):
    """List recent chat conversations."""
    from datetime import datetime
    from chat import list_recent_chats

    try:
        chats = asyncio.run(list_recent_chats(profile=profile))
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
    table.add_column("CID", style="dim")
    table.add_column("Date", style="dim")

    for i, c in enumerate(chats, 1):
        dt = datetime.fromtimestamp(c["timestamp"]).strftime("%Y-%m-%d %H:%M")
        pin = "* " if c.get("is_pinned") else ""
        title = c["title"] or "(untitled)"
        if len(title) > 50:
            title = title[:47] + "..."
        table.add_row(str(i), f"{pin}{title}", _display_cid(c["cid"]), dt)

    console.print(table)


@chats_app.command(name="show")
def chats_show(
    cid: str = typer.Argument(help="Chat ID to display (e.g. 1975e4a9e33a362, with or without c_ prefix)"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of turns to show",
    ),
):
    """Show conversation history for a chat."""
    from chat import read_chat_history

    cid = _normalize_cid(cid)
    try:
        history = asyncio.run(read_chat_history(cid, limit=limit, profile=profile))
    except GDRError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)
    except Exception as e:
        code = _handle_api_error(e)
        if code is not None:
            raise typer.Exit(code)
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if history is None:
        console.print(f"[yellow]Chat not found: {_display_cid(cid)}[/yellow]")
        raise typer.Exit(1)

    console.print(f"[bold]Chat:[/bold] {_display_cid(cid)}")
    console.print(f"[bold]Turns:[/bold] {len(history['turns'])}\n")

    for turn in history["turns"]:
        if turn["role"] == "user":
            console.print(f"[green]You:[/green] {turn['text']}")
        else:
            console.print(f"[blue]Gemini:[/blue] {turn['text']}")
        console.print()


@app.command()
def research(
    query: str = typer.Argument(help="Research topic or question"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Max research time in minutes",
    ),
    poll_interval: float = typer.Option(
        10.0, "--poll", help="Status polling interval in seconds",
    ),
    no_confirm: bool = typer.Option(
        False, "--no-confirm", "-n", help="Skip plan confirmation and start research immediately",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write report to file",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Auto-save report to DIR/{date}-{slug}.md",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Model name, e.g. gemini-3-pro-advanced (default: auto)",
    ),
):
    """Run Gemini Deep Research on a topic."""
    from research import format_result, run_deep_research

    cid_holder: list[str | None] = [None]
    try:
        result = asyncio.run(
            run_deep_research(
                query=query,
                profile=profile,
                timeout_min=timeout,
                poll_interval=poll_interval,
                auto_confirm=no_confirm,
                model=model,
                _cid_holder=cid_holder,
            )
        )
    except GDRError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        code = _handle_api_error(e)
        if code is not None:
            raise typer.Exit(code)
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    report = format_result(result, cid=cid_holder[0])

    out_path = output
    if not out_path and output_dir and result.text:
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9\s-]", "", query.lower()).replace(" ", "-")[:60].rstrip("-")
        out_path = output_dir / f"{date.today()}-{slug}.md"

    if out_path and result.text:
        header = [
            "# Deep Research Report",
            "",
            f"> Query: {query}",
            f"> Status: {'COMPLETED' if result.done else 'INCOMPLETE'}",
            f"> Title: {result.plan.title or '(untitled)'}",
            "",
            result.text,
        ]
        out_path.write_text("\n".join(header), encoding="utf-8")
        console.print(f"\nReport saved to: [bold]{out_path}[/bold]")
    else:
        console.print()
        console.print(report)


@app.command()
def doctor(
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile to check",
    ),
):
    """Diagnose auth and connectivity issues."""
    from auth import AuthManager
    from config import get_cookies_file, get_metadata_file, get_profile_dir

    console.print("[bold]GDR Doctor[/bold]\n")

    auth = AuthManager(profile)

    # 1. Check profile directory
    profile_dir = get_profile_dir(profile)
    if not profile_dir.exists():
        console.print(f"  [red]FAIL[/red] Profile directory not found: {profile_dir}")
        console.print(f"  Run [bold]gdr login[/bold] first to authenticate.")
        raise typer.Exit(1)
    console.print(f"  [green]OK[/green] Profile directory: {profile_dir}")

    # 2. Check cookies file
    cookies_file = get_cookies_file(profile)
    if not cookies_file.exists():
        console.print(f"  [red]FAIL[/red] Cookies file not found: {cookies_file}")
        console.print(f"  Run [bold]gdr login[/bold] first.")
        raise typer.Exit(1)

    try:
        auth.load_profile()
    except AuthError as e:
        console.print(f"  [red]FAIL[/red] Could not load profile: {e.message}")
        raise typer.Exit(1)

    try:
        cookies = auth.get_cookies()
    except AuthError as e:
        console.print(f"  [red]FAIL[/red] {e.message}")
        raise typer.Exit(1)

    console.print(f"  [green]OK[/green] Cookies loaded ({len(cookies)} cookies)")

    # 3. Check required cookies
    required = {"__Secure-1PSID", "__Secure-1PSIDTS"}
    missing = required - set(cookies.keys())
    if missing:
        console.print(f"  [yellow]WARN[/yellow] Missing cookies: {missing}")
    else:
        console.print(f"  [green]OK[/green] Required cookies present")

    # 4. Check metadata
    metadata_file = get_metadata_file(profile)
    if metadata_file.exists():
        import json as _json
        meta = _json.loads(metadata_file.read_text())
        email = meta.get("email", "(unknown)")
        validated = meta.get("last_validated", "(never)")
        console.print(f"  [green]OK[/green] Email: {email}")
        console.print(f"  [green]OK[/green] Last validated: {validated}")
    else:
        console.print(f"  [yellow]WARN[/yellow] No metadata file (optional)")

    # 5. Test Gemini connectivity
    console.print("\n  Testing Gemini connectivity...")
    try:
        tier, dr_status = asyncio.run(_test_connectivity(cookies))
        console.print(f"  [green]OK[/green] Gemini: authenticated and accessible")
        console.print(f"  [green]OK[/green] Subscription: {tier}")
        console.print(f"  [green]OK[/green] Deep Research: {dr_status}")
    except Exception as e:
        console.print(f"  [red]FAIL[/red] Gemini connectivity: {e}")

    console.print()


async def _test_connectivity(cookies: dict[str, str]) -> tuple[str, str]:
    """Test that cookies work with gemini_webapi. Returns (tier, dr_status)."""
    from gemini_webapi import GeminiClient

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=30)

    try:
        snapshot = await client.inspect_account_status()
        summary = snapshot.get("summary", {})
        dr_available = summary.get("deep_research_feature_present", False)

        # Infer tier from probe results
        bootstrap = snapshot["rpc"].get("bootstrap", {})
        if dr_available:
            tier = "advanced"
        elif bootstrap.get("ok", False):
            tier = "plus"
        else:
            tier = "free"

        dr_status = "available" if dr_available else "not available"
        return tier, dr_status
    finally:
        await client.close()


@app.command()
def login(
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name (shared with nlm)",
    ),
    cdp_url: str = typer.Option(
        "http://127.0.0.1:9222", "--cdp-url", help="Chrome CDP endpoint",
    ),
    launch: bool = typer.Option(
        True, "--launch/--no-launch", "-l", help="Auto-launch Chrome if CDP not reachable",
    ),
):
    """Authenticate with Google via Chrome CDP (stores cookies in nlm profile dir)."""
    from cdp import login_via_cdp

    console.print("[bold]GDR Login[/bold]\n")

    try:
        result = asyncio.run(
            _async_login(profile=profile, cdp_url=cdp_url, auto_launch=launch)
        )
    except Exception as e:
        console.print(f"  [red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"  [green]OK[/green] Cookies extracted ({result['cookie_count']} cookies)")
    if result["email"]:
        console.print(f"  [green]OK[/green] Email: {result['email']}")
    console.print(f"  [green]OK[/green] Saved to profile: {profile}")
    console.print()


async def _async_login(
    profile: str, cdp_url: str, auto_launch: bool
) -> dict:
    """Run CDP login in a thread pool (CDP uses sync websocket)."""
    from cdp import login_via_cdp

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, login_via_cdp, profile, cdp_url, auto_launch
    )
