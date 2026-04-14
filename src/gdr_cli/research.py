"""Deep research orchestration using gemini_webapi."""

from __future__ import annotations

import sys
from typing import Callable

from gemini_webapi import GeminiClient
from gemini_webapi.types import DeepResearchPlan, DeepResearchResult, DeepResearchStatus

from gdr_cli.auth import AuthManager


def _status_callback(
    plan: DeepResearchPlan,
    on_status: Callable[[DeepResearchStatus], None] | None,
) -> Callable[[DeepResearchStatus], None]:
    def _callback(status: DeepResearchStatus) -> None:
        state_label = status.state.upper()
        title = status.title or plan.title or "Research"
        print(f"  [{state_label}] {title}", file=sys.stderr)
        if status.notes:
            for note in status.notes[:3]:
                print(f"    - {note}", file=sys.stderr)
        if on_status:
            on_status(status)
    return _callback


async def run_deep_research(
    query: str,
    profile: str = "default",
    timeout_min: float = 30,
    poll_interval: float = 10.0,
    auto_confirm: bool = True,
    on_status: Callable[[DeepResearchStatus], None] | None = None,
) -> DeepResearchResult:
    """Run a full deep research cycle: plan -> confirm -> poll -> result."""
    auth = AuthManager(profile)
    cookies = auth.get_cookies()

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=timeout_min * 60)

    try:
        plan = await client.create_deep_research_plan(query)

        if not auto_confirm:
            print(f"\nResearch Plan: {plan.title}", file=sys.stderr)
            print(f"ETA: {plan.eta_text}", file=sys.stderr)
            for i, step in enumerate(plan.steps, 1):
                print(f"  {i}. {step}", file=sys.stderr)

            try:
                input("\nPress Enter to start research, Ctrl+C to cancel...")
            except (KeyboardInterrupt, EOFError):
                print("\nCancelled.", file=sys.stderr)
                return DeepResearchResult(plan=plan, done=False)

        result = await client.deep_research(
            plan.query or query,
            poll_interval=poll_interval,
            timeout=timeout_min * 60,
            on_status=_status_callback(plan, on_status),
        )
        return result
    finally:
        await client.close()


def format_result(result: DeepResearchResult) -> str:
    """Format a DeepResearchResult for terminal output."""
    lines: list[str] = []

    status = "COMPLETED" if result.done else "INCOMPLETE"
    lines.append(f"Status: {status}")

    if result.plan:
        lines.append(f"Title: {result.plan.title or '(untitled)'}")
        if result.plan.eta_text:
            lines.append(f"ETA: {result.plan.eta_text}")

    if result.statuses:
        lines.append(f"Status updates: {len(result.statuses)}")

    lines.append("")

    if result.text:
        lines.append(result.text)
    else:
        lines.append("(No report text returned)")

    return "\n".join(lines)
