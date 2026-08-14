<div align="center">
  <img src="app_icon.ico" alt="ZFPlayer Logo" width="120" />

  # ZennyFLAC Player (ZFPlayer)

  **Trình phát nhạc Hi-Res Audio trực quan, mạnh mẽ và tinh gọn cho Windows**

  [![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
  [![Audio Engine](https://img.shields.io/badge/Audio-WASAPI_Bit--Perfect-success.svg?logo=windows&logoColor=white)]()
  [![UI Design](https://img.shields.io/badge/UI-Glassmorphism_Fluid_Shader-purple.svg)]()
  [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
</div>

---

**ZennyFLAC Player (ZFPlayer)** là ứng dụng nghe nhạc Lossless & Hi-Res Audio cao cấp dành riêng cho hệ điều hành Windows. Ứng dụng kết hợp giữa **Động cơ âm thanh C-Streaming & WASAPI Bit-Perfect** mạnh mẽ bên dưới và **Giao diện Glassmorphism / Fluid Shader động lực học lộng lẫy** bên trên, mang lại không gian thưởng thức âm nhạc mượt mà, chân thực và thuần khiết nhất.

---

## 🌟 Tính Năng Nổi Bật

### 1. 🎧 Động Cơ Âm Thanh Streaming & WASAPI Bit-Perfect
* **Streaming Audio Engine & Ring Buffer**: Giải mã và đọc luồng âm thanh theo từng khối nhỏ (Chunk-based C-Decoder) kết hợp đệm liên tục trong `AudioRingBuffer` (NumPy Float32 C-contiguous). Triệt tiêu 100% nguy cơ tràn RAM (OOM) khi phát các file Hi-Res dung lượng siêu lớn (FLAC 24-bit 192kHz).
* **Độ trễ 0ms (Zero Latency)**: Thao tác tua nhạc (Seek), chuyển bài, hay lặp bài diễn ra tức thì trong nháy mắt.
* **Tự Phục Hồi Luồng Phát (Hardware Auto-Recovery)**: Tự động phát hiện và kết nối lại luồng âm thanh ngay khi người dùng cắm/rút tai nghe, tháo DAC hoặc ngắt kết nối Bluetooth mà không bị câm tiếng.
* **Khử Tiếng Nổ Loa (Anti-Pop / Anti-Click Ramps)**: Tích hợp vi dốc Micro Fade-in / Fade-out (15–20ms) triệt tiêu hoàn toàn hiện tượng "bụp" giật màng loa khi Play, Pause, Seek hoặc đổi bài.
* **Chống Treo Cuối Bài (Early EOF Guard)**: Tự động chuyển bài mượt mà ngay cả khi file âm thanh bị lỗi nhẹ phần đuôi hoặc có cấu trúc nén biến thiên (VBR MP3).
* **2 Chế Độ Xuất Âm Thanh Linh Hoạt**:
  * **WASAPI Exclusive Mode (Bit-Perfect 100%)**: Truyền tải tín hiệu âm thanh trực tiếp đến DAC cứng, giữ nguyên 100% tần số lấy mẫu và bit-depth gốc mà không qua bộ trộn Windows Mixer.
  * **WASAPI Shared Mode**: Chế độ mặc định linh hoạt, cho phép vừa thưởng thức nhạc chất lượng cao vừa nghe âm thanh từ các ứng dụng khác (Game, Trình duyệt, Thông báo).

---

### 2. 🎤 Màn Hình Lời Bài Hát & Chế Độ Rạp Phim (Kinetic Lyrics Engine)
* **Giao Diện Fullscreen Động Lực Học**: Toàn màn hình với nền WebGL Fluid Shader động chuyển màu mượt mà theo ảnh bìa Album đang phát.
* **Đồng Bộ Lời Nhạc Tự Động Đa Nguồn (Multi-Source Lyrics)**:
  * Ưu tiên 1: Tệp lời bài hát rời `.lrc` cùng thư mục.
  * Ưu tiên 2: Cơ sở dữ liệu lời nhạc trực tuyến **LRCLIB Search API**.
  * Ưu tiên 3: Thẻ tag siêu dữ liệu nhúng sẵn bên trong tệp (FLAC Vorbis Comment / MP3 SYLT & USLT).
  * Ưu tiên 4: Thư viện **Syncedlyrics** (Musixmatch, NetEase, Megalobiz).
* **Động Cơ Cuộn Tay Vật Lý (Physics Inertia Spring Lerp)**: Hỗ trợ lăn chuột cuộn lời với quán tính mượt mà 60fps/120fps, tự động tiếp tục bám theo bài hát sau 3.5 giây không chạm chuột.
* **Chế Độ Rạp Phim (Cinema Idle Mode)**: Khi mở toàn màn hình, nếu người dùng không di chuột trong 3.5 giây, các thanh điều khiển sẽ tự động ẩn đi và căn giữa cụm ảnh bìa + lời bài hát vào vị trí trung tâm sang trọng.
* **Tương Tác Trực Quan**: Click vào bất kỳ câu hát nào để tua nhanh (Seek) đến đúng thời điểm đó.
* **Thuật Toán Tìm Kiếm Nhị Phân $O(\log N)$**: Định vị và highlight câu hát tức thì với độ phức tạp cực thấp.

---

### 3. 📂 Quản Lý Thư Viện & Danh Sách Phát Thông Minh
* **Quét Thư Viện Đa Luồng Siêu Tốc**: Trích xuất Metadata (`mutagen`) và ảnh bìa chất lượng cao, lưu trữ vào SQLite WAL Mode.
* **Bảo Vệ Dữ Liệu Ổ Cứng Ngoài / USB**: Tự động nhận diện và bảo vệ danh sách bài hát, danh sách Yêu thích và Playlist cá nhân khi người dùng tháo thẻ nhớ hoặc rút USB.
* **Tự Động Bỏ Qua File Lỗi (Auto-Skip)**: Nếu bài hát bị xóa khỏi đĩa hoặc lỗi tệp, hệ thống sẽ tự động phát bài kế tiếp kèm giới hạn an toàn chống lặp vô hạn.
* **Tìm Kiếm Toàn Văn Tức Thì (Full-Text Search FTS5)**: Tìm kiếm bài hát, nghệ sĩ, album siêu nhanh chỉ trong vài mili-giây.
* **Tổ Chức Danh Sách Phát Linh Hoạt**:
  * Tạo mới, đổi tên, thay ảnh bìa đại diện cho Playlist cá nhân.
  * Nhập thư mục hoặc chọn từng tệp tin vào danh sách phát.
  * Tính năng **"Phát bài tiếp theo" (Play Next)** thông minh.
  * Đánh dấu bài hát Yêu thích (Favorites) 1-click.
  * Danh mục 20 bài hát vừa nghe gần đây (Recently Played).

---

### 4. ⌨️ Hệ Thống Phím Tắt Tùy Biến Toàn Cục (Shortcuts Manager)
* **Trình Quản Lý Phím Tắt Trực Quan**: Quản lý và tùy chỉnh từng phím tắt trực tiếp trong cửa sổ **Cài đặt (Settings)**.
* **Hỗ Trợ Tổ Hợp Phím Nâng Cao**: Bắt chính xác các phím bổ trợ (`Ctrl`, `Alt`, `Shift`, `Meta`) kết hợp phím ký tự.
* **Ghi Nhận Phím Trực Tiếp (Live Key Recording)**: Nhấn tổ hợp phím mong muốn để gán ngay lập tức, tự động phát hiện và giải quyết trùng lặp phím.
* **Bộ Phím Tắt Mặc Định Tiện Dụng**:
  * <kbd>Space</kbd>: Dừng / Phát nhạc (Play / Pause).
  * <kbd>Ctrl</kbd> + <kbd>→</kbd> / <kbd>Ctrl</kbd> + <kbd>←</kbd>: Bài tiếp theo / Bài trước đó.
  * <kbd>→</kbd> / <kbd>←</kbd>: Tua tới / Tua lùi 5 giây.
  * <kbd>↑</kbd> / <kbd>↓</kbd>: Tăng / Giảm 5% âm lượng.
  * <kbd>M</kbd>: Bật / Tắt tiếng (Mute).
  * <kbd>L</kbd>: Bật / Tắt màn hình Lời bài hát toàn màn hình.
  * <kbd>S</kbd>: Bật / Tắt chế độ xáo bài (Shuffle).
  * <kbd>R</kbd>: Chuyển đổi chế độ lặp bài (Off / All / One).
  * <kbd>Esc</kbd>: Đóng màn hình Lời bài hát, Modal hoặc Menu ngữ cảnh.
  * <kbd>F11</kbd>: Bật / Tắt chế độ Toàn màn hình (Fullscreen).
* **Nút "Previous" Chuẩn Quốc Tế**: Nếu bài hát đã phát quá 3 giây $\rightarrow$ tua lại từ đầu bài (`0:00`); nếu dưới 3 giây $\rightarrow$ nhảy về bài trước.
* **Tích Hợp Windows SMTC / MediaSession**: Hỗ trợ đầy đủ các phím đa phương tiện vật lý trên bàn phím/tai nghe.

---

### 5. ⚡ Tối Ưu Hóa & Hiệu Năng Vượt Trội
* **Bảo Vệ Độ Bền SSD**: Áp dụng Debounce 300ms khi kéo thanh trượt âm lượng, giảm thiểu 95% thao tác ghi đĩa thừa thãi.
* **Bộ Nhớ Đệm Hiển Thị Giây (`_lastDisplaySec`)**: Chỉ cập nhật DOM khi số giây thay đổi, tránh lãng phí tài nguyên render ở màn hình 120Hz/144Hz.
* **Đồng Bộ Nền Thích Ứng (Adaptive Background Polling)**: Tự động điều chỉnh chu kỳ đồng bộ UI (1s khi phát, 2s khi pause, 3s khi ẩn cửa sổ) giúp ứng dụng luôn phản hồi tức thì mà không gây nghẽn Event Loop.

---

## 🛠️ Cấu Trúc Hệ Thống (Tech Stack)

ZFPlayer áp dụng mô hình **Hybrid Desktop Architecture**, tách biệt rõ ràng giữa Giao diện người dùng, Web Server nội bộ và Động cơ âm thanh C-level:

```
ZFPlayer/
├── backend/                  # Python 3.11+ Core Backend
│   ├── app.py                # Điểm khởi động ứng dụng & PyWebView Bridge
│   ├── audio/                # Động cơ âm thanh
│   │   ├── engine.py         # WASAPI Audio Engine & Callback Manager
│   │   ├── decoder.py        # C-Streaming Decoder (libsndfile)
│   │   └── buffer.py         # Audio Ring Buffer (NumPy Float32)
│   ├── services/             # Nghiệp vụ điều khiển nhạc & thư viện
│   │   ├── player_service.py # Quản lý hàng đợi, phát nhạc & Auto-skip
│   │   └── library_service.py# Quản lý CSDL, Playlist & Metadata
│   ├── workers/              # Luồng xử lý ngầm (Worker Threads)
│   │   ├── scanner.py        # Quét thư mục nhạc & Bảo vệ USB
│   │   ├── lyrics_worker.py  # Tải & đồng bộ lời bài hát đa nguồn
│   │   └── metadata_worker.py# Trích xuất ID3 / Vorbis / Hi-Res Cover Art
│   ├── storage/              # Lưu trữ cục bộ (Database, Cache, Config)
│   └── api/                  # Unified REST & Native IPC APIs
│
├── frontend/                 # Giao diện người dùng (Modern Glassmorphism)
│   ├── index.html            # Cấu trúc trang đơn (SPA)
│   ├── css/                  # Vanilla CSS Design System & Responsive Layouts
│   └── js/                   # Vanilla ES6 Modules
│       ├── main.js           # Khởi tạo ứng dụng & Kết nối thành phần
│       ├── shortcuts.js      # Trình quản lý phím tắt toàn cục (ShortcutsManager)
│       ├── player.js         # Bộ điều khiển thanh phát nhạc & Ticker 60fps
│       ├── lyrics.js         # Động cơ lời bài hát Kinetic Spring & Cinema Mode
│       ├── library.js        # Hiển thị & tìm kiếm danh sách bài hát
│       ├── playlists.js      # Trình quản lý Playlist & Nhập tệp
│       ├── fluid-shader.js   # Hiệu ứng nền nước động WebGL (Fluid Shader)
│       ├── store.js          # Quản lý trạng thái tập trung (Central State Store)
│       └── api.js            # Cầu nối Native PyWebView IPC Wrapper
│
├── architect.md              # Tài liệu chi tiết kiến trúc hệ thống
└── DEV_LOG.md                # Lịch sử chi tiết quá trình phát triển
```

---

## 🚀 Tải Về & Sử Dụng

### Dành cho Người Dùng (Chạy file EXE trực tiếp)
Bạn có thể tải bản đóng gói hoàn chỉnh cho Windows mà **không cần cài đặt Python**:
👉 **[Tải Bản Phát Hành ZFP · Releases](https://github.com/zenny126/ZFPlayer/releases)**

---

### Dành cho Lập Trình Viên (Chạy từ mã nguồn)

#### 1. Yêu Cầu Môi Trường
* Hệ điều hành: **Windows 10 / 11 (64-bit)**
* Môi trường: **Python 3.11 trở lên**
* Card âm thanh / DAC hỗ trợ driver Windows WASAPI.

#### 2. Cài Đặt Thư Viện
Mở Terminal tại thư mục gốc của dự án và chạy:
```bash
pip install sounddevice soundfile numpy PyYAML bottle pywebview mutagen requests syncedlyrics
```

#### 3. Khởi Chạy Ứng Dụng
```bash
python backend/app.py
```

---

## 📖 Hướng Dẫn Sử Dụng Nhanh

1. **Thêm Nhạc Vào Thư Viện**: Mở một Playlist bất kỳ (hoặc tạo mới) $\rightarrow$ Nhấn **Import Folder** hoặc **Select Files** $\rightarrow$ Ứng dụng sẽ quét ngầm và nạp nhạc ngay lập tức.
2. **Thưởng Thức Lời Bài Hát**: Bấm biểu tượng **Microphone** ở thanh phát nhạc bên dưới hoặc nhấn phím <kbd>L</kbd> để mở màn hình Karaoke toàn cảnh.
3. **Cá Nhân Hóa Phím Tắt**: Mở **Cài đặt (Settings)** $\rightarrow$ Chọn tab **Shortcuts** $\rightarrow$ Bấm vào nút phím cần đổi và nhấn tổ hợp phím mới trên bàn phím.
4. **Chuyển Chế Độ WASAPI**: Mở **Cài đặt (Settings)** $\rightarrow$ Chuyển đổi giữa **WASAPI Shared Mode** (nghe tiện lợi) hoặc **WASAPI Exclusive Mode** (Audiophile Bit-Perfect).

---

## 📄 Giấy Phép & Tác Giả

* **Tác giả:** Zenny ([@zenny126](https://github.com/zenny126))
* **Bản quyền:** Ứng dụng được phát hành theo giấy phép **Apache License 2.0**. Mọi người được tự do sử dụng, chỉnh sửa và phân phối lại.
