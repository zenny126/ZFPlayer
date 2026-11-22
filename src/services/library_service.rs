use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::thread;

use crate::cache::CacheManager;
use crate::config::Config;
use crate::database::Database;
use crate::workers::lyrics::LyricsWorker;
use crate::workers::scanner::LibraryScanner;

#[derive(Clone, Debug)]
struct ScanState {
    is_scanning: bool,
    scanned: usize,
    total: usize,
    current_file: String,
}

#[derive(Clone)]
pub struct LibraryService {
    pub db: Database,
    pub cache: CacheManager,
    pub scanner: LibraryScanner,
    pub lyrics_worker: LyricsWorker,
    pub config: Config,
    scan_state: Arc<Mutex<ScanState>>,
    track_info_cache: Arc<Mutex<HashMap<String, Value>>>,
}

impl LibraryService {
    pub fn new(
        db: Database,
        cache: CacheManager,
        scanner: LibraryScanner,
        lyrics_worker: LyricsWorker,
        config: Config,
    ) -> Self {
        Self {
            db,
            cache,
            scanner,
            lyrics_worker,
            config,
            scan_state: Arc::new(Mutex::new(ScanState {
                is_scanning: false,
                scanned: 0,
                total: 0,
                current_file: String::new(),
            })),
            track_info_cache: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    fn cache_track(&self, path: &str, track: Value) {
        if let Ok(mut cache) = self.track_info_cache.lock() {
            if cache.len() >= 2000 {
                let keys_to_remove: Vec<String> = cache.keys().take(400).cloned().collect();
                for k in keys_to_remove {
                    cache.remove(&k);
                }
            }
            cache.insert(path.to_string(), track);
        }
    }

    pub fn clear_ram_cache(&self) {
        if let Ok(mut cache) = self.track_info_cache.lock() {
            cache.clear();
        }
    }

    pub fn get_tracks(
        &self,
        offset: i64,
        limit: i64,
        search: &str,
        sort_by: &str,
        sort_dir: &str,
        favorites_only: bool,
        playlist_id: Option<&str>,
    ) -> Vec<Value> {
        self.db.get_tracks_paginated(
            offset,
            limit,
            search,
            sort_by,
            sort_dir,
            favorites_only,
            playlist_id,
        )
    }

    pub fn get_track_count(
        &self,
        search: &str,
        favorites_only: bool,
        playlist_id: Option<&str>,
    ) -> i64 {
        self.db.get_track_count(search, favorites_only, playlist_id)
    }

    pub fn get_all_track_paths(
        &self,
        favorites_only: bool,
        playlist_id: Option<&str>,
    ) -> Vec<String> {
        self.db.get_all_track_paths(favorites_only, playlist_id)
    }

    pub fn get_recently_played(&self, limit: i64) -> Vec<Value> {
        self.db.get_recently_played(limit)
    }

    pub fn get_track_info(&self, path: &str) -> Option<Value> {
        if path.is_empty() {
            return None;
        }
        if let Ok(cache) = self.track_info_cache.lock() {
            if let Some(cached) = cache.get(path) {
                return Some(cached.clone());
            }
        }

        let track = self.db.get_track_by_path(path)?;
        self.cache_track(path, track.clone());
        Some(track)
    }

    pub fn get_tracks_by_paths(&self, paths: &[String]) -> HashMap<String, Value> {
        let mut result = HashMap::new();
        if paths.is_empty() {
            return result;
        }

        let mut missing = Vec::new();
        if let Ok(cache) = self.track_info_cache.lock() {
            for p in paths {
                if let Some(v) = cache.get(p) {
                    result.insert(p.clone(), v.clone());
                } else {
                    missing.push(p.clone());
                }
            }
        } else {
            missing = paths.to_vec();
        }

        if !missing.is_empty() {
            let fetched = self.db.get_tracks_by_paths(&missing);
            for (p, v) in fetched {
                self.cache_track(&p, v.clone());
                result.insert(p, v);
            }
        }
        result
    }

    pub fn get_albums(&self) -> Vec<Value> {
        self.db.get_albums()
    }

    pub fn toggle_like(&self, path: &str) -> Value {
        if let Some(info) = self.get_track_info(path) {
            let cur_liked = info.get("is_liked").and_then(|v| v.as_i64()).unwrap_or(0);
            let new_liked = if cur_liked == 0 { 1 } else { 0 };
            self.db.update_track_liked(path, new_liked);
            if let Ok(mut cache) = self.track_info_cache.lock() {
                if let Some(Value::Object(ref mut map)) = cache.get_mut(path) {
                    map.insert("is_liked".to_string(), json!(new_liked));
                }
            }
            json!({
                "status": "success",
                "is_liked": new_liked
            })
        } else {
            json!({
                "status": "error",
                "message": "Track not found"
            })
        }
    }

    pub fn scan_library(&self) {
        {
            let Ok(mut st) = self.scan_state.lock() else {
                return;
            };
            if st.is_scanning {
                return;
            }
            st.is_scanning = true;
            st.scanned = 0;
            st.total = 0;
            st.current_file.clear();
        }

        let music_dirs = self.config.get_string_vec("music_dirs");
        let svc = self.clone();

        thread::Builder::new()
            .name("LibraryScanThread".to_string())
            .spawn(move || {
                let state_ref = svc.scan_state.clone();
                svc.scanner
                    .scan(&music_dirs, true, move |scanned, total, current_file| {
                        if let Ok(mut st) = state_ref.lock() {
                            st.scanned = scanned;
                            st.total = total;
                            st.current_file = current_file;
                        }
                    });

                let all_tracks = svc.db.get_all_tracks();
                if !all_tracks.is_empty() {
                    svc.lyrics_worker.enqueue_tracks(&all_tracks);
                }

                svc.clear_ram_cache();
                if let Ok(mut st) = svc.scan_state.lock() {
                    st.is_scanning = false;
                }
            })
            .ok();
    }

    pub fn get_scan_progress(&self) -> Value {
        if let Ok(st) = self.scan_state.lock() {
            json!({
                "is_scanning": st.is_scanning,
                "scanned": st.scanned,
                "total": st.total,
                "current_file": st.current_file
            })
        } else {
            json!({
                "is_scanning": false,
                "scanned": 0,
                "total": 0,
                "current_file": ""
            })
        }
    }

    pub fn add_album(&self, folder_path: &str, album_name: &str, cover_image_path: &str) -> Value {
        if folder_path.trim().is_empty() {
            return json!({
                "status": "error",
                "message": "Folder path is required."
            });
        }

        let mut dirs = self.config.get_string_vec("music_dirs");
        if !dirs.contains(&folder_path.to_string()) {
            dirs.push(folder_path.to_string());
            self.config.set("music_dirs", json!(dirs));
        }

        let mut custom_cover_hash: Option<String> = None;
        if !cover_image_path.is_empty() && Path::new(cover_image_path).exists() {
            if let Ok(bytes) = fs::read(cover_image_path) {
                if !bytes.is_empty() {
                    let mut hasher = Sha256::new();
                    hasher.update(&bytes);
                    let ch = hex::encode(hasher.finalize());
                    self.cache.save_cover_and_thumbnail(&bytes, &ch);
                    custom_cover_hash = Some(ch);
                }
            }
        }

        let svc = self.clone();
        let fp = folder_path.to_string();
        let an = album_name.to_string();

        thread::Builder::new()
            .name("AddAlbumScanThread".to_string())
            .spawn(move || {
                svc.scanner.scan(&[fp.clone()], false, |_, _, _| {});
                svc.db.update_tracks_in_folder(
                    &fp,
                    if an.is_empty() {
                        None
                    } else {
                        Some(an.as_str())
                    },
                    custom_cover_hash.as_deref(),
                );
                svc.clear_ram_cache();
                let all_tracks = svc.db.get_all_tracks();
                svc.lyrics_worker.enqueue_tracks(&all_tracks);
            })
            .ok();

        json!({
            "status": "success",
            "message": "Album added and scan started."
        })
    }

    // --- Playlists ---
    pub fn create_playlist(&self, name: &str, folder_path: Option<&str>) -> i64 {
        self.db.create_playlist(name, folder_path)
    }

    pub fn delete_playlist(&self, playlist_id: i64) {
        self.db.delete_playlist(playlist_id);
    }

    pub fn rename_playlist(&self, playlist_id: i64, new_name: &str) {
        self.db.rename_playlist(playlist_id, new_name);
    }

    pub fn get_playlists(&self) -> Vec<Value> {
        self.db.get_playlists()
    }

    pub fn add_track_to_playlist(&self, playlist_id: i64, track_path: &str) {
        self.db.add_track_to_playlist(playlist_id, track_path);
    }

    pub fn remove_track_from_playlist(&self, playlist_id: i64, track_path: &str) {
        self.db.remove_track_from_playlist(playlist_id, track_path);
    }

    pub fn import_folder_to_playlist(&self, playlist_id: i64, folder_path: &str) -> Value {
        if folder_path.trim().is_empty() {
            return json!({
                "status": "error",
                "message": "Folder path is required"
            });
        }

        if let Ok(mut st) = self.scan_state.lock() {
            st.is_scanning = true;
            st.scanned = 0;
            st.total = 0;
            st.current_file.clear();
        }

        let state_ref = self.scan_state.clone();
        self.scanner.scan(
            &[folder_path.to_string()],
            false,
            move |scanned, total, current_file| {
                if let Ok(mut st) = state_ref.lock() {
                    st.scanned = scanned;
                    st.total = total;
                    st.current_file = current_file;
                }
            },
        );

        let paths = self.db.get_tracks_in_folder(folder_path);
        let added = self.db.add_tracks_to_playlist_bulk(playlist_id, &paths);

        if let Ok(mut st) = self.scan_state.lock() {
            st.is_scanning = false;
        }

        json!({
            "status": "success",
            "message": format!("Successfully imported {} tracks", added),
            "added_count": added
        })
    }

    pub fn import_files_to_playlist(&self, playlist_id: i64, file_paths: &[String]) -> Value {
        if file_paths.is_empty() {
            return json!({
                "status": "error",
                "message": "No files provided"
            });
        }

        if let Ok(mut st) = self.scan_state.lock() {
            st.is_scanning = true;
            st.scanned = 0;
            st.total = file_paths.len();
            st.current_file.clear();
        }

        let dirs: Vec<String> = file_paths
            .iter()
            .filter_map(|p| {
                Path::new(p)
                    .parent()
                    .map(|d| d.to_string_lossy().to_string())
            })
            .collect::<HashSet<_>>()
            .into_iter()
            .collect();

        let state_ref = self.scan_state.clone();
        self.scanner
            .scan(&dirs, false, move |scanned, total, current_file| {
                if let Ok(mut st) = state_ref.lock() {
                    st.scanned = scanned;
                    st.total = total;
                    st.current_file = current_file;
                }
            });

        let added = self.db.add_tracks_to_playlist_bulk(playlist_id, file_paths);

        if let Ok(mut st) = self.scan_state.lock() {
            st.is_scanning = false;
        }

        json!({
            "status": "success",
            "message": format!("Successfully imported {} tracks", added),
            "added_count": added
        })
    }

    pub fn update_playlist_cover(&self, playlist_id: &str, cover_image_path: &str) -> Value {
        if cover_image_path.is_empty() || !Path::new(cover_image_path).exists() {
            return json!({
                "status": "error",
                "message": "Cover image not found"
            });
        }
        let Ok(bytes) = fs::read(cover_image_path) else {
            return json!({
                "status": "error",
                "message": "Failed to read image"
            });
        };
        if bytes.is_empty() {
            return json!({
                "status": "error",
                "message": "Empty image data"
            });
        }

        let mut hasher = Sha256::new();
        hasher.update(&bytes);
        let cover_hash = hex::encode(hasher.finalize());
        self.cache.save_cover_and_thumbnail(&bytes, &cover_hash);
        let cover_url = format!("/api/covers/{}_thumb.jpg", cover_hash);

        if playlist_id == "all" || playlist_id == "favorites" {
            self.config
                .set(&format!("cover_{}", playlist_id), json!(cover_url));
            return json!({
                "status": "success",
                "cover_hash": cover_hash,
                "cover_url": cover_url
            });
        }

        if let Ok(pid) = playlist_id.parse::<i64>() {
            self.db.update_playlist_cover(pid, &cover_hash);
            return json!({
                "status": "success",
                "cover_hash": cover_hash,
                "cover_url": cover_url
            });
        }

        json!({
            "status": "error",
            "message": "Invalid playlist id"
        })
    }

    pub fn get_system_playlist_covers(&self) -> Value {
        json!({
            "all": self.config.get("cover_all").unwrap_or(Value::Null),
            "favorites": self.config.get("cover_favorites").unwrap_or(Value::Null)
        })
    }

    pub fn get_bootstrap_data(&self, player_state: Value) -> Value {
        json!({
            "config": self.config.get_all(),
            "player_state": player_state,
            "playlists": self.get_playlists(),
            "system_covers": self.get_system_playlist_covers(),
            "recently_played": self.get_recently_played(20),
            "total_tracks": self.get_track_count("", false, None)
        })
    }

    pub fn clear_database(&self, clear_cache: bool) -> Value {
        self.clear_ram_cache();
        self.db.clear_database();
        if clear_cache {
            self.cache.clear_all();
        }
        json!({
            "status": "success",
            "message": "Database and library cleared successfully"
        })
    }
}
