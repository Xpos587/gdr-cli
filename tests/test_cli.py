"""Tests for cli.py — smoke tests and exception handling."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch
from gdr_cli.cli import app

runner = CliRunner()


class TestHelp:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "research" in result.output

    def test_research_help(self):
        result = runner.invoke(app, ["research", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output.lower()

    def test_chat_help(self):
        result = runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0

    def test_login_help(self):
        result = runner.invoke(app, ["login", "--help"])
        assert result.exit_code == 0

    def test_doctor_help(self):
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestErrorHandling:
    def test_chat_auth_error_shows_hint(self):
        from gdr_cli.exceptions import AuthError
        with patch("gdr_cli.chat.send_message", side_effect=AuthError("No cookies", hint="Run 'gdr login'")):
            result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 2
        assert "Run 'gdr login'" in result.output

    def test_research_rate_limit(self):
        from gemini_webapi.exceptions import UsageLimitExceeded
        with patch("gdr_cli.research.run_deep_research", side_effect=UsageLimitExceeded("limited")):
            result = runner.invoke(app, ["research", "test"])
        assert result.exit_code == 3
        assert "limit" in result.output.lower()
