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
