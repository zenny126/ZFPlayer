<div align="center">
  <img src="app_icon.ico" alt="ZFPlayer Logo" width="120" />

  # ZennyFLAC Player (ZFPlayer)

  **Ứng dụng nghe nhạc Hi-Res trực quan, dễ dùng và tinh gọn tính năng**

  [![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
  [![Audio Engine](https://img.shields.io/badge/Audio-WASAPI_Shared_Mode-success.svg?logo=windows&logoColor=white)]()
  [![UI Design](https://img.shields.io/badge/UI-Modern_Glassmorphism-purple.svg)]()
  [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
</div>

---

**ZennyFLAC Player (ZFPlayer)** là ứng dụng nghe nhạc Hi-Res Audio trực quan, dễ sử dụng và tinh gọn các tính năng. Dành riêng cho hệ điều hành Windows, ứng dụng tập trung vào trải nghiệm người dùng tối giản bằng cách ẩn đi sự phức tạp kỹ thuật bên dưới động cơ nguyên bản, mang lại không gian nghe nhạc mượt mà và tập trung nhất.

---

## Tính Năng Nổi Bật

### Tinh Gọn & Trực Quan
* **Thiết kế Tối giản**: Bố cục rõ ràng, dễ làm quen ngay từ lần đầu sử dụng. Mọi thao tác tổ chức thư viện, thiết lập và phát nhạc đều được đơn giản hóa tối đa.
* **Không gian Sống động**: Hiệu ứng kính mờ (Glassmorphism) chuyển màu tinh tế theo ảnh bìa bài hát, tạo cảm giác thư giãn mà không gây rối mắt.
* **Trải nghiệm Siêu mượt**: Tìm kiếm bài hát tích tắc và cuộn mượt mà hàng chục ngàn bài hát nhờ thuật toán tối ưu hóa giao diện.

### Trải Nghiệm Âm Thanh Hi-Res
* **Âm thanh Nguyên bản**: Hỗ trợ chơi nhạc Lossless (FLAC, WAV, v.v.) truyền trực tiếp tới phần cứng âm thanh (WASAPI) để giữ trọn vẹn chi tiết nguyên gốc.
* **Độ trễ 0ms**: Chuyển bài hay tua nhạc diễn ra ngay lập tức không có độ trễ, giữ cho luồng âm thanh của bạn luôn xuyên suốt.

### Lời Bài Hát Tự Động
* **Đồng bộ Thông minh**: Hệ thống tự động tìm và đồng bộ lời bài hát chạy chữ theo giai điệu, không cần bất kỳ thao tác thủ công nào từ phía người dùng.

---

## Cấu Trúc Dự Án (Tech Stack)

ZFPlayer áp dụng mô hình **Hybrid Desktop Architecture**, tách biệt hoàn toàn giữa UI, Backend Server và Audio Engine.

* **Backend**: Python 3.11+ / Bottle WSGI / PyWebView / SQLite3 FTS5
* **Audio Layer**: SoundDevice (WASAPI PortAudio) / SoundFile (libsndfile C-Decoder) / NumPy
* **Frontend**: Vanilla HTML5/CSS3 / ES6 Javascript / Central Store State Management

> **Xem chi tiết kiến trúc chuyên sâu tại tài liệu: [`architect.md`](architect.md)**

---

## Hướng Dẫn Cài Đặt

### 1. Yêu Cầu Hệ Thống
* Hệ điều hành: **Windows 10 / 11 (64-bit)**
* Môi trường: **Python 3.11 trở lên**
* Card âm thanh/DAC hỗ trợ driver Windows WASAPI.

### 2. Cài Đặt Phụ Thuộc
Mở Terminal tại thư mục gốc dự án và chạy lệnh sau để cài đặt các thư viện cần thiết:
```bash
pip install sounddevice soundfile numpy PyYAML bottle pywebview mutagen requests syncedlyrics
```

### 3. Khởi Chạy
Chạy lệnh khởi động ứng dụng:
```bash
python backend/app.py
```
> Ứng dụng sẽ khởi tạo ngầm một Bottle WSGI Web Server và tự động mở giao diện ứng dụng PyWebView mượt mà.

---

## Hướng Dẫn Sử Dụng Nhanh

1. **Thêm Nhạc:** Mở một Playlist bất kỳ (hoặc tạo mới) ở thanh bên trái $\rightarrow$ Click vào nút **Import Folder** hoặc **Select Files** $\rightarrow$ Hệ thống sẽ quét nhạc ngầm và tự động tải vào Playlist.
2. **Phát Nhạc:** Double-click vào bất kỳ bài hát nào để nghe với chất lượng WASAPI đỉnh cao.
3. **Tùy Chỉnh Âm Thanh:** Click vào biểu tượng **Cài đặt** (góc trái màn hình) để chuyển đổi giữa hai chế độ:
   - **Exclusive Mode (Bit-Perfect 100%)**: Nên dùng khi bạn muốn truyền tải tín hiệu âm thanh nguyên bản và tinh khiết nhất tới thiết bị giải mã (DAC) mà không bị hệ điều hành can thiệp giảm chất lượng. (Lưu ý: Ứng dụng sẽ chiếm quyền độc quyền DAC, các ứng dụng khác sẽ không phát được âm thanh).
   - **Shared Mode**: Chế độ mặc định linh hoạt. Dành cho nhu cầu nghe nhạc thông thường, cho phép bạn vừa thưởng thức âm thanh Hi-Res vừa có thể nghe âm thanh từ các ứng dụng khác cùng lúc (Chrome, Game, Thông báo).
4. **Lời Bài Hát:** Nhấn vào biểu tượng **Microphone** ở thanh Player Bar (dưới cùng) để mở màn hình lời nhạc đồng bộ lộng lẫy.
5. **Giao Diện Gọn Gàng:** Click vào biểu tượng **Logo (3 đĩa)** ở góc trái để thu gọn/mở rộng thanh bên (Sidebar).

---

## Giấy Phép & Tác Giả

* **Tác giả:** Zenny (`zenny126`)
* **Bản quyền:** Ứng dụng được phân phối dưới giấy phép **Apache License 2.0**. Mọi người tự do sử dụng, chỉnh sửa và phân phối lại.
