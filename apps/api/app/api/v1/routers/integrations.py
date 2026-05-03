"""
Integrations API router.
Handles Instagram OAuth and Connected Account flows.
"""

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import encrypt_token
from app.integrations.instagram.oauth import InstagramOAuth
from app.models.models import SocialAccount, SocialAccountStatus, WorkspaceMember
from app.schemas.schemas import SocialAccountResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _resolve_workspace(db: DbSession, user_id: uuid.UUID) -> uuid.UUID:
    """Return the user's first workspace ID."""
    stmt = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
    ws_id = (await db.execute(stmt)).scalars().first()
    if not ws_id:
        raise HTTPException(status_code=400, detail="User has no workspace")
    return ws_id


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/instagram/status")
async def get_instagram_status(
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    """Get current Instagram connection status for the user's workspace."""
    workspace_id = await _resolve_workspace(db, current_user.id)

    stmt = select(SocialAccount).where(
        SocialAccount.workspace_id == workspace_id,
        SocialAccount.platform == "instagram",
        SocialAccount.status == SocialAccountStatus.CONNECTED
    )
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    return {
        "connected": len(accounts) > 0,
        "accounts": [SocialAccountResponse.model_validate(a) for a in accounts],
    }


# ── Connect ───────────────────────────────────────────────────────────────────

@router.post("/instagram/connect")
async def connect_instagram(
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """
    Start the Instagram OAuth flow.
    Returns the authorization URL to redirect the user to.
    """
    workspace_id = await _resolve_workspace(db, current_user.id)

    # Check config
    if not settings.META_APP_ID or not settings.META_APP_SECRET:
        if settings.APP_ENV == "development":
            raise HTTPException(
                status_code=500,
                detail="META_APP_ID or META_APP_SECRET missing. Set them in .env or use mock mode."
            )
        raise HTTPException(status_code=500, detail="Instagram integration is not configured.")

    oauth = InstagramOAuth()
    auth_url = oauth.build_authorization_url(str(workspace_id), str(current_user.id))

    logger.info("instagram_oauth_started", workspace_id=str(workspace_id), user_id=str(current_user.id))
    return {"authorization_url": auth_url}


# ── Callback ──────────────────────────────────────────────────────────────────

@router.get("/instagram/callback")
async def instagram_callback(
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_reason: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """Handle Meta OAuth callback."""
    frontend_redirect = f"{settings.FRONTEND_URL}/dashboard/integrations"

    if error or not code or not state:
        logger.error(
            "instagram_oauth_failed",
            error=error,
            error_reason=error_reason,
            error_description=error_description
        )
        return RedirectResponse(f"{frontend_redirect}?error=instagram_oauth_failed")

    try:
        oauth = InstagramOAuth()
        account_data = await oauth.handle_callback(code, state)

        workspace_id = uuid.UUID(account_data["workspace_id"])
        user_id = uuid.UUID(account_data["user_id"])

        # Check if account already exists
        stmt = select(SocialAccount).where(
            SocialAccount.workspace_id == workspace_id,
            SocialAccount.ig_user_id == account_data["ig_user_id"]
        )
        existing_account = (await db.execute(stmt)).scalars().first()

        encrypted_token = encrypt_token(account_data["access_token"])

        # Calculate expiry
        import datetime
        expires_at = None
        if account_data.get("expires_in_seconds"):
            expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=account_data["expires_in_seconds"])

        if existing_account:
            existing_account.status = SocialAccountStatus.CONNECTED
            existing_account.username = account_data["username"]
            existing_account.account_type = account_data["account_type"]
            existing_account.page_id = account_data["page_id"]
            existing_account.page_name = account_data["page_name"]
            existing_account.access_token_encrypted = encrypted_token
            existing_account.token_expires_at = expires_at
            existing_account.scopes_json = account_data["scopes"]
            existing_account.disconnected_at = None
        else:
            new_account = SocialAccount(
                workspace_id=workspace_id,
                connected_by_user_id=user_id,
                platform="instagram",
                ig_user_id=account_data["ig_user_id"],
                username=account_data["username"],
                account_type=account_data["account_type"],
                page_id=account_data["page_id"],
                page_name=account_data["page_name"],
                status=SocialAccountStatus.CONNECTED,
                access_token_encrypted=encrypted_token,
                token_expires_at=expires_at,
                scopes_json=account_data["scopes"],
            )
            db.add(new_account)

        await db.commit()
        logger.info("instagram_oauth_completed", workspace_id=str(workspace_id), user_id=str(user_id))

        return RedirectResponse(f"{frontend_redirect}?connected=instagram")

    except Exception:
        logger.exception("instagram_oauth_callback_error")
        return RedirectResponse(f"{frontend_redirect}?error=instagram_oauth_failed")


# ── Mock Connect ──────────────────────────────────────────────────────────────

@router.post("/instagram/mock-connect")
async def mock_connect_instagram(
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Mock connection for local dev."""
    if settings.APP_ENV != "development" or os.environ.get("INSTAGRAM_INTEGRATION_MODE") != "mock":
        raise HTTPException(status_code=400, detail="Mock mode not enabled")

    workspace_id = await _resolve_workspace(db, current_user.id)

    stmt = select(SocialAccount).where(
        SocialAccount.workspace_id == workspace_id,
        SocialAccount.ig_user_id == "mock_ig_user_id"
    )
    existing_account = (await db.execute(stmt)).scalars().first()

    if existing_account:
        existing_account.status = SocialAccountStatus.CONNECTED
        existing_account.disconnected_at = None
    else:
        new_account = SocialAccount(
            workspace_id=workspace_id,
            connected_by_user_id=current_user.id,
            platform="instagram",
            ig_user_id="mock_ig_user_id",
            username="mock_ai_reel_studio",
            account_type="BUSINESS",
            page_id="mock_page_id",
            page_name="Mock Page",
            status=SocialAccountStatus.CONNECTED,
            access_token_encrypted=encrypt_token("mock_token_data"),
            token_expires_at=datetime.now(UTC),
            scopes_json=["mock_scope"],
            metadata_json={"is_mock": True}
        )
        db.add(new_account)

    await db.commit()
    return {"status": "ok"}


# ── Disconnect ────────────────────────────────────────────────────────────────

@router.delete("/instagram/accounts/{account_id}")
async def disconnect_instagram(
    account_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Soft-disconnect an Instagram account."""
    workspace_id = await _resolve_workspace(db, current_user.id)

    stmt = select(SocialAccount).where(
        SocialAccount.id == account_id,
        SocialAccount.workspace_id == workspace_id
    )
    account = (await db.execute(stmt)).scalars().first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.status = SocialAccountStatus.ERROR # Using ERROR or we can add DISCONNECTED
    # Actually prompt says: mark as disconnected or delete. We'll mark as error/disconnected_at
    account.disconnected_at = datetime.now(UTC)

    # Can also clear the token
    account.access_token_encrypted = encrypt_token("disconnected")

    await db.commit()
    logger.info("instagram_oauth_disconnected", account_id=str(account_id), workspace_id=str(workspace_id))
    return {"status": "disconnected"}


# ── Accounts List ─────────────────────────────────────────────────────────────

@router.get("/instagram/accounts", response_model=list[SocialAccountResponse])
async def list_instagram_accounts(
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """List connected Instagram accounts for current workspace."""
    workspace_id = await _resolve_workspace(db, current_user.id)

    stmt = select(SocialAccount).where(
        SocialAccount.workspace_id == workspace_id,
        SocialAccount.platform == "instagram"
    ).order_by(SocialAccount.created_at.desc())

    accounts = (await db.execute(stmt)).scalars().all()
    return [SocialAccountResponse.model_validate(a) for a in accounts]

# ── Reconnect ─────────────────────────────────────────────────────────────────

@router.post("/instagram/reconnect")
async def reconnect_instagram(
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Just alias to connect for now since Meta OAuth flow is same."""
    return await connect_instagram(current_user=current_user, db=db)
