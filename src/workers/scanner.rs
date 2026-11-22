use rayon::prelude::*;
use std::collections::HashSet;
use std::fs;
use std::path::{Component, Path};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::UNIX_EPOCH;
use walkdir::WalkDir;

use crate::cache::CacheManager;
use crate::database::{Database, TrackRecord};
use crate::workers::lyrics::LyricsWorker;
use crate::workers::metadata::MetadataWorker;

#[derive(Clone)]
pub struct LibraryScanner {
    database: Database,
    cache_manager: CacheManager,
    lyrics_worker: Option<LyricsWorker>,
    stop_flag: Arc<AtomicBool>,
}

impl LibraryScanner {
    pub fn new(
        database: Database,
        cache_manager: CacheManager,
        lyrics_worker: Option<LyricsWorker>,
    ) -> Self {
        Self {
            database,
            cache_manager,
            lyrics_worker,
            stop_flag: Arc::new(AtomicBool::new(false)),
        }
    }

    fn normalize_components(raw: &str) -> Vec<String> {
        let unified = raw.replace('/', "\\");
        let trimmed = unified.trim_end_matches('\\');
        let path_str = if trimmed.len() == 2 && trimmed.ends_with(':') {
            // Preserve root slash for drive roots like "D:" -> "D:\"
            format!("{}\\", trimmed)
        } else if trimmed.is_empty() && !unified.is_empty() {
            "\\".to_string()
        } else {
            trimmed.to_string()
        };

        Path::new(&path_str)
            .components()
            .filter_map(|comp| match comp {
                Component::Prefix(p) => Some(p.as_os_str().to_string_lossy().to_lowercase()),
                Component::RootDir => Some("\\".to_string()),
                Component::Normal(s) => Some(s.to_string_lossy().to_lowercase()),
                Component::CurDir | Component::ParentDir => None,
            })
            .collect()
    }

    /// Return true only when `file_path` strictly resides inside `dir_path` on component boundaries.
    pub fn is_path_under_dir(file_path: &str, dir_path: &str) -> bool {
        let file_comps = Self::normalize_components(file_path);
        let dir_comps = Self::normalize_components(dir_path);
        if dir_comps.is_empty() || file_comps.len() < dir_comps.len() {
            return false;
        }
        file_comps[..dir_comps.len()] == dir_comps[..]
    }

    fn is_supported_audio(path: &Path) -> bool {
        let Some(ext) = path.extension().and_then(|e| e.to_str()) else {
            return false;
        };
        matches!(
            ext.to_ascii_lowercase().as_str(),
            "flac" | "wav" | "mp3" | "ogg" | "aiff" | "m4a" | "aac"
        )
    }

    fn discover_audio_files(&self, music_dirs: &[String]) -> Vec<String> {
        let mut found = Vec::new();
        for dir in music_dirs {
            if self.stop_flag.load(Ordering::Relaxed) {
                break;
            }
            let p = Path::new(dir);
            if !p.exists() {
                continue;
            }
            for entry in WalkDir::new(p).follow_links(true).into_iter().flatten() {
                if self.stop_flag.load(Ordering::Relaxed) {
                    break;
                }
                let ep = entry.path();
                if ep.is_file() && Self::is_supported_audio(ep) {
                    found.push(ep.to_string_lossy().to_string());
                }
            }
        }
        found
    }

    pub fn scan<F>(&self, music_dirs: &[String], handle_deletions: bool, progress_cb: F)
    where
        F: Fn(usize, usize, String) + Send + Sync,
    {
        self.stop_flag.store(false, Ordering::SeqCst);

        let all_files = self.discover_audio_files(music_dirs);
        let total_files = all_files.len();
        let existing_tracks = self.database.get_tracks_mtime_map();

        let accessible_dirs: Vec<String> = music_dirs
            .iter()
            .filter(|d| Path::new(d).exists())
            .cloned()
            .collect();

        if total_files == 0 {
            progress_cb(0, 0, String::new());
            if handle_deletions && !accessible_dirs.is_empty() {
                let deleted: Vec<String> = existing_tracks
                    .keys()
                    .filter(|p| {
                        accessible_dirs
                            .iter()
                            .any(|ad| Self::is_path_under_dir(p, ad))
                    })
                    .cloned()
                    .collect();
                self.database.delete_tracks_bulk(&deleted);
            }
            return;
        }

        let mut to_process: Vec<(String, f64, i64)> = Vec::new();
        for path in &all_files {
            if self.stop_flag.load(Ordering::Relaxed) {
                break;
            }
            let Ok(meta) = fs::metadata(path) else {
                continue;
            };
            let size = meta.len() as i64;
            let mtime = meta
                .modified()
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_secs_f64())
                .unwrap_or(0.0);

            let changed = match existing_tracks.get(path) {
                Some((old_mtime, old_size)) => {
                    (old_mtime - mtime).abs() > 0.001 || *old_size != size
                }
                None => true,
            };

            if changed {
                to_process.push((path.clone(), mtime, size));
            }
        }

        if handle_deletions && !accessible_dirs.is_empty() {
            let disk_set: HashSet<&String> = all_files.iter().collect();
            let deleted: Vec<String> = existing_tracks
                .keys()
                .filter(|p| {
                    !disk_set.contains(p)
                        && accessible_dirs
                            .iter()
                            .any(|ad| Self::is_path_under_dir(p, ad))
                })
                .cloned()
                .collect();
            if !deleted.is_empty() {
                self.database.delete_tracks_bulk(&deleted);
            }
        }

        if to_process.is_empty() {
            progress_cb(total_files, total_files, String::new());
            return;
        }

        let process_total = to_process.len();
        let scanned_counter = AtomicUsize::new(0);
        let seen_covers: Mutex<HashSet<String>> = Mutex::new(HashSet::new());

        self.database.disable_fts_triggers();

        // Process in chunks of 100 files in parallel using Rayon
        for chunk in to_process.chunks(100) {
            if self.stop_flag.load(Ordering::Relaxed) {
                break;
            }

            let extracted_batch: Vec<TrackRecord> = chunk
                .par_iter()
                .filter_map(|(path, mtime, size)| {
                    if self.stop_flag.load(Ordering::Relaxed) {
                        return None;
                    }
                    let ext = MetadataWorker::extract(path, *mtime, *size)?;
                    if let Some(ref bytes) = ext.cover_bytes {
                        let ch = &ext.record.cover_hash;
                        if !ch.is_empty() {
                            let is_new = {
                                let mut guard = seen_covers.lock().unwrap();
                                guard.insert(ch.clone())
                            };
                            if is_new {
                                self.cache_manager.save_cover_and_thumbnail(bytes, ch);
                            }
                        }
                    }
                    let current = scanned_counter.fetch_add(1, Ordering::Relaxed) + 1;
                    progress_cb(current, process_total, path.clone());
                    Some(ext.record)
                })
                .collect();

            if !extracted_batch.is_empty() {
                self.database.bulk_insert_tracks(&extracted_batch);
                if let Some(ref lw) = self.lyrics_worker {
                    lw.enqueue_tracks(&extracted_batch);
                }
            }
        }

        self.database.enable_fts_triggers();
        self.database.rebuild_fts();
    }

    pub fn stop(&self) {
        self.stop_flag.store(true, Ordering::SeqCst);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn path_under_dir_respects_directory_boundaries() {
        assert!(LibraryScanner::is_path_under_dir(
            r"D:\Music\song.flac",
            r"D:\Music"
        ));
        assert!(LibraryScanner::is_path_under_dir(
            r"D:\Music\Album\01 - Track.flac",
            r"D:\Music\"
        ));
        assert!(LibraryScanner::is_path_under_dir(
            "d:/music/album/track.flac",
            r"D:\Music"
        ));

        // Sibling directory with same prefix MUST NOT match
        assert!(!LibraryScanner::is_path_under_dir(
            r"D:\Music2\song.flac",
            r"D:\Music"
        ));
        assert!(!LibraryScanner::is_path_under_dir(
            r"D:\Music_HiRes\song.flac",
            r"D:\Music"
        ));
        // Different drive root MUST NOT match
        assert!(!LibraryScanner::is_path_under_dir(
            r"E:\Music\song.flac",
            r"D:\Music"
        ));
    }
}
