import threading
import time
import numpy as np
import pytest
from backend.audio.buffer import AudioRingBuffer


def test_ring_buffer_initialization():
    """Verify AudioRingBuffer initializes with correct capacity, channels, and zero state."""
    buf = AudioRingBuffer(capacity_frames=1024, channels=2)
    assert buf.capacity == 1024
    assert buf.channels == 2
    assert buf.available() == 0
    assert buf.space() == 1024


def test_ring_buffer_write_and_read():
    """Verify linear write and read operations maintain audio data fidelity."""
    buf = AudioRingBuffer(capacity_frames=512, channels=2)
    
    # Create test signal: 100 frames
    test_data = np.arange(200, dtype=np.float32).reshape(100, 2)
    written = buf.write(test_data)
    assert written == 100
    assert buf.available() == 100
    assert buf.space() == 412

    # Read back 100 frames
    out = np.zeros((100, 2), dtype=np.float32)
    read_count = buf.read_into(out)
    assert read_count == 100
    assert buf.available() == 0
    assert np.array_equal(out, test_data)


def test_ring_buffer_wraparound():
    """Verify circular wrap-around across the end boundary of the internal numpy array."""
    capacity = 100
    buf = AudioRingBuffer(capacity_frames=capacity, channels=2)

    # 1. Fill 80 frames
    chunk1 = np.full((80, 2), 1.0, dtype=np.float32)
    buf.write(chunk1)
    
    # 2. Read 60 frames -> read_idx advances to 60, size is 20
    out1 = np.zeros((60, 2), dtype=np.float32)
    buf.read_into(out1)
    assert buf.available() == 20
    assert buf.space() == 80

    # 3. Write 50 frames -> write_idx is at 80, so 20 frames go to [80:100] and 30 frames wrap to [0:30]
    chunk2 = np.full((50, 2), 2.0, dtype=np.float32)
    written = buf.write(chunk2)
    assert written == 50
    assert buf.available() == 70

    # 4. Read all 70 frames -> read_idx spans [60:100] and [0:30]
    out2 = np.zeros((70, 2), dtype=np.float32)
    read_count = buf.read_into(out2)
    assert read_count == 70
    assert buf.available() == 0

    # First 20 frames must be 1.0, remaining 50 frames must be 2.0
    assert np.all(out2[:20] == 1.0)
    assert np.all(out2[20:] == 2.0)


def test_ring_buffer_overflow_protection():
    """Verify buffer caps writes at available capacity without throwing or corrupting memory."""
    buf = AudioRingBuffer(capacity_frames=50, channels=2)
    
    data = np.ones((80, 2), dtype=np.float32)
    written = buf.write(data)
    
    assert written == 50
    assert buf.available() == 50
    assert buf.space() == 0
    
    # Attempting to write when full returns 0
    second_write = buf.write(data)
    assert second_write == 0


def test_ring_buffer_underrun_zero_fill():
    """Verify reading when insufficient data zero-fills the remainder of outdata (preventing audio pops)."""
    buf = AudioRingBuffer(capacity_frames=100, channels=2)
    
    # Write only 30 frames
    data = np.full((30, 2), 5.0, dtype=np.float32)
    buf.write(data)
    
    # Request 50 frames
    out = np.full((50, 2), -1.0, dtype=np.float32)
    read_count = buf.read_into(out)
    
    assert read_count == 30
    assert buf.available() == 0
    # First 30 frames are valid data
    assert np.all(out[:30] == 5.0)
    # Remaining 20 frames are zero-filled
    assert np.all(out[30:] == 0.0)


def test_ring_buffer_clear():
    """Verify clear resets read/write pointers, size and notifies waiting producers."""
    buf = AudioRingBuffer(capacity_frames=100, channels=2)
    buf.write(np.ones((50, 2), dtype=np.float32))
    assert buf.available() == 50
    
    buf.clear()
    assert buf.available() == 0
    assert buf.space() == 100


def test_ring_buffer_concurrent_producer_consumer():
    """Verify thread-safety and data continuity under concurrent multi-threaded streaming."""
    total_frames = 20000
    chunk_size = 512
    buf = AudioRingBuffer(capacity_frames=2048, channels=2)
    
    source_audio = np.random.randn(total_frames, 2).astype(np.float32)
    received_audio = np.zeros((total_frames, 2), dtype=np.float32)
    
    def producer():
        written_total = 0
        while written_total < total_frames:
            frames_to_send = min(chunk_size, total_frames - written_total)
            chunk = source_audio[written_total:written_total + frames_to_send]
            
            # Wait for space if full
            while not buf.wait_for_space(min_space=frames_to_send, timeout=0.01):
                pass
                
            w = buf.write(chunk)
            written_total += w

    def consumer():
        read_total = 0
        temp_out = np.zeros((chunk_size, 2), dtype=np.float32)
        while read_total < total_frames:
            frames_to_read = min(chunk_size, total_frames - read_total)
            r = buf.read_into(temp_out[:frames_to_read])
            if r > 0:
                received_audio[read_total:read_total + r] = temp_out[:r]
                read_total += r
            else:
                time.sleep(0.001)

    t_prod = threading.Thread(target=producer)
    t_cons = threading.Thread(target=consumer)
    
    t_prod.start()
    t_cons.start()
    
    t_prod.join(timeout=5.0)
    t_cons.join(timeout=5.0)
    
    assert not t_prod.is_alive()
    assert not t_cons.is_alive()
    assert np.allclose(received_audio, source_audio, atol=1e-6)
