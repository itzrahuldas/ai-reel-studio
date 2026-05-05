"""
FFmpeg-based video renderer.

Produces a 1080x1920 (9:16) MP4 from:
- Source image (required)
- Audio file (optional — silent track if missing)
- Subtitle SRT file (optional)

Falls back to static image render if AI video provider is unavailable.
"""

import asyncio
import shutil
import time
from pathlib import Path
from typing import NamedTuple

import structlog

logger = structlog.get_logger(__name__)

FFMPEG_TIMEOUT_SECONDS = 600  # 10 minutes max render time
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OUTPUT_FPS = 30
OUTPUT_CRF = 23
OUTPUT_AUDIO_BITRATE = "192k"


class RenderParams(NamedTuple):
    image_path: Path
    output_path: Path
    thumbnail_path: Path
    duration_seconds: int
    audio_path: Path | None = None
    srt_path: Path | None = None
    cta_text: str | None = None


class RenderResult(NamedTuple):
    output_path: Path
    thumbnail_path: Path
    duration_seconds: int
    renderer: str
    metadata: dict


class FFmpegNotFoundError(RuntimeError):
    """Raised when FFmpeg is not installed."""


class FFmpegRenderError(RuntimeError):
    """Raised when FFmpeg exits with a non-zero return code."""


class FFmpegTimeoutError(RuntimeError):
    """Raised when FFmpeg exceeds the render timeout."""


class FFmpegRenderer:
    """
    Renders a vertical 9:16 MP4 using FFmpeg.

    Supports:
    - Static image with Ken Burns zoom/pan animation
    - Optional TTS audio track
    - Optional subtitle burn-in from SRT file
    - Thumbnail extraction at 1 second
    """

    def __init__(self) -> None:
        self._ffmpeg_path = shutil.which("ffmpeg")
        if not self._ffmpeg_path:
            logger.warning("ffmpeg_not_found", message="FFmpeg not found — using placeholder mode")

    @property
    def is_available(self) -> bool:
        return self._ffmpeg_path is not None

    async def render(self, params: RenderParams) -> RenderResult:
        """
        Render a vertical 9:16 MP4.
        Falls back to placeholder if FFmpeg is not available (local dev).
        """
        if not self.is_available:
            return self._placeholder_result(params)

        logger.info(
            "ffmpeg_render.start",
            image=str(params.image_path.name),
            duration=params.duration_seconds,
            has_audio=params.audio_path is not None,
            has_subtitles=params.srt_path is not None,
        )

        cmd = self._build_command(params)
        logger.debug("ffmpeg_render.command", cmd=" ".join(cmd))

        start_time = time.monotonic()
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=FFMPEG_TIMEOUT_SECONDS
            )
        except TimeoutError as exc:
            if proc:
                proc.kill()
            raise FFmpegTimeoutError(
                f"FFmpeg render exceeded {FFMPEG_TIMEOUT_SECONDS}s timeout"
            ) from exc

        elapsed = time.monotonic() - start_time

        if proc.returncode != 0:
            error_text = stderr.decode(errors="replace")
            logger.error(
                "ffmpeg_render.failed",
                returncode=proc.returncode,
                error=error_text[-500:],  # Last 500 chars of stderr
            )
            raise FFmpegRenderError(f"FFmpeg exited with code {proc.returncode}")

        if not params.output_path.exists() or params.output_path.stat().st_size == 0:
            raise FFmpegRenderError("FFmpeg completed but output file is missing or empty")

        logger.info(
            "ffmpeg_render.complete",
            elapsed_seconds=round(elapsed, 2),
            output_size_bytes=params.output_path.stat().st_size,
        )

        # Generate thumbnail
        await self._generate_thumbnail(params.output_path, params.thumbnail_path)

        metadata = {
            "renderer": "ffmpeg",
            "duration_seconds": params.duration_seconds,
            "width": OUTPUT_WIDTH,
            "height": OUTPUT_HEIGHT,
            "fps": OUTPUT_FPS,
            "has_audio": params.audio_path is not None,
            "has_subtitles": params.srt_path is not None,
            "render_time_seconds": round(elapsed, 2),
        }

        return RenderResult(
            output_path=params.output_path,
            thumbnail_path=params.thumbnail_path,
            duration_seconds=params.duration_seconds,
            renderer="ffmpeg",
            metadata=metadata,
        )

    def _build_command(self, params: RenderParams) -> list[str]:
        """Build the FFmpeg command list (no shell=True)."""
        total_frames = params.duration_seconds * OUTPUT_FPS
        cmd = [
            self._ffmpeg_path,
            "-y",  # Overwrite output without asking
            "-loop", "1",
            "-i", str(params.image_path),
        ]

        if params.audio_path and params.audio_path.exists():
            cmd += ["-i", str(params.audio_path)]

        # Video filter chain
        scale_crop = (
            f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=cover,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}"
        )
        ken_burns = (
            f"zoompan=z='min(zoom+0.0005,1.2)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps={OUTPUT_FPS}"
        )

        if params.srt_path and params.srt_path.exists():
            # Use absolute path — required by FFmpeg subtitle filter
            srt_abs = str(params.srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
            subtitle_filter = (
                f"subtitles='{srt_abs}':force_style="
                f"'FontName=DejaVu Sans,FontSize=42,"
                f"PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
                f"Outline=2,Alignment=2,MarginV=160'"
            )
            vf = f"{scale_crop},{ken_burns},{subtitle_filter}"
        else:
            vf = f"{scale_crop},{ken_burns}"

        cmd += ["-vf", vf]

        # Audio handling
        if params.audio_path and params.audio_path.exists():
            cmd += ["-map", "0:v", "-map", "1:a"]
            cmd += ["-c:a", "aac", "-b:a", OUTPUT_AUDIO_BITRATE, "-ar", "44100"]
        else:
            # Generate silent audio track
            cmd += [
                "-f", "lavfi",
                "-i", f"aevalsrc=0:c=stereo:s=44100:d={params.duration_seconds}",
                "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-b:a", "128k",
            ]

        cmd += [
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", str(OUTPUT_CRF),
            "-t", str(params.duration_seconds),
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            str(params.output_path),
        ]

        return cmd

    async def _generate_thumbnail(self, video_path: Path, thumbnail_path: Path) -> None:
        """Extract a thumbnail frame at 1 second."""
        if not self._ffmpeg_path:
            return
        cmd = [
            self._ffmpeg_path, "-y",
            "-i", str(video_path),
            "-ss", "00:00:01",
            "-vframes", "1",
            "-vf", f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}",
            "-q:v", "3",
            str(thumbnail_path),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)
        except Exception as e:
            logger.warning("ffmpeg_thumbnail.failed", error=str(e))

    def _placeholder_result(self, params: RenderParams) -> RenderResult:
        """Return a placeholder result when FFmpeg is not available (local dev)."""
        logger.warning(
            "ffmpeg_render.placeholder",
            message="FFmpeg not installed — returning placeholder result for local dev",
        )
        return RenderResult(
            output_path=params.output_path,
            thumbnail_path=params.thumbnail_path,
            duration_seconds=params.duration_seconds,
            renderer="placeholder",
            metadata={"renderer": "placeholder", "ffmpeg_available": False},
        )
