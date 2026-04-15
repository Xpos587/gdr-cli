"""Deep research orchestration using gemini_webapi."""

from __future__ import annotations

import json as _json
import sys
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
        try:
            plan = await client.create_deep_research_plan(query)
        except Exception as e:
            # UsageLimitExceeded must propagate — don't swallow it
            from gemini_webapi.exceptions import UsageLimitExceeded
            if isinstance(e, UsageLimitExceeded):
                raise
            plan = None
            logger.warning("Plan extraction failed, using fallback: poll for completion then extract from chat")

        if plan and not auto_confirm:
            print(f"\nResearch Plan: {plan.title}", file=sys.stderr)
            print(f"ETA: {plan.eta_text}", file=sys.stderr)
            for i, step in enumerate(plan.steps, 1):
                print(f"  {i}. {step}", file=sys.stderr)

            try:
                input("\nPress Enter to start research, Ctrl+C to cancel...")
            except (KeyboardInterrupt, EOFError):
                print("\nCancelled.", file=sys.stderr)
                return DeepResearchResult(plan=plan, done=False)

        if plan:
            result = await client.deep_research(
                plan.query or query,
                poll_interval=poll_interval,
                timeout=timeout_min * 60,
                on_status=_status_callback(plan, on_status),
            )
        else:
            result = await client.deep_research(
                query,
                poll_interval=poll_interval,
                timeout=timeout_min * 60,
                on_status=_status_callback(type("P", (), {"title": query})(), on_status),
            )

        # Fallback: if no text and plan failed, try extracting from chat history
        if not result.text and plan is None:
            chats = client._recent_chats
            cid = None
            if chats:
                cid = chats[0].cid if hasattr(chats[0], "cid") else str(chats[0])
            if cid:
                report = await _extract_report_from_chat(client, cid)
                if report:
                    result.text = report
                    result.done = True

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
