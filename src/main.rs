#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod audio;
mod cache;
mod config;
mod database;
mod paths;
mod services;
mod ui;
mod workers;

use iced::{window, Size};

fn load_window_icon() -> Option<window::Icon> {
    let img = image::load_from_memory(include_bytes!("../app_icon.png")).ok()?;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    window::icon::from_rgba(rgba.into_raw(), w, h).ok()
}

fn main() -> iced::Result {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    log::info!("Starting ZFPlayer (Pure Native Rust + iced Edition)...");

    iced::application(
        ui::app::ZFPlayerApp::title,
        ui::app::ZFPlayerApp::update,
        ui::app::ZFPlayerApp::view,
    )
    .subscription(ui::app::ZFPlayerApp::subscription)
    .theme(ui::app::ZFPlayerApp::theme)
    .window(window::Settings {
        size: Size::new(1280.0, 800.0),
        min_size: Some(Size::new(900.0, 600.0)),
        icon: load_window_icon(),
        exit_on_close_request: false,
        ..Default::default()
    })
    .run_with(ui::app::ZFPlayerApp::new)
}
