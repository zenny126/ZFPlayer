import re
import pytest
from hypothesis import given, settings, strategies as st
from backend.models.track import Track
from backend.workers.lyrics_worker import LyricsWorker


# --- Strategies for Domain Types ---
safe_text_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=60,
).filter(lambda s: bool(s.strip()) and "\x00" not in s)


@given(
    path=safe_text_strategy,
    title=safe_text_strategy,
    artist=safe_text_strategy,
    album=safe_text_strategy,
    duration=st.floats(min_value=0.1, max_value=7200.0, allow_nan=False, allow_infinity=False),
    sample_rate=st.sampled_from([44100, 48000, 88200, 96000, 176400, 192000]),
    bit_depth=st.sampled_from([16, 24, 32]),
    channels=st.sampled_from([1, 2, 6]),
)
@settings(max_examples=50, deadline=None)
def test_property_track_serialization_roundtrip(
    path: str,
    title: str,
    artist: str,
    album: str,
    duration: float,
    sample_rate: int,
    bit_depth: int,
    channels: int,
):
    """Invariant: Deserializing a serialized Track returns an identical instance."""
    original = Track(
        path=path,
        title=title,
        artist=artist,
        album=album,
        duration=duration,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=channels,
    )

    serialized = original.to_dict()
    reconstructed = Track.from_dict(serialized)

    assert reconstructed == original
    assert reconstructed.path == original.path
    assert reconstructed.sample_rate == original.sample_rate


@given(
    artist=safe_text_strategy,
    title=safe_text_strategy,
    album=safe_text_strategy,
    duration=st.floats(min_value=1.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, deadline=None)
def test_property_lyrics_cache_key_normalization(
    artist: str,
    title: str,
    album: str,
    duration: float,
):
    """Invariant: Whitespace padding and casing differences yield identical SHA-256 cache keys."""
    worker = LyricsWorker.__new__(LyricsWorker)

    key1 = worker._get_cache_key(artist, title, album, duration)
    key2 = worker._get_cache_key(
        f"  {artist.upper()}  ",
        f"\t{title.lower()}\n",
        album,
        duration,
    )

    assert key1 == key2
    assert len(key1) == 64
    assert bool(re.match(r"^[0-9a-f]{64}$", key1))


@given(
    target_duration=st.floats(min_value=60.0, max_value=600.0, allow_nan=False, allow_infinity=False),
    best_offset=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    other_offset=st.floats(min_value=4.0, max_value=20.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=40, deadline=None)
def test_property_best_lrclib_match_selection(
    target_duration: float,
    best_offset: float,
    other_offset: float,
):
    """Invariant: _find_best_lrclib_match always chooses the candidate with closest duration <= 3.5s."""
    candidates = [
        {"duration": target_duration + other_offset, "syncedLyrics": "[00:01.00] Far match"},
        {"duration": target_duration + best_offset, "syncedLyrics": "[00:01.00] Closest match"},
    ]

    selected = LyricsWorker._find_best_lrclib_match(candidates, target_duration)
    assert selected == "[00:01.00] Closest match"


@given(
    target_duration=st.floats(min_value=60.0, max_value=600.0, allow_nan=False, allow_infinity=False),
    excessive_offset=st.floats(min_value=3.6, max_value=100.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=30, deadline=None)
def test_property_best_lrclib_match_rejects_exceeding_tolerance(
    target_duration: float,
    excessive_offset: float,
):
    """Invariant: Results with duration difference > 3.5s are strictly rejected."""
    candidates = [
        {"duration": target_duration + excessive_offset, "syncedLyrics": "[00:01.00] Out of tolerance"},
    ]

    selected = LyricsWorker._find_best_lrclib_match(candidates, target_duration)
    assert selected is None
