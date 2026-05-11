"""
FFmpeg-based video renderer.

Produces a 1080x1920 (9:16) MP4 from:
- Source image(s): one per storyboard scene, or a single fallback image
- Audio file (optional — silent track if missing)
- Subtitle SRT file (optional)

Falls back to static image render if AI video provider is unavailable.
Supports multi-scene slideshow when scene_image_paths is provided.
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
FFMPEG_STDERR_TAIL_CHARS = 2000


class RenderParams(NamedTuple):
    image_path: Path
    output_path: Path
    thumbnail_path: Path
    duration_seconds: int
    audio_path: Path | None = None
    srt_path: Path | None = None
    cta_text: str | None = None
    # When provided, renders a per-scene slideshow instead of a single Ken Burns loop.
    scene_image_paths: list[Path] | None = None


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

    def __init__(
        self,
        message: str,
        *,
        returncode: int | None = None,
        stderr_tail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr_tail = stderr_tail


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
        Uses multi-scene slideshow when params.scene_image_paths is set.
        """
        if not self.is_available:
            return self._placeholder_result(params)

        use_multi = bool(params.scene_image_paths and len(params.scene_image_paths) > 1)
        logger.info(
            "ffmpeg_render.start",
            image=str(params.image_path.name),
            duration=params.duration_seconds,
            has_audio=params.audio_path is not None,
            has_subtitles=params.srt_path is not None,
            multi_scene=use_multi,
            scene_count=len(params.scene_image_paths) if use_multi else 1,
        )

        cmd = (
            self._build_multi_scene_command(params)
            if use_multi
            else self._build_command(params)
        )
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
            error_text = _safe_stderr_tail(stderr)
            logger.error(
                "ffmpeg_render.failed",
                returncode=proc.returncode,
                output=str(params.output_path.name),
                stderr_tail=error_text,
            )
            raise FFmpegRenderError(
                f"FFmpeg exited with code {proc.returncode}",
                returncode=proc.returncode,
                stderr_tail=error_text,
            )

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
            "scene_count": len(params.scene_image_paths) if params.scene_image_paths else 1,
            "multi_scene": bool(params.scene_image_paths and len(params.scene_image_paths) > 1),
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
        else:
            cmd += [
                "-f", "lavfi",
                "-i", f"aevalsrc=0:c=stereo:s=44100:d={params.duration_seconds}",
            ]

        # Video filter chain
        scale_crop = (
            f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},setsar=1"
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

    def _build_multi_scene_command(self, params: RenderParams) -> list[str]:  # noqa: C901
        """
        Build an FFmpeg command for a multi-scene slideshow.

        Each scene image is shown for duration_seconds / n_scenes.
        Scenes are joined with a simple crossfade (xfade) filter.
        Subtitles are burned in on top of the final composited stream.
        """
        scene_paths = params.scene_image_paths or [params.image_path]
        n = len(scene_paths)
        duration_per_scene = max(1.0, params.duration_seconds / n)
        total_dur = params.duration_seconds

        cmd: list[str] = [self._ffmpeg_path, "-y"]

        # Input: one still image per scene (loop for duration_per_scene)
        for img_path in scene_paths:
            cmd += [
                "-loop", "1",
                "-t", str(duration_per_scene),
                "-i", str(img_path),
            ]

        # Audio input
        if params.audio_path and params.audio_path.exists():
            cmd += ["-i", str(params.audio_path)]
            audio_input_idx = n
        else:
            cmd += [
                "-f", "lavfi",
                "-i", f"aevalsrc=0:c=stereo:s=44100:d={total_dur}",
            ]
            audio_input_idx = n

        # Build scale+crop filter for each input, then xfade chain
        scale_crop = (
            f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},setsar=1,"
            f"fps={OUTPUT_FPS}"
        )

        filter_parts: list[str] = []
        # Scale all scenes
        for i in range(n):
            filter_parts.append(f"[{i}:v]{scale_crop}[v{i}]")

        # Chain xfade between consecutive scenes
        xfade_dur = min(0.4, duration_per_scene * 0.15)
        if n == 1:
            video_out = "[v0]"
        else:
            prev_label = "[v0]"
            for i in range(1, n):
                # offset = when the next scene should start
                offset = round(i * duration_per_scene - xfade_dur, 3)
                out_label = f"[xf{i}]" if i < n - 1 else "[vmerged]"
                filter_parts.append(
                    f"{prev_label}[v{i}]xfade=transition=fade:duration={xfade_dur}:offset={offset}{out_label}"
                )
                prev_label = out_label
            video_out = "[vmerged]"

        # Subtitle burn-in on the merged video
        if params.srt_path and params.srt_path.exists():
            srt_abs = str(params.srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
            sub_filter = (
                f"subtitles='{srt_abs}':force_style="
                f"'FontName=DejaVu Sans,FontSize=42,"
                f"PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
                f"Outline=2,Alignment=2,MarginV=160'"
            )
            filter_parts.append(f"{video_out}{sub_filter}[vout]")
            video_out = "[vout]"

        filter_complex = ";".join(filter_parts)
        cmd += ["-filter_complex", filter_complex]
        cmd += ["-map", video_out]
        cmd += ["-map", f"{audio_input_idx}:a"]

        if params.audio_path and params.audio_path.exists():
            cmd += ["-c:a", "aac", "-b:a", OUTPUT_AUDIO_BITRATE, "-ar", "44100"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "128k"]

        cmd += [
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", str(OUTPUT_CRF),
            "-t", str(total_dur),
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
        """Return a placeholder result when FFmpeg is not available (local dev).

        Note: mock visual scene images are still generated on disk so thumbnail
        preview can use the first scene image even without FFmpeg.
        """
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


def _safe_stderr_tail(stderr: bytes) -> str:
    """Decode and bound FFmpeg stderr for logs and database error context."""
    text = stderr.decode(errors="replace").replace("\x00", "")
    return text[-FFMPEG_STDERR_TAIL_CHARS:]
