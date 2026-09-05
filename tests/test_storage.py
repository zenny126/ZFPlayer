import os
import io
import time
import json
import pytest
from PIL import Image
from backend.storage.cache import CacheManager
from backend.storage.config import Config


def _create_sample_image_bytes(format_name="PNG", mode="RGB", size=(400, 400), color=(100, 150, 200)) -> bytes:
    """Helper to synthesize test image bytes in memory."""
    img = Image.new(mode, size, color=color)
    bio = io.BytesIO()
    img.save(bio, format=format_name)
    return bio.getvalue()


def test_cache_save_and_retrieve_cover(temp_dir):
    """Verify CacheManager saves RGB/RGBA images as JPEG and retrieves valid paths."""
    cache = CacheManager(cache_dir=os.path.join(temp_dir, "cache"))
    img_bytes = _create_sample_image_bytes(format_name="PNG", mode="RGBA", size=(500, 500))
    cover_hash = "abc123hash"

    # 1. Save cover
    saved_path = cache.save_cover(img_bytes, cover_hash)
    assert os.path.exists(saved_path)
    assert saved_path.endswith(f"{cover_hash}.jpg")

    # 2. Verify retrieved path matches
    retrieved = cache.get_cover_path(cover_hash)
    assert retrieved == saved_path

    # 3. Verify fast-path cached hit
    second_save = cache.save_cover(img_bytes, cover_hash)
    assert second_save == saved_path


def test_cache_save_thumbnail(temp_dir):
    """Verify CacheManager generates resized thumbnails preserving aspect ratio."""
    cache = CacheManager(cache_dir=os.path.join(temp_dir, "cache"))
    img_bytes = _create_sample_image_bytes(format_name="JPEG", mode="RGB", size=(800, 600))
    cover_hash = "thumb_hash_1"

    thumb_path = cache.save_thumbnail(img_bytes, cover_hash, size=(300, 300))
    assert os.path.exists(thumb_path)
    assert thumb_path.endswith(f"{cover_hash}_thumb.jpg")

    with Image.open(thumb_path) as im:
        assert im.width <= 300
        assert im.height <= 300


def test_cache_lyrics_and_clear_all(temp_dir):
    """Verify JSON lyrics caching, file persistence, and complete cache clearance."""
    cache = CacheManager(cache_dir=os.path.join(temp_dir, "cache"))
    key = "track_key_123"
    lyrics_data = {
        "plain_lyrics": "Sample plain lyrics text",
        "synced_lyrics": "[00:05.00] Line 1\n[00:10.00] Line 2",
        "source": "unit_test"
    }

    cache.save_lyrics_cache(key, lyrics_data)
    loaded = cache.get_lyrics_cache(key)
    assert loaded == lyrics_data

    # Clear all cache and verify directories are emptied
    cache.clear_all()
    assert cache.get_lyrics_cache(key) is None
    assert cache.get_cover_path("any_hash") is None


def test_cache_handles_invalid_bytes(temp_dir):
    """Verify CacheManager safely handles empty or corrupted image bytes without crashing."""
    cache = CacheManager(cache_dir=os.path.join(temp_dir, "cache"))
    assert cache.save_cover(b"", "empty_hash") == ""
    assert cache.save_cover(b"corrupted_non_image_bytes", "bad_hash") == ""
    assert cache.save_thumbnail(b"", "empty_thumb") == ""
    assert cache.get_cover_path("") is None


def test_config_crud_and_persistence(temp_dir):
    """Verify Config reads defaults, persists mutations, and schedules save."""
    Config._instance = None
    cfg_file = os.path.join(temp_dir, "test_config.json")
    cfg = Config(config_path=cfg_file)

    assert cfg.get("repeat") == "off"
    assert cfg.get("volume") == 0.8

    cfg.set("volume", 0.95)
    cfg.set("repeat", "all")
    assert cfg.get("volume") == 0.95
    assert cfg.get("repeat") == "all"

    # Flush save explicitly to disk
    cfg._save()
    assert os.path.exists(cfg_file)
    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["volume"] == 0.95
    assert data["repeat"] == "all"
    Config._instance = None


def test_config_self_heals_corrupted_json(temp_dir):
    """Verify Config self-heals back to defaults when encountering a corrupted JSON file."""
    Config._instance = None
    cfg_file = os.path.join(temp_dir, "corrupt_config.json")
    with open(cfg_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json formatting ... ")

    cfg = Config(config_path=cfg_file)
    assert cfg.get("volume") == 0.8
    assert cfg.get("repeat") == "off"
    Config._instance = None
