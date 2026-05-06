import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ai-provider-phase1")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "a" * 64)


class FakeAsyncDb:
    def __init__(self, asset=None):
        self.asset = asset
        self.added = []

    async def get(self, _model, _pk):
        return self.asset

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()


def test_provider_factory_returns_mock_by_default(monkeypatch):
    from app.core.config import settings
    from app.services.ai.mock_provider import MockLLMProvider
    from app.services.ai.provider_factory import get_creative_planner_provider

    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
    monkeypatch.setattr(settings, "AI_API_KEY", None)

    assert isinstance(get_creative_planner_provider(), MockLLMProvider)


def test_provider_factory_returns_openai_when_configured(monkeypatch):
    from app.core.config import settings
    from app.services.ai.openai_provider import OpenAICreativePlannerProvider
    from app.services.ai.provider_factory import get_creative_planner_provider

    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")

    assert isinstance(get_creative_planner_provider(), OpenAICreativePlannerProvider)


def test_missing_openai_key_raises_setup_error(monkeypatch):
    from app.core.config import settings
    from app.services.ai.provider_factory import get_creative_planner_provider
    from app.services.ai.schemas import AIProviderConfigurationError

    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "AI_API_KEY", None)

    with pytest.raises(AIProviderConfigurationError) as exc_info:
        get_creative_planner_provider()

    assert exc_info.value.code == "AI_PROVIDER_SETUP_REQUIRED"


def test_creative_plan_json_validation_accepts_phase1_shape():
    from app.services.ai.schemas import CreativePlan

    plan = CreativePlan.model_validate(
        {
            "hook": "Stop scrolling",
            "script": "A short script.",
            "scenes": [
                {
                    "index": 1,
                    "start_time": 0,
                    "end_time": 3,
                    "visual": "Product close-up",
                    "on_screen_text": "New",
                    "voiceover": "A short script.",
                }
            ],
            "voiceover_text": "A short script.",
            "subtitle_lines": [{"start_time": 0, "end_time": 3, "text": "A short script."}],
            "caption": "Caption",
            "hashtags": ["#reels"],
            "video_prompt": "Vertical product reel",
            "moderation_flags": [],
            "estimated_duration_seconds": 3,
        }
    )

    assert plan.scenes[0].scene_number == 1
    assert plan.subtitle_lines[0].start_seconds == 0


def test_invalid_creative_plan_fails_cleanly():
    from app.services.ai.schemas import CreativePlan

    with pytest.raises(ValidationError):
        CreativePlan.model_validate({"hook": "missing fields"})


@pytest.mark.asyncio
async def test_mock_generation_still_works():
    from app.services.ai.mock_provider import MockImageAnalysisProvider, MockLLMProvider
    from app.services.ai.schemas import ReelPlanInput

    image_analysis = await MockImageAnalysisProvider().analyze_image(None)
    plan = await MockLLMProvider().generate_reel_plan(
        ReelPlanInput(
            prompt="Make a reel for a coffee shop",
            image_analysis=image_analysis,
            language="en",
            tone="professional",
            duration_seconds=15,
            cta_text="Visit today",
        )
    )

    assert plan.hook
    assert plan.voiceover_text
    assert plan.subtitle_lines


@pytest.mark.asyncio
async def test_mock_tts_generation_creates_media_asset(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.models.models import MediaAssetType
    from app.services.ai.mock_provider import MockTTSProvider
    from app.services.reel_project import _generate_voiceover_asset

    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "TTS_VOICE", "mock")

    project = SimpleNamespace(id=uuid.uuid4(), workspace_id=uuid.uuid4())
    version = SimpleNamespace(id=uuid.uuid4())
    db = FakeAsyncDb()

    asset, duration = await _generate_voiceover_asset(
        db=db,
        project=project,
        version=version,
        text="This is a short voiceover.",
        provider=MockTTSProvider(),
        provider_name="mock",
    )

    assert asset.asset_type == MediaAssetType.AUDIO
    assert duration > 0
    assert Path(tmp_path, asset.s3_key).exists()


@pytest.mark.asyncio
async def test_render_resolves_voiceover_asset(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.render_service import _resolve_voiceover_audio_path

    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    audio_path = Path(tmp_path) / "voiceovers" / "test.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"wav")
    asset_id = uuid.uuid4()
    asset = SimpleNamespace(id=asset_id, s3_bucket="local", s3_key="voiceovers/test.wav")
    version = SimpleNamespace(voiceover_asset_id=asset_id, audio_asset_id=None)

    resolved = await _resolve_voiceover_audio_path(FakeAsyncDb(asset), version)

    assert resolved == audio_path


def test_provider_errors_do_not_expose_api_key():
    from app.services.ai.openai_provider import sanitize_provider_error

    message = sanitize_provider_error(RuntimeError("bad key sk-test-secret"))

    assert "sk-test-secret" not in message


@pytest.mark.asyncio
async def test_provider_pipeline_mock_success_marks_ready(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.models.models import GenerationJob, JobStatus, ReelProject, ReelProjectStatus, ReelVersion
    from app.services.reel_project import _run_provider_pipeline_with_db

    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
    monkeypatch.setattr(settings, "IMAGE_ANALYSIS_PROVIDER", "mock")
    monkeypatch.setattr(settings, "TTS_PROVIDER", "mock")
    monkeypatch.setattr(settings, "TTS_VOICE", "mock")

    project_id = uuid.uuid4()
    version_id = uuid.uuid4()
    job_id = uuid.uuid4()
    project = SimpleNamespace(
        id=project_id,
        workspace_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        prompt="Make a reel for a coffee shop",
        language="en",
        tone="professional",
        duration_seconds=15,
        cta_text="Visit today",
        source_image_id=None,
        status=ReelProjectStatus.DRAFT,
    )
    version = SimpleNamespace(
        id=version_id,
        project_id=project_id,
        status=ReelProjectStatus.DRAFT,
        edit_metadata=None,
        audio_asset_id=None,
        voiceover_asset_id=None,
    )
    job = SimpleNamespace(
        id=job_id,
        status=JobStatus.QUEUED,
        provider=None,
        provider_metadata_json=None,
        output_payload=None,
        error_code=None,
        error_message=None,
        completed_at=None,
    )
    db = _PipelineFakeDb({GenerationJob: job, ReelProject: project, ReelVersion: version})

    result = await _run_provider_pipeline_with_db(db, project_id, version_id, job_id)

    assert result is True
    assert job.status == JobStatus.COMPLETE
    assert project.status == ReelProjectStatus.READY_FOR_REVIEW
    assert version.status == ReelProjectStatus.READY_FOR_REVIEW
    assert version.script
    assert job.provider_metadata_json["ai_provider"] == "mock"
    assert job.output_payload["creative_plan"]
    assert db.commit_count >= 2


@pytest.mark.asyncio
async def test_provider_pipeline_failure_persists_safe_job_metadata(monkeypatch):
    from app.core.config import settings
    from app.models.models import GenerationJob, JobStatus, ReelProject, ReelProjectStatus, ReelVersion
    from app.services.ai.mock_provider import MockTTSProvider
    from app.services.ai.provider_factory import AIProviderBundle
    from app.services.reel_project import _run_provider_pipeline_with_db

    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
    monkeypatch.setattr(settings, "IMAGE_ANALYSIS_PROVIDER", "mock")
    monkeypatch.setattr(settings, "TTS_PROVIDER", "mock")

    def fake_bundle() -> AIProviderBundle:
        return AIProviderBundle(
            creative_planner=_FailingPlanner(),
            image_analysis=_ImmediateImageAnalysis(),
            tts=MockTTSProvider(),
            ai_provider="mock",
            image_analysis_provider="mock",
            tts_provider="mock",
        )

    provider_factory = __import__(
        "app.services.ai.provider_factory",
        fromlist=["get_provider_bundle"],
    )
    monkeypatch.setattr(provider_factory, "get_provider_bundle", fake_bundle)

    project_id = uuid.uuid4()
    version_id = uuid.uuid4()
    job_id = uuid.uuid4()
    project = SimpleNamespace(
        id=project_id,
        workspace_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        prompt="Make a reel for a coffee shop",
        language="en",
        tone="professional",
        duration_seconds=15,
        cta_text=None,
        source_image_id=None,
        status=ReelProjectStatus.DRAFT,
    )
    version = SimpleNamespace(id=version_id, status=ReelProjectStatus.DRAFT, edit_metadata=None)
    job = SimpleNamespace(
        id=job_id,
        status=JobStatus.QUEUED,
        provider=None,
        provider_metadata_json=None,
        output_payload=None,
        error_code=None,
        error_message=None,
        completed_at=None,
    )
    db = _PipelineFakeDb({GenerationJob: job, ReelProject: project, ReelVersion: version})

    result = await _run_provider_pipeline_with_db(db, project_id, version_id, job_id)

    assert result is False
    assert job.status == JobStatus.FAILED
    assert project.status == ReelProjectStatus.FAILED_SCRIPT
    assert version.status == ReelProjectStatus.FAILED_SCRIPT
    assert job.error_code == "AI_PROVIDER_ERROR"
    assert job.provider_metadata_json == {
        "provider": "mock",
        "error_code": "AI_PROVIDER_ERROR",
        "error_type": "RuntimeError",
        "error_message": "AI provider failed while generating the reel.",
    }
    assert "sk-test-secret" not in str(job.provider_metadata_json)


class _PipelineFakeDb:
    def __init__(self, records: dict[type, object]) -> None:
        self.records = records
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    async def get(self, model, _pk):
        return self.records.get(model)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


class _ImmediateImageAnalysis:
    async def analyze_image(self, _image_path_or_url):
        from app.services.ai.schemas import ImageAnalysisResult

        return ImageAnalysisResult()


class _FailingPlanner:
    async def generate_reel_plan(self, _data):
        raise RuntimeError("bad provider sk-test-secret")
