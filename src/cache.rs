use image::codecs::jpeg::JpegEncoder;
use image::DynamicImage;
use std::collections::{HashMap, HashSet};
use std::fs::{self, File};
use std::io::BufWriter;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use crate::paths::get_cache_dir;

#[derive(Clone)]
pub struct CacheManager {
    pub covers_dir: PathBuf,
    pub lyrics_dir: PathBuf,
    cover_path_cache: Arc<Mutex<HashMap<String, PathBuf>>>,
    saved_covers: Arc<Mutex<HashSet<String>>>,
    saved_thumbnails: Arc<Mutex<HashSet<String>>>,
}

impl CacheManager {
    pub fn new() -> Self {
        Self::new_at(get_cache_dir())
    }

    pub fn new_at(cache_dir: PathBuf) -> Self {
        let covers_dir = cache_dir.join("covers");
        let lyrics_dir = cache_dir.join("lyrics");

        let _ = fs::create_dir_all(&covers_dir);
        let _ = fs::create_dir_all(&lyrics_dir);

        Self {
            covers_dir,
            lyrics_dir,
            cover_path_cache: Arc::new(Mutex::new(HashMap::new())),
            saved_covers: Arc::new(Mutex::new(HashSet::new())),
            saved_thumbnails: Arc::new(Mutex::new(HashSet::new())),
        }
    }

    pub fn save_cover_and_thumbnail(&self, image_bytes: &[u8], cover_hash: &str) {
        if cover_hash.is_empty() || image_bytes.is_empty() {
            return;
        }

        let full_path = self.covers_dir.join(format!("{}.jpg", cover_hash));
        let thumb_path = self.covers_dir.join(format!("{}_thumb.jpg", cover_hash));

        let need_full = {
            let mut saved = self.saved_covers.lock().unwrap();
            if saved.contains(cover_hash) || full_path.exists() {
                saved.insert(cover_hash.to_string());
                false
            } else {
                true
            }
        };

        let need_thumb = {
            let mut saved = self.saved_thumbnails.lock().unwrap();
            if saved.contains(cover_hash) || thumb_path.exists() {
                saved.insert(cover_hash.to_string());
                false
            } else {
                true
            }
        };

        if !need_full && !need_thumb {
            return;
        }

        let Ok(img) = image::load_from_memory(image_bytes) else {
            return;
        };

        if need_full {
            if Self::write_jpeg(&img, &full_path, 90) {
                self.saved_covers
                    .lock()
                    .unwrap()
                    .insert(cover_hash.to_string());
                self.cover_path_cache
                    .lock()
                    .unwrap()
                    .insert(cover_hash.to_string(), full_path);
            }
        }

        if need_thumb {
            let thumb = img.thumbnail(300, 300);
            if Self::write_jpeg(&thumb, &thumb_path, 85) {
                self.saved_thumbnails
                    .lock()
                    .unwrap()
                    .insert(cover_hash.to_string());
            }
        }
    }

    fn write_jpeg(img: &DynamicImage, path: &PathBuf, quality: u8) -> bool {
        let rgb = img.to_rgb8();
        let Ok(file) = File::create(path) else {
            return false;
        };
        let writer = BufWriter::new(file);
        let mut encoder = JpegEncoder::new_with_quality(writer, quality);
        encoder
            .encode(
                rgb.as_raw(),
                rgb.width(),
                rgb.height(),
                image::ExtendedColorType::Rgb8,
            )
            .is_ok()
    }

    pub fn clear_all(&self) {
        self.cover_path_cache.lock().unwrap().clear();
        self.saved_covers.lock().unwrap().clear();
        self.saved_thumbnails.lock().unwrap().clear();

        for dir in [&self.covers_dir, &self.lyrics_dir] {
            if let Ok(entries) = fs::read_dir(dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.is_file() {
                        let _ = fs::remove_file(path);
                    }
                }
            }
        }
    }
}
