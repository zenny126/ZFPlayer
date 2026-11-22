use iced::widget::scrollable::{self, RelativeOffset};
use iced::widget::{
    button, column, container, horizontal_space, image, mouse_area, row,
    scrollable as iced_scrollable, slider, text, Column, Space,
};
use iced::{Alignment, Border, Color, Element, Length, Shadow, Vector};

use crate::ui::app::Message;
use crate::ui::theme;
use crate::ui::{format_audio_quality, format_time, LyricLine, TrackItem};

pub fn lyrics_scroll_id() -> scrollable::Id {
    scrollable::Id::new("lyrics_scroll")
}

/// Parse LRC synced lyrics supporting `[mm:ss.xx]`, `[mm:ss.xxx]`, multi-timestamps per line,
/// `[offset: +/-ms]` tags, and stripping inline `<mm:ss.xx>` karaoke tags.
pub fn parse_lrc(lrc_text: &str) -> Vec<LyricLine> {
    if lrc_text.trim().is_empty() {
        return Vec::new();
    }

    let mut offset_sec = 0.0_f64;
    let mut lines_out = Vec::new();

    for raw_line in lrc_text.lines() {
        let trimmed = raw_line.trim();
        if trimmed.is_empty() {
            continue;
        }

        // Check [offset: +/-ms]
        if let Some(rest) = trimmed
            .strip_prefix("[offset:")
            .or_else(|| trimmed.strip_prefix("[OFFSET:"))
        {
            if let Some(end_idx) = rest.find(']') {
                if let Ok(ms) = rest[..end_idx].trim().parse::<f64>() {
                    offset_sec = ms / 1000.0;
                    continue;
                }
            }
        }

        // Parse leading timestamp tags: [mm:ss.xx]
        let mut cursor = trimmed;
        let mut timestamps: Vec<f64> = Vec::new();
        while cursor.starts_with('[') {
            let Some(close_idx) = cursor.find(']') else {
                break;
            };
            let tag = &cursor[1..close_idx];
            if let Some(t) = parse_timestamp_tag(tag) {
                timestamps.push(t);
                cursor = &cursor[close_idx + 1..];
            } else {
                // Non-timestamp metadata tag like [ar:...], [ti:...]
                timestamps.clear();
                cursor = "";
                break;
            }
        }

        if timestamps.is_empty() {
            continue;
        }

        let clean_text = strip_karaoke_tags(cursor).trim().to_string();
        if clean_text.is_empty() {
            continue;
        }

        for t in timestamps {
            lines_out.push(LyricLine {
                time: (t - offset_sec).max(0.0),
                text: clean_text.clone(),
            });
        }
    }

    lines_out.sort_by(|a, b| a.time.partial_cmp(&b.time).unwrap_or(std::cmp::Ordering::Equal));
    lines_out
}

fn parse_timestamp_tag(tag: &str) -> Option<f64> {
    let (min_str, sec_part) = tag.split_once(':')?;
    let mins: f64 = min_str.trim().parse().ok()?;
    let secs: f64 = sec_part.trim().replace(':', ".").parse().ok()?;
    Some(mins * 60.0 + secs)
}

fn strip_karaoke_tags(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut in_tag = false;
    for ch in s.chars() {
        match ch {
            '<' => in_tag = true,
            '>' if in_tag => in_tag = false,
            _ if !in_tag => out.push(ch),
            _ => {}
        }
    }
    out
}

pub fn find_active_lyric_index(lines: &[LyricLine], current_time: f64) -> Option<usize> {
    if lines.is_empty() {
        return None;
    }
    let idx = lines.partition_point(|l| l.time <= current_time + 0.08);
    if idx == 0 {
        None
    } else {
        Some(idx - 1)
    }
}

pub fn scroll_to_lyric_task(index: usize, total: usize) -> iced::Task<Message> {
    if total <= 1 {
        return iced::Task::none();
    }
    let y = (index as f32 / (total - 1) as f32).clamp(0.0, 1.0);
    scrollable::snap_to(lyrics_scroll_id(), RelativeOffset { x: 0.0, y })
}

#[allow(clippy::too_many_arguments)]
pub fn view<'a>(
    track: Option<&'a TrackItem>,
    cover_handle: Option<image::Handle>,
    is_playing: bool,
    position: f64,
    duration: f64,
    volume: f64,
    shuffle: bool,
    repeat: &'a str,
    center_mode: bool,
    lyrics: &'a [LyricLine],
    active_index: Option<usize>,
    lyrics_status_text: &'a str,
) -> Element<'a, Message> {
    // Top action buttons (Close + Toggle Lyrics Text)
    let top_controls = row![
        button(theme::svg_icon(theme::ICON_CLOSE, 20.0, theme::TEXT_SECONDARY))
            .padding(10)
            .style(theme::ghost_icon_btn)
            .on_press(Message::ToggleLyrics),
        horizontal_space(),
        button(theme::svg_icon(
            theme::ICON_LYRICS_TEXT,
            20.0,
            if center_mode {
                theme::TEXT_SUBDUED
            } else {
                Color::WHITE
            }
        ))
        .padding(10)
        .style(theme::top_nav_btn(!center_mode))
        .on_press(Message::ToggleLyricsCenterMode),
    ]
    .width(Length::Fill)
    .align_y(Alignment::Center);

    // Left column: Album Art + Track Metadata + Quality Badge + Controls
    let cover_widget: Element<'a, Message> = if let Some(h) = cover_handle {
        container(
            image(h)
                .width(300)
                .height(300)
                .content_fit(iced::ContentFit::Cover),
        )
        .style(|_| container::Style {
            border: Border {
                radius: 14.0.into(),
                ..Default::default()
            },
            shadow: Shadow {
                color: Color::from_rgba(0.0, 0.0, 0.0, 0.72),
                offset: Vector::new(0.0, 20.0),
                blur_radius: 44.0,
            },
            ..Default::default()
        })
        .into()
    } else {
        container(theme::svg_icon(theme::ICON_MUSIC, 88.0, theme::TEXT_SUBDUED))
            .width(300)
            .height(300)
            .align_x(Alignment::Center)
            .align_y(Alignment::Center)
            .style(theme::cover_placeholder_card)
            .into()
    };

    let (title_str, artist_str, liked, quality_badge) = if let Some(t) = track {
        let (q_label, hires) = format_audio_quality(t);
        let badge: Element<'a, Message> = container(text(q_label).size(11))
            .padding([3, 10])
            .style(theme::quality_badge_style(hires))
            .into();
        (t.title.as_str(), t.artist.as_str(), t.is_liked, badge)
    } else {
        ("No Track Playing", "Select a song to start", false, Space::new(0, 0).into())
    };

    let like_icon = if liked {
        theme::svg_icon(theme::ICON_HEART_FILLED, 20.0, Color::WHITE)
    } else {
        theme::svg_icon(theme::ICON_HEART_EMPTY, 20.0, theme::TEXT_SECONDARY)
    };

    let meta_row = row![
        column![
            theme::adv_text(title_str).size(22).color(Color::WHITE),
            theme::adv_text(artist_str).size(14).color(theme::TEXT_SECONDARY),
            quality_badge,
        ]
        .spacing(4)
        .width(Length::Fill),
        button(like_icon)
            .padding(8)
            .style(theme::ghost_icon_btn)
            .on_press(Message::ToggleLikeCurrent),
    ]
    .width(300)
    .align_y(Alignment::Center);

    let max_dur = duration.max(1.0) as f32;
    let cur_pos = (position.clamp(0.0, max_dur as f64)) as f32;

    let seek_section = column![
        slider(0.0..=max_dur, cur_pos, Message::SeekChanged)
            .step(0.25_f32)
            .width(300)
            .style(theme::clean_slider_style),
        row![
            text(format_time(position)).size(11).color(theme::TEXT_SUBDUED),
            horizontal_space(),
            text(format_time(duration)).size(11).color(theme::TEXT_SUBDUED),
        ]
        .width(300),
    ]
    .spacing(6);

    let repeat_icon = if repeat == "one" {
        theme::ICON_REPEAT_ONE
    } else {
        theme::ICON_REPEAT
    };
    let play_icon = if is_playing {
        theme::ICON_PAUSE
    } else {
        theme::ICON_PLAY
    };

    let controls_row = row![
        button(theme::svg_icon(
            theme::ICON_SHUFFLE,
            18.0,
            if shuffle { Color::WHITE } else { theme::TEXT_SUBDUED }
        ))
        .padding(8)
        .style(theme::ghost_icon_btn)
        .on_press(Message::ToggleShuffle),
        button(theme::svg_icon(theme::ICON_PREV, 22.0, Color::WHITE))
            .padding(8)
            .style(theme::ghost_icon_btn)
            .on_press(Message::PrevTrack),
        button(
            container(theme::svg_icon(play_icon, 22.0, Color::BLACK))
                .center_x(Length::Fill)
                .center_y(Length::Fill),
        )
        .width(50)
        .height(50)
        .padding(0)
        .style(theme::play_circle_btn)
        .on_press(Message::TogglePlay),
        button(theme::svg_icon(theme::ICON_NEXT, 22.0, Color::WHITE))
            .padding(8)
            .style(theme::ghost_icon_btn)
            .on_press(Message::NextTrack),
        button(theme::svg_icon(
            repeat_icon,
            18.0,
            if repeat != "off" {
                Color::WHITE
            } else {
                theme::TEXT_SUBDUED
            }
        ))
        .padding(8)
        .style(theme::ghost_icon_btn)
        .on_press(Message::ToggleRepeat),
    ]
    .width(300)
    .align_y(Alignment::Center)
    .spacing(12);

    let vol_icon = if volume <= 0.001 {
        theme::ICON_VOLUME_MUTE
    } else {
        theme::ICON_VOLUME
    };
    let volume_row = row![
        button(theme::svg_icon(vol_icon, 16.0, theme::TEXT_SECONDARY))
            .padding(6)
            .style(theme::ghost_icon_btn)
            .on_press(Message::ToggleMute),
        slider(0.0..=100.0, (volume * 100.0) as f32, Message::VolumeChanged)
            .step(1.0_f32)
            .width(Length::Fill)
            .style(theme::clean_slider_style),
    ]
    .width(300)
    .spacing(8)
    .align_y(Alignment::Center);

    let left_col = column![cover_widget, meta_row, seek_section, controls_row, volume_row]
        .spacing(16)
        .align_x(Alignment::Center);

    let body: Element<'a, Message> = if center_mode {
        container(left_col)
            .width(Length::Fill)
            .height(Length::Fill)
            .align_x(Alignment::Center)
            .align_y(Alignment::Center)
            .into()
    } else {
        let lyrics_list: Element<'a, Message> = if lyrics.is_empty() {
            container(
                theme::adv_text(lyrics_status_text)
                    .size(26)
                    .color(theme::TEXT_SECONDARY),
            )
            .width(Length::Fill)
            .height(Length::Fill)
            .align_x(Alignment::Start)
            .align_y(Alignment::Center)
            .into()
        } else {
            let mut col = Column::new().spacing(18).padding([120, 24]);
            for (idx, line) in lyrics.iter().enumerate() {
                let is_active = active_index == Some(idx);
                let is_passed = active_index.map(|a| idx < a).unwrap_or(false);
                let (color, size) = if is_active {
                    (Color::WHITE, 28)
                } else if is_passed {
                    (Color::from_rgba(1.0, 1.0, 1.0, 0.28), 23)
                } else {
                    (Color::from_rgba(1.0, 1.0, 1.0, 0.56), 23)
                };

                let t = line.time;
                let line_btn = mouse_area(
                    container(theme::adv_text(&line.text).size(size).color(color))
                        .padding([4, 8])
                        .width(Length::Fill),
                )
                .on_press(Message::SeekChanged(t as f32))
                .interaction(iced::mouse::Interaction::Pointer);

                col = col.push(line_btn);
            }

            iced_scrollable(col)
                .id(lyrics_scroll_id())
                .width(Length::Fill)
                .height(Length::Fill)
                .style(theme::dark_scrollable_style)
                .into()
        };

        row![
            container(left_col)
                .width(Length::FillPortion(4))
                .height(Length::Fill)
                .align_x(Alignment::Center)
                .align_y(Alignment::Center),
            container(lyrics_list)
                .width(Length::FillPortion(6))
                .height(Length::Fill)
                .padding([12, 24]),
        ]
        .spacing(24)
        .width(Length::Fill)
        .height(Length::Fill)
        .into()
    };

    container(column![top_controls, body].spacing(8))
        .padding([20, 32])
        .width(Length::Fill)
        .height(Length::Fill)
        .into()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_lrc_handles_timestamps_offsets_and_karaoke() {
        let sample = r#"
[ar:Test Artist]
[offset:500]
[00:05.50]Hello <00:05.75>world
[00:10.00][00:20.00]Chorus line
"#;
        let parsed = parse_lrc(sample);
        assert_eq!(parsed.len(), 3);
        assert!((parsed[0].time - 5.0).abs() < 0.01);
        assert_eq!(parsed[0].text, "Hello world");
        assert!((parsed[1].time - 9.5).abs() < 0.01);
        assert_eq!(parsed[1].text, "Chorus line");
        assert!((parsed[2].time - 19.5).abs() < 0.01);
        assert_eq!(find_active_lyric_index(&parsed, 10.0), Some(1));
        assert_eq!(find_active_lyric_index(&parsed, 1.0), None);
    }
}
