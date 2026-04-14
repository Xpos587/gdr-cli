"""CDP-based cookie extraction for gdr.

Connects to Chrome via DevTools Protocol, navigates to gemini.google.com,
waits for login, and extracts Google auth cookies.

Stores cookies in the same directory as nlm (~/.notebooklm-mcp-cli/profiles/)
for unified auth across both tools.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

GEMINI_URL = "https://gemini.google.com/app"
BROWSERS = [
    "google-chrome", "google-chrome-stable",
    "chromium", "chromium-browser",
    "brave-browser", "microsoft-edge-stable", "microsoft-edge",
    "vivaldi-stable", "vivaldi", "opera",
]

# Shared with nlm — same Chrome profile directory
PROFILE_DIR = Path.home() / ".notebooklm-mcp-cli" / "chrome-profiles" / "default"


def find_browser() -> str | None:
    for name in BROWSERS:
        path = shutil.which(name)
        if path:
            return path
    return None


def find_available_port(start: int = 9222, max_attempts: int = 10) -> int:
    from http.server import HTTPServer

    for offset in range(max_attempts):
        port = start + offset
        try:
            server = HTTPServer(("127.0.0.1", port), HTTPRequestHandler)
            server.server_close()
            return port
        except OSError:
            continue
    raise RuntimeError(f"No available CDP port in range {start}-{start + max_attempts - 1}")


class HTTPRequestHandler:
    """Dummy handler for port availability check."""

    def __init__(self, *args, **kwargs):
        pass

    def handle(self):
        pass


def get_debugger_url(port: int, tries: int = 15) -> str | None:
    """Get WebSocket debugger URL from Chrome."""
    import urllib.request

    for _ in range(tries):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3) as resp:
                data = json.loads(resp.read())
                ws_url = data.get("webSocketDebuggerUrl", "")
                if ws_url:
                    # Normalize localhost → 127.0.0.1
                    return ws_url.replace("://localhost:", "://127.0.0.1:")
        except Exception:
            pass
        time.sleep(1)
    return None


def launch_browser(port: int) -> subprocess.Popen:
    """Launch Chromium with remote debugging on the given port."""
    browser = find_browser()
    if not browser:
        raise RuntimeError(
            "No Chromium-based browser found.\n"
            "Install: pacman -S chromium"
        )

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [
            browser,
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={PROFILE_DIR}",
            "--remote-allow-origins=*",
            GEMINI_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def cdp_command(ws_url: str, method: str, params: dict | None = None) -> dict:
    """Send a single CDP command over WebSocket and return the result."""
    import websocket

    ws = websocket.create_connection(ws_url, timeout=30)
    try:
        ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == 1:
                return resp.get("result", {})
    finally:
        ws.close()


def get_all_cookies(ws_url: str) -> list[dict]:
    """Extract all cookies via Network.getAllCookies."""
    result = cdp_command(ws_url, "Network.getAllCookies")
    return result.get("cookies", [])


def get_page_html(ws_url: str) -> str:
    """Get page HTML via Runtime.evaluate."""
    cdp_command(ws_url, "Runtime.enable")
    result = cdp_command(ws_url, "Runtime.evaluate", {"expression": "document.documentElement.outerHTML"})
    return result.get("result", {}).get("value", "")


def get_current_url(ws_url: str) -> str:
    """Get current page URL."""
    cdp_command(ws_url, "Runtime.enable")
    result = cdp_command(ws_url, "Runtime.evaluate", {"expression": "window.location.href"})
    return result.get("result", {}).get("value", "")


def navigate(ws_url: str, url: str) -> None:
    """Navigate page to a URL."""
    cdp_command(ws_url, "Page.enable")
    cdp_command(ws_url, "Page.navigate", {"url": url})


def is_logged_in(url: str) -> bool:
    """Check if user is logged in (not redirected to accounts.google.com)."""
    if "accounts.google.com" in url:
        return False
    return "gemini.google.com" in url


def find_or_create_page(cdp_url: str) -> dict | None:
    """Find a Gemini page or create a new tab."""
    import urllib.request

    # List existing pages
    try:
        with urllib.request.urlopen(f"{cdp_url}/json", timeout=5) as resp:
            pages = json.loads(resp.read())
    except Exception:
        return None

    for page in pages:
        if "gemini.google.com" in page.get("url", ""):
            return page

    # Create new tab with Gemini
    try:
        with urllib.request.urlopen(
            f"{cdp_url}/json/new?{GEMINI_URL}", timeout=15
        ) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def extract_email(html: str) -> str:
    """Extract user email from page HTML."""
    patterns = [
        r'"oPEP7c":"([^"]+@[^"]+)"',
        r'"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, html):
            if "@google.com" not in match and "@gstatic" not in match:
                return match
    return ""


def extract_build_label(html: str) -> str:
    match = re.search(r'"cfb2h":"([^"]+)"', html)
    return match.group(1) if match else ""


def extract_csrf_token(html: str) -> str:
    match = re.search(r'"SNlM0e":"([^"]+)"', html)
    return match.group(1) if match else ""


def extract_session_id(html: str) -> str:
    match = re.search(r'"FdrFJe":"(\d+)"', html)
    return match.group(1) if match else ""


def check_cdp(cdp_url: str = "http://127.0.0.1:9222") -> bool:
    """Check if Chrome CDP is reachable."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def login_via_cdp(
    profile: str = "default",
    cdp_url: str = "http://127.0.0.1:9222",
    auto_launch: bool = True,
    login_timeout: int = 300,
) -> dict[str, Any]:
    """Full CDP login flow: connect → wait for login → extract cookies → save.

    Returns dict with cookies, email, csrf_token, session_id, build_label.
    Saves to ~/.notebooklm-mcp-cli/profiles/{profile}/cookies.json + metadata.json.
    """
    import urllib.request

    # 1. Ensure CDP is reachable
    if not check_cdp(cdp_url):
        if not auto_launch:
            raise RuntimeError(
                f"Chrome CDP not reachable at {cdp_url}.\n"
                "Launch Chrome with --remote-debugging-port=9222 or use --launch."
            )

        port = int(cdp_url.rsplit(":", 1)[1])
        available_port = find_available_port(port)
        launch_browser(available_port)
        cdp_url = f"http://127.0.0.1:{available_port}"
        time.sleep(2)

    # 2. Find or create Gemini page
    page = find_or_create_page(cdp_url)
    if not page:
        raise RuntimeError("Failed to find or create Gemini page in browser.")

    ws_url = page.get("webSocketDebuggerUrl", "")
    if not ws_url:
        raise RuntimeError("No WebSocket URL for page.")

    # 3. Navigate to Gemini if needed
    current_url = get_current_url(ws_url)
    if "gemini.google.com" not in current_url:
        navigate(ws_url, GEMINI_URL)
        time.sleep(2)

    # 4. Wait for login
    if not is_logged_in(get_current_url(ws_url)):
        print(f"  Browser opened — please log in to Google at {GEMINI_URL}")
        start = time.time()
        while time.time() - start < login_timeout:
            time.sleep(2)
            if is_logged_in(get_current_url(ws_url)):
                break
        else:
            raise RuntimeError("Login timed out.")

    # 5. Wait for Gemini page to fully load (consent redirect etc.)
    time.sleep(3)
    for _ in range(10):
        url = get_current_url(ws_url)
        if "gemini.google.com" in url and "consent" not in url:
            break
        time.sleep(1)

    # 6. Extract cookies — filter to .google.com only, deduplicate
    # Network.getAllCookies returns cookies from ALL domains (.youtube.com,
    # .google.de, etc.). Duplicates with different domains cause auth issues
    # when gemini_webapi picks the wrong value.
    all_cookies = get_all_cookies(ws_url)
    if not all_cookies:
        raise RuntimeError("No cookies extracted — make sure you're logged in.")

    # Keep .google.com domain cookies, prefer / path over specific paths
    seen: dict[str, dict] = {}
    for c in all_cookies:
        domain = c.get("domain", "")
        if not domain.endswith(".google.com"):
            continue
        name = c["name"]
        existing = seen.get(name)
        if existing is None:
            seen[name] = c
        elif domain == ".google.com" and existing.get("domain") != ".google.com":
            seen[name] = c  # Prefer exact .google.com over subdomains
        elif c.get("path", "/") == "/" and existing.get("path", "/") != "/":
            seen[name] = c  # Prefer root path

    cookies = list(seen.values())

    # 7. Extract metadata from page
    html = get_page_html(ws_url)
    email = extract_email(html)
    csrf_token = extract_csrf_token(html)
    session_id = extract_session_id(html)
    build_label = extract_build_label(html)

    # 8. Save to nlm profile directory via AuthManager
    from gdr_cli.auth import AuthManager

    auth = AuthManager(profile)
    auth.save_profile(
        cookies=cookies,
        csrf_token=csrf_token,
        session_id=session_id,
        email=email,
        build_label=build_label,
        force=True,
    )

    return {
        "cookies": cookies,
        "email": email,
        "csrf_token": csrf_token,
        "session_id": session_id,
        "build_label": build_label,
        "cookie_count": len(cookies),
    }
