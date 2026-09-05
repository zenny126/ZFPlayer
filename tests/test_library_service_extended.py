import pytest
from unittest.mock import MagicMock
from backend.services.library_service import LibraryService


@pytest.fixture
def lib_service(temp_db, temp_cache, sample_track_batch):
    """Fixture providing LibraryService with populated sample tracks."""
    temp_db.bulk_insert_tracks(sample_track_batch)
    mock_scanner = MagicMock()
    return LibraryService(database=temp_db, cache_manager=temp_cache, scanner=mock_scanner)


def test_library_service_sorting_by_duration(lib_service):
    """Verify get_tracks sorts correctly by duration ASC."""
    tracks = lib_service.get_tracks(offset=0, limit=10, sort_by="duration", sort_dir="ASC")
    assert len(tracks) == 3
    # 234.0 (Sơn Tùng) < 391.0 (Eagles) < 432.0 (Beethoven)
    assert tracks[0]["duration"] == 234.0
    assert tracks[2]["duration"] == 432.0


def test_library_service_sorting_by_artist(lib_service):
    """Verify get_tracks sorts correctly by artist ASC."""
    tracks = lib_service.get_tracks(offset=0, limit=10, sort_by="artist", sort_dir="ASC")
    assert len(tracks) == 3
    assert tracks[0]["artist"] == "Eagles"
    assert tracks[1]["artist"] == "Ludwig van Beethoven"
    assert tracks[2]["artist"] == "Sơn Tùng M-TP"


def test_library_service_sorting_by_album(lib_service):
    """Verify get_tracks sorts correctly by album DESC."""
    tracks = lib_service.get_tracks(offset=0, limit=10, sort_by="album", sort_dir="DESC")
    assert len(tracks) == 3
    assert tracks[0]["album"] == "M-TP Collection"
    assert tracks[2]["album"] == "Beethoven: The Symphonies"


def test_library_service_sort_direction_asc_desc(lib_service):
    """Verify get_tracks reverses order between ASC and DESC."""
    asc_tracks = lib_service.get_tracks(offset=0, limit=10, sort_by="title", sort_dir="ASC")
    desc_tracks = lib_service.get_tracks(offset=0, limit=10, sort_by="title", sort_dir="DESC")
    assert asc_tracks[0]["title"] == desc_tracks[-1]["title"]


def test_library_service_filter_favorites(lib_service, sample_track_batch):
    """Verify get_tracks favorites_only filter returns exclusively liked tracks."""
    fav_path = sample_track_batch[0]["path"]
    lib_service.update_track(fav_path, {"is_liked": 1})

    favs = lib_service.get_tracks(offset=0, limit=10, favorites_only=True)
    assert len(favs) == 1
    assert favs[0]["path"] == fav_path


def test_library_service_album_scope_query(lib_service):
    """Verify get_tracks filters accurately using album: prefix scope."""
    album_tracks = lib_service.get_tracks(offset=0, limit=10, playlist_id="album:Hotel California")
    assert len(album_tracks) == 1
    assert album_tracks[0]["album"] == "Hotel California"


def test_library_service_playlist_lifecycle(lib_service, sample_track_batch):
    """Verify creating, adding tracks, and deleting playlists in LibraryService."""
    pid = lib_service.create_playlist("Acoustic Vibes")
    assert isinstance(pid, int)

    track_path = sample_track_batch[0]["path"]
    lib_service.add_track_to_playlist(pid, track_path)

    pl_tracks = lib_service.get_tracks(offset=0, limit=10, playlist_id=str(pid))
    assert len(pl_tracks) == 1
    assert pl_tracks[0]["path"] == track_path

    lib_service.remove_track_from_playlist(pid, track_path)
    pl_empty = lib_service.get_tracks(offset=0, limit=10, playlist_id=str(pid))
    assert len(pl_empty) == 0

    lib_service.delete_playlist(pid)
    playlists = lib_service.get_playlists()
    assert not any(p["id"] == pid for p in playlists)


def test_library_service_recently_played_query(lib_service, sample_track_batch):
    """Verify recently played tracks query returns tracks with last_played timestamp."""
    p = sample_track_batch[1]["path"]
    lib_service.db.update_last_played(p)

    recent = lib_service.get_recently_played(limit=5)
    assert len(recent) >= 1
    assert recent[0]["path"] == p


def test_library_service_get_all_track_paths(lib_service):
    """Verify get_all_track_paths returns all paths in ascending title order."""
    paths = lib_service.get_all_track_paths()
    assert len(paths) == 3
    assert all(isinstance(p, str) for p in paths)


def test_library_service_scan_progress_snapshot(lib_service):
    """Verify get_scan_progress returns a thread-safe copy of scanner state."""
    progress = lib_service.get_scan_progress()
    assert isinstance(progress, dict)
    assert "is_scanning" in progress
    assert "scanned" in progress
    assert "total" in progress
