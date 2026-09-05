import numpy as np
import pytest
from hypothesis import given, settings, strategies as st
from backend.audio.buffer import AudioRingBuffer


@given(
    capacity=st.integers(min_value=64, max_value=2048),
    channels=st.integers(min_value=1, max_value=2),
)
@settings(max_examples=50, deadline=None)
def test_audio_buffer_capacity_invariant(capacity: int, channels: int):
    """Invariant: At all times available + space == capacity."""
    buf = AudioRingBuffer(capacity_frames=capacity, channels=channels)
    assert buf.available() == 0
    assert buf.space() == capacity
    assert buf.available() + buf.space() == capacity


@given(
    capacity=st.integers(min_value=100, max_value=1000),
    write_sizes=st.lists(st.integers(min_value=1, max_value=200), min_size=1, max_size=10),
)
@settings(max_examples=40, deadline=None)
def test_audio_buffer_write_space_conservation(capacity: int, write_sizes: list[int]):
    """Invariant: Writing data consumes space monotonically up to capacity."""
    buf = AudioRingBuffer(capacity_frames=capacity, channels=2)
    total_written = 0

    for sz in write_sizes:
        data = np.full((sz, 2), float(sz), dtype=np.float32)
        written = buf.write(data)
        total_written += written
        assert buf.available() == total_written
        assert buf.space() == capacity - total_written
        assert buf.available() + buf.space() == capacity
        if buf.space() == 0:
            break


@given(
    capacity=st.integers(min_value=128, max_value=512),
    chunk_size=st.integers(min_value=10, max_value=50),
    iterations=st.integers(min_value=5, max_value=20),
)
@settings(max_examples=30, deadline=None)
def test_audio_buffer_circular_wraparound_exact_stream(capacity: int, chunk_size: int, iterations: int):
    """Invariant: Data read from circular buffer exactly matches data written in FIFO order."""
    buf = AudioRingBuffer(capacity_frames=capacity, channels=1)
    written_samples = []
    read_samples = []

    for i in range(iterations):
        start_val = i * chunk_size
        chunk = np.arange(start_val, start_val + chunk_size, dtype=np.float32).reshape(-1, 1)
        actual_written = buf.write(chunk)
        written_samples.extend(chunk[:actual_written].flatten())

        read_buf = np.zeros((chunk_size // 2, 1), dtype=np.float32)
        actual_read = buf.read_into(read_buf)
        read_samples.extend(read_buf[:actual_read].flatten())

    rem = np.zeros((buf.available(), 1), dtype=np.float32)
    actual_rem = buf.read_into(rem)
    read_samples.extend(rem[:actual_rem].flatten())

    np.testing.assert_array_equal(np.array(written_samples), np.array(read_samples))


@given(
    capacity=st.integers(min_value=50, max_value=500),
    read_size=st.integers(min_value=1, max_value=600),
)
@settings(max_examples=30, deadline=None)
def test_audio_buffer_empty_read_silence_fill(capacity: int, read_size: int):
    """Invariant: Reading from empty buffer returns 0 frames read and fills outdata with silence (0.0)."""
    buf = AudioRingBuffer(capacity_frames=capacity, channels=2)
    outdata = np.ones((read_size, 2), dtype=np.float32)

    frames_read = buf.read_into(outdata)

    assert frames_read == 0
    assert np.all(outdata == 0.0)


@given(
    capacity=st.integers(min_value=100, max_value=500),
    fill_size=st.integers(min_value=10, max_value=80),
)
@settings(max_examples=30, deadline=None)
def test_audio_buffer_clear_restores_initial_state(capacity: int, fill_size: int):
    """Invariant: Calling clear() resets available to 0 and space to capacity."""
    buf = AudioRingBuffer(capacity_frames=capacity, channels=2)
    buf.write(np.ones((fill_size, 2), dtype=np.float32))

    buf.clear()

    assert buf.available() == 0
    assert buf.space() == capacity
    assert buf.write_idx == 0
    assert buf.read_idx == 0
