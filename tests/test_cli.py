"""Tests for cli.py — commands, error handling, output."""

import asyncio
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock
from cli import app, _test_connectivity

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

    def test_debug_flag(self):
        with patch("loguru.logger") as mock_logger:
            result = runner.invoke(app, ["chat", "--help"])
        # debug flag not set, logger.remove should be called
        mock_logger.remove.assert_called_once()

    def test_debug_flag_enabled(self):
        with patch("gemini_webapi.set_log_level") as mock_set:
            result = runner.invoke(app, ["--debug", "chat", "--help"])
        mock_set.assert_called_once_with("DEBUG")


class TestErrorHandling:
    def test_chat_auth_error_shows_hint(self):
        from exceptions import GDRError
        with patch("repl.run_repl", side_effect=GDRError("No cookies", hint="Run 'gdr login'")):
            result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 2
        assert "Run 'gdr login'" in result.output

    def test_chat_auth_error_no_hint(self):
        from exceptions import GDRError
        with patch("repl.run_repl", side_effect=GDRError("No cookies")):
            result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 2
        assert "No cookies" in result.output

    def test_chat_generic_error(self):
        with patch("repl.run_repl", side_effect=RuntimeError("boom")):
            result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 1
        assert "boom" in result.output

    def test_research_rate_limit(self):
        from gemini_webapi.exceptions import UsageLimitExceeded
        with patch("research.run_deep_research", new_callable=AsyncMock, side_effect=UsageLimitExceeded("limited")):
            result = runner.invoke(app, ["research", "test"])
        assert result.exit_code == 3
        assert "limit" in result.output.lower()

    def test_research_generic_error(self):
        with patch("research.run_deep_research", new_callable=AsyncMock, side_effect=RuntimeError("fail")):
            result = runner.invoke(app, ["research", "test"])
        assert result.exit_code == 1

    def test_research_gdr_error(self):
        from exceptions import GDRError
        with patch("research.run_deep_research", new_callable=AsyncMock, side_effect=GDRError("auth fail", hint="login")):
            result = runner.invoke(app, ["research", "test"])
        assert result.exit_code == 2

    def test_research_usage_limit(self):
        from gemini_webapi.exceptions import UsageLimitExceeded
        with patch("research.run_deep_research", new_callable=AsyncMock, side_effect=UsageLimitExceeded("limit")):
            result = runner.invoke(app, ["research", "test"])
        assert result.exit_code == 3
        assert "usage limit" in result.output.lower()

    def test_research_ip_blocked(self):
        from gemini_webapi.exceptions import TemporarilyBlocked
        with patch("research.run_deep_research", new_callable=AsyncMock, side_effect=TemporarilyBlocked("blocked")):
            result = runner.invoke(app, ["research", "test"])
        assert result.exit_code == 3
        assert "blocked" in result.output.lower()


class TestChatCommand:
    def test_chat_single_message(self):
        with patch("repl.run_repl", new_callable=AsyncMock) as mock_repl:
            result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 0
        mock_repl.assert_called_once()
        call_kwargs = mock_repl.call_args[1]
        assert call_kwargs["profile"] == "default"
        assert call_kwargs["metadata"] is None

    def test_chat_with_profile(self):
        with patch("repl.run_repl", new_callable=AsyncMock) as mock_repl:
            result = runner.invoke(app, ["chat", "-p", "work", "hello"])
        assert result.exit_code == 0
        assert mock_repl.call_args[1]["profile"] == "work"

    def test_chat_continue_with_cid(self):
        with patch("repl.run_repl", new_callable=AsyncMock) as mock_repl:
            result = runner.invoke(app, ["chat", "-c", "c_abc123"])
        assert result.exit_code == 0
        assert mock_repl.call_args[1]["metadata"] == ["c_abc123"]

    def test_chat_continue_with_cid_no_prefix(self):
        with patch("repl.run_repl", new_callable=AsyncMock) as mock_repl:
            result = runner.invoke(app, ["chat", "-c", "abc123"])
        assert result.exit_code == 0
        assert mock_repl.call_args[1]["metadata"] == ["c_abc123"]

    def test_chat_continue_without_cid_fetches_last(self):
        mock_chats = [{"cid": "c_last", "title": "Last", "is_pinned": False, "timestamp": 1.0}]
        with patch("chat.list_recent_chats", new_callable=AsyncMock, return_value=mock_chats):
            with patch("repl.run_repl", new_callable=AsyncMock) as mock_repl:
                result = runner.invoke(app, ["chat", "-c", ""])
        assert result.exit_code == 0
        assert mock_repl.call_args[1]["metadata"] == ["c_last"]

    def test_chat_continue_no_chats(self):
        with patch("chat.list_recent_chats", new_callable=AsyncMock, return_value=[]):
            with patch("repl.run_repl", new_callable=AsyncMock) as mock_repl:
                result = runner.invoke(app, ["chat", "-c", ""])
        assert result.exit_code == 0
        assert mock_repl.call_args[1]["metadata"] is None


class TestChatsList:
    def test_chats_list_empty(self):
        with patch("chat.list_recent_chats", new_callable=AsyncMock, return_value=[]):
            result = runner.invoke(app, ["chats", "list"])
        assert result.exit_code == 0
        assert "No recent chats" in result.output

    def test_chats_list_with_data(self):
        mock_chats = [
            {"cid": "c_abc123456789", "title": "Test Chat", "is_pinned": False, "timestamp": 1745000000.0},
            {"cid": "c_def456789012", "title": "Pinned Chat", "is_pinned": True, "timestamp": 1745000001.0},
        ]
        with patch("chat.list_recent_chats", new_callable=AsyncMock, return_value=mock_chats):
            result = runner.invoke(app, ["chats", "list"])
        assert result.exit_code == 0
        assert "Test Chat" in result.output
        assert "Pinned Chat" in result.output
        assert "* Pinned" in result.output

    def test_chats_list_truncates_long_title(self):
        mock_chats = [
            {"cid": "c_abc123def456789", "title": "x" * 100, "is_pinned": False, "timestamp": 1745000000.0},
        ]
        with patch("chat.list_recent_chats", new_callable=AsyncMock, return_value=mock_chats):
            result = runner.invoke(app, ["chats", "list"])
        assert result.exit_code == 0
        assert "abc123def456789" in result.output

    def test_chats_list_untitled(self):
        mock_chats = [
            {"cid": "c_abc123", "title": None, "is_pinned": False, "timestamp": 1745000000.0},
        ]
        with patch("chat.list_recent_chats", new_callable=AsyncMock, return_value=mock_chats):
            result = runner.invoke(app, ["chats", "list"])
        assert result.exit_code == 0
        assert "(untitled)" in result.output

    def test_chats_list_with_profile(self):
        with patch("chat.list_recent_chats", new_callable=AsyncMock, return_value=[]) as mock_list:
            result = runner.invoke(app, ["chats", "list", "-p", "work"])
        assert result.exit_code == 0
        mock_list.assert_called_once_with(profile="work")

    def test_chats_list_gdr_error(self):
        from exceptions import GDRError
        with patch("chat.list_recent_chats", new_callable=AsyncMock, side_effect=GDRError("fail", hint="login")):
            result = runner.invoke(app, ["chats", "list"])
        assert result.exit_code == 2


class TestChatsShow:
    def test_chats_show_found(self):
        mock_history = {
            "cid": "c_abc123",
            "turns": [
                {"role": "user", "text": "Hello"},
                {"role": "model", "text": "Hi there!"},
            ],
        }
        with patch("chat.read_chat_history", new_callable=AsyncMock, return_value=mock_history):
            result = runner.invoke(app, ["chats", "show", "c_abc123"])
        assert result.exit_code == 0
        assert "Hello" in result.output
        assert "Hi there!" in result.output
        assert "abc123" in result.output
        assert "c_abc123" not in result.output

    def test_chats_show_cid_without_prefix(self):
        mock_history = {
            "cid": "c_abc123",
            "turns": [],
        }
        with patch("chat.read_chat_history", new_callable=AsyncMock, return_value=mock_history) as mock_read:
            result = runner.invoke(app, ["chats", "show", "abc123"])
        assert result.exit_code == 0
        mock_read.assert_called_once_with("c_abc123", limit=20, profile="default")

    def test_chats_show_not_found(self):
        with patch("chat.read_chat_history", new_callable=AsyncMock, return_value=None):
            result = runner.invoke(app, ["chats", "show", "c_nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_chats_show_with_limit(self):
        mock_history = {"cid": "c_abc", "turns": []}
        with patch("chat.read_chat_history", new_callable=AsyncMock, return_value=mock_history) as mock_read:
            result = runner.invoke(app, ["chats", "show", "c_abc", "-n", "5"])
        assert result.exit_code == 0
        mock_read.assert_called_once_with("c_abc", limit=5, profile="default")

    def test_chats_show_gdr_error(self):
        from exceptions import GDRError
        with patch("chat.read_chat_history", new_callable=AsyncMock, side_effect=GDRError("fail")):
            result = runner.invoke(app, ["chats", "show", "c_abc"])
        assert result.exit_code == 2


class TestResearchCommand:
    def test_research_success_prints_report(self):
        mock_result = MagicMock()
        mock_result.plan = MagicMock()
        mock_result.plan.title = "Test"
        mock_result.done = True
        mock_result.text = "Research report here"

        with patch("research.run_deep_research", new_callable=AsyncMock, return_value=mock_result):
            result = runner.invoke(app, ["research", "AI safety"])
        assert result.exit_code == 0
        assert "Research report here" in result.output

    def test_research_output_file(self, tmp_path):
        mock_result = MagicMock()
        mock_result.plan = MagicMock()
        mock_result.plan.title = "T"
        mock_result.done = True
        mock_result.text = "Report"

        out_file = tmp_path / "report.md"
        with patch("research.run_deep_research", new_callable=AsyncMock, return_value=mock_result):
            result = runner.invoke(app, ["research", "test", "-o", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "Report" in content
        assert "Deep Research Report" in content

    def test_research_output_dir(self, tmp_path):
        mock_result = MagicMock()
        mock_result.plan = MagicMock()
        mock_result.plan.title = "T"
        mock_result.done = True
        mock_result.text = "R"

        with patch("research.run_deep_research", new_callable=AsyncMock, return_value=mock_result):
            result = runner.invoke(app, ["research", "test query", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        # Check a file was created
        files = list(tmp_path.glob("*.md"))
        assert len(files) == 1

    def test_research_no_text_no_file_written(self, tmp_path):
        mock_result = MagicMock()
        mock_result.plan = MagicMock()
        mock_result.plan.title = "T"
        mock_result.done = False
        mock_result.text = None

        with patch("research.run_deep_research", new_callable=AsyncMock, return_value=mock_result):
            result = runner.invoke(app, ["research", "test", "-o", str(tmp_path / "r.md")])
        assert result.exit_code == 0
        assert not (tmp_path / "r.md").exists()

    def test_research_passes_options(self):
        mock_result = MagicMock()
        mock_result.plan = MagicMock()
        mock_result.plan.title = "T"
        mock_result.done = True
        mock_result.text = "R"

        with patch("research.run_deep_research", new_callable=AsyncMock, return_value=mock_result) as mock_run:
            runner.invoke(app, ["research", "test", "-t", "60", "--poll", "15", "-n"])
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout_min"] == 60
        assert call_kwargs["poll_interval"] == 15.0
        assert call_kwargs["auto_confirm"] is True


class TestDoctorCommand:
    def test_doctor_missing_profile_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.get_profile_dir", lambda n: tmp_path / "nonexistent")
        monkeypatch.setattr("config.get_cookies_file", lambda n: tmp_path / "nonexistent" / "cookies.json")
        monkeypatch.setattr("config.get_metadata_file", lambda n: tmp_path / "nonexistent" / "metadata.json")

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_doctor_missing_cookies(self, tmp_path, monkeypatch):
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: profile_dir / "cookies.json")
        monkeypatch.setattr("config.get_metadata_file", lambda n: profile_dir / "metadata.json")

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_doctor_corrupt_cookies(self, tmp_path, monkeypatch):
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        cookies_file = profile_dir / "cookies.json"
        cookies_file.write_text("bad json{{{", encoding="utf-8")
        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: cookies_file)
        monkeypatch.setattr("config.get_metadata_file", lambda n: profile_dir / "metadata.json")

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_doctor_missing_psid(self, tmp_path, monkeypatch):
        import json
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        cookies_file = profile_dir / "cookies.json"
        cookies_file.write_text(json.dumps([{"name": "HSID", "value": "h"}]), encoding="utf-8")
        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: cookies_file)
        monkeypatch.setattr("config.get_metadata_file", lambda n: profile_dir / "metadata.json")

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1

    def test_doctor_full_success(self, tmp_path, monkeypatch):
        import json
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        cookies_file = profile_dir / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "__Secure-1PSID", "value": "pv"},
            {"name": "__Secure-1PSIDTS", "value": "ptv"},
        ]), encoding="utf-8")
        metadata_file = profile_dir / "metadata.json"
        metadata_file.write_text(json.dumps({
            "email": "user@gmail.com",
            "last_validated": "2026-04-14T12:00:00",
        }), encoding="utf-8")

        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: cookies_file)
        monkeypatch.setattr("config.get_metadata_file", lambda n: metadata_file)

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(return_value={
            "summary": {"deep_research_feature_present": True},
            "rpc": {"bootstrap": {"ok": True}},
        })
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "user@gmail.com" in result.output
        assert "available" in result.output

    def test_doctor_full_success_no_metadata(self, tmp_path, monkeypatch):
        import json
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        cookies_file = profile_dir / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "__Secure-1PSID", "value": "pv"},
            {"name": "__Secure-1PSIDTS", "value": "ptv"},
        ]), encoding="utf-8")

        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: cookies_file)
        monkeypatch.setattr("config.get_metadata_file", lambda n: profile_dir / "metadata.json")

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(return_value={
            "summary": {"deep_research_feature_present": True},
            "rpc": {"bootstrap": {"ok": True}},
        })
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0

    def test_doctor_missing_optional_cookies(self, tmp_path, monkeypatch):
        import json
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        cookies_file = profile_dir / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "__Secure-1PSID", "value": "pv"},
            # Missing __Secure-1PSIDTS
        ]), encoding="utf-8")
        metadata_file = profile_dir / "metadata.json"
        metadata_file.write_text(json.dumps({"email": "u@u.com"}), encoding="utf-8")

        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: cookies_file)
        monkeypatch.setattr("config.get_metadata_file", lambda n: metadata_file)

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(return_value={"summary": {}, "rpc": {"bootstrap": {"ok": False}}})
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "WARN" in result.output
        assert "Missing cookies" in result.output

    def test_doctor_no_metadata_file(self, tmp_path, monkeypatch):
        import json
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        cookies_file = profile_dir / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "__Secure-1PSID", "value": "pv"},
            {"name": "__Secure-1PSIDTS", "value": "ptv"},
        ]), encoding="utf-8")

        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: cookies_file)
        monkeypatch.setattr("config.get_metadata_file", lambda n: profile_dir / "metadata.json")

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(side_effect=RuntimeError("conn fail"))
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "WARN" in result.output
        assert "No metadata file" in result.output

    def test_doctor_connectivity_fail(self, tmp_path, monkeypatch):
        import json
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        cookies_file = profile_dir / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "__Secure-1PSID", "value": "pv"},
            {"name": "__Secure-1PSIDTS", "value": "ptv"},
        ]), encoding="utf-8")
        metadata_file = profile_dir / "metadata.json"
        metadata_file.write_text(json.dumps({"email": "u@u.com"}), encoding="utf-8")

        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: cookies_file)
        monkeypatch.setattr("config.get_metadata_file", lambda n: metadata_file)

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(side_effect=RuntimeError("fail"))
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            result = runner.invoke(app, ["doctor"])

        assert "FAIL" in result.output
        assert "connectivity" in result.output

    def test_doctor_dr_not_available(self, tmp_path, monkeypatch):
        import json
        profile_dir = tmp_path / "profiles" / "default"
        profile_dir.mkdir(parents=True)
        cookies_file = profile_dir / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "__Secure-1PSID", "value": "pv"},
            {"name": "__Secure-1PSIDTS", "value": "ptv"},
        ]), encoding="utf-8")
        metadata_file = profile_dir / "metadata.json"
        metadata_file.write_text(json.dumps({"email": "u@u.com"}), encoding="utf-8")

        monkeypatch.setattr("config.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("config.get_cookies_file", lambda n: cookies_file)
        monkeypatch.setattr("config.get_metadata_file", lambda n: metadata_file)

        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(return_value={
            "summary": {"deep_research_feature_present": False}, "rpc": {"bootstrap": {"ok": False}},
        })
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            result = runner.invoke(app, ["doctor"])

        assert "not available" in result.output


class TestLoginCommand:
    def test_login_success(self):
        mock_result = {
            "cookie_count": 5,
            "email": "user@gmail.com",
        }
        with patch("cli._async_login", new_callable=AsyncMock, return_value=mock_result):
            result = runner.invoke(app, ["login"])
        assert result.exit_code == 0
        assert "user@gmail.com" in result.output
        assert "5 cookies" in result.output

    def test_login_no_email(self):
        mock_result = {"cookie_count": 3, "email": ""}
        with patch("cli._async_login", new_callable=AsyncMock, return_value=mock_result):
            result = runner.invoke(app, ["login"])
        assert result.exit_code == 0
        # Email line should not appear
        assert "Email:" not in result.output

    def test_login_error(self):
        with patch("cli._async_login", new_callable=AsyncMock, side_effect=RuntimeError("CDP fail")):
            result = runner.invoke(app, ["login"])
        assert result.exit_code == 1
        assert "CDP fail" in result.output

    def test_login_with_profile(self):
        mock_result = {"cookie_count": 3, "email": "u@u.com"}
        with patch("cli._async_login", new_callable=AsyncMock, return_value=mock_result) as mock_login:
            runner.invoke(app, ["login", "-p", "work"])
        mock_login.assert_called_once()
        assert mock_login.call_args[1]["profile"] == "work"

    def test_login_with_cdp_url(self):
        mock_result = {"cookie_count": 3, "email": ""}
        with patch("cli._async_login", new_callable=AsyncMock, return_value=mock_result) as mock_login:
            runner.invoke(app, ["login", "--cdp-url", "http://127.0.0.1:9333"])
        assert mock_login.call_args[1]["cdp_url"] == "http://127.0.0.1:9333"

    def test_login_no_launch(self):
        mock_result = {"cookie_count": 3, "email": ""}
        with patch("cli._async_login", new_callable=AsyncMock, return_value=mock_result) as mock_login:
            runner.invoke(app, ["login", "--no-launch"])
        assert mock_login.call_args[1]["auto_launch"] is False


class TestChatsSmoke:
    def test_chats_help(self):
        result = runner.invoke(app, ["chats", "--help"])
        assert result.exit_code == 0

    def test_chats_list_help(self):
        result = runner.invoke(app, ["chats", "list", "--help"])
        assert result.exit_code == 0

    def test_chats_show_help(self):
        result = runner.invoke(app, ["chats", "show", "--help"])
        assert result.exit_code == 0


class TestTestConnectivity:
    def test_returns_available(self):
        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(return_value={
            "summary": {"deep_research_feature_present": True}, "rpc": {"bootstrap": {"ok": True}},
        })
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            tier, dr = asyncio.run(_test_connectivity({"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}))

        assert tier == "advanced"
        assert dr == "available"

    def test_returns_not_available(self):
        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(return_value={
            "summary": {"deep_research_feature_present": False}, "rpc": {"bootstrap": {"ok": True}},
        })
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            tier, dr = asyncio.run(_test_connectivity({"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}))

        assert tier == "plus"
        assert dr == "not available"

    def test_returns_free_tier(self):
        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(return_value={
            "summary": {"deep_research_feature_present": False}, "rpc": {"bootstrap": {"ok": False}},
        })
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            tier, dr = asyncio.run(_test_connectivity({"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}))

        assert tier == "free"

    def test_returns_none_on_error(self):
        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(side_effect=RuntimeError("fail"))
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            with pytest.raises(RuntimeError):
                asyncio.run(_test_connectivity({"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}))

    def test_closes_client_on_error(self):
        mock_client = MagicMock()
        mock_client.init = AsyncMock()
        mock_client.inspect_account_status = AsyncMock(side_effect=RuntimeError("fail"))
        mock_client.close = AsyncMock()

        with patch("gemini_webapi.GeminiClient", return_value=mock_client):
            with pytest.raises(RuntimeError):
                asyncio.run(_test_connectivity({"__Secure-1PSID": "v", "__Secure-1PSIDTS": "vt"}))

        mock_client.close.assert_called_once()
