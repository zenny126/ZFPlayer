from unittest.mock import MagicMock
import pytest
from hypothesis import given, settings, strategies as st
from backend.services.player_service import PlayerService


def create_mock_player_service():
    """Helper creating an isolated PlayerService with mocked dependencies."""
    audio_engine = MagicMock()
    audio_engine.get_state.return_value = {
        "is_playing": False,
        "position_seconds": 0.0,
        "duration_seconds": 200.0,
        "state": "IDLE",
    }
    audio_engine.state.name = "IDLE"

    config = MagicMock()
    config_store = {"repeat": "off", "shuffle": False}
    config.get.side_effect = lambda k, d=None: config_store.get(k, d)
    config.set.side_effect = lambda k, v: config_store.__setitem__(k, v)

    library_service = MagicMock()
    library_service.get_track_info.side_effect = lambda p: {
        "path": p,
        "title": p.split("/")[-1],
        "artist": "Mock Artist",
        "album": "Mock Album",
        "duration": 200.0,
    }

    service = PlayerService(audio_engine, config, library_service)
    service._config_store = config_store
    return service


@given(
    paths=st.lists(
        st.text(min_size=1, max_size=30).filter(lambda s: "\x00" not in s),
        min_size=2,
        max_size=30,
        unique=True,
    )
)
@settings(max_examples=40, deadline=None)
def test_property_playlist_index_map_bijection(paths: list[str]):
    """Invariant: _normal_index_map is a strict bijection mapping each path to its exact index."""
    service = create_mock_player_service()
    service._set_normal_playlist(paths)

    assert len(service._normal_index_map) == len(paths)
    for idx, path in enumerate(paths):
        assert service._normal_index_map[path] == idx


@given(
    paths=st.lists(
        st.integers(min_value=1, max_value=1000).map(lambda i: f"/music/track_{i}.flac"),
        min_size=3,
        max_size=25,
        unique=True,
    ),
    curr_idx=st.integers(min_value=0, max_value=24),
)
@settings(max_examples=35, deadline=None)
def test_property_reshuffle_element_conservation(paths: list[str], curr_idx: int):
    """Invariant: Reshuffling conserves all playlist elements and anchors current track at index 0."""
    service = create_mock_player_service()
    service._set_normal_playlist(paths)

    valid_curr_idx = curr_idx % len(paths)
    current_path = paths[valid_curr_idx]

    service._reshuffle_playlist(current_path=current_path)

    assert len(service.shuffled_playlist) == len(paths)
    assert set(service.shuffled_playlist) == set(paths)
    assert service.shuffled_playlist[0] == current_path


@given(
    paths=st.lists(
        st.integers(min_value=1, max_value=1000).map(lambda i: f"/music/track_{i}.flac"),
        min_size=4,
        max_size=20,
        unique=True,
    ),
    steps=st.integers(min_value=1, max_value=15),
    repeat_mode=st.sampled_from(["off", "all", "one"]),
)
@settings(max_examples=30, deadline=None)
def test_property_navigation_bounds_invariant(paths: list[str], steps: int, repeat_mode: str):
    """Invariant: Repeated navigation operations never exceed playlist boundaries."""
    service = create_mock_player_service()
    service._config_store["repeat"] = repeat_mode
    service._set_normal_playlist(paths)
    service.current_path = paths[0]
    service.current_playlist_index = 0

    for _ in range(steps):
        service.next_track(user_initiated=True)
        if service.current_path:
            assert service.current_path in paths
            assert 0 <= service.current_playlist_index < len(paths)

    for _ in range(steps):
        service.prev_track()
        if service.current_path:
            assert service.current_path in paths
            assert 0 <= service.current_playlist_index < len(paths)
