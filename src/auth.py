"""Authentication: Profile dataclass, AuthManager, cookie loading."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from exceptions import AuthError, AccountMismatchError, ProfileNotFoundError


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


class AuthManager:
    """Manages authentication profiles (cookies + metadata) on disk.

    Shares storage format with nlm CLI at ~/.notebooklm-mcp-cli/profiles/.
    """

    def __init__(self, profile_name: str = "default"):
        self.profile_name = profile_name
        self._profile: Profile | None = None

    @property
    def profile_dir(self) -> Path:
        from config import get_profile_dir
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
        from config import get_profiles_dir
        profile_path = get_profiles_dir() / self.profile_name
        if profile_path.exists():
            shutil.rmtree(profile_path)
        self._profile = None

    def get_cookies(self) -> dict[str, str]:
        return self.load_profile().get_cookies()

    @staticmethod
    def list_profiles() -> list[str]:
        from config import get_profiles_dir
        profiles_dir = get_profiles_dir()
        if not profiles_dir.exists():
            return []
        return [d.name for d in profiles_dir.iterdir() if d.is_dir()]


# Backward-compatible convenience function
def get_profile_cookies(profile_name: str = "default") -> dict[str, str]:
    """Load cookies for a profile (backward compat for research.py/chat.py)."""
    return AuthManager(profile_name).get_cookies()
