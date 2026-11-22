use rand::seq::SliceRandom;
use rand::thread_rng;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use crate::audio::AudioEngine;
use crate::config::Config;
use crate::services::LibraryService;
use crate::workers::LyricsWorker;

struct PlayerStateData {
    current_path: Option<String>,
    user_queue: Vec<String>,
    normal_playlist: Vec<String>,
    shuffled_playlist: Vec<String>,
    normal_index_map: HashMap<String, usize>,
    shuffled_index_map: HashMap<String, usize>,
    current_playlist_id: String,
    loaded_playlist_id: Option<String>,
    current_playlist_index: usize,
    playlist_version: u64,
    shuffled_version: u64,
    cached_track_path: Option<String>,
    cached_track_info: Option<Value>,
}

#[derive(Clone)]
pub struct PlayerService {
    audio_engine: Arc<AudioEngine>,
    library_service: LibraryService,
    config: Config,
    lyrics_worker: LyricsWorker,
    state: Arc<Mutex<PlayerStateData>>,
    load_token: Arc<AtomicU64>,
    consecutive_load_failures: Arc<AtomicUsize>,
    vol_save_gen: Arc<AtomicU64>,
}

impl PlayerService {
    pub fn new(
        audio_engine: Arc<AudioEngine>,
        library_service: LibraryService,
        config: Config,
        lyrics_worker: LyricsWorker,
    ) -> Self {
        let last_track = config
            .get("last_track")
            .and_then(|v| v.as_str().map(|s| s.to_string()));
        let last_pid = config
            .get("last_playlist_id")
            .and_then(|v| {
                if let Some(s) = v.as_str() {
                    Some(s.to_string())
                } else {
                    v.as_i64().map(|n| n.to_string())
                }
            })
            .unwrap_or_else(|| "all".to_string());

        let saved_vol = config.get_f64("volume", 0.8);
        audio_engine.set_volume(saved_vol);

        let svc = Self {
            audio_engine: audio_engine.clone(),
            library_service,
            config,
            lyrics_worker,
            state: Arc::new(Mutex::new(PlayerStateData {
                current_path: last_track,
                user_queue: Vec::new(),
                normal_playlist: Vec::new(),
                shuffled_playlist: Vec::new(),
                normal_index_map: HashMap::new(),
                shuffled_index_map: HashMap::new(),
                current_playlist_id: last_pid,
                loaded_playlist_id: None,
                current_playlist_index: 0,
                playlist_version: 0,
                shuffled_version: u64::MAX,
                cached_track_path: None,
                cached_track_info: None,
            })),
            load_token: Arc::new(AtomicU64::new(0)),
            consecutive_load_failures: Arc::new(AtomicUsize::new(0)),
            vol_save_gen: Arc::new(AtomicU64::new(0)),
        };

        let svc_clone = svc.clone();
        audio_engine.set_on_track_end(move || {
            let _ = svc_clone.next_track(false);
        });

        svc
    }

    fn rebuild_index_map(tracks: &[String]) -> HashMap<String, usize> {
        let mut map = HashMap::with_capacity(tracks.len());
        for (idx, p) in tracks.iter().enumerate() {
            map.entry(p.clone()).or_insert(idx);
        }
        map
    }

    fn sync_playlists_and_index(
        &self,
        st: &mut PlayerStateData,
        path: &str,
        playlist_id: Option<&str>,
    ) {
        if let Some(pid) = playlist_id {
            if !pid.is_empty() {
                st.current_playlist_id = pid.to_string();
                self.config.set("last_playlist_id", json!(pid));
            }
        }

        let resolved_pid = st.current_playlist_id.clone();
        let playlist_changed = st.loaded_playlist_id.as_deref() != Some(resolved_pid.as_str());
        let needs_reload = playlist_changed
            || st.normal_playlist.is_empty()
            || (!path.is_empty() && !st.normal_index_map.contains_key(path));

        if needs_reload {
            let is_fav = resolved_pid == "favorites" || resolved_pid == "-1";
            let target_pid = if resolved_pid == "all" || is_fav {
                None
            } else {
                Some(resolved_pid.as_str())
            };

            let mut paths = self
                .library_service
                .get_all_track_paths(is_fav, target_pid);
            if paths.is_empty() && !is_fav && target_pid.is_none() {
                paths = self.library_service.get_all_track_paths(false, None);
            }

            if !paths.is_empty() {
                st.normal_index_map = Self::rebuild_index_map(&paths);
                st.normal_playlist = paths;
                st.playlist_version += 1;
                st.shuffled_playlist.clear();
                st.shuffled_index_map.clear();
                st.loaded_playlist_id = Some(resolved_pid);
            }
        }

        if st.normal_playlist.is_empty() {
            return;
        }

        if st.shuffled_version != st.playlist_version
            || st.shuffled_playlist.len() != st.normal_playlist.len()
        {
            Self::reshuffle_internal(st, Some(path));
        }

        let shuffle = self.config.get_bool("shuffle", false);
        let active_map = if shuffle {
            &st.shuffled_index_map
        } else {
            &st.normal_index_map
        };
        st.current_playlist_index = active_map.get(path).copied().unwrap_or(0);
    }

    fn reshuffle_internal(st: &mut PlayerStateData, current_path: Option<&str>) {
        if st.normal_playlist.is_empty() {
            st.shuffled_playlist.clear();
            st.shuffled_index_map.clear();
            return;
        }

        let curr = current_path.filter(|p| !p.is_empty() && st.normal_index_map.contains_key(*p));
        let mut remaining: Vec<String> = st
            .normal_playlist
            .iter()
            .filter(|p| Some(p.as_str()) != curr)
            .cloned()
            .collect();

        let mut rng = thread_rng();
        remaining.shuffle(&mut rng);

        let mut shuffled = Vec::with_capacity(st.normal_playlist.len());
        if let Some(c) = curr {
            shuffled.push(c.to_string());
        }
        shuffled.extend(remaining);

        st.shuffled_index_map = Self::rebuild_index_map(&shuffled);
        st.shuffled_playlist = shuffled;
        st.shuffled_version = st.playlist_version;
    }

    pub fn play(&self, path: &str, playlist_id: Option<&str>) -> Value {
        self.play_internal(path, playlist_id, true)
    }

    fn play_internal(&self, path: &str, playlist_id: Option<&str>, reset_failures: bool) -> Value {
        if path.is_empty() {
            return self.get_state();
        }

        if reset_failures {
            self.consecutive_load_failures.store(0, Ordering::SeqCst);
        }

        let token = self.load_token.fetch_add(1, Ordering::SeqCst) + 1;
        let track_info = self.library_service.get_track_info(path);
        self.library_service.db.update_last_played(path);
        self.config.set("last_track", json!(path));

        let playlist_len = if let Ok(mut st) = self.state.lock() {
            st.current_path = Some(path.to_string());
            st.cached_track_path = Some(path.to_string());
            st.cached_track_info = track_info;
            st.user_queue.retain(|p| p != path);
            self.sync_playlists_and_index(&mut st, path, playlist_id);
            st.normal_playlist.len()
        } else {
            0
        };

        match self.audio_engine.load(path) {
            Ok(()) => {
                if self.load_token.load(Ordering::SeqCst) != token {
                    return self.get_state();
                }
                self.consecutive_load_failures.store(0, Ordering::SeqCst);
                self.audio_engine.play();
                let svc = self.clone();
                let p_str = path.to_string();
                thread::spawn(move || {
                    svc.preload_lyrics_for(&p_str);
                });
            }
            Err(err) => {
                log::error!("Playback load failed for {}: {}", path, err);
                if self.load_token.load(Ordering::SeqCst) != token {
                    return self.get_state();
                }
                let failures = self.consecutive_load_failures.fetch_add(1, Ordering::SeqCst) + 1;
                if failures < 10 && playlist_len > 1 {
                    log::info!("Auto-skipping broken track (failure {}/10)", failures);
                    return self.next_track_internal(false, true);
                } else {
                    log::warn!("Stopping playback after {} load failure(s)", failures);
                    self.audio_engine.stop();
                    self.consecutive_load_failures.store(0, Ordering::SeqCst);
                }
            }
        }

        self.get_state()
    }

    fn preload_lyrics_for(&self, path: &str) {
        if let Some(info) = self.library_service.get_track_info(path) {
            if let Ok(rec) = serde_json::from_value(info) {
                self.lyrics_worker.enqueue_track(&rec, true);
            }
        }

        let shuffle = self.config.get_bool("shuffle", false);
        let next_paths: Vec<String> = if let Ok(st) = self.state.lock() {
            let (active_list, active_map) = if shuffle && !st.shuffled_playlist.is_empty() {
                (&st.shuffled_playlist, &st.shuffled_index_map)
            } else {
                (&st.normal_playlist, &st.normal_index_map)
            };
            if active_list.is_empty() {
                Vec::new()
            } else {
                let cur_idx = active_map.get(path).copied().unwrap_or(0);
                let count = 5.min(active_list.len().saturating_sub(1));
                (1..=count)
                    .map(|offset| active_list[(cur_idx + offset) % active_list.len()].clone())
                    .collect()
            }
        } else {
            Vec::new()
        };

        if !next_paths.is_empty() {
            let batch = self.library_service.get_tracks_by_paths(&next_paths);
            for p in next_paths {
                if let Some(info) = batch.get(&p) {
                    if let Ok(rec) = serde_json::from_value(info.clone()) {
                        self.lyrics_worker.enqueue_track(&rec, true);
                    }
                }
            }
        }
    }

    pub fn pause(&self) -> Value {
        self.audio_engine.pause();
        self.get_state()
    }

    pub fn resume(&self) -> Value {
        let engine_state = self.audio_engine.get_state();
        let st_str = engine_state
            .get("state")
            .and_then(|v| v.as_str())
            .unwrap_or("IDLE");

        if st_str == "IDLE" || st_str == "STOPPED" {
            let (cur_path, cur_pid) = if let Ok(st) = self.state.lock() {
                (st.current_path.clone(), st.current_playlist_id.clone())
            } else {
                (None, "all".to_string())
            };
            if let Some(p) = cur_path {
                return self.play(&p, Some(&cur_pid));
            }
        }

        self.audio_engine.resume();
        self.get_state()
    }

    pub fn stop(&self) -> Value {
        self.load_token.fetch_add(1, Ordering::SeqCst);
        self.consecutive_load_failures.store(0, Ordering::SeqCst);
        self.audio_engine.stop();
        self.get_state()
    }

    pub fn seek(&self, seconds: f64) -> Value {
        self.audio_engine.seek(seconds);
        self.get_state()
    }

    pub fn set_volume(&self, level: f64) -> Value {
        let clamped = level.clamp(0.0, 1.0);
        self.audio_engine.set_volume(clamped);
        self.config.set_in_memory("volume", json!(clamped));

        let gen = self.vol_save_gen.fetch_add(1, Ordering::SeqCst) + 1;
        let cfg = self.config.clone();
        let gen_ref = self.vol_save_gen.clone();
        thread::spawn(move || {
            thread::sleep(Duration::from_millis(300));
            if gen_ref.load(Ordering::SeqCst) == gen {
                cfg.save_sync();
            }
        });

        self.get_state()
    }

    pub fn set_shuffle(&self, enabled: Option<bool>) -> Value {
        let current = self.config.get_bool("shuffle", false);
        let new_val = enabled.unwrap_or(!current);
        self.config.set("shuffle", json!(new_val));

        if let Ok(mut st) = self.state.lock() {
            let curr = st.current_path.clone();
            if new_val {
                Self::reshuffle_internal(&mut st, curr.as_deref());
            }
            if let Some(ref c) = curr {
                let idx = if new_val {
                    st.shuffled_index_map.get(c).copied().unwrap_or(0)
                } else {
                    st.normal_index_map.get(c).copied().unwrap_or(0)
                };
                st.current_playlist_index = idx;
            }
        }
        self.get_state()
    }

    pub fn set_active_playlist(&self, playlist_id: &str) -> Value {
        if let Ok(mut st) = self.state.lock() {
            let curr = st.current_path.clone().unwrap_or_default();
            self.sync_playlists_and_index(&mut st, &curr, Some(playlist_id));
        }
        self.get_state()
    }

    pub fn next_track(&self, user_initiated: bool) -> Value {
        self.next_track_internal(user_initiated, false)
    }

    fn next_track_internal(&self, user_initiated: bool, from_failure: bool) -> Value {
        let repeat_mode = self.config.get_string("repeat", "off");
        let shuffle = self.config.get_bool("shuffle", false);

        let target_info: Option<(String, String)> = {
            let Ok(mut st) = self.state.lock() else {
                return self.get_state();
            };

            let curr = st.current_path.clone().unwrap_or_default();
            let pid = st.current_playlist_id.clone();

            if !user_initiated && !from_failure && repeat_mode == "one" && !curr.is_empty() {
                Some((curr, pid))
            } else {
                self.sync_playlists_and_index(&mut st, &curr, None);
                let (active_list, active_map) = if shuffle {
                    (&st.shuffled_playlist, &st.shuffled_index_map)
                } else {
                    (&st.normal_playlist, &st.normal_index_map)
                };

                if active_list.is_empty() {
                    None
                } else if curr.is_empty() {
                    Some((active_list[0].clone(), pid))
                } else {
                    let cur_idx = active_map.get(&curr).copied();
                    let next_idx = cur_idx.map(|i| i + 1).unwrap_or(0);
                    if next_idx >= active_list.len() {
                        if !user_initiated && repeat_mode != "all" {
                            None
                        } else {
                            let chosen = active_list[0].clone();
                            st.current_playlist_index = 0;
                            Some((chosen, pid))
                        }
                    } else {
                        let chosen = active_list[next_idx].clone();
                        st.current_playlist_index = next_idx;
                        Some((chosen, pid))
                    }
                }
            }
        };

        if let Some((next_path, pid)) = target_info {
            self.play_internal(&next_path, Some(&pid), user_initiated)
        } else {
            self.stop()
        }
    }

    pub fn prev_track(&self) -> Value {
        let engine_state = self.audio_engine.get_state();
        let pos_sec = engine_state
            .get("position_seconds")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        if pos_sec > 3.0 {
            return self.seek(0.0);
        }

        let shuffle = self.config.get_bool("shuffle", false);
        let target_info: Option<(String, String)> = {
            let Ok(mut st) = self.state.lock() else {
                return self.get_state();
            };

            let curr = st.current_path.clone().unwrap_or_default();
            let pid = st.current_playlist_id.clone();
            self.sync_playlists_and_index(&mut st, &curr, None);

            let (active_list, active_map) = if shuffle {
                (&st.shuffled_playlist, &st.shuffled_index_map)
            } else {
                (&st.normal_playlist, &st.normal_index_map)
            };

            if active_list.is_empty() {
                None
            } else if curr.is_empty() {
                Some((active_list.last().unwrap().clone(), pid))
            } else {
                let cur_idx = active_map.get(&curr).copied().unwrap_or(0);
                let prev_idx = if cur_idx == 0 {
                    active_list.len() - 1
                } else {
                    cur_idx - 1
                };
                let chosen = active_list[prev_idx].clone();
                st.current_playlist_index = prev_idx;
                Some((chosen, pid))
            }
        };

        if let Some((prev_path, pid)) = target_info {
            self.play(&prev_path, Some(&pid))
        } else {
            self.get_state()
        }
    }

    pub fn insert_play_next(&self, path: &str) -> Value {
        if path.is_empty() {
            return json!({
                "status": "error",
                "message": "Invalid track path"
            });
        }

        if let Ok(mut st) = self.state.lock() {
            st.user_queue.retain(|p| p != path);
            st.user_queue.push(path.to_string());

            let curr = st.current_path.clone().unwrap_or_default();
            let pid = st.current_playlist_id.clone();
            self.sync_playlists_and_index(&mut st, &curr, Some(&pid));

            let uq = st.user_queue.clone();
            st.normal_playlist = Self::insert_after_current(&st.normal_playlist, &curr, &uq, path);
            st.normal_index_map = Self::rebuild_index_map(&st.normal_playlist);
            st.playlist_version += 1;

            st.shuffled_playlist =
                Self::insert_after_current(&st.shuffled_playlist, &curr, &uq, path);
            st.shuffled_index_map = Self::rebuild_index_map(&st.shuffled_playlist);
            st.shuffled_version = st.playlist_version;
        }

        json!({
            "status": "success",
            "message": "Track queued as next"
        })
    }

    fn insert_after_current(
        list: &[String],
        current_path: &str,
        user_queue: &[String],
        track_path: &str,
    ) -> Vec<String> {
        let mut new_list: Vec<String> = list.iter().filter(|p| *p != track_path).cloned().collect();
        if current_path.is_empty() {
            new_list.insert(0, track_path.to_string());
            return new_list;
        }

        if let Some(cur_idx) = new_list.iter().position(|p| p == current_path) {
            let mut insert_pos = cur_idx + 1;
            for q_item in user_queue {
                if q_item == track_path {
                    continue;
                }
                if let Some(q_idx) = new_list.iter().position(|p| p == q_item) {
                    if q_idx >= insert_pos {
                        insert_pos = q_idx + 1;
                    }
                }
            }
            let pos = insert_pos.min(new_list.len());
            new_list.insert(pos, track_path.to_string());
        } else {
            new_list.insert(0, track_path.to_string());
        }
        new_list
    }

    fn resolve_track_metadata(&self, path: &str) -> Value {
        if let Some(info) = self.library_service.get_track_info(path) {
            return info;
        }
        let clean_title = path
            .replace('\\', "/")
            .split('/')
            .next_back()
            .unwrap_or("Unknown Track")
            .to_string();
        json!({
            "path": path,
            "title": clean_title,
            "artist": "Unknown Artist",
            "album": "Unknown Album",
            "duration": 0,
            "cover_url": Value::Null
        })
    }

    pub fn get_queue(&self, limit: usize) -> Value {
        let shuffle = self.config.get_bool("shuffle", false);
        let (curr_opt, user_paths, upcoming_paths) = {
            let Ok(st) = self.state.lock() else {
                return json!({
                    "current": Value::Null,
                    "user_queue": [],
                    "upcoming": []
                });
            };

            let curr = st.current_path.clone();
            let u_paths: Vec<String> = st
                .user_queue
                .iter()
                .filter(|p| Some((*p).as_str()) != curr.as_deref())
                .cloned()
                .collect();
            let u_set: HashSet<String> = u_paths.iter().cloned().collect();

            let (active_list, active_map) = if shuffle {
                (&st.shuffled_playlist, &st.shuffled_index_map)
            } else {
                (&st.normal_playlist, &st.normal_index_map)
            };

            let mut needed = Vec::new();
            if let Some(ref c) = curr {
                if let Some(&cur_idx) = active_map.get(c) {
                    for p in active_list.iter().skip(cur_idx + 1) {
                        if u_set.contains(p) || p == c {
                            continue;
                        }
                        needed.push(p.clone());
                        if needed.len() >= limit {
                            break;
                        }
                    }
                }
            }

            (curr, u_paths, needed)
        };

        let current_track = curr_opt
            .as_deref()
            .map(|p| self.resolve_track_metadata(p))
            .unwrap_or(Value::Null);

        let user_batch = self.library_service.get_tracks_by_paths(&user_paths);
        let user_queue_tracks: Vec<Value> = user_paths
            .iter()
            .map(|p| {
                user_batch
                    .get(p)
                    .cloned()
                    .unwrap_or_else(|| self.resolve_track_metadata(p))
            })
            .collect();

        let upcoming_batch = self.library_service.get_tracks_by_paths(&upcoming_paths);
        let upcoming_tracks: Vec<Value> = upcoming_paths
            .iter()
            .map(|p| {
                upcoming_batch
                    .get(p)
                    .cloned()
                    .unwrap_or_else(|| self.resolve_track_metadata(p))
            })
            .collect();

        json!({
            "current": current_track,
            "user_queue": user_queue_tracks,
            "upcoming": upcoming_tracks
        })
    }

    pub fn remove_from_queue(&self, path: &str) -> Value {
        if let Ok(mut st) = self.state.lock() {
            st.user_queue.retain(|p| p != path);
            st.normal_playlist.retain(|p| p != path);
            st.normal_index_map = Self::rebuild_index_map(&st.normal_playlist);
            st.playlist_version += 1;

            st.shuffled_playlist.retain(|p| p != path);
            st.shuffled_index_map = Self::rebuild_index_map(&st.shuffled_playlist);
            st.shuffled_version = st.playlist_version;
        }
        json!({
            "status": "success",
            "message": "Removed from queue"
        })
    }

    pub fn clear_queue(&self) -> Value {
        if let Ok(mut st) = self.state.lock() {
            let queued: HashSet<String> = st.user_queue.drain(..).collect();
            let curr = st.current_path.clone();
            if !queued.is_empty() {
                st.normal_playlist
                    .retain(|p| !queued.contains(p) || Some(p) == curr.as_ref());
                st.normal_index_map = Self::rebuild_index_map(&st.normal_playlist);
                st.playlist_version += 1;

                st.shuffled_playlist
                    .retain(|p| !queued.contains(p) || Some(p) == curr.as_ref());
                st.shuffled_index_map = Self::rebuild_index_map(&st.shuffled_playlist);
                st.shuffled_version = st.playlist_version;
            }
        }
        json!({
            "status": "success",
            "message": "Queue cleared"
        })
    }

    pub fn get_state(&self) -> Value {
        let mut state_val = self.audio_engine.get_state();
        let track_val = {
            let Ok(mut st) = self.state.lock() else {
                return state_val;
            };
            let Some(ref cur_path) = st.current_path else {
                if let Value::Object(ref mut m) = state_val {
                    m.insert("track".to_string(), Value::Null);
                }
                return state_val;
            };

            if st.cached_track_path.as_ref() != Some(cur_path) || st.cached_track_info.is_none() {
                let path_clone = cur_path.clone();
                st.cached_track_info = self.library_service.get_track_info(&path_clone);
                st.cached_track_path = Some(path_clone);
            }
            st.cached_track_info.clone().unwrap_or(Value::Null)
        };

        if let Value::Object(ref mut m) = state_val {
            m.insert("track".to_string(), track_val);
        }
        state_val
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cache::CacheManager;
    use crate::database::{Database, TrackRecord};
    use crate::workers::LibraryScanner;
    use std::fs;
    use std::path::PathBuf;
    use std::sync::atomic::AtomicUsize;

    static PS_TEST_CNT: AtomicUsize = AtomicUsize::new(0);

    struct TestEnv {
        dir: PathBuf,
        db: Database,
        ps: PlayerService,
        audio: Arc<AudioEngine>,
    }

    impl TestEnv {
        fn new() -> Self {
            let n = PS_TEST_CNT.fetch_add(1, Ordering::SeqCst);
            let dir = std::env::temp_dir().join(format!(
                "zfplayer_ps_test_{}_{}",
                std::process::id(),
                n
            ));
            let _ = fs::remove_dir_all(&dir);
            fs::create_dir_all(&dir).unwrap();

            let db = Database::new_at(dir.join("test.db"));
            let cfg = Config::new_at(dir.join("config.json"));
            let cache = CacheManager::new_at(dir.join("cache"));
            let audio = AudioEngine::new(cfg.clone());
            let lw = LyricsWorker::new(db.clone());
            let scanner = LibraryScanner::new(db.clone(), cache.clone(), None);
            let lib = LibraryService::new(db.clone(), cache, scanner, lw.clone(), cfg.clone());
            let ps = PlayerService::new(audio.clone(), lib, cfg, lw);

            Self {
                dir,
                db,
                ps,
                audio,
            }
        }

        fn seed_tracks(&self, paths: &[&str]) {
            let recs: Vec<TrackRecord> = paths
                .iter()
                .enumerate()
                .map(|(i, p)| TrackRecord {
                    id: None,
                    path: p.to_string(),
                    mtime: 1.0,
                    size: 100,
                    title: format!("Track {}", i),
                    artist: "Artist".to_string(),
                    album: "Album".to_string(),
                    track_number: (i + 1) as i64,
                    duration: 180.0,
                    sample_rate: 44100,
                    bit_depth: 16,
                    channels: 2,
                    cover_hash: String::new(),
                    is_liked: 0,
                    last_played: None,
                    created_at: None,
                    cover_url: None,
                })
                .collect();
            self.db.bulk_insert_tracks(&recs);
        }
    }

    impl Drop for TestEnv {
        fn drop(&mut self) {
            self.audio.shutdown_hardware_stream();
            self.db.close_thread_conn();
            let _ = fs::remove_dir_all(&self.dir);
        }
    }

    #[test]
    fn shuffle_preserves_exact_track_set_and_current_first() {
        let env = TestEnv::new();
        let tracks = [
            r"D:\T\01.flac",
            r"D:\T\02.flac",
            r"D:\T\03.flac",
            r"D:\T\04.flac",
            r"D:\T\05.flac",
        ];
        env.seed_tracks(&tracks);

        {
            let mut st = env.ps.state.lock().unwrap();
            st.current_path = Some(tracks[2].to_string());
            env.ps
                .sync_playlists_and_index(&mut st, tracks[2], Some("all"));
        }

        env.ps.set_shuffle(Some(true));
        let st = env.ps.state.lock().unwrap();
        assert_eq!(st.shuffled_playlist.first().map(String::as_str), Some(tracks[2]));
        let normal_set: HashSet<&String> = st.normal_playlist.iter().collect();
        let shuf_set: HashSet<&String> = st.shuffled_playlist.iter().collect();
        assert_eq!(normal_set, shuf_set);
    }

    #[test]
    fn queue_insert_remove_and_clear_work() {
        let env = TestEnv::new();
        let tracks = [r"D:\Q\1.flac", r"D:\Q\2.flac", r"D:\Q\3.flac", r"D:\Q\4.flac"];
        env.seed_tracks(&tracks);

        {
            let mut st = env.ps.state.lock().unwrap();
            st.current_path = Some(tracks[0].to_string());
            env.ps
                .sync_playlists_and_index(&mut st, tracks[0], Some("all"));
        }

        env.ps.insert_play_next(tracks[3]);
        env.ps.insert_play_next(tracks[2]);
        let q = env.ps.get_queue(20);
        let uq = q["user_queue"].as_array().unwrap();
        assert_eq!(uq.len(), 2);
        assert_eq!(uq[0]["path"], tracks[3]);
        assert_eq!(uq[1]["path"], tracks[2]);

        env.ps.remove_from_queue(tracks[3]);
        let q2 = env.ps.get_queue(20);
        let uq2 = q2["user_queue"].as_array().unwrap();
        assert_eq!(uq2.len(), 1);
        assert_eq!(uq2[0]["path"], tracks[2]);

        env.ps.clear_queue();
        let q3 = env.ps.get_queue(20);
        assert!(q3["user_queue"].as_array().unwrap().is_empty());
    }

    #[test]
    fn next_track_repeat_modes_and_idle_dac_behavior() {
        let env = TestEnv::new();
        let tracks = [r"D:\R\A.flac", r"D:\R\B.flac"];
        env.seed_tracks(&tracks);

        // Idle engine must NOT hold an active hardware WASAPI stream
        assert!(!env.audio.is_stream_open());

        {
            let mut st = env.ps.state.lock().unwrap();
            st.current_path = Some(tracks[1].to_string());
            env.ps
                .sync_playlists_and_index(&mut st, tracks[1], Some("all"));
        }

        // Repeat "off" at end of list when auto-advancing stops cleanly
        env.ps.config.set("repeat", json!("off"));
        let st_off = env.ps.next_track(false);
        assert_eq!(st_off["is_playing"], json!(false));

        // Repeat "one" stays on current track (and since file doesn't exist, stops cleanly on failure)
        env.ps.config.set("repeat", json!("one"));
        let st_one = env.ps.next_track_internal(false, false);
        assert_eq!(st_one["track"]["path"], tracks[1]);
        assert_eq!(st_one["is_playing"], json!(false));
    }
}
