"""Tests for research.py — orchestration (mocked GeminiClient)."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from research import run_deep_research, format_result, _status_callback
from auth import AuthManager


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

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
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
        mock_client.close = AsyncMock()

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                result = asyncio.run(run_deep_research("test", auto_confirm=True))

        assert result.done is True
        assert result.text == "Report"

    def test_no_confirm_auto_confirm_false(self):
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
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
        mock_client.close = AsyncMock()

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                with patch("builtins.input", return_value=""):
                    result = asyncio.run(run_deep_research("test", auto_confirm=False))

        assert result.done is True

    def test_no_confirm_cancelled(self):
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_plan = MagicMock(spec=DeepResearchPlan)
        mock_plan.title = "Test"
        mock_plan.eta_text = "5 min"
        mock_plan.steps = ["Step 1"]
        mock_plan.query = "test"

        mock_client.create_deep_research_plan = AsyncMock(return_value=mock_plan)
        mock_client.close = AsyncMock()

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                with patch("builtins.input", side_effect=KeyboardInterrupt):
                    result = asyncio.run(run_deep_research("test", auto_confirm=False))

        assert result.done is False

    def test_passes_timeout_and_poll_interval(self):
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
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
        mock_client.close = AsyncMock()

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                asyncio.run(run_deep_research("q", timeout_min=15, poll_interval=5.0))

        mock_client.init.assert_called_once_with(timeout=900)
        mock_client.deep_research.assert_called_once()
        call_kwargs = mock_client.deep_research.call_args
        assert call_kwargs[1]["poll_interval"] == 5.0
        assert call_kwargs[1]["timeout"] == 900

    def test_client_closed_on_error(self):
        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.create_deep_research_plan = AsyncMock(side_effect=RuntimeError("fail"))
        mock_client.close = AsyncMock()

        with patch("auth.AuthManager.get_cookies", return_value={"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}):
            with patch("research.GeminiClient", return_value=mock_client):
                with pytest.raises(RuntimeError, match="fail"):
                    asyncio.run(run_deep_research("test"))

        mock_client.close.assert_called_once()

    def test_passes_profile(self):
        from gemini_webapi.types import DeepResearchPlan, DeepResearchResult

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
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
        mock_client.close = AsyncMock()

        with patch("research.AuthManager") as mock_auth_cls:
            mock_auth_mgr = MagicMock()
            mock_auth_mgr.get_cookies.return_value = {"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}
            mock_auth_cls.return_value = mock_auth_mgr
            with patch("research.GeminiClient", return_value=mock_client):
                asyncio.run(run_deep_research("q", profile="work"))

        mock_auth_cls.assert_called_once_with("work")
