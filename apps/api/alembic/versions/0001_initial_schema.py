"""Initial schema — all tables for AI Reel Studio v0.1.0

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-03 15:00:00.000000

This migration creates all 11 core tables:
  users, workspaces, workspace_members, social_accounts,
  media_assets, reel_projects, reel_versions, generation_jobs,
  render_jobs, publish_jobs, audit_logs

To apply:
    docker compose exec api alembic upgrade head
To rollback:
    docker compose exec api alembic downgrade -1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── workspaces ────────────────────────────────────────────────────────────
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "plan",
            sa.Enum("free", "pro", "agency", name="workspaceplan"),
            nullable=False,
            server_default="free",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])

    # ── workspace_members ─────────────────────────────────────────────────────
    op.create_table(
        "workspace_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "admin", "member", "viewer", name="workspacememberrole"),
            nullable=False,
        ),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── social_accounts ───────────────────────────────────────────────────────
    op.create_table(
        "social_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False, server_default="instagram"),
        sa.Column("platform_user_id", sa.String(255), nullable=False),
        sa.Column("platform_username", sa.String(255), nullable=True),
        sa.Column("platform_page_id", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("connected", "reconnect_required", "error", name="socialaccountstatus"),
            nullable=False,
            server_default="connected",
        ),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── reel_projects (no source_image_id FK yet — added after media_assets) ─
    op.create_table(
        "reel_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("language", sa.String(20), nullable=False, server_default="en"),
        sa.Column("tone", sa.String(100), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("cta_text", sa.String(500), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "script_generating", "script_ready", "video_generating",
                "audio_generating", "rendering", "ready_for_review", "approved",
                "publishing", "ig_processing", "published", "failed",
                "failed_script", "failed_video", "failed_audio", "failed_render",
                "failed_instagram_upload", "failed_instagram_publish",
                name="reelprojectstatus",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("latest_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_image_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reel_projects_workspace_id", "reel_projects", ["workspace_id"])
    op.create_index("ix_reel_projects_status", "reel_projects", ["status"])

    # ── reel_versions ─────────────────────────────────────────────────────────
    op.create_table(
        "reel_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reel_projects.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("script", sa.Text(), nullable=True),
        sa.Column("scenes", postgresql.JSONB(), nullable=True),
        sa.Column("voiceover_text", sa.Text(), nullable=True),
        sa.Column("subtitle_lines", postgresql.JSONB(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("video_prompt", sa.Text(), nullable=True),
        sa.Column("estimated_duration", sa.Integer(), nullable=True),
        sa.Column("moderation_flags", postgresql.JSONB(), nullable=True),
        sa.Column("audio_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("video_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rendered_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thumbnail_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "script_generating", "script_ready", "video_generating",
                "audio_generating", "rendering", "ready_for_review", "approved",
                "publishing", "ig_processing", "published", "failed",
                "failed_script", "failed_video", "failed_audio", "failed_render",
                "failed_instagram_upload", "failed_instagram_publish",
                name="reelprojectstatus",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reel_versions_project_id", "reel_versions", ["project_id"])

    # ── media_assets ──────────────────────────────────────────────────────────
    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reel_projects.id"), nullable=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reel_versions.id"), nullable=True),
        sa.Column(
            "asset_type",
            sa.Enum("source_image", "raw_video", "audio", "rendered_video", "thumbnail", name="mediaassettype"),
            nullable=False,
        ),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("s3_bucket", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending_upload", "uploaded", "processing", "ready", "error", name="mediaassetstatus"),
            nullable=False,
            server_default="ready",
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── generation_jobs ───────────────────────────────────────────────────────
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reel_projects.id"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reel_versions.id"), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("job_type", sa.String(50), nullable=False, server_default="full_generation"),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "complete", "failed", name="jobstatus"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_payload", postgresql.JSONB(), nullable=True),
        sa.Column("output_payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_generation_jobs_project_id", "generation_jobs", ["project_id"])
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])

    # ── render_jobs ───────────────────────────────────────────────────────────
    op.create_table(
        "render_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reel_versions.id"), nullable=False),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "complete", "failed", name="jobstatus"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("renderer", sa.String(50), nullable=False, server_default="ffmpeg"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("command_log", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── publish_jobs ──────────────────────────────────────────────────────────
    op.create_table(
        "publish_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reel_projects.id"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reel_versions.id"), nullable=False),
        sa.Column("social_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_accounts.id"), nullable=False),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("queued", "container_created", "polling", "published", "failed", "cancelled", name="publishjobstatus"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("ig_container_id", sa.String(255), nullable=True),
        sa.Column("ig_media_id", sa.String(255), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])

    # ── Add deferred FK constraints ───────────────────────────────────────────
    # reel_projects.latest_version_id → reel_versions.id (USE ALTER because of circular ref)
    op.create_foreign_key(
        "fk_reel_projects_latest_version",
        "reel_projects", "reel_versions",
        ["latest_version_id"], ["id"],
        use_alter=True,
    )
    # reel_projects.source_image_id → media_assets.id
    op.create_foreign_key(
        "fk_reel_projects_source_image",
        "reel_projects", "media_assets",
        ["source_image_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_reel_projects_source_image", "reel_projects", type_="foreignkey")
    op.drop_constraint("fk_reel_projects_latest_version", "reel_projects", type_="foreignkey")
    op.drop_table("audit_logs")
    op.drop_table("publish_jobs")
    op.drop_table("render_jobs")
    op.drop_table("generation_jobs")
    op.drop_table("media_assets")
    op.drop_table("reel_versions")
    op.drop_table("reel_projects")
    op.drop_table("social_accounts")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("users")
    # Drop enums
    for enum_name in [
        "reelprojectstatus", "socialaccountstatus", "mediaassettype",
        "mediaassetstatus", "jobstatus", "publishjobstatus",
        "workspaceplan", "workspacememberrole",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
