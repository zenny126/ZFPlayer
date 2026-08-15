import os
import pytest
from unittest.mock import MagicMock, patch
from backend.workers.lyrics_worker import LyricsWorker


def test_lyrics_cache_key_deterministic(temp_db):
    """Verify cache keys are deterministic, normalized and insensitive to whitespace/case differences."""
    worker = LyricsWorker(database=temp_db)
    
    key1 = worker._get_cache_key("Adele", "Rolling In The Deep", "21", 228.5)
    key2 = worker._get_cache_key("adele  ", "rolling in the deep", "21", 228.5)
    
    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex digest


def test_lyrics_local_lrc_file_reading(temp_dir, temp_db):
    """Verify Local-First Tier 1 reads sidecar .lrc files accurately."""
    worker = LyricsWorker(database=temp_db)
    
    audio_path = os.path.join(temp_dir, "MySong.flac")
    lrc_path = os.path.join(temp_dir, "MySong.lrc")
    
    # Create audio file so path exists
    with open(audio_path, "wb") as f:
        f.write(b"dummy_flac_header")
        
    lrc_content = "[00:05.00] Line 1\n[00:15.50] Line 2 with Unicode: Tiếng Việt"
    with open(lrc_path, "w", encoding="utf-8") as f:
        f.write(lrc_content)
        
    read_text = worker._read_local_lrc(audio_path)
    assert read_text == lrc_content


def test_lyrics_local_first_priority_over_network(temp_dir, temp_db):
    """Verify local .lrc file takes precedence without triggering any network calls."""
    worker = LyricsWorker(database=temp_db)
    
    audio_path = os.path.join(temp_dir, "Track1.flac")
    lrc_path = os.path.join(temp_dir, "Track1.lrc")
    
    with open(audio_path, "wb") as f:
        f.write(b"dummy_flac_header")
        
    with open(lrc_path, "w", encoding="utf-8") as f:
        f.write("[00:01.00] Local lyric line")

    with patch.object(worker, '_fetch_lrclib_exact', return_value=None) as mock_exact, \
         patch.object(worker, '_fetch_lrclib_search', return_value=None) as mock_search:
        
        result = worker.fetch_lyrics("Artist", "Track1", "Album", 120.0, path=audio_path)
        
        assert result is not None
        assert result['synced_lyrics'] == "[00:01.00] Local lyric line"
        assert result['source'] == 'local_lrc'
        
        # Network must not be called
        mock_exact.assert_not_called()
        mock_search.assert_not_called()



def test_lyrics_fetch_from_database_cache(temp_db):
    """Verify cached lyrics in DB are returned immediately with 0 network calls."""
    worker = LyricsWorker(database=temp_db)
    cache_key = worker._get_cache_key("Eagles", "Hotel California", "", 391.0)
    temp_db.save_lyrics(cache_key, "[00:30.00] On a dark desert highway", "", "lrclib")

    with patch.object(worker, '_fetch_lrclib_exact') as mock_exact:
        result = worker.fetch_lyrics("Eagles", "Hotel California", "", 391.0)
        
        assert result is not None
        assert result['synced_lyrics'] == "[00:30.00] On a dark desert highway"
        assert result['source'] == "lrclib"
        mock_exact.assert_not_called()


def test_lyrics_lrclib_exact_match_success(temp_db):
    """Verify Tier 3 (LRCLIB Exact Match) fetches, parses and caches synced lyrics."""
    worker = LyricsWorker(database=temp_db)
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": 12345,
        "trackName": "Hello",
        "artistName": "Adele",
        "syncedLyrics": "[00:10.00] Hello from the other side\n[00:15.00] I must have called a thousand times",
        "plainLyrics": "Hello from the other side"
    }

    with patch.object(worker._session, 'get', return_value=mock_resp):
        result = worker.fetch_lyrics("Adele", "Hello", "25", 295.0)
        
        assert result is not None
        assert result['source'] == 'lrclib_exact'
        assert "[00:10.00] Hello from the other side" in result['synced_lyrics']
        
        # Verify it was saved to DB cache
        cache_key = worker._get_cache_key("Adele", "Hello", "25", 295.0)
        cached = temp_db.get_lyrics(cache_key)
        assert cached is not None
        assert cached['source'] == 'lrclib_exact'


def test_lyrics_negative_cache_on_not_found(temp_db):
    """Verify when all providers fail, a negative cache [NO_LYRICS] is stored."""
    worker = LyricsWorker(database=temp_db)
    
    mock_404 = MagicMock()
    mock_404.status_code = 404
    
    with patch.object(worker._session, 'get', return_value=mock_404), \
         patch.object(worker, '_fetch_syncedlyrics_fallback', return_value=None):
        
        result = worker.fetch_lyrics("NonExistentArtist", "NonExistentTrack", "", 180.0)
        
        assert result is not None
        assert result['source'] == 'none'
        assert result['synced_lyrics'] == ''
        
        # Check that [NO_LYRICS] was recorded in DB
        cache_key = worker._get_cache_key("NonExistentArtist", "NonExistentTrack", "", 180.0)
        cached = temp_db.get_lyrics(cache_key)
        assert cached is not None
        assert cached['synced_lyrics'] == '[NO_LYRICS]'
