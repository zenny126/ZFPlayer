use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use iced::keyboard::{self, key::Named, Key, Modifiers};
use iced::widget::{
    button, column, container, horizontal_space, image, mouse_area, row, scrollable, slider,
    stack, text, text_input, Column, Row, Space,
};
use iced::{window, Alignment, Border, Color, ContentFit, Element, Length, Subscription, Task};
use rfd::FileDialog;
use serde_json::{json, Value};

use crate::audio::AudioEngine;
use crate::cache::CacheManager;
use crate::config::Config;
use crate::database::Database;
use crate::services::{LibraryService, PlayerService};
use crate::workers::{LibraryScanner, LyricsWorker};

use super::fluid_bg::{default_palette, extract_dominant_colors_from_path, FluidState};
use super::lyrics_view::{self, find_active_lyric_index, parse_lrc, scroll_to_lyric_task};
use super::modals;
use super::theme;
use super::{format_audio_quality, format_time, spawn_blocking, LyricLine, PlaylistItem, TrackItem};

const PAGE_SIZE: i64 = 100;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActiveView {
    Home,
    Library,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SettingsTab {
    Audio,
    Shortcuts,
}

#[derive(Debug, Clone)]
pub enum Message {
    NoOp,
    Tick,
    ToggleSidebar,
    GoHome,
    SelectPlaylist(String),
    SearchChanged(String),
    ClearSearch,
    FocusSearch,
    NextPage,
    PrevPage,

    PlayTrack(String),
    PlayPlaylistFirst,
    TogglePlay,
    NextTrack,
    PrevTrack,
    SeekChanged(f32),
    VolumeChanged(f32),
    ToggleMute,
    ToggleShuffle,
    ToggleRepeat,
    ToggleLike(String),
    ToggleLikeCurrent,

    ToggleQueue,
    PlayNext(String),
    RemoveFromQueue(String),
    ClearQueue,

    ToggleLyrics,
    ToggleLyricsCenterMode,
    LyricsLoaded(String, Value),

    OpenSettings,
    SelectSettingsTab(SettingsTab),
    SetAudioMode(String),
    PickAndAddMusicDir,
    MusicDirPicked(Option<PathBuf>),
    ScanLibrary,
    ClearDatabase,

    OpenCreatePlaylist,
    CreatePlaylistNameChanged(String),
    SubmitCreatePlaylist,
    ImportFolderToPlaylist,
    PlaylistFolderPicked(String, Option<PathBuf>),
    ImportFilesToPlaylist,
    PlaylistFilesPicked(String, Option<Vec<PathBuf>>),
    ImportFinished,

    PaletteExtracted(String, [[f32; 3]; 4]),
    CloseModals,
    KeyPressed(Key, Modifiers),
    CloseRequested,
}

fn search_input_id() -> text_input::Id {
    text_input::Id::new("search_input")
}

pub struct ZFPlayerApp {
    config: Config,
    cache_manager: CacheManager,
    audio_engine: Arc<AudioEngine>,
    lyrics_worker: LyricsWorker,
    library_service: LibraryService,
    player_service: PlayerService,

    active_view: ActiveView,
    sidebar_collapsed: bool,
    queue_open: bool,
    lyrics_open: bool,
    lyrics_center_mode: bool,
    settings_open: bool,
    settings_tab: SettingsTab,
    create_playlist_open: bool,
    create_playlist_name: String,

    active_playlist_id: String,
    playlists: Vec<PlaylistItem>,
    recent_tracks: Vec<TrackItem>,
    library_tracks: Vec<TrackItem>,
    library_total: i64,
    library_offset: i64,
    search_query: String,
    search_focused: bool,

    current_track: Option<TrackItem>,
    is_playing: bool,
    position: f64,
    duration: f64,
    volume: f64,
    prev_nonzero_volume: f64,
    shuffle: bool,
    repeat: String,
    audio_mode: String,

    queue_current: Option<TrackItem>,
    queue_user: Vec<TrackItem>,
    queue_upcoming: Vec<TrackItem>,

    lyrics_lines: Vec<LyricLine>,
    active_lyric_index: Option<usize>,
    lyrics_status_text: String,
    lyrics_track_path: String,

    is_scanning: bool,
    scan_status_text: String,

    fluid: FluidState,
    last_fluid_cover_hash: String,
    last_tick_at: Instant,
    last_state_sync_at: Instant,

    cover_cache: HashMap<String, image::Handle>,
    toast: Option<(String, Instant)>,
}

impl ZFPlayerApp {
    pub fn new() -> (Self, Task<Message>) {
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

        let volume = config.get_f64("volume", 0.8).clamp(0.0, 1.0);
        let shuffle = config.get_bool("shuffle", false);
        let repeat = config.get_string("repeat", "off");
        let audio_mode = config.get_string("audio_mode", "shared");

        let mut app = Self {
            config,
            cache_manager,
            audio_engine,
            lyrics_worker,
            library_service,
            player_service,

            active_view: ActiveView::Home,
            sidebar_collapsed: false,
            queue_open: false,
            lyrics_open: false,
            lyrics_center_mode: false,
            settings_open: false,
            settings_tab: SettingsTab::Audio,
            create_playlist_open: false,
            create_playlist_name: String::new(),

            active_playlist_id: "all".to_string(),
            playlists: Vec::new(),
            recent_tracks: Vec::new(),
            library_tracks: Vec::new(),
            library_total: 0,
            library_offset: 0,
            search_query: String::new(),
            search_focused: false,

            current_track: None,
            is_playing: false,
            position: 0.0,
            duration: 0.0,
            volume,
            prev_nonzero_volume: if volume > 0.01 { volume } else { 0.8 },
            shuffle,
            repeat,
            audio_mode,

            queue_current: None,
            queue_user: Vec::new(),
            queue_upcoming: Vec::new(),

            lyrics_lines: Vec::new(),
            active_lyric_index: None,
            lyrics_status_text: "Play a song to see lyrics.".to_string(),
            lyrics_track_path: String::new(),

            is_scanning: false,
            scan_status_text: String::new(),

            fluid: FluidState::default(),
            last_fluid_cover_hash: String::new(),
            last_tick_at: Instant::now(),
            last_state_sync_at: Instant::now(),

            cover_cache: HashMap::new(),
            toast: None,
        };

        app.reload_playlists_and_recent();
        app.reload_library_tracks();
        let state_val = app.player_service.get_state();
        let boot_task = app.apply_player_state(&state_val);

        (app, boot_task)
    }

    pub fn title(&self) -> String {
        if let Some(ref t) = self.current_track {
            format!("{} • {} — ZFPlayer", t.title, t.artist)
        } else {
            "ZFPlayer".to_string()
        }
    }

    pub fn theme(&self) -> iced::Theme {
        iced::Theme::Dark
    }

    pub fn subscription(&self) -> Subscription<Message> {
        let tick_sub = if self.fluid.is_transitioning() {
            iced::time::every(Duration::from_millis(42)).map(|_| Message::Tick)
        } else if self.is_playing || self.is_scanning {
            iced::time::every(Duration::from_millis(80)).map(|_| Message::Tick)
        } else {
            iced::time::every(Duration::from_millis(2000)).map(|_| Message::Tick)
        };

        let keys_sub = keyboard::on_key_press(|key, modifiers| Some(Message::KeyPressed(key, modifiers)));
        let close_sub = window::close_requests().map(|_| Message::CloseRequested);

        Subscription::batch([tick_sub, keys_sub, close_sub])
    }

    fn show_toast(&mut self, msg: impl Into<String>) {
        self.toast = Some((msg.into(), Instant::now()));
    }

    fn reload_playlists_and_recent(&mut self) {
        self.playlists = self
            .library_service
            .get_playlists()
            .iter()
            .filter_map(PlaylistItem::from_json)
            .collect();
        self.recent_tracks = self
            .library_service
            .get_recently_played(20)
            .iter()
            .filter_map(TrackItem::from_json)
            .collect();
    }

    fn reload_library_tracks(&mut self) {
        let is_fav = self.active_playlist_id == "favorites";
        let pid_opt = if self.active_playlist_id == "all" || is_fav {
            None
        } else {
            Some(self.active_playlist_id.as_str())
        };

        self.library_total = self
            .library_service
            .get_track_count(&self.search_query, is_fav, pid_opt);
        if self.library_offset >= self.library_total {
            self.library_offset = 0;
        }
        self.library_tracks = self
            .library_service
            .get_tracks(
                self.library_offset,
                PAGE_SIZE,
                &self.search_query,
                "title",
                "ASC",
                is_fav,
                pid_opt,
            )
            .iter()
            .filter_map(TrackItem::from_json)
            .collect();
    }

    fn reload_queue(&mut self) {
        let q = self.player_service.get_queue(40);
        self.queue_current = q.get("current").and_then(TrackItem::from_json);
        self.queue_user = q
            .get("user_queue")
            .and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(TrackItem::from_json).collect())
            .unwrap_or_default();
        self.queue_upcoming = q
            .get("upcoming")
            .and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(TrackItem::from_json).collect())
            .unwrap_or_default();
    }

    fn apply_player_state(&mut self, state: &Value) -> Task<Message> {
        let playing = state
            .get("is_playing")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let pos = state
            .get("position_seconds")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let dur = state
            .get("duration")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let vol = state
            .get("volume")
            .and_then(|v| v.as_f64())
            .unwrap_or(self.volume);

        self.is_playing = playing;
        self.position = pos;
        if dur > 0.0 {
            self.duration = dur;
        }
        self.volume = vol;

        let new_track = state.get("track").and_then(TrackItem::from_json);
        let track_changed = match (&self.current_track, &new_track) {
            (Some(a), Some(b)) => a.path != b.path || a.is_liked != b.is_liked,
            (None, None) => false,
            _ => true,
        };

        let mut tasks: Vec<Task<Message>> = Vec::new();
        if track_changed {
            self.current_track = new_track;
            if let Some(tr) = self.current_track.clone() {
                self.duration = tr.duration;
                let cover_hash = tr.cover_hash.clone();
                if self.queue_open {
                    self.reload_queue();
                }

                // Trigger dynamic background palette extraction on cover change
                if cover_hash != self.last_fluid_cover_hash {
                    self.last_fluid_cover_hash = cover_hash.clone();
                    if cover_hash.is_empty() {
                        self.fluid.set_target_colors(default_palette());
                    } else {
                        let hash = cover_hash;
                        let thumb_path =
                            self.cache_manager.covers_dir.join(format!("{}_thumb.jpg", hash));
                        tasks.push(spawn_blocking(
                            move || (hash, extract_dominant_colors_from_path(&thumb_path)),
                            |(h, cols)| Message::PaletteExtracted(h, cols),
                        ));
                    }
                }

                // Preload/fetch lyrics when lyrics view is open or track changed
                if tr.path != self.lyrics_track_path {
                    self.lyrics_track_path = tr.path.clone();
                    self.lyrics_lines.clear();
                    self.active_lyric_index = None;
                    self.lyrics_status_text = "Loading lyrics...".to_string();
                    tasks.push(self.fetch_lyrics_task(tr.clone()));
                }
            } else {
                self.last_fluid_cover_hash.clear();
                self.fluid.set_target_colors(default_palette());
                self.lyrics_lines.clear();
                self.active_lyric_index = None;
                self.lyrics_status_text = "Play a song to see lyrics.".to_string();
            }
        }

        Task::batch(tasks)
    }

    fn fetch_lyrics_task(&self, track: TrackItem) -> Task<Message> {
        let lw = self.lyrics_worker.clone();
        let path_key = track.path.clone();
        spawn_blocking(
            move || {
                let res = lw.fetch_lyrics(
                    &track.artist,
                    &track.title,
                    &track.album,
                    track.duration,
                    &track.path,
                );
                (path_key, res)
            },
            |(p, v)| Message::LyricsLoaded(p, v),
        )
    }

    pub fn update(&mut self, message: Message) -> Task<Message> {
        match message {
            Message::NoOp => Task::none(),

            Message::Tick => {
                let now = Instant::now();
                let dt = now.duration_since(self.last_tick_at).as_secs_f32();
                self.last_tick_at = now;

                self.fluid.step(dt, self.is_playing);

                if let Some((_, ts)) = self.toast {
                    if now.duration_since(ts) > Duration::from_secs(3) {
                        self.toast = None;
                    }
                }

                let mut tasks = Vec::new();
                if self.is_playing {
                    self.position = (self.position + dt as f64).min(self.duration.max(0.0));
                }

                // Sync active lyric line and auto-scroll
                if self.lyrics_open && !self.lyrics_lines.is_empty() {
                    let next_idx = find_active_lyric_index(&self.lyrics_lines, self.position);
                    if next_idx != self.active_lyric_index {
                        self.active_lyric_index = next_idx;
                        if let Some(i) = next_idx {
                            tasks.push(scroll_to_lyric_task(i, self.lyrics_lines.len()));
                        }
                    }
                }

                // Periodic backend state sync (~500ms while playing, ~2s idle)
                let sync_interval = if self.is_playing {
                    Duration::from_millis(500)
                } else {
                    Duration::from_millis(1800)
                };
                if now.duration_since(self.last_state_sync_at) >= sync_interval {
                    self.last_state_sync_at = now;
                    let st = self.player_service.get_state();
                    tasks.push(self.apply_player_state(&st));
                }

                if self.is_scanning {
                    let prog = self.library_service.get_scan_progress();
                    tasks.push(self.handle_scan_progress(prog));
                }

                Task::batch(tasks)
            }

            Message::ToggleSidebar => {
                self.sidebar_collapsed = !self.sidebar_collapsed;
                Task::none()
            }

            Message::GoHome => {
                self.active_view = ActiveView::Home;
                self.reload_playlists_and_recent();
                Task::none()
            }

            Message::SelectPlaylist(pid) => {
                self.active_playlist_id = pid.clone();
                self.active_view = ActiveView::Library;
                self.library_offset = 0;
                self.player_service.set_active_playlist(&pid);
                self.reload_library_tracks();
                Task::none()
            }

            Message::SearchChanged(q) => {
                self.search_query = q;
                self.library_offset = 0;
                if !self.search_query.trim().is_empty() && self.active_view != ActiveView::Library {
                    self.active_view = ActiveView::Library;
                }
                self.reload_library_tracks();
                Task::none()
            }

            Message::ClearSearch => {
                self.search_query.clear();
                self.library_offset = 0;
                self.reload_library_tracks();
                Task::none()
            }

            Message::FocusSearch => {
                self.lyrics_open = false;
                self.search_focused = true;
                text_input::focus(search_input_id())
            }

            Message::NextPage => {
                if self.library_offset + PAGE_SIZE < self.library_total {
                    self.library_offset += PAGE_SIZE;
                    self.reload_library_tracks();
                }
                Task::none()
            }

            Message::PrevPage => {
                if self.library_offset >= PAGE_SIZE {
                    self.library_offset -= PAGE_SIZE;
                    self.reload_library_tracks();
                }
                Task::none()
            }

            Message::PlayTrack(path) => {
                let pid = self.active_playlist_id.clone();
                let st = self.player_service.play(&path, Some(&pid));
                self.last_state_sync_at = Instant::now();
                let t = self.apply_player_state(&st);
                self.reload_playlists_and_recent();
                if self.queue_open {
                    self.reload_queue();
                }
                t
            }

            Message::PlayPlaylistFirst => {
                if let Some(first) = self.library_tracks.first() {
                    let path = first.path.clone();
                    return self.update(Message::PlayTrack(path));
                }
                Task::none()
            }

            Message::TogglePlay => {
                if self.current_track.is_none() {
                    if let Some(first) = self
                        .recent_tracks
                        .first()
                        .or_else(|| self.library_tracks.first())
                    {
                        let p = first.path.clone();
                        return self.update(Message::PlayTrack(p));
                    }
                    return Task::none();
                }
                let st = if self.is_playing {
                    self.player_service.pause()
                } else {
                    self.player_service.resume()
                };
                self.apply_player_state(&st)
            }

            Message::NextTrack => {
                let st = self.player_service.next_track(true);
                self.apply_player_state(&st)
            }

            Message::PrevTrack => {
                let st = self.player_service.prev_track();
                self.apply_player_state(&st)
            }

            Message::SeekChanged(sec) => {
                let target = sec as f64;
                self.position = target;
                let st = self.player_service.seek(target);
                self.apply_player_state(&st)
            }

            Message::VolumeChanged(pct) => {
                let lvl = (pct as f64 / 100.0).clamp(0.0, 1.0);
                if lvl > 0.01 {
                    self.prev_nonzero_volume = lvl;
                }
                self.volume = lvl;
                self.player_service.set_volume(lvl);
                Task::none()
            }

            Message::ToggleMute => {
                let target = if self.volume > 0.001 {
                    self.prev_nonzero_volume = self.volume;
                    0.0
                } else {
                    self.prev_nonzero_volume.max(0.2)
                };
                self.volume = target;
                self.player_service.set_volume(target);
                self.show_toast(if target == 0.0 {
                    "Muted"
                } else {
                    "Unmuted"
                });
                Task::none()
            }

            Message::ToggleShuffle => {
                let next = !self.shuffle;
                self.shuffle = next;
                self.player_service.set_shuffle(Some(next));
                if self.queue_open {
                    self.reload_queue();
                }
                self.show_toast(if next { "Shuffle: On" } else { "Shuffle: Off" });
                Task::none()
            }

            Message::ToggleRepeat => {
                let next = match self.repeat.as_str() {
                    "off" => "all",
                    "all" => "one",
                    _ => "off",
                };
                self.repeat = next.to_string();
                self.config.set("repeat", json!(next));
                self.show_toast(format!("Repeat: {}", next));
                Task::none()
            }

            Message::ToggleLike(path) => {
                let res = self.library_service.toggle_like(&path);
                let liked = res.get("is_liked").and_then(|v| v.as_bool()).unwrap_or(false);
                if let Some(ref mut cur) = self.current_track {
                    if cur.path == path {
                        cur.is_liked = liked;
                    }
                }
                self.reload_playlists_and_recent();
                self.reload_library_tracks();
                self.show_toast(if liked {
                    "Added to Favorite Songs"
                } else {
                    "Removed from Favorite Songs"
                });
                Task::none()
            }

            Message::ToggleLikeCurrent => {
                if let Some(ref cur) = self.current_track {
                    let path = cur.path.clone();
                    return self.update(Message::ToggleLike(path));
                }
                Task::none()
            }

            Message::ToggleQueue => {
                self.queue_open = !self.queue_open;
                if self.queue_open {
                    self.reload_queue();
                }
                Task::none()
            }

            Message::PlayNext(path) => {
                self.player_service.insert_play_next(&path);
                if self.queue_open {
                    self.reload_queue();
                }
                self.show_toast("Added to Play Next");
                Task::none()
            }

            Message::RemoveFromQueue(path) => {
                self.player_service.remove_from_queue(&path);
                self.reload_queue();
                Task::none()
            }

            Message::ClearQueue => {
                self.player_service.clear_queue();
                self.reload_queue();
                self.show_toast("Queue cleared");
                Task::none()
            }

            Message::ToggleLyrics => {
                self.lyrics_open = !self.lyrics_open;
                if self.lyrics_open {
                    if let Some(ref tr) = self.current_track {
                        if tr.path != self.lyrics_track_path || self.lyrics_lines.is_empty() {
                            self.lyrics_track_path = tr.path.clone();
                            self.lyrics_status_text = "Loading lyrics...".to_string();
                            return self.fetch_lyrics_task(tr.clone());
                        }
                    }
                }
                Task::none()
            }

            Message::ToggleLyricsCenterMode => {
                self.lyrics_center_mode = !self.lyrics_center_mode;
                Task::none()
            }

            Message::LyricsLoaded(path, val) => {
                if self
                    .current_track
                    .as_ref()
                    .map(|t| t.path == path)
                    .unwrap_or(false)
                {
                    let synced = val
                        .get("synced_lyrics")
                        .and_then(|v| v.as_str())
                        .unwrap_or("");
                    if synced.is_empty() || synced == "[NO_LYRICS]" {
                        let plain = val
                            .get("plain_lyrics")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        if plain.trim().is_empty() {
                            self.lyrics_lines.clear();
                            self.lyrics_status_text = "No synced lyrics available.".to_string();
                        } else {
                            self.lyrics_lines = plain
                                .lines()
                                .filter(|l| !l.trim().is_empty())
                                .map(|l| LyricLine {
                                    time: 0.0,
                                    text: l.trim().to_string(),
                                })
                                .collect();
                        }
                    } else {
                        self.lyrics_lines = parse_lrc(synced);
                        if self.lyrics_lines.is_empty() {
                            self.lyrics_status_text = "No synced lyrics available.".to_string();
                        } else {
                            self.active_lyric_index =
                                find_active_lyric_index(&self.lyrics_lines, self.position);
                        }
                    }
                }
                Task::none()
            }

            Message::OpenSettings => {
                self.settings_open = true;
                Task::none()
            }

            Message::SelectSettingsTab(tab) => {
                self.settings_tab = tab;
                Task::none()
            }

            Message::SetAudioMode(mode) => {
                let applied = self.audio_engine.set_audio_mode(&mode);
                self.audio_mode = applied.clone();
                self.show_toast(if applied == "exclusive" {
                    "WASAPI Exclusive (Bit-Perfect)"
                } else {
                    "WASAPI Shared Mode"
                });
                Task::none()
            }

            Message::PickAndAddMusicDir => spawn_blocking(
                || FileDialog::new().pick_folder(),
                Message::MusicDirPicked,
            ),

            Message::MusicDirPicked(Some(folder)) => {
                let folder_str = folder.to_string_lossy().to_string();
                let mut dirs = self.config.get_string_vec("music_dirs");
                if !dirs.contains(&folder_str) {
                    dirs.push(folder_str);
                    self.config.set("music_dirs", json!(dirs));
                }
                self.library_service.scan_library();
                self.is_scanning = true;
                self.scan_status_text = "Scanning folder...".to_string();
                Task::none()
            }
            Message::MusicDirPicked(None) => Task::none(),

            Message::ScanLibrary => {
                self.library_service.scan_library();
                self.is_scanning = true;
                self.scan_status_text = "Scanning library...".to_string();
                self.show_toast("Library scan started");
                Task::none()
            }

            Message::ClearDatabase => {
                self.player_service.stop();
                self.library_service.clear_database(true);
                self.current_track = None;
                self.is_playing = false;
                self.position = 0.0;
                self.duration = 0.0;
                self.cover_cache.clear();
                self.reload_playlists_and_recent();
                self.reload_library_tracks();
                self.show_toast("Database cleared");
                Task::none()
            }

            Message::OpenCreatePlaylist => {
                self.create_playlist_name.clear();
                self.create_playlist_open = true;
                Task::none()
            }

            Message::CreatePlaylistNameChanged(name) => {
                self.create_playlist_name = name;
                Task::none()
            }

            Message::SubmitCreatePlaylist => {
                let name = self.create_playlist_name.trim().to_string();
                if !name.is_empty() {
                    let id = self.library_service.create_playlist(&name, None);
                    self.create_playlist_open = false;
                    self.create_playlist_name.clear();
                    self.reload_playlists_and_recent();
                    if id > 0 {
                        return self.update(Message::SelectPlaylist(id.to_string()));
                    }
                }
                Task::none()
            }

            Message::ImportFolderToPlaylist => {
                let pid = self.active_playlist_id.clone();
                if pid == "all" || pid == "favorites" {
                    return Task::none();
                }
                spawn_blocking(
                    move || (pid, FileDialog::new().pick_folder()),
                    |(p, f)| Message::PlaylistFolderPicked(p, f),
                )
            }

            Message::PlaylistFolderPicked(pid, Some(folder)) => {
                let lib = self.library_service.clone();
                let pid_num = pid.parse::<i64>().unwrap_or(0);
                let f_str = folder.to_string_lossy().to_string();
                spawn_blocking(
                    move || {
                        let _ = lib.import_folder_to_playlist(pid_num, &f_str);
                    },
                    |_| Message::ImportFinished,
                )
            }
            Message::PlaylistFolderPicked(_, None) => Task::none(),

            Message::ImportFilesToPlaylist => {
                let pid = self.active_playlist_id.clone();
                if pid == "all" || pid == "favorites" {
                    return Task::none();
                }
                spawn_blocking(
                    move || {
                        let files = FileDialog::new()
                            .add_filter(
                                "Audio Files",
                                &["flac", "mp3", "wav", "ogg", "aiff", "m4a", "aac"],
                            )
                            .pick_files();
                        (pid, files)
                    },
                    |(p, f)| Message::PlaylistFilesPicked(p, f),
                )
            }

            Message::PlaylistFilesPicked(pid, Some(files)) => {
                let lib = self.library_service.clone();
                let pid_num = pid.parse::<i64>().unwrap_or(0);
                let paths: Vec<String> = files
                    .into_iter()
                    .map(|p| p.to_string_lossy().to_string())
                    .collect();
                spawn_blocking(
                    move || {
                        let _ = lib.import_files_to_playlist(pid_num, &paths);
                    },
                    |_| Message::ImportFinished,
                )
            }
            Message::PlaylistFilesPicked(_, None) => Task::none(),

            Message::ImportFinished => {
                self.reload_playlists_and_recent();
                self.reload_library_tracks();
                self.show_toast("Imported tracks into playlist");
                Task::none()
            }

            Message::PaletteExtracted(hash, cols) => {
                if hash == self.last_fluid_cover_hash {
                    self.fluid.set_target_colors(cols);
                }
                Task::none()
            }

            Message::CloseModals => {
                self.settings_open = false;
                self.create_playlist_open = false;
                Task::none()
            }

            Message::KeyPressed(key, modifiers) => self.handle_key(key, modifiers),

            Message::CloseRequested => {
                self.library_service.scanner.stop();
                self.audio_engine.shutdown_hardware_stream();
                iced::exit()
            }
        }
    }

    fn handle_scan_progress(&mut self, prog: Value) -> Task<Message> {
        let scanning = prog
            .get("is_scanning")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let scanned = prog.get("scanned").and_then(|v| v.as_u64()).unwrap_or(0);
        let total = prog.get("total").and_then(|v| v.as_u64()).unwrap_or(0);

        if scanning {
            self.scan_status_text = format!("Scanning {}/{} files...", scanned, total);
        } else if self.is_scanning {
            self.is_scanning = false;
            self.scan_status_text.clear();
            self.reload_playlists_and_recent();
            self.reload_library_tracks();
            self.show_toast("Library scan complete");
        }
        Task::none()
    }

    fn handle_key(&mut self, key: Key, modifiers: Modifiers) -> Task<Message> {
        if modifiers.control() && matches!(&key, Key::Character(c) if c.eq_ignore_ascii_case("k")) {
            return self.update(Message::FocusSearch);
        }

        if matches!(key, Key::Named(Named::Escape)) {
            if self.settings_open || self.create_playlist_open {
                return self.update(Message::CloseModals);
            }
            if self.lyrics_open {
                return self.update(Message::ToggleLyrics);
            }
            return Task::none();
        }

        if self.settings_open || self.create_playlist_open {
            return Task::none();
        }

        match key {
            Key::Named(Named::Space) if !self.search_focused => self.update(Message::TogglePlay),
            Key::Named(Named::ArrowRight) if modifiers.control() => {
                self.update(Message::NextTrack)
            }
            Key::Named(Named::ArrowLeft) if modifiers.control() => {
                self.update(Message::PrevTrack)
            }
            Key::Named(Named::ArrowRight) => {
                let target = (self.position + 5.0).min(self.duration.max(0.0)) as f32;
                self.update(Message::SeekChanged(target))
            }
            Key::Named(Named::ArrowLeft) => {
                let target = (self.position - 5.0).max(0.0) as f32;
                self.update(Message::SeekChanged(target))
            }
            Key::Named(Named::ArrowUp) => {
                let pct = ((self.volume * 100.0) + 5.0).min(100.0) as f32;
                self.update(Message::VolumeChanged(pct))
            }
            Key::Named(Named::ArrowDown) => {
                let pct = ((self.volume * 100.0) - 5.0).max(0.0) as f32;
                self.update(Message::VolumeChanged(pct))
            }
            Key::Named(Named::F11) => window::get_latest().and_then(|id| {
                window::change_mode(id, window::Mode::Windowed)
            }),
            Key::Character(ref c) if !self.search_focused => match c.to_ascii_lowercase().as_str()
            {
                "/" => self.update(Message::FocusSearch),
                "l" => self.update(Message::ToggleLyrics),
                "t" if self.lyrics_open => self.update(Message::ToggleLyricsCenterMode),
                "q" => self.update(Message::ToggleQueue),
                "m" => self.update(Message::ToggleMute),
                "s" => self.update(Message::ToggleShuffle),
                "r" => self.update(Message::ToggleRepeat),
                _ => Task::none(),
            },
            _ => Task::none(),
        }
    }

    pub fn view(&self) -> Element<'_, Message> {
        let bg_fluid = image(self.fluid.frame_handle())
            .width(Length::Fill)
            .height(Length::Fill)
            .content_fit(ContentFit::Fill)
            .filter_method(image::FilterMethod::Linear);

        let mut layers: Vec<Element<'_, Message>> = vec![bg_fluid.into()];

        if self.lyrics_open {
            let full_cover = self
                .current_track
                .as_ref()
                .and_then(|t| self.peek_cover_handle(&t.cover_hash, true));
            layers.push(lyrics_view::view(
                self.current_track.as_ref(),
                full_cover,
                self.is_playing,
                self.position,
                self.duration,
                self.volume,
                self.shuffle,
                &self.repeat,
                self.lyrics_center_mode,
                &self.lyrics_lines,
                self.active_lyric_index,
                &self.lyrics_status_text,
            ));
        } else {
            let main_layout = column![
                self.view_top_bar(),
                self.view_workspace(),
                self.view_player_bar(),
            ]
            .spacing(8)
            .padding(8)
            .width(Length::Fill)
            .height(Length::Fill);

            layers.push(main_layout.into());
        }

        if self.settings_open {
            layers.push(modals::settings_modal(
                self.settings_tab,
                &self.audio_mode,
                self.is_scanning,
                &self.scan_status_text,
            ));
        } else if self.create_playlist_open {
            layers.push(modals::create_playlist_modal(&self.create_playlist_name));
        }

        if let Some((ref toast_msg, _)) = self.toast {
            let toast = container(
                container(theme::adv_text(toast_msg).size(13).color(Color::WHITE))
                    .padding([10, 18])
                    .style(theme::toast_pill),
            )
            .width(Length::Fill)
            .height(Length::Fill)
            .padding(iced::Padding {
                top: 0.0,
                right: 0.0,
                bottom: 108.0,
                left: 0.0,
            })
            .align_x(Alignment::Center)
            .align_y(iced::alignment::Vertical::Bottom);
            layers.push(toast.into());
        }

        stack(layers)
            .width(Length::Fill)
            .height(Length::Fill)
            .into()
    }

    fn peek_cover_handle(&self, cover_hash: &str, full: bool) -> Option<image::Handle> {
        if cover_hash.is_empty() {
            return None;
        }
        let key = if full {
            format!("{}_full", cover_hash)
        } else {
            cover_hash.to_string()
        };
        if let Some(h) = self.cover_cache.get(&key) {
            return Some(h.clone());
        }
        let filename = if full {
            format!("{}.jpg", cover_hash)
        } else {
            format!("{}_thumb.jpg", cover_hash)
        };
        let path = self.cache_manager.covers_dir.join(filename);
        if path.is_file() {
            Some(image::Handle::from_path(path))
        } else {
            None
        }
    }

    fn view_top_bar(&self) -> Element<'_, Message> {
        let left = container(
            button(theme::svg_icon(theme::ICON_SIDEBAR, 18.0, theme::TEXT_SECONDARY))
                .width(40)
                .height(40)
                .padding(10)
                .style(theme::top_nav_btn(false))
                .on_press(Message::ToggleSidebar),
        )
        .width(Length::FillPortion(1))
        .align_x(Alignment::Start);

        let mut search_row = row![
            theme::svg_icon(theme::ICON_SEARCH, 16.0, theme::TEXT_SECONDARY),
            text_input("What do you want to play?", &self.search_query)
                .id(search_input_id())
                .on_input(Message::SearchChanged)
                .size(14)
                .padding([6, 8])
                .style(theme::search_input_style)
                .width(Length::Fill),
        ]
        .align_y(Alignment::Center)
        .spacing(6);

        if self.search_query.is_empty() {
            search_row = search_row.push(
                container(text("Ctrl+K").size(11).color(theme::TEXT_SUBDUED))
                    .padding([2, 7])
                    .style(theme::shortcut_pill),
            );
        } else {
            search_row = search_row.push(
                button(theme::svg_icon(theme::ICON_CLOSE, 13.0, theme::TEXT_SECONDARY))
                    .padding(4)
                    .style(theme::ghost_icon_btn)
                    .on_press(Message::ClearSearch),
            );
        }

        let center = row![
            button(theme::svg_icon(theme::ICON_HOME, 18.0, Color::WHITE))
                .width(40)
                .height(40)
                .padding(10)
                .style(theme::top_nav_btn(self.active_view == ActiveView::Home))
                .on_press(Message::GoHome),
            container(search_row)
                .width(420)
                .height(40)
                .padding([0, 12])
                .align_y(Alignment::Center)
                .style(theme::search_pill),
        ]
        .spacing(10)
        .align_y(Alignment::Center);

        let right = container(
            button(theme::svg_icon(theme::ICON_SETTINGS, 18.0, theme::TEXT_SECONDARY))
                .width(40)
                .height(40)
                .padding(10)
                .style(theme::top_nav_btn(self.settings_open))
                .on_press(Message::OpenSettings),
        )
        .width(Length::FillPortion(1))
        .align_x(Alignment::End);

        row![left, center, right]
            .height(52)
            .padding([0, 12])
            .align_y(Alignment::Center)
            .into()
    }

    fn view_workspace(&self) -> Element<'_, Message> {
        let sidebar = self.view_sidebar();
        let main_panel = container(match self.active_view {
            ActiveView::Home => self.view_home(),
            ActiveView::Library => self.view_library(),
        })
        .width(Length::Fill)
        .height(Length::Fill)
        .padding(20)
        .style(theme::glass_panel);

        let mut ws = row![sidebar, main_panel].spacing(8).height(Length::Fill);
        if self.queue_open {
            ws = ws.push(self.view_queue_panel());
        }
        ws.into()
    }

    fn view_sidebar(&self) -> Element<'_, Message> {
        let width = if self.sidebar_collapsed { 72.0 } else { 250.0 };

        let header: Element<'_, Message> = if self.sidebar_collapsed {
            container(theme::svg_icon(theme::ICON_FOLDER, 20.0, theme::TEXT_SECONDARY))
                .width(Length::Fill)
                .padding([12, 0])
                .align_x(Alignment::Center)
                .into()
        } else {
            row![
                theme::svg_icon(theme::ICON_FOLDER, 18.0, theme::TEXT_SECONDARY),
                text("Your Library").size(15).color(Color::WHITE),
                horizontal_space(),
                button(theme::svg_icon(theme::ICON_PLUS, 18.0, theme::TEXT_SECONDARY))
                    .padding(6)
                    .style(theme::ghost_icon_btn)
                    .on_press(Message::OpenCreatePlaylist),
            ]
            .spacing(8)
            .padding([8, 8])
            .align_y(Alignment::Center)
            .into()
        };

        let mut list = Column::new().spacing(6);

        let sys_items = [
            ("all", "All Songs", "All your local tracks", theme::ICON_MUSIC),
            (
                "favorites",
                "Favorite Songs",
                "Your favorite tracks",
                theme::ICON_HEART_FILLED,
            ),
        ];

        for (id, title, sub, icon) in sys_items {
            let active = self.active_view == ActiveView::Library && self.active_playlist_id == id;
            let content: Element<'_, Message> = if self.sidebar_collapsed {
                container(theme::svg_icon(icon, 20.0, Color::WHITE))
                    .width(Length::Fill)
                    .align_x(Alignment::Center)
                    .into()
            } else {
                row![
                    container(theme::svg_icon(icon, 20.0, Color::WHITE))
                        .width(44)
                        .height(44)
                        .align_x(Alignment::Center)
                        .align_y(Alignment::Center)
                        .style(theme::cover_placeholder_card),
                    column![
                        theme::adv_text(title).size(14).color(Color::WHITE),
                        theme::adv_text(sub).size(11).color(theme::TEXT_SUBDUED),
                    ]
                    .spacing(2),
                ]
                .spacing(10)
                .align_y(Alignment::Center)
                .into()
            };

            list = list.push(
                button(content)
                    .width(Length::Fill)
                    .padding(6)
                    .style(theme::track_row_btn(active))
                    .on_press(Message::SelectPlaylist(id.to_string())),
            );
        }

        for pl in &self.playlists {
            let active =
                self.active_view == ActiveView::Library && self.active_playlist_id == pl.id;
            let cover = self.peek_cover_handle(&pl.cover_hash, false);
            let thumb: Element<'_, Message> = if let Some(h) = cover {
                container(
                    image(h)
                        .width(44)
                        .height(44)
                        .content_fit(iced::ContentFit::Cover),
                )
                .clip(true)
                .style(|_| container::Style {
                    border: Border {
                        radius: 6.0.into(),
                        ..Default::default()
                    },
                    ..Default::default()
                })
                .into()
            } else {
                container(theme::svg_icon(theme::ICON_MUSIC, 18.0, theme::TEXT_SUBDUED))
                    .width(44)
                    .height(44)
                    .align_x(Alignment::Center)
                    .align_y(Alignment::Center)
                    .style(theme::cover_placeholder_card)
                    .into()
            };

            let content: Element<'_, Message> = if self.sidebar_collapsed {
                container(thumb).width(Length::Fill).align_x(Alignment::Center).into()
            } else {
                row![
                    thumb,
                    column![
                        theme::adv_text(&pl.name).size(14).color(Color::WHITE),
                        text(format!("{} tracks", pl.track_count))
                            .size(11)
                            .color(theme::TEXT_SUBDUED),
                    ]
                    .spacing(2),
                ]
                .spacing(10)
                .align_y(Alignment::Center)
                .into()
            };

            list = list.push(
                button(content)
                    .width(Length::Fill)
                    .padding(6)
                    .style(theme::track_row_btn(active))
                    .on_press(Message::SelectPlaylist(pl.id.clone())),
            );
        }

        container(column![
            header,
            scrollable(list)
                .height(Length::Fill)
                .style(theme::dark_scrollable_style),
        ])
        .width(width)
        .height(Length::Fill)
        .padding(8)
        .style(theme::glass_panel)
        .into()
    }

    fn view_home(&self) -> Element<'_, Message> {
        let mut cards = Row::new().spacing(16);

        let make_card = |id: String,
                         title: String,
                         sub: String,
                         cover: Option<image::Handle>,
                         icon: &'static [u8]| {
            let art: Element<'_, Message> = if let Some(h) = cover {
                container(
                    image(h)
                        .width(Length::Fill)
                        .height(136)
                        .content_fit(iced::ContentFit::Cover),
                )
                .clip(true)
                .style(|_| container::Style {
                    border: Border {
                        radius: 8.0.into(),
                        ..Default::default()
                    },
                    ..Default::default()
                })
                .into()
            } else {
                container(theme::svg_icon(icon, 42.0, Color::WHITE))
                    .width(Length::Fill)
                    .height(136)
                    .align_x(Alignment::Center)
                    .align_y(Alignment::Center)
                    .style(theme::cover_placeholder_card)
                    .into()
            };

            button(
                column![
                    art,
                    theme::adv_text(title).size(14).color(Color::WHITE),
                    theme::adv_text(sub).size(12).color(theme::TEXT_SUBDUED),
                ]
                .spacing(6),
            )
            .width(168)
            .padding(12)
            .style(theme::glass_card_btn(false))
            .on_press(Message::SelectPlaylist(id))
        };

        cards = cards.push(make_card(
            "all".to_string(),
            "All Songs".to_string(),
            "All your local tracks".to_string(),
            None,
            theme::ICON_MUSIC,
        ));
        cards = cards.push(make_card(
            "favorites".to_string(),
            "Favorite Songs".to_string(),
            "Your favorite tracks".to_string(),
            None,
            theme::ICON_HEART_FILLED,
        ));
        for pl in self.playlists.iter().take(3) {
            let cover = self.peek_cover_handle(&pl.cover_hash, false);
            cards = cards.push(make_card(
                pl.id.clone(),
                pl.name.clone(),
                format!("{} tracks", pl.track_count),
                cover,
                theme::ICON_MUSIC,
            ));
        }

        let create_card = button(
            column![
                container(theme::svg_icon(theme::ICON_PLUS, 36.0, theme::TEXT_SECONDARY))
                    .width(Length::Fill)
                    .height(136)
                    .align_x(Alignment::Center)
                    .align_y(Alignment::Center)
                    .style(theme::cover_placeholder_card),
                text("Create Playlist").size(14).color(Color::WHITE),
                text("Create a new playlist")
                    .size(12)
                    .color(theme::TEXT_SUBDUED),
            ]
            .spacing(6),
        )
        .width(168)
        .padding(12)
        .style(theme::glass_card_btn(false))
        .on_press(Message::OpenCreatePlaylist);

        cards = cards.push(create_card);

        let mut recent_col = Column::new().spacing(4);
        if self.recent_tracks.is_empty() {
            recent_col = recent_col.push(
                text("No recently played tracks yet. Add a music folder in Settings or select All Songs.")
                    .size(13)
                    .color(theme::TEXT_SUBDUED),
            );
        } else {
            for (idx, tr) in self.recent_tracks.iter().enumerate() {
                recent_col = recent_col.push(self.view_track_row(idx + 1, tr));
            }
        }

        scrollable(
            column![
                text("Playlists").size(22).color(Color::WHITE),
                scrollable(cards)
                    .direction(scrollable::Direction::Horizontal(
                        scrollable::Scrollbar::default()
                    ))
                    .style(theme::dark_scrollable_style),
                Space::with_height(8),
                text("Recently Played (Last 20)").size(20).color(Color::WHITE),
                self.view_track_table_header(),
                recent_col,
            ]
            .spacing(12),
        )
        .width(Length::Fill)
        .height(Length::Fill)
        .style(theme::dark_scrollable_style)
        .into()
    }

    fn view_library(&self) -> Element<'_, Message> {
        let mut content = Column::new().spacing(12);

        let is_custom = self.active_playlist_id != "all" && self.active_playlist_id != "favorites";
        let pl_title = if self.active_playlist_id == "all" {
            "All Songs".to_string()
        } else if self.active_playlist_id == "favorites" {
            "Favorite Songs".to_string()
        } else {
            self.playlists
                .iter()
                .find(|p| p.id == self.active_playlist_id)
                .map(|p| p.name.clone())
                .unwrap_or_else(|| "Playlist".to_string())
        };

        let mut actions = row![
            button(
                container(theme::svg_icon(theme::ICON_PLAY, 18.0, Color::BLACK))
                    .center_x(Length::Fill)
                    .center_y(Length::Fill)
            )
            .width(42)
            .height(42)
            .padding(0)
            .style(theme::play_circle_btn)
            .on_press(Message::PlayPlaylistFirst),
        ]
        .spacing(10)
        .align_y(Alignment::Center);

        if is_custom {
            actions = actions
                .push(
                    button(text("Import Folder").size(12))
                        .padding([8, 16])
                        .style(theme::outline_pill_btn)
                        .on_press(Message::ImportFolderToPlaylist),
                )
                .push(
                    button(text("Select Files").size(12))
                        .padding([8, 16])
                        .style(theme::outline_pill_btn)
                        .on_press(Message::ImportFilesToPlaylist),
                );
        }

        content = content.push(
            container(
                row![
                    column![
                        text(if is_custom { "Playlist" } else { "Collection" })
                            .size(11)
                            .color(theme::TEXT_SUBDUED),
                        theme::adv_text(pl_title).size(26).color(Color::WHITE),
                        text(format!("{} tracks", self.library_total))
                            .size(13)
                            .color(theme::TEXT_SECONDARY),
                    ]
                    .spacing(4),
                    horizontal_space(),
                    actions,
                ]
                .align_y(Alignment::Center),
            )
            .padding(16)
            .width(Length::Fill)
            .style(theme::playlist_header_card),
        );

        content = content.push(self.view_track_table_header());

        let mut rows = Column::new().spacing(2);
        if self.library_tracks.is_empty() {
            rows = rows.push(
                container(
                    text("No tracks found.")
                        .size(14)
                        .color(theme::TEXT_SUBDUED),
                )
                .padding(24),
            );
        } else {
            for (i, tr) in self.library_tracks.iter().enumerate() {
                let num = (self.library_offset as usize) + i + 1;
                rows = rows.push(self.view_track_row(num, tr));
            }
        }

        if self.library_total > PAGE_SIZE {
            let page = (self.library_offset / PAGE_SIZE) + 1;
            let total_pages = (self.library_total + PAGE_SIZE - 1) / PAGE_SIZE;
            rows = rows.push(
                row![
                    horizontal_space(),
                    button(text("Previous").size(12))
                        .padding([6, 14])
                        .style(theme::outline_pill_btn)
                        .on_press(Message::PrevPage),
                    text(format!("Page {} / {}", page, total_pages))
                        .size(12)
                        .color(theme::TEXT_SECONDARY),
                    button(text("Next").size(12))
                        .padding([6, 14])
                        .style(theme::outline_pill_btn)
                        .on_press(Message::NextPage),
                ]
                .spacing(10)
                .padding([12, 0])
                .align_y(Alignment::Center),
            );
        }

        content = content.push(
            scrollable(rows)
                .width(Length::Fill)
                .height(Length::Fill)
                .style(theme::dark_scrollable_style),
        );

        content.into()
    }

    fn view_track_table_header(&self) -> Element<'_, Message> {
        container(
            row![
                text("#").size(11).color(theme::TEXT_SUBDUED).width(36),
                text("TITLE")
                    .size(11)
                    .color(theme::TEXT_SUBDUED)
                    .width(Length::FillPortion(5)),
                text("ALBUM")
                    .size(11)
                    .color(theme::TEXT_SUBDUED)
                    .width(Length::FillPortion(3)),
                Space::with_width(68),
                text("TIME").size(11).color(theme::TEXT_SUBDUED).width(52),
            ]
            .spacing(10)
            .padding([6, 10])
            .align_y(Alignment::Center),
        )
        .width(Length::Fill)
        .into()
    }

    fn view_track_row<'a>(&'a self, number: usize, tr: &'a TrackItem) -> Element<'a, Message> {
        let is_active = self
            .current_track
            .as_ref()
            .map(|c| c.path == tr.path)
            .unwrap_or(false);
        let cover = self.peek_cover_handle(&tr.cover_hash, false);
        let thumb: Element<'_, Message> = if let Some(h) = cover {
            container(
                image(h)
                    .width(38)
                    .height(38)
                    .content_fit(iced::ContentFit::Cover),
            )
            .clip(true)
            .style(|_| container::Style {
                border: Border {
                    radius: 4.0.into(),
                    ..Default::default()
                },
                ..Default::default()
            })
            .into()
        } else {
            container(theme::svg_icon(theme::ICON_MUSIC, 16.0, theme::TEXT_SUBDUED))
                .width(38)
                .height(38)
                .align_x(Alignment::Center)
                .align_y(Alignment::Center)
                .style(theme::cover_placeholder_card)
                .into()
        };

        let like_icon = if tr.is_liked {
            theme::svg_icon(theme::ICON_HEART_FILLED, 15.0, Color::WHITE)
        } else {
            theme::svg_icon(theme::ICON_HEART_EMPTY, 15.0, theme::TEXT_SUBDUED)
        };

        let path_play = tr.path.clone();
        let path_like = tr.path.clone();
        let path_next = tr.path.clone();

        let title_color = if is_active {
            theme::ACCENT_GOLD
        } else {
            Color::WHITE
        };

        let row_body = row![
            text(number.to_string())
                .size(13)
                .color(if is_active {
                    theme::ACCENT_GOLD
                } else {
                    theme::TEXT_SUBDUED
                })
                .width(36),
            row![
                thumb,
                column![
                    theme::adv_text(&tr.title).size(14).color(title_color),
                    theme::adv_text(&tr.artist).size(12).color(theme::TEXT_SECONDARY),
                ]
                .spacing(1),
            ]
            .spacing(10)
            .align_y(Alignment::Center)
            .width(Length::FillPortion(5)),
            theme::adv_text(&tr.album)
                .size(13)
                .color(theme::TEXT_SECONDARY)
                .width(Length::FillPortion(3)),
            row![
                button(theme::svg_icon(theme::ICON_PLUS, 14.0, theme::TEXT_SUBDUED))
                    .padding(6)
                    .style(theme::ghost_icon_btn)
                    .on_press(Message::PlayNext(path_next)),
                button(like_icon)
                    .padding(6)
                    .style(theme::ghost_icon_btn)
                    .on_press(Message::ToggleLike(path_like)),
            ]
            .spacing(2)
            .width(68),
            text(format_time(tr.duration))
                .size(13)
                .color(theme::TEXT_SUBDUED)
                .width(52),
        ]
        .spacing(10)
        .align_y(Alignment::Center);

        button(row_body)
            .width(Length::Fill)
            .padding([6, 10])
            .style(theme::track_row_btn(is_active))
            .on_press(Message::PlayTrack(path_play))
            .into()
    }

    fn view_queue_panel(&self) -> Element<'_, Message> {
        let header = row![
            theme::svg_icon(theme::ICON_QUEUE, 16.0, Color::WHITE),
            text("Play Queue").size(15).color(Color::WHITE),
            horizontal_space(),
            button(theme::svg_icon(theme::ICON_TRASH, 15.0, theme::TEXT_SECONDARY))
                .padding(6)
                .style(theme::ghost_icon_btn)
                .on_press(Message::ClearQueue),
            button(theme::svg_icon(theme::ICON_CLOSE, 15.0, theme::TEXT_SECONDARY))
                .padding(6)
                .style(theme::ghost_icon_btn)
                .on_press(Message::ToggleQueue),
        ]
        .spacing(8)
        .align_y(Alignment::Center);

        let mut list = Column::new().spacing(8);

        if let Some(ref cur) = self.queue_current {
            list = list.push(text("Now Playing").size(11).color(theme::TEXT_SUBDUED));
            list = list.push(self.view_queue_row(cur, false));
        }

        if !self.queue_user.is_empty() {
            list = list.push(text("Next in Queue").size(11).color(theme::TEXT_SUBDUED));
            for t in &self.queue_user {
                list = list.push(self.view_queue_row(t, true));
            }
        }

        if !self.queue_upcoming.is_empty() {
            list = list.push(text("Next Up").size(11).color(theme::TEXT_SUBDUED));
            for t in self.queue_upcoming.iter().take(20) {
                list = list.push(self.view_queue_row(t, false));
            }
        }

        container(
            column![
                header,
                scrollable(list)
                    .height(Length::Fill)
                    .style(theme::dark_scrollable_style),
            ]
            .spacing(12),
        )
        .width(290)
        .height(Length::Fill)
        .padding(14)
        .style(theme::glass_panel)
        .into()
    }

    fn view_queue_row<'a>(&'a self, tr: &'a TrackItem, removable: bool) -> Element<'a, Message> {
        let path_play = tr.path.clone();
        let path_rem = tr.path.clone();
        let mut r = row![
            column![
                theme::adv_text(&tr.title).size(13).color(Color::WHITE),
                theme::adv_text(&tr.artist).size(11).color(theme::TEXT_SECONDARY),
            ]
            .spacing(2)
            .width(Length::Fill),
        ]
        .spacing(6)
        .align_y(Alignment::Center);

        if removable {
            r = r.push(
                button(theme::svg_icon(theme::ICON_CLOSE, 13.0, theme::TEXT_SUBDUED))
                    .padding(4)
                    .style(theme::ghost_icon_btn)
                    .on_press(Message::RemoveFromQueue(path_rem)),
            );
        }

        button(r)
            .width(Length::Fill)
            .padding([6, 8])
            .style(theme::track_row_btn(false))
            .on_press(Message::PlayTrack(path_play))
            .into()
    }

    fn view_player_bar(&self) -> Element<'_, Message> {
        let cover_handle = self
            .current_track
            .as_ref()
            .and_then(|t| self.peek_cover_handle(&t.cover_hash, false));

        let cover_elem: Element<'_, Message> = if let Some(h) = cover_handle {
            container(
                image(h)
                    .width(54)
                    .height(54)
                    .content_fit(iced::ContentFit::Cover),
            )
            .clip(true)
            .style(|_| container::Style {
                border: Border {
                    radius: 6.0.into(),
                    ..Default::default()
                },
                ..Default::default()
            })
            .into()
        } else {
            container(theme::svg_icon(theme::ICON_MUSIC, 22.0, theme::TEXT_SUBDUED))
                .width(54)
                .height(54)
                .align_x(Alignment::Center)
                .align_y(Alignment::Center)
                .style(theme::cover_placeholder_card)
                .into()
        };

        let (title_str, artist_str, liked, badge_el) = if let Some(ref tr) = self.current_track {
            let (q_label, hires) = format_audio_quality(tr);
            let badge: Element<'_, Message> = container(text(q_label).size(10))
                .padding([3, 8])
                .style(theme::quality_badge_style(hires))
                .into();
            (tr.title.as_str(), tr.artist.as_str(), tr.is_liked, badge)
        } else {
            ("No Track", "Unknown Artist", false, Space::new(0, 0).into())
        };

        let like_icon = if liked {
            theme::svg_icon(theme::ICON_HEART_FILLED, 16.0, Color::WHITE)
        } else {
            theme::svg_icon(theme::ICON_HEART_EMPTY, 16.0, theme::TEXT_SECONDARY)
        };

        let left = row![
            mouse_area(cover_elem)
                .on_press(Message::ToggleLyrics)
                .interaction(iced::mouse::Interaction::Pointer),
            column![
                theme::adv_text(title_str).size(14).color(Color::WHITE),
                theme::adv_text(artist_str).size(12).color(theme::TEXT_SECONDARY),
            ]
            .spacing(2)
            .width(Length::Fill),
            button(like_icon)
                .padding(6)
                .style(theme::ghost_icon_btn)
                .on_press(Message::ToggleLikeCurrent),
        ]
        .spacing(10)
        .align_y(Alignment::Center)
        .width(Length::FillPortion(3));

        let play_icon = if self.is_playing {
            theme::ICON_PAUSE
        } else {
            theme::ICON_PLAY
        };
        let repeat_icon = if self.repeat == "one" {
            theme::ICON_REPEAT_ONE
        } else {
            theme::ICON_REPEAT
        };

        let max_dur = self.duration.max(1.0) as f32;
        let cur_pos = (self.position.clamp(0.0, max_dur as f64)) as f32;

        let center = column![
            row![
                button(theme::svg_icon(
                    theme::ICON_SHUFFLE,
                    15.0,
                    if self.shuffle {
                        Color::WHITE
                    } else {
                        theme::TEXT_SUBDUED
                    }
                ))
                .padding(6)
                .style(theme::ghost_icon_btn)
                .on_press(Message::ToggleShuffle),
                button(theme::svg_icon(theme::ICON_PREV, 18.0, Color::WHITE))
                    .padding(6)
                    .style(theme::ghost_icon_btn)
                    .on_press(Message::PrevTrack),
                button(
                    container(theme::svg_icon(play_icon, 16.0, Color::BLACK))
                        .center_x(Length::Fill)
                        .center_y(Length::Fill),
                )
                .width(34)
                .height(34)
                .padding(0)
                .style(theme::play_circle_btn)
                .on_press(Message::TogglePlay),
                button(theme::svg_icon(theme::ICON_NEXT, 18.0, Color::WHITE))
                    .padding(6)
                    .style(theme::ghost_icon_btn)
                    .on_press(Message::NextTrack),
                button(theme::svg_icon(
                    repeat_icon,
                    15.0,
                    if self.repeat != "off" {
                        Color::WHITE
                    } else {
                        theme::TEXT_SUBDUED
                    }
                ))
                .padding(6)
                .style(theme::ghost_icon_btn)
                .on_press(Message::ToggleRepeat),
            ]
            .spacing(14)
            .align_y(Alignment::Center),
            row![
                text(format_time(self.position))
                    .size(11)
                    .color(theme::TEXT_SUBDUED)
                    .width(38),
                slider(0.0..=max_dur, cur_pos, Message::SeekChanged)
                    .step(0.25_f32)
                    .width(Length::Fill)
                    .style(theme::clean_slider_style),
                text(format_time(self.duration))
                    .size(11)
                    .color(theme::TEXT_SUBDUED)
                    .width(38),
            ]
            .spacing(8)
            .align_y(Alignment::Center)
            .width(Length::Fill),
        ]
        .spacing(6)
        .align_x(Alignment::Center)
        .width(Length::FillPortion(4));

        let vol_icon = if self.volume <= 0.001 {
            theme::ICON_VOLUME_MUTE
        } else {
            theme::ICON_VOLUME
        };

        let right = row![
            horizontal_space(),
            badge_el,
            button(theme::svg_icon(
                theme::ICON_QUEUE,
                16.0,
                if self.queue_open {
                    Color::WHITE
                } else {
                    theme::TEXT_SECONDARY
                }
            ))
            .padding(6)
            .style(theme::ghost_icon_btn)
            .on_press(Message::ToggleQueue),
            button(theme::svg_icon(
                theme::ICON_LYRICS,
                16.0,
                if self.lyrics_open {
                    Color::WHITE
                } else {
                    theme::TEXT_SECONDARY
                }
            ))
            .padding(6)
            .style(theme::ghost_icon_btn)
            .on_press(Message::ToggleLyrics),
            button(theme::svg_icon(vol_icon, 16.0, theme::TEXT_SECONDARY))
                .padding(6)
                .style(theme::ghost_icon_btn)
                .on_press(Message::ToggleMute),
            slider(0.0..=100.0, (self.volume * 100.0) as f32, Message::VolumeChanged)
                .step(1.0_f32)
                .width(88)
                .style(theme::clean_slider_style),
        ]
        .spacing(6)
        .align_y(Alignment::Center)
        .width(Length::FillPortion(3));

        container(row![left, center, right].spacing(16).align_y(Alignment::Center))
            .height(82)
            .padding([8, 16])
            .width(Length::Fill)
            .style(theme::glass_panel)
            .into()
    }
}
