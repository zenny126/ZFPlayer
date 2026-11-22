use std::path::Path;

use iced::widget::image;

pub const FLUID_W: u32 = 96;
pub const FLUID_H: u32 = 60;

#[inline]
fn fract(x: f32) -> f32 {
    x - x.floor()
}

#[inline]
fn ign(px: f32, py: f32) -> f32 {
    fract(52.9829189 * fract(px * 0.06711056 + py * 0.00583715))
}

#[inline]
fn mod289(x: f32) -> f32 {
    x - (x * (1.0 / 289.0)).floor() * 289.0
}

#[inline]
fn permute(x: f32) -> f32 {
    mod289(((x * 34.0) + 1.0) * x)
}

#[inline]
fn snoise(vx: f32, vy: f32) -> f32 {
    const C0: f32 = 0.211324865405187;
    const C1: f32 = 0.366025403784439;
    const C2: f32 = -0.577350269189626;
    const C3: f32 = 0.024390243902439;

    let s = (vx + vy) * C1;
    let ix = (vx + s).floor();
    let iy = (vy + s).floor();

    let t = (ix + iy) * C0;
    let x0x = vx - ix + t;
    let x0y = vy - iy + t;

    let (i1x, i1y) = if x0x > x0y { (1.0, 0.0) } else { (0.0, 1.0) };

    let x1x = x0x + C0 - i1x;
    let x1y = x0y + C0 - i1y;
    let x2x = x0x + C2;
    let x2y = x0y + C2;

    let imx = mod289(ix);
    let imy = mod289(iy);

    let p0 = permute(permute(imy) + imx);
    let p1 = permute(permute(imy + i1y) + imx + i1x);
    let p2 = permute(permute(imy + 1.0) + imx + 1.0);

    let mut m0 = (0.5 - (x0x * x0x + x0y * x0y)).max(0.0);
    let mut m1 = (0.5 - (x1x * x1x + x1y * x1y)).max(0.0);
    let mut m2 = (0.5 - (x2x * x2x + x2y * x2y)).max(0.0);
    m0 = m0 * m0 * m0 * m0;
    m1 = m1 * m1 * m1 * m1;
    m2 = m2 * m2 * m2 * m2;

    let xf0 = 2.0 * fract(p0 * C3) - 1.0;
    let xf1 = 2.0 * fract(p1 * C3) - 1.0;
    let xf2 = 2.0 * fract(p2 * C3) - 1.0;

    let h0 = xf0.abs() - 0.5;
    let h1 = xf1.abs() - 0.5;
    let h2 = xf2.abs() - 0.5;

    let a0 = xf0 - (xf0 + 0.5).floor();
    let a1 = xf1 - (xf1 + 0.5).floor();
    let a2 = xf2 - (xf2 + 0.5).floor();

    m0 *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h0 * h0);
    m1 *= 1.79284291400159 - 0.85373472095314 * (a1 * a1 + h1 * h1);
    m2 *= 1.79284291400159 - 0.85373472095314 * (a2 * a2 + h2 * h2);

    let g0 = a0 * x0x + h0 * x0y;
    let g1 = a1 * x1x + h1 * x1y;
    let g2 = a2 * x2x + h2 * x2y;

    130.0 * (m0 * g0 + m1 * g1 + m2 * g2)
}

#[inline]
fn rot_mul(sin_a: f32, cos_a: f32, vx: f32, vy: f32) -> (f32, f32) {
    (cos_a * vx - sin_a * vy, sin_a * vx + cos_a * vy)
}

/// Renders the 4-color Simplex-Noise domain-warped fluid backdrop into an RGBA8 buffer (`FLUID_W x FLUID_H`).
pub fn render_fluid_rgba(displayed: &[[f32; 3]; 4], t: f32) -> Vec<u8> {
    let mut out = vec![0u8; (FLUID_W * FLUID_H * 4) as usize];

    let p2x = 0.5 + 0.4 * (t * 0.3).cos();
    let p2y = 0.5 + 0.4 * (t * 0.4).sin();
    let p3x = 0.5 + 0.4 * (t * 0.5).sin();
    let p3y = 0.5 + 0.4 * (t * 0.2).cos();
    let p4x = 0.5 + 0.4 * (t * 0.4).cos();
    let p4y = 0.5 + 0.4 * (t * 0.6).sin();

    let (s2, c2) = (t * 0.5).sin_cos();
    let (s3, c3) = (-t * 0.3).sin_cos();
    let (s4, c4) = (t * 0.7).sin_cos();

    let bg_weight = 7.0_f32;
    let c_bg = displayed[0];
    let c_2 = displayed[1];
    let c_3 = displayed[2];
    let c_4 = displayed[3];

    let inv_w = 1.0 / (FLUID_W as f32);
    let inv_h = 1.0 / (FLUID_H as f32);

    for py in 0..FLUID_H {
        let v = (py as f32 + 0.5) * inv_h;
        for px in 0..FLUID_W {
            let u = (px as f32 + 0.5) * inv_w;

            let n1 = snoise(u * 1.5 + t * 0.15, v * 1.5 + t * 0.15);
            let n2 = snoise(u * 1.5 - t * 0.12, v * 1.5 - t * 0.12);

            let wp2x = p2x + n1 * 0.2;
            let wp2y = p2y + n2 * 0.2;
            let wp3x = p3x - n2 * 0.2;
            let wp3y = p3y - n1 * 0.2;
            let wp4x = p4x - n1 * 0.2;
            let wp4y = p4y + n2 * 0.2;

            let (r2x, r2y) = rot_mul(s2, c2, u - wp2x, v - wp2y);
            let (r3x, r3y) = rot_mul(s3, c3, u - wp3x, v - wp3y);
            let (r4x, r4y) = rot_mul(s4, c4, u - wp4x, v - wp4y);

            let l2 = ((r2x * 1.0).powi(2) + (r2y * 1.6).powi(2)).sqrt();
            let l3 = ((r3x * 1.5).powi(2) + (r3y * 1.0).powi(2)).sqrt();
            let l4 = ((r4x * 1.2).powi(2) + (r4y * 1.5).powi(2)).sqrt();

            let d2 = (1.0 / (l2 + 0.08)).powf(2.4);
            let d3 = (1.0 / (l3 + 0.08)).powf(2.4);
            let d4 = (1.0 / (l4 + 0.08)).powf(2.4);

            let sum = bg_weight + d2 + d3 + d4;
            let mut r = (c_bg[0] * bg_weight + c_2[0] * d2 + c_3[0] * d3 + c_4[0] * d4) / sum;
            let mut g = (c_bg[1] * bg_weight + c_2[1] * d2 + c_3[1] * d3 + c_4[1] * d4) / sum;
            let mut b = (c_bg[2] * bg_weight + c_2[2] * d2 + c_3[2] * d3 + c_4[2] * d4) / sum;

            let dx = u - 0.5;
            let dy = v - 0.5;
            let vignette = ((dx * dx + dy * dy).sqrt() * 1.2).clamp(0.0, 1.0);
            let vig_scale = 1.0 - 0.75 * vignette;
            r *= vig_scale;
            g *= vig_scale;
            b *= vig_scale;

            let d1 = ign(px as f32, py as f32);
            let d2n = ign(px as f32 + 5.588238, py as f32 + 17.13191);
            let dither = (d1 + d2n - 1.0) / 255.0;
            let non_black = if r.max(g).max(b) >= 0.001 { 1.0 } else { 0.0 };

            r = (r + dither * non_black).clamp(0.0, 1.0);
            g = (g + dither * non_black).clamp(0.0, 1.0);
            b = (b + dither * non_black).clamp(0.0, 1.0);

            let idx = ((py * FLUID_W + px) * 4) as usize;
            out[idx] = (r * 255.0 + 0.5) as u8;
            out[idx + 1] = (g * 255.0 + 0.5) as u8;
            out[idx + 2] = (b * 255.0 + 0.5) as u8;
            out[idx + 3] = 255;
        }
    }

    out
}

#[derive(Clone, Debug)]
pub struct FluidState {
    current: [[f32; 3]; 4],
    displayed: [[f32; 3]; 4],
    target: [[f32; 3]; 4],
    transition_progress: f32,
    anim_time: f32,
    frame_accum: f32,
    frame_handle: image::Handle,
}

impl Default for FluidState {
    fn default() -> Self {
        let init = [
            [42.0 / 255.0, 8.0 / 255.0, 69.0 / 255.0],
            [100.0 / 255.0, 65.0 / 255.0, 165.0 / 255.0],
            [10.0 / 255.0, 17.0 / 255.0, 40.0 / 255.0],
            [18.0 / 255.0, 14.0 / 255.0, 43.0 / 255.0],
        ];
        let initial_time = 1.5;
        let pixels = render_fluid_rgba(&init, initial_time);
        Self {
            current: init,
            displayed: init,
            target: init,
            transition_progress: 1.0,
            anim_time: initial_time,
            frame_accum: 0.0,
            frame_handle: image::Handle::from_rgba(FLUID_W, FLUID_H, pixels),
        }
    }
}

impl FluidState {
    pub fn is_transitioning(&self) -> bool {
        self.transition_progress < 1.0
    }

    pub fn frame_handle(&self) -> image::Handle {
        self.frame_handle.clone()
    }

    pub fn set_target_colors(&mut self, next: [[f32; 3]; 4]) {
        self.current = self.displayed;
        self.target = next;
        self.transition_progress = 0.0;
    }

    pub fn step(&mut self, dt_secs: f32, is_playing: bool) {
        let clamped_dt = dt_secs.clamp(0.0, 0.12);
        let was_transitioning = self.transition_progress < 1.0;

        if is_playing || was_transitioning {
            self.anim_time += clamped_dt;
            self.frame_accum += clamped_dt;
        }

        if was_transitioning {
            self.transition_progress = (self.transition_progress + clamped_dt * 0.55).min(1.0);
        }

        let t = self.transition_progress;
        let ease = t * t * t * (t * (t * 6.0 - 15.0) + 10.0);

        for i in 0..4 {
            self.displayed[i] = lerp_rgb_linear(self.current[i], self.target[i], ease);
        }

        if self.transition_progress >= 1.0 {
            self.current = self.target;
        }

        if was_transitioning || (is_playing && self.frame_accum >= 0.08) {
            self.frame_accum = 0.0;
            let pixels = render_fluid_rgba(&self.displayed, self.anim_time);
            self.frame_handle = image::Handle::from_rgba(FLUID_W, FLUID_H, pixels);
        }
    }
}

pub fn default_palette() -> [[f32; 3]; 4] {
    [
        [0.0, 0.0, 0.0],
        [138.0 / 255.0, 43.0 / 255.0, 226.0 / 255.0],
        [0.0, 210.0 / 255.0, 1.0],
        [1.0, 0.0, 127.0 / 255.0],
    ]
}

fn srgb_to_linear(c: f32) -> f32 {
    c.clamp(0.0, 1.0).powf(2.2)
}

fn linear_to_srgb(c: f32) -> f32 {
    c.clamp(0.0, 1.0).powf(1.0 / 2.2)
}

pub fn lerp_rgb_linear(a: [f32; 3], b: [f32; 3], t: f32) -> [f32; 3] {
    [
        linear_to_srgb(srgb_to_linear(a[0]) + (srgb_to_linear(b[0]) - srgb_to_linear(a[0])) * t),
        linear_to_srgb(srgb_to_linear(a[1]) + (srgb_to_linear(b[1]) - srgb_to_linear(a[1])) * t),
        linear_to_srgb(srgb_to_linear(a[2]) + (srgb_to_linear(b[2]) - srgb_to_linear(a[2])) * t),
    ]
}

/// Extract 4 dominant ambient colors from a cached album art file (matching `ui.js` heuristics).
pub fn extract_dominant_colors_from_path(path: &Path) -> [[f32; 3]; 4] {
    let Ok(img) = ::image::open(path) else {
        return default_palette();
    };
    let small = img.thumbnail_exact(64, 64).to_rgb8();
    let raw = small.as_raw();

    #[derive(Clone, Copy)]
    struct Cand {
        r: u8,
        g: u8,
        b: u8,
        sat: u8,
    }

    let mut cands: Vec<Cand> = Vec::new();
    for px in raw.chunks_exact(3).step_by(16) {
        let (r, g, b) = (px[0], px[1], px[2]);
        let max_c = r.max(g).max(b);
        let min_c = r.min(g).min(b);
        let sat = max_c - min_c;
        if max_c >= 50 && max_c <= 215 && sat >= 45 {
            cands.push(Cand { r, g, b, sat });
        }
    }

    cands.sort_by(|a, b| b.sat.cmp(&a.sat));

    let mut selected: Vec<[f32; 3]> = Vec::with_capacity(4);
    selected.push([0.0, 0.0, 0.0]);

    for c in cands {
        let distinct = selected.iter().skip(1).all(|ex| {
            let dr = c.r as f32 - ex[0] * 255.0;
            let dg = c.g as f32 - ex[1] * 255.0;
            let db = c.b as f32 - ex[2] * 255.0;
            (dr * dr + dg * dg + db * db).sqrt() >= 50.0
        });
        if distinct {
            selected.push([c.r as f32 / 255.0, c.g as f32 / 255.0, c.b as f32 / 255.0]);
            if selected.len() == 4 {
                break;
            }
        }
    }

    let fallback = [
        [138.0 / 255.0, 43.0 / 255.0, 226.0 / 255.0],
        [0.0, 210.0 / 255.0, 1.0],
        [1.0, 0.0, 127.0 / 255.0],
    ];
    let mut fi = 0;
    while selected.len() < 4 && fi < fallback.len() {
        selected.push(fallback[fi]);
        fi += 1;
    }

    [selected[0], selected[1], selected[2], selected[3]]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_dominant_colors_and_linear_lerp() {
        let missing = Path::new("nonexistent_cover_12345.jpg");
        assert_eq!(extract_dominant_colors_from_path(missing), default_palette());

        let mid = lerp_rgb_linear([0.0, 0.0, 0.0], [1.0, 1.0, 1.0], 0.5);
        assert!(mid[0] > 0.7 && mid[0] < 0.76, "Linear midpoint ~0.73 sRGB");

        let mut st = FluidState::default();
        let rgba = render_fluid_rgba(&default_palette(), 1.5);
        assert_eq!(rgba.len(), (FLUID_W * FLUID_H * 4) as usize);
        assert!(rgba.chunks_exact(4).any(|px| px[0] > 0 || px[1] > 0 || px[2] > 0));

        st.set_target_colors(default_palette());
        assert!(st.is_transitioning());
        for _ in 0..80 {
            st.step(0.03, false);
        }
        assert!(!st.is_transitioning());
    }
}
