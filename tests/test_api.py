import os
import pytest
from unittest.mock import MagicMock
from backend.api.config_api import ConfigAPI
from backend.api.lyrics_api import LyricsAPI
from backend.api.library_api import LibraryAPI
from backend.api.player_api import PlayerAPI
from backend.services.library_service import LibraryService
from backend.services.player_service import PlayerService
from backend.storage.config import Config


def test_config_api_get_and_set(temp_dir):
    """Verify ConfigAPI reads and writes configuration keys correctly."""
    Config._instance = None
    config_file = os.path.join(temp_dir, "config.json")
    cfg = Config(config_path=config_file)
    api = ConfigAPI(config=cfg)
    
    # 1. Get initial config
    data = api.get_config()
    assert isinstance(data, dict)
    
    # 2. Set config
    api.set_config("volume", 75)
    updated = api.get_config()
    assert updated.get("volume") == 75

    # 3. Set audio mode
    res = api.set_audio_mode("exclusive")
    assert res["status"] == "success"
    assert res["audio_mode"] == "exclusive"
    Config._instance = None


def test_lyrics_api_delegation():
    """Verify LyricsAPI delegates to LyricsWorker and handles None gracefully."""
    mock_worker = MagicMock()
    mock_worker.fetch_lyrics.return_value = {"synced_lyrics": "[00:01.00] Test", "source": "test"}
    
    api = LyricsAPI(lyrics_worker=mock_worker)
    res = api.get_lyrics("Artist", "Title", "Album", 120.0)
    
    assert res["synced_lyrics"] == "[00:01.00] Test"
    mock_worker.fetch_lyrics.assert_called_once_with("Artist", "Title", "Album", 120.0, "")

    # When worker returns None, API should return empty dict
    mock_worker.fetch_lyrics.return_value = None
    res_empty = api.get_lyrics("Unknown", "Unknown")
    assert res_empty == {}


def test_library_api_operations(temp_db, temp_cache, sample_track_batch):
    """Verify LibraryAPI operations: tracks listing, playlist CRUD, liking."""
    temp_db.bulk_insert_tracks(sample_track_batch)
    
    mock_config = MagicMock()
    mock_scanner = MagicMock()
    lib_service = LibraryService(database=temp_db, cache_manager=temp_cache, scanner=mock_scanner, lyrics_worker=None)
    api = LibraryAPI(library_service=lib_service, config=mock_config)
    
    # 1. Get tracks paginated and total count
    res_tracks = api.get_tracks(limit=10)
    assert len(res_tracks) == 3
    assert api.get_track_count() == 3

    # 2. Toggle like
    res_like = api.toggle_like(sample_track_batch[0]["path"])
    assert res_like["status"] == "success"
    assert res_like["is_liked"] == 1

    # 3. Playlist management
    p_res = api.create_playlist("Chill Vibes")
    assert p_res["status"] == "success"
    p_id = p_res["playlist_id"]
    
    playlists = api.get_playlists()
    assert any(p["id"] == p_id for p in playlists)
    
    del_res = api.delete_playlist(p_id)
    assert del_res["status"] == "success"



def test_player_api_delegation():
    """Verify PlayerAPI dispatches playback commands to PlayerService correctly."""
    mock_service = MagicMock()
    mock_service.get_state.return_value = {"is_playing": True, "position": 15.5}
    
    api = PlayerAPI(player_service=mock_service)
    
    api.play("C:\\music\\song.flac", 1)
    mock_service.play.assert_called_once_with("C:\\music\\song.flac", 1)
    
    api.pause()
    mock_service.pause.assert_called_once()
    
    api.resume()
    mock_service.resume.assert_called_once()
    
    api.seek(45.0)
    mock_service.seek.assert_called_once_with(45.0)
    
    api.set_volume(0.8)
    mock_service.set_volume.assert_called_once_with(0.8)
    
    state = api.get_player_state()
    assert state["is_playing"] is True
    assert state["position"] == 15.5

