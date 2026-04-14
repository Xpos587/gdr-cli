# GDR CLI Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite gdr-cli with nlm-inspired auth (Profile + AuthManager), custom exceptions with hints, persistent config, and Rich-polished CLI — while keeping gemini_webapi for HTTP and the existing CDP login.

**Architecture:** Auth module uses Profile dataclass + AuthManager class with save/load/list profiles. Custom exceptions carry user-facing hints. Config module adds persistent JSON config alongside existing path helpers. CLI commands catch typed exceptions and display Rich-formatted errors.

**Tech Stack:** Python 3.12+, uv, gemini_webapi >= 2.0.0, typer >= 0.15.0, rich >= 13.0.0, websocket-client >= 1.0.0, pydantic >= 2.0, pytest, pytest-asyncio

---

### Task 1: Custom Exceptions

**Files:**

- Create: `src/gdr_cli/exceptions.py`
- Test: `tests/test_exceptions.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for exceptions.py — custom exception hierarchy."""

import pytest
from gdr_cli.exceptions import (
    GDRError, AuthError, ProfileNotFoundError,
    AccountMismatchError, ResearchError, RateLimitError,
)


class TestGDRError:
    def test_base_error_has_message(self):
        err = GDRError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"

    def test_base_error_optional_hint(self):
        err = GDRError("msg", hint="try again")
        assert err.hint == "try again"


class TestAuthError:
    def test_auth_error_is_gdr_error(self):
        assert issubclass(AuthError, GDRError)

    def test_auth_error_with_hint(self):
        err = AuthError("Missing cookies", hint="Run 'gdr login'")
        assert "Missing cookies" in str(err)
        assert err.hint == "Run 'gdr login'"


class TestProfileNotFoundError:
    def test_includes_profile_name(self):
        err = ProfileNotFoundError("work")
        assert "work" in str(err)
        assert err.profile_name == "work"


class TestAccountMismatchError:
    def test_includes_both_emails(self):
        err = AccountMismatchError(stored_email="a@b.com", new_email="c@d.com")
        assert "a@b.com" in str(err)
        assert "c@d.com" in str(err)


class TestResearchError:
    def test_is_gdr_error(self):
        assert issubclass(ResearchError, GDRError)


class TestRateLimitError:
    def test_has_default_hint(self):
        err = RateLimitError()
        assert err.hint is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_exceptions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gdr_cli.exceptions'`

- [ ] **Step 3: Write minimal implementation**

Create `src/gdr_cli/exceptions.py`:

```python
"""Custom exception hierarchy for gdr-cli."""


class GDRError(Exception):
    """Base error for all gdr-cli exceptions."""

    def __init__(self, message: str, *, hint: str | None = None):
        self.message = message
        self.hint = hint
        super().__init__(message)


class AuthError(GDRError):
    """Authentication failure (missing cookies, expired session)."""


class ProfileNotFoundError(GDRError):
    """Requested auth profile does not exist."""

    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        super().__init__(
            f"Profile not found: {profile_name}",
            hint="Run 'gdr login' to create a profile.",
        )


class AccountMismatchError(GDRError):
    """Attempted to save credentials for a different Google account."""

    def __init__(self, stored_email: str, new_email: str):
        self.stored_email = stored_email
        self.new_email = new_email
        super().__init__(
            f"Account mismatch: profile has {stored_email}, trying to save {new_email}",
            hint="Use --force to overwrite, or create a new profile with -p <name>.",
        )


class ResearchError(GDRError):
    """Deep research specific error (plan not created, polling failed)."""


class RateLimitError(GDRError):
    """Gemini usage limit exceeded."""

    def __init__(self):
        super().__init__(
            "Deep Research usage limit exceeded.",
            hint="Wait a while or check your Gemini Advanced subscription.",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_exceptions.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/exceptions.py tests/test_exceptions.py
git commit -m "feat: add custom exception hierarchy with user hints"
```

---

### Task 2: Profile Dataclass

**Files:**

- Create: (add to `src/gdr_cli/auth.py` — rewrite existing file)
- Test: `tests/test_auth.py` (rewrite existing)

- [ ] **Step 1: Write the failing tests for Profile**

Add these tests to a new `tests/test_auth.py` (replace existing content):

```python
"""Tests for auth.py — Profile dataclass and AuthManager."""

import json
from datetime import datetime
from pathlib import Path
import pytest
from gdr_cli.auth import Profile
from gdr_cli.exceptions import AuthError


class TestProfile:
    def test_from_list_cookies_dict(self):
        profile = Profile(
            name="default",
            cookies=[
                {"name": "__Secure-1PSID", "value": "psid-val"},
                {"name": "__Secure-1PSIDTS", "value": "psidts-val"},
            ],
            email="user@gmail.com",
        )
        assert profile.name == "default"
        assert profile.email == "user@gmail.com"

    def test_to_dict_roundtrip(self):
        profile = Profile(
            name="work",
            cookies=[{"name": "__Secure-1PSID", "value": "v"}],
            csrf_token="csrf-123",
            session_id="sid-456",
            email="a@b.com",
            build_label="label-1",
            last_validated=datetime(2026, 4, 14, 12, 0, 0),
        )
        d = profile.to_dict()
        assert d["name"] == "work"
        assert d["cookies"] == [{"name": "__Secure-1PSID", "value": "v"}]
        assert d["csrf_token"] == "csrf-123"
        assert d["email"] == "a@b.com"
        assert d["last_validated"] == "2026-04-14T12:00:00"

    def test_from_dict_with_list_cookies(self):
        data = {
            "name": "default",
            "cookies": [{"name": "__Secure-1PSID", "value": "v"}],
            "csrf_token": "csrf",
            "email": "e@e.com",
            "last_validated": "2026-04-14T12:00:00",
        }
        profile = Profile.from_dict(data)
        assert profile.cookies == [{"name": "__Secure-1PSID", "value": "v"}]
        assert profile.last_validated == datetime(2026, 4, 14, 12, 0, 0)

    def test_from_dict_with_dict_cookies(self):
        data = {
            "name": "default",
            "cookies": {"__Secure-1PSID": "v", "HSID": "h"},
            "email": "e@e.com",
        }
        profile = Profile.from_dict(data)
        assert profile.cookies == {"__Secure-1PSID": "v", "HSID": "h"}

    def test_from_dict_defaults(self):
        data = {"name": "test"}
        profile = Profile.from_dict(data)
        assert profile.name == "test"
        assert profile.cookies == []
        assert profile.csrf_token is None
        assert profile.email is None

    def test_get_cookies_from_list(self):
        profile = Profile(
            name="d",
            cookies=[
                {"name": "__Secure-1PSID", "value": "pv"},
                {"name": "HSID", "value": "hv"},
            ],
        )
        cookies = profile.get_cookies()
        assert cookies == {"__Secure-1PSID": "pv", "HSID": "hv"}

    def test_get_cookies_from_dict(self):
        profile = Profile(
            name="d",
            cookies={"__Secure-1PSID": "pv", "HSID": "hv"},
        )
        cookies = profile.get_cookies()
        assert cookies == {"__Secure-1PSID": "pv", "HSID": "hv"}

    def test_get_cookies_validates_psid(self):
        profile = Profile(name="d", cookies=[{"name": "HSID", "value": "h"}])
        with pytest.raises(AuthError, match="__Secure-1PSID"):
            profile.get_cookies()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_auth.py -v`
Expected: FAIL — `ImportError: cannot import name 'Profile' from 'gdr_cli.auth'`

- [ ] **Step 3: Implement Profile in auth.py**

Rewrite `src/gdr_cli/auth.py`:

```python
"""Authentication: Profile dataclass, cookie loading, validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from gdr_cli.exceptions import AuthError


@dataclass
class Profile:
    """An authentication profile with cookies and metadata."""

    name: str
    cookies: list[dict[str, Any]] | dict[str, str] = field(default_factory=list)
    csrf_token: str | None = None
    session_id: str | None = None
    email: str | None = None
    build_label: str | None = None
    last_validated: datetime | None = None

    def get_cookies(self) -> dict[str, str]:
        """Return cookies as a simple name→value dict.

        Raises AuthError if __Secure-1PSID is missing.
        """
        if isinstance(self.cookies, list):
            result = {
                c["name"]: c["value"]
                for c in self.cookies
                if isinstance(c, dict) and "name" in c and "value" in c
            }
        elif isinstance(self.cookies, dict):
            result = {str(k): str(v) for k, v in self.cookies.items()}
        else:
            result = {}

        if "__Secure-1PSID" not in result:
            raise AuthError(
                "__Secure-1PSID not found in cookies.",
                hint="Run 'gdr login' to authenticate.",
            )
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile for storage."""
        return {
            "name": self.name,
            "cookies": self.cookies,
            "csrf_token": self.csrf_token,
            "session_id": self.session_id,
            "email": self.email,
            "build_label": self.build_label,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Deserialize profile from stored data."""
        last_validated = None
        if data.get("last_validated"):
            try:
                last_validated = datetime.fromisoformat(data["last_validated"])
            except (ValueError, TypeError):
                pass

        return cls(
            name=data.get("name", "default"),
            cookies=data.get("cookies", []),
            csrf_token=data.get("csrf_token"),
            session_id=data.get("session_id"),
            email=data.get("email"),
            build_label=data.get("build_label"),
            last_validated=last_validated,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_auth.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/auth.py tests/test_auth.py
git commit -m "feat: add Profile dataclass with serialization and cookie validation"
```

---

### Task 3: AuthManager

**Files:**

- Modify: `src/gdr_cli/auth.py` (add AuthManager)
- Test: `tests/test_auth.py` (add AuthManager tests)

- [ ] **Step 1: Write the failing tests for AuthManager**

Add to `tests/test_auth.py`:

```python
from gdr_cli.auth import AuthManager
from gdr_cli.exceptions import ProfileNotFoundError, AccountMismatchError


class TestAuthManager:
    def _make_manager(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.auth.get_profile_dir",
                            lambda name: tmp_path / "profiles" / name)
        return AuthManager("default")

    def test_profile_exists_false(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        assert mgr.profile_exists() is False

    def test_save_and_load_profile(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(
            cookies=[{"name": "__Secure-1PSID", "value": "pv"},
                     {"name": "__Secure-1PSIDTS", "value": "ptv"}],
            csrf_token="csrf",
            email="user@gmail.com",
        )
        assert mgr.profile_exists() is True
        profile = mgr.load_profile()
        assert profile.email == "user@gmail.com"
        assert profile.csrf_token == "csrf"

    def test_save_sets_restrictive_permissions(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(
            cookies=[{"name": "__Secure-1PSID", "value": "v"}],
        )
        cookies_file = tmp_path / "profiles" / "default" / "cookies.json"
        # Mode may be masked by umask on some systems — check it's at most 0o600
        assert (cookies_file.stat().st_mode & 0o777) <= 0o600

    def test_load_raises_when_not_found(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        with pytest.raises(ProfileNotFoundError):
            mgr.load_profile()

    def test_get_cookies(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(
            cookies=[{"name": "__Secure-1PSID", "value": "pv"},
                     {"name": "__Secure-1PSIDTS", "value": "ptv"}],
        )
        cookies = mgr.get_cookies()
        assert cookies["__Secure-1PSID"] == "pv"

    def test_delete_profile(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        assert mgr.profile_exists() is True
        mgr.delete_profile()
        assert mgr.profile_exists() is False

    def test_list_profiles(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.auth.get_profiles_dir",
                            lambda: tmp_path / "profiles")
        mgr = AuthManager("default")
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        mgr2 = AuthManager("work")
        mgr2.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v2"}])
        profiles = AuthManager.list_profiles()
        assert sorted(profiles) == ["default", "work"]

    def test_account_mismatch_guard(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(
            cookies=[{"name": "__Secure-1PSID", "value": "v"}],
            email="old@gmail.com",
        )
        with pytest.raises(AccountMismatchError):
            mgr.save_profile(
                cookies=[{"name": "__Secure-1PSID", "value": "v2"}],
                email="new@gmail.com",
            )

    def test_force_overwrites_mismatch(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(
            cookies=[{"name": "__Secure-1PSID", "value": "v"}],
            email="old@gmail.com",
        )
        mgr.save_profile(
            cookies=[{"name": "__Secure-1PSID", "value": "v2"}],
            email="new@gmail.com",
            force=True,
        )
        assert mgr.load_profile().email == "new@gmail.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_auth.py::TestAuthManager -v`
Expected: FAIL — `ImportError: cannot import name 'AuthManager'`

- [ ] **Step 3: Add AuthManager to auth.py**

Add to the end of `src/gdr_cli/auth.py`:

```python
class AuthManager:
    """Manages authentication profiles (cookies + metadata) on disk.

    Shares storage format with nlm CLI at ~/.notebooklm-mcp-cli/profiles/.
    """

    def __init__(self, profile_name: str = "default"):
        self.profile_name = profile_name
        self._profile: Profile | None = None

    @property
    def profile_dir(self) -> Path:
        from gdr_cli.config import get_profile_dir
        return get_profile_dir(self.profile_name)

    @property
    def cookies_file(self) -> Path:
        return self.profile_dir / "cookies.json"

    @property
    def metadata_file(self) -> Path:
        return self.profile_dir / "metadata.json"

    def profile_exists(self) -> bool:
        return self.cookies_file.exists()

    def load_profile(self, force_reload: bool = False) -> Profile:
        if self._profile is not None and not force_reload:
            return self._profile

        if not self.profile_exists():
            raise ProfileNotFoundError(self.profile_name)

        try:
            raw_cookies = json.loads(self.cookies_file.read_text(encoding="utf-8"))
            metadata = {}
            if self.metadata_file.exists():
                metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise AuthError(f"Failed to load profile '{self.profile_name}': {e}") from e

        self._profile = Profile(
            name=self.profile_name,
            cookies=raw_cookies,
            csrf_token=metadata.get("csrf_token"),
            session_id=metadata.get("session_id"),
            email=metadata.get("email"),
            build_label=metadata.get("build_label"),
            last_validated=datetime.fromisoformat(metadata["last_validated"])
            if metadata.get("last_validated") else None,
        )
        return self._profile

    def save_profile(
        self,
        cookies: list[dict[str, Any]] | dict[str, str],
        *,
        csrf_token: str | None = None,
        session_id: str | None = None,
        email: str | None = None,
        build_label: str | None = None,
        force: bool = False,
    ) -> Profile:
        from gdr_cli.exceptions import AccountMismatchError

        # Guard: account mismatch
        if not force and email and self.metadata_file.exists():
            try:
                existing = json.loads(self.metadata_file.read_text(encoding="utf-8"))
                stored_email = existing.get("email")
                if stored_email and stored_email != email:
                    raise AccountMismatchError(
                        stored_email=stored_email, new_email=email
                    )
            except (json.JSONDecodeError, KeyError):
                pass

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.profile_dir.chmod(0o700)

        self.cookies_file.write_text(
            json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.cookies_file.chmod(0o600)

        metadata = {
            "csrf_token": csrf_token,
            "session_id": session_id,
            "email": email,
            "build_label": build_label,
            "last_validated": datetime.now().isoformat(),
        }
        self.metadata_file.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.metadata_file.chmod(0o600)

        self._profile = Profile(
            name=self.profile_name,
            cookies=cookies,
            csrf_token=csrf_token,
            session_id=session_id,
            email=email,
            build_label=build_label,
            last_validated=datetime.now(),
        )
        return self._profile

    def delete_profile(self) -> None:
        import shutil
        from gdr_cli.config import get_profiles_dir

        profile_path = get_profiles_dir() / self.profile_name
        if profile_path.exists():
            shutil.rmtree(profile_path)
        self._profile = None

    def get_cookies(self) -> dict[str, str]:
        return self.load_profile().get_cookies()

    @staticmethod
    def list_profiles() -> list[str]:
        from gdr_cli.config import get_profiles_dir
        profiles_dir = get_profiles_dir()
        if not profiles_dir.exists():
            return []
        return [d.name for d in profiles_dir.iterdir() if d.is_dir()]


# Backward-compatible convenience function
def get_profile_cookies(profile_name: str = "default") -> dict[str, str]:
    """Load cookies for a profile (backward compat for research.py/chat.py)."""
    return AuthManager(profile_name).get_cookies()
```

Also add `from gdr_cli.config import get_profiles_dir` to the config import section at the top.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_auth.py -v`
Expected: 16 passed (8 Profile + 8 AuthManager)

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/auth.py tests/test_auth.py
git commit -m "feat: add AuthManager with profile save/load/delete/list"
```

---

### Task 4: Config Module — Persistent JSON Config

**Files:**

- Modify: `src/gdr_cli/config.py` (rewrite)
- Test: `tests/test_config.py` (rewrite)

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_config.py`:

```python
"""Tests for config.py — path resolution and persistent config."""

from pathlib import Path
import json
import pytest
from gdr_cli.config import (
    get_base_dir, get_profiles_dir, get_profile_dir,
    get_cookies_file, get_metadata_file, get_config,
)


class TestPaths:
    def test_get_base_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "nlm")
        assert get_base_dir() == tmp_path / "nlm"

    def test_get_profiles_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "nlm")
        assert get_profiles_dir() == tmp_path / "nlm" / "profiles"

    def test_get_profile_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "nlm")
        assert get_profile_dir("work") == tmp_path / "nlm" / "profiles" / "work"

    def test_get_cookies_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "nlm")
        assert get_cookies_file("default") == tmp_path / "nlm" / "profiles" / "default" / "cookies.json"

    def test_get_metadata_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "nlm")
        assert get_metadata_file("default") == tmp_path / "nlm" / "profiles" / "default" / "metadata.json"


class TestGDRConfig:
    def test_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "nlm")
        cfg = get_config()
        assert cfg.default_profile == "default"
        assert cfg.default_timeout == 30
        assert cfg.default_poll_interval == 10.0
        assert cfg.auto_confirm is True
        assert cfg.output_dir is None

    def test_loads_from_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "nlm")
        config_file = tmp_path / "nlm" / "gdr-config.json"
        config_file.parent.mkdir(parents=True)
        config_file.write_text(json.dumps({
            "default_profile": "work",
            "default_timeout": 60,
            "auto_confirm": False,
        }))
        cfg = get_config()
        assert cfg.default_profile == "work"
        assert cfg.default_timeout == 60
        assert cfg.auto_confirm is False

    def test_handles_corrupt_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "nlm")
        config_file = tmp_path / "nlm" / "gdr-config.json"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("not json")
        cfg = get_config()
        assert cfg.default_profile == "default"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_config.py -v`
Expected: FAIL — `config_file` path mismatch (old code uses `config.toml`, test expects `gdr-config.json`)

- [ ] **Step 3: Rewrite config.py**

Replace `src/gdr_cli/config.py`:

```python
"""Path resolution and persistent config for gdr-cli."""

from __future__ import annotations

import json
from pathlib import Path
from pydantic import BaseModel


_BASE_DIR = Path.home() / ".notebooklm-mcp-cli"


class GDRConfig(BaseModel):
    """Persistent CLI configuration."""

    default_profile: str = "default"
    default_timeout: int = 30
    default_poll_interval: float = 10.0
    auto_confirm: bool = True
    output_dir: str | None = None


def get_base_dir() -> Path:
    return _BASE_DIR


def get_profiles_dir() -> Path:
    return _BASE_DIR / "profiles"


def get_profile_dir(profile_name: str) -> Path:
    return get_profiles_dir() / profile_name


def get_cookies_file(profile_name: str = "default") -> Path:
    return get_profile_dir(profile_name) / "cookies.json"


def get_metadata_file(profile_name: str = "default") -> Path:
    return get_profile_dir(profile_name) / "metadata.json"


def get_config() -> GDRConfig:
    config_path = _BASE_DIR / "gdr-config.json"
    if not config_path.exists():
        return GDRConfig()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return GDRConfig(**data)
    except (json.JSONDecodeError, ValueError):
        return GDRConfig()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_config.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/config.py tests/test_config.py
git commit -m "refactor: switch config from TOML to JSON, add output_dir and poll_interval"
```

---

### Task 5: Update research.py to Use AuthManager

**Files:**

- Modify: `src/gdr_cli/research.py`
- Modify: `tests/test_research.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_research.py`:

```python
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
    def test_raises_auth_error_on_missing_profile(self):
        from gdr_cli.auth import AuthManager
        from gdr_cli.exceptions import ProfileNotFoundError
        import asyncio

        with patch.object(AuthManager, "get_cookies", side_effect=ProfileNotFoundError("default")):
            with pytest.raises(ProfileNotFoundError):
                asyncio.run(run_deep_research("test query"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_research.py -v`
Expected: FAIL — the mock target changed from `get_profile_cookies` to `AuthManager.get_cookies`

- [ ] **Step 3: Update research.py**

Replace `src/gdr_cli/research.py`:

```python
"""Deep research orchestration using gemini_webapi."""

from __future__ import annotations

import sys
from typing import Callable

from gemini_webapi import GeminiClient
from gemini_webapi.types import DeepResearchPlan, DeepResearchResult, DeepResearchStatus

from gdr_cli.auth import AuthManager


def _status_callback(
    plan: DeepResearchPlan,
    on_status: Callable[[DeepResearchStatus], None] | None,
) -> Callable[[DeepResearchStatus], None]:
    def _callback(status: DeepResearchStatus) -> None:
        state_label = status.state.upper()
        title = status.title or plan.title or "Research"
        print(f"  [{state_label}] {title}", file=sys.stderr)
        if status.notes:
            for note in status.notes[:3]:
                print(f"    - {note}", file=sys.stderr)
        if on_status:
            on_status(status)
    return _callback


async def run_deep_research(
    query: str,
    profile: str = "default",
    timeout_min: float = 30,
    poll_interval: float = 10.0,
    auto_confirm: bool = True,
    on_status: Callable[[DeepResearchStatus], None] | None = None,
) -> DeepResearchResult:
    """Run a full deep research cycle: plan -> confirm -> poll -> result."""
    auth = AuthManager(profile)
    cookies = auth.get_cookies()

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=timeout_min * 60)

    try:
        plan = await client.create_deep_research_plan(query)

        if not auto_confirm:
            print(f"\nResearch Plan: {plan.title}", file=sys.stderr)
            print(f"ETA: {plan.eta_text}", file=sys.stderr)
            for i, step in enumerate(plan.steps, 1):
                print(f"  {i}. {step}", file=sys.stderr)

            try:
                input("\nPress Enter to start research, Ctrl+C to cancel...")
            except (KeyboardInterrupt, EOFError):
                print("\nCancelled.", file=sys.stderr)
                return DeepResearchResult(plan=plan, done=False)

        result = await client.deep_research(
            plan.query or query,
            poll_interval=poll_interval,
            timeout=timeout_min * 60,
            on_status=_status_callback(plan, on_status),
        )
        return result
    finally:
        await client.close()


def format_result(result: DeepResearchResult) -> str:
    """Format a DeepResearchResult for terminal output."""
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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_research.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/research.py tests/test_research.py
git commit -m "refactor: research.py uses AuthManager instead of raw cookie loading"
```

---

### Task 6: Update chat.py to Use AuthManager

**Files:**

- Modify: `src/gdr_cli/chat.py`

- [ ] **Step 1: Update chat.py**

Replace `src/gdr_cli/chat.py`:

```python
"""Regular chat with Gemini via gemini_webapi."""

from __future__ import annotations

from gemini_webapi import GeminiClient

from gdr_cli.auth import AuthManager


async def send_message(
    prompt: str,
    profile: str = "default",
    timeout: float = 120,
) -> str:
    """Send a single message to Gemini and return the text response."""
    auth = AuthManager(profile)
    cookies = auth.get_cookies()

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=timeout)

    try:
        chat = client.start_chat()
        output = await chat.send_message(prompt)
        return output.text or ""
    finally:
        await client.close()
```

- [ ] **Step 2: Run all tests to verify nothing broke**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/chat.py
git commit -m "refactor: chat.py uses AuthManager instead of raw cookie loading"
```

---

### Task 7: Update CDP Login to Use AuthManager

**Files:**

- Modify: `src/gdr_cli/cdp.py` (login_via_cdp only)

- [ ] **Step 1: Update the save section of login_via_cdp**

In `src/gdr_cli/cdp.py`, the `login_via_cdp()` function currently saves cookies and metadata manually (lines 316-334). Replace the "Save to nlm profile directory" section (starting at the comment `# 8. Save to nlm profile directory`) with a call to AuthManager.

Find this block in cdp.py (approximately lines 316-344):

```python
    # 8. Save to nlm profile directory
    profile_dir = get_profile_dir(profile)
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Save cookies
    cookies_file = profile_dir / "cookies.json"
    cookies_file.write_text(json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8")
    cookies_file.chmod(0o600)

    # Save metadata
    metadata = {
        "csrf_token": csrf_token,
        "session_id": session_id,
        "email": email,
        "build_label": build_label,
        "last_validated": datetime.now().isoformat(),
    }
    metadata_file = profile_dir / "metadata.json"
    metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    metadata_file.chmod(0o600)

    return {
        "cookies": cookies,
        "email": email,
        "csrf_token": csrf_token,
        "session_id": session_id,
        "build_label": build_label,
        "cookie_count": len(cookies),
    }
```

Replace with:

```python
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
```

Also remove the now-unused imports at the top of cdp.py: `from datetime import datetime` and `from gdr_cli.config import get_profile_dir`.

- [ ] **Step 2: Run all tests**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/cdp.py
git commit -m "refactor: cdp login uses AuthManager.save_profile for cookie storage"
```

---

### Task 8: Rewrite CLI with Rich Polish and Custom Exceptions

**Files:**

- Modify: `src/gdr_cli/cli.py` (rewrite)
- Modify: `tests/test_cli.py` (rewrite)

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_cli.py`:

```python
"""Tests for cli.py — smoke tests and exception handling."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
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
        with patch("gdr_cli.cli.send_message", side_effect=AuthError("No cookies", hint="Run 'gdr login'")):
            result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 2
        assert "Run 'gdr login'" in result.output

    def test_research_rate_limit(self):
        from gemini_webapi.exceptions import UsageLimitExceeded
        with patch("gdr_cli.cli.run_deep_research", side_effect=UsageLimitExceeded("limited")):
            result = runner.invoke(app, ["research", "test"])
        assert result.exit_code == 3
        assert "limit" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest tests/test_cli.py -v`
Expected: FAIL — import paths changed, exception handling not matching

- [ ] **Step 3: Rewrite cli.py**

Replace `src/gdr_cli/cli.py`:

```python
"""GDR CLI — Gemini Deep Research via HTTP, shared auth with nlm."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from gdr_cli import __version__
from gdr_cli.exceptions import AuthError, ProfileNotFoundError, ResearchError

app = typer.Typer(
    name="gdr",
    help="Gemini Deep Research CLI — chat and deep research via HTTP, shares auth with nlm",
    no_args_is_help=True,
    add_completion=False,
)
console = Console(stderr=True)


def version_callback(value: bool):
    if value:
        console.print(f"gdr-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit",
    ),
):
    pass


@app.command()
def chat(
    prompt: str = typer.Argument(help="Message to send to Gemini"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
):
    """Send a message to Gemini and get a response (quick test)."""
    from gdr_cli.chat import send_message

    try:
        response = asyncio.run(send_message(prompt, profile=profile))
    except AuthError as e:
        console.print(f"[red]Auth Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(response)


@app.command()
def research(
    query: str = typer.Argument(help="Research topic or question"),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name",
    ),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Max research time in minutes",
    ),
    poll_interval: float = typer.Option(
        10.0, "--poll", help="Status polling interval in seconds",
    ),
    no_confirm: bool = typer.Option(
        False, "--no-confirm", "-n", help="Show plan and wait for manual confirmation",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write report to file",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Auto-save report to DIR/{date}-{slug}.md",
    ),
):
    """Run Gemini Deep Research on a topic."""
    from gdr_cli.research import format_result, run_deep_research
    from gdr_cli.exceptions import RateLimitError

    try:
        result = asyncio.run(
            run_deep_research(
                query=query,
                profile=profile,
                timeout_min=timeout,
                poll_interval=poll_interval,
                auto_confirm=not no_confirm,
            )
        )
    except AuthError as e:
        console.print(f"[red]Auth Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(2)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        from gemini_webapi.exceptions import UsageLimitExceeded

        if isinstance(e, UsageLimitExceeded):
            console.print("[red]Error:[/red] Deep Research usage limit exceeded.")
            console.print("Wait a while or check your Gemini Advanced subscription.")
            raise typer.Exit(3)
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    report = format_result(result)

    out_path = output
    if not out_path and output_dir and result.text:
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9\s-]", "", query.lower()).replace(" ", "-")[:60].rstrip("-")
        out_path = output_dir / f"{date.today()}-{slug}.md"

    if out_path and result.text:
        header = [
            "# Deep Research Report",
            "",
            f"> Query: {query}",
            f"> Status: {'COMPLETED' if result.done else 'INCOMPLETE'}",
            f"> Title: {result.plan.title or '(untitled)'}",
            "",
            result.text,
        ]
        out_path.write_text("\n".join(header), encoding="utf-8")
        console.print(f"\nReport saved to: [bold]{out_path}[/bold]")
    else:
        console.print()
        console.print(report)


@app.command()
def doctor(
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile to check",
    ),
):
    """Diagnose auth and connectivity issues."""
    from gdr_cli.auth import AuthManager
    from gdr_cli.config import get_cookies_file, get_metadata_file, get_profile_dir

    console.print("[bold]GDR Doctor[/bold]\n")

    auth = AuthManager(profile)

    # 1. Check profile directory
    profile_dir = get_profile_dir(profile)
    if not profile_dir.exists():
        console.print(f"  [red]FAIL[/red] Profile directory not found: {profile_dir}")
        console.print(f"  Run [bold]gdr login[/bold] first to authenticate.")
        raise typer.Exit(1)
    console.print(f"  [green]OK[/green] Profile directory: {profile_dir}")

    # 2. Check cookies file
    cookies_file = get_cookies_file(profile)
    if not cookies_file.exists():
        console.print(f"  [red]FAIL[/red] Cookies file not found: {cookies_file}")
        console.print(f"  Run [bold]gdr login[/bold] first.")
        raise typer.Exit(1)

    try:
        auth.load_profile()
    except AuthError as e:
        console.print(f"  [red]FAIL[/red] Could not load profile: {e.message}")
        raise typer.Exit(1)

    try:
        cookies = auth.get_cookies()
    except AuthError as e:
        console.print(f"  [red]FAIL[/red] {e.message}")
        raise typer.Exit(1)

    console.print(f"  [green]OK[/green] Cookies loaded ({len(cookies)} cookies)")

    # 3. Check required cookies
    required = {"__Secure-1PSID", "__Secure-1PSIDTS"}
    missing = required - set(cookies.keys())
    if missing:
        console.print(f"  [yellow]WARN[/yellow] Missing cookies: {missing}")
    else:
        console.print(f"  [green]OK[/green] Required cookies present")

    # 4. Check metadata
    metadata_file = get_metadata_file(profile)
    if metadata_file.exists():
        import json as _json
        meta = _json.loads(metadata_file.read_text())
        email = meta.get("email", "(unknown)")
        validated = meta.get("last_validated", "(never)")
        console.print(f"  [green]OK[/green] Email: {email}")
        console.print(f"  [green]OK[/green] Last validated: {validated}")
    else:
        console.print(f"  [yellow]WARN[/yellow] No metadata file (optional)")

    # 5. Test Gemini connectivity
    console.print("\n  Testing Gemini connectivity...")
    try:
        result = asyncio.run(_test_connectivity(cookies))
        if result:
            console.print(f"  [green]OK[/green] Gemini: authenticated and accessible")
            console.print(f"  [green]OK[/green] Deep Research: {result}")
        else:
            console.print(f"  [red]FAIL[/red] Gemini returned no access token")
    except Exception as e:
        console.print(f"  [red]FAIL[/red] Gemini connectivity: {e}")

    console.print()


async def _test_connectivity(cookies: dict[str, str]) -> str | None:
    """Test that cookies work with gemini_webapi."""
    from gemini_webapi import GeminiClient

    client = GeminiClient(
        secure_1psid=cookies.get("__Secure-1PSID"),
        secure_1psidts=cookies.get("__Secure-1PSIDTS"),
    )
    await client.init(timeout=30)

    try:
        snapshot = await client.inspect_account_status()
        summary = snapshot.get("summary", {})
        dr_available = summary.get("deep_research_feature_present", False)
        return "available" if dr_available else "not available (check subscription)"
    finally:
        await client.close()


@app.command()
def login(
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Auth profile name (shared with nlm)",
    ),
    cdp_url: str = typer.Option(
        "http://127.0.0.1:9222", "--cdp-url", help="Chrome CDP endpoint",
    ),
    launch: bool = typer.Option(
        True, "--launch/--no-launch", "-l", help="Auto-launch Chrome if CDP not reachable",
    ),
):
    """Authenticate with Google via Chrome CDP (stores cookies in nlm profile dir)."""
    from gdr_cli.cdp import login_via_cdp

    console.print("[bold]GDR Login[/bold]\n")

    try:
        result = asyncio.run(
            _async_login(profile=profile, cdp_url=cdp_url, auto_launch=launch)
        )
    except Exception as e:
        console.print(f"  [red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"  [green]OK[/green] Cookies extracted ({result['cookie_count']} cookies)")
    if result["email"]:
        console.print(f"  [green]OK[/green] Email: {result['email']}")
    console.print(f"  [green]OK[/green] Saved to profile: {profile}")
    console.print()


async def _async_login(
    profile: str, cdp_url: str, auto_launch: bool
) -> dict:
    """Run CDP login in a thread pool (CDP uses sync websocket)."""
    from gdr_cli.cdp import login_via_cdp

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, login_via_cdp, profile, cdp_url, auto_launch
    )
```

- [ ] **Step 4: Run all tests**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add src/gdr_cli/cli.py tests/test_cli.py
git commit -m "refactor: CLI uses custom exceptions with hints and AuthManager"
```

---

### Task 9: Update pyproject.toml

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Add pydantic dependency explicitly**

Current `pyproject.toml` already has `gemini-webapi>=2.0.0` which pulls in pydantic transitively, but we should declare it explicitly since we use it in config.py.

In the `dependencies` list, add `"pydantic>=2.0.0"`:

```toml
dependencies = [
    "gemini-webapi>=2.0.0",
    "typer>=0.15.0",
    "rich>=13.0.0",
    "websocket-client>=1.0.0",
    "pydantic>=2.0.0",
]
```

- [ ] **Step 2: Run uv sync and verify**

Run: `cd /home/michael/Github/gdr-cli && uv sync`
Expected: Success (pydantic already installed transitively)

- [ ] **Step 3: Run all tests**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add pyproject.toml uv.lock
git commit -m "build: add explicit pydantic dependency"
```

---

### Task 10: Update README

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Rewrite README.md**

```markdown
# gdr-cli

Gemini Deep Research CLI — run Google's Deep Research from the terminal.
Shares authentication with [notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli).

## Features

- **Deep Research** — Run Gemini's multi-source deep research investigations
- **Chat** — Quick single-message chat with Gemini
- **Shared Auth** — Login once, use with both gdr and nlm
- **CDP Login** — Browser-based authentication via Chrome DevTools Protocol

## Install

```bash
uv tool install git+https://github.com/<user>/gdr-cli.git
```

Or from source:

```bash
git clone https://github.com/<user>/gdr-cli.git
cd gdr-cli
uv sync
uv run gdr --help
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Chrome/Chromium (for login)
- Gemini Advanced subscription (for Deep Research)

## Quick Start

### Login

```bash
uv run gdr login
```

Opens Chrome for Google authentication. Cookies are saved to `~/.notebooklm-mcp-cli/profiles/default/`.

### Deep Research

```bash
# Auto-confirm plan (default)
uv run gdr research "AI safety research landscape 2026"

# Manual plan review
uv run gdr research "quantum computing applications" --no-confirm

# Save to file
uv run gdr research "Rust vs Go for systems programming" -o report.md

# Custom timeout and polling
uv run gdr research "long topic" --timeout 60 --poll 15
```

### Chat

```bash
uv run gdr chat "Explain the difference between TCP and UDP"
```

### Doctor

```bash
uv run gdr doctor
```

Checks auth, cookies, and Gemini connectivity.

## Commands

| Command | Description |
|---------|-------------|
| `gdr research <query>` | Run Deep Research on a topic |
| `gdr chat <prompt>` | Send a message to Gemini |
| `gdr login` | Authenticate via Chrome CDP |
| `gdr doctor` | Diagnose auth and connectivity |

### Global Options

- `--profile, -p` — Auth profile name (default: `default`)
- `--version, -v` — Show version

### Research Options

- `--timeout, -t` — Max research time in minutes (default: 30)
- `--poll` — Status polling interval in seconds (default: 10)
- `--no-confirm, -n` — Show plan and wait for manual confirmation
- `--output, -o` — Write report to file
- `--output-dir` — Auto-save to `DIR/{date}-{slug}.md`

## Auth Sharing with nlm

gdr-cli stores authentication in the same directory as notebooklm-mcp-cli:

```
~/.notebooklm-mcp-cli/
├── profiles/
│   └── default/
│       ├── cookies.json
│       └── metadata.json
└── gdr-config.json
```

Login once with either tool, both can use the same Google cookies.

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
cd /home/michael/Github/gdr-cli
git add README.md
git commit -m "docs: rewrite README for gdr-cli"
```

---

### Task 11: Final Integration Test

**Files:**

- None (testing only)

- [ ] **Step 1: Run full test suite**

Run: `cd /home/michael/Github/gdr-cli && uv run pytest -v`
Expected: All tests pass (exceptions + auth + config + research + cli)

- [ ] **Step 2: Verify CLI smoke tests**

Run: `cd /home/michael/Github/gdr-cli && uv run gdr --help`
Expected: Shows research, chat, login, doctor commands

Run: `cd /home/michael/Github/gdr-cli && uv run gdr research --help`
Expected: Shows all research options

- [ ] **Step 3: Verify import chain is clean**

Run: `cd /home/michael/Github/gdr-cli && uv run python -c "from gdr_cli.auth import AuthManager, Profile; from gdr_cli.exceptions import AuthError, RateLimitError; from gdr_cli.config import get_config; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 4: Final commit if any fixes needed**

```bash
cd /home/michael/Github/gdr-cli
git add -A
git commit -m "fix: final integration fixes"
```
