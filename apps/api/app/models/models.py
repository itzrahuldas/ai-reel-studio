"""
SQLAlchemy models for AI Reel Studio.
All models use UUID primary keys, created_at/updated_at timestamps,
and status enums.
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Persist StrEnum values instead of member names for legacy lowercase DB enums."""
    return [member.value for member in enum_cls]

# ── Status Enums ────────────────────────────────────────────────────────────


class ReelProjectStatus(enum.StrEnum):
    DRAFT = "draft"
    SCRIPT_GENERATING = "script_generating"
    SCRIPT_READY = "script_ready"
    VIDEO_GENERATING = "video_generating"
    AUDIO_GENERATING = "audio_generating"
    RENDERING = "rendering"
    RENDERED = "rendered"
    READY_FOR_REVIEW = "ready_for_review"
    READY_TO_PUBLISH = "ready_to_publish"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    IG_PROCESSING = "ig_processing"
    PUBLISHED = "published"
    FAILED = "failed"
    FAILED_SCRIPT = "failed_script"
    FAILED_VIDEO = "failed_video"
    FAILED_AUDIO = "failed_audio"
    FAILED_RENDER = "failed_render"
    FAILED_INSTAGRAM_UPLOAD = "failed_instagram_upload"
    FAILED_INSTAGRAM_PUBLISH = "failed_instagram_publish"


class SocialAccountStatus(enum.StrEnum):
    CONNECTED = "connected"
    RECONNECT_REQUIRED = "reconnect_required"
    ERROR = "error"


class MediaAssetStatus(enum.StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class MediaAssetType(enum.StrEnum):
    SOURCE_IMAGE = "source_image"
    RAW_VIDEO = "raw_video"
    AUDIO = "audio"
    RENDERED_VIDEO = "rendered_video"
    THUMBNAIL = "thumbnail"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class PublishJobStatus(enum.StrEnum):
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    CONTAINER_CREATED = "container_created"
    POLLING = "polling"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECONNECT_REQUIRED = "reconnect_required"


class WorkspacePlan(enum.StrEnum):
    FREE = "free"
    CREATOR = "creator"
    PRO = "pro"
    AGENCY = "agency"


class WorkspaceMemberRole(enum.StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class SubscriptionStatus(enum.StrEnum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"


class UsageEventType(enum.StrEnum):
    AI_GENERATION = "AI_GENERATION"
    RENDER = "RENDER"
    PUBLISH = "PUBLISH"
    SCHEDULED_PUBLISH = "SCHEDULED_PUBLISH"



# ── Mixin ───────────────────────────────────────────────────────────────────


class TimestampMixin:
    """Adds created_at and updated_at to any model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ── Models ───────────────────────────────────────────────────────────────────


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    workspace_memberships: Mapped[list["WorkspaceMember"]] = relationship(
        back_populates="user",
        foreign_keys="WorkspaceMember.user_id",
    )
    owned_workspaces: Mapped[list["Workspace"]] = relationship(back_populates="owner")


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    owner_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan: Mapped[WorkspacePlan] = mapped_column(
        Enum(WorkspacePlan, name="workspaceplan", values_callable=enum_values),
        default=WorkspacePlan.FREE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="owned_workspaces")
    members: Mapped[list["WorkspaceMember"]] = relationship(back_populates="workspace")
    social_accounts: Mapped[list["SocialAccount"]] = relationship(back_populates="workspace")
    reel_projects: Mapped[list["ReelProject"]] = relationship(back_populates="workspace")
    subscription: Mapped["WorkspaceSubscription"] = relationship(back_populates="workspace", uselist=False)
    usage_counters: Mapped[list["UsageCounter"]] = relationship(back_populates="workspace")
    usage_events: Mapped[list["UsageEvent"]] = relationship(back_populates="workspace")


class WorkspaceMember(TimestampMixin, Base):
    __tablename__ = "workspace_members"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[WorkspaceMemberRole] = mapped_column(
        Enum(WorkspaceMemberRole, name="workspacememberrole", values_callable=enum_values),
        nullable=False,
    )
    invited_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="workspace_memberships", foreign_keys=[user_id])


class SocialAccount(TimestampMixin, Base):
    __tablename__ = "social_accounts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    connected_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="instagram")
    status: Mapped[SocialAccountStatus] = mapped_column(
        Enum(SocialAccountStatus, name="socialaccountstatus", values_callable=enum_values),
        default=SocialAccountStatus.CONNECTED,
        nullable=False,
    )
    username: Mapped[str | None] = mapped_column(String(255))
    account_type: Mapped[str | None] = mapped_column(String(50))
    ig_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    page_id: Mapped[str | None] = mapped_column(String(255))
    page_name: Mapped[str | None] = mapped_column(String(255))
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes_json: Mapped[list[str] | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="social_accounts")
    publish_jobs: Mapped[list["PublishJob"]] = relationship(back_populates="social_account")


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_projects.id"))
    version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_versions.id"))
    asset_type: Mapped[MediaAssetType] = mapped_column(
        Enum(MediaAssetType, name="mediaassettype", values_callable=enum_values),
        nullable=False,
    )
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[MediaAssetStatus] = mapped_column(
        Enum(MediaAssetStatus, name="mediaassetstatus", values_callable=enum_values),
        default=MediaAssetStatus.PENDING_UPLOAD,
        nullable=False,
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)


class ReelProject(TimestampMixin, Base):
    __tablename__ = "reel_projects"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    tone: Mapped[str | None] = mapped_column(String(100))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    cta_text: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ReelProjectStatus] = mapped_column(
        Enum(ReelProjectStatus, name="reelprojectstatus", values_callable=enum_values),
        default=ReelProjectStatus.DRAFT,
        nullable=False,
        index=True,
    )
    latest_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_versions.id", use_alter=True))
    source_image_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("media_assets.id"))

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="reel_projects")
    versions: Mapped[list["ReelVersion"]] = relationship(
        back_populates="project",
        foreign_keys="ReelVersion.project_id",
    )
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(back_populates="project")
    publish_jobs: Mapped[list["PublishJob"]] = relationship(back_populates="project")


class ReelVersion(TimestampMixin, Base):
    __tablename__ = "reel_versions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_projects.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hook: Mapped[str | None] = mapped_column(Text)
    script: Mapped[str | None] = mapped_column(Text)
    scenes: Mapped[list | None] = mapped_column(JSONB)
    voiceover_text: Mapped[str | None] = mapped_column(Text)
    subtitle_lines: Mapped[list | None] = mapped_column(JSONB)
    caption: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    video_prompt: Mapped[str | None] = mapped_column(Text)
    estimated_duration: Mapped[int | None] = mapped_column(Integer)
    moderation_flags: Mapped[dict | None] = mapped_column(JSONB)
    render_settings: Mapped[dict | None] = mapped_column("render_settings", JSONB)
    edit_metadata: Mapped[dict | None] = mapped_column("edit_metadata", JSONB)
    voiceover_asset_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("media_assets.id"),
    )
    audio_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("media_assets.id"))
    video_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("media_assets.id"))
    rendered_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("media_assets.id"))
    thumbnail_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("media_assets.id"))
    status: Mapped[ReelProjectStatus] = mapped_column(
        Enum(ReelProjectStatus, name="reelprojectstatus", values_callable=enum_values),
        default=ReelProjectStatus.DRAFT,
        nullable=False,
    )
    approved_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    # Relationships
    project: Mapped["ReelProject"] = relationship(back_populates="versions", foreign_keys=[project_id])
    render_jobs: Mapped[list["RenderJob"]] = relationship(back_populates="version")


class GenerationJob(TimestampMixin, Base):
    __tablename__ = "generation_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_projects.id"), nullable=False, index=True)
    version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_versions.id"))
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    job_type: Mapped[str] = mapped_column(String(50), default="full_generation", nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus", values_callable=enum_values),
        default=JobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_payload: Mapped[dict | None] = mapped_column(JSONB)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    provider: Mapped[str | None] = mapped_column(String(50), index=True)
    provider_metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100), index=True)

    # Relationships
    project: Mapped["ReelProject"] = relationship(back_populates="generation_jobs")


class RenderJob(TimestampMixin, Base):
    __tablename__ = "render_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_projects.id"), nullable=False, index=True)
    version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_versions.id"), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus", values_callable=enum_values),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    renderer: Mapped[str] = mapped_column(String(50), default="ffmpeg", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    command_log: Mapped[str | None] = mapped_column(Text)
    input_payload: Mapped[dict | None] = mapped_column(JSONB)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    version: Mapped["ReelVersion"] = relationship(back_populates="render_jobs")



class PublishJob(TimestampMixin, Base):
    __tablename__ = "publish_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_projects.id"), nullable=False)
    version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reel_versions.id"), nullable=False)
    social_account_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("social_accounts.id"), nullable=False, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[PublishJobStatus] = mapped_column(
        Enum(PublishJobStatus, name="publishjobstatus", values_callable=enum_values),
        default=PublishJobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    ig_container_id: Mapped[str | None] = mapped_column(String(255))
    ig_media_id: Mapped[str | None] = mapped_column(String(255))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schedule_timezone: Mapped[str | None] = mapped_column(String(50))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_payload: Mapped[dict | None] = mapped_column(JSONB)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    project: Mapped["ReelProject"] = relationship(back_populates="publish_jobs")
    version: Mapped["ReelVersion"] = relationship()
    social_account: Mapped["SocialAccount"] = relationship(back_populates="publish_jobs")


class WorkspaceSubscription(TimestampMixin, Base):
    __tablename__ = "workspace_subscriptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan_key: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), index=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), index=True)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="subscription")


class StripeWebhookEvent(TimestampMixin, Base):
    __tablename__ = "stripe_webhook_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    processing_status: Mapped[str] = mapped_column(String(50), default="processing", nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict | None] = mapped_column(JSONB)


class UsageCounter(TimestampMixin, Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        Index("ix_usage_counters_workspace_period", "workspace_id", "period_start", "period_end"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ai_generations_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    renders_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    publishes_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_publishes_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="usage_counters")


class UsageEvent(TimestampMixin, Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_workspace_type_job", "workspace_id", "event_type", "related_job_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[UsageEventType] = mapped_column(Enum(UsageEventType), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Context references
    related_project_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    related_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    related_job_id: Mapped[str | None] = mapped_column(String(255)) # string for flexibility if we use worker UUIDs

    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="usage_events")



class AuditLog(Base):
    """Immutable audit log — never updated, only appended."""
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
