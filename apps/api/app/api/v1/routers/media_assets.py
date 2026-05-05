"""
Media Assets API router.
Handles local file upload and serving for development.
In production, swap STORAGE_PROVIDER=s3 and use pre-signed S3 URLs.

Storage strategy:
  - STORAGE_PROVIDER=local : files saved under LOCAL_STORAGE_PATH/uploads/
  - STORAGE_PROVIDER=s3    : TODO — return a pre-signed PUT URL for direct browser upload

URL strategy:
  - All media URLs go through /api/v1/media-assets/{id}/view
  - Raw filesystem paths are NEVER exposed in responses.
"""

import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.models import (
    MediaAsset,
    MediaAssetStatus,
    MediaAssetType,
    WorkspaceMember,
)
from app.schemas.schemas import MediaAssetResponse
from app.services.render_service import build_media_url, get_local_storage_path

logger = structlog.get_logger(__name__)
router = APIRouter()

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
UPLOAD_DIR = Path(settings.LOCAL_STORAGE_PATH) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _resolve_workspace(db: DbSession, user_id: uuid.UUID) -> uuid.UUID:
    """Return the user's first workspace ID."""
    stmt = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
    ws_id = (await db.execute(stmt)).scalars().first()
    if not ws_id:
        raise HTTPException(status_code=400, detail="User has no workspace")
    return ws_id


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=MediaAssetResponse, status_code=201)
async def upload_media_asset(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> Any:
    """
    Upload a source image for reel generation.

    Validates:
    - Content-Type must be image/jpeg, image/png, or image/webp
    - File size must not exceed MAX_UPLOAD_BYTES (default 20 MB)

    Returns:
    - MediaAsset record with id — use this as `source_image_id` when creating a reel project.
    - `url` field contains a safe API URL (no raw filesystem paths).
    """
    # ── Validate MIME type ────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: jpeg, png, webp.",
        )

    # ── Validate file size ────────────────────────────────────────────────────
    file_bytes = await file.read()
    file_size = len(file_bytes)
    if file_size > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size} bytes). Max: {settings.MAX_UPLOAD_BYTES} bytes.",
        )
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    # ── Resolve workspace ─────────────────────────────────────────────────────
    workspace_id = await _resolve_workspace(db, current_user.id)

    # ── Write to local storage ────────────────────────────────────────────────
    ext = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    asset_id = uuid.uuid4()
    storage_filename = f"{asset_id}{ext}"
    file_path = UPLOAD_DIR / storage_filename

    try:
        file_path.write_bytes(file_bytes)
    except OSError as e:
        logger.error("file_write_failed", path=str(file_path), error=str(e))
        raise HTTPException(status_code=500, detail="File upload failed — storage error.") from e

    # ── Create MediaAsset record ──────────────────────────────────────────────
    # s3_key stores the relative path; s3_bucket="local" is sentinel for local storage.
    # NEVER store the raw filesystem path in public fields.
    asset = MediaAsset(
        id=asset_id,
        workspace_id=workspace_id,
        asset_type=MediaAssetType.SOURCE_IMAGE,
        s3_key=f"uploads/{storage_filename}",
        s3_bucket="local",
        filename=file.filename,
        mime_type=file.content_type,
        file_size=file_size,
        status=MediaAssetStatus.READY,
        metadata_={
            "storage_provider": "local",
            "original_filename": file.filename,
            "uploaded_by": str(current_user.id),
        },
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    logger.info(
        "media_asset_uploaded",
        asset_id=str(asset.id),
        filename=file.filename,
        size_bytes=file_size,
        workspace_id=str(workspace_id),
    )
    return _enrich_asset_response(asset)


# ── Get asset metadata ────────────────────────────────────────────────────────

@router.get("/{asset_id}", response_model=MediaAssetResponse)
async def get_media_asset(
    asset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Return safe metadata and dev-accessible URL for a media asset."""
    from app.services.render_service import get_media_asset_for_user
    asset = await get_media_asset_for_user(db, current_user.id, asset_id)
    return _enrich_asset_response(asset)


# ── View / stream asset ───────────────────────────────────────────────────────

@router.get("/{asset_id}/view")
async def view_media_asset(
    asset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """
    Stream the media asset file for inline preview.
    Only works in local storage mode. In production, redirect to CDN/S3 URL.

    Never exposes raw filesystem paths in the response.
    Auth required — user must be workspace member.
    """
    from app.services.render_service import get_media_asset_for_user
    asset = await get_media_asset_for_user(db, current_user.id, asset_id)

    local_path = get_local_storage_path(asset)
    if not local_path or not local_path.exists():
        raise HTTPException(status_code=404, detail="Asset file not found on storage")

    media_type = asset.mime_type or "application/octet-stream"
    filename = asset.filename or local_path.name

    return FileResponse(
        path=str(local_path),
        media_type=media_type,
        filename=filename,
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _enrich_asset_response(asset: MediaAsset) -> dict:
    """Build a safe response dict with url field (no raw FS paths)."""
    return {
        "id": str(asset.id),
        "workspace_id": str(asset.workspace_id),
        "asset_type": asset.asset_type.value,
        "s3_key": asset.s3_key,
        "filename": asset.filename,
        "mime_type": asset.mime_type,
        "file_size": asset.file_size,
        "status": asset.status.value,
        "url": build_media_url(asset),
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }
