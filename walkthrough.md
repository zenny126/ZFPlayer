# Báo Cáo Thay Đổi Tài Liệu (Walkthrough)

## Các Việc Đã Thực Hiện

### 1. Viết lại `README.md`
- **Tệp thay đổi:** [`README.md`](file:///d:/ZFPlayer/README.md)
- **Nội dung:**
  - Chuẩn hóa tổng quan dự án ZeroFLAC Player (ZFPlayer).
  - Trình bày 4 nhóm tính năng nổi bật (Âm thanh Hi-Res WASAPI, Giao diện Glassmorphism Apple-style, Synced Lyrics 4 cấp fallback, Virtual Scrolling 60fps).
  - Tóm tắt công nghệ Backend/Frontend, sơ đồ cây cấu trúc dự án.
  - Hướng dẫn cài đặt, khởi chạy ứng dụng và hướng dẫn sử dụng chi tiết.
  - Loại bỏ các icon trang trí dư thừa theo đúng yêu cầu từ người dùng.

### 2. Viết lại `docs/ARCHITECTURE.md` và tạo `architect.md`
- **Tệp thay đổi / tạo mới:** [`docs/ARCHITECTURE.md`](file:///d:/ZFPlayer/docs/ARCHITECTURE.md) và [`architect.md`](file:///d:/ZFPlayer/architect.md)
- **Nội dung:**
  - **Cấu trúc Hệ thống:** Mô hình Client-Server lai Desktop với sơ đồ Mermaid chi tiết.
  - **5 Luồng Dữ Liệu Cốt Lõi:**
    1. *Luồng Khởi chạy & IPC Bridge* (`pywebview` Edge Chromium + `bottle` WSGI REST API).
    2. *Luồng Giải mã & Phát nhạc PCM Zero-Latency* (`soundfile` C-decoder + `numpy` RAM array + `sounddevice` WASAPI Shared Mode callback).
    3. *Luồng Quét nhạc ngầm & Đánh chỉ mục FTS5* (`threading.Thread` + `mutagen` + SQLite3 FTS5 batch transaction).
    4. *Luồng Tải & Đồng bộ Lời bài hát* (`queue.PriorityQueue` 2 cấp + Single Worker Thread với 0.5s throttle + Thác nước 4 cấp nguồn Local LRC / LRCLIB Search / Embedded Tag / Syncedlyrics).
    5. *Luồng Frontend & Virtual Scrolling* (Central Unidirectional Store + `scrollTop - offsetTop` VirtualList Math + CSS Glass Tokens).
  - **Yêu cầu Kỹ thuật Chuyên sâu:**
    - Quy chuẩn Phần cứng & OS (Windows 10/11 64-bit, RAM Playback Caching).
    - Thư viện phụ thuộc C-level & Python modules.
    - Cơ sở dữ liệu SQLite3 WAL Mode & FTS5 optimization directives.
    - Quy tắc đa luồng & an toàn thread (Audio Thread Callback isolation, Single Lyrics Worker Thread).
    - Chỉ số SLA & giới hạn hiệu năng (Seek latency 0ms, CPU Idle < 0.5%, UI Frame Rate 60–120 FPS).

### 3. Ghi nhật ký phát triển
- **Tệp thay đổi:** [`DEV_LOG.md`](file:///d:/ZFPlayer/DEV_LOG.md) và [`task.md`](file:///d:/ZFPlayer/task.md)
- Cập nhật nhật ký phát triển chi tiết từng mục thay đổi.

---

## Kiểm Chứng

- Đã xác minh tính đồng bộ 100% giữa tài liệu kiến trúc và mã nguồn triển khai thực tế trong `backend/` và `frontend/`.
- Tất cả tệp tài liệu đều sử dụng định dạng Markdown chuẩn, không có lỗi biểu thức và không thêm emoji rác.

## Thêm Giấy phép Apache 2.0
- **Thay đổi**: Đã tạo tệp LICENSE mới ở thư mục gốc của dự án chứa nội dung Apache License 2.0.
- **Kiểm tra**: Nội dung giấy phép đã được kiểm tra tính chính xác và đầy đủ.
