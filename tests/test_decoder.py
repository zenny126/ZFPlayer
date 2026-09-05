import os
import time
import pytest
import soundfile as sf
import numpy as np
from backend.audio.buffer import AudioRingBuffer
from backend.audio.decoder import StreamingDecoder


def _generate_test_wav(file_path: str, duration_sec: float = 1.0, samplerate: int = 44100):
    """Synthesize a standard 16-bit PCM stereo WAV file for testing."""
    total_samples = int(samplerate * duration_sec)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False, dtype=np.float32)
    left = 0.5 * np.sin(2 * np.pi * 440 * t)
    right = 0.5 * np.cos(2 * np.pi * 440 * t)
    stereo = np.column_stack((left, right))
    sf.write(file_path, stereo, samplerate, subtype="PCM_16")


def test_decoder_load_and_metadata(temp_dir):
    """Verify StreamingDecoder loads file and extracts accurate audio format metadata."""
    wav_path = os.path.join(temp_dir, "test_tone.wav")
    _generate_test_wav(wav_path, duration_sec=1.5, samplerate=44100)

    ring_buf = AudioRingBuffer(capacity_frames=16384, channels=2)
    decoder = StreamingDecoder(ring_buffer=ring_buf)

    decoder.load(wav_path)
    info = decoder.get_info()

    assert info["samplerate"] == 44100
    assert info["channels"] == 2
    assert info["bit_depth"] == 16
    assert abs(info["duration"] - 1.5) < 0.05
    assert info["total_frames"] == int(44100 * 1.5)

    decoder.stop()


def test_decoder_streaming_decode_into_ring_buffer(temp_dir):
    """Verify StreamingDecoder streams decoded audio frames into the ring buffer."""
    wav_path = os.path.join(temp_dir, "test_stream.wav")
    _generate_test_wav(wav_path, duration_sec=1.0, samplerate=44100)

    ring_buf = AudioRingBuffer(capacity_frames=32768, channels=2)
    decoder = StreamingDecoder(ring_buffer=ring_buf)

    decoder.load(wav_path)
    decoder.start()

    # Wait for decoder thread to decode into ring buffer
    for _ in range(50):
        if ring_buf.available() > 4096:
            break
        time.sleep(0.02)

    assert ring_buf.available() > 0
    read_buf = np.zeros((2048, 2), dtype=np.float32)
    frames_read = ring_buf.read_into(read_buf)
    assert frames_read == 2048
    assert not np.all(read_buf == 0)

    decoder.stop()
    assert decoder.thread is None or not decoder.thread.is_alive()


def test_decoder_seek_operation(temp_dir):
    """Verify StreamingDecoder seeking updates file pointer accurately."""
    wav_path = os.path.join(temp_dir, "test_seek.wav")
    _generate_test_wav(wav_path, duration_sec=2.0, samplerate=44100)

    ring_buf = AudioRingBuffer(capacity_frames=16384, channels=2)
    decoder = StreamingDecoder(ring_buffer=ring_buf)

    decoder.load(wav_path)
    assert decoder.get_position() == 0

    target_frame = 44100  # 1.0 second mark
    decoder.seek(target_frame)
    assert decoder.get_position() == target_frame

    decoder.stop()
