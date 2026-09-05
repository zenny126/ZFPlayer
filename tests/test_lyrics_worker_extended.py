import os
import pytest
from unittest.mock import MagicMock, patch
from backend.workers.lyrics_worker import LyricsWorker


@pytest.fixture
def static_worker(temp_db, temp_cache):
    """Provides LyricsWorker without background queue consumer thread."""
    with patch.object(LyricsWorker, "_start_queue_worker"):
        return LyricsWorker(database=temp_db, cache_manager=temp_cache)


def test_lyrics_worker_normalize_string():
    """Verify normalize_string handles casing, unicode normalization, and collapses whitespace."""
    assert LyricsWorker.normalize_string("  Adele  ") == "adele"
    assert LyricsWorker.normalize_string("Sơn   Tùng   M-TP") == "sơn tùng m-tp"
    assert LyricsWorker.normalize_string("") == ""
    assert LyricsWorker.normalize_string(None) == ""


def test_lyrics_worker_cache_key_deterministic(static_worker):
    """Verify _get_cache_key generates identical hashes regardless of whitespace or casing."""
    key1 = static_worker._get_cache_key("Adele", "Rolling in the Deep", "21", 228.4)
    key2 = static_worker._get_cache_key("  adele  ", "ROLLING IN THE DEEP", "21", 228.1)
    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex string


def test_lyrics_worker_enqueue_skips_unknown(static_worker):
    """Verify enqueue_track ignores tracks with missing or 'Unknown' titles/artists."""
    static_worker.enqueue_track({"artist": "Unknown", "title": "Song 1"})
    static_worker.enqueue_track({"artist": "Adele", "title": "Unknown"})
    static_worker.enqueue_track({})

    assert static_worker._queue.qsize() == 0


def test_lyrics_worker_enqueue_deduplication(static_worker):
    """Verify enqueue_track does not enqueue duplicate requests in non-priority mode."""
    track = {"artist": "Eagles", "title": "Hotel California", "album": "Hotel", "duration": 391.0}

    static_worker.enqueue_track(track, priority=False)
    static_worker.enqueue_track(track, priority=False)

    assert static_worker._queue.qsize() == 1


def test_lyrics_worker_priority_queueing(static_worker):
    """Verify priority=True puts item at high priority (priority_val=1)."""
    track_low = {"artist": "ArtistA", "title": "TrackA", "duration": 180.0}
    track_high = {"artist": "ArtistB", "title": "TrackB", "duration": 200.0}

    static_worker.enqueue_track(track_low, priority=False)
    static_worker.enqueue_track(track_high, priority=True)

    item1 = static_worker._queue.get()
    item2 = static_worker._queue.get()

    assert item1[0] == 1  # priority_val 1 (High)
    assert item1[2]["title"] == "TrackB"
    assert item2[0] == 10  # priority_val 10 (Low)
    assert item2[2]["title"] == "TrackA"


def test_lyrics_worker_db_cache_hit_skips_queue(static_worker, temp_db):
    """Verify enqueue_track skips queue if lyrics are already cached in SQLite."""
    artist = "Coldplay"
    title = "Yellow"
    cache_key = static_worker._get_cache_key(artist, title, "", 260.0)

    # Prepopulate SQLite lyrics cache
    temp_db.save_lyrics(cache_key, "[00:10.00] Look at the stars", "Look at the stars", "db_test")

    track = {"artist": artist, "title": title, "duration": 260.0}
    static_worker.enqueue_track(track)
    assert static_worker._queue.qsize() == 0


def test_lyrics_worker_local_lrc_content_reading(temp_dir, static_worker):
    """Verify _read_local_lrc detects and reads sidecar .lrc files cleanly."""
    track_path = os.path.join(temp_dir, "my_song.flac")
    lrc_path = os.path.join(temp_dir, "my_song.lrc")

    with open(track_path, "w") as f:
        f.write("dummy audio")
    with open(lrc_path, "w", encoding="utf-8") as f:
        f.write("[00:01.00] Line 1\n[00:05.00] Line 2")

    content = static_worker._read_local_lrc(track_path)
    assert content is not None
    assert "[00:01.00]" in content


def test_lyrics_worker_negative_cache_storage(static_worker, temp_db):
    """Verify negative caching (source: none, [NO_LYRICS]) stores empty lyrics to prevent spam."""
    artist = "NonExistentArtistXYZ"
    title = "GhostSongABC"

    with patch.object(static_worker, "_fetch_lrclib_exact", return_value=None), \
         patch.object(static_worker, "_fetch_syncedlyrics_fallback", return_value=None):
        result = static_worker.fetch_lyrics(artist, title, "Album", 150.0, "")

        assert result is not None
        assert result["source"] == "none"
        assert result["synced_lyrics"] == ""

        cache_key = static_worker._get_cache_key(artist, title, "Album", 150.0)
        cached = temp_db.get_lyrics(cache_key)
        assert cached is not None
        assert cached["synced_lyrics"] == "[NO_LYRICS]"
