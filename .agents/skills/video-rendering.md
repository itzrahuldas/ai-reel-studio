# Skill: Video Rendering

## FFmpeg Rules
- Validate FFmpeg installed: shutil.which('ffmpeg') before any render
- All FFmpeg subprocess calls use syncio.create_subprocess_exec (not shell=True)
- Timeout every render: syncio.wait_for(..., timeout=600)
- Log sanitized command (no secrets, no full paths to sensitive files)
- Validate output file exists and is non-zero size after render

## Video Output Rules
- Always output 1080x1920 (9:16 vertical) — never other aspect ratios
- Codec: H.264 (libx264), preset=fast, crf=23
- Audio: AAC, 192kbps, 44100Hz stereo
- Container: MP4 with faststart (-movflags +faststart)
- Frame rate: 30 FPS

## Subtitle Rules
- Generate .srt file before rendering
- Use absolute paths for subtitle files in FFmpeg command
- Font: Inter (bundled in Docker image), fallback: DejaVu Sans
- Style: white text, black outline (Outline=2), bottom-center, 160px margin
- Font size: 42px at 1080x1920

## Audio Mixing Rules
- TTS voiceover: primary track (weight 1.0)
- Background music (optional): ambient track (weight 0.2)
- Mix with mix=inputs=2:duration=shortest
- If no audio: generate silent track with evalsrc=0

## Local Fallback Render Rules
- If VIDEO_PROVIDER=none or video provider fails: use FFmpeg directly
- Use Ken Burns zoom/pan on static image: zoompan=z='min(zoom+0.001,1.3)'
- Must produce a valid MP4 even with only image input (no audio fallback)
- Document fallback in RenderJob.renderer = 'ffmpeg_fallback'
