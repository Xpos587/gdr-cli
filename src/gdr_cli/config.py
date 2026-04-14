"""Path resolution and config loading. Shares ~/.notebooklm-mcp-cli/ with nlm CLI."""

from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel


_BASE_DIR = Path.home() / ".notebooklm-mcp-cli"


class GdrConfig(BaseModel):
    """CLI configuration (loaded from config.toml, merged with defaults)."""

    default_profile: str = "default"
    timeout_min: int = 30
    poll_interval: float = 10.0
    auto_confirm: bool = True


def get_base_dir() -> Path:
    """Return the shared nlm/gdr base directory."""
    return _BASE_DIR


def get_profiles_dir() -> Path:
    """Return the profiles directory."""
    return _BASE_DIR / "profiles"


def get_profile_dir(profile_name: str) -> Path:
    """Return the directory for a specific auth profile."""
    return get_profiles_dir() / profile_name


def get_cookies_file(profile_name: str = "default") -> Path:
    """Return the cookies.json path for a profile."""
    return get_profile_dir(profile_name) / "cookies.json"


def get_metadata_file(profile_name: str = "default") -> Path:
    """Return the metadata.json path for a profile."""
    return get_profile_dir(profile_name) / "metadata.json"


def get_config() -> GdrConfig:
    """Load config from config.toml, falling back to defaults."""
    import tomllib

    config_path = _BASE_DIR / "config.toml"
    if not config_path.exists():
        return GdrConfig()

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        return GdrConfig(
            default_profile=data.get("auth", {}).get("default_profile", "default"),
        )
    except (tomllib.TOMLDecodeError, KeyError, TypeError):
        return GdrConfig()