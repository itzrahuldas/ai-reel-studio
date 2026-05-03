# Video Rendering — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-03

---

## 1. Target MP4 Format

| Property        | Value                        |
|-----------------|------------------------------|
| Container       | MP4                          |
| Video Codec     | H.264 (libx264)              |
| Audio Codec     | AAC                          |
| Resolution      | 1080 × 1920 (9:16 vertical)  |
| Frame Rate      | 30 FPS                       |
| Video Bitrate   | 4–6 Mbps (CRF 23)            |
| Audio Bitrate   | 192 kbps                     |
| Sample Rate     | 44100 Hz                     |
| Channels        | Stereo                       |
| Duration        | 15–90 seconds                |
| Max File Size   | ~1 GB (Instagram limit)      |

---

## 2. 9:16 Video Rules

- **Always** output 1080×1920 — never any other aspect ratio
- Source image must be padded/cropped to fill 9:16 (no black bars if possible)
- Use `scale=1080:1920:force_original_aspect_ratio=cover,crop=1080:1920` in FFmpeg
- Text overlays stay within the **safe zone**: 60px padding from all edges
- Subtitles positioned at 80% from top (bottom-center safe area)
- Logo/watermark (if any) in top-right corner, 40px from edges

---

## 3. FFmpeg Render Plan

### 3.1 Static Image Reel (Fallback)
```bash
ffmpeg \
  -loop 1 -i {source_image} \
  -i {audio_file} \
  -filter_complex "
    [0:v]scale=1080:1920:force_original_aspect_ratio=cover,
          crop=1080:1920,
          zoompan=z='min(zoom+0.001,1.3)':x='iw/2-(iw/zoom/2)':
                  y='ih/2-(ih/zoom/2)':d={fps*duration}:s=1080x1920:fps={fps}
          [vid];
    [vid]subtitles={srt_file}:force_style='FontName=Inter,
          FontSize=42,PrimaryColour=&HFFFFFF&,
          OutlineColour=&H000000&,Outline=2,
          Alignment=2,MarginV=160'[out]
  " \
  -map "[out]" -map 1:a \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 192k \
  -t {duration} \
  -movflags +faststart \
  -y {output_path}
```

### 3.2 AI Video + Audio Mix
```bash
ffmpeg \
  -i {ai_video_file} \
  -i {tts_audio_file} \
  -filter_complex "
    [0:v]scale=1080:1920:force_original_aspect_ratio=cover,
          crop=1080:1920[vid];
    [vid]subtitles={srt_file}:force_style='...'[vout];
    [0:a][1:a]amix=inputs=2:duration=shortest:weights=0.3 1[aout]
  " \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  -y {output_path}
```

---

## 4. Subtitle Burn-In Plan

1. Generate `.srt` file from `ReelVersion.subtitle_lines`
2. Pass to FFmpeg via `subtitles=` filter
3. Style: white text, black outline, centered, bottom safe zone
4. Font: Inter (must be installed in Docker image or use fallback)
5. Font size: 42px at 1080×1920
6. Subtitle file path must use absolute paths (FFmpeg requirement)

```
subtitle_lines → subtitles.py → render.srt → FFmpeg subtitles filter → burned into MP4
```

---

## 5. Audio Mixing Plan

If both TTS audio and background music are present:
- TTS (voiceover): weight 1.0 (primary)
- Background music: weight 0.15–0.3 (ambient)
- Use `amix` filter with duration=shortest

If only TTS audio:
- Map directly, no mixing required

If no audio:
- Generate silent audio track: `aevalsrc=0:c=stereo:s=44100`

---

## 6. Thumbnail Generation Plan

After rendering, generate a thumbnail:
```bash
ffmpeg -i {rendered_mp4} -ss 00:00:01 -vframes 1 \
  -vf "scale=1080:1920" {thumbnail_path}
```

- Thumbnail = frame at 1 second (avoids black frame at 0s)
- Saved as JPEG, quality 85
- Stored as MediaAsset (type: thumbnail)

---

## 7. Failure Handling

| Failure                      | Action                                           |
|------------------------------|--------------------------------------------------|
| FFmpeg not found             | Return FAILED_RENDER with clear install message  |
| Source image invalid/corrupt | Return FAILED_RENDER, prompt user to re-upload   |
| Audio file missing           | Render without audio (silent reel)               |
| SRT file malformed           | Render without subtitles, log warning            |
| Output write failed          | Return FAILED_RENDER, check disk space           |
| FFmpeg command timeout       | Kill process after 10 minutes, mark FAILED_RENDER|
| Output file too large        | Re-encode with higher CRF (lower quality), retry |

```python
class FFmpegRenderer:
    TIMEOUT_SECONDS = 600  # 10 minutes max render time
    
    async def render(self, params: RenderParams) -> RenderResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.TIMEOUT_SECONDS
            )
            if proc.returncode != 0:
                raise FFmpegRenderError(stderr.decode())
            return RenderResult(output_path=output_path, ...)
        except asyncio.TimeoutError:
            proc.kill()
            raise FFmpegTimeoutError(f"Render exceeded {self.TIMEOUT_SECONDS}s")
```

---

## 8. Local Dev Without FFmpeg

If FFmpeg is not installed locally:
1. `FFmpegRenderer` detects absence via `shutil.which("ffmpeg")`
2. Returns a pre-baked placeholder video (bundled in repo at `tests/fixtures/placeholder_reel.mp4`)
3. Logs `WARNING: FFmpeg not found — using placeholder video for local dev`
4. In Docker Compose, FFmpeg is always available via `ffmpeg` apt package in `worker` image
