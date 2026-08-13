# ZennyFLAC Player (ZFPlayer)

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Audio Engine](https://img.shields.io/badge/Audio-WASAPI%20Shared%20Mode-success.svg)]()
[![UI Design](https://img.shields.io/badge/UI-Apple%20Music%20Glassmorphism-purple.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

**ZennyFLAC Player (ZFPlayer)** là ứng dụng nghe nhạc Hi-Res Audio chuyên nghiệp chuẩn mã nguồn mở dành cho hệ điều hành Windows. Ứng dụng kết hợp kiến trúc xử lý âm thanh tốc độ C trễ bằng 0 (Zero-Latency RAM Caching & WASAPI Shared Mode) với ngôn ngữ thiết kế kính mờ sang trọng Apple Music Glassmorphic UI, mang lại trải nghiệm nghe nhạc đỉnh cao và trực quan nhất.

---

## 1. Tính Năng Nổi Bật

### 1.1 Động Cơ Âm Thanh Hi-Res & WASAPI Shared Mode
- **Streaming Audio Engine & Ring Buffer:** Giải mã và đọc luồng âm thanh theo từng khối nhỏ (chunk) thông qua C-Decoder thay vì nạp toàn bộ vào RAM. Dữ liệu PCM được đệm liên tục vào một Ring Buffer khép kín, giúp triệt tiêu hiện tượng tràn RAM (OOM) khi phát các file nhạc Lossless dung lượng siêu lớn, trong khi vẫn giữ nguyên độ trễ 0ms khi tua nhạc (Seek) hay chuyển bài.
- **Windows WASAPI Shared Mode Driver:** Tối ưu hóa giao tiếp âm thanh qua `sounddevice` (PortAudio C-wrapper), tự động giữ nguyên tần số lấy mẫu (Sample Rate 44.1kHz – 192kHz) và căn chỉnh Bit-Depth (16-bit / 24-bit PCM / 32-bit Float) sắc nét.
- **Xử lý Bit-Depth chuẩn xác:** Tự động mở rộng dải động bài hát 24-bit (`raw_data << 8`) để truyền trọn vẹn tín hiệu âm thanh nguyên bản đến DAC cứng.

### 1.2 Giao Diện Glassmorphic Đẳng Cấp (Apple Music Style)
- **Hình nền kính mờ động (Dynamic Blur Background):** Trích xuất tự động màu sắc & hình ảnh bìa Album đang phát, phủ lớp sương mờ 80px (`backdrop-filter: blur(80px) saturate(1.5)`), chuyển màu mềm mại theo từng giai điệu.
- **Chữ mơ màng chống lóa (Dreamy Glow Typography):** Font chữ trắng thuần `#FFFFFF` tương phản cao kết hợp hiệu ứng tạo quầng hào quang nhẹ (`text-shadow glow`), giúp dễ đọc 100% trên mọi hình nền.
- **Playlist Vector SVG Động:** "All Songs" và "Favorite Songs" tự động vẽ các ảnh bìa Vector SVG màu Gradient xanh lam và cam hồng cực kỳ bắt mắt.
- **Chuyển cảnh mượt mà (Smooth UI Transitions):** Áp dụng đường cong gia tốc chuẩn macOS/iOS (`cubic-bezier(0.2, 0.9, 0.3, 1)`) cho các tương tác micro-interactions, Modals, Context Menu và View Transitions.

### 1.3 Hệ Thống Tải & Đồng Bộ Lời Bài Hát (Synced Lyrics)
- **Hàng đợi ưu tiên ngầm (Priority Queue Background Worker):** Sử dụng 1 luồng ngầm tiêu thụ hàng đợi tuần tự với cơ chế `0.5s Throttle` giữa các request, bảo vệ API và chống ghi khóa CSDL.
  - *Priority 1 (Ưu tiên cao):* Tải tức thì lời bài đang phát và 5 bài hát kế tiếp.
  - *Priority 10 (Ưu tiên thấp):* Tải lần lượt lời nhạc cho các bài hát mới được import.
- **Thác nước 4 Cấp Ưu Tiên Nguồn (4-Level Fallback Waterfall):**
  1. *Ưu tiên 1:* Đọc tệp `.lrc` cục bộ nằm cùng thư mục và cùng tên với bài hát.
  2. *Ưu tiên 2:* Tìm kiếm qua API `LRCLIB` (`/api/search`) với thuật toán khớp thời lượng bài hát ($\le 3.0s$).
  3. *Ưu tiên 3:* Trích xuất thẻ lời nhạc nhúng trực tiếp trong file (`USLT`, `LYRICS`, `UNSYNCEDLYRICS`).
  4. *Ưu tiên 4:* Tra cứu trực tuyến ngầm qua `syncedlyrics` (Musixmatch / NetEase / Megalobiz).

### 1.4 Thư Viện Nhạc Siêu Tốc & Virtual Scrolling Engine
- **Thuật toán VirtualList 60–120 FPS:** Tự xây dựng bộ thuật toán cuộn danh sách ảo (Offset-aware Index Math), duy trì chỉ 30–40 DOM elements trên cây DOM ngay cả khi hiển thị hơn 50.000 bài hát.
- **Tìm kiếm Full-Text SQLite FTS5:** Tìm kiếm bài hát, ca sĩ, album tức thì với chỉ mục FTS5.
- **Trang chủ 20 bài gần đây & Sidebar thông minh:** Cập nhật tức thì danh sách 20 bài nghe gần nhất, hỗ trợ thu gọn/mở rộng Sidebar với 1-click.

---

## 2. Công Nghệ Sử Dụng (Tech Stack)

### Backend (Python 3.11+)
- **PyWebView / Edge Chromium (WebView2):** Cầu nối giao diện Desktop Windows nguyên bản và Web Frontend.
- **Bottle WSGI Web Server:** HTTP REST API Server đa luồng (Threaded WSGI) cực nhẹ.
- **SoundFile (`libsndfile` C-Decoder) & SoundDevice (PortAudio WASAPI):** Động cơ phát âm thanh C-level nguyên bản.
- **NumPy:** Đệm dữ liệu PCM nguyên bản trong Ring Buffer C-contiguous siêu tốc.
- **SQLite3 (WAL Mode & FTS5):** Cơ sở dữ liệu lưu trữ Metadata, chỉ mục tìm kiếm và bộ nhớ đệm lời bài hát.
- **Mutagen & Syncedlyrics:** Đọc thẻ bài hát Hi-Res và tải lời bài hát đồng bộ.

### Frontend (Vanilla Web Standards)
- **Vanilla HTML5 & CSS3:** CSS Custom Properties (Tokens), Dynamic Backdrop Filter, GPU Acceleration (`will-change: transform`).
- **JavaScript ES6+ & Central Store:** Mô hình quản lý trạng thái 1 chiều (Unidirectional Publisher/Subscriber Store).

---

## 3. Cấu Trúc Dự Án (Directory Structure)

```
ZFPlayer/
├── backend/
│   ├── api/                 # REST API endpoints (player_api, library_api, lyrics_api, config_api)
│   ├── audio/               # Động cơ WASAPI & PCM RAM Buffer (engine.py, decoder.py, buffer.py)
│   ├── models/              # Data models đại diện cho bài hát (track.py)
│   ├── services/            # Logic nghiệp vụ trung tâm (library_service.py, player_service.py)
│   ├── storage/             # Quản lý SQLite DB (database.py), Cache & Config
│   ├── workers/             # Luồng ngầm quét nhạc (scanner.py), Priority Lyrics Worker (lyrics_worker.py)
│   └── app.py               # Điểm khởi chạy ứng dụng (Backend WSGI & PyWebView Window)
├── frontend/
│   ├── css/
│   │   ├── main.css         # Design Tokens, Glassmorphism & Keyframe Animations
│   │   ├── library.css      # Giao diện danh sách bài hát & Sticky Header
│   │   ├── player.css       # Thanh Player Bar điều khiển phát nhạc bên dưới
│   │   ├── lyrics.css       # Giao diện xem lời bài hát đồng bộ (Overlay)
│   │   └── albums.css       # Thẻ Album, Playlist & Grid layout
│   ├── js/
│   │   ├── store.js         # Hệ thống quản lý trạng thái trung tâm (Central State Store)
│   │   ├── api.js           # Cầu nối PyWebView Bridge & HTTP REST Client
│   │   ├── player.js        # Controller điều khiển trình phát nhạc & đồng bộ Slider
│   │   ├── library.js       # Thuật toán VirtualList Math & Render Bảng bài hát
│   │   ├── home.js          # Controller Trang chủ & 20 bài nghe gần đây
│   │   ├── playlists.js     # Quản lý Playlist & SVG Dynamic Cover Generator
│   │   ├── ui.js            # Điều hướng Topbar, Sidebar Toggle & Modals
│   │   └── main.js          # Khởi tạo giao diện ứng dụng
│   └── index.html           # Khung vỏ HTML5 chính của ứng dụng
├── docs/
│   └── ARCHITECTURE.md      # Tài liệu Kiến trúc Hệ thống & Yêu cầu Kỹ thuật Chuyên sâu
├── architect.md             # Bản sao liên kết Tài liệu Kiến trúc Hệ thống
├── DEV_LOG.md               # Nhật ký phát triển chi tiết từng phiên bản
├── walkthrough.md           # Báo cáo các thay đổi kỹ thuật & giao diện
└── README.md                # Tài liệu hướng dẫn sử dụng dự án
```

---

## 4. Hướng Dẫn Cài Đặt & Khởi Chạy

### 4.1 Yêu cầu hệ thống
- Hệ điều hành: **Windows 10 / 11 (64-bit)**
- **Python 3.11+**
- Card âm thanh / DAC hỗ trợ driver Windows WASAPI.

### 4.2 Cài đặt môi trường
Mở Terminal tại thư mục gốc dự án và cài đặt các phụ thuộc:
```bash
pip install sounddevice soundfile numpy PyYAML bottle pywebview mutagen requests syncedlyrics
```

### 4.3 Khởi chạy ứng dụng
Chạy lệnh khởi tạo ứng dụng:
```bash
python backend/app.py
```
Ứng dụng sẽ tự động khởi chạy Bottle WSGI Server ngầm và mở cửa sổ ứng dụng Desktop PyWebView sắc nét!

---

## 5. Hướng Dẫn Sử Dụng

1. **Thêm Thư Mục Nhạc:** Bấm vào biểu tượng **Settings (Bánh răng)** ở góc trên bên phải -> Chọn thư mục chứa các tệp nhạc FLAC/MP3 -> Hệ thống sẽ tự động quét ngầm và hiển thị nhạc.
2. **Thu Gọn Sidebar:** Bấm vào **Icon Logo 3 đĩa** ở góc trên bên trái để thu gọn hoặc mở rộng thanh bên Library.
3. **Phát Nhạc:** Nhấp đúp vào bất kỳ bài hát nào ở Trang chủ hoặc Thư viện để phát nhạc lập tức với âm thanh WASAPI nguyên bản.
4. **Xem Lời Bài Hát:** Nhấp vào icon **Microphone** trên thanh Player Bar bên dưới để mở màn hình xem lời bài hát đồng bộ.
5. **Điều Chỉnh Âm Lượng:** Sử dụng thanh trượt Volume trên Player bar hoặc tại màn hình Lyrics, trạng thái âm lượng sẽ tự động lưu lại cho các lần khởi chạy sau.

---

## 6. Giấy Phép & Tác Giả

- **Tác giả:** Zenny (`zenny126`)
- **Dự án:** ZeroFLAC Player (ZFPlayer) - Open Source High-Fidelity Audio Experience.
