"""Provider factory for AI Reel Studio Phase 1 AI integrations."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.services.ai.base import CreativePlannerProvider, ImageAnalysisProvider, TTSProvider
from app.services.ai.mock_provider import (
    MockImageAnalysisProvider,
    MockLLMProvider,
    MockTTSProvider,
)
from app.services.ai.schemas import AIProviderConfigurationError, ProviderMode


@dataclass(frozen=True)
class AIProviderBundle:
    creative_planner: CreativePlannerProvider
    image_analysis: ImageAnalysisProvider
    tts: TTSProvider
    ai_provider: str
    image_analysis_provider: str
    tts_provider: str


def normalize_provider(value: str | None) -> str:
    return (value or ProviderMode.MOCK.value).strip().lower()


def _validate_supported(provider_name: str, selected: str) -> None:
    if selected not in {ProviderMode.MOCK.value, ProviderMode.OPENAI.value}:
        raise AIProviderConfigurationError(
            f"{provider_name}={selected} is not supported in Phase 1. Use mock or openai.",
            code="AI_PROVIDER_UNSUPPORTED",
        )


def _requires_openai_key(*provider_values: str) -> bool:
    return any(value == ProviderMode.OPENAI.value for value in provider_values)


def validate_provider_configuration() -> None:
    ai_provider = normalize_provider(settings.AI_PROVIDER)
    image_provider = normalize_provider(settings.IMAGE_ANALYSIS_PROVIDER)
    tts_provider = normalize_provider(settings.TTS_PROVIDER)

    _validate_supported("AI_PROVIDER", ai_provider)
    _validate_supported("IMAGE_ANALYSIS_PROVIDER", image_provider)
    _validate_supported("TTS_PROVIDER", tts_provider)

    if _requires_openai_key(ai_provider, image_provider, tts_provider) and not settings.AI_API_KEY:
        raise AIProviderConfigurationError(
            "OpenAI provider is selected but AI_API_KEY is not configured.",
            code="AI_PROVIDER_SETUP_REQUIRED",
        )


def get_creative_planner_provider() -> CreativePlannerProvider:
    selected = normalize_provider(settings.AI_PROVIDER)
    _validate_supported("AI_PROVIDER", selected)
    if selected == ProviderMode.OPENAI.value:
        if not settings.AI_API_KEY:
            raise AIProviderConfigurationError(
                "OpenAI creative planning requires AI_API_KEY.",
                code="AI_PROVIDER_SETUP_REQUIRED",
            )
        from app.services.ai.openai_provider import OpenAICreativePlannerProvider

        return OpenAICreativePlannerProvider()
    return MockLLMProvider()


def get_image_analysis_provider() -> ImageAnalysisProvider:
    selected = normalize_provider(settings.IMAGE_ANALYSIS_PROVIDER)
    _validate_supported("IMAGE_ANALYSIS_PROVIDER", selected)
    if selected == ProviderMode.OPENAI.value:
        if not settings.AI_API_KEY:
            raise AIProviderConfigurationError(
                "OpenAI image analysis requires AI_API_KEY.",
                code="AI_PROVIDER_SETUP_REQUIRED",
            )
        from app.services.ai.openai_provider import OpenAIImageAnalysisProvider

        return OpenAIImageAnalysisProvider()
    return MockImageAnalysisProvider()


def get_tts_provider() -> TTSProvider:
    selected = normalize_provider(settings.TTS_PROVIDER)
    _validate_supported("TTS_PROVIDER", selected)
    if selected == ProviderMode.OPENAI.value:
        if not settings.AI_API_KEY:
            raise AIProviderConfigurationError(
                "OpenAI TTS requires AI_API_KEY.",
                code="AI_PROVIDER_SETUP_REQUIRED",
            )
        from app.services.ai.openai_provider import OpenAITTSProvider

        return OpenAITTSProvider()
    return MockTTSProvider()


def get_provider_bundle() -> AIProviderBundle:
    validate_provider_configuration()
    return AIProviderBundle(
        creative_planner=get_creative_planner_provider(),
        image_analysis=get_image_analysis_provider(),
        tts=get_tts_provider(),
        ai_provider=normalize_provider(settings.AI_PROVIDER),
        image_analysis_provider=normalize_provider(settings.IMAGE_ANALYSIS_PROVIDER),
        tts_provider=normalize_provider(settings.TTS_PROVIDER),
    )


def get_provider_status() -> dict[str, object]:
    ai_provider = normalize_provider(settings.AI_PROVIDER)
    image_provider = normalize_provider(settings.IMAGE_ANALYSIS_PROVIDER)
    tts_provider = normalize_provider(settings.TTS_PROVIDER)
    setup_warning = None
    supported = True
    configured = True

    try:
        validate_provider_configuration()
    except AIProviderConfigurationError as exc:
        configured = False
        supported = exc.code != "AI_PROVIDER_UNSUPPORTED"
        setup_warning = str(exc)

    return {
        "ai_provider": ai_provider,
        "image_analysis_provider": image_provider,
        "tts_provider": tts_provider,
        "ai_model": settings.AI_MODEL or None,
        "image_analysis_model": settings.IMAGE_ANALYSIS_MODEL or None,
        "tts_model": settings.TTS_MODEL or None,
        "tts_voice": settings.TTS_VOICE or None,
        "configured": configured,
        "supported": supported,
        "setup_warning": setup_warning,
        "mock_mode": (
            ai_provider == ProviderMode.MOCK.value
            and image_provider == ProviderMode.MOCK.value
            and tts_provider == ProviderMode.MOCK.value
        ),
    }
