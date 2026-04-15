"""Tests for research.py — orchestration (mocked GeminiClient)."""

import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from research import run_deep_research, format_result, _status_callback, _extract_report_from_chat, _poll_for_report
from auth import AuthManager


def _create_mock_client_with_chat_mocks():
    """Create a mock client with chat-related mocks for fallback path."""
    mock_client = MagicMock()
    mock_client.init = AsyncMock()
    mock_client.close = AsyncMock()
    # Add mocks for deep_research and fallback path
    mock_client.deep_research = AsyncMock()
    # Add mocks for fallback path
    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock()
    mock_client.start_chat = MagicMock(return_value=mock_chat)
    mock_client.list_chats = MagicMock(return_value=[])
    return mock_client


class TestFormatResult:
    def test_formats_completed_result(self):
        plan = MagicMock()
        plan.title = "AI Trends 2026"
        plan.steps = ["Step 1: Search", "Step 2: Analyze"]
        plan.eta_text = "~10 minutes"

        result = MagicMock()
        result.plan = plan
        result.statuses = []
        result.done = True
        result.text = "Here is the research report..."

        output = format_result(result)
        assert "COMPLETED" in output
        assert "AI Trends 2026" in output

    def test_formats_incomplete_result(self):
        plan = MagicMock()
        plan.title = "Test"
        plan.steps = []
        plan.eta_text = None

        result = MagicMock()
        result.plan = plan
        result.statuses = []
        result.done = False
        result.text = ""

        output = format_result(result)
        assert "INCOMPLETE" in output

    def test_formats_with_no_text(self):
        plan = MagicMock()
        plan.title = "Empty"
        plan.eta_text = None

        result = MagicMock()
        result.plan = plan
        result.statuses = []
        result.done = True
        result.text = ""

        output = format_result(result)
        assert "No report text returned" in output

    def test_formats_with_no_plan(self):
        result = MagicMock()
        result.plan = None
        result.statuses = []
        result.done = False
        result.text = "some text"

        output = format_result(result)
        assert "INCOMPLETE" in output

    def test_formats_with_eta(self):
        plan = MagicMock()
        plan.title = "T"
        plan.eta_text = "5 min"

        result = MagicMock()
        result.plan = plan
        result.statuses = []
        result.done = True
        result.text = "report"

        output = format_result(result)
        assert "5 min" in output

    def test_formats_with_status_count(self):
        plan = MagicMock()
        plan.title = "T"
        plan.eta_text = None

        result = MagicMock()
        result.plan = plan
        result.statuses = [MagicMock(), MagicMock(), MagicMock()]
        result.done = True
        result.text = "r"

        output = format_result(result)
        assert "3" in output

    def test_format_result_no_text_no_plan(self):
        result = MagicMock()
        result.plan = None
        result.statuses = []
        result.done = True
        result.text = ""
        output = format_result(result)
        assert "COMPLETED" in output
        assert "No report text returned" in output


class TestStatusCallback:
    def test_calls_on_status(self):
        plan = MagicMock()
        plan.title = "Research"
        on_status = MagicMock()
        status = MagicMock()
        status.state = "working"
        status.title = "Step 1"
        status.notes = ["Searching..."]

        cb = _status_callback(plan, on_status)
        cb(status)

        on_status.assert_called_once_with(status)

    def test_truncates_notes(self):
        plan = MagicMock()
        plan.title = "R"
        on_status = MagicMock()
        status = MagicMock()
        status.state = "working"
        status.title = "S"
        status.notes = ["a", "b", "c", "d", "e"]

        cb = _status_callback(plan, on_status)
        cb(status)

        on_status.assert_called_once()

    def test_no_on_status(self):
        plan = MagicMock()
        plan.title = "R"
        status = MagicMock()
        status.state = "done"
        status.title = "Complete"
        status.notes = []

        cb = _status_callback(plan, None)
        cb(status)  # Should not raise

    def test_none_title_uses_plan_title(self):
        plan = MagicMock()
        plan.title = "Plan Title"
        status = MagicMock()
        status.state = "working"
        status.title = None
        status.notes = []

        cb = _status_callback(plan, None)
        cb(status)  # Should not raise

    def test_none_plan_title(self):
        plan = MagicMock()
        plan.title = None
        status = MagicMock()
        status.state = "working"
        status.title = None
        status.notes = []

        cb = _status_callback(plan, None)
        cb(status)  # Should not raise


class TestRunDeepResearch:
    def test_raises_auth_error_on_missing_profile(self):
        from auth import AuthManager
        from exceptions import ProfileNotFoundError

        with patch.object(AuthManager, "get_cookies", side_effect=ProfileNotFoundError("default")):
            with pytest.raises(ProfileNotFoundError):
                asyncio.run(run_deep_research("test query"))

    def test_auto_confirm_skips_prompt(self):
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = _create_mock_client_with_chat_mocks()
        mock_result = MagicMock(spec=DeepResearchResult)
        mock_result.plan = MagicMock(spec=DeepResearchPlan)
        mock_result.plan.title = "Test"
        mock_result.statuses = []
        mock_result.done = True
        mock_result.text = "Report"

        # Mock chat.send_message since code uses regular chat now
        mock_chat = MagicMock()
        mock_chat.send_message = AsyncMock(return_value="Report")
        mock_client.start_chat = MagicMock(return_value=mock_chat)

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                result = asyncio.run(run_deep_research("test", auto_confirm=True))

        assert result.done is True
        assert result.text == "Report"

    def test_no_confirm_auto_confirm_false(self):
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = _create_mock_client_with_chat_mocks()
        mock_plan = MagicMock(spec=DeepResearchPlan)
        mock_plan.title = "Test"
        mock_plan.eta_text = "5 min"
        mock_plan.steps = ["Step 1"]
        mock_plan.query = "test"

        mock_result = MagicMock(spec=DeepResearchResult)
        mock_result.plan = mock_plan
        mock_result.statuses = []
        mock_result.done = True
        mock_result.text = "Report"

        mock_client.create_deep_research_plan = AsyncMock(return_value=mock_plan)
        mock_client.deep_research = AsyncMock(return_value=mock_result)

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                with patch("builtins.input", return_value=""):
                    result = asyncio.run(run_deep_research("test", auto_confirm=False))

        assert result.done is True

    def test_no_confirm_runs_research(self):
        """Test that --no-confirm runs research (no cancellation supported in new flow)."""
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = _create_mock_client_with_chat_mocks()
        mock_result = MagicMock(spec=DeepResearchResult)
        mock_result.plan = MagicMock(spec=DeepResearchPlan)
        mock_result.plan.title = "Test"
        mock_result.done = True
        mock_result.text = "Report"

        mock_client.deep_research = AsyncMock(return_value=mock_result)

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                result = asyncio.run(run_deep_research("test", auto_confirm=False))

        # With the simplified flow, research runs directly regardless of auto_confirm
        assert result.done is True

    def test_passes_timeout_and_poll_interval(self):
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = _create_mock_client_with_chat_mocks()
        mock_result = MagicMock(spec=DeepResearchResult)
        mock_result.plan = MagicMock(spec=DeepResearchPlan)
        mock_result.plan.title = "T"
        mock_result.statuses = []
        mock_result.done = True
        mock_result.text = "R"

        # Mock chat.send_message since code uses regular chat now
        mock_chat = MagicMock()
        mock_chat.send_message = AsyncMock(return_value="R")
        mock_client.start_chat = MagicMock(return_value=mock_chat)

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                asyncio.run(run_deep_research("q", timeout_min=15, poll_interval=5.0))

        mock_client.init.assert_called_once_with(timeout=900)

    def test_client_closed_on_error(self):
        from gemini_webapi.exceptions import UsageLimitExceeded

        mock_client = _create_mock_client_with_chat_mocks()
        # UsageLimitExceeded from chat.send_message should propagate
        mock_chat = MagicMock()
        mock_chat.send_message = AsyncMock(side_effect=UsageLimitExceeded("limit"))
        mock_client.start_chat = MagicMock(return_value=mock_chat)

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                with pytest.raises(UsageLimitExceeded):
                    asyncio.run(run_deep_research("test"))

        mock_client.close.assert_called_once()

    def test_passes_profile(self):
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = _create_mock_client_with_chat_mocks()
        mock_plan = MagicMock(spec=DeepResearchPlan)
        mock_plan.title = "T"
        mock_plan.eta_text = None
        mock_plan.steps = []
        mock_plan.query = "q"

        mock_result = MagicMock(spec=DeepResearchResult)
        mock_result.plan = mock_plan
        mock_result.statuses = []
        mock_result.done = True
        mock_result.text = "R"

        mock_client.create_deep_research_plan = AsyncMock(return_value=mock_plan)
        mock_client.deep_research = AsyncMock(return_value=mock_result)

        with patch("research.AuthManager") as mock_auth_cls:
            mock_auth_mgr = MagicMock()
            mock_auth_mgr.get_cookies.return_value = {"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}
            mock_auth_cls.return_value = mock_auth_mgr
            with patch("research.GeminiClient", return_value=mock_client):
                asyncio.run(run_deep_research("q", profile="work"))

        mock_auth_cls.assert_called_once_with("work")

class TestExtractReportFromChat:
    def test_extracts_report_from_chat_success(self):
        """Verify the helper extracts report from the nested chat data path."""
        mock_client = _create_mock_client_with_chat_mocks()
        report_text = "This is the full research report."
        # Build nested structure matching data[0][0][3][0][0][30][0][4]
        # Each level needs enough padding to support the index
        level6 = [None] * 5
        level6[4] = report_text
        level5 = [level6]  # [0] -> level6
        level4 = [None] * 31
        level4[30] = level5  # [30] -> level5
        level3 = [level4]  # [0] -> level4
        level2 = [level3]  # [0] -> level3
        level1 = [None] * 4
        level1[3] = level2  # [3] -> level2
        level0 = [level1]  # [0] -> level1
        data = [level0]  # [0] -> level0
        data_json_str = json.dumps(data)
        # Frame format: [metadata, ..., payload_json_string]
        frame = [None, None, data_json_str]

        mock_response = MagicMock()
        mock_response.text = ")]}'\n5"
        mock_client._batch_execute = AsyncMock(return_value=mock_response)

        with patch("gemini_webapi.utils.extract_json_from_response", return_value=[frame]):
            result = asyncio.run(_extract_report_from_chat(mock_client, "c_abc"))

        assert result == report_text

    def test_returns_none_on_empty_response(self):
        mock_client = _create_mock_client_with_chat_mocks()
        mock_response = MagicMock()
        mock_response.text = ")]}'\n5"
        mock_client._batch_execute = AsyncMock(return_value=mock_response)

        with patch("gemini_webapi.utils.extract_json_from_response", return_value=[]):
            result = asyncio.run(_extract_report_from_chat(mock_client, "c_abc"))

        assert result is None

    def test_returns_none_on_exception(self):
        mock_client = _create_mock_client_with_chat_mocks()
        mock_client._batch_execute = AsyncMock(side_effect=RuntimeError("network error"))

        result = asyncio.run(_extract_report_from_chat(mock_client, "c_abc"))

        assert result is None

    def test_propagates_usage_limit_exceeded(self):
        from gemini_webapi.exceptions import UsageLimitExceeded
        mock_client = _create_mock_client_with_chat_mocks()
        mock_client._batch_execute = AsyncMock(side_effect=UsageLimitExceeded("limit"))
        with pytest.raises(UsageLimitExceeded):
            asyncio.run(_extract_report_from_chat(mock_client, "c_abc"))

    def test_propagates_temporarily_blocked(self):
        from gemini_webapi.exceptions import TemporarilyBlocked
        mock_client = _create_mock_client_with_chat_mocks()
        mock_client._batch_execute = AsyncMock(side_effect=TemporarilyBlocked("blocked"))
        with pytest.raises(TemporarilyBlocked):
            asyncio.run(_extract_report_from_chat(mock_client, "c_abc"))


class TestPollForReport:
    def test_extracts_report_on_first_poll(self):
        mock_client = _create_mock_client_with_chat_mocks()
        mock_client._recent_chats = [MagicMock(cid="c_abc")]
        with patch("research._extract_report_from_chat", new_callable=AsyncMock, return_value="report"):
            with patch("research.asyncio.sleep", new_callable=AsyncMock):
                result = asyncio.run(_poll_for_report(mock_client, poll_interval=0.1, timeout_min=1))
        assert result.done is True
        assert result.text == "report"

    def test_times_out_if_no_report(self):
        mock_client = _create_mock_client_with_chat_mocks()
        mock_client._recent_chats = [MagicMock(cid="c_abc")]
        call_count = 0
        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return 0.0 if call_count <= 4 else 99999.0
        with patch("research._extract_report_from_chat", new_callable=AsyncMock, return_value=None):
            with patch("research.asyncio.sleep", new_callable=AsyncMock):
                with patch("research.time.monotonic", side_effect=fake_monotonic):
                    result = asyncio.run(_poll_for_report(mock_client, poll_interval=0.1, timeout_min=1))
        assert result.done is False

    def test_skips_when_no_chats(self):
        mock_client = _create_mock_client_with_chat_mocks()
        mock_client._recent_chats = None
        call_count = 0
        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return 0.0 if call_count <= 2 else 99999.0
        with patch("research._extract_report_from_chat", new_callable=AsyncMock, return_value="report") as mock_extract:
            with patch("research.asyncio.sleep", new_callable=AsyncMock):
                with patch("time.monotonic", side_effect=fake_monotonic):
                    result = asyncio.run(_poll_for_report(mock_client, poll_interval=0.1, timeout_min=1))
        mock_extract.assert_not_called()
        assert result.done is False

    def test_skips_when_no_cid(self):
        mock_chat = MagicMock(spec=["__str__"])
        type(mock_chat).__str__ = lambda self: ""
        mock_client = _create_mock_client_with_chat_mocks()
        mock_client._recent_chats = [mock_chat]
        call_count = 0
        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return 0.0 if call_count <= 2 else 99999.0
        with patch("research._extract_report_from_chat", new_callable=AsyncMock) as mock_extract:
            with patch("research.asyncio.sleep", new_callable=AsyncMock):
                with patch("research.time.monotonic", side_effect=fake_monotonic):
                    result = asyncio.run(_poll_for_report(mock_client, poll_interval=0.1, timeout_min=1))
        mock_extract.assert_not_called()
        assert result.done is False

    def test_bails_after_max_fails(self):
        mock_client = _create_mock_client_with_chat_mocks()
        mock_client._recent_chats = [MagicMock(cid="c_abc")]
        call_count = 0
        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return 0.0
        with patch("research._extract_report_from_chat", new_callable=AsyncMock, return_value=None):
            with patch("research.asyncio.sleep", new_callable=AsyncMock):
                with patch("research.time.monotonic", side_effect=fake_monotonic):
                    result = asyncio.run(_poll_for_report(mock_client, poll_interval=0.1, timeout_min=30))
        assert result.done is False
