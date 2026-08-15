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

        # Pre-allocated zero-allocation DSP ramp buffers
        self._ramp_capacity = 8192
        self._ramp_buf = np.zeros((self._ramp_capacity, 1), dtype=np.float32)
        self._ramp_indices = np.arange(self._ramp_capacity, dtype=np.float32).reshape(-1, 1)

        self._lock = threading.Lock()

        # Dedicated asynchronous dispatcher for track end event (Zero GIL lock in audio callback)
        self._track_end_event = threading.Event()
        self._track_end_dispatcher = threading.Thread(target=self._track_end_worker, daemon=True, name="AudioTrackEndDispatcher")
        self._track_end_dispatcher.start()

    def _track_end_worker(self):
        while True:
            self._track_end_event.wait()
            self._track_end_event.clear()
            if self.on_track_end:
                try:
                    self.on_track_end()
                except Exception as e:
                    logger.error(f"Error executing on_track_end: {e}")

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
        self.stop_immediate(close_hardware=False)
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
            
            stream_to_recreate = False
            with self._lock:
                # If sample rate or channels changed, we MUST recreate the stream
                if self.stream is not None and (self._current_samplerate != sr or self._current_channels != ch or not getattr(self.stream, 'active', False)):
                    stream_to_recreate = True

                self.ring_buffer = ring_buffer
                self.decoder = decoder
                self.play_pos = 0
                self.total_frames = total_frames
                self.duration = self.total_frames / sr if sr else 0.0
                self._current_samplerate = sr
                self._current_channels = ch
                self._sd_dtype = 'float32'
                self._fade_in_remaining = 0
                self._fade_out_remaining = 0

            if stream_to_recreate:
                self.shutdown_hardware_stream()

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
        
        logger.info(f"Opening persistent WASAPI stream (mode={mode}, device={dev_id}, sr={sr}, dtype=float32)")

        if mode in ('exclusive', 'exclusive_push', 'exclusive_event'):
            wasapi_settings = sd.WasapiSettings(exclusive=True)
            try:
                if hasattr(sd, '_lib') and hasattr(sd._lib, 'paWinWasapiPolling'):
                    wasapi_settings._streaminfo.flags |= sd._lib.paWinWasapiPolling
            except Exception as e:
                logger.warning(f"Failed to set paWinWasapiPolling flag: {e}")
            latency_setting = 'low'
        else: # 'shared'
            try:
                wasapi_settings = sd.WasapiSettings(exclusive=False, auto_convert=True)
            except TypeError:
                wasapi_settings = sd.WasapiSettings(exclusive=False)
            
            try:
                if hasattr(sd, '_lib') and hasattr(sd._lib, 'paWinWasapiAutoConvert'):
                    wasapi_settings._streaminfo.flags |= sd._lib.paWinWasapiAutoConvert
            except Exception as e:
                logger.warning(f"Failed to set paWinWasapiAutoConvert flag: {e}")
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
            logger.warning(f"Failed to open audio stream (mode={mode}, sr={sr}): {e}. Attempting smart fallback...")
            
            # Step 1: If exclusive mode failed, fallback to WASAPI Shared Mode with AutoConvert
            if mode != 'shared':
                try:
                    try:
                        shared_settings = sd.WasapiSettings(exclusive=False, auto_convert=True)
                    except TypeError:
                        shared_settings = sd.WasapiSettings(exclusive=False)
                    try:
                        if hasattr(sd, '_lib') and hasattr(sd._lib, 'paWinWasapiAutoConvert'):
                            shared_settings._streaminfo.flags |= sd._lib.paWinWasapiAutoConvert
                    except Exception:
                        pass
                    
                    fallback_kwargs = {
                        'samplerate': sr,
                        'channels': ch,
                        'dtype': 'float32',
                        'latency': 'high',
                        'extra_settings': shared_settings,
                        'callback': self._audio_callback,
                    }
                    if dev_id is not None:
                        fallback_kwargs['device'] = dev_id
                        
                    self.stream = sd.OutputStream(**fallback_kwargs)
                    self.stream.start()
                    logger.info("Successfully opened audio stream via WASAPI Shared fallback.")
                    return
                except Exception as ex_shared:
                    logger.warning(f"WASAPI Shared fallback failed: {ex_shared}. Proceeding to generic audio fallback...")
            
            # Step 2: Universal Fallback - Standard PortAudio output stream without extra_settings (allows PortAudio software mixer & auto-resampler)
            try:
                generic_kwargs = {
                    'samplerate': sr,
                    'channels': ch,
                    'dtype': 'float32',
                    'latency': 'high',
                    'callback': self._audio_callback,
                }
                self.stream = sd.OutputStream(**generic_kwargs)
                self.stream.start()
                logger.info("Successfully opened audio stream via generic PortAudio fallback.")
            except Exception as final_e:
                logger.error(f"All audio stream initialization attempts failed: {final_e}")
                raise final_e

    def play(self):
        if self.state in (AudioState.PLAYING, AudioState.LOADING):
            return

        with self._lock:
            if self.stream is None or not getattr(self.stream, 'active', False):
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

    def stop(self, close_hardware: bool = False):
        if self.state in (AudioState.PLAYING, AudioState.PAUSED):
            with self._lock:
                fade_samples = int(self._current_samplerate * 0.015)
                self._fade_out_total = max(1, fade_samples)
                self._fade_out_remaining = self._fade_out_total
                self._target_state_after_fade = AudioState.STOPPED
                
            # Short wait for callback to render smooth fade-out
            threading.Event().wait(0.020)
            
        self.stop_immediate(close_hardware=close_hardware)

    def stop_immediate(self, close_hardware: bool = False):
        """Stop playback and optionally close the hardware stream.
        By default close_hardware=False keeps the active WASAPI stream alive
        feeding 0.0f to maintain 0V reference voltage on DAC and eliminate hiss."""
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
            
            if close_hardware and self.stream is not None:
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

    def shutdown_hardware_stream(self):
        """Close the PortAudio hardware output stream completely."""
        stream_to_close = None
        with self._lock:
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

    def seek(self, seconds: float):
        sr = self._current_samplerate
        total = self.total_frames
        frame = int(seconds * sr)
        target_pos = max(0, min(frame, total))
        
        # Perform decoder disk I/O seek outside engine lock to prevent audio callback stall
        decoder = self.decoder
        if decoder:
            decoder.seek(target_pos)

        with self._lock:
            self.play_pos = target_pos
            if self.ring_buffer:
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

    def _apply_linear_ramp(self, out_slice: np.ndarray, start_val: float, end_val: float, length: int):
        if length <= 0:
            return
        if self._ramp_capacity < length:
            self._ramp_capacity = max(length, self._ramp_capacity * 2)
            self._ramp_buf = np.zeros((self._ramp_capacity, 1), dtype=np.float32)
            self._ramp_indices = np.arange(self._ramp_capacity, dtype=np.float32).reshape(-1, 1)
            
        step = (end_val - start_val) / max(1, length - 1) if length > 1 else 0.0
        np.multiply(self._ramp_indices[:length], step, out=self._ramp_buf[:length])
        self._ramp_buf[:length] += start_val
        out_slice[:length] *= self._ramp_buf[:length]

    def _audio_callback(self, outdata, frames, time_info, status):
        if status:
            logger.debug(f"Audio callback status: {status}")

        try:
            with self._lock:
                # Handle Fade-Out phase when pausing/stopping manually
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
                    self._apply_linear_ramp(outdata, start_ratio, end_ratio, fade_len)

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
                is_eof = (self.decoder is not None and getattr(self.decoder, 'eof_reached', False) and self.ring_buffer.available() == 0)
                if remaining <= 0 or is_eof:
                    outdata.fill(0)
                    if self.state == AudioState.PLAYING:
                        self.state = AudioState.STOPPED
                        if self.on_track_end:
                            self._track_end_event.set()
                    return

                frames_to_copy = min(frames, remaining)
                read_frames = 0
                if frames_to_copy > 0:
                    read_frames = self.ring_buffer.read_into(outdata[:frames_to_copy])
                    self.play_pos += read_frames

                if read_frames < frames:
                    outdata[read_frames:].fill(0)

                # Tail Micro Fade-Out: If approaching the end of track, smooth out last 20ms to prevent DC cut-off pop
                tail_remaining = self.total_frames - self.play_pos
                tail_threshold = int(self._current_samplerate * 0.020)
                if read_frames > 0 and tail_remaining <= tail_threshold:
                    start_r = max(0.0, min(1.0, (tail_remaining + read_frames) / max(1, tail_threshold)))
                    end_r = max(0.0, min(1.0, tail_remaining / max(1, tail_threshold)))
                    self._apply_linear_ramp(outdata[:read_frames], start_r, end_r, read_frames)

                # Handle Micro Fade-In phase when starting/seeking
                if self._fade_in_remaining > 0 and read_frames > 0:
                    fade_len = min(read_frames, self._fade_in_remaining)
                    done = self._fade_in_total - self._fade_in_remaining
                    start_ratio = done / self._fade_in_total
                    end_ratio = (done + fade_len) / self._fade_in_total
                    self._apply_linear_ramp(outdata, start_ratio, end_ratio, fade_len)
                    self._fade_in_remaining -= fade_len

                if self.volume != 1.0:
                    outdata *= self.volume
        except Exception as e:
            logger.debug(f"Audio callback exception: {e}")
            outdata.fill(0)
