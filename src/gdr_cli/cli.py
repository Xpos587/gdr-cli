"""GDR CLI — Gemini Deep Research via HTTP, shared auth with nlm."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from gdr_cli import __version__

app = typer.Typer(
    name="gdr",
    help="Gemini CLI — chat and deep research via HTTP, shares auth with nlm",
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
):
    pass


@app.command()
def chat(
    prompt: str = typer.Argument(help="Message to send to Gemini"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="nlm auth profile name",
    ),
):
    """Send a message to Gemini and get a response (quick test)."""
    from gdr_cli.chat import send_message

    try:
        response = asyncio.run(send_message(prompt, profile=profile))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        from gemini_webapi.exceptions import AuthError as GeminiAuthError

        if isinstance(e, GeminiAuthError):
            console.print(f"[red]Auth Error:[/red] {e}")
            console.print("Run [bold]nlm login[/bold] to re-authenticate.")
            raise typer.Exit(2)
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(response)


@app.command()
def research(
    query: str = typer.Argument(help="Research topic or question"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="nlm auth profile name",
    ),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Max research time in minutes",
    ),
    poll_interval: float = typer.Option(
        10.0, "--poll", help="Status polling interval in seconds",
    ),
    no_confirm: bool = typer.Option(
        False, "--no-confirm", "-n", help="Show plan and wait for manual confirmation",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write report to file",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Auto-save report to DIR/{date}-{slug}.md",
    ),
):
    """Run Gemini Deep Research on a topic."""
    from gdr_cli.research import format_result, run_deep_research

    try:
        result = asyncio.run(
            run_deep_research(
                query=query,
                profile=profile,
                timeout_min=timeout,
                poll_interval=poll_interval,
                auto_confirm=not no_confirm,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        from gemini_webapi.exceptions import AuthError as GeminiAuthError, UsageLimitExceeded

        if isinstance(e, GeminiAuthError):
            console.print(f"[red]Auth Error:[/red] {e}")
            console.print("Run [bold]nlm login[/bold] to re-authenticate.")
            raise typer.Exit(2)
        if isinstance(e, UsageLimitExceeded):
            console.print("[red]Error:[/red] Deep Research usage limit exceeded.")
            console.print("Wait a while or check your Gemini Advanced subscription.")
            raise typer.Exit(3)
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    report = format_result(result)

    # Determine output path
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
        "default", "--profile", "-p", help="nlm auth profile to check",
    ),
):
    """Diagnose auth and connectivity issues."""
    from gdr_cli.config import get_cookies_file, get_metadata_file, get_profile_dir

    console.print("[bold]GDR Doctor[/bold]\n")

    # 1. Check profile directory
    profile_dir = get_profile_dir(profile)
    if not profile_dir.exists():
        console.print(f"  [red]FAIL[/red] Profile directory not found: {profile_dir}")
        console.print(f"  Run [bold]nlm login[/bold] first to authenticate.")
        raise typer.Exit(1)
    console.print(f"  [green]OK[/green] Profile directory: {profile_dir}")

    # 2. Check cookies file
    cookies_file = get_cookies_file(profile)
    if not cookies_file.exists():
        console.print(f"  [red]FAIL[/red] Cookies file not found: {cookies_file}")
        console.print(f"  Run [bold]nlm login[/bold] first.")
        raise typer.Exit(1)

    try:
        from gdr_cli.auth import load_cookies
        cookies = load_cookies(cookies_file)
    except Exception as e:
        console.print(f"  [red]FAIL[/red] Could not load cookies: {e}")
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
        meta = json.loads(metadata_file.read_text())
        email = meta.get("email", "(unknown)")
        validated = meta.get("last_validated", "(never)")
        console.print(f"  [green]OK[/green] Email: {email}")
        console.print(f"  [green]OK[/green] Last validated: {validated}")
    else:
        console.print(f"  [yellow]WARN[/yellow] No metadata file (optional)")

    # 5. Test Gemini connectivity
    console.print("\n  Testing Gemini connectivity...")
    try:
        result = asyncio.run(_test_connectivity(cookies))
        if result:
            console.print(f"  [green]OK[/green] Gemini: authenticated and accessible")
            console.print(f"  [green]OK[/green] Deep Research: {result}")
        else:
            console.print(f"  [red]FAIL[/red] Gemini returned no access token")
    except Exception as e:
        console.print(f"  [red]FAIL[/red] Gemini connectivity: {e}")

    console.print()


async def _test_connectivity(cookies: dict[str, str]) -> str | None:
    """Test that cookies work with gemini_webapi."""
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
        return "available" if dr_available else "not available (check subscription)"
    finally:
        await client.close()


@app.command()
def login(
    profile: str = typer.Option(
        "default", "--profile", "-p", help="nlm profile to use",
    ),
):
    """Authenticate via nlm (delegates to 'nlm login')."""
    nlm_path = shutil.which("nlm")
    if not nlm_path:
        console.print("[red]Error:[/red] nlm CLI not found in PATH.")
        console.print("Install it first: [bold]uv tool install notebooklm-mcp-cli[/bold]")
        raise typer.Exit(1)

    result = subprocess.run([nlm_path, "login", "--profile", profile])
    raise typer.Exit(result.returncode)
