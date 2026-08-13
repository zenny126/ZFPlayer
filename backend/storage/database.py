import sqlite3
import threading
from typing import List, Dict, Any, Optional
import os

from backend.utils.path_utils import get_db_path

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
        if not hasattr(self, 'initialized'):
            self.db_path = db_path or get_db_path()
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._local = threading.local()
            self.init()
            self.initialized = True

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute('PRAGMA journal_mode=WAL')
        return self._local.conn

    def init(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
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

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_album ON tracks(album)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON tracks(title)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_path ON tracks(path)')
        
        cursor.execute("PRAGMA table_info(tracks)")
        columns = [col['name'] for col in cursor.fetchall()]
        if 'is_liked' not in columns:
            cursor.execute('ALTER TABLE tracks ADD COLUMN is_liked INTEGER DEFAULT 0')
        if 'last_played' not in columns:
            cursor.execute('ALTER TABLE tracks ADD COLUMN last_played TIMESTAMP')
            
        cursor.execute("PRAGMA table_info(playlists)")
        playlist_cols = [col['name'] for col in cursor.fetchall()]
        if 'type' not in playlist_cols:
            cursor.execute("ALTER TABLE playlists ADD COLUMN type TEXT DEFAULT 'manual'")
        if 'folder_path' not in playlist_cols:
            cursor.execute('ALTER TABLE playlists ADD COLUMN folder_path TEXT')
        if 'cover_hash' not in playlist_cols:
            cursor.execute('ALTER TABLE playlists ADD COLUMN cover_hash TEXT')
            
        conn.commit()

    def insert_track(self, track_dict: Dict[str, Any]):
        conn = self._get_conn()
        cursor = conn.cursor()
        cols = ', '.join(track_dict.keys())
        placeholders = ', '.join(['?'] * len(track_dict))
        query = f'INSERT OR REPLACE INTO tracks ({cols}) VALUES ({placeholders})'
        cursor.execute(query, list(track_dict.values()))
        conn.commit()

    def update_track(self, path: str, track_dict: Dict[str, Any]):
        conn = self._get_conn()
        cursor = conn.cursor()
        set_clause = ', '.join([f'{k} = ?' for k in track_dict.keys()])
        values = list(track_dict.values()) + [path]
        query = f'UPDATE tracks SET {set_clause} WHERE path = ?'
        cursor.execute(query, values)
        conn.commit()

    def delete_track(self, path: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tracks WHERE path = ?', (path,))
        conn.commit()

    def update_last_played(self, path: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('UPDATE tracks SET last_played = CURRENT_TIMESTAMP WHERE path = ?', (path,))
        conn.commit()

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

    def get_all_track_paths(self, is_favorites: bool = False, playlist_id: Optional[int] = None) -> List[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        if playlist_id is not None:
            cursor.execute('''
                SELECT t.path FROM tracks t
                INNER JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position ASC
            ''', (playlist_id,))
        elif is_favorites:
            cursor.execute('SELECT path FROM tracks WHERE is_liked = 1 ORDER BY title ASC')
        else:
            cursor.execute('SELECT path FROM tracks ORDER BY title ASC')
        return [row['path'] for row in cursor.fetchall()]

    def get_tracks_paginated(self, offset: int, limit: int, search: str = '', sort_by: str = 'title', sort_dir: str = 'ASC', is_favorites: bool = False, playlist_id: Optional[int] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        allowed_sorts = ['title', 'artist', 'album', 'duration', 'created_at', 'last_played']
        sort_by = sort_by if sort_by in allowed_sorts else 'title'
        sort_dir = 'ASC' if sort_dir and str(sort_dir).upper() == 'ASC' else 'DESC'
        
        query = 'SELECT t.* FROM tracks t'
        if playlist_id is not None:
            query += ' INNER JOIN playlist_tracks pt ON t.id = pt.track_id'
            
        params = []
        conditions = []
        
        if playlist_id is not None:
            conditions.append('pt.playlist_id = ?')
            params.append(playlist_id)
            
        if is_favorites:
            conditions.append('t.is_liked = 1')
            
        if search:
            conditions.append('(t.title LIKE ? OR t.artist LIKE ? OR t.album LIKE ?)')
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param])
            
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
            
        if playlist_id is not None:
            query += ' ORDER BY pt.position ASC LIMIT ? OFFSET ?'
        else:
            query += f' ORDER BY t.{sort_by} {sort_dir} LIMIT ? OFFSET ?'
            
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

    def bulk_insert_tracks(self, tracks: List[Dict[str, Any]]):
        if not tracks:
            return
        conn = self._get_conn()
        cursor = conn.cursor()
        keys = tracks[0].keys()
        cols = ', '.join(keys)
        placeholders = ', '.join(['?'] * len(keys))
        query = f'INSERT OR REPLACE INTO tracks ({cols}) VALUES ({placeholders})'
        
        values = [[t[k] for k in keys] for t in tracks]
        cursor.executemany(query, values)
        conn.commit()

    def get_lyrics(self, cache_key: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM lyrics_cache WHERE cache_key = ?', (cache_key,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def save_lyrics(self, cache_key: str, synced: str, plain: str, source: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO lyrics_cache (cache_key, synced_lyrics, plain_lyrics, source)
            VALUES (?, ?, ?, ?)
        ''', (cache_key, synced, plain, source))
        conn.commit()

    def get_track_count(self, search: str = '', is_favorites: bool = False, playlist_id: Optional[int] = None) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = 'SELECT COUNT(*) FROM tracks t'
        if playlist_id is not None:
            query += ' INNER JOIN playlist_tracks pt ON t.id = pt.track_id'
            
        params = []
        conditions = []
        
        if playlist_id is not None:
            conditions.append('pt.playlist_id = ?')
            params.append(playlist_id)
            
        if is_favorites:
            conditions.append('t.is_liked = 1')
            
        if search:
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
        if not updates_dict or not folder_path:
            return
        conn = self._get_conn()
        cursor = conn.cursor()
        set_clause = ', '.join([f'{k} = ?' for k in updates_dict.keys()])
        
        folder_clean = folder_path.rstrip('\\/')
        folder_prefix_win = folder_clean.replace('/', '\\') + '\\%'
        folder_prefix_posix = folder_clean.replace('\\', '/') + '/%'
        
        values = list(updates_dict.values()) + [folder_clean, folder_prefix_win, folder_prefix_posix]
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

    def add_track_to_playlist(self, playlist_id: int, track_path: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tracks WHERE path = ?', (track_path,))
        row = cursor.fetchone()
        if not row: return
        track_id = row['id']
        
        cursor.execute('SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?', (playlist_id, track_id))
        if cursor.fetchone()[0] > 0: return
            
        cursor.execute('SELECT MAX(position) FROM playlist_tracks WHERE playlist_id = ?', (playlist_id,))
        max_pos = cursor.fetchone()[0]
        next_pos = (max_pos or 0) + 1
        
        cursor.execute('INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)', (playlist_id, track_id, next_pos))
        
        cursor.execute('SELECT cover_hash FROM playlists WHERE id = ?', (playlist_id,))
        p_row = cursor.fetchone()
        if p_row and not p_row['cover_hash']:
            cursor.execute('SELECT cover_hash FROM tracks WHERE id = ?', (track_id,))
            t_row = cursor.fetchone()
            if t_row and t_row['cover_hash']:
                cursor.execute('UPDATE playlists SET cover_hash = ? WHERE id = ?', (t_row['cover_hash'], playlist_id))
                
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
