import threading
import logging
import soundfile as sf
import time
import numpy as np
from backend.audio.buffer import AudioRingBuffer

logger = logging.getLogger(__name__)

# All subtypes read as float32 to support volume and fade DSP
_SUBTYPE_MAP = {
    'PCM_16': {'dtype': 'float32', 'bit_depth': 16},
    'PCM_24': {'dtype': 'float32', 'bit_depth': 24},
    'PCM_32': {'dtype': 'float32', 'bit_depth': 32},
    'FLOAT':  {'dtype': 'float32', 'bit_depth': 32},
    'DOUBLE': {'dtype': 'float32', 'bit_depth': 64},
    'PCM_U8': {'dtype': 'float32', 'bit_depth': 8},
    'PCM_S8': {'dtype': 'float32', 'bit_depth': 8},
}

class StreamingDecoder:
    def __init__(self, ring_buffer: AudioRingBuffer):
        self.ring_buffer = ring_buffer
        self.file_path = None
        self.sf_file = None
        self.thread = None
        self.stop_event = threading.Event()
        self.info = {}
        self.eof_reached = False
        self.chunk_size = 4096
        self.lock = threading.Lock()

    def load(self, file_path: str):
        with self.lock:
            self.file_path = file_path
            if self.sf_file:
                self.sf_file.close()
            self.sf_file = sf.SoundFile(file_path)
            
            subtype = self.sf_file.subtype
            fmt = _SUBTYPE_MAP.get(subtype, {'dtype': 'float32', 'bit_depth': 16})
            self._read_dtype = fmt['dtype']
            
            self.info = {
                'samplerate': self.sf_file.samplerate,
                'channels': self.sf_file.channels,
                'duration': len(self.sf_file) / self.sf_file.samplerate if self.sf_file.samplerate else 0,
                'total_frames': len(self.sf_file),
                'subtype': subtype,
                'bit_depth': fmt['bit_depth'],
                'read_dtype': self._read_dtype,
                'out_dtype': 'float32',
            }
            self.eof_reached = False
            
            logger.info(
                f"Loaded: {file_path} | "
                f"{self.sf_file.samplerate}Hz / {fmt['bit_depth']}bit / "
                f"{self.sf_file.channels}ch / {subtype} → read as {self._read_dtype}"
            )

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._decode_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join()
        with self.lock:
            if self.sf_file:
                self.sf_file.close()
                self.sf_file = None

    def seek(self, frame: int):
        with self.lock:
            if self.sf_file:
                self.sf_file.seek(frame)
                self.eof_reached = False

    def get_position(self) -> int:
        with self.lock:
            if self.sf_file:
                return self.sf_file.tell()
            return 0

    def get_info(self) -> dict:
        return self.info

    def _decode_loop(self):
        while not self.stop_event.is_set():
            needs_sleep = False
            with self.lock:
                if not self.sf_file or self.eof_reached:
                    needs_sleep = True
            
            if needs_sleep:
                time.sleep(0.01)
                continue

            space = self.ring_buffer.space()
            if space < self.chunk_size:
                time.sleep(0.005)
                continue

            frames_to_read = min(self.chunk_size, space)
            
            with self.lock:
                if not self.sf_file or self.eof_reached:
                    continue
                try:
                    data = self.sf_file.read(frames_to_read, dtype=self._read_dtype)
                except Exception:
                    data = []
            
            if len(data) == 0:
                with self.lock:
                    self.eof_reached = True
                continue
                
            if len(data.shape) == 1:
                data = data.reshape(-1, 1)

            # (Removed int32 MSB alignment as engine needs float32 for DSP)

            written = 0
            while written < len(data) and not self.stop_event.is_set():
                w = self.ring_buffer.write(data[written:])
                written += w
                if w == 0:
                    time.sleep(0.001)
