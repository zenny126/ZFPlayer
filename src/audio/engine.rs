use serde_json::{json, Value};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use wasapi::{
    calculate_period_100ns, initialize_mta, AudioClient, Device, DeviceEnumerator, Direction,
    Handle as WasapiHandle, SampleType, ShareMode, StreamMode, WasapiError, WaveFormat,
};

use crate::audio::buffer::AudioRingBuffer;
use crate::audio::decoder::StreamingDecoder;
use crate::config::Config;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AudioState {
    Idle,
    Loading,
    Playing,
    Paused,
    Stopped,
}

impl AudioState {
    pub fn as_str(&self) -> &'static str {
        match self {
            AudioState::Idle => "IDLE",
            AudioState::Loading => "LOADING",
            AudioState::Playing => "PLAYING",
            AudioState::Paused => "PAUSED",
            AudioState::Stopped => "STOPPED",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DacSampleFormat {
    Float32,
    Int24In32,
    Int24Packed,
    Int32,
    Int16,
}

struct SharedAudioContext {
    state: AudioState,
    volume: f32,
    audio_mode: String,
    ring_buffer: Option<Arc<AudioRingBuffer>>,
    decoder: Option<StreamingDecoder>,
    play_pos_frames: u64,
    total_frames: u64,
    duration_secs: f64,
    sample_rate: u32,
    channels: usize,

    // Smooth anti-pop micro ramps (20ms fade-in, 15ms fade-out)
    fade_in_total: u64,
    fade_in_remaining: u64,
    fade_out_total: u64,
    fade_out_remaining: u64,
    target_state_after_fade: AudioState,
}

pub struct AudioEngine {
    ctx: Arc<Mutex<SharedAudioContext>>,
    config: Config,
    track_end_pair: Arc<(Mutex<bool>, Condvar)>,
    on_track_end_cb: Arc<Mutex<Option<Box<dyn Fn() + Send + Sync + 'static>>>>,
    stream_alive: Arc<AtomicBool>,
    stream_open: Arc<AtomicBool>,
    stream_rebuild_needed: Arc<AtomicBool>,
    stream_wake: Arc<(Mutex<u64>, Condvar)>,
    stream_spec_ready: Arc<(Mutex<u64>, Condvar)>,
}

impl AudioEngine {
    pub fn new(config: Config) -> Arc<Self> {
        let initial_mode = config.get_string("audio_mode", "shared");
        let initial_vol = config.get_f64("volume", 0.8) as f32;

        let ctx = Arc::new(Mutex::new(SharedAudioContext {
            state: AudioState::Idle,
            volume: initial_vol.clamp(0.0, 1.0),
            audio_mode: initial_mode,
            ring_buffer: None,
            decoder: None,
            play_pos_frames: 0,
            total_frames: 0,
            duration_secs: 0.0,
            sample_rate: 44100,
            channels: 2,
            fade_in_total: 0,
            fade_in_remaining: 0,
            fade_out_total: 0,
            fade_out_remaining: 0,
            target_state_after_fade: AudioState::Stopped,
        }));

        let track_end_pair = Arc::new((Mutex::new(false), Condvar::new()));
        let on_track_end_cb: Arc<Mutex<Option<Box<dyn Fn() + Send + Sync + 'static>>>> =
            Arc::new(Mutex::new(None));

        let engine = Arc::new(Self {
            ctx,
            config,
            track_end_pair: track_end_pair.clone(),
            on_track_end_cb: on_track_end_cb.clone(),
            stream_alive: Arc::new(AtomicBool::new(true)),
            stream_open: Arc::new(AtomicBool::new(false)),
            stream_rebuild_needed: Arc::new(AtomicBool::new(false)),
            stream_wake: Arc::new((Mutex::new(0), Condvar::new())),
            stream_spec_ready: Arc::new((Mutex::new(0), Condvar::new())),
        });

        // Dedicated Track-End Event Dispatcher Thread (decoupled from WASAPI realtime thread)
        {
            let pair = track_end_pair;
            let cb_holder = on_track_end_cb;
            thread::Builder::new()
                .name("AudioTrackEndDispatcher".to_string())
                .spawn(move || loop {
                    let (lock, cvar) = &*pair;
                    let mut triggered = lock.lock().unwrap();
                    while !*triggered {
                        triggered = cvar.wait(triggered).unwrap();
                    }
                    *triggered = false;
                    drop(triggered);

                    if let Ok(guard) = cb_holder.lock() {
                        if let Some(ref cb) = *guard {
                            cb();
                        }
                    }
                })
                .ok();
        }

        // Dedicated Native WASAPI Render Thread (Shared AutoConvert & Exclusive Bit-Perfect)
        {
            let eng = engine.clone();
            thread::Builder::new()
                .name("WASAPIRenderThread".to_string())
                .spawn(move || {
                    eng.wasapi_render_loop();
                })
                .ok();
        }

        engine
    }

    pub fn set_on_track_end<F>(&self, callback: F)
    where
        F: Fn() + Send + Sync + 'static,
    {
        if let Ok(mut guard) = self.on_track_end_cb.lock() {
            *guard = Some(Box::new(callback));
        }
    }

    fn notify_stream_wake(&self) {
        let (lock, cvar) = &*self.stream_wake;
        if let Ok(mut gen) = lock.lock() {
            *gen = gen.wrapping_add(1);
            cvar.notify_all();
        }
    }

    fn request_stream_rebuild_and_wait(&self) {
        if !self.stream_open.load(Ordering::SeqCst) {
            return;
        }
        let target_seq = {
            let (lock, _) = &*self.stream_spec_ready;
            lock.lock().map(|g| *g).unwrap_or(0)
        };
        self.stream_rebuild_needed.store(true, Ordering::SeqCst);
        self.notify_stream_wake();

        let (lock, cvar) = &*self.stream_spec_ready;
        let deadline = Instant::now() + Duration::from_millis(300);
        if let Ok(mut guard) = lock.lock() {
            while *guard == target_seq && self.stream_open.load(Ordering::SeqCst) {
                let rem = deadline.saturating_duration_since(Instant::now());
                if rem.is_zero() {
                    break;
                }
                let Ok((g, timeout_res)) = cvar.wait_timeout(guard, rem) else {
                    break;
                };
                guard = g;
                if timeout_res.timed_out() {
                    break;
                }
            }
        }
    }

    fn make_exclusive_mode(use_events: bool, period_hns: i64) -> StreamMode {
        if use_events {
            StreamMode::EventsExclusive { period_hns }
        } else {
            StreamMode::PollingExclusive {
                buffer_duration_hns: 4 * period_hns,
                period_hns,
            }
        }
    }

    fn init_exclusive_with_alignment(
        device: &Device,
        desired_format: &WaveFormat,
        desired_period: i64,
        use_events: bool,
    ) -> Result<(AudioClient, Option<WasapiHandle>), String> {
        let mut audio_client = device
            .get_iaudioclient()
            .map_err(|e| format!("get_iaudioclient failed: {}", e))?;
        let mode = Self::make_exclusive_mode(use_events, desired_period);

        match audio_client.initialize_client(desired_format, Direction::Render, mode, None) {
            Ok(()) => {}
            Err(WasapiError::Windows(werr)) if werr.code().0 as u32 == 0x88890019 => {
                // Handle AUDCLNT_E_BUFFER_SIZE_NOT_ALIGNED (0x88890019)
                let buffersize = audio_client
                    .get_buffer_size()
                    .map_err(|e| format!("get_buffer_size failed: {}", e))?;
                let aligned_period = calculate_period_100ns(
                    buffersize as i64,
                    desired_format.get_samplespersec() as i64,
                );
                audio_client = device
                    .get_iaudioclient()
                    .map_err(|e| format!("re-create iaudioclient failed: {}", e))?;
                let aligned_mode = Self::make_exclusive_mode(use_events, aligned_period);
                audio_client
                    .initialize_client(desired_format, Direction::Render, aligned_mode, None)
                    .map_err(|e| format!("Aligned Exclusive initialize failed: {}", e))?;
            }
            Err(e) => return Err(format!("WASAPI Exclusive init error: {}", e)),
        }

        if use_events {
            let ev = audio_client
                .set_get_eventhandle()
                .map_err(|e| format!("set_get_eventhandle failed: {}", e))?;
            Ok((audio_client, Some(ev)))
        } else {
            Ok((audio_client, None))
        }
    }

    /// Negotiate and initialize WASAPI Exclusive Mode (Bit-Perfect 100%) at exact native (sr, ch),
    /// preferring zero-poll event-driven timing with transparent fallback to polling mode.
    fn try_open_exclusive(
        device: &Device,
        sr: usize,
        ch: usize,
    ) -> Result<(AudioClient, WaveFormat, DacSampleFormat, Option<WasapiHandle>), String> {
        let probe_client = device
            .get_iaudioclient()
            .map_err(|e| format!("get_iaudioclient failed: {}", e))?;

        // Try bit-perfect formats in priority order: Float32 -> 24-in-32 Int -> 24-bit packed -> 32-bit Int -> 16-bit Int
        let candidates = [
            (32, 32, SampleType::Float, DacSampleFormat::Float32),
            (32, 24, SampleType::Int, DacSampleFormat::Int24In32),
            (24, 24, SampleType::Int, DacSampleFormat::Int24Packed),
            (32, 32, SampleType::Int, DacSampleFormat::Int32),
            (16, 16, SampleType::Int, DacSampleFormat::Int16),
        ];

        let mut negotiated: Option<(WaveFormat, DacSampleFormat)> = None;
        for (store_bits, valid_bits, stype, dac_fmt) in candidates {
            let fmt = WaveFormat::new(store_bits, valid_bits, stype, sr, ch, None);
            if let Ok(supported_fmt) = probe_client.is_supported_exclusive_with_quirks(&fmt) {
                negotiated = Some((supported_fmt, dac_fmt));
                break;
            }
        }

        let (desired_format, dac_fmt) = negotiated.ok_or_else(|| {
            format!(
                "DAC does not support {}Hz / {}ch in WASAPI Exclusive mode",
                sr, ch
            )
        })?;

        let (def_period, _min_period) = probe_client
            .get_device_period()
            .map_err(|e| format!("get_device_period failed: {}", e))?;
        let desired_period = probe_client
            .calculate_aligned_period_near(def_period, Some(128), &desired_format)
            .unwrap_or(def_period);
        drop(probe_client);

        match Self::init_exclusive_with_alignment(device, &desired_format, desired_period, true) {
            Ok((client, ev)) => Ok((client, desired_format, dac_fmt, ev)),
            Err(_) => {
                let (client, ev) =
                    Self::init_exclusive_with_alignment(device, &desired_format, desired_period, false)?;
                Ok((client, desired_format, dac_fmt, ev))
            }
        }
    }

    /// Initialize WASAPI Shared Mode at track's native (sr, ch) with AutoConvert enabled,
    /// preferring zero-poll event-driven timing with fallback to polling mode.
    fn try_open_shared(
        device: &Device,
        sr: usize,
        ch: usize,
    ) -> Result<(AudioClient, WaveFormat, DacSampleFormat, Option<WasapiHandle>), String> {
        let mut audio_client = device
            .get_iaudioclient()
            .map_err(|e| format!("get_iaudioclient failed: {}", e))?;

        let desired_format = WaveFormat::new(32, 32, SampleType::Float, sr, ch, None);
        let needs_convert = !matches!(
            audio_client.is_supported(&desired_format, ShareMode::Shared),
            Ok(None)
        );

        let (def_time, _min_time) = audio_client.get_device_period().unwrap_or((100_000, 30_000));
        // Use 4x default period (or at least 40ms) for zero-glitch shared mode stability
        let buffer_hns = (def_time * 4).max(400_000);

        let event_mode = StreamMode::EventsShared {
            autoconvert: needs_convert,
            buffer_duration_hns: buffer_hns,
        };
        if audio_client
            .initialize_client(&desired_format, Direction::Render, event_mode, None)
            .is_ok()
        {
            if let Ok(ev) = audio_client.set_get_eventhandle() {
                return Ok((audio_client, desired_format, DacSampleFormat::Float32, Some(ev)));
            }
            audio_client = device
                .get_iaudioclient()
                .map_err(|e| format!("re-create iaudioclient failed: {}", e))?;
        }

        let poll_mode = StreamMode::PollingShared {
            autoconvert: needs_convert,
            buffer_duration_hns: buffer_hns,
        };
        audio_client
            .initialize_client(&desired_format, Direction::Render, poll_mode, None)
            .map_err(|e| format!("WASAPI Shared initialize failed: {}", e))?;

        Ok((audio_client, desired_format, DacSampleFormat::Float32, None))
    }

    fn wasapi_render_loop(&self) {
        let _ = initialize_mta();

        let mut f32_scratch: Vec<f32> = Vec::with_capacity(8192 * 2);
        let mut byte_scratch: Vec<u8> = Vec::with_capacity(8192 * 8);

        while self.stream_alive.load(Ordering::Relaxed) {
            // Sleep on condition variable when idle/paused/stopped so the DAC hardware is never
            // held exclusively before playback and CPU usage stays at 0%.
            {
                let (lock, cvar) = &*self.stream_wake;
                let mut gen_guard = lock.lock().unwrap();
                loop {
                    if !self.stream_alive.load(Ordering::Relaxed) {
                        return;
                    }
                    let is_active = self
                        .ctx
                        .lock()
                        .map(|c| c.state == AudioState::Playing || c.fade_out_remaining > 0)
                        .unwrap_or(false);
                    if is_active {
                        break;
                    }
                    let Ok(g) = cvar.wait(gen_guard) else {
                        return;
                    };
                    gen_guard = g;
                }
            }

            let Ok(enumerator) = DeviceEnumerator::new() else {
                thread::sleep(Duration::from_millis(500));
                continue;
            };
            let Ok(device) = enumerator.get_default_device(Direction::Render) else {
                thread::sleep(Duration::from_millis(500));
                continue;
            };

            let (sr, ch, mode) = if let Ok(guard) = self.ctx.lock() {
                (
                    guard.sample_rate.max(8000) as usize,
                    guard.channels.max(1),
                    guard.audio_mode.clone(),
                )
            } else {
                (44100, 2, "shared".to_string())
            };

            self.stream_rebuild_needed.store(false, Ordering::SeqCst);

            let opened = if mode == "exclusive" {
                match Self::try_open_exclusive(&device, sr, ch) {
                    Ok(res) => {
                        log::info!(
                            "Opened WASAPI Exclusive Bit-Perfect stream: {}Hz / {}ch ({:?})",
                            sr,
                            ch,
                            res.2
                        );
                        Ok(res)
                    }
                    Err(e) => {
                        log::warn!(
                            "WASAPI Exclusive failed ({}), falling back to WASAPI Shared AutoConvert",
                            e
                        );
                        Self::try_open_shared(&device, sr, ch)
                    }
                }
            } else {
                let res = Self::try_open_shared(&device, sr, ch);
                if res.is_ok() {
                    log::info!(
                        "Opened WASAPI Shared stream: {}Hz / {}ch (AutoConvert)",
                        sr,
                        ch
                    );
                }
                res
            };

            let Ok((audio_client, wave_format, dac_fmt, event_handle)) = opened else {
                thread::sleep(Duration::from_millis(300));
                continue;
            };

            let Ok(render_client) = audio_client.get_audiorenderclient() else {
                thread::sleep(Duration::from_millis(300));
                continue;
            };

            let buffer_frames = audio_client.get_buffer_size().unwrap_or(4096) as usize;
            let block_align = wave_format.get_blockalign() as usize;
            let sleep_ms = ((500 * buffer_frames as u64) / (sr as u64).max(1)).clamp(2, 15);
            let sleep_period = Duration::from_millis(sleep_ms);

            // Prime the WASAPI buffer before starting stream
            if let Ok(avail) = audio_client.get_available_space_in_frames() {
                let n_frames = avail as usize;
                if n_frames > 0 {
                    f32_scratch.resize(n_frames * ch, 0.0);
                    Self::render_f32_frames(&mut f32_scratch, ch, &self.ctx, &self.track_end_pair);
                    Self::pack_dac_bytes(&f32_scratch, dac_fmt, block_align, ch, &mut byte_scratch);
                    let _ = render_client.write_to_device(&byte_scratch, None);
                }
            }

            if audio_client.start_stream().is_err() {
                thread::sleep(Duration::from_millis(300));
                continue;
            }

            self.stream_open.store(true, Ordering::SeqCst);
            let mut idle_since: Option<Instant> = None;

            while self.stream_alive.load(Ordering::Relaxed)
                && !self.stream_rebuild_needed.load(Ordering::Relaxed)
            {
                let (release_now, is_idle) = if let Ok(c) = self.ctx.lock() {
                    let active = c.state == AudioState::Playing || c.fade_out_remaining > 0;
                    if active {
                        (false, false)
                    } else {
                        // In Exclusive mode, release hardware DAC immediately when not playing
                        (c.audio_mode == "exclusive", true)
                    }
                } else {
                    (false, true)
                };

                if release_now {
                    break;
                }
                if is_idle {
                    let since = *idle_since.get_or_insert_with(Instant::now);
                    if since.elapsed() >= Duration::from_millis(500) {
                        break;
                    }
                } else {
                    idle_since = None;
                }

                if let Some(ref h_ev) = event_handle {
                    if h_ev.wait_for_event(100).is_err() {
                        continue;
                    }
                } else {
                    thread::sleep(sleep_period);
                }

                if !self.stream_alive.load(Ordering::Relaxed)
                    || self.stream_rebuild_needed.load(Ordering::Relaxed)
                {
                    break;
                }

                let Ok(avail) = audio_client.get_available_space_in_frames() else {
                    // Device disconnected or invalidated -> break to auto-recover
                    break;
                };

                let n_frames = avail as usize;
                if n_frames == 0 {
                    continue;
                }

                f32_scratch.resize(n_frames * ch, 0.0);
                Self::render_f32_frames(&mut f32_scratch, ch, &self.ctx, &self.track_end_pair);
                Self::pack_dac_bytes(&f32_scratch, dac_fmt, block_align, ch, &mut byte_scratch);

                if render_client.write_to_device(&byte_scratch, None).is_err() {
                    break;
                }
            }

            drop(render_client);
            let _ = audio_client.stop_stream();
            drop(audio_client);

            self.stream_open.store(false, Ordering::SeqCst);
            {
                let (lock, cvar) = &*self.stream_spec_ready;
                if let Ok(mut seq) = lock.lock() {
                    *seq = seq.wrapping_add(1);
                    cvar.notify_all();
                }
            }
        }
    }

    fn pack_dac_bytes(
        samples: &[f32],
        dac_fmt: DacSampleFormat,
        block_align: usize,
        channels: usize,
        out_bytes: &mut Vec<u8>,
    ) {
        let _ = (block_align, channels);
        let sample_bytes = match dac_fmt {
            DacSampleFormat::Float32 | DacSampleFormat::Int24In32 | DacSampleFormat::Int32 => 4,
            DacSampleFormat::Int24Packed => 3,
            DacSampleFormat::Int16 => 2,
        };
        out_bytes.resize(samples.len() * sample_bytes, 0);

        match dac_fmt {
            DacSampleFormat::Float32 => {
                for (dst, &s) in out_bytes.chunks_exact_mut(4).zip(samples.iter()) {
                    dst.copy_from_slice(&s.to_le_bytes());
                }
            }
            DacSampleFormat::Int24In32 => {
                // 24-bit valid sample in upper 24 bits of 32-bit container with zeroed LSB padding byte
                for (dst, &s) in out_bytes.chunks_exact_mut(4).zip(samples.iter()) {
                    let clamped = s.clamp(-1.0, 1.0) as f64;
                    let s24 = (clamped * 8388607.0).round() as i32;
                    dst.copy_from_slice(&(s24 << 8).to_le_bytes());
                }
            }
            DacSampleFormat::Int32 => {
                for (dst, &s) in out_bytes.chunks_exact_mut(4).zip(samples.iter()) {
                    let clamped = s.clamp(-1.0, 1.0) as f64;
                    let v = (clamped * 2147483647.0).round() as i32;
                    dst.copy_from_slice(&v.to_le_bytes());
                }
            }
            DacSampleFormat::Int24Packed => {
                for (dst, &s) in out_bytes.chunks_exact_mut(3).zip(samples.iter()) {
                    let clamped = s.clamp(-1.0, 1.0) as f64;
                    let v = (clamped * 8388607.0).round() as i32;
                    let b = v.to_le_bytes();
                    dst[0] = b[0];
                    dst[1] = b[1];
                    dst[2] = b[2];
                }
            }
            DacSampleFormat::Int16 => {
                for (dst, &s) in out_bytes.chunks_exact_mut(2).zip(samples.iter()) {
                    let clamped = s.clamp(-1.0, 1.0);
                    let v = (clamped * 32767.0).round() as i16;
                    dst.copy_from_slice(&v.to_le_bytes());
                }
            }
        }
    }

    fn render_f32_frames(
        outdata: &mut [f32],
        ch: usize,
        ctx_mutex: &Arc<Mutex<SharedAudioContext>>,
        track_end_pair: &Arc<(Mutex<bool>, Condvar)>,
    ) {
        let Ok(mut ctx) = ctx_mutex.lock() else {
            outdata.fill(0.0);
            return;
        };

        let frames = outdata.len() / ch.max(1);
        if frames == 0 {
            return;
        }

        // 1. Handle active Fade-Out (during manual pause/stop)
        if ctx.fade_out_remaining > 0 {
            let fade_len = (frames as u64).min(ctx.fade_out_remaining) as usize;
            let remaining = ctx.total_frames.saturating_sub(ctx.play_pos_frames) as usize;
            let frames_to_copy = fade_len.min(remaining);

            if let Some(ref rb) = ctx.ring_buffer {
                if frames_to_copy > 0 {
                    let read_frames = rb.read_into(&mut outdata[0..(frames_to_copy * ch)], ch);
                    ctx.play_pos_frames += read_frames as u64;
                    if read_frames < fade_len {
                        outdata[(read_frames * ch)..(fade_len * ch)].fill(0.0);
                    }
                } else {
                    outdata[0..(fade_len * ch)].fill(0.0);
                }
            } else {
                outdata[0..(fade_len * ch)].fill(0.0);
            }

            let start_ratio = ctx.fade_out_remaining as f32 / ctx.fade_out_total.max(1) as f32;
            let end_ratio = (ctx.fade_out_remaining.saturating_sub(fade_len as u64)) as f32
                / ctx.fade_out_total.max(1) as f32;
            Self::apply_linear_ramp(
                &mut outdata[0..(fade_len * ch)],
                ch,
                start_ratio,
                end_ratio,
                fade_len,
            );

            let vol = ctx.volume;
            if (vol - 1.0).abs() > f32::EPSILON {
                for s in &mut outdata[0..(fade_len * ch)] {
                    *s *= vol;
                }
            }

            if fade_len < frames {
                outdata[(fade_len * ch)..].fill(0.0);
            }

            ctx.fade_out_remaining = ctx.fade_out_remaining.saturating_sub(fade_len as u64);
            if ctx.fade_out_remaining == 0 {
                ctx.state = ctx.target_state_after_fade;
            }
            return;
        }

        // 2. Normal Playback
        if ctx.state != AudioState::Playing || ctx.ring_buffer.is_none() {
            outdata.fill(0.0);
            return;
        }

        let remaining = ctx.total_frames.saturating_sub(ctx.play_pos_frames);
        let is_eof = ctx
            .decoder
            .as_ref()
            .map(|d| d.is_eof())
            .unwrap_or(false)
            && ctx
                .ring_buffer
                .as_ref()
                .map(|r| r.available_frames() == 0)
                .unwrap_or(true);

        if (ctx.total_frames > 0 && remaining == 0) || is_eof {
            outdata.fill(0.0);
            if ctx.state == AudioState::Playing {
                ctx.state = AudioState::Stopped;
                let (lock, cvar) = &**track_end_pair;
                if let Ok(mut triggered) = lock.lock() {
                    *triggered = true;
                    cvar.notify_one();
                }
            }
            return;
        }

        let frames_to_copy = if ctx.total_frames > 0 {
            frames.min(remaining as usize)
        } else {
            frames
        };

        let read_frames = if let Some(ref rb) = ctx.ring_buffer {
            rb.read_into(&mut outdata[0..(frames_to_copy * ch)], ch)
        } else {
            0
        };

        ctx.play_pos_frames += read_frames as u64;
        if read_frames < frames {
            outdata[(read_frames * ch)..].fill(0.0);
        }

        // Tail 20ms micro fade-out near end of track
        if ctx.total_frames > 0 && read_frames > 0 {
            let tail_rem = ctx.total_frames.saturating_sub(ctx.play_pos_frames);
            let tail_thresh = (ctx.sample_rate as u64 * 20) / 1000;
            if tail_rem <= tail_thresh && tail_thresh > 0 {
                let start_r = ((tail_rem + read_frames as u64) as f32 / tail_thresh as f32)
                    .clamp(0.0, 1.0);
                let end_r = (tail_rem as f32 / tail_thresh as f32).clamp(0.0, 1.0);
                Self::apply_linear_ramp(
                    &mut outdata[0..(read_frames * ch)],
                    ch,
                    start_r,
                    end_r,
                    read_frames,
                );
            }
        }

        // Head 20ms/15ms micro fade-in when starting or seeking
        if ctx.fade_in_remaining > 0 && read_frames > 0 {
            let fade_len = (read_frames as u64).min(ctx.fade_in_remaining) as usize;
            let done = ctx.fade_in_total.saturating_sub(ctx.fade_in_remaining);
            let total = ctx.fade_in_total.max(1) as f32;
            let start_ratio = done as f32 / total;
            let end_ratio = (done + fade_len as u64) as f32 / total;
            Self::apply_linear_ramp(
                &mut outdata[0..(fade_len * ch)],
                ch,
                start_ratio,
                end_ratio,
                fade_len,
            );
            ctx.fade_in_remaining = ctx.fade_in_remaining.saturating_sub(fade_len as u64);
        }

        let vol = ctx.volume;
        if (vol - 1.0).abs() > f32::EPSILON {
            for s in &mut outdata[0..(read_frames * ch)] {
                *s *= vol;
            }
        }
    }

    fn apply_linear_ramp(
        slice: &mut [f32],
        channels: usize,
        start_val: f32,
        end_val: f32,
        frames: usize,
    ) {
        if frames == 0 || channels == 0 {
            return;
        }
        let step = if frames > 1 {
            (end_val - start_val) / (frames - 1) as f32
        } else {
            0.0
        };
        for f in 0..frames {
            let gain = start_val + (f as f32) * step;
            let base = f * channels;
            for c in 0..channels {
                if base + c < slice.len() {
                    slice[base + c] *= gain;
                }
            }
        }
    }

    pub fn load(&self, file_path: &str) -> Result<(), String> {
        self.stop_immediate();

        let (mut decoder, ring_buffer) = StreamingDecoder::probe_and_create(file_path)?;
        let spec = decoder.spec.clone();
        decoder.start(file_path.to_string());

        let mut recreate_stream = false;
        if let Ok(mut ctx) = self.ctx.lock() {
            if ctx.sample_rate != spec.sample_rate || ctx.channels != spec.channels {
                recreate_stream = true;
            }
            ctx.ring_buffer = Some(ring_buffer);
            ctx.decoder = Some(decoder);
            ctx.play_pos_frames = 0;
            ctx.total_frames = spec.total_frames;
            ctx.duration_secs = spec.duration_secs;
            ctx.sample_rate = spec.sample_rate;
            ctx.channels = spec.channels;
            ctx.fade_in_remaining = 0;
            ctx.fade_out_remaining = 0;
            ctx.state = AudioState::Stopped;
        }

        if recreate_stream {
            self.request_stream_rebuild_and_wait();
        }

        Ok(())
    }

    pub fn play(&self) {
        if let Ok(mut ctx) = self.ctx.lock() {
            if ctx.state == AudioState::Playing || ctx.state == AudioState::Loading {
                return;
            }
            let fade_samples = ((ctx.sample_rate as u64) * 20 / 1000).max(1);
            ctx.fade_in_total = fade_samples;
            ctx.fade_in_remaining = fade_samples;
            ctx.fade_out_remaining = 0;
            ctx.state = AudioState::Playing;
        }
        self.notify_stream_wake();
    }

    pub fn pause(&self) {
        let mut was_playing = false;
        if let Ok(mut ctx) = self.ctx.lock() {
            if ctx.state == AudioState::Playing {
                let fade_samples = ((ctx.sample_rate as u64) * 15 / 1000).max(1);
                ctx.fade_out_total = fade_samples;
                ctx.fade_out_remaining = fade_samples;
                ctx.target_state_after_fade = AudioState::Paused;
                was_playing = true;
            }
        }
        if was_playing {
            thread::sleep(Duration::from_millis(20));
            if let Ok(mut ctx) = self.ctx.lock() {
                ctx.state = AudioState::Paused;
                ctx.fade_out_remaining = 0;
            }
            self.notify_stream_wake();
        }
    }

    pub fn resume(&self) {
        let is_paused = self
            .ctx
            .lock()
            .map(|c| c.state == AudioState::Paused)
            .unwrap_or(false);
        if is_paused {
            self.play();
        }
    }

    pub fn stop(&self) {
        let is_active = self
            .ctx
            .lock()
            .map(|c| c.state == AudioState::Playing || c.state == AudioState::Paused)
            .unwrap_or(false);
        if is_active {
            if let Ok(mut ctx) = self.ctx.lock() {
                let fade_samples = ((ctx.sample_rate as u64) * 15 / 1000).max(1);
                ctx.fade_out_total = fade_samples;
                ctx.fade_out_remaining = fade_samples;
                ctx.target_state_after_fade = AudioState::Stopped;
            }
            thread::sleep(Duration::from_millis(20));
        }
        self.stop_immediate();
    }

    pub fn stop_immediate(&self) {
        let old_decoder = if let Ok(mut ctx) = self.ctx.lock() {
            ctx.state = AudioState::Stopped;
            ctx.fade_in_remaining = 0;
            ctx.fade_out_remaining = 0;
            if let Some(ref rb) = ctx.ring_buffer {
                rb.clear();
            }
            ctx.ring_buffer = None;
            ctx.decoder.take()
        } else {
            None
        };
        if let Some(mut dec) = old_decoder {
            dec.stop();
        }
        self.notify_stream_wake();
    }

    pub fn seek(&self, seconds: f64) {
        if let Ok(mut ctx) = self.ctx.lock() {
            let sr = ctx.sample_rate.max(1) as f64;
            let frame = (seconds.max(0.0) * sr).round() as u64;
            let target_pos = if ctx.total_frames > 0 {
                frame.min(ctx.total_frames)
            } else {
                frame
            };

            if let Some(ref dec) = ctx.decoder {
                dec.seek_seconds(target_pos as f64 / sr);
            }
            ctx.play_pos_frames = target_pos;
            let fade_samples = ((ctx.sample_rate as u64) * 15 / 1000).max(1);
            ctx.fade_in_total = fade_samples;
            ctx.fade_in_remaining = fade_samples;
        }
    }

    pub fn set_volume(&self, level: f64) {
        if let Ok(mut ctx) = self.ctx.lock() {
            ctx.volume = (level as f32).clamp(0.0, 1.0);
        }
    }

    pub fn set_audio_mode(&self, mode: &str) -> String {
        let normalized = if mode == "exclusive_push" || mode == "exclusive" {
            "exclusive"
        } else {
            "shared"
        };

        let changed = if let Ok(mut ctx) = self.ctx.lock() {
            if ctx.audio_mode == normalized {
                false
            } else {
                ctx.audio_mode = normalized.to_string();
                true
            }
        } else {
            false
        };

        if changed {
            self.config.set("audio_mode", json!(normalized));
            self.request_stream_rebuild_and_wait();
        }

        normalized.to_string()
    }

    #[cfg_attr(not(test), allow(dead_code))]
    pub fn is_stream_open(&self) -> bool {
        self.stream_open.load(Ordering::SeqCst)
    }

    pub fn get_state(&self) -> Value {
        if let Ok(ctx) = self.ctx.lock() {
            let pos_sec = if ctx.sample_rate > 0 {
                ctx.play_pos_frames as f64 / ctx.sample_rate as f64
            } else {
                0.0
            };
            json!({
                "state": ctx.state.as_str(),
                "position_seconds": pos_sec,
                "duration": ctx.duration_secs,
                "volume": ctx.volume,
                "is_playing": ctx.state == AudioState::Playing,
                "audio_mode": ctx.audio_mode
            })
        } else {
            json!({
                "state": "IDLE",
                "position_seconds": 0.0,
                "duration": 0.0,
                "volume": 0.8,
                "is_playing": false,
                "audio_mode": "shared"
            })
        }
    }

    pub fn shutdown_hardware_stream(&self) {
        self.stop_immediate();
        self.stream_alive.store(false, Ordering::SeqCst);
        self.notify_stream_wake();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pack_dac_bytes_all_formats_and_clamping() {
        let samples = [-1.5f32, 0.0, 1.5, 0.5];
        let mut out = Vec::new();

        // Float32
        AudioEngine::pack_dac_bytes(&samples, DacSampleFormat::Float32, 4, 1, &mut out);
        assert_eq!(out.len(), 16);
        assert_eq!(&out[4..8], &0.0f32.to_le_bytes());

        // Int24In32: LSB byte MUST be zero and extremes clamped
        AudioEngine::pack_dac_bytes(&samples, DacSampleFormat::Int24In32, 4, 1, &mut out);
        assert_eq!(out.len(), 16);
        for chunk in out.chunks_exact(4) {
            assert_eq!(chunk[0], 0, "Int24In32 LSB padding byte must be 0");
        }
        assert_eq!(
            i32::from_le_bytes(out[0..4].try_into().unwrap()),
            (-8388607i32) << 8
        );
        assert_eq!(
            i32::from_le_bytes(out[8..12].try_into().unwrap()),
            8388607i32 << 8
        );

        // Int24Packed: 3 bytes per sample
        AudioEngine::pack_dac_bytes(&samples, DacSampleFormat::Int24Packed, 3, 1, &mut out);
        assert_eq!(out.len(), 12);
        assert_eq!(&out[6..9], &[0xff, 0xff, 0x7f]); // +8388607 LE

        // Int32: full 32-bit range
        AudioEngine::pack_dac_bytes(&samples, DacSampleFormat::Int32, 4, 1, &mut out);
        assert_eq!(out.len(), 16);
        assert_eq!(
            i32::from_le_bytes(out[8..12].try_into().unwrap()),
            i32::MAX
        );

        // Int16
        AudioEngine::pack_dac_bytes(&samples, DacSampleFormat::Int16, 2, 1, &mut out);
        assert_eq!(out.len(), 8);
        assert_eq!(
            i16::from_le_bytes(out[0..2].try_into().unwrap()),
            -32767i16
        );
        assert_eq!(i16::from_le_bytes(out[4..6].try_into().unwrap()), 32767i16);
    }
}
