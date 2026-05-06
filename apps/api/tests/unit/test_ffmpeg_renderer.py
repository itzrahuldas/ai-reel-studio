import os
from pathlib import Path

os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ffmpeg-renderer-tests")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "a" * 64)

from app.services.rendering.ffmpeg_renderer import (  # noqa: E402
    OUTPUT_HEIGHT,
    OUTPUT_WIDTH,
    FFmpegRenderer,
    RenderParams,
    _safe_stderr_tail,
)


def _renderer_with_fake_binary() -> FFmpegRenderer:
    renderer = FFmpegRenderer()
    renderer._ffmpeg_path = "ffmpeg"
    return renderer


def _video_filter(command: list[str]) -> str:
    return command[command.index("-vf") + 1]


def test_ffmpeg_cover_filter_uses_valid_scale_crop_chain(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    output_path = tmp_path / "out.mp4"
    thumbnail_path = tmp_path / "thumb.jpg"
    image_path.write_bytes(b"png")

    command = _renderer_with_fake_binary()._build_command(
        RenderParams(
            image_path=image_path,
            output_path=output_path,
            thumbnail_path=thumbnail_path,
            duration_seconds=3,
        )
    )
    vf = _video_filter(command)

    assert "force_original_aspect_ratio=cover" not in vf
    assert f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase" in vf
    assert f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}" in vf
    assert "setsar=1" in vf
    assert f"s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}" in vf


def test_ffmpeg_command_keeps_audio_and_subtitle_graph_valid(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    audio_path = tmp_path / "voiceover.wav"
    srt_path = tmp_path / "subs.srt"
    output_path = tmp_path / "out.mp4"
    thumbnail_path = tmp_path / "thumb.jpg"
    image_path.write_bytes(b"png")
    audio_path.write_bytes(b"wav")
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    command = _renderer_with_fake_binary()._build_command(
        RenderParams(
            image_path=image_path,
            output_path=output_path,
            thumbnail_path=thumbnail_path,
            duration_seconds=5,
            audio_path=audio_path,
            srt_path=srt_path,
        )
    )
    vf = _video_filter(command)

    assert "subtitles=" in vf
    assert "zoompan=" in vf
    assert command[command.index("-map") + 1] == "0:v"
    assert command[command.index("-map") + 3] == "1:a"
    assert str(audio_path) in command
    assert str(output_path) == command[-1]


def test_ffmpeg_silent_audio_input_is_declared_before_filter_options(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    output_path = tmp_path / "out.mp4"
    thumbnail_path = tmp_path / "thumb.jpg"
    image_path.write_bytes(b"png")

    command = _renderer_with_fake_binary()._build_command(
        RenderParams(
            image_path=image_path,
            output_path=output_path,
            thumbnail_path=thumbnail_path,
            duration_seconds=4,
        )
    )

    assert command.index("-i", 6) < command.index("-vf")
    assert "aevalsrc=0:c=stereo:s=44100:d=4" in command


def test_ffmpeg_stderr_tail_is_bounded_and_text_safe() -> None:
    stderr = ("a" * 2500 + "\x00Undefined constant cover").encode()

    tail = _safe_stderr_tail(stderr)

    assert "\x00" not in tail
    assert len(tail) == 2000
    assert tail.endswith("Undefined constant cover")
