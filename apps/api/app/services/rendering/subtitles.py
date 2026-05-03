"""
Subtitle utilities — converts ReelVersion.subtitle_lines to SRT format.
"""

from pathlib import Path

from app.services.ai.base import SubtitleLine


def seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def subtitle_lines_to_srt(subtitle_lines: list[SubtitleLine]) -> str:
    """Convert a list of SubtitleLine objects to SRT format string."""
    lines = []
    for i, line in enumerate(subtitle_lines, start=1):
        start = seconds_to_srt_timestamp(line.start_seconds)
        end = seconds_to_srt_timestamp(line.end_seconds)
        lines.append(f"{i}\n{start} --> {end}\n{line.text}\n")
    return "\n".join(lines)


def write_srt_file(subtitle_lines: list[SubtitleLine], output_path: Path) -> Path:
    """Write subtitle lines to an SRT file and return the path."""
    srt_content = subtitle_lines_to_srt(subtitle_lines)
    output_path.write_text(srt_content, encoding="utf-8")
    return output_path
