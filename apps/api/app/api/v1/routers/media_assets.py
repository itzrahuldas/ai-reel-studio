"""
Media Assets API router.
Handles local file upload for development.
In production, swap STORAGE_PROVIDER=s3 and use pre-signed S3 URLs.

Storage strategy:
  - STORAGE_PROVIDER=local : files saved under LOCAL_STORAGE_PATH/uploads/
  - STORAGE_PROVIDER=s3    : TODO — return a pre-signed PUT URL for direct browser upload
"""

import os
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile
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

logger = structlog.get_logger(__name__)
router = APIRouter()

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
UPLOAD_DIR = os.path.join(settings.LOCAL_STORAGE_PATH, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _resolve_workspace(db: DbSession, user_id: uuid.UUID) -> uuid.UUID:
    """Return the user's first workspace ID."""
    stmt = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
    ws_id = (await db.execute(stmt)).scalars().first()
    if not ws_id:
        raise HTTPException(status_code=400, detail="User has no workspace")
    return ws_id


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

    NOTE: In production with STORAGE_PROVIDER=s3, this endpoint should return a
    pre-signed PUT URL so the browser uploads directly to S3, avoiding memory
    overhead on the API. The local storage adapter here is for development only.
    """
    # ── Validate MIME type ────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Allowed: jpeg, png, webp.",
        )

    # ── Validate file size ────────────────────────────────────────────────────
    # Read entire file into memory to check size (acceptable for ≤20 MB images)
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
    ext = os.path.splitext(file.filename or "image")[1].lower() or ".jpg"
    asset_id = uuid.uuid4()
    storage_filename = f"{asset_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, storage_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
    except OSError as e:
        logger.error("file_write_failed", path=file_path, error=str(e))
        raise HTTPException(status_code=500, detail="File upload failed — storage error.")

    # ── Create MediaAsset record ──────────────────────────────────────────────
    # s3_key stores the relative path; s3_bucket stores the provider name
    asset = MediaAsset(
        id=asset_id,
        workspace_id=workspace_id,
        asset_type=MediaAssetType.SOURCE_IMAGE,
        s3_key=f"uploads/{storage_filename}",
        s3_bucket="local",  # Sentinel value for local storage
        filename=file.filename,
        mime_type=file.content_type,
        file_size=file_size,
        status=MediaAssetStatus.READY,
        metadata_={
            "storage_provider": "local",
            "storage_path": file_path,
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
    return asset
