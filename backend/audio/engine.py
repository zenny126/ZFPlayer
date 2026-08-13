import enum
import logging
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from backend.storage.config import Config

# Default to WASAPI Shared Mode for stability
try:
    wasapi_info = next((api for api in sd.query_hostapis() if 'WASAPI' in api['name']), None)
    if wasapi_info and wasapi_info['default_output_device'] >= 0:
        sd.default.device = wasapi_info['default_output_device']
except Exception:
    pass # Fallback to default if WASAPI is not available

logger = logging.getLogger(__name__)

class AudioState(enum.Enum):
    IDLE = 1
    LOADING = 2
    PLAYING = 3
    PAUSED = 4
    STOPPED = 5

class AudioEngine:
    def __init__(self):
        self.state = AudioState.IDLE
        self.stream = None
        self.volume = 1.0
        self.on_track_end = None
        
        self.audio_data = None      # Full audio loaded into RAM (numpy float32 array)
        self.play_pos = 0          # Frame offset in audio_data
        self.total_frames = 0
        self.duration = 0.0
        self._current_samplerate = 44100
        self._current_channels = 2
        self._sd_dtype = 'float32'

        # Smooth anti-pop ramps (Micro Fade-In & Micro Fade-Out)
        self._fade_in_total = 0
        self._fade_in_remaining = 0
        self._fade_out_total = 0
        self._fade_out_remaining = 0
        self._target_state_after_fade = None
        self._lock = threading.Lock()

    def load(self, file_path: str):
        self.stop_immediate()
        self.state = AudioState.LOADING
        
        try:
            # Read ENTIRE file into RAM via libsndfile (C speed) as float32 normalized [-1.0, 1.0]
            sf_file = sf.SoundFile(file_path)
            sr = sf_file.samplerate
            ch = sf_file.channels
            
            raw_data = sf_file.read(dtype='float32', always_2d=True)
            sf_file.close()

            with self._lock:
                self.audio_data = raw_data
                self.play_pos = 0
                self.total_frames = raw_data.shape[0]
                self.duration = self.total_frames / sr if sr else 0.0
                
                samplerate_changed = (self._current_samplerate != sr or self._current_channels != ch)
                self._current_samplerate = sr
                self._current_channels = ch
                self._sd_dtype = 'float32'

                # Re-create stream only if audio format/channels changed
                if samplerate_changed and self.stream is not None:
                    try:
                        self.stream.stop()
                        self.stream.close()
                    except Exception:
                        pass
                    self.stream = None

            ram_mb = raw_data.nbytes / (1024 * 1024)
            logger.info(
                f"[RAM PLAYBACK] Loaded 100% to RAM: {file_path} | "
                f"{self.duration:.2f}s ({ram_mb:.1f} MB) | {sr}Hz / {ch}ch / float32"
            )
            self.state = AudioState.STOPPED
        except Exception as e:
            logger.error(f"Failed to load audio into RAM: {e}")
            self.state = AudioState.IDLE
            raise e

    def _create_stream(self):
        sr = self._current_samplerate
        ch = self._current_channels
        
        logger.info(f"Opening WASAPI Shared RAM stream (sr={sr}, dtype=float32)")
        self.stream = sd.OutputStream(
            samplerate=sr,
            channels=ch,
            dtype='float32',
            latency='high',  # Use 'high' latency to prevent crackling in Shared Mode
            callback=self._audio_callback,
        )
        self.stream.start()

    def play(self):
        if self.state in (AudioState.PLAYING, AudioState.LOADING):
            return

        with self._lock:
            if not self.stream:
                self._create_stream()
            elif not self.stream.active:
                self.stream.start()

            # Trigger 20ms micro fade-in ramp to eliminate start pops/clicks
            fade_samples = int(self._current_samplerate * 0.020)
            self._fade_in_total = max(1, fade_samples)
            self._fade_in_remaining = self._fade_in_total
            self._fade_out_remaining = 0
                
            self.state = AudioState.PLAYING

    def pause(self):
        if self.state == AudioState.PLAYING:
            with self._lock:
                fade_samples = int(self._current_samplerate * 0.015)
                self._fade_out_total = max(1, fade_samples)
                self._fade_out_remaining = self._fade_out_total
                self._target_state_after_fade = AudioState.PAUSED
                
            # Short wait for callback to render smooth fade-out
            threading.Event().wait(0.020)
            
            with self._lock:
                if self.state == AudioState.PAUSED and self.stream:
                    try:
                        self.stream.stop()
                    except Exception:
                        pass

    def resume(self):
        if self.state == AudioState.PAUSED:
            self.play()

    def stop(self):
        if self.state in (AudioState.PLAYING, AudioState.PAUSED):
            with self._lock:
                fade_samples = int(self._current_samplerate * 0.015)
                self._fade_out_total = max(1, fade_samples)
                self._fade_out_remaining = self._fade_out_total
                self._target_state_after_fade = AudioState.STOPPED
                
            # Short wait for callback to render smooth fade-out
            threading.Event().wait(0.020)
            
        self.stop_immediate()

    def stop_immediate(self):
        with self._lock:
            self.state = AudioState.STOPPED
            self._fade_in_remaining = 0
            self._fade_out_remaining = 0
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            self.play_pos = 0

    def seek(self, seconds: float):
        with self._lock:
            frame = int(seconds * self._current_samplerate)
            self.play_pos = max(0, min(frame, self.total_frames))
            # 15ms anti-pop micro ramp after seek
            fade_samples = int(self._current_samplerate * 0.015)
            self._fade_in_total = max(1, fade_samples)
            self._fade_in_remaining = self._fade_in_total

    def set_volume(self, level: float):
        self.volume = max(0.0, min(1.0, level))

    def get_state(self) -> dict:
        pos_sec = self.play_pos / self._current_samplerate if self._current_samplerate else 0.0
        return {
            'state': self.state.name,
            'position_seconds': pos_sec,
            'duration': self.duration,
            'volume': self.volume,
            'is_playing': self.state == AudioState.PLAYING
        }

    def _audio_callback(self, outdata, frames, time_info, status):
        if status:
            logger.debug(f"Audio callback status: {status}")

        with self._lock:
            # Handle Fade-Out phase when pausing/stopping
            if self._fade_out_remaining > 0:
                fade_len = min(frames, self._fade_out_remaining)
                remaining = self.total_frames - self.play_pos
                frames_to_copy = min(fade_len, max(0, remaining))

                if self.audio_data is not None and frames_to_copy > 0:
                    outdata[:frames_to_copy] = self.audio_data[self.play_pos : self.play_pos + frames_to_copy]
                    self.play_pos += frames_to_copy
                    if frames_to_copy < fade_len:
                        outdata[frames_to_copy:fade_len].fill(0)
                else:
                    outdata[:fade_len].fill(0)

                start_ratio = self._fade_out_remaining / self._fade_out_total
                end_ratio = max(0.0, (self._fade_out_remaining - fade_len) / self._fade_out_total)
                ramp = np.linspace(start_ratio, end_ratio, fade_len, dtype=np.float32).reshape(-1, 1)
                outdata[:fade_len] *= ramp

                if self.volume != 1.0:
                    outdata[:fade_len] *= self.volume

                if fade_len < frames:
                    outdata[fade_len:].fill(0)

                self._fade_out_remaining -= fade_len
                if self._fade_out_remaining <= 0:
                    self.state = self._target_state_after_fade or AudioState.STOPPED
                return

            if self.audio_data is None or self.state != AudioState.PLAYING:
                outdata.fill(0)
                return

            remaining = self.total_frames - self.play_pos
            if remaining <= 0:
                outdata.fill(0)
                if self.on_track_end:
                    threading.Thread(target=self.on_track_end, daemon=True).start()
                raise sd.CallbackStop()

            frames_to_copy = min(frames, remaining)
            outdata[:frames_to_copy] = self.audio_data[self.play_pos : self.play_pos + frames_to_copy]

            if frames_to_copy < frames:
                outdata[frames_to_copy:].fill(0)

            # Handle Micro Fade-In phase when starting/seeking
            if self._fade_in_remaining > 0:
                fade_len = min(frames_to_copy, self._fade_in_remaining)
                done = self._fade_in_total - self._fade_in_remaining
                start_ratio = done / self._fade_in_total
                end_ratio = (done + fade_len) / self._fade_in_total
                ramp = np.linspace(start_ratio, end_ratio, fade_len, dtype=np.float32).reshape(-1, 1)
                outdata[:fade_len] *= ramp
                self._fade_in_remaining -= fade_len

            if self.volume != 1.0:
                outdata *= self.volume

            self.play_pos += frames_to_copy

