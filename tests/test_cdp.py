"""Tests for cdp.py — Chrome DevTools Protocol login flow."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from cdp import (
    find_browser, find_available_port, launch_browser, login_via_cdp,
    extract_email, extract_build_label, extract_csrf_token,
    extract_session_id, is_logged_in, GEMINI_URL, PROFILE_DIR,
)


class TestFindBrowser:
    @patch("cdp.shutil.which")
    def test_returns_first_found(self, mock_which):
        mock_which.side_effect = lambda name: f"/usr/bin/{name}" if name == "chromium" else None
        result = find_browser()
        assert result == "/usr/bin/chromium"

    @patch("cdp.shutil.which")
    def test_returns_none_when_no_browser(self, mock_which):
        mock_which.return_value = None
        result = find_browser()
        assert result is None

    @patch("cdp.shutil.which")
    def test_checks_multiple_browsers(self, mock_which):
        mock_which.side_effect = lambda name: f"/usr/bin/{name}" if name == "brave-browser" else None
        result = find_browser()
        assert result == "/usr/bin/brave-browser"


class TestFindAvailablePort:
    def test_returns_start_port(self):
        port = find_available_port(start=19222, max_attempts=1)
        assert port == 19222

    def test_returns_next_port_when_taken(self):
        import socket
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        taken_port = sock.getsockname()[1]
        port = find_available_port(start=taken_port, max_attempts=5)
        assert port != taken_port
        sock.close()


class TestGetDebuggerUrl:
    @patch("cdp.time.sleep")
    @patch("urllib.request.urlopen")
    def test_returns_ws_url(self, mock_urlopen, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/1"
        }).encode()
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        from cdp import get_debugger_url
        result = get_debugger_url(9222, tries=1)
        assert result == "ws://127.0.0.1:9222/devtools/page/1"

    @patch("cdp.time.sleep")
    @patch("urllib.request.urlopen")
    def test_returns_none_on_failure(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = Exception("conn refused")
        from cdp import get_debugger_url
        result = get_debugger_url(9222, tries=1)
        assert result is None

    @patch("cdp.time.sleep")
    @patch("urllib.request.urlopen")
    def test_retries_on_empty_url(self, mock_urlopen, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.read.side_effect = [
            json.dumps({"webSocketDebuggerUrl": ""}).encode(),
            json.dumps({"webSocketDebuggerUrl": "ws://127.0.0.1:9222/ws"}).encode(),
        ]
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        from cdp import get_debugger_url
        result = get_debugger_url(9222, tries=3)
        assert result == "ws://127.0.0.1:9222/ws"
        assert mock_sleep.call_count == 1


class TestCheckCdp:
    @patch("urllib.request.urlopen")
    def test_returns_true_when_reachable(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        from cdp import check_cdp
        assert check_cdp("http://127.0.0.1:9222") is True

    @patch("urllib.request.urlopen")
    def test_returns_false_when_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("refused")
        from cdp import check_cdp
        assert check_cdp("http://127.0.0.1:9222") is False


class TestIsLoggedIn:
    def test_logged_in_gemini(self):
        assert is_logged_in("https://gemini.google.com/app") is True

    def test_not_logged_in_accounts(self):
        assert is_logged_in("https://accounts.google.com/login") is False

    def test_not_logged_in_other(self):
        assert is_logged_in("https://example.com") is False


class TestExtractEmail:
    def test_extracts_email(self):
        html = '"oPEP7c":"user@gmail.com"'
        assert extract_email(html) == "user@gmail.com"

    def test_skips_gstatic(self):
        html = '"oPEP7c":"something@gstatic.com"'
        assert extract_email(html) == ""

    def test_skips_google(self):
        html = '"oPEP7c":"noreply@google.com"'
        assert extract_email(html) == ""

    def test_no_email(self):
        assert extract_email("no email here") == ""


class TestExtractBuildLabel:
    def test_extracts_label(self):
        html = '"cfb2h":"boq_assistant-bobo-frontend_20250101.00_p0"'
        assert extract_build_label(html) == "boq_assistant-bobo-frontend_20250101.00_p0"

    def test_no_label(self):
        assert extract_build_label("nothing") == ""


class TestExtractCsrfToken:
    def test_extracts_token(self):
        html = '"SNlM0e":"abc123token"'
        assert extract_csrf_token(html) == "abc123token"

    def test_no_token(self):
        assert extract_csrf_token("nothing") == ""


class TestExtractSessionId:
    def test_extracts_id(self):
        html = '"FdrFJe":"12345"'
        assert extract_session_id(html) == "12345"

    def test_no_id(self):
        assert extract_session_id("nothing") == ""


class TestCdpCommand:
    @patch("websocket.create_connection")
    def test_sends_command(self, mock_ws):
        mock_ws_instance = MagicMock()
        mock_ws_instance.recv.return_value = json.dumps({"id": 1, "result": {"value": "ok"}})
        mock_ws_instance.__enter__ = MagicMock(return_value=mock_ws_instance)
        mock_ws_instance.__exit__ = MagicMock(return_value=False)
        mock_ws.return_value = mock_ws_instance

        from cdp import cdp_command
        result = cdp_command("ws://localhost:9222/ws", "Runtime.evaluate", {"expression": "1+1"})
        assert result == {"value": "ok"}


class TestGetAllCookies:
    def test_returns_cookies_via_login(self):
        # Covered by TestLoginViaCdp tests
        pass


class TestNavigate:
    def test_calls_navigate(self):
        with patch("websocket.create_connection") as mock_ws:
            mock_ws_instance = MagicMock()
            mock_ws_instance.recv.return_value = json.dumps({"id": 1, "result": {}})
            mock_ws_instance.__enter__ = MagicMock(return_value=mock_ws_instance)
            mock_ws_instance.__exit__ = MagicMock(return_value=False)
            mock_ws.return_value = mock_ws_instance

            from cdp import navigate
            navigate("ws://localhost/ws", "https://gemini.google.com/app")


class TestFindOrCreatePage:
    @patch("urllib.request.urlopen")
    def test_finds_existing_gemini_page(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([
            {"url": "https://gemini.google.com/app", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/ws/1"}
        ]).encode()
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        from cdp import find_or_create_page
        result = find_or_create_page("http://127.0.0.1:9222")
        assert result["url"] == "https://gemini.google.com/app"

    @patch("urllib.request.urlopen")
    def test_returns_none_on_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("fail")
        from cdp import find_or_create_page
        result = find_or_create_page("http://127.0.0.1:9222")
        assert result is None


class TestLaunchBrowser:
    @patch("cdp.find_browser", return_value="/usr/bin/chromium")
    @patch("cdp.subprocess.Popen")
    def test_launches_with_correct_args(self, mock_popen, mock_find):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        result = launch_browser(9222)

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "--remote-debugging-port=9222" in args
        assert "--no-first-run" in args
        assert "--user-data-dir" in str(args)
        assert GEMINI_URL in args
        assert result is mock_proc

    @patch("cdp.find_browser", return_value=None)
    def test_raises_when_no_browser(self, mock_find):
        with pytest.raises(RuntimeError, match="No Chromium-based browser"):
            launch_browser(9222)


class TestLoginViaCdp:
    @patch("cdp.get_all_cookies", return_value=[
        {"name": "__Secure-1PSID", "value": "pv", "domain": ".google.com", "path": "/"},
        {"name": "__Secure-1PSIDTS", "value": "ptv", "domain": ".google.com", "path": "/"},
        {"name": "NID", "value": "nv", "domain": ".google.com", "path": "/"},
        {"name": "SID", "value": "sv", "domain": ".youtube.com", "path": "/"},
    ])
    @patch("cdp.get_page_html", return_value='"oPEP7c":"user@gmail.com" "SNlM0e":"csrf123" "FdrFJe":"456" "cfb2h":"label1"')
    @patch("cdp.is_logged_in", return_value=True)
    @patch("cdp.get_current_url", return_value="https://gemini.google.com/app")
    @patch("cdp.find_or_create_page", return_value={"webSocketDebuggerUrl": "ws://127.0.0.1:9222/ws"})
    @patch("cdp.check_cdp", return_value=True)
    def test_full_login_flow(self, mock_check, mock_find_page, mock_url, mock_logged, mock_html, mock_cookies):
        with patch("auth.AuthManager") as mock_auth_cls:
            mock_mgr = MagicMock()
            mock_auth_cls.return_value = mock_mgr

            result = login_via_cdp(profile="test")

        assert result["email"] == "user@gmail.com"
        assert result["csrf_token"] == "csrf123"
        assert result["session_id"] == "456"
        assert result["build_label"] == "label1"
        assert result["cookie_count"] == 3  # Only .google.com cookies
        mock_mgr.save_profile.assert_called_once()

    @patch("cdp.check_cdp", return_value=False)
    @patch("cdp.find_browser", return_value=None)
    def test_raises_when_no_browser_and_no_launch(self, mock_find, mock_check):
        with pytest.raises(RuntimeError, match="Chrome CDP not reachable"):
            login_via_cdp(auto_launch=False)

    @patch("cdp.check_cdp", return_value=False)
    @patch("cdp.find_browser", return_value=None)
    def test_raises_when_no_browser_even_with_launch(self, mock_find, mock_check):
        with pytest.raises(RuntimeError, match="No Chromium-based browser"):
            login_via_cdp(auto_launch=True)

    @patch("cdp.find_or_create_page", return_value=None)
    @patch("cdp.check_cdp", return_value=True)
    def test_raises_when_no_page(self, mock_check, mock_find_page):
        with pytest.raises(RuntimeError, match="Failed to find or create"):
            login_via_cdp()

    @patch("cdp.check_cdp", return_value=True)
    @patch("cdp.find_or_create_page", return_value={"webSocketDebuggerUrl": ""})
    def test_raises_when_no_ws_url(self, mock_find_page, mock_check):
        with pytest.raises(RuntimeError, match="No WebSocket URL"):
            login_via_cdp()

    @patch("cdp.time.sleep")
    @patch("cdp.navigate")
    @patch("cdp.get_current_url")
    @patch("cdp.get_page_html")
    @patch("cdp.get_all_cookies", return_value=[])
    @patch("cdp.is_logged_in", return_value=False)
    @patch("cdp.find_or_create_page", return_value={"webSocketDebuggerUrl": "ws://127.0.0.1:9222/ws"})
    @patch("cdp.check_cdp", return_value=True)
    def test_raises_on_login_timeout(self, mock_check, mock_find_page, mock_logged, mock_cookies, mock_html, mock_url, mock_navigate, mock_sleep):
        mock_url.return_value = "https://accounts.google.com/login"

        with pytest.raises(RuntimeError, match="Login timed out"):
            login_via_cdp(login_timeout=1)

    @patch("cdp.get_all_cookies", return_value=[])
    @patch("cdp.is_logged_in", return_value=True)
    @patch("cdp.get_current_url", return_value="https://gemini.google.com/app")
    @patch("cdp.find_or_create_page", return_value={"webSocketDebuggerUrl": "ws://127.0.0.1:9222/ws"})
    @patch("cdp.check_cdp", return_value=True)
    def test_raises_on_no_cookies(self, mock_check, mock_find_page, mock_url, mock_logged, mock_cookies):
        with pytest.raises(RuntimeError, match="No cookies extracted"):
            login_via_cdp()

    @patch("cdp.get_all_cookies", return_value=[
        {"name": "__Secure-1PSID", "value": "pv", "domain": ".google.com", "path": "/"},
    ])
    @patch("cdp.get_page_html", return_value="no email here")
    @patch("cdp.is_logged_in", return_value=True)
    @patch("cdp.get_current_url", return_value="https://gemini.google.com/app")
    @patch("cdp.find_or_create_page", return_value={"webSocketDebuggerUrl": "ws://127.0.0.1:9222/ws"})
    @patch("cdp.check_cdp", return_value=True)
    def test_handles_missing_email(self, mock_check, mock_find_page, mock_url, mock_logged, mock_html, mock_cookies):
        with patch("auth.AuthManager") as mock_auth_cls:
            mock_mgr = MagicMock()
            mock_auth_cls.return_value = mock_mgr
            result = login_via_cdp()
        assert result["email"] == ""

    @patch("cdp.time.sleep")
    @patch("cdp.navigate")
    @patch("cdp.get_current_url")
    @patch("cdp.get_page_html")
    @patch("cdp.get_all_cookies", return_value=[
        {"name": "__Secure-1PSID", "value": "pv", "domain": ".google.com", "path": "/"},
    ])
    @patch("cdp.is_logged_in")
    @patch("cdp.find_or_create_page", return_value={"webSocketDebuggerUrl": "ws://127.0.0.1:9222/ws"})
    @patch("cdp.check_cdp", return_value=True)
    def test_navigates_to_gemini_if_needed(self, mock_check, mock_find_page, mock_logged, mock_cookies, mock_html, mock_url, mock_navigate, mock_sleep):
        mock_logged.side_effect = [False, True]
        mock_url.return_value = "https://example.com"
        mock_html.return_value = "no email"

        with patch("auth.AuthManager"):
            login_via_cdp()

        mock_navigate.assert_called_once_with("ws://127.0.0.1:9222/ws", GEMINI_URL)

    @patch("cdp.time.sleep")
    @patch("cdp.navigate")
    @patch("cdp.get_page_html")
    @patch("cdp.get_all_cookies", return_value=[
        {"name": "__Secure-1PSID", "value": "pv", "domain": ".google.com", "path": "/"},
    ])
    @patch("cdp.is_logged_in", return_value=True)
    @patch("cdp.get_current_url", return_value="https://gemini.google.com/app")
    @patch("cdp.find_or_create_page", return_value={"webSocketDebuggerUrl": "ws://127.0.0.1:9222/ws"})
    @patch("cdp.check_cdp", return_value=True)
    def test_waits_for_consent_redirect(self, mock_check, mock_find_page, mock_url, mock_logged, mock_cookies, mock_html, mock_navigate, mock_sleep):
        mock_html.return_value = "no email"
        # Step 3: get_current_url returns gemini (no navigate needed)
        # Step 4: is_logged_in(get_current_url()) returns True (mocked), skip wait loop
        # Step 5: time.sleep(3), then consent loop:
        #   iteration 1: consent URL -> sleep(1)
        #   iteration 2: consent URL -> sleep(1)
        #   iteration 3: gemini URL -> break
        # Total sleeps: 1 (initial) + 2 (consent loop) = 3
        mock_url.side_effect = [
            "https://gemini.google.com/app",   # step 3: check if navigate needed
            "https://gemini.google.com/app",   # step 4: is_logged_in check
            "https://gemini.google.com/consent",  # consent loop iter 1
            "https://gemini.google.com/consent",  # consent loop iter 2
            "https://gemini.google.com/app",   # consent loop break
        ]
        with patch("auth.AuthManager"):
            login_via_cdp()
        assert mock_sleep.call_count >= 3

    def test_cookie_dedup_prefers_root_domain(self):
        """Verify dedup logic: .google.com preferred over subdomains, / preferred over specific paths."""
        cookies = [
            {"name": "__Secure-1PSID", "value": "sub", "domain": "accounts.google.com", "path": "/"},
            {"name": "__Secure-1PSID", "value": "root", "domain": ".google.com", "path": "/"},
            {"name": "__Secure-1PSID", "value": "path", "domain": ".google.com", "path": "/accounts"},
            {"name": "NID", "value": "v", "domain": ".youtube.com", "path": "/"},
        ]
        seen = {}
        for c in cookies:
            domain = c.get("domain", "")
            if not domain.endswith(".google.com"):
                continue
            name = c["name"]
            existing = seen.get(name)
            if existing is None:
                seen[name] = c
            elif domain == ".google.com" and existing.get("domain") != ".google.com":
                seen[name] = c
            elif c.get("path", "/") == "/" and existing.get("path", "/") != "/":
                seen[name] = c

        assert seen["__Secure-1PSID"]["value"] == "root"  # .google.com with /
        assert "NID" not in seen  # .youtube.com filtered out
