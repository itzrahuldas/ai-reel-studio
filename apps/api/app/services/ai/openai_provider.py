"""OpenAI-backed AI providers for creative planning, vision, and TTS."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

import structlog
from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import ValidationError

from app.core.config import settings
from app.services.ai.base import ImageAnalysisProvider, LLMProvider, TTSProvider, TTSResult
from app.services.ai.schemas import (
    AIProviderConfigurationError,
    AIProviderRuntimeError,
    CreativePlan,
    ImageAnalysisResult,
    ReelPlanInput,
    TTSVoiceoverResult,
)

logger = structlog.get_logger(__name__)

DEFAULT_AI_MODEL = "gpt-4.1-mini"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "coral"


def sanitize_provider_error(exc: Exception) -> str:
    """Return a safe error message that never includes API keys or raw prompts."""
    if isinstance(exc, AIProviderConfigurationError):
        return str(exc)
    if isinstance(exc, (APITimeoutError, TimeoutError)):
        return "AI provider timed out. Please try again."
    if isinstance(exc, RateLimitError):
        return "AI provider rate limit reached. Please try again later."
    if isinstance(exc, APIConnectionError):
        return "AI provider connection failed. Please try again."
    if isinstance(exc, APIError):
        return "AI provider request failed."
    if isinstance(exc, ValidationError):
        return "AI provider returned invalid structured output."
    return "AI provider failed while generating the reel."


def _require_api_key() -> str:
    if not settings.AI_API_KEY:
        raise AIProviderConfigurationError(
            "OpenAI provider is selected but AI_API_KEY is not configured.",
            code="AI_PROVIDER_SETUP_REQUIRED",
        )
    return settings.AI_API_KEY


def _load_prompt_template(filename: str) -> str:
    repo_root = Path(__file__).resolve().parents[5]
    prompt_path = repo_root / "packages" / "prompts" / filename
    if not prompt_path.exists():
        return ""
    return prompt_path.read_text(encoding="utf-8")


def _json_schema_format(
    schema_model: type[CreativePlan] | type[ImageAnalysisResult],
    name: str,
) -> dict[str, object]:
    return {
        "type": "json_schema",
        "name": name,
        "schema": schema_model.model_json_schema(),
        "strict": False,
    }


class _OpenAIBase:
    def __init__(self) -> None:
        api_key = _require_api_key()
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )

    @staticmethod
    def _model(value: str | None, default: str) -> str:
        return value.strip() if value and value.strip() else default


class OpenAICreativePlannerProvider(_OpenAIBase, LLMProvider):
    """Generates Reel creative plans using OpenAI structured outputs."""

    async def generate_reel_plan(self, data: ReelPlanInput) -> CreativePlan:
        model = self._model(settings.AI_MODEL, DEFAULT_AI_MODEL)
        prompt_template = _load_prompt_template("reel_planner.md")
        system_prompt = (
            prompt_template
            or "You are an expert Instagram Reel producer. Return JSON only."
        )
        user_payload = {
            "prompt": data.prompt,
            "image_analysis": data.image_analysis.model_dump(mode="json"),
            "language": data.language,
            "tone": data.tone,
            "duration_seconds": data.duration_seconds,
            "cta_text": data.cta_text,
            "brand_inputs": data.brand_inputs,
        }
        try:
            response = await self.client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Create an Instagram Reels creative plan from this JSON input:\n"
                            f"{json.dumps(user_payload, ensure_ascii=False)}"
                        ),
                    },
                ],
                temperature=settings.AI_GENERATION_TEMPERATURE,
                text_format=CreativePlan,
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                output_text = getattr(response, "output_text", "")
                parsed = CreativePlan.model_validate_json(output_text)
            return CreativePlan.model_validate(parsed)
        except TypeError:
            return await self._generate_reel_plan_with_json_schema(
                model,
                system_prompt,
                user_payload,
            )
        except Exception as exc:
            logger.warning(
                "openai.creative_plan.failed",
                error_type=type(exc).__name__,
                provider="openai",
            )
            raise AIProviderRuntimeError(sanitize_provider_error(exc)) from exc

    async def _generate_reel_plan_with_json_schema(
        self,
        model: str,
        system_prompt: str,
        user_payload: dict[str, object],
    ) -> CreativePlan:
        try:
            response = await self.client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Return JSON matching the CreativePlan schema for this input:\n"
                            f"{json.dumps(user_payload, ensure_ascii=False)}"
                        ),
                    },
                ],
                temperature=settings.AI_GENERATION_TEMPERATURE,
                text={"format": _json_schema_format(CreativePlan, "creative_plan")},
            )
            return CreativePlan.model_validate_json(response.output_text)
        except Exception as exc:
            logger.warning(
                "openai.creative_plan_json_schema.failed",
                error_type=type(exc).__name__,
                provider="openai",
            )
            raise AIProviderRuntimeError(sanitize_provider_error(exc)) from exc

    async def regenerate_caption(
        self,
        script: str,
        tone: str,
        cta: str | None,
        feedback: str | None,
    ) -> tuple[str, list[str]]:
        del feedback
        tone_note = f" Tone: {tone}." if tone else ""
        fallback_caption = f"{script[:120]}...\n\n{cta or 'Follow for more'}{tone_note}"
        return fallback_caption, ["#reels", "#instagram", "#content"]


class OpenAIImageAnalysisProvider(_OpenAIBase, ImageAnalysisProvider):
    """Analyzes source images using OpenAI vision models."""

    async def analyze_image(self, image_path_or_url: str | None) -> ImageAnalysisResult:
        if not image_path_or_url:
            return ImageAnalysisResult()

        model = self._model(
            settings.IMAGE_ANALYSIS_MODEL,
            self._model(settings.AI_MODEL, DEFAULT_AI_MODEL),
        )
        prompt_template = _load_prompt_template("image_analysis.md")
        image_url = self._as_image_url(image_path_or_url)
        try:
            response = await self.client.responses.parse(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": prompt_template or "Analyze this image for safe Reel planning.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Return structured image analysis for Instagram Reel planning."
                                ),
                            },
                            {"type": "input_image", "image_url": image_url, "detail": "low"},
                        ],
                    },
                ],
                text_format=ImageAnalysisResult,
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                parsed = ImageAnalysisResult.model_validate_json(response.output_text)
            return ImageAnalysisResult.model_validate(parsed)
        except TypeError:
            return await self._analyze_image_with_json_schema(model, prompt_template, image_url)
        except Exception as exc:
            logger.warning(
                "openai.image_analysis.failed",
                error_type=type(exc).__name__,
                provider="openai",
            )
            raise AIProviderRuntimeError(sanitize_provider_error(exc)) from exc

    async def _analyze_image_with_json_schema(
        self,
        model: str,
        prompt_template: str,
        image_url: str,
    ) -> ImageAnalysisResult:
        try:
            response = await self.client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": prompt_template or "Analyze this image for safe Reel planning.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Return structured image analysis JSON.",
                            },
                            {"type": "input_image", "image_url": image_url, "detail": "low"},
                        ],
                    },
                ],
                text={"format": _json_schema_format(ImageAnalysisResult, "image_analysis")},
            )
            return ImageAnalysisResult.model_validate_json(response.output_text)
        except Exception as exc:
            logger.warning(
                "openai.image_analysis_json_schema.failed",
                error_type=type(exc).__name__,
                provider="openai",
            )
            raise AIProviderRuntimeError(sanitize_provider_error(exc)) from exc

    @staticmethod
    def _as_image_url(image_path_or_url: str) -> str:
        if image_path_or_url.startswith(("http://", "https://", "data:")):
            return image_path_or_url

        image_path = Path(image_path_or_url)
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"


class OpenAITTSProvider(_OpenAIBase, TTSProvider):
    """Generates MP3 voiceover files through OpenAI TTS."""

    async def synthesize(
        self,
        text: str,
        language: str = "en",
        voice_id: str | None = None,
        speaking_rate: float = 1.0,
    ) -> TTSResult:
        del language, speaking_rate
        output_path = Path(settings.LOCAL_STORAGE_PATH) / "voiceovers" / "preview_openai_tts.mp3"
        result = await self.generate_voiceover(text, voice_id, str(output_path))
        return TTSResult(
            audio_bytes=output_path.read_bytes(),
            duration_seconds=result.duration_seconds,
            format=result.format,
        )

    async def generate_voiceover(
        self,
        text: str,
        voice: str | None,
        output_path: str,
    ) -> TTSVoiceoverResult:
        model = self._model(settings.TTS_MODEL, DEFAULT_TTS_MODEL)
        selected_voice = self._model(voice or settings.TTS_VOICE, DEFAULT_TTS_VOICE)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with self.client.audio.speech.with_streaming_response.create(
                model=model,
                voice=selected_voice,
                input=text,
                instructions="Speak clearly for a short Instagram Reel voiceover.",
            ) as response:
                await response.stream_to_file(path)
            return TTSVoiceoverResult(
                audio_path=str(path),
                duration_seconds=max(1.0, len(text.split()) / 2.5),
                provider="openai",
                format="mp3",
            )
        except Exception as exc:
            logger.warning(
                "openai.tts.failed",
                error_type=type(exc).__name__,
                provider="openai",
            )
            raise AIProviderRuntimeError(sanitize_provider_error(exc), code="TTS_FAILED") from exc
