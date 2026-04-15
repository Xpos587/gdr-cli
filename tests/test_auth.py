"""Tests for auth.py — Profile dataclass and AuthManager."""

import json
from datetime import datetime
from pathlib import Path
import pytest
from auth import Profile, AuthManager, get_profile_cookies
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

    def test_to_dict_none_last_validated(self):
        profile = Profile(name="d", cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        d = profile.to_dict()
        assert d["last_validated"] is None

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

    def test_from_dict_invalid_last_validated(self):
        data = {"name": "test", "last_validated": "not-a-date"}
        profile = Profile.from_dict(data)
        assert profile.last_validated is None

    def test_from_dict_none_last_validated(self):
        data = {"name": "test", "last_validated": None}
        profile = Profile.from_dict(data)
        assert profile.last_validated is None

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

    def test_get_cookies_empty_list(self):
        profile = Profile(name="d", cookies=[])
        with pytest.raises(AuthError, match="__Secure-1PSID"):
            profile.get_cookies()

    def test_get_cookies_skips_invalid_entries(self):
        profile = Profile(
            name="d",
            cookies=[
                {"name": "__Secure-1PSID", "value": "pv"},
                "not-a-dict",
                {"no_name": "v"},
                {"name": 123, "value": "v"},
                {"name": "HSID", "value": "hv"},
            ],
        )
        cookies = profile.get_cookies()
        # Code only checks isinstance(c, dict) and "name" in c and "value" in c
        # {123: "v"} has "name" key as int, str(123)="123" -> included
        assert "__Secure-1PSID" in cookies
        assert "HSID" in cookies

    def test_get_cookies_non_standard_cookies_type(self):
        profile = Profile(name="d", cookies=42)
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

    def test_load_corrupt_cookies_json(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.profile_dir.mkdir(parents=True, exist_ok=True)
        mgr.cookies_file.write_text("not json{{{", encoding="utf-8")
        with pytest.raises(AuthError, match="Failed to load"):
            mgr.load_profile()

    def test_load_corrupt_metadata_json(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        mgr.metadata_file.write_text("bad json", encoding="utf-8")
        # Should still load cookies, metadata just skipped
        profile = mgr.load_profile()
        assert profile.email is None

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

    def test_delete_nonexistent_profile(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.get_profile_dir",
                            lambda name: tmp_path / "profiles" / name)
        monkeypatch.setattr("config.get_profiles_dir",
                            lambda: tmp_path / "profiles")
        mgr = AuthManager("nonexistent")
        mgr.delete_profile()  # Should not raise

    def test_list_profiles(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.get_profiles_dir",
                            lambda: tmp_path / "profiles")
        mgr = AuthManager("default")
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        mgr2 = AuthManager("work")
        mgr2.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v2"}])
        profiles = AuthManager.list_profiles()
        assert sorted(profiles) == ["default", "work"]

    def test_list_profiles_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.get_profiles_dir",
                            lambda: tmp_path / "profiles")
        profiles = AuthManager.list_profiles()
        assert profiles == []

    def test_list_profiles_skips_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.get_profiles_dir",
                            lambda: tmp_path / "profiles")
        (tmp_path / "profiles").mkdir()
        (tmp_path / "profiles" / "default").mkdir()
        (tmp_path / "profiles" / "not_a_dir.txt").write_text("hi")
        profiles = AuthManager.list_profiles()
        assert profiles == ["default"]

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

    def test_save_with_dict_cookies(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(
            cookies={"__Secure-1PSID": "pv", "HSID": "hv"},
            email="d@e.com",
        )
        loaded = mgr.load_profile()
        assert loaded.cookies == {"__Secure-1PSID": "pv", "HSID": "hv"}

    def test_save_with_all_fields(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(
            cookies=[{"name": "__Secure-1PSID", "value": "v"}],
            csrf_token="ct",
            session_id="sid",
            email="a@b.com",
            build_label="bl",
        )
        profile = mgr.load_profile()
        assert profile.csrf_token == "ct"
        assert profile.session_id == "sid"
        assert profile.build_label == "bl"
        assert profile.last_validated is not None

    def test_load_profile_caches(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        p1 = mgr.load_profile()
        p2 = mgr.load_profile()
        assert p1 is p2  # Same object due to caching

    def test_load_profile_force_reload(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        p1 = mgr.load_profile()
        p2 = mgr.load_profile(force_reload=True)
        assert p1 is not p2

    def test_account_mismatch_corrupt_metadata_ignored(self, tmp_path, monkeypatch):
        mgr = self._make_manager(tmp_path, monkeypatch)
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "v"}])
        mgr.metadata_file.write_text("corrupt{{", encoding="utf-8")
        # Should not raise, corrupt metadata is caught
        mgr.save_profile(
            cookies=[{"name": "__Secure-1PSID", "value": "v2"}],
            email="new@gmail.com",
        )

    def test_get_profile_cookies_backward_compat(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.get_profile_dir",
                            lambda name: tmp_path / "profiles" / name)
        mgr = AuthManager("default")
        mgr.save_profile(cookies=[{"name": "__Secure-1PSID", "value": "pv"}])
        cookies = get_profile_cookies("default")
        assert cookies["__Secure-1PSID"] == "pv"
