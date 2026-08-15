import os
import sys
import tempfile
import pytest
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.storage.database import Database
from backend.storage.cache import CacheManager
from backend.storage.config import Config


@pytest.fixture
def temp_dir():
    """Provides an isolated temporary directory for test file operations."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def temp_db(temp_dir):
    """Provides an isolated SQLite Database instance."""
    Database._instance = None
    db_path = os.path.join(temp_dir, "test_zfplayer.db")
    db = Database(db_path=db_path)
    db.init()
    yield db
    db.close()
    Database._instance = None



@pytest.fixture
def temp_cache(temp_dir):
    """Provides an isolated CacheManager instance."""
    cache_dir = os.path.join(temp_dir, "cache")
    return CacheManager(cache_dir=cache_dir)


@pytest.fixture
def sample_track():
    """Standard sample track dictionary."""
    return {
        "path": "C:\\Music\\Adele\\21\\01_Rolling_in_the_Deep.flac",
        "title": "Rolling in the Deep",
        "artist": "Adele",
        "album": "21",
        "duration": 228.5,
        "samplerate": 96000,
        "bit_depth": 24,
        "channels": 2,
        "format": "FLAC",
        "cover_hash": "a1b2c3d4e5f6",
        "mtime": 1700000000.0,
        "size": 52428800
    }


@pytest.fixture
def sample_track_batch():
    """Batch of sample tracks for testing bulk operations and FTS."""
    return [
        {
            "path": "C:\\Music\\Rock\\Hotel_California.flac",
            "title": "Hotel California",
            "artist": "Eagles",
            "album": "Hotel California",
            "duration": 391.0,
            "samplerate": 192000,
            "bit_depth": 24,
            "channels": 2,
            "format": "FLAC",
            "cover_hash": "cover_eagles",
            "mtime": 1700000001.0,
            "size": 104857600
        },
        {
            "path": "C:\\Music\\Classical\\Beethoven_Symphony_No5.wav",
            "title": "Symphony No. 5 in C Minor, Op. 67",
            "artist": "Ludwig van Beethoven",
            "album": "Beethoven: The Symphonies",
            "duration": 432.0,
            "samplerate": 44100,
            "bit_depth": 16,
            "channels": 2,
            "format": "WAV",
            "cover_hash": "cover_beethoven",
            "mtime": 1700000002.0,
            "size": 75600000
        },
        {
            "path": "C:\\Music\\VPop\\Em_Cua_Ngay_Hom_Qua.mp3",
            "title": "Em Của Ngày Hôm Qua",
            "artist": "Sơn Tùng M-TP",
            "album": "M-TP Collection",
            "duration": 234.0,
            "samplerate": 44100,
            "bit_depth": 16,
            "channels": 2,
            "format": "MP3",
            "cover_hash": "cover_sontung",
            "mtime": 1700000003.0,
            "size": 8900000
        }
    ]


@pytest.fixture
def mock_audio_frames():
    """Generates 1024 frames of 2-channel float32 audio waveform."""
    t = np.linspace(0, 1, 1024, endpoint=False, dtype=np.float32)
    left = np.sin(2 * np.pi * 440 * t)  # 440 Hz Sine wave
    right = np.cos(2 * np.pi * 440 * t)
    return np.column_stack((left, right)).astype(np.float32)
