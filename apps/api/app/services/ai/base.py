"""
Abstract base classes for all AI providers.
Every provider must implement these interfaces.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

# ── Image Analysis ────────────────────────────────────────────────────────────

class ImageAnalysisResult(BaseModel):
    description: str
    dominant_colors: list[str] = []
    detected_objects: list[str] = []
    scene_type: str = "product"
    brand_elements: list[str] = []
    mood: str = "neutral"


class ImageAnalysisProvider(ABC):
    """Analyzes an uploaded image to extract context for reel generation."""

    @abstractmethod
    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ImageAnalysisResult:
        """Analyze image and return structured description."""
        ...


# ── LLM (Creative Plan Generation) ───────────────────────────────────────────

class SceneItem(BaseModel):
    scene_number: int
    duration_seconds: int
    visual_description: str
    text_overlay: str | None = None
    transition: str = "cut"


class SubtitleLine(BaseModel):
    start_seconds: float
    end_seconds: float
    text: str


class ModerationFlags(BaseModel):
    contains_harmful_content: bool = False
    contains_misleading_claims: bool = False
    contains_restricted_categories: bool = False
    notes: str = ""


class CreativePlan(BaseModel):
    """Validated output schema for LLM creative plan generation."""
    hook: str
    script: str
    scenes: list[SceneItem]
    voiceover_text: str
    subtitle_lines: list[SubtitleLine]
    caption: str
    hashtags: list[str]
    video_prompt: str
    moderation_flags: ModerationFlags
    estimated_duration_seconds: int


class LLMProvider(ABC):
    """Generates creative plans, captions, and scripts via LLM."""

    @abstractmethod
    async def generate_creative_plan(self, prompt: str, context: dict[str, Any]) -> CreativePlan:
        """Generate a full creative plan for a reel."""
        ...

    @abstractmethod
    async def regenerate_caption(self, script: str, tone: str, cta: str | None, feedback: str | None) -> tuple[str, list[str]]:
        """Regenerate caption and hashtags for an existing script."""
        ...


# ── Video Generation ──────────────────────────────────────────────────────────

class VideoGenerationResult(BaseModel):
    video_url: str
    status: str  # "complete" | "failed"
    generation_id: str
    duration_seconds: int


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


# ── TTS ───────────────────────────────────────────────────────────────────────

class TTSResult(BaseModel):
    audio_bytes: bytes
    duration_seconds: float
    format: str = "mp3"


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
