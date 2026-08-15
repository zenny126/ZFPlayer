import os
import pytest
from unittest.mock import MagicMock, patch
from backend.workers.scanner import LibraryScanner


def test_scanner_filters_supported_audio_formats(temp_dir, temp_db, temp_cache):
    """Verify scanner only indexes supported audio extensions and skips others."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)
    
    # Create test files
    valid_file = os.path.join(temp_dir, "song.flac")
    invalid_file = os.path.join(temp_dir, "lyrics.lrc")
    image_file = os.path.join(temp_dir, "cover.jpg")
    
    for p in [valid_file, invalid_file, image_file]:
        with open(p, "wb") as f:
            f.write(b"dummy_data")
            
    mock_extracted = {
        'path': valid_file,
        'title': 'Test Song',
        'artist': 'Test Artist',
        'album': 'Test Album',
        'duration': 120.0,
        'samplerate': 44100,
        'bit_depth': 16,
        'channels': 2,
        'format': 'FLAC',
        'cover_hash': None
    }

    with patch.object(scanner.metadata_worker, 'extract', return_value=mock_extracted):
        scanner.scan([temp_dir], handle_deletions=False)
        
    tracks = temp_db.get_all_tracks()
    assert len(tracks) == 1
    assert tracks[0]['path'] == valid_file


def test_scanner_incremental_skips_unchanged_files(temp_dir, temp_db, temp_cache):
    """Verify incremental scanner skips files that have unchanged mtime and size."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)
    
    song_path = os.path.join(temp_dir, "audio.wav")
    with open(song_path, "wb") as f:
        f.write(b"RIFF_AUDIO_DATA_12345")
        
    mtime = os.path.getmtime(song_path)
    size = os.path.getsize(song_path)

    # Insert existing track record
    temp_db.insert_track({
        'path': song_path,
        'title': 'Unchanged Song',
        'artist': 'Artist',
        'album': 'Album',
        'duration': 60.0,
        'samplerate': 44100,
        'bit_depth': 16,
        'channels': 2,
        'format': 'WAV',
        'cover_hash': None,
        'mtime': mtime,
        'size': size
    })

    # Run scan with metadata extractor mock
    with patch.object(scanner.metadata_worker, 'extract') as mock_extract:
        scanner.scan([temp_dir], handle_deletions=False)
        # extract should NOT be called because mtime and size match
        mock_extract.assert_not_called()


def test_scanner_usb_disconnect_safety_guards(temp_db, temp_cache):
    """Verify disconnected/unmounted USB drives do not trigger accidental library deletion."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)
    
    # Existing tracks residing on a disconnected USB drive 'E:\Music'
    usb_path = "E:\\Music\\Album\\Song.flac"
    temp_db.insert_track({
        'path': usb_path,
        'title': 'USB Song',
        'artist': 'Artist',
        'album': 'Album',
        'duration': 180.0,
        'samplerate': 44100,
        'bit_depth': 16,
        'channels': 2,
        'format': 'FLAC',
        'cover_hash': None,
        'mtime': 1700000000.0,
        'size': 20000000
    })

    # Scan with non-existent / disconnected folder path
    scanner.scan(["E:\\Music"], handle_deletions=True)
    
    # Track must still be safely preserved in database
    tracks = temp_db.get_all_tracks()
    assert len(tracks) == 1
    assert tracks[0]['path'] == usb_path


def test_scanner_deletes_removed_files_on_mounted_drive(temp_dir, temp_db, temp_cache):
    """Verify deleted files are removed from database if the parent folder is accessible and mounted."""
    scanner = LibraryScanner(database=temp_db, cache_manager=temp_cache)
    
    deleted_path = os.path.join(temp_dir, "deleted_song.flac")
    temp_db.insert_track({
        'path': deleted_path,
        'title': 'Deleted Song',
        'artist': 'Artist',
        'album': 'Album',
        'duration': 180.0,
        'samplerate': 44100,
        'bit_depth': 16,
        'channels': 2,
        'format': 'FLAC',
        'cover_hash': None,
        'mtime': 1700000000.0,
        'size': 20000000
    })

    # temp_dir exists but deleted_song.flac does not exist on disk
    scanner.scan([temp_dir], handle_deletions=True)
    
    # Must be purged from database
    tracks = temp_db.get_all_tracks()
    assert len(tracks) == 0
