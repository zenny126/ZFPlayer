import enum
import logging
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from backend.storage.config import Config
from backend.audio.buffer import AudioRingBuffer
from backend.audio.decoder import StreamingDecoder

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
        self.audio_mode = Config().get('audio_mode', 'shared')
        
        self.ring_buffer = None     # Replaces audio_data
        self.decoder = None         # Streaming decoder instance
        self.play_pos = 0          # Frame offset
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

    def _get_wasapi_device_id(self):
        try:
            wasapi_info = next((api for api in sd.query_hostapis() if 'WASAPI' in api['name']), None)
            if wasapi_info and wasapi_info.get('default_output_device', -1) >= 0:
                return wasapi_info['default_output_device']
        except Exception as e:
            logger.warning(f"Error querying WASAPI output device: {e}")
        return None

    def set_audio_mode(self, mode: str) -> str:
        if mode in ('exclusive_push', 'exclusive'):
            mode = 'exclusive'
        elif mode != 'shared':
            mode = 'shared'
            
        stream_to_close = None
        with self._lock:
            if getattr(self, 'audio_mode', 'shared') == mode:
                return mode
                
            logger.info(f"Changing WASAPI audio mode from '{getattr(self, 'audio_mode', 'shared')}' to '{mode}'")
            self.audio_mode = mode
            Config().set('audio_mode', mode)

            is_playing = (self.state == AudioState.PLAYING)
            if self.stream is not None:
                stream_to_close = self.stream
                self.stream = None

        if stream_to_close is not None:
            try:
                if stream_to_close.active:
                    stream_to_close.stop()
                stream_to_close.close()
            except Exception:
                pass

        if is_playing:
            with self._lock:
                self._create_stream()
                fade_samples = int(self._current_samplerate * 0.020)
                self._fade_in_total = max(1, fade_samples)
                self._fade_in_remaining = self._fade_in_total
                self._fade_out_remaining = 0

        return mode

    def load(self, file_path: str):
        self.stop_immediate()
        self.state = AudioState.LOADING
        
        try:
            # Just read metadata
            sf_file = sf.SoundFile(file_path)
            sr = sf_file.samplerate
            ch = sf_file.channels
            total_frames = len(sf_file)
            sf_file.close()

            # Create ring buffer for 2 seconds of audio
            capacity = int(sr * 2.0)
            ring_buffer = AudioRingBuffer(capacity, ch, dtype=np.float32)
            decoder = StreamingDecoder(ring_buffer)
            decoder.load(file_path)
            
            with self._lock:
                self.ring_buffer = ring_buffer
                self.decoder = decoder
                self.play_pos = 0
                self.total_frames = total_frames
                self.duration = self.total_frames / sr if sr else 0.0
                self._current_samplerate = sr
                self._current_channels = ch
                self._sd_dtype = 'float32'

            self.decoder.start()
            logger.info(
                f"[STREAM PLAYBACK] Loaded via StreamingDecoder: {file_path} | "
                f"{self.duration:.2f}s | {sr}Hz / {ch}ch / float32"
            )
            self.state = AudioState.STOPPED
        except Exception as e:
            logger.error(f"Failed to load audio for streaming: {e}")
            self.state = AudioState.IDLE
            raise e

    def _create_stream(self):
        sr = self._current_samplerate
        ch = self._current_channels
        mode = getattr(self, 'audio_mode', 'shared')
        dev_id = self._get_wasapi_device_id()
        
        logger.info(f"Opening WASAPI stream (mode={mode}, device={dev_id}, sr={sr}, dtype=float32)")

        if mode in ('exclusive', 'exclusive_push', 'exclusive_event'):
            wasapi_settings = sd.WasapiSettings(exclusive=True)
            try:
                wasapi_settings._streaminfo.flags |= sd._lib.paWinWasapiPolling
            except Exception as e:
                logger.warning(f"Failed to set paWinWasapiPolling flag: {e}")
            latency_setting = 'low'
        else: # 'shared'
            wasapi_settings = sd.WasapiSettings(exclusive=False)
            latency_setting = 'high'

        try:
            kwargs = {
                'samplerate': sr,
                'channels': ch,
                'dtype': 'float32',
                'latency': latency_setting,
                'extra_settings': wasapi_settings,
                'callback': self._audio_callback,
            }
            if dev_id is not None:
                kwargs['device'] = dev_id

            self.stream = sd.OutputStream(**kwargs)
            self.stream.start()
        except Exception as e:
            if mode != 'shared':
                logger.warning(f"Failed to open WASAPI mode '{mode}' ({e}). Falling back to WASAPI Shared Mode.")
                wasapi_settings = sd.WasapiSettings(exclusive=False)
                kwargs['latency'] = 'high'
                kwargs['extra_settings'] = wasapi_settings
                self.stream = sd.OutputStream(**kwargs)
                self.stream.start()
            else:
                raise e

    def play(self):
        if self.state in (AudioState.PLAYING, AudioState.LOADING):
            return

        with self._lock:
            # Always create a fresh stream — WASAPI Exclusive Push
            # cannot reliably restart a stopped stream.
            self._create_stream()

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
                if self.state == AudioState.PAUSED:
                    self.state = AudioState.PAUSED

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
        """Stop playback and close the hardware stream.
        Stream close and decoder stop are done OUTSIDE self._lock
        to prevent deadlock with PortAudio callback thread."""
        stream_to_close = None
        decoder_to_stop = None
        with self._lock:
            self.state = AudioState.STOPPED
            self._fade_in_remaining = 0
            self._fade_out_remaining = 0
            
            if self.decoder:
                decoder_to_stop = self.decoder
                self.decoder = None
            if self.ring_buffer:
                self.ring_buffer.clear()
                self.ring_buffer = None
            
            if self.stream is not None:
                stream_to_close = self.stream
                self.stream = None

        if decoder_to_stop is not None:
            decoder_to_stop.stop()

        if stream_to_close is not None:
            try:
                if stream_to_close.active:
                    stream_to_close.stop()
                stream_to_close.close()
            except Exception:
                pass

    def seek(self, seconds: float):
        with self._lock:
            frame = int(seconds * self._current_samplerate)
            self.play_pos = max(0, min(frame, self.total_frames))
            
            if self.decoder:
                self.decoder.seek(self.play_pos)
                self.ring_buffer.clear()

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
            'is_playing': self.state == AudioState.PLAYING,
            'audio_mode': getattr(self, 'audio_mode', 'shared')
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

                if self.ring_buffer is not None and frames_to_copy > 0:
                    read_frames = self.ring_buffer.read_into(outdata[:frames_to_copy])
                    self.play_pos += read_frames
                    if read_frames < fade_len:
                        outdata[read_frames:fade_len].fill(0)
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

            if self.ring_buffer is None or self.state != AudioState.PLAYING:
                outdata.fill(0)
                return

            remaining = self.total_frames - self.play_pos
            if remaining <= 0:
                outdata.fill(0)
                self.state = AudioState.STOPPED
                if self.on_track_end:
                    threading.Thread(target=self.on_track_end, daemon=True).start()
                return

            frames_to_copy = min(frames, remaining)
            read_frames = 0
            if frames_to_copy > 0:
                read_frames = self.ring_buffer.read_into(outdata[:frames_to_copy])
                self.play_pos += read_frames

            if read_frames < frames:
                outdata[read_frames:].fill(0)

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
