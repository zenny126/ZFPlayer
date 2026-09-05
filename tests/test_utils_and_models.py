import os
from pathlib import Path
import pytest
from backend.utils.path_utils import (
    get_bundle_dir,
    get_app_data_dir,
    get_config_path,
    get_db_path,
    get_cache_dir
)
from backend.models.track import Track


def test_path_utils_get_bundle_dir():
    """Verify get_bundle_dir returns an existing valid Path."""
    bundle = get_bundle_dir()
    assert isinstance(bundle, Path)
    assert bundle.exists()


def test_path_utils_get_app_data_dir():
    """Verify get_app_data_dir creates and returns a writable application directory."""
    app_data = get_app_data_dir()
    assert isinstance(app_data, Path)
    assert app_data.exists()
    assert os.access(app_data, os.W_OK)


def test_path_utils_derived_paths():
    """Verify get_config_path, get_db_path, and get_cache_dir resolve expected filenames."""
    cfg_p = get_config_path()
    assert cfg_p.endswith("config.json")

    db_p = get_db_path()
    assert db_p.endswith("library.db")

    cache_d = get_cache_dir()
    assert os.path.exists(cache_d)


def test_track_model_defaults():
    """Verify Track dataclass default values and types."""
    t = Track(path="C:\\Music\\test.flac")
    assert t.path == "C:\\Music\\test.flac"
    assert t.title == "Unknown"
    assert t.artist == "Unknown"
    assert t.album == "Unknown"
    assert t.sample_rate == 44100
    assert t.channels == 2
    assert t.is_liked == 0


def test_track_model_serialization_roundtrip():
    """Verify Track to_dict and from_dict bidirectional conversion."""
    original = Track(
        path="C:\\Music\\Song.flac",
        title="My Song",
        artist="Top Artist",
        album="Great Album",
        duration=210.5,
        cover_hash="hash9988",
        is_liked=1
    )
    d = original.to_dict()
    assert isinstance(d, dict)
    assert d["title"] == "My Song"
    assert d["is_liked"] == 1

    restored = Track.from_dict(d)
    assert restored.path == original.path
    assert restored.duration == original.duration
    assert restored.is_liked == original.is_liked


def test_track_model_partial_customization():
    """Verify Track model accepts explicit audio attributes."""
    t = Track(
        path="C:\\HiRes\\Track.flac",
        sample_rate=192000,
        bit_depth=24,
        channels=2,
        duration=360.0
    )
    assert t.sample_rate == 192000
    assert t.bit_depth == 24
    assert t.duration == 360.0


def test_path_utils_cache_subdirectories_creatable():
    """Verify subdirectories inside cache dir can be created safely."""
    cache_dir = Path(get_cache_dir())
    test_sub = cache_dir / "test_subfolder"
    test_sub.mkdir(parents=True, exist_ok=True)
    assert test_sub.exists()
    test_sub.rmdir()


def test_track_model_equality():
    """Verify Track dataclass value equality comparison."""
    t1 = Track(path="C:\\song.flac", title="Test")
    t2 = Track(path="C:\\song.flac", title="Test")
    assert t1 == t2


def test_path_utils_portable_mode_detection(temp_dir, monkeypatch):
    """Verify get_app_data_dir prioritizes portable markers next to the executable."""
    fake_exe = Path(temp_dir) / "bin" / "ZennyFLAC_Player.exe"
    fake_exe.parent.mkdir(parents=True, exist_ok=True)
    fake_exe.touch()

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(fake_exe))

    # Without portable marker, falls back to APPDATA
    normal_dir = get_app_data_dir()
    assert normal_dir != fake_exe.parent

    # With portable marker file 'portable.txt'
    marker = fake_exe.parent / "portable.txt"
    marker.touch()
    portable_dir = get_app_data_dir()
    assert portable_dir == fake_exe.parent

