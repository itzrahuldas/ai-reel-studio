# ADR-0003: Video Provider Abstraction

**Status:** Accepted
**Date:** 2026-05-03
**Deciders:** System Architect, AI Pipeline Engineer, Video Rendering Engineer

---

## Context

AI video generation is an emerging market with rapidly changing providers (Runway, Luma, Stability, Kling, etc.). Pricing, quality, and availability vary significantly. We cannot depend on a single provider.

Additionally, for local development and testing, we need a zero-cost fallback that produces valid output.

## Decision

**Implement a provider-abstraction pattern for all AI services:**

```python
class VideoGenerationProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, image_url: str, duration: int) -> VideoGenerationResult:
        ...
```

**And implement FFmpeg as a mandatory local fallback renderer.**

The FFmpeg renderer:
- Takes the source image + TTS audio + subtitle lines
- Produces a Ken Burns-animated 9:16 MP4
- Requires no external API calls
- Always available in the Docker worker image

## Provider Selection at Runtime

```
VIDEO_PROVIDER=runway  → RunwayMLProvider
VIDEO_PROVIDER=luma    → LumaLabsProvider
VIDEO_PROVIDER=none    → skip AI video, use FFmpeg renderer directly
VIDEO_PROVIDER=mock    → MockVideoProvider (returns test fixture)
```

## Consequences

**Positive:**
- Can swap video providers without touching core logic
- Production works without AI video credits (FFmpeg fallback)
- Easy to add new providers as market evolves
- Testing does not require expensive API calls (mock provider)

**Negative:**
- Abstraction adds indirection (mitigated by clear interface)
- FFmpeg fallback quality lower than AI-generated video
- Provider API differences require per-provider adapters

## Same Pattern Applied To

- LLM providers (OpenAI/Gemini/Anthropic/Mock)
- Image analysis providers (GPT-4o Vision/Gemini Vision/Mock)
- TTS providers (ElevenLabs/OpenAI TTS/Google TTS/Mock)
- Storage providers (S3/Local filesystem)
