"""
Tests for Reel Project endpoints and mock generation pipeline.

Uses FastAPI TestClient with mocked service layer to avoid needing
a real database or Celery broker during CI.

Test categories:
- Media asset upload (valid, invalid type, oversized)
- Reel project creation (auth, workspace, success)
- Project listing (only own workspace)
- Project detail (with version data)
- Regenerate endpoint
- Sync pipeline inline execution
- Worker task (idempotency, failure handling)
"""

import importlib
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.models import (
    GenerationJob,
    JobStatus,
    ReelProject,
    ReelProjectStatus,
    ReelVersion,
)

client = TestClient(app)

# ── Fixtures ──────────────────────────────────────────────────────────────────

FAKE_USER_ID = str(uuid4())
FAKE_WORKSPACE_ID = str(uuid4())
FAKE_PROJECT_ID = str(uuid4())
FAKE_VERSION_ID = str(uuid4())
FAKE_JOB_ID = str(uuid4())
FAKE_ASSET_ID = str(uuid4())

FAKE_TOKEN = "fake-bearer-token"
AUTH_HEADERS = {"Authorization": f"Bearer {FAKE_TOKEN}"}


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _make_user():
    u = MagicMock()
    u.id = FAKE_USER_ID
    u.email = "test@example.com"
    u.full_name = "Test User"
    u.is_active = True
    u.is_verified = False
    return u


def _authenticate_user() -> None:
    async def _current_user():
        return _make_user()

    app.dependency_overrides[get_current_user] = _current_user


@contextmanager
def _worker_generate_module() -> Iterator[object]:
    """Import worker tasks with worker package precedence, then restore API imports."""
    api_root = Path(__file__).resolve().parents[1]
    worker_root = Path(__file__).resolve().parents[2] / "worker"
    saved_path = sys.path[:]
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]

    sys.path[:] = [str(worker_root), str(api_root)] + [
        path for path in sys.path if path not in {str(worker_root), str(api_root)}
    ]

    try:
        yield importlib.import_module("app.tasks.generate_reel")
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_modules)
        sys.path[:] = saved_path


def _make_project():
    p = MagicMock(spec=ReelProject)
    p.id = FAKE_PROJECT_ID
    p.workspace_id = FAKE_WORKSPACE_ID
    p.title = "Test Reel"
    p.prompt = "A great reel about coffee"
    p.language = "en"
    p.tone = "professional"
    p.duration_seconds = 15
    p.cta_text = "Buy now"
    p.status = ReelProjectStatus.DRAFT
    p.latest_version_id = FAKE_VERSION_ID
    p.source_image_id = FAKE_ASSET_ID
    p.created_at = "2026-05-03T10:00:00Z"
    p.updated_at = "2026-05-03T10:00:00Z"
    return p


def _make_version():
    v = MagicMock(spec=ReelVersion)
    v.id = FAKE_VERSION_ID
    v.project_id = FAKE_PROJECT_ID
    v.version_number = 1
    v.hook = "Wait until you see this!"
    v.script = "Are you ready to transform your experience?"
    v.scenes = [{"scene_number": 1, "duration_seconds": 5, "visual_description": "Close-up"}]
    v.voiceover_text = "Full voiceover text here"
    v.subtitle_lines = [{"start_seconds": 0, "end_seconds": 3, "text": "Hello world"}]
    v.caption = "Amazing caption"
    v.hashtags = ["#ai", "#reels"]
    v.video_prompt = "Cinematic vertical video"
    v.estimated_duration = 15
    v.moderation_flags = {"contains_harmful_content": False}
    v.render_settings = None
    v.edit_metadata = None
    v.audio_asset_id = None
    v.voiceover_asset_id = None
    v.video_asset_id = None
    v.rendered_asset_id = None
    v.thumbnail_asset_id = None
    v.status = ReelProjectStatus.READY_FOR_REVIEW
    v.approved_at = None
    v.created_at = "2026-05-03T10:00:00Z"
    v.updated_at = "2026-05-03T10:00:00Z"
    return v


def _make_job():
    j = MagicMock(spec=GenerationJob)
    j.id = FAKE_JOB_ID
    j.project_id = FAKE_PROJECT_ID
    j.version_id = FAKE_VERSION_ID
    j.job_type = "mock_generation"
    j.status = JobStatus.QUEUED
    j.started_at = None
    j.completed_at = None
    j.error_message = None
    j.provider = None
    j.provider_metadata_json = None
    j.error_code = None
    j.retry_count = 0
    j.created_at = "2026-05-03T10:00:00Z"
    j.updated_at = "2026-05-03T10:00:00Z"
    return j


def _make_render_job():
    from app.models.models import RenderJob
    j = MagicMock(spec=RenderJob)
    j.id = str(uuid4())
    j.project_id = FAKE_PROJECT_ID
    j.version_id = FAKE_VERSION_ID
    j.status = JobStatus.QUEUED
    j.celery_task_id = None
    j.renderer = "ffmpeg"
    j.started_at = None
    j.completed_at = None
    j.error_message = None
    j.command_log = None
    j.input_payload = None
    j.output_payload = None
    j.created_at = "2026-05-03T10:00:00Z"
    j.updated_at = "2026-05-03T10:00:00Z"
    return j


# ── Media Asset Upload Tests ──────────────────────────────────────────────────

@patch("app.api.deps.decode_token")
@patch("app.api.deps.AsyncSession.get")
@patch("app.api.v1.routers.media_assets._resolve_workspace", new_callable=AsyncMock)
def test_upload_media_asset_unsupported_type(mock_ws, mock_get, mock_decode):
    """Reject files that are not jpeg/png/webp."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    mock_get.return_value = _make_user()

    response = client.post(
        "/api/v1/media-assets/upload",
        headers=AUTH_HEADERS,
        files={"file": ("video.mp4", b"fake-video-data", "video/mp4")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_media_asset_unauthenticated():
    """Reject upload without Bearer token."""
    response = client.post(
        "/api/v1/media-assets/upload",
        files={"file": ("img.jpg", b"data", "image/jpeg")},
    )
    assert response.status_code == 401


# ── Reel Project Creation Tests ───────────────────────────────────────────────

def test_create_reel_project_unauthenticated():
    """Unauthenticated request should return 401."""
    response = client.post(
        "/api/v1/reel-projects/",
        json={"prompt": "A great reel about coffee"},
    )
    assert response.status_code == 401


@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.create_reel_project", new_callable=AsyncMock)
def test_create_reel_project_success(mock_create, mock_decode):
    """Authenticated user creates a reel project successfully."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    mock_create.return_value = (_make_project(), _make_version(), _make_job())

    response = client.post(
        "/api/v1/reel-projects/",
        headers=AUTH_HEADERS,
        json={
            "prompt": "A coffee shop reel for Instagram",
            "language": "en",
            "tone": "professional",
            "duration_seconds": 15,
            "cta_text": "Visit our shop!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "project" in data
    assert "version" in data
    assert "generation_job" in data
    assert data["project"]["status"] == "draft"


@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.create_reel_project", new_callable=AsyncMock)
def test_create_reel_project_with_image(mock_create, mock_decode):
    """Project creation accepts source_image_id."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    project = _make_project()
    project.source_image_id = FAKE_ASSET_ID
    mock_create.return_value = (project, _make_version(), _make_job())

    response = client.post(
        "/api/v1/reel-projects/",
        headers=AUTH_HEADERS,
        json={
            "prompt": "Product launch reel",
            "language": "hi",
            "tone": "luxury",
            "duration_seconds": 20,
            "source_image_id": FAKE_ASSET_ID,
        },
    )
    assert response.status_code == 201
    assert response.json()["project"]["source_image_id"] == FAKE_ASSET_ID


@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.get_projects", new_callable=AsyncMock)
def test_list_projects_success(mock_list, mock_decode):
    """Authenticated user can list their workspace projects."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    mock_list.return_value = [_make_project()]

    response = client.get("/api/v1/reel-projects/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["prompt"] == "A great reel about coffee"


@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.get_project_with_version", new_callable=AsyncMock)
def test_get_project_with_version_detail(mock_get, mock_decode):
    """Reel detail endpoint returns project + latest version content."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    version = _make_version()
    version.status = ReelProjectStatus.READY_FOR_REVIEW
    mock_get.return_value = {"project": _make_project(), "latest_version": version}

    response = client.get(f"/api/v1/reel-projects/{FAKE_PROJECT_ID}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["latest_version"]["hook"] == "Wait until you see this!"
    assert data["latest_version"]["script"] is not None
    assert data["latest_version"]["hashtags"] == ["#ai", "#reels"]


@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.get_project_with_version", new_callable=AsyncMock)
def test_get_project_not_found(mock_get, mock_decode):
    """Returns 404 for non-existent or inaccessible project."""
    from fastapi import HTTPException
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    mock_get.side_effect = HTTPException(status_code=404, detail="Project not found")

    response = client.get(f"/api/v1/reel-projects/{uuid4()}", headers=AUTH_HEADERS)
    assert response.status_code == 404


@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.regenerate_reel_project", new_callable=AsyncMock)
def test_regenerate_creates_new_version(mock_regen, mock_decode):
    """Regenerate endpoint creates new version + job."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    new_version = _make_version()
    new_version.version_number = 2
    new_job = _make_job()
    mock_regen.return_value = (new_version, new_job)

    response = client.post(
        f"/api/v1/reel-projects/{FAKE_PROJECT_ID}/regenerate",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 201
    data = response.json()
    assert "version" in data
    assert "generation_job" in data


@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.get_project_jobs", new_callable=AsyncMock)
def test_get_project_jobs(mock_jobs, mock_decode):
    """Jobs endpoint returns generation timeline."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    mock_jobs.return_value = [_make_job()]

    response = client.get(
        f"/api/v1/reel-projects/{FAKE_PROJECT_ID}/jobs",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["job_type"] == "mock_generation"


# ── Render Pipeline Tests ─────────────────────────────────────────────────────

@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.create_render_job", new_callable=AsyncMock)
def test_render_project_success(mock_render, mock_decode):
    """Render endpoint creates a render job and returns it."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    mock_render.return_value = (_make_render_job(), _make_project(), _make_version())

    response = client.post(
        f"/api/v1/reel-projects/{FAKE_PROJECT_ID}/render",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 201
    data = response.json()
    assert "render_job" in data
    assert "project" in data
    assert "version" in data


def test_render_project_unauthenticated():
    response = client.post(f"/api/v1/reel-projects/{FAKE_PROJECT_ID}/render")
    assert response.status_code == 401


@patch("app.api.deps.decode_token")
@patch("app.api.v1.routers.reel_projects.get_render_jobs", new_callable=AsyncMock)
def test_get_render_jobs(mock_get_jobs, mock_decode):
    """Render jobs endpoint returns list of render jobs."""
    _authenticate_user()
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    mock_get_jobs.return_value = [_make_render_job()]

    response = client.get(
        f"/api/v1/reel-projects/{FAKE_PROJECT_ID}/render-jobs",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["renderer"] == "ffmpeg"


# ── Sync Pipeline Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_pipeline_produces_valid_output():
    """Sync pipeline creates valid CreativePlan via mock provider."""
    from app.services.ai.base import CreativePlan
    from app.services.ai.mock_provider import MockLLMProvider

    provider = MockLLMProvider()
    plan = await provider.generate_creative_plan(
        prompt="Test reel about coffee",
        context={"tone": "professional", "duration": 15, "cta": "Visit us"},
    )
    validated = CreativePlan.model_validate(plan.model_dump())

    assert validated.hook
    assert validated.script
    assert len(validated.scenes) > 0
    assert validated.voiceover_text
    assert len(validated.subtitle_lines) > 0
    assert validated.caption
    assert len(validated.hashtags) > 0
    assert validated.video_prompt
    assert validated.estimated_duration_seconds > 0
    assert not validated.moderation_flags.contains_harmful_content


@pytest.mark.asyncio
async def test_hinglish_language_accepted():
    """'hinglish' language value must pass schema validation."""
    from app.schemas.schemas import CreateReelProjectRequest

    req = CreateReelProjectRequest(
        prompt="Ek amazing coffee shop ka reel banao",
        language="hinglish",
        tone="funny",
        duration_seconds=15,
    )
    assert req.language == "hinglish"


# ── Worker Task Tests (unit-level, no DB) ─────────────────────────────────────

def test_worker_task_missing_job():
    """Task returns error if job not found in DB."""
    session = MagicMock()
    session.get.return_value = None

    with _worker_generate_module() as worker_generate, patch.object(
        worker_generate, "_get_sync_db", return_value=session
    ):
        result = worker_generate.generate_reel_mock_task.run(
            project_id=str(uuid4()),
            version_id=str(uuid4()),
            job_id=str(uuid4()),
        )
    assert result["status"] == "error"
    assert result["reason"] == "missing_records"


def test_worker_task_idempotent():
    """Task skips execution if job is already COMPLETE."""
    job = MagicMock(spec=GenerationJob)
    job.status = JobStatus.COMPLETE

    session = MagicMock()
    session.get.side_effect = (
        lambda model, pk: job if getattr(model, "__name__", None) == "GenerationJob" else MagicMock()
    )

    with _worker_generate_module() as worker_generate, patch.object(
        worker_generate, "_get_sync_db", return_value=session
    ):
        result = worker_generate.generate_reel_mock_task.run(
            project_id=str(uuid4()),
            version_id=str(uuid4()),
            job_id=str(uuid4()),
        )
    assert result["status"] == "skipped"
    assert result["reason"] == "already_complete"
