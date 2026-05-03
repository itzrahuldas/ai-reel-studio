"""
Mock AI providers for local development and testing.
All mock providers return realistic-looking fixture data
without making any external API calls.
"""

import asyncio
from typing import Any

from app.services.ai.base import (
    CreativePlan,
    ImageAnalysisProvider,
    ImageAnalysisResult,
    LLMProvider,
    ModerationFlags,
    SceneItem,
    SubtitleLine,
    TTSProvider,
    TTSResult,
    VideoGenerationProvider,
    VideoGenerationResult,
)


class MockImageAnalysisProvider(ImageAnalysisProvider):
    """Returns fixture image analysis data instantly."""

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ImageAnalysisResult:
        await asyncio.sleep(0.1)  # Simulate latency
        return ImageAnalysisResult(
            description="A vibrant product shot showing the subject in good lighting with a clean background.",
            dominant_colors=["#F4A261", "#2A9D8F", "#264653"],
            detected_objects=["product", "background", "table"],
            scene_type="product",
            brand_elements=["logo area", "brand colors"],
            mood="energetic",
        )


class MockLLMProvider(LLMProvider):
    """Returns fixture creative plan data instantly."""

    async def generate_creative_plan(self, prompt: str, context: dict[str, Any]) -> CreativePlan:
        await asyncio.sleep(0.2)  # Simulate latency
        return CreativePlan(
            hook="Wait until you see this! 🤩",
            script=(
                "Are you ready to transform your everyday experience? "
                "We've got something incredible for you. "
                "This is exactly what you've been waiting for. "
                "Don't miss out — grab yours today!"
            ),
            scenes=[
                SceneItem(
                    scene_number=1,
                    duration_seconds=5,
                    visual_description="Product close-up with dynamic lighting",
                    text_overlay="Game Changer.",
                    transition="fade",
                ),
                SceneItem(
                    scene_number=2,
                    duration_seconds=8,
                    visual_description="Lifestyle shot showing product in use",
                    text_overlay="Made for YOU.",
                    transition="slide",
                ),
                SceneItem(
                    scene_number=3,
                    duration_seconds=7,
                    visual_description="Brand logo with CTA overlay",
                    text_overlay="Get Yours Now →",
                    transition="zoom",
                ),
            ],
            voiceover_text=(
                "Are you ready to transform your everyday experience? "
                "We've got something incredible for you. "
                "This is exactly what you've been waiting for. "
                "Don't miss out — grab yours today!"
            ),
            subtitle_lines=[
                SubtitleLine(start_seconds=0.0, end_seconds=3.0, text="Are you ready to transform your experience?"),
                SubtitleLine(start_seconds=3.0, end_seconds=8.0, text="We've got something incredible for you."),
                SubtitleLine(start_seconds=8.0, end_seconds=13.0, text="This is exactly what you've been waiting for."),
                SubtitleLine(start_seconds=13.0, end_seconds=18.0, text="Don't miss out — grab yours today!"),
            ],
            caption=(
                f"✨ Transform your life with something incredible.\n\n"
                f"{prompt[:100]}...\n\n"
                "Drop a 🔥 if you want one!\n\n"
                "Link in bio 👆"
            ),
            hashtags=[
                "#newproduct", "#musthave", "#trending", "#viral",
                "#lifestyle", "#innovation", "#todaysfind", "#reels",
            ],
            video_prompt=(
                f"Cinematic vertical video showcasing: {prompt[:200]}. "
                "Vibrant colors, dynamic camera movement, professional lighting."
            ),
            moderation_flags=ModerationFlags(
                contains_harmful_content=False,
                contains_misleading_claims=False,
                contains_restricted_categories=False,
                notes="",
            ),
            estimated_duration_seconds=20,
        )

    async def regenerate_caption(
        self, script: str, tone: str, cta: str | None, feedback: str | None
    ) -> tuple[str, list[str]]:
        await asyncio.sleep(0.1)
        return (
            f"✨ {script[:80]}...\n\nLink in bio 👆",
            ["#newpost", "#trending", "#viral", "#reels"],
        )


class MockVideoGenerationProvider(VideoGenerationProvider):
    """Returns a placeholder generation result without calling any API."""

    async def generate(
        self,
        prompt: str,
        reference_image_url: str,
        duration_seconds: int,
    ) -> VideoGenerationResult:
        await asyncio.sleep(0.1)
        return VideoGenerationResult(
            video_url="",
            status="skipped",
            generation_id="mock-gen-001",
            duration_seconds=duration_seconds,
        )

    async def check_status(self, generation_id: str) -> VideoGenerationResult:
        return VideoGenerationResult(
            video_url="",
            status="skipped",
            generation_id=generation_id,
            duration_seconds=30,
        )


class MockTTSProvider(TTSProvider):
    """Returns silent audio bytes without calling any API."""

    async def synthesize(
        self,
        text: str,
        language: str = "en",
        voice_id: str | None = None,
        speaking_rate: float = 1.0,
    ) -> TTSResult:
        await asyncio.sleep(0.1)
        # Return minimal valid MP3 header bytes (silent)
        silent_mp3 = bytes([
            0xFF, 0xFB, 0x90, 0x00,  # MP3 header
            *([0x00] * 413),          # Silent frame
        ])
        return TTSResult(
            audio_bytes=silent_mp3,
            duration_seconds=float(len(text.split()) / 2.5),  # ~2.5 words/sec estimate
            format="mp3",
        )
