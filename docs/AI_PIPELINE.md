# AI Pipeline — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-05

---

## Phase 1 Real Provider Update

The generation pipeline now supports provider-selected creative planning, image
analysis, TTS voiceover generation, and timed subtitle alignment.

Provider modes are selected independently:

- `AI_PROVIDER=mock|openai`
- `IMAGE_ANALYSIS_PROVIDER=mock|openai`
- `TTS_PROVIDER=mock|openai`

Mock remains the default and does not call external APIs. OpenAI mode uses the
server-only `AI_API_KEY`; missing keys return a setup error before usage is
consumed.

`TTS_PROVIDER=mock` writes a valid silent placeholder audio file so local render
and preview flows can be tested without paid provider credentials. It is not
expected to produce spoken narration. Real spoken voice requires
`TTS_PROVIDER=openai` with valid `AI_API_KEY` and TTS configuration.

Runtime flow:

1. Usage is validated with the existing job idempotency key.
2. The uploaded source image is resolved from `media_assets`.
3. The image analysis provider returns safe visual context.
4. The creative planner returns a Pydantic-validated JSON creative plan.
5. TTS writes voiceover audio to local/S3-compatible media storage and creates
   an `audio` media asset.
6. Subtitle timings are generated or aligned to the voiceover duration.
7. `reel_versions`, `generation_jobs.output_payload`, and
   `generation_jobs.provider_metadata_json` store safe provider metadata.
8. The project/version moves to `READY_FOR_REVIEW`.

Phase 1 intentionally does not implement real AI video generation. FFmpeg still
renders from the source image, storyboard text, subtitles, and optional
voiceover audio.

## 1. Prompt-to-Storyboard Pipeline

```
Input: { prompt, image_s3_key, language, tone, duration_seconds, cta_text }

Step 1: Image Analysis
  → ImageAnalysisProvider.analyze(image_bytes)
  → Output: { description, dominant_colors, detected_objects, scene_type }

Step 2: Build Planning Prompt
  → Load packages/prompts/reel_planner.md
  → Inject: prompt, image_analysis, language, tone, duration_seconds, cta_text
  → Build full prompt string

Step 3: LLM Generation
  → LLMProvider.generate(planning_prompt)
  → Enforce JSON output mode

Step 4: Output Validation
  → Parse JSON against CreativePlanSchema (Pydantic)
  → Validate required fields present
  → Validate scene count matches duration
  → Validate subtitle timing

Step 5: Moderation Check
  → Check moderation_flags field from LLM output
  → If harmful/violating content detected → reject + log
  → Write moderation result to GenerationJob

Step 6: Persist
  → Create ReelVersion with all plan fields
  → Update GenerationJob status
```

---

## 2. LLM Output Schema

The LLM **must** output valid JSON matching this schema:

```json
{
  "hook": "string — opening line (max 100 chars)",
  "script": "string — full narration script",
  "scenes": [
    {
      "scene_number": 1,
      "duration_seconds": 5,
      "visual_description": "Close-up of golden sourdough loaf on wooden board",
      "text_overlay": "Fresh. Artisan. Daily.",
      "transition": "fade"
    }
  ],
  "voiceover_text": "string — clean TTS input (no markdown)",
  "subtitle_lines": [
    {
      "start_seconds": 0.0,
      "end_seconds": 3.0,
      "text": "Fresh from the oven every morning"
    }
  ],
  "caption": "string — Instagram caption (max 2200 chars)",
  "hashtags": ["#sourdough", "#artisanbakery"],
  "video_prompt": "string — prompt for AI video generation",
  "moderation_flags": {
    "contains_harmful_content": false,
    "contains_misleading_claims": false,
    "contains_restricted_categories": false,
    "notes": ""
  },
  "estimated_duration_seconds": 30
}
```

---

## 3. Image Analysis Step

```python
class ImageAnalysisProvider(ABC):
    @abstractmethod
    async def analyze(self, image_bytes: bytes) -> ImageAnalysisResult:
        pass

class ImageAnalysisResult(BaseModel):
    description: str
    dominant_colors: list[str]
    detected_objects: list[str]
    scene_type: str  # "product", "lifestyle", "event", "portrait", "landscape"
    brand_elements: list[str]
    mood: str
```

**Providers:**
- `GeminiVisionProvider` — uses Gemini 1.5 Pro Vision
- `OpenAIVisionProvider` — uses GPT-4o Vision
- `MockImageAnalysisProvider` — for local dev/testing

---

## 4. Script Generation

The planning prompt includes:
- User's original business idea/prompt
- Image analysis results
- Target language and tone
- Duration constraints
- CTA text

The LLM generates a complete creative plan. Prompt template: `packages/prompts/reel_planner.md`

---

## 5. Caption & Hashtag Generation

Caption and hashtags are generated as part of the main planning step (same LLM call). They can also be regenerated independently:

```python
async def regenerate_caption(version_id: str, feedback: str | None):
    → load existing version data
    → load packages/prompts/caption_generator.md
    → inject: script, tone, cta_text, feedback
    → LLMProvider.generate(caption_prompt)
    → validate output
    → update ReelVersion.caption, hashtags
```

---

## 6. Video Provider Adapter

```python
class VideoGenerationProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        reference_image_url: str,
        duration_seconds: int,
    ) -> VideoGenerationResult:
        pass

class VideoGenerationResult(BaseModel):
    video_url: str
    status: str  # "complete" | "failed"
    generation_id: str
    duration_seconds: int

# Implementations:
# - RunwayMLProvider
# - LumaLabsProvider  
# - StabilityAIProvider
# - MockVideoProvider (returns pre-baked test video)
```

---

## 7. TTS Adapter

```python
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: str,
        voice_id: str | None = None,
        speaking_rate: float = 1.0,
    ) -> TTSResult:
        pass

class TTSResult(BaseModel):
    audio_bytes: bytes
    duration_seconds: float
    format: str  # "mp3"

# Implementations:
# - ElevenLabsProvider
# - OpenAITTSProvider (tts-1 / tts-1-hd)
# - GoogleCloudTTSProvider
# - MockTTSProvider
```

Local preview uses the media URL returned by the API, built from
`STORAGE_PUBLIC_BASE_URL` and the media asset `s3_key`. For local staging,
verify audio reachability with:

```bash
curl -I http://localhost:8000/static/<asset-key>
ffprobe <media-file>
```

---

## 8. Subtitle Generation

Subtitle timing is generated by the LLM during planning. If timing needs refinement:

```python
def align_subtitles(subtitle_lines: list[SubtitleLine], audio_duration: float):
    → proportionally distribute timing if total > audio_duration
    → output SRT-formatted subtitle file
    → save as assets/subtitles.srt
```

---

## 9. Moderation & Safety Checks

Every LLM output is checked for:
- `contains_harmful_content` — explicit violence, adult content
- `contains_misleading_claims` — false medical/financial claims
- `contains_restricted_categories` — weapons, illegal substances

If any flag is `true`:
1. Generation marked `FAILED_SCRIPT` with reason
2. AuditLog written with moderation result
3. User shown: "Content moderation flag raised — please revise your prompt"

Additional checks:
- User-uploaded image passed through content moderation API before processing
- Caption checked against Instagram Community Guidelines patterns

---

## 10. Fallback Rendering Strategy

If AI video provider fails or is not configured:

```
1. Log warning: "AI video provider unavailable — using FFmpeg static render"
2. Skip generate_video_task
3. Proceed directly to render_reel_task
4. FFmpegRenderer.render_static_image_reel(
     image_path, audio_path, subtitle_lines, duration
   )
5. Output: Ken Burns zoom + pan on static image + audio + subtitle burn-in
6. Upload rendered MP4 to S3
7. Mark as render_type: "ffmpeg_fallback" in RenderJob
```

This ensures a working video is always produced, even without AI video credits.

---

## 11. Retry & Fallback Rules

| Failure Point         | Retry          | Fallback                         |
|-----------------------|----------------|----------------------------------|
| LLM generation fails  | 3× with delay  | Return FAILED_SCRIPT to user     |
| Image analysis fails  | 2× with delay  | Skip image context, use prompt only |
| TTS fails             | 3× with delay  | Return silent video (no audio)   |
| AI video fails        | 2× with delay  | FFmpeg fallback renderer         |
| FFmpeg render fails   | 1× with delay  | Return FAILED_RENDER to user     |
