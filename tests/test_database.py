import os
import time
import sqlite3
import pytest
from datetime import datetime, timedelta
from backend.storage.database import Database


def test_database_schema_initialization(temp_db):
    """Verify that tables, indexes and FTS5 are created on database init."""
    conn = temp_db._get_conn()
    cursor = conn.cursor()
    
    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row['name'] for row in cursor.fetchall()}
    assert 'tracks' in tables
    assert 'playlists' in tables
    assert 'playlist_tracks' in tables
    assert 'lyrics_cache' in tables
    
    # Check FTS index table exists
    if getattr(temp_db, '_has_fts', False):
        assert 'tracks_fts' in tables


def test_track_crud_operations(temp_db, sample_track):
    """Verify single track insert, fetch, update like, and deletion."""
    # 1. Insert Track
    temp_db.insert_track(sample_track)
    
    # 2. Fetch all tracks
    tracks = temp_db.get_all_tracks()
    assert len(tracks) == 1
    t = tracks[0]
    assert t['title'] == "Rolling in the Deep"
    assert t['artist'] == "Adele"
    assert t['is_liked'] == 0


    # 3. Toggle Like via update_track
    temp_db.update_track(sample_track['path'], {'is_liked': 1})
    favs = temp_db.get_tracks_paginated(0, 10, is_favorites=True)
    assert len(favs) == 1
    assert favs[0]['path'] == sample_track['path']
    assert favs[0]['is_liked'] == 1

    # 4. Update last played
    temp_db.update_last_played(sample_track['path'])
    recents = temp_db.get_recently_played(limit=10)
    assert len(recents) == 1
    assert recents[0]['last_played'] is not None

    # 5. Delete Track
    temp_db.delete_track(sample_track['path'])
    assert len(temp_db.get_all_tracks()) == 0


def test_bulk_track_insert_and_delete(temp_db, sample_track_batch):
    """Verify bulk insert and bulk delete operations."""
    temp_db.bulk_insert_tracks(sample_track_batch)
    assert temp_db.get_track_count() == 3
    
    paths_to_delete = [sample_track_batch[0]['path'], sample_track_batch[1]['path']]
    temp_db.delete_tracks_bulk(paths_to_delete)
    
    remaining = temp_db.get_all_tracks()
    assert len(remaining) == 1
    assert remaining[0]['path'] == sample_track_batch[2]['path']


def test_playlist_management_and_bulk_add(temp_db, sample_track_batch):
    """Verify playlist creation, bulk adding tracks, ordering, and deletion."""
    temp_db.bulk_insert_tracks(sample_track_batch)
    
    # 1. Create Playlist
    p_id = temp_db.create_playlist("My Hi-Res Playlist")
    assert p_id is not None
    
    # 2. Bulk Add Tracks to Playlist
    paths = [t['path'] for t in sample_track_batch]
    added_count = temp_db.add_tracks_to_playlist_bulk(p_id, paths)
    assert added_count == 3
    
    # 3. Fetch Playlist Tracks and verify order & metadata
    p_tracks = temp_db.get_tracks_paginated(0, 10, playlist_id=p_id)
    assert len(p_tracks) == 3
    assert p_tracks[0]['title'] == "Hotel California"
    assert p_tracks[1]['title'] == "Symphony No. 5 in C Minor, Op. 67"
    assert p_tracks[2]['title'] == "Em Của Ngày Hôm Qua"

    # 4. Remove single track from playlist
    temp_db.remove_track_from_playlist(p_id, paths[0])
    p_tracks_after = temp_db.get_tracks_paginated(0, 10, playlist_id=p_id)
    assert len(p_tracks_after) == 2

    # 5. Rename Playlist
    temp_db.rename_playlist(p_id, "Renamed Playlist")
    playlists = temp_db.get_playlists()
    p_dict = {p['id']: p['name'] for p in playlists}
    assert p_dict[p_id] == "Renamed Playlist"

    # 6. Delete Playlist
    temp_db.delete_playlist(p_id)
    assert len(temp_db.get_tracks_paginated(0, 10, playlist_id=p_id)) == 0


def test_fts5_full_text_search(temp_db, sample_track_batch):
    """Verify FTS5 full-text search matching across title, artist, and album."""
    temp_db.bulk_insert_tracks(sample_track_batch)
    
    # Search by artist keyword
    results_eagles = temp_db.get_tracks_paginated(0, 10, search="Eagles")
    assert len(results_eagles) == 1
    assert results_eagles[0]['artist'] == "Eagles"

    # Search with Vietnamese diacritics
    results_sontung = temp_db.get_tracks_paginated(0, 10, search="Sơn Tùng")
    assert len(results_sontung) == 1
    assert results_sontung[0]['title'] == "Em Của Ngày Hôm Qua"

    # Search partial word
    results_beethoven = temp_db.get_tracks_paginated(0, 10, search="Symphony")
    assert len(results_beethoven) == 1
    assert results_beethoven[0]['artist'] == "Ludwig van Beethoven"



def test_lyrics_cache_and_negative_ttl(temp_db):
    """Verify lyrics cache persistence, negative caching [NO_LYRICS], and 7-day TTL expiration."""
    cache_key = "test_artist_test_title_test_album"
    
    # 1. Normal lyrics save & fetch
    temp_db.save_lyrics(cache_key, "[00:10.00] Hello World", "Hello World", "lrclib")
    lyrics = temp_db.get_lyrics(cache_key)
    assert lyrics is not None
    assert lyrics['synced_lyrics'] == "[00:10.00] Hello World"
    assert lyrics['source'] == "lrclib"

    # 2. Negative Cache Save
    neg_key = "unknown_artist_unknown_song"
    temp_db.save_lyrics(neg_key, "[NO_LYRICS]", "", "none")
    neg_lyrics = temp_db.get_lyrics(neg_key)
    assert neg_lyrics is not None
    assert neg_lyrics['synced_lyrics'] == "[NO_LYRICS]"

    # 3. Simulate expired negative cache (older than 7 days)
    conn = temp_db._get_conn()
    cursor = conn.cursor()
    expired_date = (datetime.utcnow() - timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE lyrics_cache SET fetched_at = ? WHERE cache_key = ?", (expired_date, neg_key))
    conn.commit()

    # Fetching expired negative cache must return None (triggering refetch)
    expired_result = temp_db.get_lyrics(neg_key)
    assert expired_result is None


def test_database_self_healing_intact(temp_dir):
    """Verify _check_and_heal_database passes when database is healthy."""
    Database._instance = None
    db_path = os.path.join(temp_dir, "healthy.db")
    db = Database(db_path=db_path)
    db.init()
    
    # Running check on healthy database should not alter or delete file
    db._check_and_heal_database()
    assert os.path.exists(db_path)
    db.close()
    Database._instance = None


def test_database_self_healing_on_corruption(temp_dir):
    """Verify _check_and_heal_database auto-heals when SQLite database header is corrupted."""
    Database._instance = None
    db_path = os.path.join(temp_dir, "corrupt.db")
    
    # Create corrupted file with invalid binary header
    with open(db_path, "wb") as f:
        f.write(b"CORRUPTED_NON_SQLITE_BINARY_DATA_GARBAGE_HEADER")
        
    db = Database(db_path=db_path)
    # Self-heal should detect corruption, backup corrupt file and recreate fresh DB
    db.init()
    
    tracks = db.get_all_tracks()
    assert tracks == []
    assert os.path.exists(db_path)
    
    # Verify backup corrupt file was created
    backups = [f for f in os.listdir(temp_dir) if ".corrupt_" in f]
    assert len(backups) == 1
    db.close()
    Database._instance = None


