"""Instagram integration error types."""


class InstagramError(Exception):
    """Base class for all Instagram integration errors."""


class InstagramOAuthError(InstagramError):
    """OAuth flow error — invalid code, state, or configuration."""


class InstagramTokenExpiredError(InstagramError):
    """Access token is expired or revoked (error code 190)."""


class InstagramAPIError(InstagramError):
    """Generic Meta Graph API error."""


class InstagramContainerError(InstagramError):
    """Media container creation or processing error."""


class InstagramPublishError(InstagramError):
    """Media publish step failed."""


class InstagramRateLimitError(InstagramError):
    """Rate limit exceeded."""


class InstagramAccountNotConnectedError(InstagramError):
    """Social account not in CONNECTED status."""
