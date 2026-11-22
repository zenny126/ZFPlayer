use std::sync::{Condvar, Mutex};
use std::time::Duration;

struct RingState {
    buffer: Vec<f32>,
    capacity_frames: usize,
    channels: usize,
    write_frame: usize,
    read_frame: usize,
    size_frames: usize,
}

/// Zero-allocation interleaved `f32` ring buffer synchronized with Condition Variable.
pub struct AudioRingBuffer {
    state: Mutex<RingState>,
    has_space_cond: Condvar,
}

impl AudioRingBuffer {
    pub fn new(capacity_frames: usize, channels: usize) -> Self {
        let ch = channels.max(1);
        let cap = capacity_frames.max(1024);
        Self {
            state: Mutex::new(RingState {
                buffer: vec![0.0f32; cap * ch],
                capacity_frames: cap,
                channels: ch,
                write_frame: 0,
                read_frame: 0,
                size_frames: 0,
            }),
            has_space_cond: Condvar::new(),
        }
    }

    /// Write interleaved f32 samples into the ring buffer. Returns number of frames written.
    pub fn write_interleaved(&self, data: &[f32]) -> usize {
        let Ok(mut st) = self.state.lock() else {
            return 0;
        };
        let ch = st.channels;
        let frames_to_write = data.len() / ch;
        let space_left = st.capacity_frames.saturating_sub(st.size_frames);
        if space_left == 0 || frames_to_write == 0 {
            return 0;
        }

        let frames_written = frames_to_write.min(space_left);
        let end_frame = st.write_frame + frames_written;
        let cap = st.capacity_frames;
        let w_idx = st.write_frame;

        if end_frame <= cap {
            let dst_start = w_idx * ch;
            let dst_end = end_frame * ch;
            st.buffer[dst_start..dst_end].copy_from_slice(&data[0..(frames_written * ch)]);
        } else {
            let part1_frames = cap - w_idx;
            let part2_frames = frames_written - part1_frames;
            let dst1_start = w_idx * ch;
            let dst1_end = cap * ch;
            st.buffer[dst1_start..dst1_end].copy_from_slice(&data[0..(part1_frames * ch)]);
            st.buffer[0..(part2_frames * ch)]
                .copy_from_slice(&data[(part1_frames * ch)..(frames_written * ch)]);
        }

        st.write_frame = (w_idx + frames_written) % cap;
        st.size_frames += frames_written;
        frames_written
    }

    /// Read interleaved f32 frames into `out`. Fills any remaining slice with 0.0.
    /// Returns number of frames actually read from the buffer.
    pub fn read_into(&self, out: &mut [f32], channels: usize) -> usize {
        let ch = channels.max(1);
        let requested_frames = out.len() / ch;
        let Ok(mut st) = self.state.lock() else {
            out.fill(0.0);
            return 0;
        };

        if st.channels != ch || st.size_frames == 0 || requested_frames == 0 {
            out.fill(0.0);
            return 0;
        }

        let frames_to_read = requested_frames.min(st.size_frames);
        let cap = st.capacity_frames;
        let r_idx = st.read_frame;
        let end_frame = r_idx + frames_to_read;

        if end_frame <= cap {
            let src_start = r_idx * ch;
            let src_end = end_frame * ch;
            out[0..(frames_to_read * ch)].copy_from_slice(&st.buffer[src_start..src_end]);
        } else {
            let part1_frames = cap - r_idx;
            let part2_frames = frames_to_read - part1_frames;
            let src1_start = r_idx * ch;
            let src1_end = cap * ch;
            out[0..(part1_frames * ch)].copy_from_slice(&st.buffer[src1_start..src1_end]);
            out[(part1_frames * ch)..(frames_to_read * ch)]
                .copy_from_slice(&st.buffer[0..(part2_frames * ch)]);
        }

        st.read_frame = (r_idx + frames_to_read) % cap;
        st.size_frames -= frames_to_read;

        if frames_to_read < requested_frames {
            out[(frames_to_read * ch)..].fill(0.0);
        }

        self.has_space_cond.notify_all();
        frames_to_read
    }

    pub fn wait_for_space(&self, min_space_frames: usize, timeout: Duration) -> bool {
        let Ok(guard) = self.state.lock() else {
            return false;
        };
        if guard.capacity_frames.saturating_sub(guard.size_frames) >= min_space_frames {
            return true;
        }
        let Ok((guard2, _)) = self.has_space_cond.wait_timeout(guard, timeout) else {
            return false;
        };
        guard2.capacity_frames.saturating_sub(guard2.size_frames) >= min_space_frames
    }

    pub fn wake_up(&self) {
        self.has_space_cond.notify_all();
    }

    pub fn available_frames(&self) -> usize {
        self.state.lock().map(|s| s.size_frames).unwrap_or(0)
    }

    #[cfg_attr(not(test), allow(dead_code))]
    pub fn space_frames(&self) -> usize {
        self.state
            .lock()
            .map(|s| s.capacity_frames.saturating_sub(s.size_frames))
            .unwrap_or(0)
    }

    pub fn clear(&self) {
        if let Ok(mut st) = self.state.lock() {
            st.write_frame = 0;
            st.read_frame = 0;
            st.size_frames = 0;
        }
        self.has_space_cond.notify_all();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn write_read_and_wraparound() {
        let rb = AudioRingBuffer::new(1024, 2);
        assert_eq!(rb.available_frames(), 0);
        assert_eq!(rb.space_frames(), 1024);

        let chunk1: Vec<f32> = (0..1600).map(|i| i as f32).collect(); // 800 frames * 2ch
        let written1 = rb.write_interleaved(&chunk1);
        assert_eq!(written1, 800);
        assert_eq!(rb.available_frames(), 800);
        assert_eq!(rb.space_frames(), 224);

        let mut out1 = vec![0.0f32; 1200]; // 600 frames
        let read1 = rb.read_into(&mut out1, 2);
        assert_eq!(read1, 600);
        assert_eq!(&out1[..10], &chunk1[..10]);
        assert_eq!(rb.available_frames(), 200);

        // Next write wraps around capacity 1024
        let chunk2: Vec<f32> = (0..1400).map(|i| (i + 5000) as f32).collect(); // 700 frames
        let written2 = rb.write_interleaved(&chunk2);
        assert_eq!(written2, 700);
        assert_eq!(rb.available_frames(), 900);

        // Read all 900 frames + 100 trailing zero-padded frames
        let mut out2 = vec![-1.0f32; 2000];
        let read2 = rb.read_into(&mut out2, 2);
        assert_eq!(read2, 900);
        // First 200 frames come from tail of chunk1
        assert_eq!(out2[0], chunk1[1200]);
        assert_eq!(out2[399], chunk1[1599]);
        // Next 700 frames come from chunk2
        assert_eq!(out2[400], chunk2[0]);
        assert_eq!(out2[1799], chunk2[1399]);
        // Remaining 100 frames must be zero-padded
        assert!(out2[1800..].iter().all(|&s| s == 0.0));
    }

    #[test]
    fn channel_mismatch_and_clear() {
        let rb = AudioRingBuffer::new(1024, 2);
        let written = rb.write_interleaved(&[0.5, -0.5, 0.25, -0.25]);
        assert_eq!(written, 2);

        // Channel mismatch fills output with zeros without consuming frames
        let mut mono_out = vec![9.0f32; 4];
        assert_eq!(rb.read_into(&mut mono_out, 1), 0);
        assert!(mono_out.iter().all(|&s| s == 0.0));
        assert_eq!(rb.available_frames(), 2);

        rb.clear();
        assert_eq!(rb.available_frames(), 0);
        assert_eq!(rb.space_frames(), 1024);
    }
}
