import os
import pytest
from backend.storage.database import Database


def test_database_chunked_batch_paths(temp_db):
    """Verify get_tracks_by_paths chunks requests > 500 without SQLite variable overflow."""
    # Generate 650 synthetic track records
    tracks = []
    for i in range(650):
        tracks.append({
            "path": f"C:\\Music\\Album_{i // 50}\\track_{i:04d}.flac",
            "title": f"Song {i}",
            "artist": f"Artist {i // 10}",
            "album": f"Album {i // 50}",
            "duration": 180.0,
            "samplerate": 44100,
            "bit_depth": 16,
            "channels": 2,
            "format": "FLAC",
            "cover_hash": f"hash_{i // 50}",
            "mtime": 1700000000.0 + i,
            "size": 25000000
        })

    temp_db.bulk_insert_tracks(tracks)
    all_paths = [t["path"] for t in tracks]

    # Query all 650 paths simultaneously
    batch_result = temp_db.get_tracks_by_paths(all_paths)
    assert len(batch_result) == 650
    assert batch_result[all_paths[0]]["title"] == "Song 0"
    assert batch_result[all_paths[649]]["title"] == "Song 649"

    # Query with empty list returns empty dict
    assert temp_db.get_tracks_by_paths([]) == {}


def test_database_albums_aggregation(temp_db, sample_track_batch):
    """Verify get_albums returns unique albums with accurate track counts."""
    temp_db.bulk_insert_tracks(sample_track_batch)

    albums = temp_db.get_albums()
    assert len(albums) == 3

    album_names = {a["album"] for a in albums}
    assert "Hotel California" in album_names
    assert "Beethoven: The Symphonies" in album_names
    assert "M-TP Collection" in album_names

    for a in albums:
        assert a["track_count"] == 1


def test_database_update_tracks_in_folder(temp_db, sample_track_batch):
    """Verify update_tracks_in_folder updates matching prefix tracks."""
    temp_db.bulk_insert_tracks(sample_track_batch)

    # Update rock folder tracks
    temp_db.update_tracks_in_folder("C:\\Music\\Rock", {"artist": "Eagles Remastered"})

    rock_track = temp_db.get_track_by_path("C:\\Music\\Rock\\Hotel_California.flac")
    assert rock_track is not None
    assert rock_track["artist"] == "Eagles Remastered"

    # Non-rock track should remain unchanged
    vpop_track = temp_db.get_track_by_path("C:\\Music\\VPop\\Em_Cua_Ngay_Hom_Qua.mp3")
    assert vpop_track is not None
    assert vpop_track["artist"] == "Sơn Tùng M-TP"


def test_database_fts5_special_characters_robustness(temp_db, sample_track_batch):
    """Verify FTS5 search handles malicious or special regex/wildcard syntax safely without errors."""
    temp_db.bulk_insert_tracks(sample_track_batch)

    dangerous_searches = [
        '""',
        '"Hotel" OR "NonExistent"',
        "Beethoven*",
        "NOT AND OR",
        "(Sơn Tùng)",
        "***",
        "''",
        "---",
        "title:Hotel"
    ]

    for term in dangerous_searches:
        # Must execute without throwing sqlite3.OperationalError
        results = temp_db.get_tracks_paginated(0, 10, search=term)
        assert isinstance(results, list)
        count = temp_db.get_track_count(search=term)
        assert isinstance(count, int)
