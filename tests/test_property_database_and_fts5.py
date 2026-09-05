import os
import gc
import tempfile
import sqlite3
from contextlib import contextmanager
import pytest
from hypothesis import given, settings, strategies as st
from backend.storage.database import Database


@contextmanager
def ephemeral_db():
    """Context manager providing a clean, isolated database for each hypothesis example."""
    old_instance = Database._instance
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "hypothesis_ephemeral.db")
    Database._instance = None
    db = Database(db_path=db_path)
    try:
        yield db
    finally:
        db.close()
        gc.collect()
        Database._instance = old_instance
        try:
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except OSError as ex:
            import logging
            logging.getLogger(__name__).debug("Cleanup directory notice: %s", ex)


@pytest.fixture(scope="module")
def module_fts_db(tmp_path_factory):
    """Shared read-only FTS database for search queries across hypothesis executions."""
    td = tmp_path_factory.mktemp("fts_module")
    db_path = os.path.join(str(td), "module_fts.db")
    db = Database(db_path)
    db.insert_track({"path": "/m/1.flac", "title": "Bohemian Rhapsody", "artist": "Queen", "album": "Opera"})
    db.insert_track({"path": "/m/2.flac", "title": "Rolling in the Deep", "artist": "Adele", "album": "21"})
    db.insert_track({"path": "/m/3.flac", "title": "Tiếng Chim Hót", "artist": "Various", "album": "Nature"})
    yield db
    db.close()
    gc.collect()


@given(search_query=st.text(max_size=200))
@settings(max_examples=80, deadline=None)
def test_property_fts5_formatting_never_crashes(search_query: str):
    """Invariant: _format_fts_query handles any arbitrary text without unhandled exceptions."""
    db = Database.__new__(Database)
    db._has_fts = True
    formatted = db._format_fts_query(search_query)

    if formatted is not None:
        assert isinstance(formatted, str)
        tokens = formatted.split()
        for tok in tokens:
            assert tok.startswith('"')
            assert tok.endswith('"*')


@given(raw_search=st.text(max_size=100))
@settings(max_examples=60, deadline=None)
def test_property_database_fts5_search_safety(module_fts_db, raw_search: str):
    """Invariant: Arbitrary search text never induces sqlite3 syntax or injection errors."""
    try:
        results = module_fts_db.get_tracks_paginated(offset=0, limit=20, search=raw_search)
        assert isinstance(results, list)
    except sqlite3.OperationalError as ex:
        pytest.fail(f"FTS5 or SQL syntax error on search='{raw_search}': {ex}")


@given(
    track_count=st.integers(min_value=5, max_value=20),
    page_size=st.integers(min_value=2, max_value=6),
)
@settings(max_examples=20, deadline=None)
def test_property_pagination_partition_completeness(track_count: int, page_size: int):
    """Invariant: Paginated queries cleanly partition the dataset without duplicates or drops."""
    with ephemeral_db() as db:
        for i in range(track_count):
            db.insert_track({
                "path": f"/music/track_{i:03d}.flac",
                "title": f"Song {i:03d}",
                "artist": "Artist A",
                "album": "Album A",
                "duration": 180.0,
            })

        all_collected_paths = []
        offset = 0
        while offset < track_count:
            page = db.get_tracks_paginated(offset=offset, limit=page_size, sort_by="title", sort_dir="ASC")
            if not page:
                break
            all_collected_paths.extend(t["path"] for t in page)
            offset += page_size

        assert len(all_collected_paths) == track_count
        assert len(set(all_collected_paths)) == track_count


@given(
    title=st.text(min_size=1, max_size=40).filter(lambda s: "\x00" not in s),
    artist=st.text(min_size=1, max_size=40).filter(lambda s: "\x00" not in s),
    duration=st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=25, deadline=None)
def test_property_track_upsert_idempotence(title: str, artist: str, duration: float):
    """Invariant: Updating the same track path modifies fields without duplicating rows."""
    with ephemeral_db() as db:
        track_path = "/music/idempotent_test.flac"
        track_payload = {
            "path": track_path,
            "title": title,
            "artist": artist,
            "album": "Fixed Album",
            "duration": duration,
        }

        db.insert_track(track_payload)
        count_before = db.get_track_count()

        track_payload["title"] = title + "_updated"
        db.insert_track(track_payload)
        count_after = db.get_track_count()

        assert count_before == count_after
        retrieved = db.get_track_by_path(track_path)
        assert retrieved is not None
        assert retrieved["title"] == title + "_updated"
