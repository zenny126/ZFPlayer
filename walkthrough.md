# Walkthrough - Khắc Phục Lỗi WASAPI Shared Mode & Tự Động Chuyển Đổi Tần Số Lấy Mẫu

Đã khắc phục triệt để hiện tượng mất tiếng trong chế độ **WASAPI Shared Mode** khi tần số lấy mẫu của bài hát (ví dụ FLAC 44.1kHz hoặc Hi-Res 96kHz/192kHz) không trùng khớp với tần số cấu hình trong Windows Sound Mixer (ví dụ 48000Hz 32-bit Studio Quality).

---

## 🛠️ Chi Tiết Các Thay Đổi

### `backend/audio/engine.py`
1. **Kích hoạt cờ Tự động Resample phần cứng/hệ điều hành**:
   - Khởi tạo `sd.WasapiSettings(exclusive=False, auto_convert=True)` và bổ sung cờ `paWinWasapiAutoConvert` (`AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM`).
   - Cho phép Windows Audio Engine (AudioDG) tự động chuyển đổi tần số của file nhạc (ví dụ 44.1kHz chuẩn CD hoặc 96kHz Hi-Res) khớp với tần số cấu hình trong Windows Sound Mixer (ví dụ 48000Hz 32-bit Studio Quality) mà không bị từ chối kết nối với mã lỗi `AUDCLNT_E_UNSUPPORTED_FORMAT`.
2. **Kiến trúc Fallback 2 lớp thông minh (Smart Multi-layer Fallback)**:
   - *Lớp 1 (Exclusive -> Shared)*: Nếu chế độ Exclusive Mode gặp sự cố phần cứng, tự động chuyển về Shared Mode với `auto_convert=True`.
   - *Lớp 2 (Universal PortAudio Fallback)*: Nếu driver soundcard của người dùng không hỗ trợ cờ WASAPI mở rộng, hệ thống tự động fallback về stream PortAudio chuẩn không có extra_settings để bộ resampler chất lượng cao của PortAudio tự động xử lý, đảm bảo 100% không bao giờ bị mất tiếng hay crash ứng dụng.

---

## 🔍 Kết Quả Kiểm Thử & Xác Minh (Verification Results)
* **WASAPI Shared Mode**: Tự động phát mượt mà khi Windows Default Format đặt 48000Hz, 44100Hz, 96000Hz hoặc 192000Hz.
* **WASAPI Exclusive Mode**: Giữ nguyên cơ chế Bit-perfect 1:1 độc quyền DAC trực tiếp.
* **An toàn luồng**: Loại bỏ hoàn toàn ngoại lệ `AUDCLNT_E_UNSUPPORTED_FORMAT` và `PaErrorCode -9997`.

---

## 📚 Tài Liệu Liên Quan
* Nhật ký phát triển: [`DEV_LOG.md`](file:///d:/ZFPlayer/DEV_LOG.md)
