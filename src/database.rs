use chrono::{DateTime, Duration, NaiveDateTime, Utc};
use rusqlite::{params, params_from_iter, Connection, OptionalExtension, Row};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::paths::get_db_path;

thread_local! {
    static DB_CONNS: RefCell<HashMap<PathBuf, Connection>> = RefCell::new(HashMap::new());
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrackRecord {
    pub id: Option<i64>,
    pub path: String,
    pub mtime: f64,
    pub size: i64,
    pub title: String,
    pub artist: String,
    pub album: String,
    pub track_number: i64,
    pub duration: f64,
    pub sample_rate: i64,
    pub bit_depth: i64,
    pub channels: i64,
    pub cover_hash: String,
    pub is_liked: i64,
    pub last_played: Option<String>,
    pub created_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cover_url: Option<String>,
}

impl TrackRecord {
    pub fn to_json(&self) -> Value {
        json!({
            "id": self.id,
            "path": self.path,
            "mtime": self.mtime,
            "size": self.size,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "track_number": self.track_number,
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "bit_depth": self.bit_depth,
            "channels": self.channels,
            "cover_hash": self.cover_hash,
            "is_liked": self.is_liked,
            "last_played": self.last_played,
            "created_at": self.created_at,
            "cover_url": if !self.cover_hash.is_empty() {
                Value::String(format!("/api/covers/{}_thumb.jpg", self.cover_hash))
            } else {
                Value::Null
            }
        })
    }
}

#[derive(Clone)]
pub struct Database {
    db_path: PathBuf,
    has_fts: Arc<AtomicBool>,
}

impl Database {
    pub fn new() -> Self {
        Self::new_at(get_db_path())
    }

    pub fn new_at(db_path: PathBuf) -> Self {
        if let Some(parent) = db_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let db = Self {
            db_path,
            has_fts: Arc::new(AtomicBool::new(false)),
        };
        db.check_and_heal_database();
        db.init();
        db
    }

    fn configure_conn(conn: &Connection) {
        let _ = conn.execute_batch(
            "PRAGMA journal_mode=WAL;
             PRAGMA synchronous=NORMAL;
             PRAGMA busy_timeout=30000;
             PRAGMA cache_size=-64000;
             PRAGMA temp_store=MEMORY;
             PRAGMA mmap_size=67108864;",
        );
    }

    /// Execute `f` with a pooled thread-local SQLite connection for `self.db_path`.
    fn with_conn<F, R>(&self, f: F) -> rusqlite::Result<R>
    where
        F: FnOnce(&mut Connection) -> rusqlite::Result<R>,
    {
        DB_CONNS.with(|cell| {
            let mut map = cell.borrow_mut();
            if !map.contains_key(&self.db_path) {
                let conn = Connection::open(&self.db_path)?;
                Self::configure_conn(&conn);
                map.insert(self.db_path.clone(), conn);
            }
            let conn = map.get_mut(&self.db_path).expect("connection inserted");
            f(conn)
        })
    }

    pub fn close_thread_conn(&self) {
        DB_CONNS.with(|cell| {
            cell.borrow_mut().remove(&self.db_path);
        });
    }

    fn verify_integrity(&self) -> bool {
        if !self.db_path.exists() {
            return true;
        }
        let Ok(conn) = Connection::open(&self.db_path) else {
            return false;
        };
        let Ok(res) = conn.query_row("PRAGMA quick_check;", [], |row| row.get::<_, String>(0))
        else {
            return false;
        };
        res == "ok"
    }

    fn check_and_heal_database(&self) {
        if !self.verify_integrity() {
            self.close_thread_conn();
            let ts = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0);
            let backup = self.db_path.with_extension(format!("db.corrupt_{}", ts));
            let _ = fs::rename(&self.db_path, &backup);
            for ext in ["db-wal", "db-shm"] {
                let p = self.db_path.with_extension(ext);
                let _ = fs::remove_file(p);
            }
            log::warn!("Corrupted database moved to {:?}", backup);
        }
    }

    pub fn init(&self) {
        let _ = self.with_conn(|conn| {
            conn.execute_batch(
                "CREATE TABLE IF NOT EXISTS tracks (
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
                    is_liked INTEGER DEFAULT 0,
                    last_played TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS lyrics_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE,
                    synced_lyrics TEXT,
                    plain_lyrics TEXT,
                    source TEXT,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    type TEXT DEFAULT 'manual',
                    folder_path TEXT,
                    cover_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id INTEGER,
                    track_id INTEGER,
                    position INTEGER,
                    FOREIGN KEY(playlist_id) REFERENCES playlists(id),
                    FOREIGN KEY(track_id) REFERENCES tracks(id)
                );
                CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist);
                CREATE INDEX IF NOT EXISTS idx_album ON tracks(album);
                CREATE INDEX IF NOT EXISTS idx_title ON tracks(title);
                CREATE INDEX IF NOT EXISTS idx_path ON tracks(path);
                CREATE INDEX IF NOT EXISTS idx_tracks_is_liked ON tracks(is_liked);
                CREATE INDEX IF NOT EXISTS idx_tracks_last_played ON tracks(last_played);
                CREATE INDEX IF NOT EXISTS idx_tracks_album_artist ON tracks(album, artist);
                CREATE INDEX IF NOT EXISTS idx_tracks_album_trackno ON tracks(album, track_number);
                CREATE INDEX IF NOT EXISTS idx_tracks_artist_album ON tracks(artist, album);
                CREATE INDEX IF NOT EXISTS idx_playlist_tracks_pos ON playlist_tracks(playlist_id, position);
                CREATE INDEX IF NOT EXISTS idx_lyrics_key ON lyrics_cache(cache_key);",
            )?;

            let fts_res = conn.execute_batch(
                "CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                    title, artist, album,
                    content='tracks',
                    content_rowid='id',
                    tokenize='unicode61'
                );
                CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
                    INSERT INTO tracks_fts(rowid, title, artist, album) VALUES (new.id, new.title, new.artist, new.album);
                END;
                CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album) VALUES('delete', old.id, old.title, old.artist, old.album);
                END;
                CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album) VALUES('delete', old.id, old.title, old.artist, old.album);
                    INSERT INTO tracks_fts(rowid, title, artist, album) VALUES (new.id, new.title, new.artist, new.album);
                END;",
            );

            if fts_res.is_ok() {
                let count: i64 = conn
                    .query_row("SELECT COUNT(*) FROM tracks_fts", [], |r| r.get(0))
                    .unwrap_or(0);
                if count == 0 {
                    let _ = conn.execute("INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild')", []);
                }
                self.has_fts.store(true, Ordering::Relaxed);
            }
            Ok(())
        });
    }

    fn map_track_row(row: &Row) -> rusqlite::Result<TrackRecord> {
        Ok(TrackRecord {
            id: row.get("id").ok(),
            path: row.get::<_, String>("path").unwrap_or_default(),
            mtime: row.get::<_, f64>("mtime").unwrap_or(0.0),
            size: row.get::<_, i64>("size").unwrap_or(0),
            title: row
                .get::<_, Option<String>>("title")
                .ok()
                .flatten()
                .unwrap_or_else(|| "Unknown".to_string()),
            artist: row
                .get::<_, Option<String>>("artist")
                .ok()
                .flatten()
                .unwrap_or_else(|| "Unknown".to_string()),
            album: row
                .get::<_, Option<String>>("album")
                .ok()
                .flatten()
                .unwrap_or_else(|| "Unknown".to_string()),
            track_number: row.get::<_, i64>("track_number").unwrap_or(0),
            duration: row.get::<_, f64>("duration").unwrap_or(0.0),
            sample_rate: row.get::<_, i64>("sample_rate").unwrap_or(44100),
            bit_depth: row.get::<_, i64>("bit_depth").unwrap_or(16),
            channels: row.get::<_, i64>("channels").unwrap_or(2),
            cover_hash: row
                .get::<_, Option<String>>("cover_hash")
                .ok()
                .flatten()
                .unwrap_or_default(),
            is_liked: row.get::<_, i64>("is_liked").unwrap_or(0),
            last_played: row.get::<_, Option<String>>("last_played").ok().flatten(),
            created_at: row.get::<_, Option<String>>("created_at").ok().flatten(),
            cover_url: None,
        })
    }

    fn format_fts_query(&self, search: &str) -> Option<String> {
        if search.trim().is_empty() {
            return None;
        }
        let clean: String = search
            .chars()
            .filter(|c| c.is_alphanumeric() || c.is_whitespace())
            .collect();
        let tokens: Vec<String> = clean
            .split_whitespace()
            .filter(|t| !t.is_empty())
            .map(|t| format!("\"{}\"*", t))
            .collect();
        if tokens.is_empty() {
            None
        } else {
            Some(tokens.join(" "))
        }
    }

    fn escape_like_prefix(raw: &str) -> String {
        let mut out = String::with_capacity(raw.len());
        for ch in raw.chars() {
            match ch {
                '!' | '%' | '_' => {
                    out.push('!');
                    out.push(ch);
                }
                _ => out.push(ch),
            }
        }
        out
    }

    pub fn get_tracks_paginated(
        &self,
        offset: i64,
        limit: i64,
        search: &str,
        sort_by: &str,
        sort_dir: &str,
        favorites_only: bool,
        playlist_id: Option<&str>,
    ) -> Vec<Value> {
        self.with_conn(|conn| {
            let is_album_scope = playlist_id
                .map(|p| p.starts_with("album:"))
                .unwrap_or(false);
            let real_playlist_id = playlist_id.and_then(|p| p.parse::<i64>().ok());
            let is_fav = favorites_only
                || playlist_id
                    .map(|p| p == "favorites" || p == "-1")
                    .unwrap_or(false);

            let mut query = String::from("SELECT t.* FROM tracks t");
            if real_playlist_id.is_some() {
                query.push_str(" INNER JOIN playlist_tracks pt ON t.id = pt.track_id");
            }

            let mut params_vec: Vec<rusqlite::types::Value> = Vec::new();
            let mut conditions: Vec<String> = Vec::new();

            if is_album_scope {
                if let Some(pid) = playlist_id {
                    conditions.push("t.album = ?".to_string());
                    params_vec.push(rusqlite::types::Value::Text(pid[6..].to_string()));
                }
            } else if let Some(pid) = real_playlist_id {
                conditions.push("pt.playlist_id = ?".to_string());
                params_vec.push(rusqlite::types::Value::Integer(pid));
            }

            if is_fav {
                conditions.push("t.is_liked = 1".to_string());
            }

            if !search.is_empty() {
                let fts_q = if self.has_fts.load(Ordering::Relaxed) {
                    self.format_fts_query(search)
                } else {
                    None
                };
                if let Some(fq) = fts_q {
                    query.push_str(" INNER JOIN tracks_fts fts ON t.id = fts.rowid");
                    conditions.push("tracks_fts MATCH ?".to_string());
                    params_vec.push(rusqlite::types::Value::Text(fq));
                } else {
                    conditions.push("(t.title LIKE ? OR t.artist LIKE ? OR t.album LIKE ?)".to_string());
                    let pat = format!("%{}%", search);
                    params_vec.push(rusqlite::types::Value::Text(pat.clone()));
                    params_vec.push(rusqlite::types::Value::Text(pat.clone()));
                    params_vec.push(rusqlite::types::Value::Text(pat));
                }
            }

            if !conditions.is_empty() {
                query.push_str(" WHERE ");
                query.push_str(&conditions.join(" AND "));
            }

            if is_album_scope {
                query.push_str(" ORDER BY t.track_number ASC, t.title ASC LIMIT ? OFFSET ?");
            } else if real_playlist_id.is_some() {
                query.push_str(" ORDER BY pt.position ASC LIMIT ? OFFSET ?");
            } else {
                let allowed = [
                    "title",
                    "artist",
                    "album",
                    "duration",
                    "track_number",
                    "created_at",
                    "last_played",
                ];
                let clean_sort = if allowed.contains(&sort_by) {
                    sort_by
                } else {
                    "title"
                };
                let clean_dir = if sort_dir.eq_ignore_ascii_case("DESC") {
                    "DESC"
                } else {
                    "ASC"
                };
                query.push_str(&format!(
                    " ORDER BY t.{} {} LIMIT ? OFFSET ?",
                    clean_sort, clean_dir
                ));
            }

            params_vec.push(rusqlite::types::Value::Integer(limit));
            params_vec.push(rusqlite::types::Value::Integer(offset));

            let mut stmt = conn.prepare(&query)?;
            let rows = stmt.query_map(params_from_iter(params_vec), Self::map_track_row)?;
            Ok(rows.flatten().map(|r| r.to_json()).collect())
        })
        .unwrap_or_default()
    }

    pub fn get_track_count(
        &self,
        search: &str,
        favorites_only: bool,
        playlist_id: Option<&str>,
    ) -> i64 {
        self.with_conn(|conn| {
            let is_album_scope = playlist_id
                .map(|p| p.starts_with("album:"))
                .unwrap_or(false);
            let real_playlist_id = playlist_id.and_then(|p| p.parse::<i64>().ok());
            let is_fav = favorites_only
                || playlist_id
                    .map(|p| p == "favorites" || p == "-1")
                    .unwrap_or(false);

            let mut query = String::from("SELECT COUNT(*) FROM tracks t");
            if real_playlist_id.is_some() {
                query.push_str(" INNER JOIN playlist_tracks pt ON t.id = pt.track_id");
            }

            let mut params_vec: Vec<rusqlite::types::Value> = Vec::new();
            let mut conditions: Vec<String> = Vec::new();

            if is_album_scope {
                if let Some(pid) = playlist_id {
                    conditions.push("t.album = ?".to_string());
                    params_vec.push(rusqlite::types::Value::Text(pid[6..].to_string()));
                }
            } else if let Some(pid) = real_playlist_id {
                conditions.push("pt.playlist_id = ?".to_string());
                params_vec.push(rusqlite::types::Value::Integer(pid));
            }

            if is_fav {
                conditions.push("t.is_liked = 1".to_string());
            }

            if !search.is_empty() {
                let fts_q = if self.has_fts.load(Ordering::Relaxed) {
                    self.format_fts_query(search)
                } else {
                    None
                };
                if let Some(fq) = fts_q {
                    query.push_str(" INNER JOIN tracks_fts fts ON t.id = fts.rowid");
                    conditions.push("tracks_fts MATCH ?".to_string());
                    params_vec.push(rusqlite::types::Value::Text(fq));
                } else {
                    conditions.push("(t.title LIKE ? OR t.artist LIKE ? OR t.album LIKE ?)".to_string());
                    let pat = format!("%{}%", search);
                    params_vec.push(rusqlite::types::Value::Text(pat.clone()));
                    params_vec.push(rusqlite::types::Value::Text(pat.clone()));
                    params_vec.push(rusqlite::types::Value::Text(pat));
                }
            }

            if !conditions.is_empty() {
                query.push_str(" WHERE ");
                query.push_str(&conditions.join(" AND "));
            }

            conn.query_row(&query, params_from_iter(params_vec), |r| r.get(0))
        })
        .unwrap_or(0)
    }

    pub fn get_all_track_paths(
        &self,
        favorites_only: bool,
        playlist_id: Option<&str>,
    ) -> Vec<String> {
        self.with_conn(|conn| {
            let is_fav = favorites_only
                || playlist_id
                    .map(|p| p == "favorites" || p == "-1")
                    .unwrap_or(false);

            if let Some(pid) = playlist_id {
                if pid.starts_with("album:") {
                    let album_name = &pid[6..];
                    let mut stmt = conn.prepare(
                        "SELECT path FROM tracks WHERE album = ? ORDER BY track_number ASC, title ASC",
                    )?;
                    let rows = stmt.query_map([album_name], |r| r.get::<_, String>(0))?;
                    return Ok(rows.flatten().collect());
                } else if let Ok(num_id) = pid.parse::<i64>() {
                    let mut stmt = conn.prepare(
                        "SELECT t.path FROM tracks t
                         INNER JOIN playlist_tracks pt ON t.id = pt.track_id
                         WHERE pt.playlist_id = ?
                         ORDER BY pt.position ASC",
                    )?;
                    let rows = stmt.query_map([num_id], |r| r.get::<_, String>(0))?;
                    return Ok(rows.flatten().collect());
                }
            }

            let sql = if is_fav {
                "SELECT path FROM tracks WHERE is_liked = 1 ORDER BY title ASC"
            } else {
                "SELECT path FROM tracks ORDER BY title ASC"
            };

            let mut stmt = conn.prepare(sql)?;
            let rows = stmt.query_map([], |r| r.get::<_, String>(0))?;
            Ok(rows.flatten().collect())
        })
        .unwrap_or_default()
    }

    pub fn get_track_by_path(&self, path: &str) -> Option<Value> {
        self.with_conn(|conn| {
            conn.query_row(
                "SELECT * FROM tracks WHERE path = ?",
                [path],
                Self::map_track_row,
            )
            .optional()
        })
        .ok()
        .flatten()
        .map(|r| r.to_json())
    }

    pub fn get_tracks_by_paths(&self, paths: &[String]) -> HashMap<String, Value> {
        if paths.is_empty() {
            return HashMap::new();
        }
        self.with_conn(|conn| {
            let mut result = HashMap::new();
            for chunk in paths.chunks(500) {
                let placeholders = vec!["?"; chunk.len()].join(",");
                let sql = format!("SELECT * FROM tracks WHERE path IN ({})", placeholders);
                if let Ok(mut stmt) = conn.prepare(&sql) {
                    let params_iter = chunk
                        .iter()
                        .map(|s| rusqlite::types::Value::Text(s.clone()));
                    if let Ok(rows) =
                        stmt.query_map(params_from_iter(params_iter), Self::map_track_row)
                    {
                        for r in rows.flatten() {
                            result.insert(r.path.clone(), r.to_json());
                        }
                    }
                }
            }
            Ok(result)
        })
        .unwrap_or_default()
    }

    pub fn get_recently_played(&self, limit: i64) -> Vec<Value> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT * FROM tracks WHERE last_played IS NOT NULL ORDER BY last_played DESC LIMIT ?",
            )?;
            let rows = stmt.query_map([limit], Self::map_track_row)?;
            Ok(rows.flatten().map(|r| r.to_json()).collect())
        })
        .unwrap_or_default()
    }

    pub fn update_last_played(&self, path: &str) {
        let _ = self.with_conn(|conn| {
            conn.execute(
                "UPDATE tracks SET last_played = CURRENT_TIMESTAMP WHERE path = ?",
                [path],
            )?;
            Ok(())
        });
    }

    pub fn update_track_liked(&self, path: &str, is_liked: i64) {
        let _ = self.with_conn(|conn| {
            conn.execute(
                "UPDATE tracks SET is_liked = ? WHERE path = ?",
                params![is_liked, path],
            )?;
            Ok(())
        });
    }

    pub fn get_albums(&self) -> Vec<Value> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT album, artist, cover_hash, COUNT(id) as track_count
                 FROM tracks
                 WHERE album != 'Unknown' AND album != ''
                 GROUP BY album, artist
                 ORDER BY album ASC",
            )?;

            let rows = stmt.query_map([], |row| {
                let album: String = row.get::<_, String>("album").unwrap_or_default();
                let artist: String = row.get::<_, String>("artist").unwrap_or_default();
                let cover_hash: String = row
                    .get::<_, Option<String>>("cover_hash")
                    .ok()
                    .flatten()
                    .unwrap_or_default();
                let track_count: i64 = row.get::<_, i64>("track_count").unwrap_or(0);
                let cover_url = if !cover_hash.is_empty() {
                    Value::String(format!("/api/covers/{}_thumb.jpg", cover_hash))
                } else {
                    Value::Null
                };
                Ok(json!({
                    "album": album,
                    "artist": artist,
                    "cover_hash": cover_hash,
                    "track_count": track_count,
                    "cover_url": cover_url
                }))
            })?;
            Ok(rows.flatten().collect())
        })
        .unwrap_or_default()
    }

    pub fn get_tracks_mtime_map(&self) -> HashMap<String, (f64, i64)> {
        self.with_conn(|conn| {
            let mut map = HashMap::new();
            let mut stmt = conn.prepare("SELECT path, mtime, size FROM tracks")?;
            let rows = stmt.query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, f64>(1).unwrap_or(0.0),
                    r.get::<_, i64>(2).unwrap_or(0),
                ))
            })?;
            for (path, mtime, size) in rows.flatten() {
                map.insert(path, (mtime, size));
            }
            Ok(map)
        })
        .unwrap_or_default()
    }

    pub fn get_all_tracks(&self) -> Vec<TrackRecord> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT * FROM tracks")?;
            let rows = stmt.query_map([], Self::map_track_row)?;
            Ok(rows.flatten().collect())
        })
        .unwrap_or_default()
    }

    /// Upsert track metadata preserving primary `id`, `is_liked`, `last_played`, `created_at`,
    /// and existing `playlist_tracks` foreign key associations on conflict.
    pub fn bulk_insert_tracks(&self, tracks: &[TrackRecord]) {
        if tracks.is_empty() {
            return;
        }
        let _ = self.with_conn(|conn| {
            let tx = conn.transaction()?;
            {
                let mut stmt = tx.prepare(
                    "INSERT INTO tracks (
                        path, mtime, size, title, artist, album,
                        track_number, duration, sample_rate, bit_depth, channels, cover_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        mtime = excluded.mtime,
                        size = excluded.size,
                        title = excluded.title,
                        artist = excluded.artist,
                        album = excluded.album,
                        track_number = excluded.track_number,
                        duration = excluded.duration,
                        sample_rate = excluded.sample_rate,
                        bit_depth = excluded.bit_depth,
                        channels = excluded.channels,
                        cover_hash = excluded.cover_hash",
                )?;
                for t in tracks {
                    let _ = stmt.execute(params![
                        t.path,
                        t.mtime,
                        t.size,
                        t.title,
                        t.artist,
                        t.album,
                        t.track_number,
                        t.duration,
                        t.sample_rate,
                        t.bit_depth,
                        t.channels,
                        t.cover_hash
                    ]);
                }
            }
            tx.commit()?;
            Ok(())
        });
    }

    pub fn delete_tracks_bulk(&self, paths: &[String]) {
        if paths.is_empty() {
            return;
        }
        let _ = self.with_conn(|conn| {
            let tx = conn.transaction()?;
            {
                let mut stmt = tx.prepare("DELETE FROM tracks WHERE path = ?")?;
                for p in paths {
                    let _ = stmt.execute([p]);
                }
            }
            tx.commit()?;
            Ok(())
        });
    }

    pub fn disable_fts_triggers(&self) {
        let _ = self.with_conn(|conn| {
            conn.execute_batch(
                "DROP TRIGGER IF EXISTS tracks_ai;
                 DROP TRIGGER IF EXISTS tracks_ad;
                 DROP TRIGGER IF EXISTS tracks_au;",
            )
        });
    }

    pub fn enable_fts_triggers(&self) {
        let _ = self.with_conn(|conn| {
            conn.execute_batch(
                "CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
                    INSERT INTO tracks_fts(rowid, title, artist, album) VALUES (new.id, new.title, new.artist, new.album);
                END;
                CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album) VALUES('delete', old.id, old.title, old.artist, old.album);
                END;
                CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album) VALUES('delete', old.id, old.title, old.artist, old.album);
                    INSERT INTO tracks_fts(rowid, title, artist, album) VALUES (new.id, new.title, new.artist, new.album);
                END;",
            )
        });
    }

    pub fn rebuild_fts(&self) {
        let _ = self.with_conn(|conn| {
            conn.execute("INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild')", [])?;
            Ok(())
        });
    }

    pub fn get_tracks_in_folder(&self, folder_path: &str) -> Vec<String> {
        if folder_path.is_empty() {
            return vec![];
        }
        let clean = folder_path.trim_end_matches(&['\\', '/'][..]);
        let prefix_win = format!("{}\\%", Self::escape_like_prefix(&clean.replace('/', "\\")));
        let prefix_posix = format!("{}/%", Self::escape_like_prefix(&clean.replace('\\', "/")));

        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT path FROM tracks WHERE path = ? OR path LIKE ? ESCAPE '!' OR path LIKE ? ESCAPE '!'",
            )?;
            let rows = stmt.query_map(params![clean, prefix_win, prefix_posix], |r| {
                r.get::<_, String>(0)
            })?;
            Ok(rows.flatten().collect())
        })
        .unwrap_or_default()
    }

    pub fn update_tracks_in_folder(
        &self,
        folder_path: &str,
        album_name: Option<&str>,
        cover_hash: Option<&str>,
    ) {
        if folder_path.is_empty() {
            return;
        }
        let clean = folder_path.trim_end_matches(&['\\', '/'][..]);
        let prefix_win = format!("{}\\%", Self::escape_like_prefix(&clean.replace('/', "\\")));
        let prefix_posix = format!("{}/%", Self::escape_like_prefix(&clean.replace('\\', "/")));

        let _ = self.with_conn(|conn| {
            if let Some(album) = album_name {
                if !album.is_empty() {
                    conn.execute(
                        "UPDATE tracks SET album = ? WHERE path = ? OR path LIKE ? ESCAPE '!' OR path LIKE ? ESCAPE '!'",
                        params![album, clean, prefix_win, prefix_posix],
                    )?;
                }
            }
            if let Some(ch) = cover_hash {
                if !ch.is_empty() {
                    conn.execute(
                        "UPDATE tracks SET cover_hash = ? WHERE path = ? OR path LIKE ? ESCAPE '!' OR path LIKE ? ESCAPE '!'",
                        params![ch, clean, prefix_win, prefix_posix],
                    )?;
                }
            }
            Ok(())
        });
    }

    // --- Playlist Operations ---
    pub fn create_playlist(&self, name: &str, folder_path: Option<&str>) -> i64 {
        self.with_conn(|conn| {
            conn.execute(
                "INSERT INTO playlists (name, folder_path) VALUES (?, ?)",
                params![name, folder_path],
            )?;
            Ok(conn.last_insert_rowid())
        })
        .unwrap_or(0)
    }

    pub fn delete_playlist(&self, playlist_id: i64) {
        let _ = self.with_conn(|conn| {
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ?",
                [playlist_id],
            )?;
            conn.execute("DELETE FROM playlists WHERE id = ?", [playlist_id])?;
            Ok(())
        });
    }

    pub fn rename_playlist(&self, playlist_id: i64, new_name: &str) {
        let _ = self.with_conn(|conn| {
            conn.execute(
                "UPDATE playlists SET name = ? WHERE id = ?",
                params![new_name, playlist_id],
            )?;
            Ok(())
        });
    }

    pub fn update_playlist_cover(&self, playlist_id: i64, cover_hash: &str) {
        let _ = self.with_conn(|conn| {
            conn.execute(
                "UPDATE playlists SET cover_hash = ? WHERE id = ?",
                params![cover_hash, playlist_id],
            )?;
            Ok(())
        });
    }

    pub fn get_playlists(&self) -> Vec<Value> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT p.id, p.name, p.type, p.folder_path, p.cover_hash, p.created_at,
                        (SELECT COUNT(*) FROM playlist_tracks pt WHERE pt.playlist_id = p.id) as track_count
                 FROM playlists p
                 ORDER BY p.created_at DESC",
            )?;

            let rows = stmt.query_map([], |row| {
                let id: i64 = row.get(0).unwrap_or(0);
                let name: String = row.get(1).unwrap_or_default();
                let ptype: String = row
                    .get::<_, Option<String>>(2)
                    .ok()
                    .flatten()
                    .unwrap_or_else(|| "manual".to_string());
                let folder_path: Option<String> = row.get(3).ok().flatten();
                let cover_hash: Option<String> = row.get(4).ok().flatten();
                let created_at: Option<String> = row.get(5).ok().flatten();
                let track_count: i64 = row.get(6).unwrap_or(0);

                let cover_url = cover_hash
                    .as_ref()
                    .filter(|s| !s.is_empty())
                    .map(|ch| format!("/api/covers/{}_thumb.jpg", ch));

                Ok(json!({
                    "id": id,
                    "name": name,
                    "type": ptype,
                    "folder_path": folder_path,
                    "cover_hash": cover_hash,
                    "created_at": created_at,
                    "track_count": track_count,
                    "cover_url": cover_url
                }))
            })?;
            Ok(rows.flatten().collect())
        })
        .unwrap_or_default()
    }

    pub fn add_track_to_playlist(&self, playlist_id: i64, track_path: &str) {
        self.add_tracks_to_playlist_bulk(playlist_id, &[track_path.to_string()]);
    }

    pub fn add_tracks_to_playlist_bulk(&self, playlist_id: i64, track_paths: &[String]) -> usize {
        if track_paths.is_empty() {
            return 0;
        }
        self.with_conn(|conn| {
            let tx = conn.transaction()?;

            let mut track_map: HashMap<String, (i64, Option<String>)> = HashMap::new();
            for chunk in track_paths.chunks(500) {
                let placeholders = vec!["?"; chunk.len()].join(",");
                let sql = format!(
                    "SELECT id, path, cover_hash FROM tracks WHERE path IN ({})",
                    placeholders
                );
                if let Ok(mut stmt) = tx.prepare(&sql) {
                    let p_iter = chunk
                        .iter()
                        .map(|s| rusqlite::types::Value::Text(s.clone()));
                    if let Ok(rows) = stmt.query_map(params_from_iter(p_iter), |r| {
                        Ok((
                            r.get::<_, i64>(0)?,
                            r.get::<_, String>(1)?,
                            r.get::<_, Option<String>>(2).ok().flatten(),
                        ))
                    }) {
                        for (id, path, ch) in rows.flatten() {
                            track_map.insert(path, (id, ch));
                        }
                    }
                }
            }

            if track_map.is_empty() {
                return Ok(0);
            }

            let mut existing_ids: HashSet<i64> = HashSet::new();
            if let Ok(mut stmt) =
                tx.prepare("SELECT track_id FROM playlist_tracks WHERE playlist_id = ?")
            {
                if let Ok(rows) = stmt.query_map([playlist_id], |r| r.get::<_, i64>(0)) {
                    for tid in rows.flatten() {
                        existing_ids.insert(tid);
                    }
                }
            }

            let mut max_pos: i64 = tx
                .query_row(
                    "SELECT COALESCE(MAX(position), 0) FROM playlist_tracks WHERE playlist_id = ?",
                    [playlist_id],
                    |r| r.get(0),
                )
                .unwrap_or(0);

            let mut inserted = 0usize;
            let mut first_cover: Option<String> = None;

            {
                let mut insert_stmt = tx.prepare(
                    "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                )?;

                for p in track_paths {
                    let Some((tid, ch)) = track_map.get(p) else {
                        continue;
                    };
                    if existing_ids.contains(tid) {
                        continue;
                    }
                    max_pos += 1;
                    if insert_stmt
                        .execute(params![playlist_id, tid, max_pos])
                        .is_ok()
                    {
                        existing_ids.insert(*tid);
                        inserted += 1;
                        if first_cover.is_none() {
                            if let Some(c) = ch {
                                if !c.is_empty() {
                                    first_cover = Some(c.clone());
                                }
                            }
                        }
                    }
                }
            }

            if let Some(cover) = first_cover {
                let current_cover: Option<String> = tx
                    .query_row(
                        "SELECT cover_hash FROM playlists WHERE id = ?",
                        [playlist_id],
                        |r| r.get::<_, Option<String>>(0),
                    )
                    .ok()
                    .flatten();
                if current_cover.as_deref().unwrap_or("").is_empty() {
                    let _ = tx.execute(
                        "UPDATE playlists SET cover_hash = ? WHERE id = ?",
                        params![cover, playlist_id],
                    );
                }
            }

            tx.commit()?;
            Ok(inserted)
        })
        .unwrap_or(0)
    }

    pub fn remove_track_from_playlist(&self, playlist_id: i64, track_path: &str) {
        let _ = self.with_conn(|conn| {
            let Some(track_id) = conn
                .query_row("SELECT id FROM tracks WHERE path = ?", [track_path], |r| {
                    r.get::<_, i64>(0)
                })
                .optional()?
            else {
                return Ok(());
            };
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                params![playlist_id, track_id],
            )?;
            Ok(())
        });
    }

    fn is_negative_cache_expired(fetched_at: Option<&str>, negative_ttl_days: i64) -> bool {
        if negative_ttl_days < 0 {
            return false;
        }
        let Some(ts) = fetched_at.map(str::trim).filter(|s| !s.is_empty()) else {
            return false;
        };
        let parsed = NaiveDateTime::parse_from_str(ts, "%Y-%m-%d %H:%M:%S")
            .or_else(|_| DateTime::parse_from_rfc3339(ts).map(|dt| dt.naive_utc()));
        let Ok(fetched_dt) = parsed else {
            return false;
        };
        let age = Utc::now().naive_utc().signed_duration_since(fetched_dt);
        age > Duration::days(negative_ttl_days)
    }

    // --- Lyrics Cache ---
    pub fn get_lyrics(&self, cache_key: &str) -> Option<Value> {
        self.get_lyrics_with_ttl(cache_key, 7)
    }

    pub fn get_lyrics_with_ttl(&self, cache_key: &str, negative_ttl_days: i64) -> Option<Value> {
        self.with_conn(|conn| {
            let row = conn
                .query_row(
                    "SELECT synced_lyrics, plain_lyrics, source, fetched_at FROM lyrics_cache WHERE cache_key = ?",
                    [cache_key],
                    |r| {
                        let synced: String = r.get::<_, Option<String>>(0)?.unwrap_or_default();
                        let plain: String = r.get::<_, Option<String>>(1)?.unwrap_or_default();
                        let source: String = r.get::<_, Option<String>>(2)?.unwrap_or_default();
                        let fetched_at: Option<String> = r.get::<_, Option<String>>(3).ok().flatten();
                        Ok((synced, plain, source, fetched_at))
                    },
                )
                .optional()?;

            let Some((synced, plain, source, fetched_at)) = row else {
                return Ok(None);
            };

            if synced == "[NO_LYRICS]"
                && Self::is_negative_cache_expired(fetched_at.as_deref(), negative_ttl_days)
            {
                let _ = conn.execute("DELETE FROM lyrics_cache WHERE cache_key = ?", [cache_key]);
                return Ok(None);
            }

            Ok(Some(json!({
                "synced_lyrics": synced,
                "plain_lyrics": plain,
                "source": source
            })))
        })
        .ok()
        .flatten()
    }

    pub fn save_lyrics(&self, cache_key: &str, synced: &str, plain: &str, source: &str) {
        let _ = self.with_conn(|conn| {
            conn.execute(
                "INSERT OR REPLACE INTO lyrics_cache (cache_key, synced_lyrics, plain_lyrics, source, fetched_at)
                 VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                params![cache_key, synced, plain, source],
            )?;
            Ok(())
        });
    }

    pub fn clear_database(&self) {
        let _ = self.with_conn(|conn| {
            conn.execute_batch(
                "DELETE FROM playlist_tracks;
                 DELETE FROM playlists;
                 DELETE FROM lyrics_cache;
                 DELETE FROM tracks;",
            )?;
            if self.has_fts.load(Ordering::Relaxed) {
                let _ = conn.execute("INSERT INTO tracks_fts(tracks_fts) VALUES('delete-all')", []);
            }
            let _ = conn.execute("VACUUM", []);
            Ok(())
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;

    static TEST_COUNTER: AtomicUsize = AtomicUsize::new(0);

    struct TempDb {
        dir: PathBuf,
        db: Database,
    }

    impl TempDb {
        fn new() -> Self {
            let n = TEST_COUNTER.fetch_add(1, Ordering::SeqCst);
            let dir = std::env::temp_dir().join(format!(
                "zfplayer_db_test_{}_{}",
                std::process::id(),
                n
            ));
            let _ = fs::remove_dir_all(&dir);
            fs::create_dir_all(&dir).unwrap();
            let db = Database::new_at(dir.join("test.db"));
            Self { dir, db }
        }
    }

    impl Drop for TempDb {
        fn drop(&mut self) {
            self.db.close_thread_conn();
            let _ = fs::remove_dir_all(&self.dir);
        }
    }

    fn make_track(path: &str, title: &str, artist: &str, album: &str, mtime: f64) -> TrackRecord {
        TrackRecord {
            id: None,
            path: path.to_string(),
            mtime,
            size: 1024,
            title: title.to_string(),
            artist: artist.to_string(),
            album: album.to_string(),
            track_number: 1,
            duration: 180.0,
            sample_rate: 44100,
            bit_depth: 16,
            channels: 2,
            cover_hash: String::new(),
            is_liked: 0,
            last_played: None,
            created_at: None,
            cover_url: None,
        }
    }

    #[test]
    fn bulk_insert_upsert_preserves_id_likes_and_playlist_links() {
        let tdb = TempDb::new();
        let path = r"D:\Music\Song1.flac";
        tdb.db
            .bulk_insert_tracks(&[make_track(path, "Original Title", "Artist A", "Album 1", 100.0)]);

        tdb.db.update_track_liked(path, 1);
        tdb.db.update_last_played(path);
        let original = tdb.db.get_track_by_path(path).unwrap();
        let orig_id = original["id"].as_i64().unwrap();

        let pid = tdb.db.create_playlist("My Favs", None);
        tdb.db.add_track_to_playlist(pid, path);

        // Re-scan updates title and mtime on conflict
        tdb.db
            .bulk_insert_tracks(&[make_track(path, "Updated Title", "Artist A", "Album 1", 200.0)]);

        let updated = tdb.db.get_track_by_path(path).unwrap();
        assert_eq!(updated["id"].as_i64().unwrap(), orig_id);
        assert_eq!(updated["title"].as_str().unwrap(), "Updated Title");
        assert_eq!(updated["is_liked"].as_i64().unwrap(), 1);
        assert!(updated["last_played"].as_str().is_some());

        // Playlist tracks join must still find the track
        let pl_paths = tdb.db.get_all_track_paths(false, Some(&pid.to_string()));
        assert_eq!(pl_paths, vec![path.to_string()]);
    }

    #[test]
    fn fts5_search_and_pagination_work() {
        let tdb = TempDb::new();
        tdb.db.bulk_insert_tracks(&[
            make_track(r"D:\Music\1.flac", "Bohemian Rhapsody", "Queen", "Opera", 1.0),
            make_track(r"D:\Music\2.flac", "Lạc Trôi", "Sơn Tùng M-TP", "Single", 2.0),
            make_track(r"D:\Music\3.flac", "Rolling in the Deep", "Adele", "21", 3.0),
        ]);

        assert_eq!(tdb.db.get_track_count("Queen", false, None), 1);
        let res = tdb.db.get_tracks_paginated(0, 10, "Bohemian", "title", "ASC", false, None);
        assert_eq!(res.len(), 1);
        assert_eq!(res[0]["artist"], "Queen");

        let page1 = tdb.db.get_tracks_paginated(0, 2, "", "title", "ASC", false, None);
        let page2 = tdb.db.get_tracks_paginated(2, 2, "", "title", "ASC", false, None);
        assert_eq!(page1.len(), 2);
        assert_eq!(page2.len(), 1);
    }

    #[test]
    fn folder_like_escapes_wildcards() {
        let tdb = TempDb::new();
        tdb.db.bulk_insert_tracks(&[
            make_track(r"D:\Music_100%\track1.flac", "T1", "A", "Al", 1.0),
            make_track(r"D:\MusicX100abc\track2.flac", "T2", "A", "Al", 1.0),
        ]);

        let matched = tdb.db.get_tracks_in_folder(r"D:\Music_100%");
        assert_eq!(matched, vec![r"D:\Music_100%\track1.flac".to_string()]);
    }

    #[test]
    fn negative_lyrics_cache_expires_after_ttl() {
        let tdb = TempDb::new();
        let key = "neg_key_1";
        let old_ts = (Utc::now().naive_utc() - Duration::days(10))
            .format("%Y-%m-%d %H:%M:%S")
            .to_string();

        tdb.db
            .with_conn(|conn| {
                conn.execute(
                    "INSERT INTO lyrics_cache (cache_key, synced_lyrics, plain_lyrics, source, fetched_at)
                     VALUES (?, '[NO_LYRICS]', '', 'none', ?)",
                    params![key, old_ts],
                )?;
                Ok(())
            })
            .unwrap();

        // Expired after 7 days -> must delete row and return None
        assert!(tdb.db.get_lyrics_with_ttl(key, 7).is_none());

        // Fresh entry should NOT expire
        tdb.db.save_lyrics("fresh_key", "[NO_LYRICS]", "", "none");
        let cached = tdb.db.get_lyrics_with_ttl("fresh_key", 7);
        assert!(cached.is_some());
        assert_eq!(cached.unwrap()["synced_lyrics"], "[NO_LYRICS]");
    }
}
