"""
Mock AI providers for local development and testing.
All mock providers return realistic-looking fixture data
without making any external API calls.
"""

import asyncio
import io
import wave
from pathlib import Path

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
    TTSVoiceoverResult,
    VideoGenerationProvider,
    VideoGenerationResult,
)
from app.services.ai.schemas import ReelPlanInput, align_subtitle_lines


class MockImageAnalysisProvider(ImageAnalysisProvider):
    """Returns fixture image analysis data instantly."""

    async def analyze_image(self, image_path_or_url: str | None) -> ImageAnalysisResult:
        await asyncio.sleep(0.1)  # Simulate latency
        suffix = f" Reference: {Path(image_path_or_url).name}." if image_path_or_url else ""
        return ImageAnalysisResult(
            description=(
                "A vibrant product shot showing the subject in good lighting with a clean "
                f"background.{suffix}"
            ),
            objects=["product", "background", "table"],
            style="energetic product photography",
            brand_safety_notes=[],
            recommended_visual_direction=(
                "Use clean product framing, close-ups, and quick movement around the key "
                "visual details."
            ),
            dominant_colors=["#F4A261", "#2A9D8F", "#264653"],
            detected_objects=["product", "background", "table"],
            scene_type="product",
            brand_elements=["logo area", "brand colors"],
            mood="energetic",
        )

    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> ImageAnalysisResult:
        del image_bytes, mime_type
        return await self.analyze_image(None)


class MockLLMProvider(LLMProvider):
    """Returns fixture creative plan data instantly."""

    async def generate_reel_plan(self, data: ReelPlanInput) -> CreativePlan:
        await asyncio.sleep(0.2)  # Simulate latency
        duration = max(10, data.duration_seconds)
        tone = data.tone or "professional"
        cta = data.cta_text or "Follow for more"
        first_scene_end = round(duration * 0.3, 2)
        second_scene_end = round(duration * 0.7, 2)
        return CreativePlan(
            hook="Wait until you see this!",
            script=(
                "Are you ready to transform your everyday experience? "
                "We've got something incredible for you. "
                "This is exactly what you've been waiting for. "
                f"{cta}."
            ),
            scenes=[
                SceneItem(
                    index=1,
                    start_time=0,
                    end_time=first_scene_end,
                    visual=(
                        f"{data.image_analysis.recommended_visual_direction} "
                        "Start with a product close-up."
                    ),
                    on_screen_text="Game Changer.",
                    voiceover="Are you ready to transform your everyday experience?",
                    transition="fade",
                ),
                SceneItem(
                    index=2,
                    start_time=first_scene_end,
                    end_time=second_scene_end,
                    visual="Lifestyle shot showing the offer in use.",
                    on_screen_text="Made for YOU.",
                    voiceover="We've got something incredible for you.",
                    transition="slide",
                ),
                SceneItem(
                    index=3,
                    start_time=second_scene_end,
                    end_time=float(duration),
                    visual="Brand logo with CTA overlay.",
                    on_screen_text=cta,
                    voiceover=cta,
                    transition="zoom",
                ),
            ],
            voiceover_text=(
                "Are you ready to transform your everyday experience? "
                "We've got something incredible for you. "
                "This is exactly what you've been waiting for. "
                f"{cta}."
            ),
            subtitle_lines=[
                SubtitleLine(
                    start_seconds=0.0,
                    end_seconds=3.0,
                    text="Are you ready to transform your experience?",
                ),
                SubtitleLine(
                    start_seconds=3.0,
                    end_seconds=8.0,
                    text="We've got something incredible for you.",
                ),
                SubtitleLine(
                    start_seconds=8.0,
                    end_seconds=13.0,
                    text="This is exactly what you've been waiting for.",
                ),
                SubtitleLine(start_seconds=13.0, end_seconds=float(duration), text=cta),
            ],
            caption=(
                "Transform your life with something incredible.\n\n"
                f"{data.prompt[:100]}...\n\n"
                f"{cta}"
            ),
            hashtags=[
                "#newproduct",
                "#musthave",
                "#trending",
                "#viral",
                "#lifestyle",
                "#innovation",
                "#todaysfind",
                "#reels",
            ],
            video_prompt=(
                f"Cinematic vertical video showcasing: {data.prompt[:200]}. "
                f"Tone: {tone}. Vibrant colors, dynamic camera movement, professional lighting."
            ),
            moderation_flags=ModerationFlags(
                contains_harmful_content=False,
                contains_misleading_claims=False,
                contains_restricted_categories=False,
                notes="",
            ),
            estimated_duration_seconds=duration,
        )

    async def generate_creative_plan(
        self,
        prompt: str,
        context: dict[str, object],
    ) -> CreativePlan:
        plan = await super().generate_creative_plan(prompt, context)
        plan.subtitle_lines = align_subtitle_lines(
            plan.subtitle_lines,
            float(plan.estimated_duration_seconds),
        )
        return plan

    async def regenerate_caption(
        self, script: str, tone: str, cta: str | None, feedback: str | None
    ) -> tuple[str, list[str]]:
        del tone, cta, feedback
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
        del prompt, reference_image_url
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
    """Returns valid silent WAV audio bytes without calling any API."""

    async def synthesize(
        self,
        text: str,
        language: str = "en",
        voice_id: str | None = None,
        speaking_rate: float = 1.0,
    ) -> TTSResult:
        del language, voice_id, speaking_rate
        await asyncio.sleep(0.1)
        duration = max(1.0, float(len(text.split()) / 2.5))
        sample_rate = 44_100
        sample_count = int(sample_rate * duration)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * sample_count)
        return TTSResult(
            audio_bytes=buffer.getvalue(),
            duration_seconds=duration,
            format="wav",
        )

    async def generate_voiceover(
        self,
        text: str,
        voice: str | None,
        output_path: str,
    ) -> TTSVoiceoverResult:
        result = await self.synthesize(text=text, voice_id=voice)
        Path(output_path).write_bytes(result.audio_bytes)
        return TTSVoiceoverResult(
            audio_path=output_path,
            duration_seconds=result.duration_seconds,
            provider="mock",
            format=result.format,
        )
