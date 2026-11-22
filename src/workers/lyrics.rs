use icu_normalizer::ComposingNormalizer;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{HashSet, VecDeque};
use std::fs;
use std::path::Path;
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use crate::database::{Database, TrackRecord};
use crate::workers::metadata::MetadataWorker;

#[derive(Clone, Debug)]
pub struct LyricsQueueItem {
    pub artist: String,
    pub title: String,
    pub album: String,
    pub duration: f64,
    pub path: String,
    pub high_priority: bool,
}

struct QueueState {
    deque: VecDeque<LyricsQueueItem>,
    queued_keys: HashSet<String>,
}

enum LrclibFetch {
    Found(String),
    NotFound,
    NetworkError,
}

struct InFlightGuard {
    pair: Arc<(Mutex<HashSet<String>>, Condvar)>,
    key: String,
}

impl Drop for InFlightGuard {
    fn drop(&mut self) {
        let (lock, cvar) = &*self.pair;
        if let Ok(mut guard) = lock.lock() {
            guard.remove(&self.key);
            cvar.notify_all();
        }
    }
}

#[derive(Clone)]
pub struct LyricsWorker {
    database: Database,
    agent: ureq::Agent,
    queue_pair: Arc<(Mutex<QueueState>, Condvar)>,
    in_flight: Arc<(Mutex<HashSet<String>>, Condvar)>,
}

impl LyricsWorker {
    pub fn new(database: Database) -> Self {
        let worker = Self::new_without_thread(database);
        worker.start_background_worker();
        worker
    }

    fn new_without_thread(database: Database) -> Self {
        let agent = ureq::AgentBuilder::new()
            .timeout_connect(Duration::from_millis(1500))
            .timeout_read(Duration::from_millis(2500))
            .user_agent("ZennyFLACPlayer-Rust/3.0 (https://github.com/zenny126/ZFPlayer)")
            .build();

        let queue_pair = Arc::new((
            Mutex::new(QueueState {
                deque: VecDeque::new(),
                queued_keys: HashSet::new(),
            }),
            Condvar::new(),
        ));

        Self {
            database,
            agent,
            queue_pair,
            in_flight: Arc::new((Mutex::new(HashSet::new()), Condvar::new())),
        }
    }

    fn start_background_worker(&self) {
        let w = self.clone();
        thread::Builder::new()
            .name("LyricsQueueWorker".to_string())
            .spawn(move || loop {
                let item = {
                    let (lock, cvar) = &*w.queue_pair;
                    let mut guard = lock.lock().unwrap();
                    while guard.deque.is_empty() {
                        guard = cvar.wait(guard).unwrap();
                    }
                    let popped = guard.deque.pop_front().unwrap();
                    let key = Self::cache_key(&popped.artist, &popped.title, popped.duration);
                    guard.queued_keys.remove(&key);
                    popped
                };

                let key = Self::cache_key(&item.artist, &item.title, item.duration);
                if w.database.get_lyrics(&key).is_none() {
                    let _ = w.fetch_lyrics(
                        &item.artist,
                        &item.title,
                        &item.album,
                        item.duration,
                        &item.path,
                    );
                    if !item.high_priority {
                        thread::sleep(Duration::from_millis(400));
                    }
                }
            })
            .ok();
    }

    pub fn normalize_string(text: &str) -> String {
        let nfkc = ComposingNormalizer::new_nfkc().normalize(text);
        nfkc.trim()
            .to_lowercase()
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ")
    }

    pub fn cache_key(artist: &str, title: &str, duration: f64) -> String {
        let norm_artist = Self::normalize_string(artist);
        let norm_title = Self::normalize_string(title);
        let norm_dur = duration.round() as i64;
        let raw = format!("{}|{}|{}", norm_artist, norm_title, norm_dur);
        let mut hasher = Sha256::new();
        hasher.update(raw.as_bytes());
        hex::encode(hasher.finalize())
    }

    pub fn enqueue_track(&self, track: &TrackRecord, priority: bool) {
        let clean_artist = track.artist.trim();
        let clean_title = track.title.trim();
        if clean_artist.is_empty()
            || clean_title.is_empty()
            || clean_artist.eq_ignore_ascii_case("unknown")
            || clean_artist.eq_ignore_ascii_case("unknown artist")
            || clean_title.eq_ignore_ascii_case("unknown")
        {
            return;
        }

        let key = Self::cache_key(clean_artist, clean_title, track.duration);
        if self.database.get_lyrics(&key).is_some() {
            return;
        }

        let item = LyricsQueueItem {
            artist: track.artist.clone(),
            title: track.title.clone(),
            album: track.album.clone(),
            duration: track.duration,
            path: track.path.clone(),
            high_priority: priority,
        };

        let (lock, cvar) = &*self.queue_pair;
        if let Ok(mut guard) = lock.lock() {
            if guard.queued_keys.contains(&key) && !priority {
                return;
            }
            guard.queued_keys.insert(key);
            if priority {
                guard.deque.push_front(item);
            } else {
                guard.deque.push_back(item);
            }
            cvar.notify_one();
        }
    }

    pub fn enqueue_tracks(&self, tracks: &[TrackRecord]) {
        for t in tracks {
            self.enqueue_track(t, false);
        }
    }

    fn read_local_lrc(path: &str) -> Option<String> {
        if path.is_empty() {
            return None;
        }
        let audio_path = Path::new(path);
        if !audio_path.exists() {
            return None;
        }
        let lrc_path = audio_path.with_extension("lrc");
        if !lrc_path.exists() {
            return None;
        }
        let content = fs::read_to_string(&lrc_path).ok()?;
        let trimmed = content.trim();
        if !trimmed.is_empty() && trimmed.contains('[') && trimmed.contains(']') {
            Some(trimmed.to_string())
        } else {
            None
        }
    }

    fn fetch_lrclib_exact(
        &self,
        artist: &str,
        title: &str,
        album: &str,
        duration: f64,
    ) -> LrclibFetch {
        let mut req = self
            .agent
            .get("https://lrclib.net/api/get")
            .query("artist_name", artist)
            .query("track_name", title);

        if !album.is_empty() && !album.eq_ignore_ascii_case("unknown") {
            req = req.query("album_name", album);
        }
        if duration > 0.0 {
            req = req.query("duration", &format!("{}", duration.round() as i64));
        }

        match req.call() {
            Ok(resp) => {
                if resp.status() == 200 {
                    if let Ok(data) = resp.into_json::<Value>() {
                        if let Some(synced) = data.get("syncedLyrics").and_then(|v| v.as_str()) {
                            if !synced.trim().is_empty() {
                                return LrclibFetch::Found(synced.to_string());
                            }
                        }
                    }
                    LrclibFetch::NotFound
                } else if resp.status() == 404 {
                    LrclibFetch::NotFound
                } else {
                    LrclibFetch::NetworkError
                }
            }
            Err(ureq::Error::Status(404, _)) => LrclibFetch::NotFound,
            Err(_) => LrclibFetch::NetworkError,
        }
    }

    fn fetch_lrclib_search(&self, artist: &str, title: &str, duration: f64) -> LrclibFetch {
        let resp = match self
            .agent
            .get("https://lrclib.net/api/search")
            .query("artist_name", artist)
            .query("track_name", title)
            .call()
        {
            Ok(r) => r,
            Err(ureq::Error::Status(404, _)) => return LrclibFetch::NotFound,
            Err(_) => return LrclibFetch::NetworkError,
        };

        if resp.status() == 404 {
            return LrclibFetch::NotFound;
        }
        if resp.status() != 200 {
            return LrclibFetch::NetworkError;
        }

        let Ok(results) = resp.into_json::<Value>() else {
            return LrclibFetch::NotFound;
        };
        let Some(arr) = results.as_array() else {
            return LrclibFetch::NotFound;
        };

        let mut best_lyrics: Option<String> = None;
        let mut min_diff = f64::INFINITY;

        for item in arr {
            let Some(synced) = item.get("syncedLyrics").and_then(|v| v.as_str()) else {
                continue;
            };
            if synced.trim().is_empty() {
                continue;
            }
            let item_dur = item.get("duration").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let diff = if duration > 0.0 {
                (item_dur - duration).abs()
            } else {
                0.0
            };
            if diff < min_diff {
                min_diff = diff;
                best_lyrics = Some(synced.to_string());
            }
        }

        if duration == 0.0 || min_diff <= 3.5 {
            match best_lyrics {
                Some(lrc) => LrclibFetch::Found(lrc),
                None => LrclibFetch::NotFound,
            }
        } else {
            LrclibFetch::NotFound
        }
    }

    fn format_cached(cached: Value) -> Value {
        if cached.get("synced_lyrics").and_then(|v| v.as_str()) == Some("[NO_LYRICS]") {
            json!({
                "synced_lyrics": "",
                "plain_lyrics": "",
                "source": "none"
            })
        } else {
            cached
        }
    }

    fn acquire_in_flight_slot(&self, key: &str) -> Option<InFlightGuard> {
        let (lock, cvar) = &*self.in_flight;
        let deadline = Instant::now() + Duration::from_secs(6);
        let mut guard = lock.lock().ok()?;
        while guard.contains(key) {
            let rem = deadline.saturating_duration_since(Instant::now());
            if rem.is_zero() {
                break;
            }
            let Ok((g, timeout_res)) = cvar.wait_timeout(guard, rem) else {
                return None;
            };
            guard = g;
            if timeout_res.timed_out() {
                break;
            }
        }
        guard.insert(key.to_string());
        Some(InFlightGuard {
            pair: self.in_flight.clone(),
            key: key.to_string(),
        })
    }

    pub fn fetch_lyrics(
        &self,
        artist: &str,
        title: &str,
        album: &str,
        duration: f64,
        path: &str,
    ) -> Value {
        let key = Self::cache_key(artist, title, duration);
        if let Some(cached) = self.database.get_lyrics(&key) {
            return Self::format_cached(cached);
        }

        // 1. Check local .lrc file
        if let Some(local_lrc) = Self::read_local_lrc(path) {
            self.database
                .save_lyrics(&key, &local_lrc, "", "local_lrc");
            return json!({
                "synced_lyrics": local_lrc,
                "plain_lyrics": "",
                "source": "local_lrc"
            });
        }

        // 2. Check embedded audio tags
        if let Some(embedded) = MetadataWorker::extract_embedded_lyrics(path) {
            self.database
                .save_lyrics(&key, &embedded, "", "embedded_tag");
            return json!({
                "synced_lyrics": embedded,
                "plain_lyrics": "",
                "source": "embedded_tag"
            });
        }

        // 3. Check network LRCLIB if artist & title are valid
        let valid_meta = !artist.trim().is_empty()
            && !title.trim().is_empty()
            && !artist.trim().eq_ignore_ascii_case("unknown")
            && !artist.trim().eq_ignore_ascii_case("unknown artist")
            && !title.trim().eq_ignore_ascii_case("unknown");

        if valid_meta {
            let _slot_guard = self.acquire_in_flight_slot(&key);

            // Re-check cache in case another thread finished fetching while we waited
            if let Some(cached) = self.database.get_lyrics(&key) {
                return Self::format_cached(cached);
            }

            let exact_res = self.fetch_lrclib_exact(artist, title, album, duration);
            if let LrclibFetch::Found(exact) = exact_res {
                self.database
                    .save_lyrics(&key, &exact, "", "lrclib_exact");
                return json!({
                    "synced_lyrics": exact,
                    "plain_lyrics": "",
                    "source": "lrclib_exact"
                });
            }

            let search_res = self.fetch_lrclib_search(artist, title, duration);
            if let LrclibFetch::Found(searched) = search_res {
                self.database
                    .save_lyrics(&key, &searched, "", "lrclib_search");
                return json!({
                    "synced_lyrics": searched,
                    "plain_lyrics": "",
                    "source": "lrclib_search"
                });
            }

            // Only negative-cache when LRCLIB definitively reported NotFound (never on transient network errors)
            if matches!(exact_res, LrclibFetch::NotFound)
                && matches!(search_res, LrclibFetch::NotFound)
            {
                self.database.save_lyrics(&key, "[NO_LYRICS]", "", "none");
            }
        }

        json!({
            "synced_lyrics": "",
            "plain_lyrics": "",
            "source": "none"
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_and_cache_key_handle_nfkc_and_whitespace() {
        // Full-width "Ａ" + extra whitespace vs normal lowercase "a"
        assert_eq!(
            LyricsWorker::normalize_string("  \u{FF21}dele   21  "),
            "adele 21"
        );
        // Decomposed 'Cafe\u{0301}' vs precomposed 'Caf\u{00E9}' normalize to the exact same key
        let k1 = LyricsWorker::cache_key("Artis\u{FF54}", "Cafe\u{0301}", 200.4);
        let k2 = LyricsWorker::cache_key("artist", "Caf\u{00E9}", 200.2);
        assert_eq!(k1, k2);
    }

    #[test]
    fn new_without_thread_initializes_cleanly() {
        let dir = std::env::temp_dir().join(format!("zfplayer_lrc_test_{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        let db = Database::new_at(dir.join("lrc.db"));
        let lw = LyricsWorker::new_without_thread(db.clone());
        let res = lw.fetch_lyrics("Unknown", "Unknown", "", 0.0, "");
        assert_eq!(res["source"], "none");
        db.close_thread_conn();
        let _ = fs::remove_dir_all(&dir);
    }
}
