import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ReelProject, ReelProjectStatus, ReelVersion, WorkspaceMember
from app.schemas.schemas import (
    ReelVersionEditorResponse,
    SaveEditorDraftResponse,
    UpdateReelVersionRequest,
)


async def get_project_and_version(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID, version_id: uuid.UUID | None = None
) -> tuple[ReelProject, ReelVersion]:
    stmt = (
        select(ReelProject)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(
            WorkspaceMember.user_id == user_id,
            ReelProject.id == project_id,
        )
    )
    result = await db.execute(stmt)
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if version_id:
        v_stmt = select(ReelVersion).where(ReelVersion.id == version_id, ReelVersion.project_id == project_id)
        v_res = await db.execute(v_stmt)
        version = v_res.scalars().first()
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
    else:
        if not project.latest_version_id:
            raise HTTPException(status_code=404, detail="Project has no versions")
        v_stmt = select(ReelVersion).where(ReelVersion.id == project.latest_version_id)
        v_res = await db.execute(v_stmt)
        version = v_res.scalars().first()
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

    return project, version


async def get_editor_data(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> ReelVersionEditorResponse:
    project, version = await get_project_and_version(db, user_id, project_id)

    # Determine capabilities
    can_edit = version.status not in (ReelProjectStatus.PUBLISHED, ReelProjectStatus.IG_PROCESSING, ReelProjectStatus.PUBLISHING)

    # can render if not generating or rendering currently
    can_render = project.status not in (ReelProjectStatus.SCRIPT_GENERATING, ReelProjectStatus.RENDERING) and can_edit

    # can publish if rendered and not edited since last render
    has_unrendered_edits = False
    if version.rendered_asset_id and version.updated_at > version.created_at:
        # Real logic: checking if updated_at > render job completed_at would be ideal,
        # but since we create a new version when editing a published/rendered one,
        # we can just assume it has unrendered edits if edit_metadata indicates changes after render.
        pass

    # A better check for unrendered edits is comparing version.status
    has_unrendered_edits = (version.status == ReelProjectStatus.DRAFT) and (version.rendered_asset_id is not None)
    if version.rendered_asset_id is None:
        has_unrendered_edits = True # need render first

    can_publish = (not has_unrendered_edits) and (version.rendered_asset_id is not None) and (project.status != ReelProjectStatus.PUBLISHING)

    from app.schemas.schemas import ReelProjectResponse, ReelVersionResponse

    return ReelVersionEditorResponse(
        project=ReelProjectResponse.model_validate(project),
        version=ReelVersionResponse.model_validate(version),
        can_edit=can_edit,
        can_render=can_render,
        can_publish=can_publish,
        has_unrendered_edits=has_unrendered_edits,
    )


async def update_reel_version(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    data: UpdateReelVersionRequest,
) -> SaveEditorDraftResponse:
    project, version = await get_project_and_version(db, user_id, project_id, version_id)

    if version.status in (ReelProjectStatus.PUBLISHED, ReelProjectStatus.IG_PROCESSING, ReelProjectStatus.PUBLISHING):
        raise HTTPException(
            status_code=409,
            detail="Cannot edit a published or publishing version. Please clone it first.",
        )

    # If it has a rendered asset, we should technically clone it, but the requirements say:
    # "Prefer creating a new version when a user edits generated content after rendering/publishing."
    # Let's clone automatically if it's already rendered.
    cloned = False
    if version.rendered_asset_id:
        # Clone
        stmt = select(ReelVersion).where(ReelVersion.project_id == project_id)
        existing = list((await db.execute(stmt)).scalars().all())
        new_version_number = len(existing) + 1

        new_version = ReelVersion(
            project_id=project.id,
            version_number=new_version_number,
            status=ReelProjectStatus.DRAFT,
            hook=version.hook,
            script=version.script,
            scenes=version.scenes,
            voiceover_text=version.voiceover_text,
            subtitle_lines=version.subtitle_lines,
            caption=version.caption,
            hashtags=version.hashtags,
            video_prompt=version.video_prompt,
            estimated_duration=version.estimated_duration,
            moderation_flags=version.moderation_flags,
            voiceover_asset_id=version.voiceover_asset_id,
            audio_asset_id=version.audio_asset_id, # Keep audio if we want, or reset
            # DO NOT copy rendered_asset_id or thumbnail_asset_id
        )
        db.add(new_version)
        await db.flush()
        version = new_version
        project.latest_version_id = version.id
        cloned = True

    # Update fields
    if data.hook is not None:
        version.hook = data.hook
    if data.script is not None:
        version.script = data.script
    if data.storyboard is not None:
        version.scenes = [s.model_dump() for s in data.storyboard]
    if data.voiceover_text is not None:
        version.voiceover_text = data.voiceover_text
    if data.subtitle_lines is not None:
        version.subtitle_lines = [sl.model_dump() for sl in data.subtitle_lines]
    if data.caption is not None:
        version.caption = data.caption
    if data.hashtags is not None:
        version.hashtags = data.hashtags
    if data.video_prompt is not None:
        version.video_prompt = data.video_prompt
    if data.render_settings is not None:
        version.render_settings = data.render_settings.model_dump()

    # Mark as draft so it requires re-render
    version.status = ReelProjectStatus.DRAFT
    project.status = ReelProjectStatus.DRAFT

    version.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(project)
    await db.refresh(version)

    from app.schemas.schemas import ReelProjectResponse, ReelVersionResponse

    return SaveEditorDraftResponse(
        project=ReelProjectResponse.model_validate(project),
        version=ReelVersionResponse.model_validate(version),
        message="Created a new editable version." if cloned else "Draft updated successfully.",
    )


async def clone_reel_version(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
) -> ReelVersion:
    project, version = await get_project_and_version(db, user_id, project_id, version_id)

    stmt = select(ReelVersion).where(ReelVersion.project_id == project_id)
    existing = list((await db.execute(stmt)).scalars().all())
    new_version_number = len(existing) + 1

    new_version = ReelVersion(
        project_id=project.id,
        version_number=new_version_number,
        status=ReelProjectStatus.DRAFT,
        hook=version.hook,
        script=version.script,
        scenes=version.scenes,
        voiceover_text=version.voiceover_text,
        subtitle_lines=version.subtitle_lines,
        caption=version.caption,
        hashtags=version.hashtags,
        video_prompt=version.video_prompt,
        estimated_duration=version.estimated_duration,
        moderation_flags=version.moderation_flags,
        render_settings=version.render_settings,
        edit_metadata=version.edit_metadata,
        voiceover_asset_id=version.voiceover_asset_id,
        audio_asset_id=version.audio_asset_id,
        # Render/video media is not copied because it belongs to a specific render.
    )
    db.add(new_version)
    await db.flush()

    project.latest_version_id = new_version.id
    project.status = ReelProjectStatus.DRAFT

    await db.commit()
    await db.refresh(new_version)
    return new_version
