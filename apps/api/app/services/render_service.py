"""
Render service — orchestrates the full video render pipeline.
Creates RenderJob, calls FFmpegRenderer, creates MediaAsset records,
and updates ReelProject/ReelVersion status.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    AuditLog,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaAssetType,
    ReelProject,
    ReelProjectStatus,
    ReelVersion,
    RenderJob,
    UsageEventType,
    WorkspaceMember,
)
from app.services.ai.base import SubtitleLine
from app.services.rendering.ffmpeg_renderer import FFmpegRenderer, RenderParams
from app.services.rendering.mock_visuals import generate_mock_storyboard
from app.services.rendering.subtitles import write_srt_file
from app.services.usage_service import consume_usage

logger = structlog.get_logger(__name__)

ERROR_MESSAGE_MAX_CHARS = 1000


def _safe_error_message(exc: Exception, max_length: int = ERROR_MESSAGE_MAX_CHARS) -> str:
    """Return a bounded single-line error message for render logs and job state."""
    message = str(exc) or type(exc).__name__
    message = message.replace("\r", " ").replace("\n", " ")
    if len(message) > max_length:
        return f"{message[:max_length]}..."
    return message


# ── URL Helper ────────────────────────────────────────────────────────────────

def _safe_storage_key(s3_key: str) -> str:
    """Return a URL-safe storage key without exposing accidental filesystem paths."""
    normalized_key = s3_key.replace("\\", "/")
    if normalized_key.startswith(("//", "/var/", "/tmp/", "/home/", "/Users/", "/mnt/", "/opt/")):
        normalized_key = normalized_key.rsplit("/", 1)[-1]
    key = normalized_key.lstrip("/")
    first_segment = key.split("/", 1)[0]
    if ":" in first_segment:
        key = key.rsplit("/", 1)[-1]
    return "/".join(quote(segment) for segment in key.split("/") if segment)


def _media_base_url(base_url: str | None = None) -> str:
    if base_url:
        clean_base = base_url.rstrip("/")
        return clean_base if clean_base.endswith("/static") else f"{clean_base}/static"

    if settings.STORAGE_PUBLIC_BASE_URL:
        return settings.STORAGE_PUBLIC_BASE_URL.rstrip("/")

    if settings.API_PUBLIC_BASE_URL:
        return f"{settings.API_PUBLIC_BASE_URL.rstrip('/')}/static"

    return "/static"


def build_media_url(asset: MediaAsset, base_url: str | None = None) -> str:
    """
    Build a safe public URL for a MediaAsset.

    For local storage: {STORAGE_PUBLIC_BASE_URL}/{s3_key}
    For S3/prod: the s3_key would be used with a CDN or pre-signed URL.

    NEVER exposes raw filesystem paths.
    """
    safe_key = _safe_storage_key(asset.s3_key)
    return f"{_media_base_url(base_url)}/{safe_key}"


def build_media_asset_response(asset: MediaAsset) -> dict:
    """Build a safe media asset response dict with absolute media URLs."""
    safe_key = _safe_storage_key(asset.s3_key)
    url = build_media_url(asset)
    metadata = asset.metadata_ if isinstance(asset.metadata_, dict) else {}
    # Expose safe render metadata fields only — never expose local filesystem paths
    _SAFE_METADATA_KEYS = {
        "visual_source", "mock_visual_theme", "mock_visual_scene_count",
        "generated_scene_count", "scene_count", "multi_scene",
        "has_audio", "has_subtitles", "renderer",
        "duration_seconds", "width", "height", "fps",
        "render_time_seconds", "provider",
    }
    safe_metadata = {k: v for k, v in metadata.items() if k in _SAFE_METADATA_KEYS}
    return {
        "id": str(asset.id),
        "workspace_id": str(asset.workspace_id),
        "asset_type": asset.asset_type.value,
        "s3_key": safe_key,
        "filename": safe_key.rsplit("/", 1)[-1],
        "mime_type": asset.mime_type,
        "file_size": asset.file_size,
        "status": asset.status.value,
        "url": url,
        "public_url": url,
        "media_url": url,
        "provider": metadata.get("provider"),
        "renderer": metadata.get("renderer"),
        "metadata": safe_metadata,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


def get_local_storage_path(asset: MediaAsset) -> Path | None:
    """Resolve the local filesystem path from s3_key (dev only)."""
    if asset.s3_bucket != "local":
        return None
    # s3_key format: "uploads/{filename}" or "renders/{filename}"
    return Path(settings.LOCAL_STORAGE_PATH) / asset.s3_key


# ── Render Service ────────────────────────────────────────────────────────────

async def create_render_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID | None = None,
) -> tuple[RenderJob, ReelProject, ReelVersion]:
    """
    Create a RenderJob for the project's generated version,
    then run sync or async pipeline per GENERATION_MODE setting.
    """
    # ── Auth & ownership ──────────────────────────────────────────────────────
    stmt = (
        select(ReelProject)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(
            WorkspaceMember.user_id == user_id,
            ReelProject.id == project_id,
        )
    )
    project = (await db.execute(stmt)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # ── Validate state ────────────────────────────────────────────────────────
    target_version_id = version_id or project.latest_version_id
    if not target_version_id:
        raise HTTPException(status_code=400, detail="No generated version to render")

    version = await db.get(ReelVersion, target_version_id)
    if not version or version.project_id != project.id:
        raise HTTPException(status_code=400, detail="Version record not found")

    if not version.script:
        raise HTTPException(
            status_code=400,
            detail="Version has no generated content. Run AI generation first.",
        )

    # ── Consume Usage ────────────────────────────────────────────────────────
    # ── Create RenderJob ──────────────────────────────────────────────────────
    render_job = RenderJob(
        project_id=project.id,
        version_id=version.id,
        status=JobStatus.QUEUED,
        renderer="ffmpeg",
        input_payload={
            "project_id": str(project.id),
            "version_id": str(version.id),
            "duration_seconds": project.duration_seconds,
            "has_source_image": project.source_image_id is not None,
            "has_voiceover": bool(version.voiceover_asset_id or version.audio_asset_id),
        },
    )
    db.add(render_job)
    await db.flush()

    await consume_usage(
        db=db,
        workspace_id=project.workspace_id,
        user_id=user_id,
        event_type=UsageEventType.RENDER,
        quantity=1,
        related_project_id=project.id,
        related_version_id=version.id,
        related_job_id=str(render_job.id),
    )

    audit = AuditLog(
        action="render_job_created",
        workspace_id=project.workspace_id,
        user_id=user_id,
        resource_type="render_job",
        resource_id=render_job.id,
        metadata_={"project_id": str(project.id), "version_id": str(version.id)},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(render_job)
    await db.refresh(project)
    await db.refresh(version)

    # ── Dispatch ──────────────────────────────────────────────────────────────
    mode = settings.GENERATION_MODE
    if mode == "sync":
        await _run_render_pipeline_inline(
            project_id=project.id,
            version_id=version.id,
            render_job_id=render_job.id,
        )
        await db.refresh(render_job)
        await db.refresh(project)
        await db.refresh(version)
    else:
        try:
            from app.workers.celery_client import celery_client
            celery_client.send_task(
                "app.tasks.render_reel.render_reel_task",
                args=[str(project.id), str(version.id), str(render_job.id)],
                queue="rendering",
            )
            logger.info(
                "render_job_enqueued",
                project_id=str(project.id),
                render_job_id=str(render_job.id),
            )
        except Exception as e:
            logger.warning("celery_render_enqueue_failed", error=str(e))

    return render_job, project, version


async def get_render_jobs(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[RenderJob]:
    """Return all render jobs for a project (with auth check)."""
    # Auth check via workspace membership
    stmt = (
        select(ReelProject)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(WorkspaceMember.user_id == user_id, ReelProject.id == project_id)
    )
    project = (await db.execute(stmt)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = (
        select(RenderJob)
        .where(RenderJob.project_id == project_id)
        .order_by(RenderJob.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_media_asset_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> MediaAsset:
    """Fetch a MediaAsset ensuring user has workspace access."""
    stmt = (
        select(MediaAsset)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == MediaAsset.workspace_id)
        .where(
            WorkspaceMember.user_id == user_id,
            MediaAsset.id == asset_id,
        )
    )
    asset = (await db.execute(stmt)).scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return asset


# ── Inline Render Pipeline (sync mode) ───────────────────────────────────────

async def _run_render_pipeline_inline(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    render_job_id: uuid.UUID,
) -> bool:
    """Run the render pipeline inline (GENERATION_MODE=sync)."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            render_job = await db.get(RenderJob, render_job_id)
            project = await db.get(ReelProject, project_id)
            version = await db.get(ReelVersion, version_id)

            if not all([render_job, project, version]):
                logger.error(
                    "render_pipeline_missing_records",
                    project_id=str(project_id),
                    version_id=str(version_id),
                    render_job_id=str(render_job_id),
                )
                return False

            # ── Mark RUNNING ──────────────────────────────────────────────────
            render_job.status = JobStatus.RUNNING
            render_job.started_at = datetime.now(UTC)
            project.status = ReelProjectStatus.RENDERING
            version.status = ReelProjectStatus.RENDERING
            await db.commit()

            # ── Resolve source image path ─────────────────────────────────────
            image_path = _get_source_image_path(project, version, settings.LOCAL_STORAGE_PATH)
            audio_path = await _resolve_voiceover_audio_path(db, version)

            # ── Prepare output directories ────────────────────────────────────
            renders_dir = Path(settings.LOCAL_STORAGE_PATH) / "renders"
            renders_dir.mkdir(parents=True, exist_ok=True)

            output_filename = f"reel_{project_id}_{version_id}.mp4"
            thumbnail_filename = f"thumb_{project_id}_{version_id}.jpg"
            output_path = renders_dir / output_filename
            thumbnail_path = renders_dir / thumbnail_filename

            # ── Write SRT file ────────────────────────────────────────────────
            srt_path = None
            if version.subtitle_lines:
                try:
                    subtitle_objects = [
                        SubtitleLine(**sl) if isinstance(sl, dict) else sl
                        for sl in version.subtitle_lines
                    ]
                    srt_path = renders_dir / f"subs_{version_id}.srt"
                    write_srt_file(subtitle_objects, srt_path)
                except Exception as e:
                    logger.warning("subtitle_write_failed", error=str(e))
                    srt_path = None

            # ── Generate mock visual scene images (when no real source image) ─────
            scene_image_paths: list[Path] | None = None
            visual_source = "source_image" if project.source_image_id else "mock_storyboard"
            mock_theme_name: str | None = None
            mock_scene_count: int | None = None

            if not project.source_image_id:
                try:
                    raw_scenes = version.scenes if hasattr(version, "scenes") and version.scenes else None
                    scene_dicts: list[dict] | None = None
                    if raw_scenes:
                        scene_dicts = [
                            sl if isinstance(sl, dict) else sl.model_dump()
                            for sl in raw_scenes
                        ]
                    mock_result = generate_mock_storyboard(
                        prompt=project.prompt,
                        project_id=project.id,
                        version_id=version.id,
                        storage_root=settings.LOCAL_STORAGE_PATH,
                        scenes=scene_dicts,
                        scene_count=3,  # fallback if no scenes stored
                    )
                    if mock_result.scene_paths:
                        scene_image_paths = mock_result.scene_paths
                        # Use first scene as fallback image_path
                        image_path = mock_result.scene_paths[0]
                        mock_theme_name = mock_result.theme_name
                        mock_scene_count = mock_result.scene_count
                        logger.info(
                            "mock_visual.using_storyboard_scenes",
                            project_id=str(project.id),
                            theme=mock_theme_name,
                            scene_count=mock_scene_count,
                        )
                except Exception as mock_exc:
                    logger.warning(
                        "mock_visual.generation_failed",
                        project_id=str(project.id),
                        error=str(mock_exc),
                    )
                    # Fallback: image_path is already the solid-color placeholder

            # ── Run FFmpeg renderer ───────────────────────────────────────────
            renderer = FFmpegRenderer()

            # Apply render settings if present
            duration = project.duration_seconds
            cta_text = project.cta_text
            if version.render_settings:
                if (
                    "duration_seconds" in version.render_settings
                    and version.render_settings["duration_seconds"] is not None
                ):
                    duration = version.render_settings["duration_seconds"]
                if (
                    "cta_position" in version.render_settings
                    and version.render_settings["cta_position"] is not None
                ):
                    # In phase 1, we just respect the text override or position flag conceptually,
                    # but cta_text itself might be edited via updateReelVersion,
                    # which currently does not update project.cta_text.
                    pass

            params = RenderParams(
                image_path=image_path,
                output_path=output_path,
                thumbnail_path=thumbnail_path,
                duration_seconds=duration,
                audio_path=audio_path,
                srt_path=srt_path,
                cta_text=cta_text,
                scene_image_paths=scene_image_paths,
            )
            result = await renderer.render(params)

            # ── Create MediaAsset for video ───────────────────────────────────
            video_size = result.output_path.stat().st_size if result.output_path.exists() else 0
            video_metadata: dict = {
                "storage_provider": "local",
                "storage_path": str(result.output_path),
                "renderer": result.renderer,
                "audio_asset_id": str(version.voiceover_asset_id or version.audio_asset_id)
                if audio_path
                else None,
                "visual_source": visual_source,
                "has_audio": params.audio_path is not None,
                "has_subtitles": params.srt_path is not None,
                **result.metadata,
            }
            if mock_theme_name:
                video_metadata["mock_visual_theme"] = mock_theme_name
            if mock_scene_count is not None:
                video_metadata["mock_visual_scene_count"] = mock_scene_count
                video_metadata["generated_scene_count"] = mock_scene_count

            video_asset = MediaAsset(
                workspace_id=project.workspace_id,
                project_id=project.id,
                version_id=version.id,
                asset_type=MediaAssetType.RENDERED_VIDEO,
                s3_key=f"renders/{output_filename}",
                s3_bucket="local",
                filename=output_filename,
                mime_type="video/mp4",
                file_size=video_size,
                status=MediaAssetStatus.READY,
                metadata_=video_metadata,
            )
            db.add(video_asset)
            await db.flush()

            # ── Create MediaAsset for thumbnail ───────────────────────────────
            # If FFmpeg didn't produce a thumbnail (e.g. placeholder mode),
            # copy the first mock visual scene image as the thumbnail.
            if not result.thumbnail_path.exists() and scene_image_paths:
                try:
                    import shutil
                    shutil.copy2(scene_image_paths[0], result.thumbnail_path)
                    logger.info(
                        "render_pipeline.using_first_scene_as_thumbnail",
                        scene=str(scene_image_paths[0].name),
                    )
                except Exception as thumb_exc:
                    logger.warning("render_pipeline.thumbnail_copy_failed", error=str(thumb_exc))

            thumb_size = (
                result.thumbnail_path.stat().st_size if result.thumbnail_path.exists() else 0
            )
            thumb_asset = MediaAsset(
                workspace_id=project.workspace_id,
                project_id=project.id,
                version_id=version.id,
                asset_type=MediaAssetType.THUMBNAIL,
                s3_key=f"renders/{thumbnail_filename}",
                s3_bucket="local",
                filename=thumbnail_filename,
                mime_type="image/jpeg",
                file_size=thumb_size,
                status=MediaAssetStatus.READY if thumb_size > 0 else MediaAssetStatus.ERROR,
                metadata_={
                    "storage_provider": "local",
                    "storage_path": str(result.thumbnail_path),
                },
            )
            db.add(thumb_asset)
            await db.flush()

            # ── Update version ────────────────────────────────────────────────
            version.video_asset_id = video_asset.id
            version.rendered_asset_id = video_asset.id
            version.thumbnail_asset_id = thumb_asset.id
            version.status = ReelProjectStatus.READY_TO_PUBLISH

            # ── Finalize job ──────────────────────────────────────────────────
            render_job.status = JobStatus.COMPLETE
            render_job.completed_at = datetime.now(UTC)
            render_job.output_payload = result.metadata

            project.status = ReelProjectStatus.READY_TO_PUBLISH

            # ── Audit ─────────────────────────────────────────────────────────
            audit = AuditLog(
                action="render_completed",
                workspace_id=project.workspace_id,
                user_id=project.created_by,
                resource_type="render_job",
                resource_id=render_job.id,
                metadata_={
                    "video_asset_id": str(video_asset.id),
                    "renderer": result.renderer,
                    "mode": "sync",
                },
            )
            db.add(audit)
            await db.commit()

            logger.info(
                "render_pipeline_complete",
                project_id=str(project_id),
                version_id=str(version_id),
                render_job_id=str(render_job_id),
                renderer=result.renderer,
            )
            return True

        except Exception as exc:
            safe_error = _safe_error_message(exc)
            stderr_tail = getattr(exc, "stderr_tail", None)
            logger.exception(
                "render_pipeline_error",
                project_id=str(project_id),
                version_id=str(version_id),
                render_job_id=str(render_job_id),
                error_type=type(exc).__name__,
                error=safe_error,
                ffmpeg_stderr_tail=stderr_tail,
            )
            try:
                render_job = await db.get(RenderJob, render_job_id)
                project = await db.get(ReelProject, project_id)
                version = await db.get(ReelVersion, version_id)
                if render_job:
                    render_job.status = JobStatus.FAILED
                    render_job.error_message = safe_error
                    if stderr_tail:
                        render_job.command_log = stderr_tail
                    render_job.output_payload = {
                        "error": safe_error,
                        "error_type": type(exc).__name__,
                        "ffmpeg_stderr_tail": stderr_tail,
                    }
                    render_job.completed_at = datetime.now(UTC)
                if project:
                    project.status = ReelProjectStatus.FAILED_RENDER
                if version:
                    version.status = ReelProjectStatus.FAILED_RENDER
                audit = AuditLog(
                    action="render_failed",
                    workspace_id=project.workspace_id if project else None,
                    user_id=project.created_by if project else None,
                    resource_type="render_job",
                    resource_id=render_job_id,
                    metadata_={
                        "error": safe_error,
                        "error_type": type(exc).__name__,
                        "has_ffmpeg_stderr": bool(stderr_tail),
                    },
                )
                db.add(audit)
                await db.commit()
            except Exception:
                logger.exception("render_pipeline_cleanup_error")
            return False


async def _resolve_voiceover_audio_path(
    db: AsyncSession,
    version: ReelVersion,
) -> Path | None:
    """Resolve generated voiceover audio for FFmpeg, if available."""
    asset_id = version.voiceover_asset_id or version.audio_asset_id
    if not asset_id:
        return None
    asset = await db.get(MediaAsset, asset_id)
    if not asset:
        return None
    audio_path = get_local_storage_path(asset)
    if audio_path and audio_path.exists():
        return audio_path
    logger.warning("voiceover_audio_missing", asset_id=str(asset_id))
    return None


def _get_source_image_path(
    project: ReelProject,
    _version: ReelVersion,
    storage_root: str,
) -> Path:
    """
    Resolve the source image local filesystem path.
    Falls back to a placeholder if image is not found.
    """
    placeholder_dir = Path(storage_root) / "placeholders"
    placeholder_dir.mkdir(parents=True, exist_ok=True)

    # Try to find source image from metadata
    if project.source_image_id:
        # Look for any file matching the asset pattern in uploads/
        uploads_dir = Path(storage_root) / "uploads"
        if uploads_dir.exists():
            # Search for file with asset_id in name
            matches = list(uploads_dir.glob(f"{project.source_image_id}*"))
            if matches:
                return matches[0]

    # No source image — create a solid color placeholder
    placeholder_path = placeholder_dir / f"placeholder_{project.id}.png"
    if not placeholder_path.exists():
        _create_placeholder_image(placeholder_path)
    return placeholder_path


def _create_placeholder_image(path: Path) -> None:
    """Create a simple solid color placeholder PNG using struct (no PIL needed)."""
    import struct
    import zlib

    width, height = 1080, 1920
    # Create a dark navy gradient PNG
    path.parent.mkdir(parents=True, exist_ok=True)

    def create_png(w: int, h: int, color: tuple[int, int, int]) -> bytes:
        def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
            crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

        signature = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        ihdr = make_chunk(b"IHDR", ihdr_data)

        row = bytes([0]) + bytes(list(color) * w)
        raw = row * h
        compressed = zlib.compress(raw)
        idat = make_chunk(b"IDAT", compressed)
        iend = make_chunk(b"IEND", b"")
        return signature + ihdr + idat + iend

    png_bytes = create_png(width, height, (15, 23, 42))  # Dark navy
    path.write_bytes(png_bytes)
    logger.info("placeholder_image_created", path=str(path))
