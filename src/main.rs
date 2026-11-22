#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod api;
mod audio;
mod cache;
mod config;
mod database;
mod paths;
mod services;
mod workers;

use std::path::PathBuf;
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use tao::dpi::LogicalSize;
use tao::event::{Event, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoopBuilder};
use tao::window::{Fullscreen, WindowBuilder};
use wry::{MemoryUsageLevel, Theme, WebViewBuilder, WebViewBuilderExtWindows, WebViewExtWindows};

use crate::api::{
    now_epoch_ms, start_http_server, ZFPlayerAPI, LAST_UI_ACTIVITY_MS, UI_CLOSED, UI_CONNECTED,
};
use crate::audio::AudioEngine;
use crate::cache::CacheManager;
use crate::config::Config;
use crate::database::Database;
use crate::paths::{get_cache_dir, get_frontend_dir};
use crate::services::{LibraryService, PlayerService};
use crate::workers::{LibraryScanner, LyricsWorker};

#[derive(Debug, Clone, Copy)]
enum UserEvent {
    ToggleFullscreen,
}

/// Safe low-RAM Chromium / WebView2 flags compatible with both hardware GPUs and
/// Windows Sandbox (software Basic Render Driver + elevated WDAGUtilityAccount).
/// Note: `--test-type` suppresses any command-line flag notice banner in Chromium.
const LOW_RAM_BROWSER_ARGS: &str = concat!(
    "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection,Translate,OptimizationHints,",
    "MediaRouter,SpareRendererForSitePerProcess,BackForwardCache,",
    "AudioServiceOutOfProcess,InterestFeedContentSuggestions,AutofillServerCommunication,OutOfProcessPdf ",
    "--renderer-process-limit=1 ",
    "--js-flags=--max-old-space-size=64 ",
    "--disable-extensions ",
    "--disable-component-update ",
    "--disable-background-networking ",
    "--disable-sync ",
    "--disable-default-apps ",
    "--disable-breakpad ",
    "--disable-crash-reporter ",
    "--disable-speech-api ",
    "--no-default-browser-check ",
    "--no-first-run ",
    "--no-sandbox ",
    "--disable-gpu-sandbox ",
    "--test-type"
);

/// JavaScript bridge injected at document creation so `window.pywebview.api` works seamlessly
/// alongside the native Rust HTTP RPC server.
const INIT_BRIDGE_SCRIPT: &str = r#"
(function() {
    if (!window.pywebview) {
        const rpcCall = async (method, ...args) => {
            const resp = await fetch('/api/rpc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ method, args })
            });
            if (!resp.ok) {
                throw new Error(`RPC HTTP error ${resp.status} on ${method}`);
            }
            const res = await resp.json();
            if (method === 'toggle_fullscreen' && res && res.handled === false) {
                if (document.fullscreenElement) {
                    document.exitFullscreen().catch(() => {});
                } else {
                    document.documentElement.requestFullscreen().catch(() => {});
                }
            }
            return res;
        };
        window.pywebview = {
            api: new Proxy({}, {
                get: (_target, prop) => {
                    if (typeof prop !== 'string' || prop === 'then') return undefined;
                    return (...args) => rpcCall(prop, ...args);
                }
            })
        };
        window.addEventListener('DOMContentLoaded', () => {
            window.dispatchEvent(new Event('pywebviewready'));
        });
    }
})();
"#;

/// Trim the current process working set on Windows to keep RAM footprint minimal.
fn trim_process_working_set() {
    #[cfg(target_os = "windows")]
    {
        extern "system" {
            fn GetCurrentProcess() -> isize;
            fn SetProcessWorkingSetSize(
                hProcess: isize,
                dwMinimumWorkingSetSize: usize,
                dwMaximumWorkingSetSize: usize,
            ) -> i32;
        }
        unsafe {
            let _ = SetProcessWorkingSetSize(GetCurrentProcess(), usize::MAX, usize::MAX);
        }
    }
}

/// Locate built-in Microsoft Edge or Chrome executable for Zero-WebView2 App Mode fallback
/// (e.g., on clean Windows Sandbox or stripped Windows LTSC without WebView2 Runtime).
fn find_system_chromium_browser() -> Option<PathBuf> {
    let candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ];
    for c in candidates {
        let p = PathBuf::from(c);
        if p.is_file() {
            return Some(p);
        }
    }
    if let Ok(local_app) = std::env::var("LOCALAPPDATA") {
        for sub in [
            r"Microsoft\Edge\Application\msedge.exe",
            r"Google\Chrome\Application\chrome.exe",
        ] {
            let p = PathBuf::from(&local_app).join(sub);
            if p.is_file() {
                return Some(p);
            }
        }
    }
    None
}

/// Launch built-in Edge/Chrome in chromeless Desktop App Mode (`--app=...`) when WebView2
/// runtime is unavailable (such as inside a clean Windows Sandbox).
fn run_browser_app_fallback(
    app_url: &str,
    audio_engine: &AudioEngine,
    library_service: &LibraryService,
) -> bool {
    let Some(browser_exe) = find_system_chromium_browser() else {
        return false;
    };

    let profile_dir = get_cache_dir().join("app_browser_profile");
    let _ = std::fs::create_dir_all(&profile_dir);

    UI_CONNECTED.store(false, Ordering::SeqCst);
    UI_CLOSED.store(false, Ordering::SeqCst);

    log::info!(
        "Launching Zero-WebView2 App Mode via {:?} at {}",
        browser_exe,
        app_url
    );

    let spawn_app = || {
        let mut cmd = Command::new(&browser_exe);
        cmd.arg(format!("--app={}", app_url))
            .arg(format!("--user-data-dir={}", profile_dir.to_string_lossy()))
            .arg("--window-size=1280,800")
            .arg("--no-first-run")
            .arg("--no-default-browser-check")
            .arg("--disable-extensions")
            .arg("--disable-sync")
            .arg("--disable-background-networking")
            .arg("--disable-component-update")
            .arg("--disable-background-timer-throttling")
            .arg("--disable-renderer-backgrounding")
            .arg("--disable-features=Translate,OptimizationHints,MediaRouter,msWebOOUI,msPdfOOUI,msSmartScreenProtection,AudioServiceOutOfProcess,SpareRendererForSitePerProcess")
            .arg("--renderer-process-limit=1")
            .arg("--js-flags=--max-old-space-size=64")
            .arg("--no-sandbox")
            .arg("--disable-gpu-sandbox")
            .arg("--test-type");
        cmd.spawn()
    };

    let Ok(mut child) = spawn_app() else {
        return false;
    };

    trim_process_working_set();

    // 1. Wait up to 25 seconds for the browser window to connect to our local HTTP server.
    // Never exit early if the initial launcher stub process hands off to a background broker!
    let start_wait = Instant::now();
    let mut retried_spawn = false;
    while !UI_CONNECTED.load(Ordering::SeqCst) && start_wait.elapsed() < Duration::from_secs(25) {
        if !retried_spawn && start_wait.elapsed() > Duration::from_millis(3000) {
            if let Ok(Some(_)) = child.try_wait() {
                if !UI_CONNECTED.load(Ordering::SeqCst) {
                    retried_spawn = true;
                    if let Ok(new_child) = spawn_app() {
                        child = new_child;
                    }
                }
            }
        }
        thread::sleep(Duration::from_millis(100));
    }

    // 2. Keep the Rust backend server alive for the entire lifetime of the UI window.
    loop {
        if UI_CLOSED.load(Ordering::SeqCst) {
            // Grace check of 400ms in case user merely refreshed (F5) the page
            thread::sleep(Duration::from_millis(400));
            if UI_CLOSED.load(Ordering::SeqCst) {
                break;
            }
        }

        let last_ms = LAST_UI_ACTIVITY_MS.load(Ordering::SeqCst);
        let now_ms = now_epoch_ms();
        if last_ms > 0 && now_ms.saturating_sub(last_ms) > 12_000 {
            // No heartbeat for > 12 seconds -> window was closed
            break;
        }

        // Also check if child process is still running and UI never connected
        if !UI_CONNECTED.load(Ordering::SeqCst) {
            if let Ok(Some(_)) = child.try_wait() {
                break;
            }
        }

        thread::sleep(Duration::from_millis(250));
    }

    library_service.scanner.stop();
    audio_engine.shutdown_hardware_stream();
    true
}

fn load_window_icon() -> Option<tao::window::Icon> {
    let img = image::load_from_memory(include_bytes!("../frontend/app_icon.png")).ok()?;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    tao::window::Icon::from_rgba(rgba.into_raw(), w, h).ok()
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    log::info!("Starting ZennyFLAC Player (Rust Edition v3.0)...");

    // 1. Initialize core storage, audio engine, workers, and domain services
    let database = Database::new();
    let config = Config::new();
    let cache_manager = CacheManager::new();
    let audio_engine = AudioEngine::new(config.clone());

    let lyrics_worker = LyricsWorker::new(database.clone());
    let scanner = LibraryScanner::new(
        database.clone(),
        cache_manager.clone(),
        Some(lyrics_worker.clone()),
    );

    let library_service = LibraryService::new(
        database.clone(),
        cache_manager.clone(),
        scanner,
        lyrics_worker.clone(),
        config.clone(),
    );

    let player_service = PlayerService::new(
        audio_engine.clone(),
        library_service.clone(),
        config.clone(),
        lyrics_worker.clone(),
    );

    let api = ZFPlayerAPI::new(
        player_service,
        library_service,
        lyrics_worker,
        config.clone(),
        audio_engine.clone(),
    );

    // 2. Start embedded multi-threaded HTTP + JSON-RPC server
    let frontend_dir = get_frontend_dir();
    let covers_dir = cache_manager.covers_dir.clone();
    let app_mode_heartbeat = Arc::new(AtomicBool::new(false));
    let port = start_http_server(
        api.clone(),
        frontend_dir,
        covers_dir,
        app_mode_heartbeat.clone(),
    );
    let app_url = format!("http://127.0.0.1:{}", port);

    // 3. Check if WebView2 Runtime is available; if not (e.g. Windows Sandbox without WebView2)
    // or if --app-mode is requested, launch Zero-WebView2 App Mode immediately.
    let force_app_mode = std::env::var("ZFPLAYER_APP_MODE")
        .map(|v| v == "1")
        .unwrap_or(false)
        || std::env::args().any(|a| a == "--app-mode")
        || wry::webview_version().is_err();

    if force_app_mode {
        app_mode_heartbeat.store(true, Ordering::SeqCst);
        if run_browser_app_fallback(&app_url, &audio_engine, &api.library_service) {
            return;
        }
        app_mode_heartbeat.store(false, Ordering::SeqCst);
    }

    // 4. Create native desktop window (initially hidden to prevent any white window flash)
    let event_loop = EventLoopBuilder::<UserEvent>::with_user_event().build();
    let proxy = event_loop.create_proxy();

    api.set_fullscreen_callback(move || {
        let _ = proxy.send_event(UserEvent::ToggleFullscreen);
    });

    let window = WindowBuilder::new()
        .with_title("ZFPlayer")
        .with_window_icon(load_window_icon())
        .with_inner_size(LogicalSize::new(1280.0, 800.0))
        .with_min_inner_size(LogicalSize::new(900.0, 600.0))
        .with_visible(false)
        .build(&event_loop)
        .expect("Failed to create desktop window");

    let webview_data_dir = get_cache_dir().join("webview_rust_lowram");
    let _ = std::fs::create_dir_all(&webview_data_dir);

    let mut web_context = wry::WebContext::new(Some(webview_data_dir));
    let webview_res = WebViewBuilder::new(&window)
        .with_web_context(&mut web_context)
        .with_url(&app_url)
        .with_background_color((11, 13, 18, 255))
        .with_theme(Theme::Dark)
        .with_additional_browser_args(LOW_RAM_BROWSER_ARGS)
        .with_browser_accelerator_keys(false)
        .with_initialization_script(INIT_BRIDGE_SCRIPT)
        .with_devtools(cfg!(debug_assertions))
        .build();

    let webview = match webview_res {
        Ok(wv) => {
            let _ = wv.set_memory_usage_level(MemoryUsageLevel::Normal);
            window.set_visible(true);
            trim_process_working_set();
            wv
        }
        Err(err) => {
            log::warn!(
                "WebView2 initialization failed ({}). Falling back to Zero-WebView2 App Mode...",
                err
            );
            drop(window);
            app_mode_heartbeat.store(true, Ordering::SeqCst);
            if run_browser_app_fallback(&app_url, &audio_engine, &api.library_service) {
                return;
            }
            panic!("Failed to initialize both WebView2 and Edge App Mode: {}", err);
        }
    };

    // 5. Run native Win32 event loop
    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;

        match event {
            Event::UserEvent(UserEvent::ToggleFullscreen) => {
                if window.fullscreen().is_some() {
                    window.set_fullscreen(None);
                } else {
                    window.set_fullscreen(Some(Fullscreen::Borderless(None)));
                }
            }
            Event::WindowEvent {
                event: WindowEvent::Focused(focused),
                ..
            } => {
                if focused {
                    let _ = webview.set_memory_usage_level(MemoryUsageLevel::Normal);
                } else {
                    let _ = webview.set_memory_usage_level(MemoryUsageLevel::Low);
                    trim_process_working_set();
                }
            }
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => {
                log::info!("Window closed. Shutting down scanner and WASAPI stream...");
                api.library_service.scanner.stop();
                audio_engine.shutdown_hardware_stream();
                *control_flow = ControlFlow::Exit;
            }
            _ => {}
        }
    });
}
