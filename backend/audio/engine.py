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
        
        self.audio_data = None      # Full audio loaded into RAM (numpy array)
        self.play_pos = 0          # Frame offset in audio_data
        self.total_frames = 0
        self.duration = 0.0
        self._current_samplerate = 44100
        self._current_channels = 2
        self._sd_dtype = 'int32'

    def load(self, file_path: str):
        self.stop()
        self.state = AudioState.LOADING
        
        try:
            # Read ENTIRE file into RAM via libsndfile (C speed)
            sf_file = sf.SoundFile(file_path)
            sr = sf_file.samplerate
            ch = sf_file.channels
            subtype = sf_file.subtype
            
            # Read as native integers or float
            if 'PCM_24' in subtype or 'PCM_32' in subtype:
                raw_data = sf_file.read(dtype='int32')
                if 'PCM_24' in subtype:
                    raw_data = raw_data << 8
            elif 'FLOAT' in subtype or 'DOUBLE' in subtype:
                raw_data = sf_file.read(dtype='float32')
            else: # PCM_16 or default
                raw_data = sf_file.read(dtype='int16')
                raw_data = (raw_data.astype(np.int32)) << 16

            sf_file.close()

            if len(raw_data.shape) == 1:
                raw_data = raw_data.reshape(-1, 1)

            self.audio_data = raw_data
            self.play_pos = 0
            self.total_frames = raw_data.shape[0]
            self.duration = self.total_frames / sr if sr else 0.0
            
            self._current_samplerate = sr
            self._current_channels = ch
            self._sd_dtype = 'float32' if raw_data.dtype == np.float32 else 'int32'

            ram_mb = raw_data.nbytes / (1024 * 1024)
            logger.info(
                f"[RAM PLAYBACK] Loaded 100% to RAM: {file_path} | "
                f"{self.duration:.2f}s ({ram_mb:.1f} MB) | {sr}Hz / {ch}ch / {self._sd_dtype}"
            )
            self.state = AudioState.STOPPED
        except Exception as e:
            logger.error(f"Failed to load audio into RAM: {e}")
            self.state = AudioState.IDLE
            raise e

    def _create_stream(self):
        sr = self._current_samplerate
        ch = self._current_channels
        
        logger.info(f"Opening WASAPI Shared RAM stream (sr={sr}, dtype={self._sd_dtype})")
        self.stream = sd.OutputStream(
            samplerate=sr,
            channels=ch,
            dtype=self._sd_dtype,
            latency='high',  # Use 'high' latency to prevent crackling in Shared Mode
            callback=self._audio_callback,
        )
        self.stream.start()

    def play(self):
        if self.state in (AudioState.PLAYING, AudioState.IDLE, AudioState.LOADING):
            return

        if not self.stream:
            self._create_stream()
            
        self.state = AudioState.PLAYING

    def pause(self):
        if self.state == AudioState.PLAYING:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            self.state = AudioState.PAUSED

    def resume(self):
        if self.state == AudioState.PAUSED:
            self.play()

    def stop(self):
        self.state = AudioState.STOPPED
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.play_pos = 0

    def seek(self, seconds: float):
        frame = int(seconds * self._current_samplerate)
        self.play_pos = max(0, min(frame, self.total_frames))

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

        if self.audio_data is None or self.state != AudioState.PLAYING:
            outdata.fill(0)
            return

        remaining = self.total_frames - self.play_pos
        if remaining <= 0:
            outdata.fill(0)
            if self.on_track_end:
                threading.Thread(target=self.on_track_end).start()
            raise sd.CallbackStop()

        frames_to_copy = min(frames, remaining)
        outdata[:frames_to_copy] = self.audio_data[self.play_pos : self.play_pos + frames_to_copy]

        if frames_to_copy < frames:
            outdata[frames_to_copy:].fill(0)

        if self.volume != 1.0:
            np.multiply(outdata, self.volume, out=outdata, casting='unsafe')

        self.play_pos += frames_to_copy
