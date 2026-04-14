"""Tests for cli.py — smoke tests."""

import pytest
from typer.testing import CliRunner
from gdr_cli.cli import app

runner = CliRunner()


class TestCli:
    def test_gdr_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Gemini Deep Research" in result.output

    def test_research_help(self):
        result = runner.invoke(app, ["research", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output.lower()

    def test_doctor_help(self):
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0

    def test_login_help(self):
        result = runner.invoke(app, ["login", "--help"])
        assert result.exit_code == 0

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestLiveAuth:
    """Integration tests that hit real nlm profile (skipped in CI)."""

    def test_load_real_cookies(self):
        from gdr_cli.config import get_cookies_file
        from gdr_cli.auth import load_cookies

        cookies_file = get_cookies_file("default")
        if not cookies_file.exists():
            pytest.skip("nlm profile not found")

        cookies = load_cookies(cookies_file)
        assert "__Secure-1PSID" in cookies
        assert len(cookies) > 5

    def test_doctor_runs(self):
        from gdr_cli.config import get_cookies_file

        if not get_cookies_file("default").exists():
            pytest.skip("nlm profile not found")

        result = runner.invoke(app, ["doctor"])
        assert "Profile directory" in result.output or "FAIL" in result.output
