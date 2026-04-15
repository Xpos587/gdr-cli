# Deep Research Report Extraction Workaround

> **For agentic workers:** REQUIRED SUBKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `gdr research` by adding fallback report extraction from chat history when `gemini_webapi` fails to parse the deep research plan.

**Architecture:** When `create_deep_research_plan` raises `GeminiError`, catch it, poll for research completion, then extract the report from chat history via `READ_CHAT` RPC at `data[0][0][3][0][0][30][0][4]`.

**Tech Stack:** Python async, `gemini_webapi` (internal RPC), typer, rich

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/research.py` | Fallback: catch plan error → poll → extract from chat history |
| `src/cli.py` | Research command: handle new `text` field on fallback result |
| `tests/test_research.py` | Tests for fallback path |

## Key References

- `gemini_webapi.constants.GRPC.READ_CHAT` = `"hNvQHb"`
- `gemini_webapi.utils.extract_json_from_response(text)` → list
- Extraction path: `data[0][0][3][0][0][30][0][4]` — 21K+ chars of report text
- `src/research.py:30-71` — current `run_deep_research()`
- `src/research.py:74-96` — current `format_result()`

---

### Task 1: Add `_extract_report_from_chat` helper to research.py

**Files:**
- Modify: `src/research.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_research.py — add to TestExtractReportFromChat class

def test_extracts_report_from_chat_success(self):
    """Verify the helper extracts report from the nested chat data path."""
    mock_client = MagicMock()
    mock_client._batch_execute = AsyncMock(return_value=MagicMock(
        text=")]}'"
    ))
    from gemini_webapi.utils import extract_json_from_response

    # Simulate the actual nested structure
    report_text = "This is the full research report."
    data = [[[[[[[[[None, report_text]]]]]]]]]
    mock_response = MagicMock()
    mock_response.text = ")]}'\n5"
    from unittest.mock import patch
    with patch("research.extract_json_from_response", return_value=[json.dumps([None, json.dumps(data)])]):
        with patch("research.GRPC", READ_CHAT):
            result = asyncio.run(_extract_report_from_chat(mock_client, "c_abc"))

    assert result == report_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_research.py::TestExtractReportFromChat -v`
Expected: FAIL — `_extract_report_from_chat` not defined

- [ ] **Step 3: Implement `_extract_report_from_chat`**

Add to `src/research.py` (after imports, before `run_deep_research`):

```python
import json as _json
from loguru import logger


async def _extract_report_from_chat(client, cid: str) -> str | None:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_research.py::TestExtractReportFromChat -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/research.py tests/test_research.py
git commit -m "feat: add fallback report extraction from chat history"
```

---

### Task 2: Wire fallback into `run_deep_research`

**Files:**
- Modify: `src/research.py:30-71` (run_deep_research function)

- [ ] **Step 1: Write test for fallback path**

```python
# tests/test_research.py

def test_fallback_to_chat_history_on_plan_error(self):
    """When plan extraction fails, research completes and report is extracted from chat."""
    from gemini_webapi.exceptions import GeminiError

    mock_client = MagicMock()
    mock_client.init = AsyncMock()
    mock_client.create_deep_research_plan = AsyncMock(
        side_effect=GeminiError("Gemini did not return a deep research plan.")
    )
    mock_client.close = AsyncMock()

    # Chat history returns a CID for polling
    mock_client.start_chat = MagicMock()
    mock_session = MagicMock()
    mock_session.cid = "c_fallback123"
    mock_client.start_chat.return_value = mock_session

    mock_report = "Fallback research report from chat history."

    with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
        with patch("research.GeminiClient", return_value=mock_client):
            with patch("research._extract_report_from_chat", new_callable=AsyncMock, return_value=mock_report):
                result = asyncio.run(run_deep_research("test", auto_confirm=True))

    assert result.done is True
    assert result.text == mock_report
    mock_client.close.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_research.py::TestRunDeepResearch::test_fallback_to_chat_history_on_plan_error -v`
Expected: FAIL

- [ ] **Step 3: Add fallback logic to `run_deep_research`**

Modify `src/research.py:30-71`. The key change: wrap `create_deep_research_plan` in try/except, and if it fails, still start the research (get CID from `start_chat`), poll for completion, then extract report from chat.

```python
async def run_deep_research(
    query: str,
    profile: str = "default",
    timeout_min: float = 30,
    poll_interval: float = 10.0,
    auto_confirm: bool = True,
    on_status: Callable[[DeepResearchStatus], None] | None = None,
) -> DeepResearchResult:
    auth = AuthManager(profile)
    cookies = auth.get_cookies()

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=timeout_min * 60)

    try:
        plan = await client.create_deep_research_plan(query)
    except Exception:
        plan = None
        logger.warning("Plan extraction failed, using fallback: poll for completion then extract from chat")

    try:
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
            # Fallback: send the query to start research, then poll
            from gemini_webapi.exceptions import UsageLimitExceeded
            try:
                chat = client.start_chat()
                await chat.send_message(query)
                cid = chat.cid
                logger.info(f"Research started, chat CID: {cid}")

                # Poll using deep_research with the original query
                poll_result = await client.deep_research(
                    query,
                    poll_interval=poll_interval,
                    timeout=timeout_min * 60,
                    on_status=_status_callback(MagicMock(title=query), on_status),
                )
                result = poll_result
            except UsageLimitExceeded:
                raise

        # If result has no text but plan extraction failed, try chat history fallback
        if not result.text and plan is None:
            cid = None
            if hasattr(result, 'start_output') and result.start_output:
                # Try to get CID from metadata
                pass
            if not cid:
                chats = client._recent_chats
                if chats:
                    cid = chats[0].cid if hasattr(chats[0], 'cid') else str(chats[0])
            if cid:
                report = await _extract_report_from_chat(client, cid)
                if report:
                    result.text = report
                    result.done = True
    finally:
        await client.close()

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_research.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/research.py tests/test_research.py
git commit -m "feat: fallback to chat history when plan extraction fails"
```

---

### Task 3: Fix `format_result` for fallback case

**Files:**
- Modify: `src/research.py:74-96`

- [ ] **Step 1: Write test**

```python
def test_format_result_no_text_no_plan(self):
    result = MagicMock()
    result.plan = None
    result.statuses = []
    result.done = True
    result.text = ""
    output = format_result(result)
    assert "INCOMPLETE" in output
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_research.py::TestFormatResult::test_format_result_no_text_no_plan -v`
Expected: PASS (likely already passing)

- [ ] **Step 3: Ensure `format_result` handles None plan**

Verify `format_result` doesn't crash when `result.plan is None`. If it accesses `result.plan.title`, add a guard:

```python
def format_result(result: DeepResearchResult) -> str:
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_research.py -q`

- [ ] **Step 5: Commit if changed**

```bash
git add src/research.py
git commit -m "fix: guard format_result against None plan"
```

---

### Task 4: End-to-end test

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ --cov=src --cov-report=term-missing -q
```

Expected: 211+ tests pass, coverage >= 95%

- [ ] **Step 2: Commit all remaining changes**

```bash
git add -A
git commit -m "test: add tests for fallback report extraction"
```

- [ ] **Step 3: Push**

```bash
git push origin master
```

---

## Notes

- The `data[0][0][3][0][0][30][0][4]` path is specific to the "immersive container" format Gemini now uses for research reports
- `_batch_execute` and `_recent_chats` are private methods — using them is fragile but necessary given upstream hasn't fixed this yet
- The fallback path logs warnings via `loguru.logger` — only visible with `--debug`
- When upstream fixes `gemini_webapi`, this fallback becomes dead code and can be removed
