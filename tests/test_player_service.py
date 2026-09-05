import time
from unittest.mock import MagicMock
import pytest
from backend.services.player_service import PlayerService


@pytest.fixture
def mock_audio_engine():
    engine = MagicMock()
    engine.state.name = "IDLE"
    engine.get_state.return_value = {
        "is_playing": False,
        "position_seconds": 0.0,
        "duration_seconds": 180.0,
    }
    return engine


@pytest.fixture
def mock_library_service():
    lib = MagicMock()
    tracks = ["/music/song1.flac", "/music/song2.flac", "/music/song3.flac"]
    lib.get_all_track_paths.return_value = tracks
    lib.get_track_info.side_effect = lambda p: {
        "path": p,
        "title": p.split("/")[-1],
        "artist": "Artist",
        "duration": 180.0,
    }
    lib.get_tracks_by_paths.side_effect = lambda paths: {
        p: lib.get_track_info(p) for p in paths
    }
    return lib


@pytest.fixture
def mock_config():
    store = {
        "last_track": None,
        "last_playlist_id": "all",
        "volume": 0.8,
        "shuffle": False,
        "repeat": "off",
    }
    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: store.get(key, default)
    cfg.set.side_effect = lambda key, val: store.__setitem__(key, val)
    return cfg


def test_player_service_index_map_and_monotonic_version(mock_audio_engine, mock_library_service, mock_config):
    """Verify O(1) index map and monotonic playlist versioning."""
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    assert service._playlist_version == 0
    assert service._shuffled_version == -1

    # Synchronize playlist
    service._sync_playlists_and_index("/music/song1.flac", playlist_id="all")
    assert service.normal_playlist == ["/music/song1.flac", "/music/song2.flac", "/music/song3.flac"]
    assert service._normal_index_map["/music/song1.flac"] == 0
    assert service._normal_index_map["/music/song2.flac"] == 1
    assert service._normal_index_map["/music/song3.flac"] == 2
    assert service._playlist_version == 1

    # Shuffled version should sync to current playlist version
    assert service._shuffled_version == service._playlist_version
    assert len(service.shuffled_playlist) == 3

    # Subsequent sync without changes should not bump playlist version
    old_version = service._playlist_version
    old_shuffled = list(service.shuffled_playlist)
    service._sync_playlists_and_index("/music/song2.flac", playlist_id="all")
    assert service._playlist_version == old_version
    assert service.shuffled_playlist == old_shuffled


def test_player_service_immediate_play(mock_audio_engine, mock_library_service, mock_config):
    """Verify immediate play loads and plays track synchronously."""
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    state = service.play("/music/song1.flac", playlist_id="all", immediate=True)

    mock_audio_engine.load.assert_called_with("/music/song1.flac")
    mock_audio_engine.play.assert_called_once()
    assert service.current_path == "/music/song1.flac"
    assert state["track"]["title"] == "song1.flac"


def test_player_service_next_and_prev_navigation(mock_audio_engine, mock_library_service, mock_config):
    """Verify next_track and prev_track navigation with O(1) lookups."""
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    service.play("/music/song1.flac", playlist_id="all", immediate=True)

    # Next track
    service.next_track(user_initiated=True)
    assert service.current_path == "/music/song2.flac"

    service.next_track(user_initiated=True)
    assert service.current_path == "/music/song3.flac"

    # User skip from end wraps to 0
    service.next_track(user_initiated=True)
    assert service.current_path == "/music/song1.flac"

    # Previous track from 0 wraps to end
    service.prev_track()
    assert service.current_path == "/music/song3.flac"


def test_player_service_prev_track_seek_guard(mock_audio_engine, mock_library_service, mock_config):
    """Verify prev_track seeks to 0.0 if track has been playing for > 3.0 seconds."""
    mock_audio_engine.get_state.return_value = {
        "is_playing": True,
        "position_seconds": 5.2,
        "duration_seconds": 180.0,
    }
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    service.play("/music/song2.flac", playlist_id="all", immediate=True)

    service.prev_track()
    mock_audio_engine.seek.assert_called_with(0.0)
    # Track should not change
    assert service.current_path == "/music/song2.flac"


def test_player_service_insert_play_next(mock_audio_engine, mock_library_service, mock_config):
    """Verify insert_play_next queues track directly after current_path."""
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    service.play("/music/song1.flac", playlist_id="all", immediate=True)

    res = service.insert_play_next("/music/song_bonus.flac")
    assert res["status"] == "success"
    assert service.normal_playlist[1] == "/music/song_bonus.flac"
    assert service._normal_index_map["/music/song_bonus.flac"] == 1


def test_player_service_auto_skip_consecutive_failure_limit(mock_audio_engine, mock_library_service, mock_config):
    """Verify consecutive load failure guard stops playback after 10 failures."""
    mock_audio_engine.load.side_effect = OSError("Corrupted audio file")
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    service.current_path = "/music/bad.flac"

    for _ in range(11):
        service._handle_load_failure("/music/bad.flac", service._load_token, OSError("Corrupted audio"))

    mock_audio_engine.stop.assert_called()


def test_player_service_playlist_scope_switching_regression(mock_audio_engine, mock_library_service, mock_config):
    """Regression test: switching playlists must reload playlist tracks and confine next_track to that playlist."""
    mock_library_service.get_all_track_paths.side_effect = lambda favorites_only=False, playlist_id=None, **kwargs: (
        ["/fav/fav1.flac", "/fav/fav2.flac"] if (favorites_only or playlist_id == "favorites")
        else ["/all/song1.flac", "/all/song2.flac", "/all/song3.flac"]
    )
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)

    # 1. Play in 'all' playlist (3 tracks)
    service.play("/all/song1.flac", playlist_id="all", immediate=True)
    assert len(service.normal_playlist) == 3
    assert service.loaded_playlist_id == "all"

    # 2. Switch and play in 'favorites' playlist (2 tracks)
    service.play("/fav/fav1.flac", playlist_id="favorites", immediate=True)
    assert len(service.normal_playlist) == 2
    assert service.loaded_playlist_id == "favorites"
    assert service.normal_playlist == ["/fav/fav1.flac", "/fav/fav2.flac"]

    # 3. Next track must stay inside favorites
    service.next_track(user_initiated=True)
    assert service.current_path == "/fav/fav2.flac"

    # 4. Next track again must wrap around inside favorites
    service.next_track(user_initiated=True)
    assert service.current_path == "/fav/fav1.flac"


def test_player_service_reshuffle_on_toggle(mock_audio_engine, mock_library_service, mock_config):
    """Verify toggling shuffle produces a fresh random permutation while retaining active track at index 0."""
    tracks = [f"/music/song_{i}.flac" for i in range(20)]
    mock_library_service.get_all_track_paths.return_value = tracks
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    service.play("/music/song_0.flac", playlist_id="all", immediate=True)

    # 1. Enable shuffle run 1
    service.set_shuffle(True)
    order1 = list(service.shuffled_playlist)
    assert order1[0] == "/music/song_0.flac"
    assert len(order1) == 20

    # 2. Disable shuffle
    service.set_shuffle(False)
    assert service.config.get("shuffle") is False

    # 3. Enable shuffle run 2 - must generate new permutation
    service.set_shuffle(True)
    order2 = list(service.shuffled_playlist)
    assert order2[0] == "/music/song_0.flac"
    assert len(order2) == 20

    # Probability of 20 items having identical random shuffle is 1/(19!) ~ 0
    assert order1 != order2, "Toggling shuffle on must generate a fresh shuffle permutation"


def test_player_service_queue_operations(mock_audio_engine, mock_library_service, mock_config):
    """Verify get_queue, remove_from_queue, and clear_queue work reliably."""
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    service.play("/music/song1.flac", playlist_id="all", immediate=True)

    # 1. Initially user queue is empty, upcoming contains song2 and song3
    q = service.get_queue()
    assert q["current"]["path"] == "/music/song1.flac"
    assert len(q["user_queue"]) == 0
    assert len(q["upcoming"]) == 2
    assert q["upcoming"][0]["path"] == "/music/song2.flac"

    # 2. Queue bonus tracks
    service.insert_play_next("/music/bonus1.flac")
    service.insert_play_next("/music/bonus2.flac")

    q = service.get_queue()
    assert len(q["user_queue"]) == 2
    assert q["user_queue"][0]["path"] == "/music/bonus1.flac"
    assert q["user_queue"][1]["path"] == "/music/bonus2.flac"
    assert q["upcoming"][0]["path"] == "/music/song2.flac"

    # 3. Remove bonus1 from queue
    service.remove_from_queue("/music/bonus1.flac")
    q = service.get_queue()
    assert len(q["user_queue"]) == 1
    assert q["user_queue"][0]["path"] == "/music/bonus2.flac"

    # 4. Clear queue
    service.clear_queue()
    q = service.get_queue()
    assert len(q["user_queue"]) == 0


def test_player_service_get_queue_batch_performance(mock_audio_engine, mock_library_service, mock_config):
    """Verify get_queue leverages batch metadata lookup instead of N sequential single lookups."""
    mock_library_service.get_all_track_paths.return_value = [f"/music/song{i}.flac" for i in range(50)]
    service = PlayerService(mock_audio_engine, mock_library_service, mock_config)
    service.play("/music/song0.flac", playlist_id="all", immediate=True)

    mock_library_service.get_tracks_by_paths.reset_mock()
    q = service.get_queue(limit=20)

    assert len(q["upcoming"]) == 20
    assert mock_library_service.get_tracks_by_paths.called
    assert mock_library_service.get_tracks_by_paths.call_count == 1
    call_args = mock_library_service.get_tracks_by_paths.call_args[0][0]
    assert len(call_args) == 20


