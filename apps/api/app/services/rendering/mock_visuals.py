"""
Mock visual storyboard scene generator.

Generates prompt-specific 1080x1920 vertical scene card images for local
development. Every render produces visually different scenes that reflect
the prompt/theme — never the same generic placeholder.

Visual assets are stored at:
  LOCAL_STORAGE_PATH/mock_visuals/<project_id>/<version_id>/scene_NNN.jpg

Internal filesystem paths are NEVER returned in public API responses.

Requirements: Pillow (already available via Docker image).
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# ── Canvas constants ────────────────────────────────────────────────────────────
WIDTH = 1080
HEIGHT = 1920
SAFE_MARGIN = 80  # px from edge — keeps text inside Instagram safe zone


# ── Theme definitions ──────────────────────────────────────────────────────────

@dataclass
class ThemeSpec:
    name: str
    keywords: list[str]
    # Two-colour radial gradient (top → bottom)
    bg_top: tuple[int, int, int]
    bg_bottom: tuple[int, int, int]
    accent: tuple[int, int, int]          # accent shape colour
    text_primary: tuple[int, int, int]    # main text
    text_secondary: tuple[int, int, int]  # sub-text
    motif: str                            # short label / icon-label
    headline_prefix: list[str] = field(default_factory=list)

    def keyword_match_score(self, prompt_lower: str) -> int:
        """Return number of keyword matches in prompt."""
        return sum(1 for kw in self.keywords if kw in prompt_lower)


_THEMES: list[ThemeSpec] = [
    ThemeSpec(
        name="coffee",
        keywords=["coffee", "cafe", "caramel", "espresso", "latte", "cappuccino", "brew", "roast", "iced coffee"],
        bg_top=(40, 22, 10),
        bg_bottom=(100, 50, 20),
        accent=(210, 140, 50),
        text_primary=(255, 245, 220),
        text_secondary=(210, 170, 110),
        motif="☕ CAFE",
        headline_prefix=["Sip the", "Taste the", "Experience", "Introducing"],
    ),
    ThemeSpec(
        name="fitness",
        keywords=["gym", "fitness", "workout", "training", "challenge", "transformation", "muscle", "athlete", "health", "run", "cardio"],
        bg_top=(12, 8, 30),
        bg_bottom=(30, 10, 60),
        accent=(200, 50, 255),
        text_primary=(240, 220, 255),
        text_secondary=(180, 130, 220),
        motif="⚡ FITNESS",
        headline_prefix=["Train", "Transform", "Unleash", "Push Beyond"],
    ),
    ThemeSpec(
        name="travel",
        keywords=["travel", "beach", "bali", "vacation", "trip", "destination", "mountain", "adventure", "explore", "getaway", "tourism"],
        bg_top=(5, 30, 60),
        bg_bottom=(10, 80, 120),
        accent=(0, 200, 220),
        text_primary=(220, 245, 255),
        text_secondary=(140, 210, 230),
        motif="✈ TRAVEL",
        headline_prefix=["Escape to", "Discover", "Explore", "Journey to"],
    ),
    ThemeSpec(
        name="beauty",
        keywords=["skincare", "beauty", "glow", "serum", "makeup", "cosmetic", "fashion", "luxury", "radiant", "skin", "moisturizer"],
        bg_top=(30, 10, 30),
        bg_bottom=(80, 30, 80),
        accent=(255, 150, 200),
        text_primary=(255, 235, 245),
        text_secondary=(220, 170, 200),
        motif="✨ BEAUTY",
        headline_prefix=["Glow with", "Reveal Your", "Elevate", "Discover"],
    ),
    ThemeSpec(
        name="tech",
        keywords=["app", "saas", "software", "tech", "ai", "platform", "digital", "startup", "product", "tool", "launch"],
        bg_top=(5, 15, 35),
        bg_bottom=(10, 30, 70),
        accent=(50, 150, 255),
        text_primary=(210, 230, 255),
        text_secondary=(130, 170, 230),
        motif="⚙ TECH",
        headline_prefix=["Introducing", "Meet", "Powered by", "The Future of"],
    ),
    ThemeSpec(
        name="education",
        keywords=["course", "learn", "education", "training", "workshop", "class", "skill", "certificate", "tutorial", "study"],
        bg_top=(10, 30, 20),
        bg_bottom=(20, 70, 50),
        accent=(50, 220, 130),
        text_primary=(210, 255, 235),
        text_secondary=(130, 210, 170),
        motif="📚 LEARN",
        headline_prefix=["Master", "Learn", "Unlock", "Build Your"],
    ),
    ThemeSpec(
        name="realestate",
        keywords=["real estate", "interior", "home", "property", "apartment", "house", "luxury home", "design", "architecture"],
        bg_top=(18, 18, 18),
        bg_bottom=(40, 35, 25),
        accent=(200, 170, 80),
        text_primary=(245, 240, 225),
        text_secondary=(190, 175, 130),
        motif="🏠 PROPERTY",
        headline_prefix=["Your Dream", "Find Your", "Experience", "Welcome to"],
    ),
    ThemeSpec(
        name="finance",
        keywords=["finance", "business", "invest", "money", "bank", "wealth", "profit", "growth", "strategy", "entrepreneur"],
        bg_top=(5, 20, 10),
        bg_bottom=(10, 50, 25),
        accent=(60, 200, 100),
        text_primary=(215, 255, 230),
        text_secondary=(130, 200, 155),
        motif="📈 BUSINESS",
        headline_prefix=["Grow Your", "Unlock", "Maximize", "Scale Your"],
    ),
    ThemeSpec(
        name="generic",
        keywords=[],  # fallback — always matches
        bg_top=(15, 15, 40),
        bg_bottom=(35, 25, 80),
        accent=(130, 90, 230),
        text_primary=(230, 225, 255),
        text_secondary=(165, 150, 210),
        motif="🎬 REEL",
        headline_prefix=["Discover", "Experience", "Introducing", "See"],
    ),
]


def detect_theme(prompt: str) -> ThemeSpec:
    """Return the best matching ThemeSpec for the given prompt."""
    prompt_lower = prompt.lower()
    best = _THEMES[-1]  # fallback = generic
    best_score = 0
    for theme in _THEMES[:-1]:
        score = theme.keyword_match_score(prompt_lower)
        if score > best_score:
            best_score = score
            best = theme
    return best


def _prompt_hash(prompt: str, seed: int = 0) -> int:
    """Deterministic int hash from prompt + seed for randomised-but-stable variation."""
    digest = hashlib.md5(f"{prompt}|{seed}".encode()).hexdigest()  # noqa: S324
    return int(digest, 16)


def _extract_keywords(prompt: str, n: int = 4) -> list[str]:
    """Extract up to n meaningful words from the prompt (skip stop words)."""
    stop = {
        "a", "an", "the", "for", "in", "on", "of", "to", "with", "and", "or",
        "is", "are", "this", "that", "it", "at", "by", "from", "make", "create",
        "reel", "video", "instagram", "second", "seconds", "short", "my",
    }
    words = re.findall(r"[a-zA-Z']+", prompt)
    keywords = [w.capitalize() for w in words if w.lower() not in stop and len(w) > 2]
    return keywords[:n]


# ── Scene content templates ────────────────────────────────────────────────────

_SCENE_ROLES = [
    ("HOOK",     "Stop Scrolling"),
    ("REVEAL",   "Introducing"),
    ("SHOWCASE", "Features"),
    ("PROOF",    "Why It Works"),
    ("CTA",      "Take Action"),
    ("CLOSING",  "Don't Miss Out"),
]


def _scene_headline(theme: ThemeSpec, scene_idx: int, prompt: str) -> str:
    """Generate a short deterministic headline for a scene."""
    kw = _extract_keywords(prompt)
    prefix_idx = _prompt_hash(prompt, scene_idx) % len(theme.headline_prefix)
    kw_idx = _prompt_hash(prompt, scene_idx + 1) % max(1, len(kw))
    prefix = theme.headline_prefix[prefix_idx]
    kw_word = kw[kw_idx] if kw else theme.name.capitalize()
    return f"{prefix} {kw_word}"


def _scene_role_tag(scene_idx: int, scene_count: int) -> tuple[str, str]:
    """Return (role_label, on_screen_text) for scene position."""
    # Map proportionally into the roles list
    ratio = scene_idx / max(1, scene_count - 1) if scene_count > 1 else 0.0
    role_idx = min(int(ratio * len(_SCENE_ROLES)), len(_SCENE_ROLES) - 1)
    return _SCENE_ROLES[role_idx]


# ── Image generation ───────────────────────────────────────────────────────────

def _lerp_color(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _build_gradient_image(
    theme: ThemeSpec,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> "PILImage":  # type: ignore[name-defined]
    from PIL import Image as PILImage, ImageDraw as PILImageDraw

    img = PILImage.new("RGB", (width, height))
    draw = PILImageDraw.Draw(img)
    # Draw horizontal strip rectangles — much faster than per-pixel loop
    step = 4  # 4px strips: fast enough, smooth enough
    for y in range(0, height, step):
        t = y / height
        color = _lerp_color(theme.bg_top, theme.bg_bottom, t)
        draw.rectangle([(0, y), (width, min(y + step, height))], fill=color)
    return img


def _draw_accent_shapes(
    draw: "ImageDraw",  # type: ignore[name-defined]
    theme: ThemeSpec,
    scene_idx: int,
    prompt: str,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> None:
    """Draw deterministic accent shapes/blocks to differentiate scenes."""
    h = _prompt_hash(prompt, scene_idx * 7)
    accent = theme.accent
    # Vary opacity via RGBA blending — draw accent band at a different position each scene
    band_y = int(height * 0.25) + (scene_idx * int(height * 0.12)) % int(height * 0.5)
    band_h = int(height * 0.006)
    draw.rectangle(
        [(SAFE_MARGIN, band_y), (width - SAFE_MARGIN, band_y + band_h)],
        fill=(*accent, 160),
    )

    # Decorative circle
    r = 40 + (h % 60)
    cx = SAFE_MARGIN + (h % (width - 2 * SAFE_MARGIN - 2 * r)) + r
    cy_options = [int(height * 0.12), int(height * 0.82), int(height * 0.48)]
    cy = cy_options[scene_idx % len(cy_options)]
    draw.ellipse(
        [(cx - r, cy - r), (cx + r, cy + r)],
        fill=(*accent, 80),
        outline=(*accent, 220),
        width=3,
    )

    # Corner accent bracket (top-left)
    bracket_len = 60
    bx, by = SAFE_MARGIN, SAFE_MARGIN
    draw.line([(bx, by), (bx + bracket_len, by)], fill=(*accent, 200), width=4)
    draw.line([(bx, by), (bx, by + bracket_len)], fill=(*accent, 200), width=4)

    # Bottom-right corner bracket
    bx2, by2 = width - SAFE_MARGIN, height - SAFE_MARGIN
    draw.line([(bx2, by2), (bx2 - bracket_len, by2)], fill=(*accent, 200), width=4)
    draw.line([(bx2, by2), (bx2, by2 - bracket_len)], fill=(*accent, 200), width=4)


def _get_font(size: int) -> "ImageFont":  # type: ignore[name-defined]
    """Return an ImageFont, falling back gracefully if custom fonts not available."""
    from PIL import ImageFont

    # Try DejaVu (available in many Docker images), then fall back to default
    for font_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            pass
    # Built-in default (no crash, smaller size)
    return ImageFont.load_default()


def _wrap_text(text: str, max_chars_per_line: int) -> list[str]:
    """Simple word-wrap."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars_per_line:
            current += (" " if current else "") + word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _draw_text_block(
    draw: "ImageDraw",  # type: ignore[name-defined]
    text: str,
    x: int,
    y: int,
    font: "ImageFont",  # type: ignore[name-defined]
    fill: tuple[int, int, int],
    max_chars: int = 28,
) -> int:
    """Draw wrapped text, return Y after last line."""
    lines = _wrap_text(text, max_chars)
    # Determine line height — Pillow 10+ uses getbbox(); older uses getsize()
    try:
        bbox = font.getbbox("Ag")  # type: ignore[attr-defined]
        line_h = bbox[3] - bbox[1]
    except AttributeError:
        try:
            _, line_h = font.getsize("Ag")  # type: ignore[attr-defined]
        except AttributeError:
            line_h = 40

    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h + 8
    return y


def generate_scene_image(
    output_path: Path,
    prompt: str,
    scene_idx: int,
    scene_count: int,
    visual_description: str,
    on_screen_text: str | None = None,
    theme: ThemeSpec | None = None,
) -> Path:
    """
    Generate a single 1080x1920 scene card image for mock storyboard rendering.

    Returns the output_path on success.
    Does NOT expose any local filesystem path in API responses.
    """
    from PIL import Image, ImageDraw

    if theme is None:
        theme = detect_theme(prompt)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Base gradient — build as RGB then convert to RGBA for alpha-blended shapes
    img = _build_gradient_image(theme).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")

    # Accent shapes
    _draw_accent_shapes(draw, theme, scene_idx, prompt)

    # Scene role tag (e.g. HOOK / SHOWCASE / CTA)
    role_label, _ = _scene_role_tag(scene_idx, scene_count)

    # Fonts
    font_motif = _get_font(34)
    font_role = _get_font(28)
    font_scene_num = _get_font(22)
    font_headline = _get_font(72)
    font_visual = _get_font(38)
    font_cta = _get_font(44)

    # --- Top area: motif label ---
    y = SAFE_MARGIN
    draw.text((SAFE_MARGIN, y), theme.motif, font=font_motif, fill=(*theme.accent, 230))
    y += 60

    # Role tag badge
    draw.rectangle(
        [(SAFE_MARGIN, y), (SAFE_MARGIN + 160, y + 38)],
        fill=(*theme.accent, 50),
        outline=(*theme.accent, 160),
        width=2,
    )
    draw.text((SAFE_MARGIN + 12, y + 6), role_label, font=font_role, fill=theme.accent)
    y += 60

    # Scene number indicator
    scene_label = f"SCENE {scene_idx + 1} / {scene_count}"
    draw.text((SAFE_MARGIN, y), scene_label, font=font_scene_num, fill=(*theme.text_secondary, 180))
    y += 50

    # --- Middle area: headline ---
    headline = _scene_headline(theme, scene_idx, prompt)
    y = int(HEIGHT * 0.38)
    y = _draw_text_block(draw, headline.upper(), SAFE_MARGIN, y, font_headline, theme.text_primary, max_chars=16)
    y += 20

    # Horizontal rule under headline
    draw.rectangle(
        [(SAFE_MARGIN, y), (SAFE_MARGIN + 200, y + 4)],
        fill=(*theme.accent, 200),
    )
    y += 30

    # Visual description (short)
    short_visual = visual_description[:90] + ("…" if len(visual_description) > 90 else "")
    y = _draw_text_block(draw, short_visual, SAFE_MARGIN, y, font_visual, theme.text_secondary, max_chars=30)
    y += 20

    # On-screen text overlay / CTA
    if on_screen_text:
        short_cta = on_screen_text[:60]
        cta_y = int(HEIGHT * 0.76)
        # CTA backing rectangle
        draw.rectangle(
            [(SAFE_MARGIN, cta_y - 14), (WIDTH - SAFE_MARGIN, cta_y + 80)],
            fill=(*theme.accent, 35),
            outline=(*theme.accent, 120),
            width=2,
        )
        _draw_text_block(draw, short_cta, SAFE_MARGIN + 16, cta_y, font_cta, theme.text_primary, max_chars=24)

    # --- Bottom: keywords strip ---
    kw_list = _extract_keywords(prompt, 4)
    if kw_list:
        kw_text = "  ·  ".join(kw_list)
        kw_y = HEIGHT - SAFE_MARGIN - 40
        draw.text((SAFE_MARGIN, kw_y), kw_text, font=font_scene_num, fill=(*theme.text_secondary, 150))

    # Save as JPEG
    img.convert("RGB").save(str(output_path), "JPEG", quality=90)

    logger.info(
        "mock_visual.scene_generated",
        path=output_path.name,
        theme=theme.name,
        scene_idx=scene_idx,
    )
    return output_path


# ── Public interface ───────────────────────────────────────────────────────────

@dataclass
class MockVisualResult:
    scene_paths: list[Path]
    theme_name: str
    scene_count: int


def generate_mock_storyboard(
    prompt: str,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    storage_root: str,
    scenes: list[dict] | None = None,
    scene_count: int | None = None,
) -> MockVisualResult:
    """
    Generate a full mock storyboard: one 1080x1920 image per scene.

    Parameters
    ----------
    prompt:        Original reel prompt (for theme detection + keyword extraction).
    project_id:    Used to namespace output directory.
    version_id:    Used to namespace output directory.
    storage_root:  LOCAL_STORAGE_PATH.
    scenes:        Optional list of SceneItem-like dicts with visual/visual_description
                   and on_screen_text/text_overlay.
    scene_count:   Number of scenes to generate if `scenes` is not provided.

    Returns
    -------
    MockVisualResult with sorted list of generated image Paths.
    """
    try:
        from PIL import Image  # noqa: F401  — verify Pillow is importable
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for mock visual generation. "
            "Install it: pip install Pillow>=10.0.0"
        ) from exc

    theme = detect_theme(prompt)

    # Normalise scene list
    if not scenes:
        n = max(3, scene_count or 3)
        scenes = [
            {
                "visual_description": f"Scene {i + 1}: {theme.name.capitalize()} visual for '{prompt[:60]}'",
                "on_screen_text": f"{theme.headline_prefix[i % len(theme.headline_prefix)]} — Scene {i + 1}",
            }
            for i in range(n)
        ]

    n_scenes = len(scenes)
    out_dir = (
        Path(storage_root)
        / "mock_visuals"
        / str(project_id)
        / str(version_id)
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    for i, scene in enumerate(scenes):
        visual_desc = (
            scene.get("visual")
            or scene.get("visual_description")
            or f"Scene {i + 1}"
        )
        on_screen = scene.get("on_screen_text") or scene.get("text_overlay")
        out_path = out_dir / f"scene_{i + 1:03d}.jpg"
        generate_scene_image(
            output_path=out_path,
            prompt=prompt,
            scene_idx=i,
            scene_count=n_scenes,
            visual_description=str(visual_desc),
            on_screen_text=str(on_screen) if on_screen else None,
            theme=theme,
        )
        generated.append(out_path)

    logger.info(
        "mock_visual.storyboard_complete",
        project_id=str(project_id),
        version_id=str(version_id),
        theme=theme.name,
        scene_count=n_scenes,
    )

    return MockVisualResult(
        scene_paths=generated,
        theme_name=theme.name,
        scene_count=n_scenes,
    )
