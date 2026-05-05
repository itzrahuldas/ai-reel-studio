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
