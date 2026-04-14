"""Tests for exceptions.py — custom exception hierarchy."""

import pytest
from exceptions import (
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