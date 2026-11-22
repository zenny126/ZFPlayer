use lofty::file::{AudioFile, TaggedFileExt};
use lofty::probe::Probe;
use lofty::tag::{Accessor, ItemKey};
use sha2::{Digest, Sha256};
use std::path::Path;

use crate::database::TrackRecord;

pub struct ExtractedMetadata {
    pub record: TrackRecord,
    pub cover_bytes: Option<Vec<u8>>,
}

pub struct MetadataWorker;

impl MetadataWorker {
    pub fn extract(file_path: &str, mtime: f64, size: i64) -> Option<ExtractedMetadata> {
        let path = Path::new(file_path);
        let tagged_file = Probe::open(path).ok()?.read().ok()?;

        let props = tagged_file.properties();
        let duration = props.duration().as_secs_f64();
        let sample_rate = props.sample_rate().unwrap_or(44100) as i64;
        let bit_depth = props.bit_depth().unwrap_or(16) as i64;
        let channels = props.channels().unwrap_or(2) as i64;

        let mut title = String::from("Unknown");
        let mut artist = String::from("Unknown");
        let mut album = String::from("Unknown");
        let mut track_number: i64 = 0;
        let mut cover_bytes: Option<Vec<u8>> = None;

        if let Some(tag) = tagged_file
            .primary_tag()
            .or_else(|| tagged_file.first_tag())
        {
            if let Some(t) = tag.title() {
                let s = t.trim();
                if !s.is_empty() {
                    title = s.to_string();
                }
            }
            if let Some(a) = tag.artist() {
                let s = a.trim();
                if !s.is_empty() {
                    artist = s.to_string();
                }
            }
            if let Some(al) = tag.album() {
                let s = al.trim();
                if !s.is_empty() {
                    album = s.to_string();
                }
            }
            if let Some(tr) = tag.track() {
                track_number = tr as i64;
            }
            if let Some(pic) = tag.pictures().first() {
                let data = pic.data();
                if !data.is_empty() {
                    cover_bytes = Some(data.to_vec());
                }
            }
        }

        // Fallback title to filename stem if still Unknown
        if title == "Unknown" {
            if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                if !stem.trim().is_empty() {
                    title = stem.trim().to_string();
                }
            }
        }

        let cover_hash = if let Some(ref bytes) = cover_bytes {
            let mut hasher = Sha256::new();
            hasher.update(bytes);
            hex::encode(hasher.finalize())
        } else {
            String::new()
        };

        let record = TrackRecord {
            id: None,
            path: file_path.to_string(),
            mtime,
            size,
            title,
            artist,
            album,
            track_number,
            duration,
            sample_rate,
            bit_depth,
            channels,
            cover_hash,
            is_liked: 0,
            last_played: None,
            created_at: None,
            cover_url: None,
        };

        Some(ExtractedMetadata {
            record,
            cover_bytes,
        })
    }

    /// Extract embedded synced lyrics from FLAC Vorbis comments or MP3 ID3 tags.
    pub fn extract_embedded_lyrics(file_path: &str) -> Option<String> {
        let path = Path::new(file_path);
        if !path.exists() {
            return None;
        }
        let tagged_file = Probe::open(path).ok()?.read().ok()?;
        for tag in tagged_file.tags() {
            if let Some(lyrics) = tag.get_string(&ItemKey::Lyrics) {
                let trimmed = lyrics.trim();
                if trimmed.contains('[') && trimmed.contains(':') {
                    return Some(trimmed.to_string());
                }
            }
            for item in tag.items() {
                if let ItemKey::Unknown(ref key) = item.key() {
                    let lower = key.to_lowercase();
                    if lower == "syncedlyrics"
                        || lower == "lyrics_synced"
                        || lower == "lyrics"
                        || lower == "unsyncedlyrics"
                        || lower.starts_with("sylt")
                        || lower.starts_with("uslt")
                    {
                        if let Some(text) = item.value().text() {
                            let trimmed = text.trim();
                            if trimmed.contains('[') && trimmed.contains(':') {
                                return Some(trimmed.to_string());
                            }
                        }
                    }
                }
            }
        }
        None
    }
}
