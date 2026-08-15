# ADR-0003: Local-First Priority & Persistent Pool Network Lyrics Pipeline

## Status
**Accepted** (2026-08-15)

## Context & Problem Statement
Hệ thống tải lời bài hát ban đầu luôn gửi request HTTP ra Internet đến LRCLIB Search API trước khi kiểm tra các nguồn cục bộ. Việc này gây ra:
1. **Lãng Phí Băng Thông & Tăng Độ Trễ**: Ngay cả khi người dùng đã lưu sẵn file `.lrc` chất lượng cao trong thư mục nhạc, ứng dụng vẫn phải chờ 300 - 800ms để kết nối Internet.
2. **Chi Phí Bắt Tay TLS & TCP Connection Churn**: Việc tạo mới `requests.get()` cho từng bài hát làm tăng độ trễ mạng do phải bắt tay TLS nhiều lần.
3. **Spam Request Đối Với Bài Không Lời**: Các bản nhạc không lời (Instrumental/EDM) liên tục bị gửi request tìm kiếm trên mạng mỗi khi phát lại.

## Decision Drivers
- Tốc độ tải lời từ máy cục bộ phải là $< 5\text{ms}$.
- Giữ kết nối HTTP Keep-Alive để tái sử dụng socket mạng.
- Ngăn chặn triệt để tình trạng spam request đối với các bài không có lời.

## Considered Options
1. **Option A (Online First)**: Luôn tìm kiếm trên Internet trước, nếu lỗi mới fallback về file cục bộ. (Bị loại vì lãng phí mạng và độ trễ cao).
2. **Option B (Local-First với Short-Lived HTTP Client)**: Ưu tiên file `.lrc` cục bộ nhưng dùng `requests.get()` không duy trì session. (Bị loại vì chi phí bắt tay TLS cao).
3. **Option C (Local-First + Persistent Session Pool + Negative Cache TTL - Được chọn)**:
   - Cấp 1: Đọc file `.lrc` cục bộ (< 5ms).
   - Cấp 2: Đọc thẻ nhúng `USLT` / `SYLT` (< 15ms).
   - Cấp 3: Gọi trực tiếp LRCLIB CDN `/api/get` (Exact Match) qua `requests.Session` có Connection Pooling.
   - Cấp 4: Cache kết quả âm tính `[NO_LYRICS]` với TTL 7 ngày.

## Decision Outcome
Lựa chọn **Option C**:
- Toàn bộ pipeline ưu tiên nguồn cục bộ.
- `LyricsWorker` khởi tạo một `requests.Session()` dùng chung với `HTTPAdapter(pool_connections=5, pool_maxsize=10)`.
- Khi bài hát không có lời, lưu giá trị đánh dấu `[NO_LYRICS]` vào bảng `lyrics_cache` với thời hạn 7 ngày.

### Positive Consequences
- 90% bài hát có sẵn `.lrc` hiển thị lời ngay tức khắc (< 5ms).
- Độ trễ tải lời online giảm từ 800ms xuống còn ~120ms nhờ HTTP Keep-Alive và exact endpoint `/api/get`.
- Triệt tiêu hoàn toàn các request mạng dư thừa cho các bản nhạc không lời.
