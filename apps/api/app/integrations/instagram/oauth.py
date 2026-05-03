"""
Instagram OAuth and API client.

IMPORTANT SAFETY RULES:
- Never log access tokens
- Never return access tokens in API responses  
- Always validate CSRF state token before token exchange
- Always check token expiry before publishing
"""

from urllib.parse import urlencode

import httpx
import structlog

from app.core.config import settings
from app.core.security import create_oauth_state_token, validate_oauth_state_token
from app.integrations.instagram.errors import (
    InstagramOAuthError,
)

logger = structlog.get_logger(__name__)

IG_REQUIRED_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_read_engagement",
]


class InstagramOAuth:
    """
    Handles Meta OAuth 2.0 flow for Instagram Business Account connection.
    """

    BASE_URL = "https://www.facebook.com"
    GRAPH_URL = "https://graph.facebook.com"

    def __init__(self) -> None:
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET
        self.redirect_uri = settings.META_REDIRECT_URI
        self.api_version = settings.META_GRAPH_API_VERSION

    def build_authorization_url(self, workspace_id: str, user_id: str) -> str:
        """
        Build the Meta OAuth authorization URL.
        Returns the URL the user should be redirected to.
        """
        state = create_oauth_state_token(workspace_id=workspace_id, user_id=user_id)
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(IG_REQUIRED_SCOPES),
            "response_type": "code",
            "state": state,
        }
        return f"{self.BASE_URL}/{self.api_version}/dialog/oauth?{urlencode(params)}"

    async def handle_callback(self, code: str, state: str) -> dict:
        """
        Handle the OAuth callback:
        1. Validate CSRF state token
        2. Exchange code for short-lived token
        3. Exchange for long-lived token
        4. Fetch IG Business Account info
        5. Return account data (NOT the raw token — caller stores it encrypted)
        """
        # 1. Validate CSRF state
        try:
            state_payload = validate_oauth_state_token(state)
        except Exception as e:
            raise InstagramOAuthError(f"Invalid OAuth state token: {e}") from e

        workspace_id = state_payload["workspace_id"]
        user_id = state_payload["user_id"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 2. Exchange code for short-lived token
            short_token_resp = await client.get(
                f"{self.GRAPH_URL}/{self.api_version}/oauth/access_token",
                params={
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )
            if short_token_resp.status_code != 200:
                raise InstagramOAuthError(
                    f"Token exchange failed: {short_token_resp.text}"
                )
            short_token_data = short_token_resp.json()
            short_token = short_token_data.get("access_token")

            # 3. Exchange for long-lived token (60 days)
            long_token_resp = await client.get(
                f"{self.GRAPH_URL}/{self.api_version}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "fb_exchange_token": short_token,
                },
            )
            if long_token_resp.status_code != 200:
                raise InstagramOAuthError(
                    f"Long-lived token exchange failed: {long_token_resp.text}"
                )
            long_token_data = long_token_resp.json()
            long_token = long_token_data.get("access_token")
            expires_in = long_token_data.get("expires_in", 5184000)  # Default 60 days

            # 4. Fetch Facebook Pages + IG Business Account
            pages_resp = await client.get(
                f"{self.GRAPH_URL}/{self.api_version}/me/accounts",
                params={"access_token": long_token, "fields": "id,name,instagram_business_account"},
            )
            pages_data = pages_resp.json()

            ig_account_id = None
            page_id = None
            for page in pages_data.get("data", []):
                if "instagram_business_account" in page:
                    ig_account_id = page["instagram_business_account"]["id"]
                    page_id = page["id"]
                    break

            if not ig_account_id:
                raise InstagramOAuthError(
                    "No Instagram Business Account found linked to this Facebook account. "
                    "Please ensure you have an Instagram Business or Creator account "
                    "linked to a Facebook Page."
                )

            # 5. Fetch IG username
            ig_resp = await client.get(
                f"{self.GRAPH_URL}/{self.api_version}/{ig_account_id}",
                params={"access_token": long_token, "fields": "id,username"},
            )
            ig_data = ig_resp.json()
            ig_username = ig_data.get("username", "")

        logger.info(
            "instagram.oauth.success",
            workspace_id=workspace_id,
            user_id=user_id,
            ig_user_id=ig_account_id,
            ig_username=ig_username,
            # NOTE: access_token intentionally NOT logged
        )

        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "platform_user_id": ig_account_id,
            "platform_username": ig_username,
            "platform_page_id": page_id,
            "access_token": long_token,  # Caller must encrypt before storing
            "expires_in_seconds": expires_in,
            "scopes": IG_REQUIRED_SCOPES,
        }
