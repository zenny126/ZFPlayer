# ZeroFLAC Player 🎧

**ZeroFLAC Player** là ứng dụng nghe nhạc Hi-Res Audio chuyên nghiệp cho các định dạng nhạc chất lượng cao (FLAC, WAV, MP3) trên Windows. Đón nhận thiết kế lấy cảm hứng từ ngôn ngữ giao diện **Apple Music Glassmorphic**, ứng dụng mang lại trải nghiệm âm thanh chân thực đỉnh cao kết hợp với giao diện kính mờ xuyên thấu sắc nét, mượt mà và chuyển động sống động.

---

## 🌟 Tính Năng Nổi Bật

### 🔊 1. Âm Thanh High-Fidelity & Windows WASAPI
- **Kiến trúc đọc Zero-Latency vào RAM:** Tải toàn bộ dữ liệu PCM nguyên bản của bản nhạc vào bộ nhớ RAM (SoundFile / Libsndfile) để phát âm thanh tốc độ C không trễ, không rật.
- **Mặc định WASAPI Shared Mode:** Tối ưu hóa driver Windows WASAPI giúp âm thanh tròn trịa, giữ nguyên tần số lấy mẫu (Sample Rate) và bit-depth (16-bit / 24-bit / 32-bit Float) mà không gây vỡ tiếng hay xung đột thiết bị.
- **Xử lý chuyển đổi tín hiệu chuẩn xác:** Hỗ trợ mượt mà các file FLAC 24-bit/96kHz và Hi-Res Audio.

### 🎨 2. Giao Diện Immersive Glassmorphism (Apple Music Style)
- **Hình nền kính mờ động (Dynamic Blur Background):** Tự động trích xuất ảnh bìa Album đang phát, phủ lớp mờ sương 80px (`backdrop-filter: blur(80px) saturate(1.5)`), biến đổi màu sắc linh hoạt theo từng bài hát.
- **Chữ trắng mộng mơ (Dreamy Glow Typography):** Chữ trắng thuần `#FFFFFF` nổi bật với lớp hào quang sương mù nhẹ (`text-shadow glow`), chống lóa 100% trên các nền ảnh chói sáng.
- **Pop-up & Context Menu kính mờ:** Các bảng cài đặt, danh mục chuột phải và ô nhập liệu đều sử dụng kính mờ mỏng mờ (`blur(40px)`) kèm viền kính phản quang.
- **Bìa Playlist Vector SVG Động:** "All Songs" và "Favorite Songs" tự động vẽ các ảnh bìa Vector SVG màu Gradient xanh lam và cam hồng cực kỳ bắt mắt.

### ⚡ 3. Tối Ưu Hiệu Năng & Danh Sách Bài Hát
- **Công nghệ VirtualList tự chế:** Tự xây dựng danh sách ảo (Virtual Scrolling) cho phép tải và cuộn hàng chục nghìn bài hát mượt mà ở tốc độ 60fps mà không làm lag trình duyệt.
- **Dòng tiêu đề dính (Sticky Column Header):** Thanh tiêu đề cột (`#`, `TITLE`, `ALBUM`, `DATE ADDED`, `Duration`) tự động "đóng đinh" ở mép trên khi cuộn, phủ lớp kính mờ ngăn chữ trượt đè lên nhau.
- **Trang chủ (Home View) 20 bài gần đây:** Hiển thị danh mục 20 bài nghe gần nhất dưới dạng bảng thông tin chuẩn 7 cột, nhấp đúp là phát ngay.
- **Sidebar thông minh:** Thu gọn / Mở rộng danh mục bên trái chỉ với 1 click vào Logo góc trên.

### 🎤 4. Lời Bài Hát Đồng Bộ (Synced Lyrics) & Thư Viện
- **Tự động tải lời bài hát LRC:** Tải và đồng bộ lời hát theo thời gian thực với hiệu ứng chữ sáng mờ khi ca sĩ cất lời.
- **Quản lý Playlist & Yêu thích:** Tạo danh sách phát cá nhân, thả tim bài hát yêu thích, tìm kiếm bài hát siêu tốc với SQLite FTS.

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack)

### **Backend (Python 3.11)**
- **PyWebView / Chromium:** Trình diễn giao diện web nguyên bản trên ứng dụng Desktop Windows.
- **Bottle Web Server:** HTTP REST Server đa luồng (Threaded WSGI) tốc độ cao phục vụ API và Static Files.
- **SoundDevice & SoundFile:** Driver âm thanh WASAPI nguyên bản đọc trực tiếp dữ liệu PCM C-level.
- **SQLite3 & FTS5:** Cơ sở dữ liệu lưu trữ Metadata bài hát, lượt nghe, lời nhạc và chỉ mục tìm kiếm siêu tốc.

### **Frontend (Vanilla Web)**
- **Vanilla HTML5 & CSS3:** Không phụ thuộc thư viện nặng như React/Tailwind, tối ưu hóa CSS Glass Tokens và GPU acceleration (`transform`, `backdrop-filter`).
- **JavaScript ES6+ & Store Subscriber Pattern:** Luồng dữ liệu 1 chiều (Unidirectional Data Flow) tự động cập nhật UI khi trạng thái phát nhạc thay đổi.

---

## 📁 Cấu Trúc Dự Án (Directory Structure)

```
ZFPlayer/
├── backend/
│   ├── api/                 # Phân hệ REST API (Player, Library, Lyrics, Config)
│   ├── audio/               # Động cơ âm thanh WASAPI & Ring Buffer (engine.py)
│   ├── models/              # Data Models (track.py)
│   ├── services/            # Logic nghiệp vụ (library_service.py, player_service.py)
│   ├── storage/             # Quản lý SQLite DB (database.py) & Cache
│   ├── workers/             # Luồng ngầm quét nhạc (scanner.py) & Tải lời bài hát
│   └── app.py               # Điểm khởi chạy chính ứng dụng Backend & PyWebView
├── frontend/
│   ├── css/
│   │   ├── main.css         # Hệ thống thiết kế Glassmorphism & Tokens
│   │   ├── library.css      # Giao diện bảng danh sách bài hát & Sticky Header
│   │   ├── player.css       # Thanh điều khiển phát nhạc bên dưới
│   │   ├── lyrics.css       # Giao diện xem lời bài hát đồng bộ
│   │   └── albums.css       # Thẻ Playlist & Grid
│   ├── js/
│   │   ├── store.js         # Hệ thống Quản lý Trạng thái (Central State Store)
│   │   ├── api.js           # Cầu nối PyWebView Bridge & REST API
│   │   ├── player.js        # Controller điều khiển trình phát nhạc
│   │   ├── library.js       # Thuật toán VirtualList & Render Bảng bài hát
│   │   ├── home.js          # Controller Trang chủ & 20 bài nghe gần đây
│   │   ├── playlists.js     # Quản lý Playlist & SVG Cover Generator
│   │   ├── ui.js            # Điều hướng Topbar, Sidebar Toggle, Modals
│   │   └── main.js          # Khởi tạo giao diện ứng dụng
│   └── index.html           # Khung vỏ giao diện HTML5 chính
├── DEV_LOG.md               # Nhật ký phát triển chi tiết từng phiên bản
├── walkthrough.md           # Báo cáo các thay đổi kỹ thuật & giao diện
└── README.md                # Tài liệu hướng dẫn dự án
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### 1. Yêu cầu hệ thống
- Hệ điều hành: **Windows 10 / 11**
- **Python 3.11+**
- Đã cài đặt C++ Build Tools hoặc thư viện `soundfile` / `sounddevice`

### 2. Cài đặt môi trường
Mở Terminal tại thư mục dự án và cài đặt các phụ thuộc:
```bash
pip install sounddevice soundfile numpy PyYAML bottle pywebview mutagen requests
```

### 3. Khởi chạy ứng dụng
Chạy tệp `app.py`:
```bash
python backend/app.py
```
Ứng dụng sẽ tự động khởi tạo Server nội bộ và mở cửa sổ PyWebView với giao diện Glassmorphism rực rỡ!

---

## 📖 Hướng Dẫn Sử Dụng
1. **Thêm Thư Mục Nhạc:** Bấm vào biểu tượng **Cài đặt (Bánh răng)** ở góc trên bên phải -> Chọn thư mục chứa các tệp nhạc FLAC/MP3 của bạn -> Hệ thống sẽ tự động quét nhạc và hiển thị.
2. **Thu Gọn Sidebar:** Bấm vào **Icon Logo 3 đĩa** ở góc trên bên trái để thu gọn hoặc mở rộng thanh bên Library.
3. **Phát Nhạc:** Nhấp đúp vào bất kỳ bài hát nào ở Trang chủ hoặc Thư viện để phát nhạc lập tức với âm thanh WASAPI mượt mà.
4. **Xem Lời Bài Hát:** Nhấp vào icon Micro trên thanh Player bar để mở màn hình Lời bài hát đồng bộ.

---

## 📄 Giấy Phép & Tác Giả
- **Tác giả:** Zenny (`zenny126`)
- **Dự án:** ZeroFLAC Player - Open Source High-Fidelity Audio Experience.
