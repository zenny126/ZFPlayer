import math
from unittest.mock import patch
import pytest
from backend.audio.engine import AudioEngine
from backend.workers.lyrics_worker import LyricsWorker


# =============================================================================
# 1. AudioEngine Volume Clamping Boundary Tests
# =============================================================================

@pytest.mark.parametrize("input_vol,expected_clamped", [
    (-100.0, 0.0),
    (-0.001, 0.0),
    (0.0, 0.0),
    (0.0001, 0.0001),
    (0.5, 0.5),
    (0.9999, 0.9999),
    (1.0, 1.0),
    (1.0001, 1.0),
    (50.0, 1.0),
])
def test_bva_audio_engine_volume_boundaries(input_vol: float, expected_clamped: float):
    """BVA: AudioEngine volume must be clamped strictly within [0.0, 1.0]."""
    engine = AudioEngine()
    engine.set_volume(input_vol)
    assert math.isclose(engine.volume, expected_clamped, rel_tol=1e-5)


@pytest.mark.parametrize("special_float", [
    float("nan"),
    float("inf"),
    float("-inf"),
])
def test_bva_audio_engine_volume_special_floats(special_float: float):
    """BVA: Special IEEE-754 floats (NaN, Inf) must not corrupt engine volume."""
    engine = AudioEngine()

    try:
        engine.set_volume(special_float)
    except (ValueError, TypeError) as ex:
        assert str(ex) or isinstance(ex, Exception)

    assert not math.isnan(engine.volume)
    assert 0.0 <= engine.volume <= 1.0


# =============================================================================
# 2. AudioEngine Seek Boundaries
# =============================================================================

@pytest.mark.parametrize("seek_input,expected_min", [
    (-100.0, 0.0),
    (-0.1, 0.0),
    (0.0, 0.0),
])
def test_bva_audio_engine_seek_negative_boundaries(seek_input: float, expected_min: float):
    """BVA: Seeking to negative positions must clamp to >= 0.0."""
    engine = AudioEngine()
    engine.seek(seek_input)
    state = engine.get_state()
    assert state["position_seconds"] >= expected_min


# =============================================================================
# 3. Database Pagination Boundary Tests
# =============================================================================

@pytest.mark.parametrize("offset,limit", [
    (0, 0),
    (0, 1),
    (0, 10),
    (1000, 10),
    (999999, 100),
])
def test_bva_database_pagination_extreme_boundaries(temp_db, offset: int, limit: int):
    """BVA: Extreme offset and limit values must return lists without exceptions."""
    results = temp_db.get_tracks_paginated(offset=offset, limit=limit)
    assert isinstance(results, list)
    assert len(results) <= max(0, limit)


# =============================================================================
# 4. LyricsWorker Input Sanitization Boundaries
# =============================================================================

@pytest.mark.parametrize("artist,title,expected_queue_size", [
    ("", "", 0),
    ("   ", "   ", 0),
    ("Unknown", "Song", 0),
    ("Artist", "unknown", 0),
    ("Unknown Artist", "Valid Song", 0),
    ("  Artist  ", "  Title  ", 1),
    ("Đen Vâu 🚀", "Trốn Tìm", 1),
    ("A" * 1000, "B" * 1000, 1),
])
def test_bva_lyrics_worker_enqueue_boundaries(temp_db, artist: str, title: str, expected_queue_size: int):
    """BVA: String boundary cases (empty, whitespace, sentinel 'unknown', unicode, stress length)."""
    with patch.object(LyricsWorker, "_start_queue_worker"):
        worker = LyricsWorker(database=temp_db)

        track_info = {
            "artist": artist,
            "title": title,
            "album": "Album",
            "duration": 180.0,
            "path": "/music/test.flac",
        }

        worker.enqueue_track(track_info)
        assert worker._queue.qsize() == expected_queue_size
