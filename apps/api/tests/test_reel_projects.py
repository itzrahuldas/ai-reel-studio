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

import asyncio
import importlib
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import settings
from app.main import app
from app.models.models import (
    GenerationJob,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaAssetType,
    ReelProject,
    ReelProjectStatus,
    ReelVersion,
)
from app.services.render_service import build_media_asset_response, build_media_url

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


def _make_media_asset(
    asset_type: MediaAssetType,
    s3_key: str,
    mime_type: str,
    metadata: dict | None = None,
) -> MediaAsset:
    return MediaAsset(
        id=uuid4(),
        workspace_id=uuid4(),
        project_id=FAKE_PROJECT_ID,
        version_id=FAKE_VERSION_ID,
        asset_type=asset_type,
        s3_key=s3_key,
        s3_bucket="local",
        filename=s3_key.rsplit("/", 1)[-1],
        mime_type=mime_type,
        file_size=1234,
        status=MediaAssetStatus.READY,
        metadata_=metadata or {},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


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


def test_local_media_url_uses_storage_public_base(monkeypatch):
    """Local media URLs should use STORAGE_PUBLIC_BASE_URL and the relative s3_key."""
    monkeypatch.setattr(settings, "STORAGE_PUBLIC_BASE_URL", "http://localhost:8000/static")
    asset = _make_media_asset(
        MediaAssetType.RENDERED_VIDEO,
        "renders/reel-test.mp4",
        "video/mp4",
    )

    assert build_media_url(asset) == "http://localhost:8000/static/renders/reel-test.mp4"


def test_media_asset_response_does_not_expose_local_storage_path(monkeypatch):
    """Safe asset responses include public URLs, not raw filesystem metadata."""
    monkeypatch.setattr(settings, "STORAGE_PUBLIC_BASE_URL", "http://localhost:8000/static")
    asset = _make_media_asset(
        MediaAssetType.RENDERED_VIDEO,
        "renders/reel-test.mp4",
        "video/mp4",
        metadata={"storage_path": "/var/lib/ai-reel-studio/media/renders/reel-test.mp4"},
    )

    response = build_media_asset_response(asset)

    assert response["url"] == "http://localhost:8000/static/renders/reel-test.mp4"
    assert response["media_url"] == response["url"]
    assert response["public_url"] == response["url"]
    assert "storage_path" not in response
    assert "/var/lib" not in response["url"]
    assert "/var/lib" not in response["s3_key"]


def test_media_url_sanitizes_accidental_filesystem_key(monkeypatch):
    """Even malformed s3_key values must not leak local filesystem prefixes."""
    monkeypatch.setattr(settings, "STORAGE_PUBLIC_BASE_URL", "http://localhost:8000/static")
    asset = _make_media_asset(
        MediaAssetType.RENDERED_VIDEO,
        r"C:\private\media\reel-test.mp4",
        "video/mp4",
    )

    url = build_media_url(asset)

    assert url == "http://localhost:8000/static/reel-test.mp4"
    assert "C:" not in url
    assert "\\" not in url


def test_media_url_sanitizes_accidental_posix_filesystem_key(monkeypatch):
    """POSIX storage paths should be collapsed to the basename before URL exposure."""
    monkeypatch.setattr(settings, "STORAGE_PUBLIC_BASE_URL", "http://localhost:8000/static")
    asset = _make_media_asset(
        MediaAssetType.RENDERED_VIDEO,
        "/var/lib/ai-reel-studio/media/renders/reel-test.mp4",
        "video/mp4",
    )

    url = build_media_url(asset)

    assert url == "http://localhost:8000/static/reel-test.mp4"
    assert "/var/lib" not in url

    response = build_media_asset_response(asset)

    assert response["s3_key"] == "reel-test.mp4"
    assert response["filename"] == "reel-test.mp4"


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
def test_get_project_detail_includes_safe_media_urls(mock_get, mock_decode, monkeypatch):
    """Reel detail response includes playable media URLs without filesystem paths."""
    _authenticate_user()
    monkeypatch.setattr(settings, "STORAGE_PUBLIC_BASE_URL", "http://localhost:8000/static")
    mock_decode.return_value = {"sub": FAKE_USER_ID, "type": "access"}
    version = _make_version()
    video_asset = _make_media_asset(
        MediaAssetType.RENDERED_VIDEO,
        "renders/reel-test.mp4",
        "video/mp4",
        metadata={"storage_path": "/var/lib/ai-reel-studio/media/renders/reel-test.mp4"},
    )
    thumbnail_asset = _make_media_asset(
        MediaAssetType.THUMBNAIL,
        "renders/thumb-test.jpg",
        "image/jpeg",
    )
    audio_asset = _make_media_asset(
        MediaAssetType.AUDIO,
        "voiceovers/voiceover-test.wav",
        "audio/wav",
        metadata={"provider": "mock"},
    )
    version.video_asset_id = video_asset.id
    version.thumbnail_asset_id = thumbnail_asset.id
    version.voiceover_asset_id = audio_asset.id
    mock_get.return_value = {
        "project": _make_project(),
        "latest_version": version,
        "media_assets": {
            "rendered_video": video_asset,
            "thumbnail": thumbnail_asset,
            "voiceover_audio": audio_asset,
        },
    }

    response = client.get(f"/api/v1/reel-projects/{FAKE_PROJECT_ID}", headers=AUTH_HEADERS)

    assert response.status_code == 200
    latest_version = response.json()["latest_version"]
    assert latest_version["rendered_video_url"] == "http://localhost:8000/static/renders/reel-test.mp4"
    assert latest_version["thumbnail_url"] == "http://localhost:8000/static/renders/thumb-test.jpg"
    assert latest_version["voiceover_url"] == "http://localhost:8000/static/voiceovers/voiceover-test.wav"
    assert latest_version["audio_url"] == latest_version["voiceover_url"]
    assert latest_version["voiceover_provider"] == "mock"
    assert "/var/lib" not in latest_version["rendered_video_url"]


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


def test_generation_provider_job_uses_local_async_session(monkeypatch):
    """Provider task helper creates and disposes async DB resources per event loop."""
    with _worker_generate_module() as worker_generate:
        fake_engine = _FakeAsyncEngine()
        fake_session = _FakeAsyncSession()
        captured: dict[str, object] = {}

        def fake_create_async_engine(*args, **kwargs):
            captured["engine_args"] = args
            captured["engine_kwargs"] = kwargs
            return fake_engine

        def fake_async_sessionmaker(**kwargs):
            captured["sessionmaker_kwargs"] = kwargs
            return _FakeAsyncSessionFactory(fake_session)

        async def fake_pipeline(db, project_id, version_id, job_id):
            assert db is fake_session
            assert project_id
            assert version_id
            assert job_id
            return True

        reel_project = importlib.import_module("app.services.reel_project")
        monkeypatch.setattr(worker_generate, "create_async_engine", fake_create_async_engine)
        monkeypatch.setattr(worker_generate, "async_sessionmaker", fake_async_sessionmaker)
        monkeypatch.setattr(reel_project, "_run_provider_pipeline_with_db", fake_pipeline)

        result = asyncio.run(
            worker_generate.run_generation_provider_job(uuid4(), uuid4(), uuid4())
        )

        assert result is True
        assert fake_session.entered is True
        assert fake_session.exited is True
        assert fake_engine.disposed is True
        assert captured["engine_args"][0] == worker_generate.settings.DATABASE_URL


def test_generate_reel_task_failed_pipeline_does_not_log_complete(monkeypatch):
    """Provider task returns failed and does not emit a misleading complete log."""
    with _worker_generate_module() as worker_generate:
        fake_logger = _FakeWorkerLogger()

        async def fake_provider_job(project_id, version_id, job_id):
            assert project_id
            assert version_id
            assert job_id
            return False

        monkeypatch.setattr(worker_generate, "run_generation_provider_job", fake_provider_job)
        monkeypatch.setattr(worker_generate, "logger", fake_logger)

        result = worker_generate.generate_reel_task.run(
            project_id=str(uuid4()),
            version_id=str(uuid4()),
            job_id=str(uuid4()),
        )

        assert result["status"] == "failed"
        assert "generate_reel_task.failed" in fake_logger.warning_events
        assert "generate_reel_task.complete" not in fake_logger.info_events


class _FakeAsyncEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True


class _FakeAsyncSessionFactory:
    def __init__(self, session: _FakeAsyncSession) -> None:
        self.session = session

    def __call__(self) -> _FakeAsyncSession:
        return self.session


class _FakeWorkerLogger:
    def __init__(self) -> None:
        self.info_events: list[str] = []
        self.warning_events: list[str] = []
        self.error_events: list[str] = []

    def info(self, event: str, **_kwargs) -> None:
        self.info_events.append(event)

    def warning(self, event: str, **_kwargs) -> None:
        self.warning_events.append(event)

    def error(self, event: str, **_kwargs) -> None:
        self.error_events.append(event)

    def exception(self, event: str, **_kwargs) -> None:
        self.error_events.append(event)
