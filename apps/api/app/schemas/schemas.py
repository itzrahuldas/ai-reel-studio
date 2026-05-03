"""Pydantic schemas for request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ── Base ─────────────────────────────────────────────────────────────────────

class OrmBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=255)


class AuthResponse(BaseModel):
    user: "UserResponse"
    workspace: "WorkspaceResponse"
    access_token: str
    token_type: str = "bearer"


class WorkspaceMemberResponse(OrmBaseModel):
    user_id: UUID
    workspace_id: UUID
    role: str
    joined_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(OrmBaseModel):
    id: UUID
    email: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime


# ── Workspace ─────────────────────────────────────────────────────────────────

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class WorkspaceResponse(OrmBaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime


# ── Media Assets ──────────────────────────────────────────────────────────────

class UploadURLRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    mime_type: str = Field(..., pattern=r"^image/(jpeg|png|webp)$")
    file_size: int = Field(..., gt=0, le=20 * 1024 * 1024)
    project_id: UUID | None = None


class UploadURLResponse(BaseModel):
    asset_id: UUID
    upload_url: str
    expires_at: datetime


class MediaAssetResponse(OrmBaseModel):
    id: UUID
    workspace_id: UUID
    asset_type: str
    s3_key: str
    filename: str | None
    mime_type: str | None
    file_size: int | None
    status: str
    url: str | None = None
    created_at: datetime


# ── Reel Version ──────────────────────────────────────────────────────────────

class ReelVersionResponse(OrmBaseModel):
    id: UUID
    project_id: UUID
    version_number: int
    hook: str | None
    script: str | None
    scenes: list | None
    voiceover_text: str | None
    subtitle_lines: list | None
    caption: str | None
    hashtags: list[str] | None
    video_prompt: str | None
    estimated_duration: int | None
    moderation_flags: dict | None
    status: str
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ── Reel Project ──────────────────────────────────────────────────────────────

class CreateReelProjectRequest(BaseModel):
    workspace_id: UUID | None = None
    prompt: str = Field(..., min_length=5, max_length=2000)
    # Loosened language validation: allow 'en', 'hi', 'hinglish', 'en-US', etc.
    language: str = Field(default="en", max_length=30)
    tone: str | None = Field(None, max_length=100)
    duration_seconds: int = Field(default=15, ge=10, le=60)
    cta_text: str | None = Field(None, max_length=500)
    title: str | None = Field(None, max_length=500)
    source_image_id: UUID | None = None


class ReelProjectResponse(OrmBaseModel):
    id: UUID
    workspace_id: UUID
    title: str | None
    prompt: str
    language: str
    tone: str | None
    duration_seconds: int
    cta_text: str | None
    status: str
    latest_version_id: UUID | None
    source_image_id: UUID | None
    created_at: datetime
    updated_at: datetime
    # Enriched detail (optional — populated on detail endpoint)
    latest_version: "ReelVersionResponse | None" = None


class CreateReelProjectResponse(BaseModel):
    project: ReelProjectResponse
    version: ReelVersionResponse
    generation_job: "GenerationJobResponse"


class UpdateCaptionRequest(BaseModel):
    caption: str = Field(..., max_length=2200)


class UpdateHashtagsRequest(BaseModel):
    hashtags: list[str] = Field(..., max_length=30)


class ApproveVersionRequest(BaseModel):
    pass  # No body needed; auth token identifies the approver


class RejectVersionRequest(BaseModel):
    reason: str | None = Field(None, max_length=1000)





# ── Social Accounts ───────────────────────────────────────────────────────────

class SocialAccountResponse(OrmBaseModel):
    id: UUID
    workspace_id: UUID
    connected_by_user_id: UUID
    platform: str
    username: str | None
    account_type: str | None
    ig_user_id: str
    page_id: str | None
    page_name: str | None
    status: str
    token_expires_at: datetime | None
    scopes_json: list[str] | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime
    disconnected_at: datetime | None


# ── Generation Jobs ───────────────────────────────────────────────────────────

class GenerationJobResponse(OrmBaseModel):
    id: UUID
    project_id: UUID
    version_id: UUID | None
    job_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime


# ── Render Jobs ───────────────────────────────────────────────────────────────

class RenderJobResponse(OrmBaseModel):
    id: UUID
    project_id: UUID
    version_id: UUID
    celery_task_id: str | None
    status: str
    renderer: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    command_log: str | None
    input_payload: dict | None
    output_payload: dict | None
    created_at: datetime
    updated_at: datetime


class CreateRenderJobResponse(BaseModel):
    render_job: RenderJobResponse
    project: ReelProjectResponse
    version: ReelVersionResponse


# ── Editor Schemas ────────────────────────────────────────────────────────────

class StoryboardSceneInput(BaseModel):
    scene_number: int | None = None
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    visual_description: str
    text_overlay: str | None = None
    voiceover_text: str | None = None

class SubtitleLineInput(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str

class RenderSettingsInput(BaseModel):
    duration_seconds: int | None = Field(None, gt=0, le=60)
    resolution: str | None = None
    fps: int | None = None
    subtitle_style: str | None = None
    text_position: str | None = None
    cta_position: str | None = None
    include_caption_burn_in: bool | None = None

class UpdateReelVersionRequest(BaseModel):
    hook: str | None = Field(None, max_length=500)
    script: str | None = Field(None, max_length=2000)
    storyboard: list[StoryboardSceneInput] | None = None
    voiceover_text: str | None = Field(None, max_length=2000)
    subtitle_lines: list[SubtitleLineInput] | None = None
    caption: str | None = Field(None, max_length=2200)
    hashtags: list[str] | None = Field(None, max_length=30)
    video_prompt: str | None = Field(None, max_length=1000)
    render_settings: RenderSettingsInput | None = None

class ReelVersionEditorResponse(BaseModel):
    project: ReelProjectResponse
    version: ReelVersionResponse
    can_edit: bool
    can_render: bool
    can_publish: bool
    has_unrendered_edits: bool

class SaveEditorDraftResponse(BaseModel):
    project: ReelProjectResponse
    version: ReelVersionResponse
    message: str


# ── Publish Jobs ──────────────────────────────────────────────────────────────

class PublishJobResponse(OrmBaseModel):
    id: UUID
    project_id: UUID
    version_id: UUID
    social_account_id: UUID
    celery_task_id: str | None
    status: str
    ig_container_id: str | None
    ig_media_id: str | None
    scheduled_for: datetime | None
    schedule_timezone: str | None
    queued_at: datetime | None
    locked_at: datetime | None
    started_at: datetime | None
    published_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    error_message: str | None
    retry_count: int
    execution_attempts: int
    next_attempt_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CreatePublishJobRequest(BaseModel):
    social_account_id: UUID
    caption: str | None = None
    share_to_feed: bool = True
    allow_comments: bool = True

class SchedulePublishJobRequest(BaseModel):
    social_account_id: UUID
    caption: str | None = None
    share_to_feed: bool = True
    allow_comments: bool = True
    scheduled_at: datetime
    schedule_timezone: str = "UTC"


class CreatePublishJobResponse(BaseModel):
    publish_job: PublishJobResponse
    project: ReelProjectResponse
    version: ReelVersionResponse


# ── Errors ────────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail
