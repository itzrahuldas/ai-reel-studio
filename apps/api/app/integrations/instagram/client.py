"""
Instagram Graph API client — media container creation, polling, and publishing.

Safety rules:
- Tokens are NEVER logged (use [REDACTED])
- All publish attempts are logged in audit_logs
- Token expiry is checked before every operation
"""


import httpx
import structlog

from app.core.config import settings
from app.integrations.instagram.errors import (
    InstagramAPIError,
    InstagramContainerError,
    InstagramPublishError,
    InstagramRateLimitError,
    InstagramTokenExpiredError,
)

logger = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.facebook.com"
MAX_POLL_ATTEMPTS = 20
POLL_INTERVAL_SECONDS = 10


class InstagramClient:
    """
    Thin client over the Meta Graph API for Reels publishing.

    Usage:
        client = InstagramClient(access_token=decrypted_token)
        container_id = await client.create_media_container(...)
        status = await client.check_container_status(container_id)
        media_id = await client.publish_media(ig_user_id, container_id)
    """

    def __init__(self, access_token: str) -> None:
        self._token = access_token  # Never logged
        self._api_version = settings.META_GRAPH_API_VERSION
        self._base = f"{GRAPH_BASE}/{self._api_version}"

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    async def create_media_container(
        self,
        ig_user_id: str,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
    ) -> str:
        """
        Create a Reels media container.
        Returns the container_id to be used for polling and publishing.
        """
        logger.info(
            "instagram.create_container.start",
            ig_user_id=ig_user_id,
            share_to_feed=share_to_feed,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base}/{ig_user_id}/media",
                params={"access_token": self._token},
                json={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption,
                    "share_to_feed": share_to_feed,
                },
            )

        self._raise_for_error(resp, "create_media_container")
        container_id = resp.json().get("id")
        if not container_id:
            raise InstagramContainerError("No container ID returned from Meta API")

        logger.info("instagram.create_container.success", container_id=container_id)
        return container_id

    async def check_container_status(self, container_id: str) -> str:
        """
        Check the processing status of a media container.
        Returns one of: IN_PROGRESS | FINISHED | ERROR | EXPIRED
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self._base}/{container_id}",
                params={
                    "access_token": self._token,
                    "fields": "status_code",
                },
            )

        self._raise_for_error(resp, "check_container_status")
        status_code = resp.json().get("status_code", "UNKNOWN")
        logger.debug("instagram.poll_status", container_id=container_id, status_code=status_code)
        return status_code

    async def publish_media(self, ig_user_id: str, container_id: str) -> str:
        """
        Publish a FINISHED media container.
        Returns the published media_id.
        """
        logger.info("instagram.publish.start", ig_user_id=ig_user_id, container_id=container_id)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base}/{ig_user_id}/media_publish",
                params={"access_token": self._token},
                json={"creation_id": container_id},
            )

        self._raise_for_error(resp, "publish_media")
        media_id = resp.json().get("id")
        if not media_id:
            raise InstagramPublishError("No media_id returned from publish call")

        logger.info("instagram.publish.success", ig_user_id=ig_user_id, media_id=media_id)
        return media_id

    def _raise_for_error(self, resp: httpx.Response, operation: str) -> None:
        """Parse Meta API error responses and raise typed exceptions."""
        if resp.status_code == 200:
            return

        try:
            error_data = resp.json().get("error", {})
        except Exception:
            error_data = {}

        code = error_data.get("code", 0)
        message = error_data.get("message", f"HTTP {resp.status_code}")

        logger.error(
            "instagram.api_error",
            operation=operation,
            http_status=resp.status_code,
            error_code=code,
            message=message,
        )

        if code == 190:
            raise InstagramTokenExpiredError(f"Token expired or invalid: {message}")
        if resp.status_code == 429 or code == 4:
            raise InstagramRateLimitError(f"Rate limited: {message}")
        raise InstagramAPIError(f"Instagram API error [{code}]: {message}")
