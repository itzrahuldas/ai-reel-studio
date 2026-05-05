"""Shared schemas and helpers for AI provider integrations."""

from __future__ import annotations

import enum
import math
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator


class ProviderMode(enum.StrEnum):
    MOCK = "mock"
    OPENAI = "openai"


class AIProviderConfigurationError(RuntimeError):
    """Raised when a selected AI provider is not configured for runtime use."""

    def __init__(self, message: str, code: str = "AI_PROVIDER_SETUP_REQUIRED") -> None:
        super().__init__(message)
        self.code = code


class AIProviderRuntimeError(RuntimeError):
    """Raised for sanitized provider execution errors."""

    def __init__(self, message: str, code: str = "AI_PROVIDER_ERROR") -> None:
        super().__init__(message)
        self.code = code


class ImageAnalysisResult(BaseModel):
    """Structured visual context returned by image analysis providers."""

    description: str = "No reference image was provided."
    objects: list[str] = Field(default_factory=list)
    style: str = "neutral"
    brand_safety_notes: list[str] = Field(default_factory=list)
    recommended_visual_direction: str = "Use the prompt as the primary visual direction."

    # Backwards-compatible fields used by the original mock pipeline/docs.
    dominant_colors: list[str] = Field(default_factory=list)
    detected_objects: list[str] = Field(default_factory=list)
    scene_type: str = "product"
    brand_elements: list[str] = Field(default_factory=list)
    mood: str = "neutral"

    @model_validator(mode="after")
    def normalize_legacy_fields(self) -> Self:
        if not self.objects and self.detected_objects:
            self.objects = list(self.detected_objects)
        if not self.detected_objects and self.objects:
            self.detected_objects = list(self.objects)
        if self.style == "neutral" and self.mood != "neutral":
            self.style = self.mood
        if self.mood == "neutral" and self.style != "neutral":
            self.mood = self.style
        if not self.recommended_visual_direction:
            self.recommended_visual_direction = self.description
        return self


class SceneItem(BaseModel):
    """Scene schema that accepts both legacy and Phase 1 field names."""

    index: int | None = None
    start_time: float | None = None
    end_time: float | None = None
    visual: str | None = None
    on_screen_text: str | None = None
    voiceover: str | None = None

    # Legacy editor/render fields.
    scene_number: int | None = None
    duration_seconds: int | None = None
    visual_description: str | None = None
    text_overlay: str | None = None
    transition: str = "cut"

    @model_validator(mode="after")
    def normalize_scene_fields(self) -> Self:
        scene_index = self.index or self.scene_number or 1
        self.index = scene_index
        self.scene_number = scene_index

        if self.start_time is None:
            duration = self.duration_seconds or 3
            self.start_time = float(max(scene_index - 1, 0) * duration)
        if self.end_time is None:
            self.end_time = self.start_time + float(self.duration_seconds or 3)

        duration_seconds = max(1, int(math.ceil(self.end_time - self.start_time)))
        self.duration_seconds = self.duration_seconds or duration_seconds

        visual = self.visual or self.visual_description or "Scene visual direction."
        self.visual = visual
        self.visual_description = visual

        on_screen_text = self.on_screen_text or self.text_overlay
        self.on_screen_text = on_screen_text
        self.text_overlay = on_screen_text
        return self


class SubtitleLine(BaseModel):
    """Timed subtitle line supporting both old and new key names."""

    start_time: float | None = None
    end_time: float | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    text: str

    @model_validator(mode="after")
    def normalize_subtitle_fields(self) -> Self:
        start = self.start_time if self.start_time is not None else self.start_seconds
        end = self.end_time if self.end_time is not None else self.end_seconds
        self.start_time = float(start or 0.0)
        self.start_seconds = self.start_time
        self.end_time = float(end if end is not None else self.start_time + 2.5)
        self.end_seconds = self.end_time
        return self


class ModerationFlags(BaseModel):
    contains_harmful_content: bool = False
    contains_misleading_claims: bool = False
    contains_restricted_categories: bool = False
    notes: str = ""


class CreativePlan(BaseModel):
    """Validated output schema for provider creative planning."""

    hook: str
    script: str
    scenes: list[SceneItem]
    voiceover_text: str
    subtitle_lines: list[SubtitleLine]
    caption: str
    hashtags: list[str]
    video_prompt: str
    moderation_flags: ModerationFlags = Field(default_factory=ModerationFlags)
    estimated_duration_seconds: int

    @field_validator("moderation_flags", mode="before")
    @classmethod
    def normalize_moderation_flags(cls, value: object) -> object:
        if isinstance(value, list):
            return {
                "contains_harmful_content": False,
                "contains_misleading_claims": False,
                "contains_restricted_categories": False,
                "notes": ", ".join(str(item) for item in value),
            }
        return value

    @model_validator(mode="after")
    def validate_duration_and_subtitles(self) -> Self:
        self.estimated_duration_seconds = max(1, int(self.estimated_duration_seconds))
        if not self.subtitle_lines:
            self.subtitle_lines = build_subtitle_lines_from_text(
                self.voiceover_text,
                float(self.estimated_duration_seconds),
            )
        else:
            self.subtitle_lines = align_subtitle_lines(
                self.subtitle_lines,
                float(self.estimated_duration_seconds),
            )
        return self


class ReelPlanInput(BaseModel):
    prompt: str
    image_analysis: ImageAnalysisResult
    language: str = "en"
    tone: str | None = None
    duration_seconds: int = 15
    cta_text: str | None = None
    brand_inputs: dict[str, str] = Field(default_factory=dict)


class TTSVoiceoverResult(BaseModel):
    audio_asset_id: str | None = None
    audio_path: str
    duration_seconds: float
    provider: str
    format: str = "wav"
    warning: str | None = None


class TTSResult(BaseModel):
    audio_bytes: bytes
    duration_seconds: float
    format: str = "wav"


class VideoGenerationResult(BaseModel):
    video_url: str
    status: str
    generation_id: str
    duration_seconds: int


def build_subtitle_lines_from_text(text: str, duration_seconds: float) -> list[SubtitleLine]:
    """Build simple timed subtitle lines from text when a provider omits timings."""
    words = [word for word in text.split() if word.strip()]
    if not words:
        return []

    target_lines = max(1, min(6, math.ceil(duration_seconds / 3.0)))
    words_per_line = max(1, math.ceil(len(words) / target_lines))
    lines: list[SubtitleLine] = []
    start = 0.0
    line_duration = duration_seconds / target_lines

    for index in range(target_lines):
        chunk = words[index * words_per_line : (index + 1) * words_per_line]
        if not chunk:
            break
        end = duration_seconds if index == target_lines - 1 else start + line_duration
        lines.append(SubtitleLine(start_seconds=start, end_seconds=end, text=" ".join(chunk)))
        start = end

    return lines


def align_subtitle_lines(
    subtitle_lines: list[SubtitleLine],
    duration_seconds: float,
) -> list[SubtitleLine]:
    """Scale subtitle timing to fit a known audio or target duration."""
    if not subtitle_lines or duration_seconds <= 0:
        return subtitle_lines

    normalized = [SubtitleLine.model_validate(line.model_dump()) for line in subtitle_lines]
    current_end = max((line.end_seconds or 0.0) for line in normalized)
    if current_end <= 0:
        return build_subtitle_lines_from_text(
            " ".join(line.text for line in normalized),
            duration_seconds,
        )

    scale = duration_seconds / current_end
    if 0.95 <= scale <= 1.05:
        return normalized

    aligned: list[SubtitleLine] = []
    for line in normalized:
        start = max(0.0, (line.start_seconds or 0.0) * scale)
        end = min(duration_seconds, max(start + 0.4, (line.end_seconds or 0.0) * scale))
        aligned.append(
            SubtitleLine(
                start_seconds=round(start, 2),
                end_seconds=round(end, 2),
                text=line.text,
            )
        )
    return aligned
