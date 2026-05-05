"""Abstract base classes for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.services.ai.schemas import (
    CreativePlan,
    ImageAnalysisResult,
    ModerationFlags,
    ReelPlanInput,
    SceneItem,
    SubtitleLine,
    TTSResult,
    TTSVoiceoverResult,
    VideoGenerationResult,
)


class ImageAnalysisProvider(ABC):
    """Analyzes uploaded images to extract context for reel generation."""

    @abstractmethod
    async def analyze_image(self, image_path_or_url: str | None) -> ImageAnalysisResult:
        """Analyze an image from a local path or URL."""
        ...

    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> ImageAnalysisResult:
        """Legacy byte-oriented analysis entry point."""
        del image_bytes, mime_type
        return await self.analyze_image(None)


class CreativePlannerProvider(ABC):
    """Generates a structured creative plan for a Reel."""

    @abstractmethod
    async def generate_reel_plan(self, data: ReelPlanInput) -> CreativePlan:
        """Generate a full creative plan for a reel."""
        ...


class LLMProvider(CreativePlannerProvider):
    """Legacy LLM provider interface kept for compatibility."""

    async def generate_creative_plan(
        self,
        prompt: str,
        context: dict[str, object],
    ) -> CreativePlan:
        image_analysis = context.get("image_analysis")
        plan_input = ReelPlanInput(
            prompt=prompt,
            image_analysis=(
                image_analysis
                if isinstance(image_analysis, ImageAnalysisResult)
                else ImageAnalysisResult()
            ),
            language=str(context.get("language") or "en"),
            tone=str(context.get("tone")) if context.get("tone") is not None else None,
            duration_seconds=int(context.get("duration") or context.get("duration_seconds") or 15),
            cta_text=str(context.get("cta")) if context.get("cta") is not None else None,
        )
        return await self.generate_reel_plan(plan_input)

    @abstractmethod
    async def regenerate_caption(
        self,
        script: str,
        tone: str,
        cta: str | None,
        feedback: str | None,
    ) -> tuple[str, list[str]]:
        """Regenerate caption and hashtags for an existing script."""
        ...


class VideoGenerationProvider(ABC):
    """Generates AI video from a prompt and reference image."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        reference_image_url: str,
        duration_seconds: int,
    ) -> VideoGenerationResult:
        ...

    @abstractmethod
    async def check_status(self, generation_id: str) -> VideoGenerationResult:
        """Poll the status of a generation job."""
        ...


class TTSProvider(ABC):
    """Text-to-speech provider for voiceover generation."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: str = "en",
        voice_id: str | None = None,
        speaking_rate: float = 1.0,
    ) -> TTSResult:
        ...

    async def generate_voiceover(
        self,
        text: str,
        voice: str | None,
        output_path: str,
    ) -> TTSVoiceoverResult:
        """Generate voiceover directly to a path when providers support it."""
        result = await self.synthesize(text=text, voice_id=voice)
        Path(output_path).write_bytes(result.audio_bytes)
        return TTSVoiceoverResult(
            audio_path=output_path,
            duration_seconds=result.duration_seconds,
            provider="mock",
            format=result.format,
        )


class SubtitleTimingProvider(ABC):
    """Optional provider for subtitle timing refinement."""

    @abstractmethod
    async def refine_timings(
        self,
        subtitle_lines: list[SubtitleLine],
        audio_duration_seconds: float,
    ) -> list[SubtitleLine]:
        ...


__all__ = [
    "CreativePlan",
    "CreativePlannerProvider",
    "ImageAnalysisProvider",
    "ImageAnalysisResult",
    "LLMProvider",
    "ModerationFlags",
    "ReelPlanInput",
    "SceneItem",
    "SubtitleLine",
    "SubtitleTimingProvider",
    "TTSProvider",
    "TTSResult",
    "TTSVoiceoverResult",
    "VideoGenerationProvider",
    "VideoGenerationResult",
]
