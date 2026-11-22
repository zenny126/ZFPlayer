use percent_encoding::percent_decode_str;
use rfd::FileDialog;
use serde::Deserialize;
use serde_json::{json, Value};
use std::fs;
use std::net::TcpListener;
use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};
use tiny_http::{Header, Method, Request, Response, Server, StatusCode};

pub static UI_CONNECTED: AtomicBool = AtomicBool::new(false);
pub static UI_CLOSED: AtomicBool = AtomicBool::new(false);
pub static LAST_UI_ACTIVITY_MS: AtomicU64 = AtomicU64::new(0);

pub fn now_epoch_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn mark_ui_alive() {
    UI_CONNECTED.store(true, Ordering::SeqCst);
    UI_CLOSED.store(false, Ordering::SeqCst);
    LAST_UI_ACTIVITY_MS.store(now_epoch_ms(), Ordering::SeqCst);
}

use crate::audio::AudioEngine;
use crate::config::Config;
use crate::services::{LibraryService, PlayerService};
use crate::workers::LyricsWorker;

#[derive(Deserialize)]
struct RpcPayload {
    method: String,
    #[serde(default)]
    args: Vec<Value>,
}

#[derive(Clone)]
pub struct ZFPlayerAPI {
    pub player_service: PlayerService,
    pub library_service: LibraryService,
    pub lyrics_worker: LyricsWorker,
    pub config: Config,
    pub audio_engine: Arc<AudioEngine>,
    fullscreen_cb: Arc<Mutex<Option<Box<dyn Fn() + Send + Sync + 'static>>>>,
}

impl ZFPlayerAPI {
    pub fn new(
        player_service: PlayerService,
        library_service: LibraryService,
        lyrics_worker: LyricsWorker,
        config: Config,
        audio_engine: Arc<AudioEngine>,
    ) -> Self {
        Self {
            player_service,
            library_service,
            lyrics_worker,
            config,
            audio_engine,
            fullscreen_cb: Arc::new(Mutex::new(None)),
        }
    }

    pub fn set_fullscreen_callback<F>(&self, cb: F)
    where
        F: Fn() + Send + Sync + 'static,
    {
        if let Ok(mut guard) = self.fullscreen_cb.lock() {
            *guard = Some(Box::new(cb));
        }
    }

    fn arg_str(args: &[Value], idx: usize, default: &str) -> String {
        args.get(idx)
            .and_then(|v| {
                if let Some(s) = v.as_str() {
                    Some(s.to_string())
                } else if v.is_number() {
                    Some(v.to_string())
                } else {
                    None
                }
            })
            .unwrap_or_else(|| default.to_string())
    }

    fn arg_opt_str(args: &[Value], idx: usize) -> Option<String> {
        args.get(idx).and_then(|v| {
            if v.is_null() {
                None
            } else if let Some(s) = v.as_str() {
                Some(s.to_string())
            } else if v.is_number() {
                Some(v.to_string())
            } else {
                None
            }
        })
    }

    fn arg_i64(args: &[Value], idx: usize, default: i64) -> i64 {
        args.get(idx)
            .and_then(|v| {
                v.as_i64()
                    .or_else(|| v.as_str().and_then(|s| s.parse::<i64>().ok()))
            })
            .unwrap_or(default)
    }

    fn arg_f64(args: &[Value], idx: usize, default: f64) -> f64 {
        args.get(idx)
            .and_then(|v| {
                v.as_f64()
                    .or_else(|| v.as_str().and_then(|s| s.parse::<f64>().ok()))
            })
            .unwrap_or(default)
    }

    /// Unified RPC method dispatcher matching all Python `ZFPlayerAPI` methods.
    pub fn dispatch(&self, method: &str, args: &[Value]) -> Value {
        match method {
            // --- Bootstrap & Library ---
            "get_bootstrap_data" => {
                let p_state = self.player_service.get_state();
                self.library_service.get_bootstrap_data(p_state)
            }
            "get_tracks" => {
                let offset = Self::arg_i64(args, 0, 0);
                let limit = Self::arg_i64(args, 1, 50);
                let search = Self::arg_str(args, 2, "");
                let sort_by = Self::arg_str(args, 3, "title");
                let sort_dir = Self::arg_str(args, 4, "ASC");
                let pid = Self::arg_opt_str(args, 5);
                let is_fav = pid
                    .as_deref()
                    .map(|p| p == "favorites" || p == "-1")
                    .unwrap_or(false);
                json!(self.library_service.get_tracks(
                    offset,
                    limit,
                    &search,
                    &sort_by,
                    &sort_dir,
                    is_fav,
                    pid.as_deref()
                ))
            }
            "get_track_count" => {
                let search = Self::arg_str(args, 0, "");
                let pid = Self::arg_opt_str(args, 1);
                let is_fav = pid
                    .as_deref()
                    .map(|p| p == "favorites" || p == "-1")
                    .unwrap_or(false);
                json!(self
                    .library_service
                    .get_track_count(&search, is_fav, pid.as_deref()))
            }
            "get_recently_played" => {
                let limit = Self::arg_i64(args, 0, 20);
                json!(self.library_service.get_recently_played(limit))
            }
            "get_albums" => json!(self.library_service.get_albums()),
            "get_track_info" => {
                let path = Self::arg_str(args, 0, "");
                self.library_service
                    .get_track_info(&path)
                    .unwrap_or_else(|| json!({}))
            }
            "toggle_like" => {
                let path = Self::arg_str(args, 0, "");
                self.library_service.toggle_like(&path)
            }
            "scan_library" => {
                self.library_service.scan_library();
                json!({ "status": "success" })
            }
            "get_scan_progress" => self.library_service.get_scan_progress(),
            "add_album" => {
                let folder_path = Self::arg_str(args, 0, "");
                let album_name = Self::arg_str(args, 1, "");
                let cover_path = Self::arg_str(args, 2, "");
                self.library_service
                    .add_album(&folder_path, &album_name, &cover_path)
            }
            "clear_database" => {
                let clear_cache = args.first().and_then(|v| v.as_bool()).unwrap_or(true);
                self.library_service.clear_database(clear_cache)
            }

            // --- Playlists ---
            "create_playlist" => {
                let name = Self::arg_str(args, 0, "New Playlist");
                let folder_path = Self::arg_opt_str(args, 1);
                let pid = self
                    .library_service
                    .create_playlist(&name, folder_path.as_deref());
                json!({ "status": "success", "playlist_id": pid })
            }
            "delete_playlist" => {
                let pid = Self::arg_i64(args, 0, 0);
                self.library_service.delete_playlist(pid);
                json!({ "status": "success" })
            }
            "rename_playlist" => {
                let pid = Self::arg_i64(args, 0, 0);
                let new_name = Self::arg_str(args, 1, "");
                self.library_service.rename_playlist(pid, &new_name);
                json!({ "status": "success" })
            }
            "get_playlists" => json!(self.library_service.get_playlists()),
            "add_to_playlist" => {
                let pid = Self::arg_i64(args, 0, 0);
                let path = Self::arg_str(args, 1, "");
                self.library_service.add_track_to_playlist(pid, &path);
                json!({ "status": "success" })
            }
            "remove_from_playlist" => {
                let pid = Self::arg_i64(args, 0, 0);
                let path = Self::arg_str(args, 1, "");
                self.library_service.remove_track_from_playlist(pid, &path);
                json!({ "status": "success" })
            }
            "import_folder_to_playlist" => {
                let pid = Self::arg_i64(args, 0, 0);
                let folder = Self::arg_str(args, 1, "");
                self.library_service.import_folder_to_playlist(pid, &folder)
            }
            "import_files_to_playlist" => {
                let pid = Self::arg_i64(args, 0, 0);
                let files: Vec<String> = args
                    .get(1)
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str().map(|s| s.to_string()))
                            .collect()
                    })
                    .unwrap_or_default();
                self.library_service.import_files_to_playlist(pid, &files)
            }
            "update_playlist_cover" => {
                let pid = Self::arg_str(args, 0, "");
                let cover = Self::arg_str(args, 1, "");
                self.library_service.update_playlist_cover(&pid, &cover)
            }
            "get_system_playlist_covers" => self.library_service.get_system_playlist_covers(),

            // --- Player Controls & Queue ---
            "play" => {
                let path = Self::arg_str(args, 0, "");
                let pid = Self::arg_opt_str(args, 1);
                self.player_service.play(&path, pid.as_deref())
            }
            "pause" => self.player_service.pause(),
            "resume" => self.player_service.resume(),
            "stop" => self.player_service.stop(),
            "seek" => {
                let secs = Self::arg_f64(args, 0, 0.0);
                self.player_service.seek(secs)
            }
            "set_volume" => {
                let level = Self::arg_f64(args, 0, 0.8);
                self.player_service.set_volume(level)
            }
            "get_player_state" => self.player_service.get_state(),
            "next_track" => self.player_service.next_track(true),
            "prev_track" => self.player_service.prev_track(),
            "set_active_playlist" | "setActivePlaylist" => {
                let pid = Self::arg_str(args, 0, "all");
                self.player_service.set_active_playlist(&pid)
            }
            "play_next" => {
                let path = Self::arg_str(args, 0, "");
                self.player_service.insert_play_next(&path)
            }
            "set_shuffle" => {
                let state = args.first().and_then(|v| v.as_bool());
                self.player_service.set_shuffle(state)
            }
            "toggle_shuffle" => self.player_service.set_shuffle(None),
            "get_queue" => {
                let limit = Self::arg_i64(args, 0, 50).max(1) as usize;
                self.player_service.get_queue(limit)
            }
            "remove_from_queue" => {
                let path = Self::arg_str(args, 0, "");
                self.player_service.remove_from_queue(&path)
            }
            "clear_queue" => self.player_service.clear_queue(),

            // --- Lyrics ---
            "get_lyrics" => {
                let artist = Self::arg_str(args, 0, "");
                let title = Self::arg_str(args, 1, "");
                let album = Self::arg_str(args, 2, "");
                let duration = Self::arg_f64(args, 3, 0.0);
                let path = Self::arg_str(args, 4, "");
                self.lyrics_worker
                    .fetch_lyrics(&artist, &title, &album, duration, &path)
            }

            // --- Config & Dialogs ---
            "get_config" => self.config.get_all(),
            "set_config" => {
                let key = Self::arg_str(args, 0, "");
                let val = args.get(1).cloned().unwrap_or(Value::Null);
                if !key.is_empty() {
                    self.config.set(&key, val.clone());
                    if key == "audio_mode" {
                        if let Some(m) = val.as_str() {
                            self.audio_engine.set_audio_mode(m);
                        }
                    } else if key == "shuffle" {
                        if let Some(b) = val.as_bool() {
                            self.player_service.set_shuffle(Some(b));
                        }
                    }
                }
                self.config.get_all()
            }
            "set_audio_mode" => {
                let mode = Self::arg_str(args, 0, "shared");
                let active = self.audio_engine.set_audio_mode(&mode);
                json!({ "status": "success", "audio_mode": active })
            }
            "select_music_dir" => {
                if let Some(folder) = FileDialog::new().pick_folder() {
                    Value::String(folder.to_string_lossy().to_string())
                } else {
                    Value::Null
                }
            }
            "select_music_file" => {
                if let Some(file) = FileDialog::new()
                    .add_filter(
                        "Audio Files",
                        &["flac", "mp3", "wav", "ogg", "aiff", "m4a", "aac"],
                    )
                    .pick_file()
                {
                    Value::String(file.to_string_lossy().to_string())
                } else {
                    Value::Null
                }
            }
            "select_music_files" => {
                if let Some(files) = FileDialog::new()
                    .add_filter(
                        "Audio Files",
                        &["flac", "mp3", "wav", "ogg", "aiff", "m4a", "aac"],
                    )
                    .pick_files()
                {
                    let list: Vec<String> = files
                        .into_iter()
                        .map(|f| f.to_string_lossy().to_string())
                        .collect();
                    json!(list)
                } else {
                    Value::Null
                }
            }
            "select_cover_image" => {
                if let Some(file) = FileDialog::new()
                    .add_filter("Image Files", &["jpg", "jpeg", "png", "webp"])
                    .pick_file()
                {
                    Value::String(file.to_string_lossy().to_string())
                } else {
                    Value::Null
                }
            }
            "toggle_fullscreen" => {
                let mut handled = false;
                if let Ok(guard) = self.fullscreen_cb.lock() {
                    if let Some(ref cb) = *guard {
                        cb();
                        handled = true;
                    }
                }
                json!({
                    "status": if handled { "success" } else { "fallback" },
                    "handled": handled
                })
            }
            _ => {
                log::warn!("Unknown RPC method called: {}", method);
                Value::Null
            }
        }
    }
}

pub fn find_free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(18452)
}

pub fn start_http_server(
    api: ZFPlayerAPI,
    frontend_dir: PathBuf,
    covers_dir: PathBuf,
    app_mode_heartbeat: Arc<AtomicBool>,
) -> u16 {
    let port = find_free_port();
    let addr = format!("127.0.0.1:{}", port);
    let server = Arc::new(Server::http(&addr).expect("Failed to bind local HTTP server"));

    log::info!("ZennyFLAC Rust Server listening on http://{}", addr);

    // Spawn 4 worker threads for concurrent static asset & RPC serving
    for i in 0..4 {
        let srv = server.clone();
        let api_clone = api.clone();
        let f_dir = frontend_dir.clone();
        let c_dir = covers_dir.clone();
        let hb_flag = app_mode_heartbeat.clone();

        thread::Builder::new()
            .name(format!("HttpWorker-{}", i))
            .spawn(move || {
                for request in srv.incoming_requests() {
                    handle_http_request(request, &api_clone, &f_dir, &c_dir, &hb_flag);
                }
            })
            .ok();
    }

    port
}

fn handle_http_request(
    mut request: Request,
    api: &ZFPlayerAPI,
    frontend_dir: &PathBuf,
    covers_dir: &PathBuf,
    app_mode_heartbeat: &AtomicBool,
) {
    let url_raw = request.url().to_string();
    let path_part = url_raw.split('?').next().unwrap_or("/");

    if path_part == "/api/heartbeat" {
        mark_ui_alive();
        let _ = request.respond(Response::from_string("ok"));
        return;
    }

    if path_part == "/api/window_closed" {
        UI_CLOSED.store(true, Ordering::SeqCst);
        let _ = request.respond(Response::from_string("bye"));
        return;
    }

    mark_ui_alive();

    // 1. Handle JSON-RPC API endpoint: POST /api/rpc
    if *request.method() == Method::Post && path_part == "/api/rpc" {
        let mut body = String::new();
        let _ = request.as_reader().read_to_string(&mut body);
        let response_val = match serde_json::from_str::<RpcPayload>(&body) {
            Ok(payload) => api.dispatch(&payload.method, &payload.args),
            Err(e) => json!({ "status": "error", "message": format!("Invalid JSON: {}", e) }),
        };

        let bytes = serde_json::to_vec(&response_val).unwrap_or_else(|_| b"null".to_vec());
        let content_type = Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap();
        let cache_ctrl = Header::from_bytes(&b"Cache-Control"[..], &b"no-store"[..]).unwrap();
        let resp = Response::from_data(bytes)
            .with_header(content_type)
            .with_header(cache_ctrl);
        let _ = request.respond(resp);
        return;
    }

    // 2. Serve album covers: /api/covers/<filename>
    if let Some(cover_name) = path_part.strip_prefix("/api/covers/") {
        let Some(safe_rel) = sanitize_rel_path(cover_name) else {
            let resp = Response::from_string("Bad Request").with_status_code(StatusCode(400));
            let _ = request.respond(resp);
            return;
        };
        let file_path = covers_dir.join(safe_rel);
        serve_static_file(
            request,
            &file_path,
            "image/jpeg",
            "public, max-age=31536000, immutable",
        );
        return;
    }

    // 3. Serve frontend static files
    let rel_raw = if path_part == "/" || path_part.is_empty() {
        "index.html"
    } else {
        path_part.strip_prefix('/').unwrap_or(path_part)
    };

    let Some(safe_rel_path) = sanitize_rel_path(rel_raw) else {
        let resp = Response::from_string("Bad Request").with_status_code(StatusCode(400));
        let _ = request.respond(resp);
        return;
    };

    let safe_rel_str = rel_path_to_unix_string(&safe_rel_path);
    let target_file = frontend_dir.join(&safe_rel_path);
    let mime = guess_mime_type(&safe_rel_str);
    let cache = if safe_rel_str == "index.html" || safe_rel_str.ends_with(".js") {
        "no-cache"
    } else {
        "public, max-age=86400"
    };

    if safe_rel_str == "index.html" {
        let raw_bytes = if target_file.exists() {
            fs::read(&target_file).ok()
        } else {
            get_embedded_frontend_asset("index.html").map(|b| b.to_vec())
        };
        if let Some(bytes) = raw_bytes {
            let html = String::from_utf8_lossy(&bytes);
            let heartbeat_snippet = if app_mode_heartbeat.load(Ordering::Relaxed) {
                r#"
    setInterval(() => {
        fetch('/api/heartbeat', { method: 'GET', cache: 'no-store' }).catch(() => {});
    }, 3000);
    window.addEventListener('pagehide', () => {
        if (navigator.sendBeacon) navigator.sendBeacon('/api/window_closed');
    });"#
            } else {
                ""
            };
            let bridge_tag = format!(
                r#"<script>
(function() {{
    if (!window.pywebview) {{
        const rpcCall = async (method, ...args) => {{
            const resp = await fetch('/api/rpc', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ method, args }})
            }});
            if (!resp.ok) throw new Error(`RPC HTTP error ${{resp.status}} on ${{method}}`);
            const res = await resp.json();
            if (method === 'toggle_fullscreen' && res && res.handled === false) {{
                if (document.fullscreenElement) {{
                    document.exitFullscreen().catch(() => {{}});
                }} else {{
                    document.documentElement.requestFullscreen().catch(() => {{}});
                }}
            }}
            return res;
        }};
        window.pywebview = {{
            api: new Proxy({{}}, {{
                get: (_target, prop) => {{
                    if (typeof prop !== 'string' || prop === 'then') return undefined;
                    return (...args) => rpcCall(prop, ...args);
                }}
            }})
        }};
        window.addEventListener('DOMContentLoaded', () => {{
            window.dispatchEvent(new Event('pywebviewready'));
        }});
    }}{heartbeat}
}})();
</script>"#,
                heartbeat = heartbeat_snippet
            );
            let injected = if let Some(idx) = html.find("<head>") {
                let mut out = String::with_capacity(html.len() + bridge_tag.len() + 16);
                out.push_str(&html[..idx + 6]);
                out.push_str(&bridge_tag);
                out.push_str(&html[idx + 6..]);
                out
            } else {
                format!("{}{}", bridge_tag, html)
            };
            let ct = Header::from_bytes(&b"Content-Type"[..], mime.as_bytes()).unwrap();
            let cc = Header::from_bytes(&b"Cache-Control"[..], cache.as_bytes()).unwrap();
            let resp = Response::from_data(injected.into_bytes())
                .with_header(ct)
                .with_header(cc);
            let _ = request.respond(resp);
            return;
        }
    }

    if target_file.exists() {
        serve_static_file(request, &target_file, mime, cache);
    } else if let Some(embedded_bytes) = get_embedded_frontend_asset(&safe_rel_str) {
        let ct = Header::from_bytes(&b"Content-Type"[..], mime.as_bytes()).unwrap();
        let cc = Header::from_bytes(&b"Cache-Control"[..], cache.as_bytes()).unwrap();
        let resp = Response::from_data(embedded_bytes.to_vec())
            .with_header(ct)
            .with_header(cc);
        let _ = request.respond(resp);
    } else {
        let resp = Response::from_string("Not Found").with_status_code(StatusCode(404));
        let _ = request.respond(resp);
    }
}

/// Percent-decode and sanitize a relative HTTP request path, rejecting directory traversal (`..`)
/// and rooted/drive-prefixed paths.
pub fn sanitize_rel_path(raw: &str) -> Option<PathBuf> {
    let decoded = percent_decode_str(raw).decode_utf8_lossy();
    if decoded.is_empty()
        || decoded.starts_with('/')
        || decoded.starts_with('\\')
        || decoded.contains('\0')
    {
        return None;
    }

    let unified = decoded.replace('\\', "/");
    let mut clean = PathBuf::new();
    for seg in unified.split('/') {
        if seg.is_empty() || seg == "." {
            continue;
        }
        if seg == ".." || seg.contains(':') {
            return None;
        }
        clean.push(seg);
    }

    for comp in clean.components() {
        if !matches!(comp, Component::Normal(_)) {
            return None;
        }
    }

    if clean.as_os_str().is_empty() {
        None
    } else {
        Some(clean)
    }
}

fn rel_path_to_unix_string(path: &Path) -> String {
    path.components()
        .filter_map(|c| match c {
            Component::Normal(s) => Some(s.to_string_lossy().into_owned()),
            _ => None,
        })
        .collect::<Vec<_>>()
        .join("/")
}

fn get_embedded_frontend_asset(rel_path: &str) -> Option<&'static [u8]> {
    match rel_path.replace('\\', "/").as_str() {
        "index.html" => Some(include_bytes!("../../frontend/index.html")),
        "favicon.ico" => Some(include_bytes!("../../frontend/favicon.ico")),
        "app_icon.ico" => Some(include_bytes!("../../frontend/app_icon.ico")),
        "app_icon.png" => Some(include_bytes!("../../frontend/app_icon.png")),
        "css/albums.css" => Some(include_bytes!("../../frontend/css/albums.css")),
        "css/library.css" => Some(include_bytes!("../../frontend/css/library.css")),
        "css/lyrics.css" => Some(include_bytes!("../../frontend/css/lyrics.css")),
        "css/main.css" => Some(include_bytes!("../../frontend/css/main.css")),
        "css/player.css" => Some(include_bytes!("../../frontend/css/player.css")),
        "js/albums.js" => Some(include_bytes!("../../frontend/js/albums.js")),
        "js/api.js" => Some(include_bytes!("../../frontend/js/api.js")),
        "js/fluid-shader.js" => Some(include_bytes!("../../frontend/js/fluid-shader.js")),
        "js/home.js" => Some(include_bytes!("../../frontend/js/home.js")),
        "js/library.js" => Some(include_bytes!("../../frontend/js/library.js")),
        "js/lyrics.js" => Some(include_bytes!("../../frontend/js/lyrics.js")),
        "js/main.js" => Some(include_bytes!("../../frontend/js/main.js")),
        "js/player.js" => Some(include_bytes!("../../frontend/js/player.js")),
        "js/playlists.js" => Some(include_bytes!("../../frontend/js/playlists.js")),
        "js/queue.js" => Some(include_bytes!("../../frontend/js/queue.js")),
        "js/shortcuts.js" => Some(include_bytes!("../../frontend/js/shortcuts.js")),
        "js/store.js" => Some(include_bytes!("../../frontend/js/store.js")),
        "js/ui.js" => Some(include_bytes!("../../frontend/js/ui.js")),
        _ => None,
    }
}

fn serve_static_file(request: Request, file_path: &PathBuf, mime: &str, cache_header: &str) {
    if let Ok(bytes) = fs::read(file_path) {
        let ct = Header::from_bytes(&b"Content-Type"[..], mime.as_bytes()).unwrap();
        let cc = Header::from_bytes(&b"Cache-Control"[..], cache_header.as_bytes()).unwrap();
        let resp = Response::from_data(bytes).with_header(ct).with_header(cc);
        let _ = request.respond(resp);
    } else {
        let resp = Response::from_string("Not Found").with_status_code(StatusCode(404));
        let _ = request.respond(resp);
    }
}

fn guess_mime_type(path: &str) -> &'static str {
    let lower = path.to_ascii_lowercase();
    if lower.ends_with(".html") {
        "text/html; charset=utf-8"
    } else if lower.ends_with(".css") {
        "text/css; charset=utf-8"
    } else if lower.ends_with(".js") {
        "application/javascript; charset=utf-8"
    } else if lower.ends_with(".png") {
        "image/png"
    } else if lower.ends_with(".jpg") || lower.ends_with(".jpeg") {
        "image/jpeg"
    } else if lower.ends_with(".ico") {
        "image/x-icon"
    } else if lower.ends_with(".svg") {
        "image/svg+xml"
    } else {
        "application/octet-stream"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitize_rel_path_blocks_traversal_and_absolute_paths() {
        assert!(sanitize_rel_path("../secret").is_none());
        assert!(sanitize_rel_path("foo/../../bar").is_none());
        assert!(sanitize_rel_path("..%2Fsecret").is_none());
        assert!(sanitize_rel_path("/abs/path").is_none());
        assert!(sanitize_rel_path("%2Fetc%2Fpasswd").is_none());
        assert!(sanitize_rel_path(r"C:\Windows\System32").is_none());
        assert!(sanitize_rel_path("").is_none());

        let ok1 = sanitize_rel_path("css/main.css").unwrap();
        assert_eq!(rel_path_to_unix_string(&ok1), "css/main.css");

        let ok2 = sanitize_rel_path("covers/My%20Album%20Art.jpg").unwrap();
        assert_eq!(rel_path_to_unix_string(&ok2), "covers/My Album Art.jpg");
    }
}
