pub mod app;
pub mod fluid_bg;
pub mod lyrics_view;
pub mod modals;
pub mod theme;

use iced::futures::channel::oneshot;
use iced::Task;
use serde_json::Value;

#[derive(Clone, Debug, PartialEq)]
pub struct TrackItem {
    pub path: String,
    pub title: String,
    pub artist: String,
    pub album: String,
    pub duration: f64,
    pub sample_rate: i64,
    pub bit_depth: i64,
    pub cover_hash: String,
    pub is_liked: bool,
}

impl TrackItem {
    pub fn from_json(v: &Value) -> Option<Self> {
        let path = v.get("path")?.as_str()?.to_string();
        if path.is_empty() {
            return None;
        }
        Some(Self {
            path,
            title: v
                .get("title")
                .and_then(|x| x.as_str())
                .filter(|s| !s.is_empty())
                .unwrap_or("Unknown")
                .to_string(),
            artist: v
                .get("artist")
                .and_then(|x| x.as_str())
                .filter(|s| !s.is_empty())
                .unwrap_or("Unknown Artist")
                .to_string(),
            album: v
                .get("album")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            duration: v.get("duration").and_then(|x| x.as_f64()).unwrap_or(0.0),
            sample_rate: v
                .get("sample_rate")
                .and_then(|x| x.as_i64())
                .unwrap_or(44100),
            bit_depth: v.get("bit_depth").and_then(|x| x.as_i64()).unwrap_or(16),
            cover_hash: v
                .get("cover_hash")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            is_liked: v
                .get("is_liked")
                .and_then(|x| x.as_i64().map(|n| n != 0).or_else(|| x.as_bool()))
                .unwrap_or(false),
        })
    }
}

#[derive(Clone, Debug)]
pub struct PlaylistItem {
    pub id: String,
    pub name: String,
    pub track_count: i64,
    pub cover_hash: String,
}

impl PlaylistItem {
    pub fn from_json(v: &Value) -> Option<Self> {
        let id = match v.get("id")? {
            Value::Number(n) => n.to_string(),
            Value::String(s) => s.clone(),
            _ => return None,
        };
        let name = v
            .get("name")
            .and_then(|x| x.as_str())
            .unwrap_or("Playlist")
            .to_string();
        let track_count = v
            .get("track_count")
            .and_then(|x| x.as_i64())
            .unwrap_or(0);
        let cover_hash = v
            .get("cover_hash")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string();
        Some(Self {
            id,
            name,
            track_count,
            cover_hash,
        })
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct LyricLine {
    pub time: f64,
    pub text: String,
}

pub fn format_time(sec: f64) -> String {
    if !sec.is_finite() || sec <= 0.0 {
        return "0:00".to_string();
    }
    let total = sec.floor() as u64;
    let m = total / 60;
    let s = total % 60;
    format!("{}:{:02}", m, s)
}

pub fn format_audio_quality(track: &TrackItem) -> (String, bool) {
    let ext = std::path::Path::new(&track.path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_ascii_uppercase())
        .unwrap_or_else(|| "AUDIO".to_string());

    let sr = track.sample_rate;
    let bd = track.bit_depth;
    let sr_khz = if sr > 0 {
        if sr % 1000 == 0 {
            format!("{}kHz", sr / 1000)
        } else {
            format!("{:.1}kHz", sr as f64 / 1000.0)
        }
    } else {
        String::new()
    };

    let spec = match (bd > 0, !sr_khz.is_empty()) {
        (true, true) => format!("{}-bit/{}", bd, sr_khz),
        (false, true) => sr_khz,
        (true, false) => format!("{}-bit", bd),
        (false, false) => String::new(),
    };

    let label = if spec.is_empty() {
        ext.clone()
    } else {
        format!("{} · {}", ext, spec)
    };

    let is_hires = matches!(ext.as_str(), "FLAC" | "WAV" | "AIFF" | "ALAC")
        && (bd >= 24 || sr > 48000);

    (label, is_hires)
}

/// Run a blocking backend operation on a dedicated OS thread and deliver its result as an `iced::Task`.
pub fn spawn_blocking<T, F, M>(work: F, map: fn(T) -> M) -> Task<M>
where
    T: Send + 'static,
    F: FnOnce() -> T + Send + 'static,
    M: Send + 'static,
{
    Task::perform(
        async move {
            let (tx, rx) = oneshot::channel::<T>();
            std::thread::spawn(move || {
                let res = work();
                let _ = tx.send(res);
            });
            rx.await.expect("blocking task thread panicked")
        },
        map,
    )
}
