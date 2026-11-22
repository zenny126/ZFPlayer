use std::fs::File;
use std::path::Path;
use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use lofty::file::AudioFile;
use lofty::probe::Probe as LoftyProbe;
use symphonia::core::audio::SampleBuffer;
use symphonia::core::codecs::{DecoderOptions, CODEC_TYPE_NULL};
use symphonia::core::errors::Error as SymphoniaError;
use symphonia::core::formats::{FormatOptions, SeekMode, SeekTo};
use symphonia::core::io::MediaSourceStream;
use symphonia::core::meta::MetadataOptions;
use symphonia::core::probe::Hint;
use symphonia::core::units::Time;

use crate::audio::buffer::AudioRingBuffer;

#[derive(Clone, Debug)]
pub struct AudioTrackSpec {
    pub sample_rate: u32,
    pub channels: usize,
    pub total_frames: u64,
    pub duration_secs: f64,
}

pub struct StreamingDecoder {
    ring_buffer: Arc<AudioRingBuffer>,
    stop_flag: Arc<AtomicBool>,
    eof_reached: Arc<AtomicBool>,
    seek_target_ms: Arc<AtomicI64>,
    wake_pair: Arc<(Mutex<u64>, Condvar)>,
    worker_handle: Option<JoinHandle<()>>,
    pub spec: AudioTrackSpec,
}

impl StreamingDecoder {
    /// Probe audio file and create a pure bit-accurate native-rate streaming decoder (zero resampling).
    pub fn probe_and_create(file_path: &str) -> Result<(Self, Arc<AudioRingBuffer>), String> {
        let path = Path::new(file_path);
        let file = File::open(path).map_err(|e| format!("Cannot open audio file: {}", e))?;
        let mss = MediaSourceStream::new(Box::new(file), Default::default());

        let mut hint = Hint::new();
        if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
            hint.with_extension(ext);
        }

        let probed = symphonia::default::get_probe()
            .format(
                &hint,
                mss,
                &FormatOptions::default(),
                &MetadataOptions::default(),
            )
            .map_err(|e| format!("Unsupported audio format: {}", e))?;

        let format = probed.format;
        let track = format
            .tracks()
            .iter()
            .find(|t| t.codec_params.codec != CODEC_TYPE_NULL)
            .ok_or_else(|| "No playable audio track found".to_string())?;

        let src_sr = track.codec_params.sample_rate.unwrap_or(44100);
        let src_ch = track
            .codec_params
            .channels
            .map(|c| c.count())
            .unwrap_or(2)
            .max(1);
        let mut total_frames = track.codec_params.n_frames.unwrap_or(0);

        let mut duration_secs = if src_sr > 0 && total_frames > 0 {
            total_frames as f64 / src_sr as f64
        } else if let Some(tb) = track.codec_params.time_base {
            if total_frames > 0 {
                let t = tb.calc_time(total_frames);
                t.seconds as f64 + t.frac
            } else {
                0.0
            }
        } else {
            0.0
        };

        // Fallback for VBR MP3/OGG streams missing container n_frames header
        if duration_secs <= 0.0 || total_frames == 0 {
            if let Ok(probe) = LoftyProbe::open(path) {
                if let Ok(tagged) = probe.read() {
                    let lofty_dur = tagged.properties().duration().as_secs_f64();
                    if lofty_dur > 0.0 {
                        duration_secs = lofty_dur;
                        if total_frames == 0 && src_sr > 0 {
                            total_frames = (lofty_dur * src_sr as f64).round() as u64;
                        }
                    }
                }
            }
        }

        // Allocate 2 seconds of native-rate audio in the ring buffer (matching Python engine.py)
        let capacity_frames = (src_sr as usize) * 2;
        let ring_buffer = Arc::new(AudioRingBuffer::new(capacity_frames, src_ch));

        let spec = AudioTrackSpec {
            sample_rate: src_sr,
            channels: src_ch,
            total_frames,
            duration_secs,
        };

        let decoder = Self {
            ring_buffer: ring_buffer.clone(),
            stop_flag: Arc::new(AtomicBool::new(false)),
            eof_reached: Arc::new(AtomicBool::new(false)),
            seek_target_ms: Arc::new(AtomicI64::new(-1)),
            wake_pair: Arc::new((Mutex::new(0), Condvar::new())),
            worker_handle: None,
            spec,
        };

        Ok((decoder, ring_buffer))
    }

    fn notify_wake(wake_pair: &(Mutex<u64>, Condvar)) {
        if let Ok(mut seq) = wake_pair.0.lock() {
            *seq = seq.wrapping_add(1);
            wake_pair.1.notify_all();
        }
    }

    pub fn start(&mut self, file_path: String) {
        self.stop_flag.store(false, Ordering::SeqCst);
        self.eof_reached.store(false, Ordering::SeqCst);

        let rb = self.ring_buffer.clone();
        let stop_flag = self.stop_flag.clone();
        let eof_flag = self.eof_reached.clone();
        let seek_ms = self.seek_target_ms.clone();
        let wake_pair = self.wake_pair.clone();
        let src_ch = self.spec.channels;

        let handle = thread::Builder::new()
            .name("StreamingDecoderThread".to_string())
            .spawn(move || {
                Self::decode_loop(
                    file_path, rb, stop_flag, eof_flag, seek_ms, wake_pair, src_ch,
                );
            })
            .ok();

        self.worker_handle = handle;
    }

    pub fn seek_seconds(&self, seconds: f64) {
        let ms = (seconds.max(0.0) * 1000.0).round() as i64;
        self.seek_target_ms.store(ms, Ordering::SeqCst);
        self.eof_reached.store(false, Ordering::SeqCst);
        self.ring_buffer.clear();
        Self::notify_wake(&self.wake_pair);
    }

    pub fn is_eof(&self) -> bool {
        self.eof_reached.load(Ordering::Relaxed)
    }

    pub fn stop(&mut self) {
        self.stop_flag.store(true, Ordering::SeqCst);
        self.ring_buffer.wake_up();
        Self::notify_wake(&self.wake_pair);
        if let Some(handle) = self.worker_handle.take() {
            let _ = handle.join();
        }
    }

    fn remix_channels(raw: &[f32], in_ch: usize, out_ch: usize, out_buf: &mut Vec<f32>) {
        out_buf.clear();
        if in_ch == 0 || out_ch == 0 {
            return;
        }
        let frames = raw.len() / in_ch;
        out_buf.reserve(frames * out_ch);
        for f in 0..frames {
            let base = f * in_ch;
            if in_ch == 1 && out_ch == 2 {
                let s = raw[base];
                out_buf.push(s);
                out_buf.push(s);
            } else if out_ch == 1 {
                let sum: f32 = raw[base..base + in_ch].iter().copied().sum();
                out_buf.push(sum / in_ch as f32);
            } else {
                for c in 0..out_ch {
                    out_buf.push(raw[base + (c % in_ch)]);
                }
            }
        }
    }

    fn decode_loop(
        file_path: String,
        ring_buffer: Arc<AudioRingBuffer>,
        stop_flag: Arc<AtomicBool>,
        eof_flag: Arc<AtomicBool>,
        seek_target_ms: Arc<AtomicI64>,
        wake_pair: Arc<(Mutex<u64>, Condvar)>,
        src_ch: usize,
    ) {
        let path = Path::new(&file_path);
        let Ok(file) = File::open(path) else {
            eof_flag.store(true, Ordering::SeqCst);
            return;
        };
        let mss = MediaSourceStream::new(Box::new(file), Default::default());
        let mut hint = Hint::new();
        if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
            hint.with_extension(ext);
        }

        let Ok(probed) = symphonia::default::get_probe().format(
            &hint,
            mss,
            &FormatOptions::default(),
            &MetadataOptions::default(),
        ) else {
            eof_flag.store(true, Ordering::SeqCst);
            return;
        };

        let mut format = probed.format;
        let Some(track) = format
            .tracks()
            .iter()
            .find(|t| t.codec_params.codec != CODEC_TYPE_NULL)
        else {
            eof_flag.store(true, Ordering::SeqCst);
            return;
        };

        let track_id = track.id;

        let Ok(mut decoder) = symphonia::default::get_codecs()
            .make(&track.codec_params, &DecoderOptions::default())
        else {
            eof_flag.store(true, Ordering::SeqCst);
            return;
        };

        let mut sample_buf: Option<SampleBuffer<f32>> = None;
        let mut sample_buf_ch: usize = 0;
        let mut remix_scratch: Vec<f32> = Vec::new();

        while !stop_flag.load(Ordering::Relaxed) {
            let pending_seek = seek_target_ms.swap(-1, Ordering::SeqCst);
            if pending_seek >= 0 {
                let secs = (pending_seek as u64) / 1000;
                let frac = ((pending_seek as u64) % 1000) as f64 / 1000.0;
                let _ = format.seek(
                    SeekMode::Accurate,
                    SeekTo::Time {
                        time: Time::new(secs, frac),
                        track_id: Some(track_id),
                    },
                );
                decoder.reset();
                ring_buffer.clear();
                eof_flag.store(false, Ordering::SeqCst);
            }

            if eof_flag.load(Ordering::Relaxed) {
                if let Ok(guard) = wake_pair.0.lock() {
                    if !stop_flag.load(Ordering::Relaxed) && seek_target_ms.load(Ordering::Relaxed) < 0 {
                        let _ = wake_pair.1.wait_timeout(guard, Duration::from_millis(500));
                    }
                }
                continue;
            }

            if !ring_buffer.wait_for_space(4096, Duration::from_millis(250)) {
                continue;
            }

            let packet = match format.next_packet() {
                Ok(p) => p,
                Err(SymphoniaError::ResetRequired) => {
                    decoder.reset();
                    continue;
                }
                Err(SymphoniaError::IoError(_)) | Err(_) => {
                    eof_flag.store(true, Ordering::SeqCst);
                    continue;
                }
            };

            if packet.track_id() != track_id {
                continue;
            }

            let decoded = match decoder.decode(&packet) {
                Ok(d) => d,
                Err(SymphoniaError::DecodeError(_)) => continue,
                Err(SymphoniaError::ResetRequired) => {
                    decoder.reset();
                    continue;
                }
                Err(_) => {
                    eof_flag.store(true, Ordering::SeqCst);
                    continue;
                }
            };

            let spec = *decoded.spec();
            let decoded_ch = spec.channels.count().max(1);
            let capacity = decoded.capacity() as u64;
            let needed_samples = (capacity as usize).saturating_mul(decoded_ch);

            if sample_buf.is_none()
                || sample_buf_ch != decoded_ch
                || sample_buf.as_ref().unwrap().capacity() < needed_samples
            {
                sample_buf = Some(SampleBuffer::<f32>::new(capacity, spec));
                sample_buf_ch = decoded_ch;
            }

            let sbuf = sample_buf.as_mut().unwrap();
            sbuf.copy_interleaved_ref(decoded);
            let raw_samples = sbuf.samples();
            if raw_samples.is_empty() {
                continue;
            }

            let samples: &[f32] = if decoded_ch == src_ch {
                raw_samples
            } else {
                Self::remix_channels(raw_samples, decoded_ch, src_ch, &mut remix_scratch);
                &remix_scratch
            };

            let mut written_samples = 0;
            while written_samples < samples.len() && !stop_flag.load(Ordering::Relaxed) {
                if seek_target_ms.load(Ordering::Relaxed) >= 0 {
                    break;
                }
                let frames_written = ring_buffer.write_interleaved(&samples[written_samples..]);
                written_samples += frames_written * src_ch;
                if frames_written == 0 {
                    let _ = ring_buffer.wait_for_space(256, Duration::from_millis(15));
                }
            }
        }
    }
}
