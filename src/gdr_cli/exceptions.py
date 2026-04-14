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