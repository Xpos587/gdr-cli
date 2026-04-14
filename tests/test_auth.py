"""Tests for auth.py — Profile dataclass and AuthManager."""

import json
from datetime import datetime
from pathlib import Path
import pytest
from auth import Profile, AuthManager
from exceptions import AuthError, ProfileNotFoundError, AccountMismatchError


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


class TestAuthManager:
    def _make_manager(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.get_profile_dir",
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
        monkeypatch.setattr("config.get_profile_dir",
                            lambda name: tmp_path / "profiles" / name)
        monkeypatch.setattr("config.get_profiles_dir",
                            lambda: tmp_path / "profiles")
        mgr = AuthManager("default")
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        assert mgr.profile_exists() is True
        mgr.delete_profile()
        assert mgr.profile_exists() is False

    def test_list_profiles(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.get_profiles_dir",
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
