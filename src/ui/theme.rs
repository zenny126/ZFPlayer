use iced::widget::{button, container, scrollable, slider, svg, text_input};
use iced::{Border, Color, Shadow, Theme, Vector};

// --- Color Tokens (ZFPlayer Dark Glassmorphism) ---
pub const TEXT_PRIMARY: Color = Color::WHITE;
pub const TEXT_SECONDARY: Color = Color::from_rgba(1.0, 1.0, 1.0, 0.72);
pub const TEXT_SUBDUED: Color = Color::from_rgba(1.0, 1.0, 1.0, 0.44);
pub const ACCENT_GOLD: Color = Color::from_rgb(0.98, 0.80, 0.08);
pub const BORDER_SUBTLE: Color = Color::from_rgba(1.0, 1.0, 1.0, 0.10);
pub const BORDER_HOVER: Color = Color::from_rgba(1.0, 1.0, 1.0, 0.24);

// --- Crisp Inline SVG Icons ---
pub const ICON_SIDEBAR: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>"##;
pub const ICON_HOME: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#ffffff"><path d="M12 3l10 9h-3v9H5v-9H2z"/></svg>"##;
pub const ICON_SEARCH: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>"##;
pub const ICON_SETTINGS: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>"##;
pub const ICON_FOLDER: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>"##;
pub const ICON_PLUS: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>"##;
pub const ICON_MUSIC: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>"##;
pub const ICON_HEART_EMPTY: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>"##;
pub const ICON_HEART_FILLED: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#ffffff"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>"##;
pub const ICON_PLAY: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#ffffff"><path d="M8 5v14l11-7z"/></svg>"##;
pub const ICON_PAUSE: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#ffffff"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>"##;
pub const ICON_PREV: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#ffffff"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>"##;
pub const ICON_NEXT: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#ffffff"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>"##;
pub const ICON_SHUFFLE: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>"##;
pub const ICON_REPEAT: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>"##;
pub const ICON_REPEAT_ONE: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/><line x1="12" y1="10" x2="12" y2="14"/></svg>"##;
pub const ICON_QUEUE: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>"##;
pub const ICON_LYRICS: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" x2="12" y1="19" y2="22"/></svg>"##;
pub const ICON_LYRICS_TEXT: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="14" y2="13"/></svg>"##;
pub const ICON_VOLUME: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>"##;
pub const ICON_VOLUME_MUTE: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>"##;
pub const ICON_CLOSE: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>"##;
pub const ICON_TRASH: &[u8] = br##"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>"##;

pub fn svg_icon<'a>(bytes: &'static [u8], size: f32, color: Color) -> svg::Svg<'a> {
    svg(svg::Handle::from_memory(bytes))
        .width(size)
        .height(size)
        .style(move |_theme, _status| svg::Style { color: Some(color) })
}

pub fn adv_text<'a>(content: impl iced::widget::text::IntoFragment<'a>) -> iced::widget::Text<'a> {
    iced::widget::text(content).shaping(iced::widget::text::Shaping::Advanced)
}

// --- Container Styles ---
pub fn glass_panel(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(0.03, 0.04, 0.07, 0.56).into()),
        border: Border {
            color: BORDER_SUBTLE,
            width: 1.0,
            radius: 12.0.into(),
        },
        text_color: Some(TEXT_PRIMARY),
        ..Default::default()
    }
}

pub fn playlist_header_card(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(1.0, 1.0, 1.0, 0.05).into()),
        border: Border {
            color: BORDER_SUBTLE,
            width: 1.0,
            radius: 12.0.into(),
        },
        text_color: Some(TEXT_PRIMARY),
        ..Default::default()
    }
}

pub fn quality_badge_style(hires: bool) -> impl Fn(&Theme) -> container::Style {
    move |_theme| {
        if hires {
            container::Style {
                background: Some(Color::from_rgba(0.98, 0.80, 0.08, 0.14).into()),
                border: Border {
                    color: Color::from_rgba(0.98, 0.80, 0.08, 0.38),
                    width: 1.0,
                    radius: 999.0.into(),
                },
                text_color: Some(ACCENT_GOLD),
                ..Default::default()
            }
        } else {
            container::Style {
                background: Some(Color::from_rgba(1.0, 1.0, 1.0, 0.08).into()),
                border: Border {
                    color: Color::from_rgba(1.0, 1.0, 1.0, 0.16),
                    width: 1.0,
                    radius: 999.0.into(),
                },
                text_color: Some(TEXT_SECONDARY),
                ..Default::default()
            }
        }
    }
}

pub fn search_pill(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(0.0, 0.0, 0.0, 0.34).into()),
        border: Border {
            color: BORDER_SUBTLE,
            width: 1.0,
            radius: 999.0.into(),
        },
        text_color: Some(TEXT_PRIMARY),
        ..Default::default()
    }
}

pub fn modal_backdrop(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(0.0, 0.0, 0.0, 0.72).into()),
        ..Default::default()
    }
}

pub fn modal_card(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(0.09, 0.10, 0.14, 0.96).into()),
        border: Border {
            color: Color::from_rgba(1.0, 1.0, 1.0, 0.16),
            width: 1.0,
            radius: 16.0.into(),
        },
        shadow: Shadow {
            color: Color::from_rgba(0.0, 0.0, 0.0, 0.65),
            offset: Vector::new(0.0, 16.0),
            blur_radius: 40.0,
        },
        text_color: Some(TEXT_PRIMARY),
    }
}

pub fn toast_pill(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(0.09, 0.10, 0.12, 0.94).into()),
        border: Border {
            color: Color::from_rgba(1.0, 1.0, 1.0, 0.16),
            width: 1.0,
            radius: 10.0.into(),
        },
        shadow: Shadow {
            color: Color::from_rgba(0.0, 0.0, 0.0, 0.5),
            offset: Vector::new(0.0, 8.0),
            blur_radius: 24.0,
        },
        text_color: Some(TEXT_PRIMARY),
    }
}

pub fn cover_placeholder_card(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(1.0, 1.0, 1.0, 0.07).into()),
        border: Border {
            color: BORDER_SUBTLE,
            width: 1.0,
            radius: 10.0.into(),
        },
        ..Default::default()
    }
}

pub fn shortcut_pill(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(1.0, 1.0, 1.0, 0.08).into()),
        border: Border {
            color: Color::from_rgba(1.0, 1.0, 1.0, 0.16),
            width: 1.0,
            radius: 6.0.into(),
        },
        text_color: Some(TEXT_PRIMARY),
        ..Default::default()
    }
}

// --- Button Styles ---
pub fn ghost_icon_btn(_theme: &Theme, status: button::Status) -> button::Style {
    let bg = match status {
        button::Status::Hovered => Some(Color::from_rgba(1.0, 1.0, 1.0, 0.10).into()),
        button::Status::Pressed => Some(Color::from_rgba(1.0, 1.0, 1.0, 0.18).into()),
        _ => None,
    };
    button::Style {
        background: bg,
        border: Border {
            radius: 999.0.into(),
            ..Default::default()
        },
        text_color: TEXT_PRIMARY,
        ..Default::default()
    }
}

pub fn top_nav_btn(active: bool) -> impl Fn(&Theme, button::Status) -> button::Style {
    move |_theme, status| {
        let bg = if active {
            Color::from_rgba(1.0, 1.0, 1.0, 0.14)
        } else {
            match status {
                button::Status::Hovered => Color::from_rgba(1.0, 1.0, 1.0, 0.10),
                button::Status::Pressed => Color::from_rgba(1.0, 1.0, 1.0, 0.18),
                _ => Color::from_rgba(0.0, 0.0, 0.0, 0.28),
            }
        };
        button::Style {
            background: Some(bg.into()),
            border: Border {
                color: if active { BORDER_HOVER } else { Color::TRANSPARENT },
                width: 1.0,
                radius: 999.0.into(),
            },
            text_color: TEXT_PRIMARY,
            ..Default::default()
        }
    }
}

pub fn play_circle_btn(_theme: &Theme, status: button::Status) -> button::Style {
    let bg = match status {
        button::Status::Hovered => Color::from_rgb(0.92, 0.92, 0.95),
        button::Status::Pressed => Color::from_rgb(0.80, 0.80, 0.85),
        _ => Color::WHITE,
    };
    button::Style {
        background: Some(bg.into()),
        border: Border {
            radius: 999.0.into(),
            ..Default::default()
        },
        shadow: Shadow {
            color: Color::from_rgba(1.0, 1.0, 1.0, 0.22),
            offset: Vector::ZERO,
            blur_radius: 12.0,
        },
        text_color: Color::BLACK,
    }
}

pub fn glass_card_btn(active: bool) -> impl Fn(&Theme, button::Status) -> button::Style {
    move |_theme, status| {
        let bg = if active {
            Color::from_rgba(1.0, 1.0, 1.0, 0.14)
        } else {
            match status {
                button::Status::Hovered => Color::from_rgba(1.0, 1.0, 1.0, 0.09),
                button::Status::Pressed => Color::from_rgba(1.0, 1.0, 1.0, 0.16),
                _ => Color::from_rgba(1.0, 1.0, 1.0, 0.045),
            }
        };
        button::Style {
            background: Some(bg.into()),
            border: Border {
                color: if active { BORDER_HOVER } else { BORDER_SUBTLE },
                width: 1.0,
                radius: 10.0.into(),
            },
            text_color: TEXT_PRIMARY,
            ..Default::default()
        }
    }
}

pub fn track_row_btn(active: bool) -> impl Fn(&Theme, button::Status) -> button::Style {
    move |_theme, status| {
        let bg = if active {
            Some(Color::from_rgba(1.0, 1.0, 1.0, 0.12).into())
        } else {
            match status {
                button::Status::Hovered => Some(Color::from_rgba(1.0, 1.0, 1.0, 0.07).into()),
                button::Status::Pressed => Some(Color::from_rgba(1.0, 1.0, 1.0, 0.14).into()),
                _ => None,
            }
        };
        button::Style {
            background: bg,
            border: Border {
                radius: 6.0.into(),
                ..Default::default()
            },
            text_color: TEXT_PRIMARY,
            ..Default::default()
        }
    }
}

pub fn outline_pill_btn(_theme: &Theme, status: button::Status) -> button::Style {
    let bg = match status {
        button::Status::Hovered => Some(Color::from_rgba(1.0, 1.0, 1.0, 0.12).into()),
        button::Status::Pressed => Some(Color::from_rgba(1.0, 1.0, 1.0, 0.20).into()),
        _ => None,
    };
    button::Style {
        background: bg,
        border: Border {
            color: Color::from_rgba(1.0, 1.0, 1.0, 0.35),
            width: 1.0,
            radius: 999.0.into(),
        },
        text_color: TEXT_PRIMARY,
        ..Default::default()
    }
}

pub fn primary_pill_btn(_theme: &Theme, status: button::Status) -> button::Style {
    let bg = match status {
        button::Status::Hovered => Color::from_rgb(0.92, 0.92, 0.95),
        button::Status::Pressed => Color::from_rgb(0.80, 0.80, 0.85),
        _ => Color::WHITE,
    };
    button::Style {
        background: Some(bg.into()),
        border: Border {
            radius: 999.0.into(),
            ..Default::default()
        },
        text_color: Color::BLACK,
        ..Default::default()
    }
}

pub fn search_input_style(_theme: &Theme, _status: text_input::Status) -> text_input::Style {
    text_input::Style {
        background: Color::TRANSPARENT.into(),
        border: Border::default(),
        icon: TEXT_SECONDARY,
        placeholder: TEXT_SUBDUED,
        value: TEXT_PRIMARY,
        selection: Color::from_rgba(1.0, 1.0, 1.0, 0.28),
    }
}

pub fn modal_input_style(_theme: &Theme, status: text_input::Status) -> text_input::Style {
    let border_color = match status {
        text_input::Status::Focused => Color::from_rgba(1.0, 1.0, 1.0, 0.55),
        text_input::Status::Hovered => Color::from_rgba(1.0, 1.0, 1.0, 0.28),
        _ => BORDER_SUBTLE,
    };
    text_input::Style {
        background: Color::from_rgba(1.0, 1.0, 1.0, 0.08).into(),
        border: Border {
            color: border_color,
            width: 1.0,
            radius: 8.0.into(),
        },
        icon: TEXT_SECONDARY,
        placeholder: TEXT_SUBDUED,
        value: TEXT_PRIMARY,
        selection: Color::from_rgba(1.0, 1.0, 1.0, 0.28),
    }
}

pub fn clean_slider_style(_theme: &Theme, status: slider::Status) -> slider::Style {
    let handle_radius = match status {
        slider::Status::Hovered | slider::Status::Dragged => 6.0,
        _ => 4.5,
    };
    slider::Style {
        rail: slider::Rail {
            backgrounds: (
                Color::WHITE.into(),
                Color::from_rgba(1.0, 1.0, 1.0, 0.22).into(),
            ),
            width: 4.0,
            border: Border {
                radius: 2.0.into(),
                ..Default::default()
            },
        },
        handle: slider::Handle {
            shape: slider::HandleShape::Circle {
                radius: handle_radius,
            },
            background: Color::WHITE.into(),
            border_width: 0.0,
            border_color: Color::TRANSPARENT,
        },
    }
}

pub fn dark_scrollable_style(theme: &Theme, status: scrollable::Status) -> scrollable::Style {
    let mut base = scrollable::default(theme, status);
    let scroller_color = match status {
        scrollable::Status::Hovered { .. } | scrollable::Status::Dragged { .. } => {
            Color::from_rgba(1.0, 1.0, 1.0, 0.34)
        }
        _ => Color::from_rgba(1.0, 1.0, 1.0, 0.14),
    };
    base.vertical_rail.background = Some(Color::TRANSPARENT.into());
    base.vertical_rail.border = Border::default();
    base.vertical_rail.scroller.color = scroller_color;
    base.vertical_rail.scroller.border = Border {
        radius: 4.0.into(),
        ..Default::default()
    };
    base
}
