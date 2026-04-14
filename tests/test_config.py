"""Tests for config.py — path resolution and config loading."""

from pathlib import Path
from gdr_cli.config import get_base_dir, get_profile_dir, get_config


class TestPaths:
    def test_get_base_dir_returns_nlm_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "notebooklm-mcp-cli")
        result = get_base_dir()
        assert result == tmp_path / "notebooklm-mcp-cli"

    def test_get_profile_dir_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "notebooklm-mcp-cli")
        result = get_profile_dir("default")
        assert result == tmp_path / "notebooklm-mcp-cli" / "profiles" / "default"

    def test_get_profile_dir_custom(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "notebooklm-mcp-cli")
        result = get_profile_dir("work")
        assert result == tmp_path / "notebooklm-mcp-cli" / "profiles" / "work"

    def test_get_config_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("gdr_cli.config._BASE_DIR", tmp_path / "notebooklm-mcp-cli")
        cfg = get_config()
        assert cfg.default_profile == "default"
        assert cfg.timeout_min == 30