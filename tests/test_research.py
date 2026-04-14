"""Tests for research.py — orchestration (mocked GeminiClient)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from gdr_cli.research import run_deep_research, format_result


class TestFormatResult:
    def test_formats_completed_result(self):
        plan = MagicMock()
        plan.title = "AI Trends 2026"
        plan.steps = ["Step 1: Search", "Step 2: Analyze"]
        plan.eta_text = "~10 minutes"

        status = MagicMock()
        status.state = "completed"
        status.title = "AI Trends 2026"

        result = MagicMock()
        result.plan = plan
        result.statuses = [status]
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


class TestRunDeepResearch:
    def test_raises_auth_error_on_bad_cookies(self):
        from gdr_cli.auth import AuthError
        import asyncio

        with patch("gdr_cli.research.get_profile_cookies", side_effect=AuthError("no cookies")):
            with pytest.raises(AuthError):
                asyncio.run(run_deep_research("test query"))
