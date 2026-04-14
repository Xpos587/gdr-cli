"""Tests for config.py — path resolution and persistent config."""

from pathlib import Path
import json
import pytest
from config import (
    get_base_dir, get_profiles_dir, get_profile_dir,
    get_cookies_file, get_metadata_file, get_config,
)


class TestPaths:
    def test_get_base_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config._BASE_DIR", tmp_path / "nlm")
        assert get_base_dir() == tmp_path / "nlm"

    def test_get_profiles_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config._BASE_DIR", tmp_path / "nlm")
        assert get_profiles_dir() == tmp_path / "nlm" / "profiles"

    def test_get_profile_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config._BASE_DIR", tmp_path / "nlm")
        assert get_profile_dir("work") == tmp_path / "nlm" / "profiles" / "work"

    def test_get_cookies_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config._BASE_DIR", tmp_path / "nlm")
        assert get_cookies_file("default") == tmp_path / "nlm" / "profiles" / "default" / "cookies.json"

    def test_get_metadata_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config._BASE_DIR", tmp_path / "nlm")
        assert get_metadata_file("default") == tmp_path / "nlm" / "profiles" / "default" / "metadata.json"


class TestGDRConfig:
    def test_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config._BASE_DIR", tmp_path / "nlm")
        cfg = get_config()
        assert cfg.default_profile == "default"
        assert cfg.default_timeout == 30
        assert cfg.default_poll_interval == 10.0
        assert cfg.auto_confirm is True
        assert cfg.output_dir is None

    def test_loads_from_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config._BASE_DIR", tmp_path / "nlm")
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
        monkeypatch.setattr("config._BASE_DIR", tmp_path / "nlm")
        config_file = tmp_path / "nlm" / "gdr-config.json"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("not json")
        cfg = get_config()
        assert cfg.default_profile == "default"
