import os
import time
import pytest
from unittest.mock import MagicMock
from backend.workers.scanner import LibraryScanner
from backend.workers.metadata_worker import MetadataWorker


def test_scanner_walk_directory_filters_extensions(temp_dir, temp_db, temp_cache):
    """Verify _walk_directory_files includes only supported audio formats."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)

    # Create dummy files
    valid_files = ["song1.flac", "song2.wav", "song3.mp3", "song4.ogg"]
    invalid_files = ["notes.txt", "cover.jpg", "app.exe", "data.json"]

    for name in valid_files + invalid_files:
        p = os.path.join(temp_dir, name)
        with open(p, "w") as f:
            f.write("content")

    found = scanner._walk_directory_files(temp_dir)
    found_names = [os.path.basename(p) for p in found]

    assert len(found) == len(valid_files)
    for v in valid_files:
        assert v in found_names
    for iv in invalid_files:
        assert iv not in found_names


def test_scanner_stop_event_cancels_walk(temp_dir, temp_db, temp_cache):
    """Verify stop_event interrupts directory discovery immediately."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)
    scanner.stop_event.set()

    # Even with valid files, walk should exit early
    p = os.path.join(temp_dir, "test.flac")
    with open(p, "w") as f:
        f.write("data")

    found = scanner._walk_directory_files(temp_dir)
    assert len(found) == 0


def test_scanner_filter_unindexed_skips_matching_mtime_and_size(temp_dir, temp_db, temp_cache):
    """Verify _filter_unindexed_files skips files whose mtime and size match DB exactly."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)
    file_path = os.path.join(temp_dir, "song.flac")
    with open(file_path, "w") as f:
        f.write("test content")

    mtime = os.path.getmtime(file_path)
    size = os.path.getsize(file_path)

    existing = {
        file_path: {"mtime": mtime, "size": size}
    }

    to_process = scanner._filter_unindexed_files([file_path], existing)
    assert len(to_process) == 0


def test_scanner_filter_unindexed_detects_mtime_change(temp_dir, temp_db, temp_cache):
    """Verify _filter_unindexed_files schedules reindexing when mtime changes."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)
    file_path = os.path.join(temp_dir, "song.flac")
    with open(file_path, "w") as f:
        f.write("test content")

    mtime = os.path.getmtime(file_path)
    size = os.path.getsize(file_path)

    # Existing DB record has older mtime
    existing = {
        file_path: {"mtime": mtime - 100, "size": size}
    }

    to_process = scanner._filter_unindexed_files([file_path], existing)
    assert len(to_process) == 1
    assert to_process[0][0] == file_path


def test_scanner_metadata_worker_fallback_on_corrupt_file(temp_dir):
    """Verify MetadataWorker handles empty/corrupt audio files without raising uncaught exceptions."""
    mw = MetadataWorker()
    corrupt_path = os.path.join(temp_dir, "broken.flac")
    with open(corrupt_path, "w") as f:
        f.write("not an audio file")

    res = mw.extract(corrupt_path)
    # Must return dict with filename fallback or None, without crashing
    assert res is None or isinstance(res, dict)


def test_scanner_flush_batch_inserts_tracks(temp_db, temp_cache, sample_track_batch):
    """Verify _flush_batch inserts track metadata and invokes lyrics enqueuing."""
    mock_lyrics = MagicMock()
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache, lyrics_worker=mock_lyrics)

    batch_copy = list(sample_track_batch)
    scanner._flush_batch(batch_copy)

    # Verify tracks inserted into database
    paths = temp_db.get_all_track_paths()
    assert len(paths) == len(sample_track_batch)

    # Verify lyrics enqueued
    mock_lyrics.enqueue_tracks.assert_called_once_with(sample_track_batch, priority=False)


def test_scanner_nonexistent_directory_handled(temp_db, temp_cache):
    """Verify _walk_directory_files on nonexistent path returns empty list safely."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)
    assert scanner._walk_directory_files("Z:\\NonExistent\\Music") == []


def test_scanner_deletion_preserves_unmounted_drives(temp_db, temp_cache):
    """Verify _handle_deletions never removes tracks belonging to unmounted drives."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)

    existing_tracks = {
        "E:\\Music\\Drive_E_Song.flac": {"mtime": 1000, "size": 5000},
        "C:\\Music\\Drive_C_Song.flac": {"mtime": 1000, "size": 5000}
    }

    # Only C:\Music is mounted and accessible; E: is detached
    accessible_dirs = ["C:\\Music"]
    disk_paths = set()  # C drive track was deleted on disk

    # Should only delete C:\Music track, leaving E:\Music intact
    del_mock = MagicMock()
    temp_db.delete_tracks_bulk = del_mock

    scanner._handle_deletions(accessible_dirs, existing_tracks, disk_paths)
    del_mock.assert_called_once_with(["C:\\Music\\Drive_C_Song.flac"])
