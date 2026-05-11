# Video Rendering — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-10

---

## Mock Visual Storyboard Renderer (AI_PROVIDER=mock)

When `AI_PROVIDER=mock` (local development default), the render pipeline
generates **prompt-specific storyboard scene card images** rather than a
generic black-screen placeholder.

### How it works

1. `render_service.py` detects `source_image_id is None` (no uploaded image).
2. Calls `generate_mock_storyboard()` in `apps/api/app/services/rendering/mock_visuals.py`.
3. Detects the prompt's **theme** from keyword matching:
   - `coffee` (café, iced coffee, espresso)
   - `fitness` (gym, workout, challenge, transformation)
   - `travel` (beach, Bali, vacation, destination)
   - `beauty` (skincare, glow, serum, cosmetic)
   - `tech` (app, SaaS, platform, startup)
   - `education` (course, learn, workshop, skill)
   - `realestate` (home, interior, property, design)
   - `finance` (invest, business, wealth, growth)
   - `generic` (fallback)
4. Generates one **1080×1920 JPEG scene card** per storyboard scene using **Pillow**:
   - Theme-coloured vertical gradient background
   - Accent shapes unique per scene (corner brackets, band, circle)
   - Scene number, role tag (HOOK / SHOWCASE / CTA / …)
   - Prompt-derived headline + visual description text
   - On-screen text / CTA if set
   - Keyword strip from the prompt at the bottom
5. Scene images are stored internally at:
   ```text
   LOCAL_STORAGE_PATH/mock_visuals/<project_id>/<version_id>/scene_001.jpg
   ```
   Local paths are **never exposed** in the public API.
6. `FFmpegRenderer` receives `scene_image_paths` and builds an FFmpeg
   **xfade crossfade slideshow** from all scene images instead of
   a single looped Ken Burns image.

### Mock render metadata exposed in API response

```json
{
  "visual_source": "mock_storyboard",
  "mock_visual_theme": "coffee",
  "generated_scene_count": 3
}
```

### Limitations

- Mock visuals are **designed storyboard cards**, not real AI-generated images or video.
- Real photorealistic/generated visuals require a future visual AI provider integration.
- Mock TTS remains a silent placeholder unless `TTS_PROVIDER=openai` is configured.
- Font fallback: if DejaVu Sans is not installed in the container, Pillow's built-in
  default bitmap font is used (smaller). DejaVu is available in the worker Docker image.

---

## Phase 1 Voiceover Integration

Real AI Provider Phase 1 can create a TTS voiceover asset during generation.
When `reel_versions.voiceover_asset_id` exists, render jobs resolve the audio
media asset and pass it into `FFmpegRenderer`. If no voiceover exists, rendering
keeps the existing silent-audio fallback.

Subtitles are still burned into the MP4 from `reel_versions.subtitle_lines`.
When voiceover duration is available, subtitle timings are proportionally
aligned to that duration before the version is marked ready for review.

In `TTS_PROVIDER=mock` mode, the voiceover asset is a valid playable silent
placeholder for local testing. Real spoken narration requires
`TTS_PROVIDER=openai` plus valid server-side `AI_API_KEY` and TTS settings.

## Local Media Preview

Rendered videos, thumbnails, and voiceovers are served to the web app through
public media URLs derived from `STORAGE_PUBLIC_BASE_URL`. In local staging this
should resolve to:

```text
http://localhost:8000/static/<asset-key>
```

The frontend should use media URLs returned by the API, not raw storage paths.
Local filesystem paths such as `/var/lib/...` or `C:\...` must never be exposed
to the browser.

Troubleshooting:

```bash
curl -I http://localhost:8000/static/<asset-key>
ffprobe <media-file>
```

On the Reel Detail page, use the "Open video in new tab" link to verify the
exact URL the browser is loading.

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
- Use `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1` in FFmpeg
- Text overlays stay within the **safe zone**: 60px padding from all edges
- Subtitles positioned at 80% from top (bottom-center safe area)
- Logo/watermark (if any) in top-right corner, 40px from edges

---

## 3. FFmpeg Render Plan

### 3.1 Mock Storyboard Multi-Scene Slideshow (new default for AI_PROVIDER=mock)
```bash
ffmpeg -y \
  -loop 1 -t {scene_dur} -i scene_001.jpg \
  -loop 1 -t {scene_dur} -i scene_002.jpg \
  -loop 1 -t {scene_dur} -i scene_003.jpg \
  -f lavfi -i "aevalsrc=0:c=stereo:s=44100:d={total_dur}" \
  -filter_complex "
    [0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[v0];
    [1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[v1];
    [2:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[v2];
    [v0][v1]xfade=transition=fade:duration=0.4:offset=3.6[xf1];
    [xf1][v2]xfade=transition=fade:duration=0.4:offset=7.6[vmerged];
    [vmerged]subtitles='...':force_style='...'[vout]
  " \
  -map "[vout]" -map "3:a" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  -t {total_dur} -movflags +faststart -pix_fmt yuv420p \
  output.mp4
```

### 3.2 Static Image Reel (Fallback with source image)
```bash
ffmpeg \
  -loop 1 -i {source_image} \
  -i {audio_file} \
  -filter_complex "
    [0:v]scale=1080:1920:force_original_aspect_ratio=increase,
          crop=1080:1920,
          setsar=1,
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
- **Fallback (FFmpeg unavailable):** first mock visual scene card image is copied as the thumbnail

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
| Pillow import error          | Fall back to solid-color placeholder image       |

---

## 8. Local Dev Without FFmpeg

If FFmpeg is not installed locally:
1. `FFmpegRenderer` detects absence via `shutil.which("ffmpeg")`
2. Mock visual scene images are still generated by Pillow
3. The first scene image is used as the thumbnail
4. Returns a placeholder render result with `renderer="placeholder"`
5. In Docker Compose, FFmpeg is always available via `ffmpeg` apt package in `worker` image
