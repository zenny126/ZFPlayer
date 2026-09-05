import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from backend.audio.engine import AudioEngine, AudioState
from backend.audio.buffer import AudioRingBuffer


def test_engine_initial_state():
    """Verify AudioEngine initializes with default state and parameters."""
    with patch("sounddevice.query_hostapis", return_value=[]):
        engine = AudioEngine()
        assert engine.state == AudioState.IDLE
        assert engine.volume == 1.0
        assert engine.play_pos == 0
        assert engine.duration == 0.0
        assert engine.ring_buffer is None


def test_engine_volume_clamping():
    """Verify AudioEngine clamps volume accurately within [0.0, 1.0]."""
    with patch("sounddevice.query_hostapis", return_value=[]):
        engine = AudioEngine()
        engine.set_volume(0.65)
        assert engine.volume == 0.65

        engine.set_volume(-0.5)
        assert engine.volume == 0.0

        engine.set_volume(1.8)
        assert engine.volume == 1.0


def test_engine_audio_mode_switch():
    """Verify AudioEngine switches between shared and exclusive modes cleanly."""
    with patch("sounddevice.query_hostapis", return_value=[]):
        engine = AudioEngine()
        mode1 = engine.set_audio_mode("exclusive")
        assert mode1 == "exclusive"
        assert engine.audio_mode == "exclusive"

        mode2 = engine.set_audio_mode("shared")
        assert mode2 == "shared"
        assert engine.audio_mode == "shared"


def test_engine_linear_ramp_dsp():
    """Verify AudioEngine._apply_linear_ramp smoothly attenuates audio samples."""
    with patch("sounddevice.query_hostapis", return_value=[]):
        engine = AudioEngine()
        outdata = np.ones((100, 2), dtype=np.float32)
        engine._apply_linear_ramp(outdata, 0.0, 1.0, 100)

        assert outdata[0, 0] < 0.05
        assert outdata[99, 0] > 0.95
        assert np.all(outdata[:, 0] == outdata[:, 1])


def test_engine_seek_position_calculation():
    """Verify AudioEngine seek computes accurate frame positions."""
    with patch("sounddevice.query_hostapis", return_value=[]):
        engine = AudioEngine()
        engine._current_samplerate = 44100
        engine.total_frames = 44100 * 10  # 10 seconds total

        engine.seek(4.5)
        assert engine.play_pos == int(4.5 * 44100)
        assert engine._fade_in_remaining > 0  # Anti-pop ramp armed


def test_engine_get_state_format():
    """Verify AudioEngine get_state returns expected structure and accurate timing."""
    with patch("sounddevice.query_hostapis", return_value=[]):
        engine = AudioEngine()
        engine._current_samplerate = 48000
        engine.total_frames = 48000 * 5
        engine.duration = 5.0
        engine.play_pos = 48000 * 2  # 2.0s mark

        state = engine.get_state()
        assert state["state"] == "IDLE"
        assert state["position_seconds"] == 2.0
        assert state["duration"] == 5.0
        assert state["volume"] == 1.0


def test_engine_track_end_worker_event():
    """Verify AudioEngine asynchronously notifies on_track_end callback."""
    with patch("sounddevice.query_hostapis", return_value=[]):
        engine = AudioEngine()
        mock_cb = MagicMock()
        engine.on_track_end = mock_cb

        engine._track_end_event.set()
        time.sleep(0.05)
        mock_cb.assert_called_once()


def test_engine_stop_immediate_clears_buffer():
    """Verify AudioEngine.stop_immediate resets position and purges ring buffer."""
    with patch("sounddevice.query_hostapis", return_value=[]):
        engine = AudioEngine()
        ring_buf = AudioRingBuffer(capacity_frames=4096, channels=2)
        ring_buf.write(np.ones((512, 2), dtype=np.float32))

        engine.ring_buffer = ring_buf
        engine.play_pos = 1000
        engine.stop_immediate(close_hardware=False)

        assert engine.state == AudioState.STOPPED
        assert engine.ring_buffer is None
