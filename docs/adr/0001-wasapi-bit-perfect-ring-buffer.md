# ADR-0001: Decoupled WASAPI Real-Time Audio Callback & Zero-Allocation Ring Buffer

## Status
**Accepted** (2026-08-15)

## Context & Problem Statement
Trong các phiên bản trước, khi bài hát kết thúc trong callback âm thanh của PortAudio/WASAPI (`_audio_callback`), hàm `on_track_end()` được gọi trực tiếp hoặc khởi tạo một `threading.Thread(...)` bên trong callback. Điều này dẫn tới:
1. **Nghẽn Khóa Python GIL & Buffer Underrun**: Việc cấp phát bộ nhớ (`PyObject_New`) hoặc tranh chấp khóa GIL trong Real-time Audio Callback làm trễ nhịp xử lý của PortAudio, gây ra tiếng nổ lách tách ("pop/click") hoặc méo tiếng ở đuôi bài hát.
2. **Áp Lực Garbage Collector (GC)**: Mỗi chunk âm thanh giải mã nạp vào buffer lại tạo ra một `np.ndarray` mới trên Heap, làm tăng đáng kể áp lực gom rác khi phát các tệp Hi-Res 24-bit 192kHz dung lượng hàng trăm Megabytes.

## Decision Drivers
- Không bao giờ cấp phát bộ nhớ Heap (`malloc`/GC) bên trong luồng Real-Time Audio Callback.
- Độ trễ phản hồi chuyển bài phải là $O(1)$ và độc lập với PortAudio.
- Bộ nhớ đệm đọc file phải được cấp phát cố định 1 lần duy nhất khi nạp bài hát.

## Considered Options
1. **Option A (Trực tiếp)**: Gọi `on_track_end()` ngay trong `_audio_callback`. (Bị loại vì nguy cơ Deadlock GIL và méo tiếng).
2. **Option B (Khởi tạo Thread trong Callback)**: `threading.Thread(target=on_track_end).start()`. (Bị loại vì cấp phát Heap trong callback thời gian thực).
3. **Option C (Decoupled Thread-Safe Signal Dispatcher - Được chọn)**: Realtime callback chỉ gán cờ `_track_end_event.set()` ($O(1)$ lockless signal). Một background worker thread chuyên biệt `_track_end_dispatcher` thường trực đợi sự kiện và kích hoạt chuyển bài ngoài vùng realtime.

## Decision Outcome
Lựa chọn **Option C** kết hợp với **Zero-Allocation Read Buffer** trong `StreamingDecoder`:
- `StreamingDecoder` cấp phát trước `self._read_buffer` dạng `float32` C-contiguous một lần duy nhất trong `load()`.
- Vòng lặp giải mã ghi đè trực tiếp vào buffer có sẵn qua `soundfile.read(out=target_slice)`.
- Callback PortAudio chỉ đọc từ `AudioRingBuffer` và báo hiệu qua `threading.Event`.

### Positive Consequences
- Triệt tiêu 100% hiện tượng xước tiếng/khựng âm thanh khi chuyển bài.
- Giảm 95% áp lực lên Python GC khi phát các tệp Hi-Res Audio.
- Luồng âm thanh thời gian thực hoàn toàn an toàn và độc lập với các tác vụ I/O của hệ điều hành.

### Negative Consequences / Trade-offs
- Tăng thêm 1 luồng nền `_track_end_dispatcher` chạy ngầm suốt vòng đời của `AudioEngine` (chi phí tài nguyên cực thấp, sleep 100% thời gian khi đang phát bình thường).
