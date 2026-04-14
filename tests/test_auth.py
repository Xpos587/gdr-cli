"""Tests for auth.py — cookie loading from nlm profiles."""

import json
from pathlib import Path
import pytest
from gdr_cli.auth import load_cookies, AuthError


class TestLoadCookies:
    def test_extracts_psid_and_psidts_from_list_format(self, tmp_path):
        cookies_file = tmp_path / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "SID", "value": "sid-val", "domain": ".google.com", "path": "/"},
            {"name": "__Secure-1PSID", "value": "my-psid-value", "domain": ".google.com", "path": "/"},
            {"name": "__Secure-1PSIDTS", "value": "my-psidts-value", "domain": ".google.com", "path": "/"},
        ]))
        result = load_cookies(cookies_file)
        assert result["__Secure-1PSID"] == "my-psid-value"
        assert result["__Secure-1PSIDTS"] == "my-psidts-value"

    def test_extracts_from_dict_format(self, tmp_path):
        cookies_file = tmp_path / "cookies.json"
        cookies_file.write_text(json.dumps({
            "__Secure-1PSID": "dict-psid",
            "__Secure-1PSIDTS": "dict-psidts",
        }))
        result = load_cookies(cookies_file)
        assert result["__Secure-1PSID"] == "dict-psid"
        assert result["__Secure-1PSIDTS"] == "dict-psidts"

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(AuthError, match="not found"):
            load_cookies(tmp_path / "nonexistent.json")

    def test_raises_on_missing_psid(self, tmp_path):
        cookies_file = tmp_path / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "SID", "value": "sid-val", "domain": ".google.com", "path": "/"},
        ]))
        with pytest.raises(AuthError, match="__Secure-1PSID"):
            load_cookies(cookies_file)

    def test_returns_all_cookies_not_just_two(self, tmp_path):
        cookies_file = tmp_path / "cookies.json"
        cookies_file.write_text(json.dumps([
            {"name": "__Secure-1PSID", "value": "psid", "domain": ".google.com", "path": "/"},
            {"name": "__Secure-1PSIDTS", "value": "psidts", "domain": ".google.com", "path": "/"},
            {"name": "HSID", "value": "hsid", "domain": ".google.com", "path": "/"},
        ]))
        result = load_cookies(cookies_file)
        assert len(result) == 3
        assert result["HSID"] == "hsid"