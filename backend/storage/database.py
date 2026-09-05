import sqlite3
import threading
from typing import List, Dict, Any, Optional
import os
import shutil
import time
import logging

from backend.utils.path_utils import get_db_path

logger = logging.getLogger(__name__)

ALLOWED_TRACK_COLUMNS = {
    'path', 'mtime', 'size', 'title', 'artist', 'album',
    'track_number', 'duration', 'sample_rate', 'bit_depth',
    'channels', 'cover_hash', 'is_liked', 'last_played', 'created_at'
}

class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._init(*args, **kwargs)
            return cls._instance

    def __init__(self, *args, **kwargs):
        pass

    def _init(self, db_path: str = None):
        self.db_path = db_path or get_db_path()
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._local = threading.local()
        self._check_and_heal_database()
        self.init()
        self.initialized = True

    def close(self):
        """Close thread-local database connection cleanly."""
        if hasattr(self, '_local') and hasattr(self._local, 'conn'):
            try:
                self._local.conn.close()
            except sqlite3.Error as ex:
                logger.debug("Error closing connection: %s", ex)
            del self._local.conn
        import gc
        gc.collect()

    def _verify_integrity(self) -> bool:
        """Verify database integrity via PRAGMA quick_check."""
        if not os.path.exists(self.db_path):
            return True
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            res = conn.execute('PRAGMA quick_check;').fetchone()
            if res and res[0] == 'ok':
                return True
            logger.error("Database quick_check failed: %s. Rebuilding database...", res)
            return False
        except Exception as e:
            logger.error("Database check encountered error: %s. Rebuilding database...", e)
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error as ex:
                    logger.debug("Error closing verify conn: %s", ex)
            import gc
            gc.collect()

    def _remove_wal_shm_files(self) -> None:
        """Remove temporary SQLite WAL and SHM files."""
        for ext in ['-wal', '-shm']:
            p = self.db_path + ext
            if not os.path.exists(p):
                continue
            try:
                os.remove(p)
            except OSError as ex:
                logger.debug("Failed removing temporary SQLite file %s: %s", p, ex)

    def _quarantine_and_reset(self) -> None:
        """Back up corrupted database and reset workspace for clean reconstruction."""
        time.sleep(0.01)
        try:
            corrupt_backup = f"{self.db_path}.corrupt_{int(time.time())}"
            shutil.move(self.db_path, corrupt_backup)
            self._remove_wal_shm_files()
            logger.info("Corrupted database backed up to %s. Creating fresh library.", corrupt_backup)
        except Exception as ex:
            logger.critical("Failed to auto-heal database: %s", ex)

    def _check_and_heal_database(self):
        """Checks SQLite integrity and self-heals if corrupted."""
        if not self._verify_integrity():
            self._quarantine_and_reset()



    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn'):
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA busy_timeout=30000')
            conn.execute('PRAGMA cache_size=-64000')  # 64MB memory cache
            conn.execute('PRAGMA temp_store=MEMORY')
            conn.execute('PRAGMA mmap_size=67108864')  # 64MB memory mapped I/O
            self._local.conn = conn
        return self._local.conn

    def _create_core_tables(self, cursor: sqlite3.Cursor):
        """Create baseline SQLite relational tables and primary indexes."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                mtime REAL,
                size INTEGER,
                title TEXT,
                artist TEXT,
                album TEXT,
                track_number INTEGER,
                duration REAL,
                sample_rate INTEGER,
                bit_depth INTEGER,
                channels INTEGER,
                cover_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lyrics_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE,
                synced_lyrics TEXT,
                plain_lyrics TEXT,
                source TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                type TEXT DEFAULT 'manual',
                folder_path TEXT,
                cover_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                playlist_id INTEGER,
                track_id INTEGER,
                position INTEGER,
                FOREIGN KEY(playlist_id) REFERENCES playlists(id),
                FOREIGN KEY(track_id) REFERENCES tracks(id)
            )
        ''')

    def _create_core_indexes(self, cursor: sqlite3.Cursor):
        """Create initial performance indexes on tracks."""
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_album ON tracks(album)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON tracks(title)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_path ON tracks(path)')

    def _apply_schema_migrations(self, cursor: sqlite3.Cursor):
        """Apply additive column migrations and composite performance indexes."""
        cursor.execute("PRAGMA table_info(tracks)")
        columns = [col['name'] for col in cursor.fetchall()]
        if 'is_liked' not in columns:
            cursor.execute('ALTER TABLE tracks ADD COLUMN is_liked INTEGER DEFAULT 0')
        if 'last_played' not in columns:
            cursor.execute('ALTER TABLE tracks ADD COLUMN last_played TIMESTAMP')
            
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracks_is_liked ON tracks(is_liked)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracks_last_played ON tracks(last_played)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracks_album_artist ON tracks(album, artist)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracks_album_trackno ON tracks(album, track_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracks_artist_album ON tracks(artist, album)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_playlist_tracks_pos ON playlist_tracks(playlist_id, position)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lyrics_key ON lyrics_cache(cache_key)')
            
        cursor.execute("PRAGMA table_info(playlists)")
        playlist_cols = [col['name'] for col in cursor.fetchall()]
        if 'type' not in playlist_cols:
            cursor.execute("ALTER TABLE playlists ADD COLUMN type TEXT DEFAULT 'manual'")
        if 'folder_path' not in playlist_cols:
            cursor.execute('ALTER TABLE playlists ADD COLUMN folder_path TEXT')
        if 'cover_hash' not in playlist_cols:
            cursor.execute('ALTER TABLE playlists ADD COLUMN cover_hash TEXT')

    def _setup_fts_indexes(self, cursor: sqlite3.Cursor, conn: sqlite3.Connection):
        """Initialize SQLite FTS5 Full-Text Search virtual table and triggers."""
        self._has_fts = False
        try:
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                    title, artist, album,
                    content='tracks',
                    content_rowid='id',
                    tokenize='unicode61'
                )
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
                  INSERT INTO tracks_fts(rowid, title, artist, album) VALUES (new.id, new.title, new.artist, new.album);
                END;
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks BEGIN
                  INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album) VALUES('delete', old.id, old.title, old.artist, old.album);
                END;
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
                  INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album) VALUES('delete', old.id, old.title, old.artist, old.album);
                  INSERT INTO tracks_fts(rowid, title, artist, album) VALUES (new.id, new.title, new.artist, new.album);
                END;
            ''')
            cursor.execute('SELECT COUNT(*) FROM tracks_fts')
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild')")
                conn.commit()
            self._has_fts = True
        except Exception as ex:
            logger.debug("FTS5 setup unavailable or failed: %s", ex)
            self._has_fts = False

    def init(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        self._create_core_tables(cursor)
        self._create_core_indexes(cursor)
        self._apply_schema_migrations(cursor)
        conn.commit()
        self._setup_fts_indexes(cursor, conn)

    def _format_fts_query(self, search: str) -> Optional[str]:
        if not search:
            return None
        clean = "".join(c for c in search if c.isalnum() or c.isspace()).strip()
        if not clean:
            return None
        tokens = [f'"{t}"*' for t in clean.split() if t]
        return " ".join(tokens) if tokens else None

    def insert_track(self, track_dict: Dict[str, Any]):
        sanitized = {k: v for k, v in track_dict.items() if k in ALLOWED_TRACK_COLUMNS}
        if not sanitized:
            return
        conn = self._get_conn()
        cursor = conn.cursor()
        cols = ', '.join(sanitized.keys())
        placeholders = ', '.join(['?'] * len(sanitized))
        query = f'INSERT OR REPLACE INTO tracks ({cols}) VALUES ({placeholders})'
        cursor.execute(query, list(sanitized.values()))
        conn.commit()

    def update_track(self, path: str, track_dict: Dict[str, Any]):
        sanitized = {k: v for k, v in track_dict.items() if k in ALLOWED_TRACK_COLUMNS}
        if not sanitized:
            return
        conn = self._get_conn()
        cursor = conn.cursor()
        set_clause = ', '.join([f'{k} = ?' for k in sanitized.keys()])
        values = list(sanitized.values()) + [path]
        query = f'UPDATE tracks SET {set_clause} WHERE path = ?'
        cursor.execute(query, values)
        conn.commit()

    def delete_track(self, path: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tracks WHERE path = ?', (path,))
        conn.commit()

    def delete_tracks_bulk(self, paths: List[str]):
        if not paths:
            return
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.executemany('DELETE FROM tracks WHERE path = ?', [(p,) for p in paths])
        conn.commit()

    def update_last_played(self, path: str):
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('UPDATE tracks SET last_played = CURRENT_TIMESTAMP WHERE path = ?', (path,))
            conn.commit()
        except Exception as e:
            logger.debug(f"Non-fatal: update_last_played failed for {path}: {e}")

    def get_recently_played(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tracks WHERE last_played IS NOT NULL ORDER BY last_played DESC LIMIT ?', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_tracks(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tracks')
        return [dict(row) for row in cursor.fetchall()]

    def get_tracks_mtime_map(self) -> Dict[str, Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT path, mtime, size FROM tracks')
        return {row['path']: {'mtime': row['mtime'], 'size': row['size']} for row in cursor.fetchall()}

    def get_all_track_paths(self, favorites_only=False, playlist_id: Optional[Any] = None, **kwargs) -> List[str]:
        is_favorites = bool(favorites_only or kwargs.get('is_favorites', False))
        conn = self._get_conn()
        cursor = conn.cursor()
        if isinstance(playlist_id, str) and playlist_id.startswith('album:'):
            album_name = playlist_id[6:]
            cursor.execute('SELECT path FROM tracks WHERE album = ? ORDER BY track_number ASC, title ASC', (album_name,))
        elif playlist_id is not None and str(playlist_id).isdigit():
            cursor.execute('''
                SELECT t.path FROM tracks t
                INNER JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position ASC
            ''', (int(playlist_id),))
        elif is_favorites or str(playlist_id) in ['favorites', '-1']:
            cursor.execute('SELECT path FROM tracks WHERE is_liked = 1 ORDER BY title ASC')
        else:
            cursor.execute('SELECT path FROM tracks ORDER BY title ASC')
        return [row['path'] for row in cursor.fetchall()]

    def _apply_search_filter(self, search: str, query: str, conditions: List[str], params: List[Any]) -> str:
        """Apply FTS5 full-text match or fallback LIKE substring filter."""
        if not search:
            return query
        fts_query = self._format_fts_query(search) if getattr(self, '_has_fts', False) else None
        if fts_query:
            query += ' INNER JOIN tracks_fts fts ON t.id = fts.rowid'
            conditions.append('tracks_fts MATCH ?')
            params.append(fts_query)
        else:
            conditions.append('(t.title LIKE ? OR t.artist LIKE ? OR t.album LIKE ?)')
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param])
        return query

    def _determine_order_by(self, scope: str, real_playlist_id: Optional[int], sort_by: str, sort_dir: str) -> str:
        """Construct secure, whitelisted ORDER BY clause."""
        if scope == 'album':
            return ' ORDER BY t.track_number ASC, t.title ASC LIMIT ? OFFSET ?'
        if real_playlist_id is not None:
            return ' ORDER BY pt.position ASC LIMIT ? OFFSET ?'
        allowed_sorts = ['title', 'artist', 'album', 'duration', 'track_number', 'created_at', 'last_played']
        clean_sort = sort_by if sort_by in allowed_sorts else 'title'
        clean_dir = 'ASC' if sort_dir and str(sort_dir).upper() == 'ASC' else 'DESC'
        return f' ORDER BY t.{clean_sort} {clean_dir} LIMIT ? OFFSET ?'

    def get_tracks_paginated(self, offset: int, limit: int, search: str = '', sort_by: str = 'title', sort_dir: str = 'ASC', favorites_only=False, playlist_id: Optional[Any] = None, **kwargs) -> List[Dict[str, Any]]:
        is_favorites = bool(favorites_only or kwargs.get('is_favorites', False))
        conn = self._get_conn()
        cursor = conn.cursor()
        
        is_album_scope = isinstance(playlist_id, str) and playlist_id.startswith('album:')
        real_playlist_id = int(playlist_id) if playlist_id is not None and str(playlist_id).isdigit() else None
        
        query = 'SELECT t.* FROM tracks t'
        if real_playlist_id is not None:
            query += ' INNER JOIN playlist_tracks pt ON t.id = pt.track_id'
            
        params: List[Any] = []
        conditions: List[str] = []
        if is_album_scope:
            conditions.append('t.album = ?')
            params.append(playlist_id[6:])
        elif real_playlist_id is not None:
            conditions.append('pt.playlist_id = ?')
            params.append(real_playlist_id)
            
        if is_favorites or str(playlist_id) in ['favorites', '-1']:
            conditions.append('t.is_liked = 1')
            
        query = self._apply_search_filter(search, query, conditions, params)
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
            
        scope_name = 'album' if is_album_scope else 'standard'
        query += self._determine_order_by(scope_name, real_playlist_id, sort_by, sort_dir)
        params.extend([limit, offset])
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_albums(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        query = '''
            SELECT album, artist, cover_hash, COUNT(id) as track_count
            FROM tracks
            WHERE album != 'Unknown' AND album != ''
            GROUP BY album, artist
            ORDER BY album ASC
        '''
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_track_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tracks WHERE path = ?', (path,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_tracks_by_paths(self, paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch multiple tracks by their file paths in a single batch query."""
        if not paths:
            return {}

        unique_paths = list(dict.fromkeys(paths))
        conn = self._get_conn()
        cursor = conn.cursor()
        result: Dict[str, Dict[str, Any]] = {}

        chunk_size = 500
        for i in range(0, len(unique_paths), chunk_size):
            chunk = unique_paths[i:i + chunk_size]
            placeholders = ','.join('?' for _ in chunk)
            cursor.execute(f'SELECT * FROM tracks WHERE path IN ({placeholders})', chunk)
            for row in cursor.fetchall():
                row_dict = dict(row)
                result[row_dict['path']] = row_dict

        return result

    def disable_fts_triggers(self):
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('DROP TRIGGER IF EXISTS tracks_ai')
            cursor.execute('DROP TRIGGER IF EXISTS tracks_ad')
            cursor.execute('DROP TRIGGER IF EXISTS tracks_au')
            conn.commit()
        except sqlite3.Error as ex:
            logger.debug("Failed dropping FTS triggers: %s", ex)

    def enable_fts_triggers(self):
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
                  INSERT INTO tracks_fts(rowid, title, artist, album) VALUES (new.id, new.title, new.artist, new.album);
                END;
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks BEGIN
                  INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album) VALUES('delete', old.id, old.title, old.artist, old.album);
                END;
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
                  INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album) VALUES('delete', old.id, old.title, old.artist, old.album);
                  INSERT INTO tracks_fts(rowid, title, artist, album) VALUES (new.id, new.title, new.artist, new.album);
                END;
            ''')
            conn.commit()
        except sqlite3.Error as ex:
            logger.debug("Failed creating FTS triggers: %s", ex)

    def rebuild_fts(self):
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild')")
            conn.commit()
        except sqlite3.Error as ex:
            logger.debug("Failed rebuilding FTS index: %s", ex)

    def bulk_insert_tracks(self, tracks: List[Dict[str, Any]]):
        if not tracks:
            return
        keys = [k for k in tracks[0].keys() if k in ALLOWED_TRACK_COLUMNS]
        if not keys:
            return
        conn = self._get_conn()
        cursor = conn.cursor()
        cols = ', '.join(keys)
        placeholders = ', '.join(['?'] * len(keys))
        query = f'INSERT OR REPLACE INTO tracks ({cols}) VALUES ({placeholders})'
        
        values = [[t.get(k) for k in keys] for t in tracks]
        cursor.executemany(query, values)
        conn.commit()

    def _is_negative_cache_expired(self, fetched_at_str: Optional[str], ttl_days: int) -> bool:
        """Check if negative lyrics cache entry ([NO_LYRICS]) has exceeded its TTL."""
        if not fetched_at_str:
            return False
        try:
            from datetime import datetime
            if 'T' in fetched_at_str:
                fetched_time = datetime.fromisoformat(fetched_at_str)
            else:
                fetched_time = datetime.strptime(fetched_at_str, '%Y-%m-%d %H:%M:%S')
            age_seconds = (datetime.utcnow() - fetched_time).total_seconds()
            return age_seconds > (ttl_days * 86400)
        except (ValueError, TypeError) as ex:
            logger.debug("Failed parsing negative cache timestamp '%s': %s", fetched_at_str, ex)
            return False

    def get_lyrics(self, cache_key: str, negative_ttl_days: int = 7) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM lyrics_cache WHERE cache_key = ?', (cache_key,))
        row = cursor.fetchone()
        if not row:
            return None
        
        result = dict(row)
        if result.get('synced_lyrics') == '[NO_LYRICS]':
            if self._is_negative_cache_expired(result.get('fetched_at'), negative_ttl_days):
                cursor.execute('DELETE FROM lyrics_cache WHERE cache_key = ?', (cache_key,))
                conn.commit()
                return None
        return result

    def save_lyrics(self, cache_key: str, synced: str, plain: str, source: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO lyrics_cache (cache_key, synced_lyrics, plain_lyrics, source, fetched_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (cache_key, synced, plain, source))
        conn.commit()

    def get_track_count(self, search: str = '', favorites_only=False, playlist_id: Optional[Any] = None, **kwargs) -> int:
        is_favorites = bool(favorites_only or kwargs.get('is_favorites', False))
        conn = self._get_conn()
        cursor = conn.cursor()
        
        is_album_scope = isinstance(playlist_id, str) and playlist_id.startswith('album:')
        real_playlist_id = int(playlist_id) if playlist_id is not None and str(playlist_id).isdigit() else None
        
        query = 'SELECT COUNT(*) FROM tracks t'
        if real_playlist_id is not None:
            query += ' INNER JOIN playlist_tracks pt ON t.id = pt.track_id'
            
        params = []
        conditions = []
        
        if is_album_scope:
            conditions.append('t.album = ?')
            params.append(playlist_id[6:])
        elif real_playlist_id is not None:
            conditions.append('pt.playlist_id = ?')
            params.append(real_playlist_id)
            
        if is_favorites or str(playlist_id) in ['favorites', '-1']:
            conditions.append('t.is_liked = 1')
            
        if search:
            fts_query = self._format_fts_query(search) if getattr(self, '_has_fts', False) else None
            if fts_query:
                query += ' INNER JOIN tracks_fts fts ON t.id = fts.rowid'
                conditions.append('tracks_fts MATCH ?')
                params.append(fts_query)
            else:
                conditions.append('(t.title LIKE ? OR t.artist LIKE ? OR t.album LIKE ?)')
                search_param = f'%{search}%'
                params.extend([search_param, search_param, search_param])
            
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
                
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def get_tracks_in_folder(self, folder_path: str) -> List[str]:
        if not folder_path:
            return []
        conn = self._get_conn()
        cursor = conn.cursor()
        folder_clean = folder_path.rstrip('\\/')
        folder_prefix_win = folder_clean.replace('/', '\\') + '\\%'
        folder_prefix_posix = folder_clean.replace('\\', '/') + '/%'
        
        query = 'SELECT path FROM tracks WHERE path = ? OR path LIKE ? OR path LIKE ?'
        cursor.execute(query, (folder_clean, folder_prefix_win, folder_prefix_posix))
        return [row['path'] for row in cursor.fetchall()]

    def update_tracks_in_folder(self, folder_path: str, updates_dict: Dict[str, Any]):
        sanitized = {k: v for k, v in updates_dict.items() if k in ALLOWED_TRACK_COLUMNS}
        if not sanitized or not folder_path:
            return
        conn = self._get_conn()
        cursor = conn.cursor()
        set_clause = ', '.join([f'{k} = ?' for k in sanitized.keys()])
        
        folder_clean = folder_path.rstrip('\\/')
        folder_prefix_win = folder_clean.replace('/', '\\') + '\\%'
        folder_prefix_posix = folder_clean.replace('\\', '/') + '/%'
        
        values = list(sanitized.values()) + [folder_clean, folder_prefix_win, folder_prefix_posix]
        query = f'UPDATE tracks SET {set_clause} WHERE path = ? OR path LIKE ? OR path LIKE ?'
        cursor.execute(query, values)
        conn.commit()

    # --- Playlist Methods ---
    def create_playlist(self, name: str, folder_path: str = None) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO playlists (name, folder_path) VALUES (?, ?)', (name, folder_path))
        conn.commit()
        return cursor.lastrowid

    def delete_playlist(self, playlist_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM playlist_tracks WHERE playlist_id = ?', (playlist_id,))
        cursor.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
        conn.commit()

    def rename_playlist(self, playlist_id: int, new_name: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('UPDATE playlists SET name = ? WHERE id = ?', (new_name, playlist_id))
        conn.commit()

    def update_playlist_cover(self, playlist_id: int, cover_hash: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('UPDATE playlists SET cover_hash = ? WHERE id = ?', (cover_hash, playlist_id))
        conn.commit()

    def get_playlists(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, (SELECT COUNT(*) FROM playlist_tracks pt WHERE pt.playlist_id = p.id) as track_count 
            FROM playlists p 
            ORDER BY p.created_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]

    def add_tracks_to_playlist_bulk(self, playlist_id: int, track_paths: List[str]) -> int:
        if not track_paths:
            return 0
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. Fetch all track IDs and cover_hashes for given paths in bulk
        placeholders = ', '.join(['?'] * len(track_paths))
        cursor.execute(f'SELECT id, path, cover_hash FROM tracks WHERE path IN ({placeholders})', track_paths)
        track_map = {row['path']: (row['id'], row['cover_hash']) for row in cursor.fetchall()}
        
        if not track_map:
            return 0
            
        # 2. Find tracks already in the playlist
        track_ids = [val[0] for val in track_map.values()]
        id_placeholders = ', '.join(['?'] * len(track_ids))
        cursor.execute(f'SELECT track_id FROM playlist_tracks WHERE playlist_id = ? AND track_id IN ({id_placeholders})', [playlist_id] + track_ids)
        existing_ids = set(row['track_id'] for row in cursor.fetchall())
        
        # 3. Get current max position
        cursor.execute('SELECT MAX(position) FROM playlist_tracks WHERE playlist_id = ?', (playlist_id,))
        max_pos = cursor.fetchone()[0] or 0
        
        # 4. Prepare bulk insert list preserving input order
        to_insert = []
        first_cover_hash = None
        for p in track_paths:
            if p not in track_map:
                continue
            t_id, c_hash = track_map[p]
            if t_id in existing_ids:
                continue
            max_pos += 1
            to_insert.append((playlist_id, t_id, max_pos))
            existing_ids.add(t_id)
            if not first_cover_hash and c_hash:
                first_cover_hash = c_hash
                        
        if to_insert:
            cursor.executemany('INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)', to_insert)
            self._update_playlist_cover_if_empty(cursor, playlist_id, first_cover_hash)
            conn.commit()
            
        return len(to_insert)

    def _update_playlist_cover_if_empty(self, cursor: sqlite3.Cursor, playlist_id: int, cover_hash: Optional[str]) -> None:
        """Update playlist cover art if not already established."""
        if not cover_hash:
            return
        cursor.execute('SELECT cover_hash FROM playlists WHERE id = ?', (playlist_id,))
        p_row = cursor.fetchone()
        if p_row and not p_row['cover_hash']:
            cursor.execute('UPDATE playlists SET cover_hash = ? WHERE id = ?', (cover_hash, playlist_id))

    def add_track_to_playlist(self, playlist_id: int, track_path: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT id, cover_hash FROM tracks WHERE path = ?', (track_path,))
        row = cursor.fetchone()
        if not row:
            return
        track_id = row['id']
        
        cursor.execute('SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?', (playlist_id, track_id))
        if cursor.fetchone()[0] > 0:
            return
            
        cursor.execute('SELECT MAX(position) FROM playlist_tracks WHERE playlist_id = ?', (playlist_id,))
        max_pos = cursor.fetchone()[0]
        next_pos = (max_pos or 0) + 1
        
        cursor.execute('INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)', (playlist_id, track_id, next_pos))
        self._update_playlist_cover_if_empty(cursor, playlist_id, row['cover_hash'])
        conn.commit()

    def remove_track_from_playlist(self, playlist_id: int, track_path: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tracks WHERE path = ?', (track_path,))
        row = cursor.fetchone()
        if not row: return
        track_id = row['id']
        cursor.execute('DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?', (playlist_id, track_id))
        conn.commit()

    def clear_database(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM playlist_tracks')
        cursor.execute('DELETE FROM playlists')
        cursor.execute('DELETE FROM lyrics_cache')
        cursor.execute('DELETE FROM tracks')
        if getattr(self, '_has_fts', False):
            try:
                cursor.execute("INSERT INTO tracks_fts(tracks_fts) VALUES('delete-all')")
            except sqlite3.Error as ex:
                logger.debug("Failed clearing FTS table: %s", ex)
        conn.commit()
        try:
            cursor.execute('VACUUM')
        except sqlite3.Error as ex:
            logger.debug("Failed VACUUM after database clear: %s", ex)
