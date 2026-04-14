"""Cookie loading from nlm profiles. No re-authentication — reuses nlm's login."""

from __future__ import annotations

import json
from pathlib import Path


class AuthError(Exception):
    """Raised when cookies cannot be loaded or are invalid."""
    pass


def load_cookies(cookies_file: Path) -> dict[str, str]:
    """Load cookies from an nlm profile cookies.json file.

    nlm stores cookies as list[dict] with name/value/domain/path keys.
    Also supports plain dict format as fallback.

    Returns dict of cookie name -> value.
    Raises AuthError if file missing or __Secure-1PSID absent.
    """
    if not cookies_file.exists():
        raise AuthError(f"Cookie file not found: {cookies_file}")

    try:
        raw = json.loads(cookies_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise AuthError(f"Failed to parse cookies: {e}") from e

    cookies: dict[str, str] = {}

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "name" in item and "value" in item:
                cookies[item["name"]] = item["value"]
    elif isinstance(raw, dict):
        cookies = {str(k): str(v) for k, v in raw.items()}
    else:
        raise AuthError(f"Unexpected cookie format: {type(raw).__name__}")

    if "__Secure-1PSID" not in cookies:
        raise AuthError(
            "__Secure-1PSID not found in cookies. "
            "Run 'nlm login' first to authenticate with Google."
        )

    return cookies


def get_profile_cookies(profile_name: str = "default") -> dict[str, str]:
    """Load cookies for a given nlm profile.

    Convenience wrapper that resolves the cookie file path.
    """
    from gdr_cli.config import get_cookies_file

    return load_cookies(get_cookies_file(profile_name))