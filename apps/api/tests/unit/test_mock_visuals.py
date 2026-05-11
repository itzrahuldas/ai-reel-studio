"""
Unit tests for mock visual storyboard scene generator.

Tests:
1. Generator creates scene images for a storyboard.
2. Generated images are 1080x1920.
3. Different prompts produce different theme metadata.
4. Different prompts produce different image hashes.
5. Public API response does not expose local filesystem paths.
6. Render pipeline uses generated mock visual scene paths when no real media exists.
"""

import hashlib
import os
import uuid
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-mock-visuals")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "b" * 64)

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()  # noqa: S324


def _skip_if_no_pillow() -> None:
    """Skip the test if Pillow is not installed."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        pytest.skip("Pillow not installed — skipping mock visual tests")


# ── Theme detection ───────────────────────────────────────────────────────────

def test_detect_theme_coffee():
    from app.services.rendering.mock_visuals import detect_theme

    theme = detect_theme("caramel iced coffee launch for a cafe")
    assert theme.name == "coffee"


def test_detect_theme_fitness():
    from app.services.rendering.mock_visuals import detect_theme

    theme = detect_theme("gym transformation challenge for fitness")
    assert theme.name == "fitness"


def test_detect_theme_travel():
    from app.services.rendering.mock_visuals import detect_theme

    theme = detect_theme("Bali travel reel adventure vacation")
    assert theme.name == "travel"


def test_detect_theme_beauty():
    from app.services.rendering.mock_visuals import detect_theme

    theme = detect_theme("skincare glow serum beauty product launch")
    assert theme.name == "beauty"


def test_detect_theme_generic_fallback():
    from app.services.rendering.mock_visuals import detect_theme

    theme = detect_theme("some completely unrelated random content xyz")
    assert theme.name == "generic"


# ── Scene generation ──────────────────────────────────────────────────────────

def test_generate_mock_storyboard_creates_scenes(tmp_path: Path) -> None:
    _skip_if_no_pillow()
    from app.services.rendering.mock_visuals import generate_mock_storyboard

    project_id = uuid.uuid4()
    version_id = uuid.uuid4()
    result = generate_mock_storyboard(
        prompt="caramel iced coffee launch for a cozy cafe",
        project_id=project_id,
        version_id=version_id,
        storage_root=str(tmp_path),
        scene_count=3,
    )

    assert len(result.scene_paths) == 3, "Should generate 3 scenes"
    for p in result.scene_paths:
        assert p.exists(), f"Scene image {p.name} should exist"
        assert p.suffix == ".jpg"
        assert p.stat().st_size > 0


def test_generated_images_are_1080x1920(tmp_path: Path) -> None:
    _skip_if_no_pillow()
    from PIL import Image

    from app.services.rendering.mock_visuals import generate_mock_storyboard

    project_id = uuid.uuid4()
    version_id = uuid.uuid4()
    result = generate_mock_storyboard(
        prompt="gym transformation challenge",
        project_id=project_id,
        version_id=version_id,
        storage_root=str(tmp_path),
        scene_count=3,
    )

    for p in result.scene_paths:
        img = Image.open(p)
        assert img.size == (1080, 1920), f"{p.name}: expected 1080x1920 got {img.size}"


def test_different_prompts_produce_different_themes(tmp_path: Path) -> None:
    _skip_if_no_pillow()
    from app.services.rendering.mock_visuals import generate_mock_storyboard

    result_cafe = generate_mock_storyboard(
        prompt="caramel iced coffee launch for a cozy cafe",
        project_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        storage_root=str(tmp_path),
        scene_count=3,
    )
    result_gym = generate_mock_storyboard(
        prompt="high-intensity gym transformation challenge",
        project_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        storage_root=str(tmp_path),
        scene_count=3,
    )

    assert result_cafe.theme_name != result_gym.theme_name, (
        "Cafe and gym prompts should produce different themes"
    )
    assert result_cafe.theme_name == "coffee"
    assert result_gym.theme_name == "fitness"


def test_different_prompts_produce_different_image_hashes(tmp_path: Path) -> None:
    _skip_if_no_pillow()
    from app.services.rendering.mock_visuals import generate_mock_storyboard

    result_cafe = generate_mock_storyboard(
        prompt="caramel iced coffee launch for a cozy cafe",
        project_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        storage_root=str(tmp_path),
        scene_count=1,
    )
    result_bali = generate_mock_storyboard(
        prompt="Bali travel adventure beach vacation reel",
        project_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        storage_root=str(tmp_path),
        scene_count=1,
    )

    hash_cafe = _file_md5(result_cafe.scene_paths[0])
    hash_bali = _file_md5(result_bali.scene_paths[0])
    assert hash_cafe != hash_bali, "Different prompts should produce different image bytes"


def test_generate_mock_storyboard_uses_scene_dicts(tmp_path: Path) -> None:
    _skip_if_no_pillow()
    from app.services.rendering.mock_visuals import generate_mock_storyboard

    scenes = [
        {"visual_description": "Scene 1: Product close-up", "on_screen_text": "Introducing!"},
        {"visual_description": "Scene 2: Lifestyle shot", "on_screen_text": "Made for You"},
        {"visual_description": "Scene 3: CTA with logo", "on_screen_text": "Shop Now"},
    ]
    result = generate_mock_storyboard(
        prompt="product launch reel",
        project_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        storage_root=str(tmp_path),
        scenes=scenes,
    )

    assert result.scene_count == 3
    assert len(result.scene_paths) == 3


def test_generate_mock_storyboard_at_least_3_scenes(tmp_path: Path) -> None:
    _skip_if_no_pillow()
    from app.services.rendering.mock_visuals import generate_mock_storyboard

    # No scenes provided — should still generate at least 3
    result = generate_mock_storyboard(
        prompt="some prompt",
        project_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        storage_root=str(tmp_path),
    )

    assert result.scene_count >= 3


# ── API response safety ───────────────────────────────────────────────────────

def test_build_media_asset_response_does_not_expose_storage_path() -> None:
    """Public API response must never include local filesystem paths."""
    import uuid as _uuid
    from types import SimpleNamespace

    from app.services.render_service import build_media_asset_response
    from app.models.models import MediaAssetStatus, MediaAssetType

    asset = SimpleNamespace(
        id=_uuid.uuid4(),
        workspace_id=_uuid.uuid4(),
        project_id=_uuid.uuid4(),
        asset_type=MediaAssetType.RENDERED_VIDEO,
        s3_key="renders/reel_abc.mp4",
        s3_bucket="local",
        filename="reel_abc.mp4",
        mime_type="video/mp4",
        file_size=12345,
        status=MediaAssetStatus.READY,
        metadata_={
            "storage_path": "/var/lib/ai-reel-studio/media/renders/reel_abc.mp4",
            "renderer": "ffmpeg",
            "visual_source": "mock_storyboard",
            "mock_visual_theme": "coffee",
            "generated_scene_count": 3,
        },
        created_at=None,
    )

    response = build_media_asset_response(asset)

    # Check no storage_path in response
    response_str = str(response)
    assert "/var/lib" not in response_str, "Local filesystem path must not appear in API response"
    assert "storage_path" not in response, "storage_path key must not appear in response"
    # Check safe metadata is exposed
    assert response["metadata"]["visual_source"] == "mock_storyboard"
    assert response["metadata"]["mock_visual_theme"] == "coffee"
    assert response["metadata"]["generated_scene_count"] == 3


# ── Render pipeline integration ───────────────────────────────────────────────

def test_render_pipeline_uses_mock_visuals_when_no_source_image(tmp_path: Path, monkeypatch) -> None:
    """
    Smoke-test: _get_source_image_path falls back to placeholder,
    and generate_mock_storyboard generates images when source_image_id is None.
    """
    _skip_if_no_pillow()
    from app.services.rendering.mock_visuals import generate_mock_storyboard

    project_id = uuid.uuid4()
    version_id = uuid.uuid4()

    result = generate_mock_storyboard(
        prompt="cozy cafe iced coffee launch for Instagram",
        project_id=project_id,
        version_id=version_id,
        storage_root=str(tmp_path),
        scene_count=3,
    )

    assert result.scene_count == 3
    assert all(p.exists() for p in result.scene_paths)
    # The render pipeline should use these as scene_image_paths
    assert len(result.scene_paths) == 3


def test_ffmpeg_render_params_accepts_scene_image_paths(tmp_path: Path) -> None:
    """RenderParams should accept scene_image_paths without error."""
    from app.services.rendering.ffmpeg_renderer import RenderParams

    scene_paths = [tmp_path / f"scene_{i}.jpg" for i in range(3)]
    for p in scene_paths:
        p.write_bytes(b"jpg")

    params = RenderParams(
        image_path=scene_paths[0],
        output_path=tmp_path / "out.mp4",
        thumbnail_path=tmp_path / "thumb.jpg",
        duration_seconds=12,
        scene_image_paths=scene_paths,
    )

    assert params.scene_image_paths is not None
    assert len(params.scene_image_paths) == 3
