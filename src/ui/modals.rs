use iced::widget::{
    button, column, container, horizontal_space, mouse_area, row, scrollable, text, text_input,
    Space,
};
use iced::{Alignment, Color, Element, Length};

use crate::ui::app::{Message, SettingsTab};
use crate::ui::theme;

#[allow(clippy::too_many_arguments)]
pub fn settings_modal<'a>(
    tab: SettingsTab,
    audio_mode: &'a str,
    is_scanning: bool,
    scan_status: &'a str,
) -> Element<'a, Message> {
    let header = row![
        text("Settings").size(22).color(Color::WHITE),
        horizontal_space(),
        button(theme::svg_icon(theme::ICON_CLOSE, 18.0, theme::TEXT_SECONDARY))
            .padding(8)
            .style(theme::ghost_icon_btn)
            .on_press(Message::CloseModals),
    ]
    .align_y(Alignment::Center);

    let tabs = row![
        button(text("Audio Engine").size(13))
            .padding([8, 16])
            .style(theme::top_nav_btn(tab == SettingsTab::Audio))
            .on_press(Message::SelectSettingsTab(SettingsTab::Audio)),
        button(text("Shortcuts").size(13))
            .padding([8, 16])
            .style(theme::top_nav_btn(tab == SettingsTab::Shortcuts))
            .on_press(Message::SelectSettingsTab(SettingsTab::Shortcuts)),
    ]
    .spacing(8);

    let body: Element<'a, Message> = match tab {
        SettingsTab::Audio => {
            let is_exclusive = audio_mode == "exclusive";
            let mode_desc = if is_exclusive {
                "Bit-Perfect 100%: Bypasses Windows Mixer directly to DAC hardware. Other apps will be muted while playing."
            } else {
                "Shared Mode: Plays smoothly alongside browsers, games, and system notifications via WASAPI Event-Driven AutoConvert."
            };

            let scan_line = if is_scanning {
                theme::adv_text(scan_status).size(12).color(theme::ACCENT_GOLD)
            } else {
                theme::adv_text("Library ready — add folders or rescan anytime.")
                    .size(12)
                    .color(theme::TEXT_SUBDUED)
            };

            column![
                text("WASAPI Output Mode").size(14).color(Color::WHITE),
                row![
                    button(text("WASAPI Shared").size(13))
                        .padding([10, 16])
                        .style(theme::glass_card_btn(!is_exclusive))
                        .on_press(Message::SetAudioMode("shared".to_string())),
                    button(text("WASAPI Exclusive (Bit-Perfect)").size(13))
                        .padding([10, 16])
                        .style(theme::glass_card_btn(is_exclusive))
                        .on_press(Message::SetAudioMode("exclusive".to_string())),
                ]
                .spacing(10),
                container(text(mode_desc).size(12).color(theme::TEXT_SECONDARY))
                    .padding(12)
                    .width(Length::Fill)
                    .style(theme::playlist_header_card),
                Space::with_height(4),
                text("Music Library").size(14).color(Color::WHITE),
                row![
                    button(text("Add Music Folder").size(13))
                        .padding([9, 16])
                        .style(theme::outline_pill_btn)
                        .on_press(Message::PickAndAddMusicDir),
                    button(text("Rescan Library").size(13))
                        .padding([9, 16])
                        .style(theme::outline_pill_btn)
                        .on_press(Message::ScanLibrary),
                    button(text("Clear DB").size(13))
                        .padding([9, 16])
                        .style(theme::outline_pill_btn)
                        .on_press(Message::ClearDatabase),
                ]
                .spacing(10),
                scan_line,
            ]
            .spacing(12)
            .into()
        }
        SettingsTab::Shortcuts => {
            let items = [
                ("Space", "Play / Pause"),
                ("Ctrl + Right / Left", "Next / Previous Track"),
                ("Right / Left", "Seek +5s / -5s"),
                ("Up / Down", "Volume +5% / -5%"),
                ("M", "Mute / Unmute"),
                ("L", "Toggle Lyrics View"),
                ("T", "Toggle Lyrics Text"),
                ("Q", "Toggle Play Queue"),
                ("S / R", "Toggle Shuffle / Repeat"),
                ("Ctrl + K  or  /", "Focus Search"),
                ("Esc", "Close Modal / Lyrics"),
            ];
            let mut list = column![].spacing(8);
            for (keys, desc) in items {
                list = list.push(
                    row![
                        text(desc).size(13).color(theme::TEXT_SECONDARY).width(Length::Fill),
                        container(text(keys).size(12))
                            .padding([4, 10])
                            .style(theme::shortcut_pill),
                    ]
                    .align_y(Alignment::Center),
                );
            }
            scrollable(list)
                .height(270)
                .style(theme::dark_scrollable_style)
                .into()
        }
    };

    let card = container(column![header, tabs, body].spacing(16))
        .width(520)
        .padding(24)
        .style(theme::modal_card);

    mouse_area(
        container(mouse_area(card).on_press(Message::NoOp))
            .width(Length::Fill)
            .height(Length::Fill)
            .align_x(Alignment::Center)
            .align_y(Alignment::Center)
            .style(theme::modal_backdrop),
    )
    .on_press(Message::CloseModals)
    .into()
}

pub fn create_playlist_modal<'a>(name_value: &'a str) -> Element<'a, Message> {
    let card = container(
        column![
            row![
                text("Create Playlist").size(20).color(Color::WHITE),
                horizontal_space(),
                button(theme::svg_icon(theme::ICON_CLOSE, 18.0, theme::TEXT_SECONDARY))
                    .padding(6)
                    .style(theme::ghost_icon_btn)
                    .on_press(Message::CloseModals),
            ]
            .align_y(Alignment::Center),
            text_input("Playlist name...", name_value)
                .on_input(Message::CreatePlaylistNameChanged)
                .on_submit(Message::SubmitCreatePlaylist)
                .padding(12)
                .size(14)
                .style(theme::modal_input_style),
            row![
                horizontal_space(),
                button(text("Cancel").size(13))
                    .padding([9, 18])
                    .style(theme::outline_pill_btn)
                    .on_press(Message::CloseModals),
                button(text("Create").size(13))
                    .padding([9, 20])
                    .style(theme::primary_pill_btn)
                    .on_press(Message::SubmitCreatePlaylist),
            ]
            .spacing(10),
        ]
        .spacing(16),
    )
    .width(400)
    .padding(24)
    .style(theme::modal_card);

    mouse_area(
        container(mouse_area(card).on_press(Message::NoOp))
            .width(Length::Fill)
            .height(Length::Fill)
            .align_x(Alignment::Center)
            .align_y(Alignment::Center)
            .style(theme::modal_backdrop),
    )
    .on_press(Message::CloseModals)
    .into()
}
