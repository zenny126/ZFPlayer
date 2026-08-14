import numpy as np
import threading

class AudioRingBuffer:
    def __init__(self, capacity_frames: int, channels: int, dtype=np.float32):
        self.capacity = capacity_frames
        self.channels = channels
        self.dtype = np.dtype(dtype)
        self.buffer = np.zeros((self.capacity, self.channels), dtype=self.dtype)
        self.write_idx = 0
        self.read_idx = 0
        self.size = 0
        self.lock = threading.Lock()
        self.has_space_cond = threading.Condition(self.lock)

    def write(self, data: np.ndarray) -> int:
        frames_to_write = data.shape[0]
        with self.lock:
            space_left = self.capacity - self.size
            if space_left == 0:
                return 0
            
            frames_written = min(frames_to_write, space_left)
            end_idx = self.write_idx + frames_written
            
            if end_idx <= self.capacity:
                self.buffer[self.write_idx:end_idx] = data[:frames_written]
            else:
                part1_size = self.capacity - self.write_idx
                self.buffer[self.write_idx:] = data[:part1_size]
                part2_size = frames_written - part1_size
                self.buffer[:part2_size] = data[part1_size:frames_written]
                
            self.write_idx = (self.write_idx + frames_written) % self.capacity
            self.size += frames_written
            return frames_written

    def read_into(self, outdata: np.ndarray) -> int:
        frames = outdata.shape[0]
        with self.lock:
            frames_to_read = min(frames, self.size)
            if frames_to_read > 0:
                end_idx = self.read_idx + frames_to_read
                if end_idx <= self.capacity:
                    outdata[:frames_to_read] = self.buffer[self.read_idx:end_idx]
                else:
                    part1_size = self.capacity - self.read_idx
                    outdata[:part1_size] = self.buffer[self.read_idx:]
                    part2_size = frames_to_read - part1_size
                    outdata[part1_size:frames_to_read] = self.buffer[:part2_size]
                    
                self.read_idx = (self.read_idx + frames_to_read) % self.capacity
                self.size -= frames_to_read
                self.has_space_cond.notify_all()
                
            if frames_to_read < frames:
                outdata[frames_to_read:] = 0
                
        return frames_to_read

    def wait_for_space(self, min_space: int = 1, timeout: float = 0.05) -> bool:
        with self.lock:
            if (self.capacity - self.size) >= min_space:
                return True
            self.has_space_cond.wait(timeout=timeout)
            return (self.capacity - self.size) >= min_space

    def wake_up(self):
        with self.lock:
            self.has_space_cond.notify_all()

    def available(self) -> int:
        with self.lock:
            return self.size

    def space(self) -> int:
        with self.lock:
            return self.capacity - self.size

    def clear(self):
        with self.lock:
            self.write_idx = 0
            self.read_idx = 0
            self.size = 0
            self.has_space_cond.notify_all()

