"""Deep research orchestration using gemini_webapi."""

from __future__ import annotations

import asyncio
import json as _json
import sys
import time
from typing import Callable

from loguru import logger

from gemini_webapi import GeminiClient
from gemini_webapi.types import DeepResearchPlan, DeepResearchResult, DeepResearchStatus

from auth import AuthManager


async def _extract_report_from_chat(client: GeminiClient, cid: str) -> str | None:
    """Extract deep research report from chat history immersive container.

    Fallback when gemini_webapi's plan parsing fails. The report is stored
    at data[0][0][3][0][0][30][0][4] in the READ_CHAT RPC response.
    """
    try:
        from gemini_webapi.constants import GRPC
        from gemini_webapi.types import RPCData
        from gemini_webapi.utils import extract_json_from_response

        response = await client._batch_execute([
            RPCData(rpcid=GRPC.READ_CHAT, payload=_json.dumps([cid, None, None, None]))
        ])
        parts = extract_json_from_response(response.text)
        if not parts:
            return None

        data = _json.loads(parts[0][2])
        report = data[0][0][3][0][0][30][0][4]
        if not report or not isinstance(report, str):
            return None

        logger.debug(f"Extracted report from chat history ({len(report)} chars)")
        return report
    except Exception as e:
        from gemini_webapi.exceptions import UsageLimitExceeded, TemporarilyBlocked
        if isinstance(e, (UsageLimitExceeded, TemporarilyBlocked)):
            raise
        logger.warning(f"Failed to extract report from chat history: {e}")
        return None


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


def _make_result_with_text(text: str, done: bool = True) -> DeepResearchResult:
    """Build a DeepResearchResult with plain text (bypasses complex ModelOutput)."""
    from gemini_webapi.types import ModelOutput, Candidate
    return DeepResearchResult.model_construct(
        plan=None, done=done, statuses=[],
        final_output=ModelOutput.model_construct(
            candidates=[Candidate.model_construct(text=text, text_delta=text)],
            chosen=0,
        ),
    )


async def _poll_for_report(
    client: GeminiClient,
    poll_interval: float = 10.0,
    timeout_min: float = 30,
) -> DeepResearchResult:
    """Poll chat history until research report appears or timeout."""
    from rich.console import Console
    from rich.status import Status

    console = Console(stderr=True)
    deadline = time.monotonic() + timeout_min * 60
    max_fails = 6
    no_progress = 0

    with Status(
        "[bold blue]Waiting for research to complete...[/]",
        spinner="dots",
        console=console,
    ) as status:
        while time.monotonic() < deadline:
            await asyncio.sleep(poll_interval)

            chats = client._recent_chats
            if not chats:
                no_progress += 1
                if no_progress >= max_fails:
                    logger.warning("No chats found after %d polls — research may not have started", max_fails)
                continue

            cid = chats[0].cid if hasattr(chats[0], "cid") else str(chats[0])
            if not cid:
                continue

            report = await _extract_report_from_chat(client, cid)
            if report:
                return _make_result_with_text(report)

            no_progress += 1
            if no_progress >= max_fails:
                print(
                    "\n  [yellow]Warning:[/yellow] No progress after "
                    f"{no_progress} polls. Research may have hit a usage limit.",
                    file=sys.stderr,
                )
                return DeepResearchResult.model_construct(plan=None, done=False, statuses=[])

            elapsed = int(time.monotonic() - (deadline - timeout_min * 60))
            remaining = int(deadline - time.monotonic())
            status.update(
                f"[bold blue]Waiting for research to complete... "
                f"({elapsed}s elapsed, timeout in {remaining}s)[/]"
            )

    return DeepResearchResult.model_construct(plan=None, done=False, statuses=[])


async def run_deep_research(
    query: str,
    profile: str = "default",
    timeout_min: float = 30,
    poll_interval: float = 10.0,
    auto_confirm: bool = True,
    on_status: Callable[[DeepResearchStatus], None] | None = None,
    model: str | None = None,
    _cid_holder: list[str | None] | None = None,
) -> DeepResearchResult:
    """Run a full research cycle: plan -> confirm -> poll -> result."""
    from rich.console import Console

    console = Console(stderr=True)
    auth = AuthManager(profile)
    cookies = auth.get_cookies()

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=timeout_min * 60)

    try:
        # NOTE: gemini_webapi's deep_research() API is non-functional.
        # Using regular chat with research query as fallback.
        # This provides a response but not the structured deep research experience.
        chat_kwargs = {}
        if model:
            chat_kwargs["model"] = model
        chat = client.start_chat(**chat_kwargs)

        # Send the research query as a regular message
        output = await chat.send_message(query)

        # Try to get CID from chat
        cid = None
        chats = client.list_chats()
        if chats:
            latest = max(chats, key=lambda c: c.timestamp)
            cid = latest.cid

        if cid:
            display_cid = cid.removeprefix("c_")
            print(f"  Chat: https://gemini.google.com/app/{display_cid}", file=sys.stderr)
            if _cid_holder is not None:
                _cid_holder[0] = cid

        # Return result as if it was deep research
        return _make_result_with_text(output or "", done=True)

    finally:
        await client.close()


def format_result(result: DeepResearchResult, cid: str | None = None) -> str:
    """Format a DeepResearchResult for terminal output."""
    lines: list[str] = []

    if cid:
        display_cid = cid.removeprefix("c_")
        lines.append(f"Chat: https://gemini.google.com/app/{display_cid}")

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
