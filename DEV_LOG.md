# DEV LOG

## Timestamp: 2026-08-13T20:11:00
### Tác vụ thực hiện
Tăng độ lệch nhịp phân tầng (Staggered Cascading Animation) và ép cố định 100% các thuộc tính sử dụng đường cong Bezier Apple Music (`cubic-bezier(0.25, 1, 0.35, 1)`).

### Danh sách tệp tin thay đổi
- `frontend/css/main.css` (MODIFIED)
- `frontend/css/lyrics.css` (MODIFIED)
- `frontend/js/lyrics.js` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Bổ Sung & Cập Nhật Token Thời Lượng Phân Tầng (`main.css`)**:
   - `--transition-lyrics-scroll: 880ms var(--ease-apple-lyrics)` (khung trôi cuộn êm ái).
   - `--transition-lyrics-focus: 780ms var(--ease-apple-lyrics)` (câu active nở sáng phóng to mượt).
   - `--transition-lyrics-passed: 800ms var(--ease-apple-lyrics)` (câu đã qua mờ dần thư thái).
   - `--transition-lyrics-next: 480ms var(--ease-apple-lyrics)` (câu kế tiếp phản hồi trước 300ms).
2. **Ép 100% Transition Dùng Bezier Curve (`lyrics.css`)**:
   - Áp dụng triệt để đường cong `--ease-apple-lyrics` cho tất cả các trạng thái: `#lyrics-content`, `.lyrics-line` base, `.lyrics-line:hover`, `.lyrics-line.active`, `.lyrics-line.next`, và `.lyrics-line.passed`.
3. **Đồng Bộ JS Scroll Logic (`lyrics.js`)**:
   - Cập nhật hàm `scrollToLine()` trường hợp `isFarJump` dùng nhịp 580ms cùng đường cong `cubic-bezier(0.25, 1, 0.35, 1)`.

---

## Timestamp: 2026-08-13T20:04:30
### Tác vụ thực hiện
Tăng tốc chuyển động (420ms) và nạp trước điểm focus nhẹ cho câu lyric tiếp theo (`.lyrics-line.next`).

### Danh sách tệp tin thay đổi
- `frontend/css/lyrics.css` (MODIFIED)
- `frontend/js/lyrics.js` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Thiết Lập Selector CSS `.lyrics-line.next` (`lyrics.css`)**:
   - Thêm quy định CSS cho `.lyrics-line.active + .lyrics-line` và `.lyrics-line.next` với thời lượng transition **420ms** (nhanh hơn 180ms so với nhịp 600ms tiêu chuẩn).
   - Tự động nạp trước điểm focus nhẹ với độ sáng `color: rgba(255,255,255,0.42)` và độ mờ nhẹ `blur(0.8px)`.
2. **Cập Nhật JS Tự Động Quản Lý Class `.next` (`lyrics.js`)**:
   - Trong phương thức `update()`, tự động gắn class `.next` cho dòng `lines[newIndex + 1]` mỗi khi chuyển câu active mới.

---

## Timestamp: 2026-08-13T19:49:00
### Tác vụ thực hiện
Nâng cấp hiệu ứng cuộn và chuyển dòng Lyric mềm mại, mượt mà chuẩn phong cách Apple Music bằng đường cong Bezier hãm quán tính chuyên dụng (`cubic-bezier(0.25, 1, 0.35, 1)`).

### Danh sách tệp tin thay đổi
- `frontend/css/main.css` (MODIFIED)
- `frontend/css/lyrics.css` (MODIFIED)
- `frontend/js/lyrics.js` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Bổ Sung Token Bezier Apple Music (`main.css`)**:
   - Thêm `--ease-apple-lyrics: cubic-bezier(0.25, 1, 0.35, 1)` (đường cong hãm quán tính siêu mượt chuẩn iOS) và token `--transition-lyrics-scroll: 650ms`.
2. **Cấu Hình Chuyển Động Khung & Dòng Hát (`lyrics.css`)**:
   - `#lyrics-content`: Cập nhật `transition: transform 650ms var(--ease-apple-lyrics)` giúp toàn bộ khung chữ trôi lên êm ái, bám theo nhịp bài hát.
   - `.lyrics-line`: Cập nhật chuyển đổi đồng bộ 600ms cho `color`, `transform`, `filter`, `text-shadow`, và `opacity`.
   - `.active`: Zoom mượt `scale(1.06)`, tỏa quầng sáng dịu mắt `text-shadow`, và xóa nhòe `blur(0)`.
   - `.passed` & dòng sắp tới: Giảm độ sáng nhẹ nhàng, nhòe mượt `blur(1.2px)`.
3. **Điều Khiển Nhảy Dòng Thông Minh (`lyrics.js`)**:
   - Phân biệt giữa chuyển dòng phát nhạc tuần tự (dùng 650ms curve siêu mềm) và click seek nhảy xa >3 câu (áp dụng 450ms curve để giao diện phản hồi nhanh không bị trễ).

---

## Timestamp: 2026-08-13T17:53:30
### Tác vụ thực hiện
Cập nhật `.gitignore` để loại bỏ các tệp build tạm (`build/`, `dist/`) và tiến hành đồng bộ / push mã nguồn lên kho lưu trữ từ xa (GitHub).

### Danh sách tệp tin tạo mới & thay đổi
- `.gitignore` (MODIFIED)
- `DEV_LOG.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Cập nhật `.gitignore`**:
   - Thêm `build/` và `dist/` vào `.gitignore` để tránh commit các file ứng dụng thực thi binary dung lượng lớn (.exe) và thư mục tạm do PyInstaller tạo ra.
2. **Chuẩn bị Push Git**:
   - Stage toàn bộ mã nguồn hợp lệ và thực hiện `git commit` / `git push` theo yêu cầu từ phía người dùng.

---

## Timestamp: 2026-08-13T17:28:00
### Tác vụ thực hiện
Tối ưu UX quá trình Import bài hát vào Playlist: hiển thị tiến độ quét thực tế (Progress Modal) và tự động cập nhật danh sách bài hát ngay sau khi nhập hoàn tất.

### Danh sách tệp tin tạo mới & thay đổi
- `build_exe.py` (MODIFIED)
- `dist/ZFPlayer_v1.1.exe` (NEW)

### Mô tả chi tiết kỹ thuật
1. **Khắc phục Bộ nhớ đệm Icon của Windows Explorer (`IconCache.db`)**:
   - Icon `app_icon.ico` được nhúng chuẩn 100% vào file thực thi trong quá trình PyInstaller build.
   - Do Windows Explorer lưu cache Icon theo đường dẫn file cũ `ZFPlayer.exe`, tạo bản sao [`dist/ZFPlayer_v1.1.exe`](file:///d:/ZFPlayer/dist/ZFPlayer_v1.1.exe) giúp Windows Explorer nhận diện đường dẫn mới và hiển thị icon `ZFP` chuẩn ngay lập tức mà không bị ảnh hưởng bởi IconCache cũ.
1. **Sửa lỗi hỏng Tự động Reload (`library.js`)**:
   - Xóa bỏ listener click bị trùng lặp và chứa lệnh gọi phương thức không tồn tại `this.reloadCurrent()`.
2. **Theo dõi Tiến độ Scan Real-time ở Backend (`library_service.py`)**:
   - Khởi tạo và cập nhật trạng thái `_scan_state` (`is_scanning`, `scanned`, `total`, `current_file`) khi chạy `import_folder_to_playlist` và `import_files_to_playlist`.
   - Trả về thông báo thành công cùng số bài hát đã thêm.
3. **Hiển thị Import Progress Modal & Toast Notification (`index.html`, `playlists.js`, `ui.js`)**:
   - Thêm HTML `#import-progress-modal` hiển thị tên bài hát đang xử lý, thanh tiến trình % và chỉ số `scanned/total`.
   - Tạo cơ chế Polling `startProgressPolling` trong `playlists.js` gọi `window.api.getScanProgress()` liên tục để cập nhật UI mượt mà.
   - Thêm phương thức `showToast` vào `UIController` thông báo kết quả khi nhập thành công.
   - Tự động gọi `window.libraryManager.reload()` và `loadPlaylists()` ngay sau khi import kết thúc để bài hát xuất hiện lập tức không cần F5.

---

## Timestamp: 2026-08-13T17:21:00
### Tác vụ thực hiện
Hoàn tất nhúng Icon `app_icon.ico` tuyệt đối vào header của tệp thực thi `dist/ZFPlayer.exe` và tạo bản sao `dist/ZFPlayer_v1.0.exe` để bỏ qua bộ nhớ đệm IconCache của Windows Explorer.

### Danh sách tệp tin tạo mới & thay đổi
- `zfplayer.spec` (MODIFIED)
- `build_exe.py` (MODIFIED)
- `dist/ZFPlayer_v1.0.exe` (NEW)

### Mô tả chi tiết kỹ thuật
1. **Xử lý Windows Explorer Icon Cache (`IconCache.db`)**:
   - Icon đã được nhúng thành công 100% vào tệp binary của Windows qua PyInstaller.
   - Tạo file `dist/ZFPlayer_v1.0.exe` để Windows Explorer đọc lại icon mới thay vì dùng ảnh đệm cũ của `dist/ZFPlayer.exe`.

---

## Timestamp: 2026-08-13T17:17:20
### Tác vụ thực hiện
Tạo tệp Icon ứng dụng `app_icon.ico` với chữ "ZFP" chuẩn đa độ phân giải và đóng gói lại tệp thực thi duy nhất `dist/ZFPlayer.exe`.

### Danh sách tệp tin tạo mới & thay đổi
- `generate_icon.py` (NEW)
- `app_icon.ico` (NEW)
- `zfplayer.spec` (MODIFIED)
- `build_exe.py` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Tạo Icon Đa Độ Phân Giải (`generate_icon.py`, `app_icon.ico`)**:
   - Sử dụng Pillow vẽ icon chất lượng cao 512x512 thiết kế chuẩn Apple Glassmorphism với chữ "ZFP" màu trắng sáng trên nền tối `#121318`, có hiệu ứng viền phát sáng (Glow border) và 3 nốt chấm âm thanh bên dưới.
   - Đóng gói file `app_icon.ico` chứa đầy đủ 6 độ phân giải chuẩn của Windows: `16x16`, `32x32`, `48x48`, `64x64`, `128x128`, `256x256`.
2. **Cấu hình Icon & Rebuild PyInstaller (`zfplayer.spec`, `build_exe.py`)**:
   - Bổ sung `icon='app_icon.ico'` vào khối `EXE()` trong `zfplayer.spec`.
   - Bổ sung logic tự dọn dẹp file `.exe` cũ trước khi build trong `build_exe.py`.
   - Biên dịch thành công tệp đơn duy nhất [`dist/ZFPlayer.exe`](file:///d:/ZFPlayer/dist/ZFPlayer.exe).

---

## Timestamp: 2026-08-13T17:14:30
### Tác vụ thực hiện
Tắt chế độ DevTools window tự nảy khi khởi chạy ứng dụng PyWebView và chuyển cấu hình PyInstaller sang đóng gói Đơn Tệp (--onefile).

### Danh sách tệp tin thay đổi
- `backend/app.py` (MODIFIED)
- `zfplayer.spec` (MODIFIED)
- `build_exe.py` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Tắt chế độ DevTools (`backend/app.py`)**:
   - Chuyển `webview.start(debug=True)` thành `debug_mode = "--debug" in sys.argv or os.environ.get("ZFPLAYER_DEBUG") == "1"`.
   - Giúp ứng dụng khi mở chỉ hiển thị cửa sổ giao diện chính của ZeroFLAC Player, không bị nảy cửa sổ Edge DevTools (`DevTools - 127.0.0.1:...`).
2. **Cấu hình Đóng gói Đơn Tệp `--onefile` (`zfplayer.spec`, `build_exe.py`)**:
   - Cập nhật khối `EXE()` trong `zfplayer.spec` gom trực tiếp `a.binaries`, `a.zipfiles`, và `a.datas` vào 1 file thực thi duy nhất.
   - Loại bỏ khối `COLLECT()`.
   - Cập nhật `build_exe.py` trỏ và kiểm tra đầu ra tại `dist/ZFPlayer.exe`.

---

## Timestamp: 2026-08-13T17:10:00
### Tác vụ thực hiện
Đóng gói ZFPlayer thành ứng dụng EXE tự chạy bằng PyInstaller & Tích hợp Windows System Media Transport Controls (SMTC).

### Danh sách tệp tin thay đổi/tạo mới
- `backend/utils/path_utils.py` (NEW)
- `zfplayer.spec` (NEW)
- `build_exe.py` (NEW)
- `backend/app.py` (MODIFIED)
- `backend/storage/config.py` (MODIFIED)
- `backend/storage/database.py` (MODIFIED)
- `backend/storage/cache.py` (MODIFIED)
- `frontend/js/player.js` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Hệ thống Quản lý Đường dẫn Linh hoạt (`path_utils.py`)**:
   - Tự động nhận diện môi trường ứng dụng: khi chạy dưới dạng gói PyInstaller (`sys.frozen`), `PROJECT_ROOT` chuyển sang `sys._MEIPASS` để phục vụ các tệp giao diện web `frontend/`.
   - Chuyển hướng lưu trữ dữ liệu người dùng (`library.db`, `config.json`, `cache/`) sang `%APPDATA%\ZFPlayer` nhằm tránh lỗi phân quyền ghi đĩa cứng khi cài ứng dụng vào `C:\Program Files\`.
2. **Windows System Media Transport Controls (SMTC) & Media Keys (`player.js`)**:
   - Khởi tạo đồng bộ `navigator.mediaSession` trong WebView2 Chromium.
   - Cập nhật thông tin `MediaMetadata` (Tên bài, Ca sĩ, Album, Cover Art) và `playbackState` (`playing`/`paused`) khi chuyển bài/phát/dừng.
   - Đăng ký `setActionHandler` cho các sự kiện phím Multimedia phần cứng Windows (`play`, `pause`, `previoustrack`, `nexttrack`, `seekto`).
3. **Cấu hình Đóng gói & Kịch bản Build (`zfplayer.spec`, `build_exe.py`)**:
   - Thiết lập PyInstaller spec bao gồm đầy đủ folder `frontend/`, C-DLLs của `soundfile` (`libsndfile`) và `sounddevice`.
   - Cấu hình `console=False` để ẩn hoàn toàn cửa sổ CMD khi người dùng mở ứng dụng.
   - Script `build_exe.py` thực thi đóng gói thành công tệp thực thi `dist/ZFPlayer/ZFPlayer.exe`.

---

## Timestamp: 2026-08-13T16:55:50
### Tác vụ thực hiện
Khắc phục triệt để lỗi câu lyric dài bị lẹm / cắt chữ và quầng sáng glow mép phải trên giao diện Lyrics Overlay.

### Danh sách tệp tin thay đổi
- `frontend/css/lyrics.css` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Khống chế Chiều Rộng & Ngắt Dòng Tự Động (`lyrics.css`)**:
   - Bổ sung `max-width: calc(100% - 60px)` (và `70px`/`80px` trên màn hình lớn) cho `.lyrics-line` để luôn chừa vùng đệm an toàn chiều ngang.
   - Thêm `word-wrap: break-word; overflow-wrap: break-word; white-space: normal;` giúp các câu lyric siêu dài tự động ngắt dòng tự nhiên mà không bao giờ vượt qua mép khung hiển thị.
2. **Mở Rộng Không Gian & Vùng Đệm An Toàn**:
   - Thu hẹp khoảng cách `gap` giữa cột track info và cột lyric từ `10%` xuống `6%` trong `.lyrics-overlay-container`.
   - Tăng `padding-right` của `.lyrics-container` từ `80px` lên `100px`, đồng thời điều chỉnh `transform: scale(1.05)` (thay vì `1.08`), đảm bảo cả nét chữ và quầng tỏa sáng `text-shadow: 0 0 35px` nằm hoàn toàn trong vùng hiển thị an toàn.
3. **Chuẩn Hóa Font-Size Tương Thích Nhiều Màn Hình**:
   - Màn hình thường (<1400px): `32px` (tinh chỉnh từ 36px).
   - Màn hình lớn (>=1400px): `40px` (từ 46px).
   - Màn hình 4K (>=1800px): `48px` (từ 54px).

---

## Timestamp: 2026-08-13T16:55:00
### Tác vụ thực hiện
Loại bỏ ô vuông nền đen (`<rect fill="#181818">`) phía sau biểu tượng SVG của All Songs & Favorite Songs trên Trang chủ và Trang chi tiết Playlist.

### Danh sách tệp tin thay đổi
- `frontend/js/playlists.js` (MODIFIED)
- `frontend/js/home.js` (MODIFIED)
- `frontend/index.html` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Loại bỏ thẻ `<rect fill="#181818">`**:
   - Xóa bỏ hoàn toàn thẻ vẽ hình chữ nhật nền màu đen trong mã `svgContent` data URL của `playlists.js`. Giờ đây cả nốt nhạc đôi và trái tim đặc trắng là các đường nét vector trên nền hoàn toàn trong suốt (100% transparent).
2. **Transparent Cover Container**:
   - Cập nhật `bg: 'transparent'` trong `home.js` cho 2 playlist hệ thống, đảm bảo không bị khung ô vuông màu đen bao quanh icon khi hiển thị ở Trang chủ.
3. **Cache-Buster**: Nâng version cache buster lên `?v=26`.

---

## Timestamp: 2026-08-13T16:48:00
### Tác vụ thực hiện
Đồng bộ hoàn toàn biểu tượng vector SVG đơn sắc màu trắng cho All Songs và Favorite Songs trên toàn bộ các giao diện (Sidebar, Trang chủ, Trang chi tiết).

### Danh sách tệp tin thay đổi
- `frontend/js/playlists.js` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)
- `frontend/css/main.css` (MODIFIED)
- `frontend/index.html` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Đồng bộ hóa biểu tượng SVG vector**:
   - Thống nhất mã đường dẫn `d` của biểu tượng **All Songs** là nốt nhạc đôi stroke trắng (`M9 18V5l12-2v13 M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z`) và **Favorite Songs** là trái tim đặc fill trắng (`M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z`).
2. **Loại bỏ ảnh ô vuông viền trắng cũ trên Sidebar**:
   - Loại bỏ đoạn mã fallback kiểm tra `allCover ? ...` / `favCover ? ...` trong `playlists.js` để Sidebar luôn luôn render biểu tượng SVG vector trắng mượt mà, không bao giờ dùng các tệp ảnh ô vuông viền trắng cũ.
   - Thêm quy tắc CSS `.library-list li .icon-placeholder.system-icon` với `background-color: transparent !important` và `border: none !important`.
3. **Cache-Buster**: Nâng version cache buster lên `?v=25`.

---

## Timestamp: 2026-08-13T16:38:30
### Tác vụ thực hiện
Tối ưu hóa phản hồi hiển thị lời bài hát (Optimistic UI Update) khi người dùng click vào dòng Lyric để seek âm thanh.

### Danh sách tệp tin thay đổi
- `frontend/js/player.js` (MODIFIED)
- `frontend/js/lyrics.js` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Optimistic UI Update Trong `player.js`**:
   - Thay đổi phương thức `seek(seconds)`: Đồng bộ trạng thái `ticker` (`ticker.sync`) và gọi `updateSeekUI` ngay lập tức tại thời điểm xảy ra sự kiện click (0ms latency), thay vì chờ kết quả từ lệnh IPC `await window.api.seek(seconds)`.
   - Bổ sung cờ thời gian `this.lastSeekTime`: Vô hiệu hóa việc ghi đè vị trí từ luồng polling ngầm `startSyncLoop` trong vòng 1.5 giây sau khi seek, giúp tránh tình trạng lyric bị giật lùi về vị trí cũ trước khi backend kịp phát âm thanh tại mốc thời gian mới.
2. **Xử Lý Tức Thì Trong `lyrics.js`**:
   - Cập nhật sự kiện `click` trên mỗi dòng `.lyrics-line`: Kích hoạt ngay lập tức `this.update(line.time)` để tự động nhảy dòng active và cuộn vị trí `scrollToLine()` smooth scroll ngay tại frame click đầu tiên.
   - Hỗ trợ mốc thời lượng `line.time >= 0` thay vì điều kiện loại trừ `line.time > 0`.

---

## Timestamp: 2026-08-13T16:28:00
### Tác vụ thực hiện
Viết lại toàn bộ `README.md` và `docs/ARCHITECTURE.md` (`architect.md`) chuẩn hóa cấu trúc hệ thống, 5 luồng dữ liệu cốt lõi và các yêu cầu kỹ thuật chuyên sâu.

### Danh sách tệp tin thay đổi
- `README.md` (MODIFIED)
- `docs/ARCHITECTURE.md` (MODIFIED)
- `architect.md` (CREATED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Chuẩn hóa `README.md`**: Cập nhật mô tả dự án, 4 nhóm tính năng nổi bật (WASAPI Shared Mode, Glassmorphic UI, Synced Lyrics 4-level fallback, VirtualList 60fps), công nghệ sử dụng, cấu trúc thư mục và hướng dẫn cài đặt/sử dụng đầy đủ không có icon thừa.
2. **Chi Tiết Luồng Hệ Thống (`docs/ARCHITECTURE.md` & `architect.md`)**: Mô tả chi tiết 5 luồng dữ liệu cốt lõi (Khởi chạy IPC/REST Bridge, Giải mã & Phát nhạc PCM Zero-Latency, Quét nhạc ngầm & FTS5 Indexing, Priority Queue Synced Lyrics 4 cấp, Frontend State & Virtual Scrolling) chia làm 2 mục: Công nghệ/Module sử dụng và Quy trình xử lý từng bước.
3. **Bổ Sung Yêu Cầu Kỹ Thuật Chuyên Sâu**: Xây dựng bảng quy chuẩn kỹ thuật đầy đủ bao gồm: Phần cứng & OS (Windows 10/11 64-bit, RAM Caching), Thư viện phụ thuộc C-level (`sounddevice`, `soundfile`, `numpy`), Cơ sở dữ liệu WAL Mode & chỉ mục FTS5, Thuật toán Virtual Scrolling math (`scrollTop - offsetTop`), Quy tắc đa luồng & cách ly Thread an toàn (Non-blocking audio thread callback, Single-thread Priority Queue throttle 0.5s), và các chỉ số SLA (0ms seek latency, CPU Idle < 0.5%).

---

## Timestamp: 2026-08-13T16:08:15
### Tác vụ thực hiện
Tối ưu hóa và cải thiện toàn bộ hệ thống Animation (Refine & Streamline Animations) theo chuẩn giao diện Apple Music & Spotify.

### Danh sách tệp tin thay đổi
- `frontend/css/main.css` (MODIFIED)
- `frontend/css/library.css` (MODIFIED)
- `frontend/css/albums.css` (MODIFIED)
- `frontend/css/lyrics.css` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Tinh chỉnh Design Tokens & Curves (`main.css`)**:
   - Thay thế các đường cung nảy `--ease-spring` (overshoot 1.56) bằng đường cong chuẩn macOS/iOS `cubic-bezier(0.2, 0.9, 0.3, 1)` và `cubic-bezier(0.16, 1, 0.3, 1)`.
   - Rút ngắn thời gian phản hồi micro-interactions từ 180-350ms xuống 150ms-250ms tức thì.
   - Thêm GPU rendering hints (`will-change: transform, opacity`) cho Modals, Context Menus, View Containers.
2. **Cắt bỏ các hiệu ứng thừa (`main.css`, `library.css`, `albums.css`, `lyrics.css`)**:
   - Loại bỏ `translateX(3px)` khi hover item Sidebar (giữ vị trí cố định chống lệch con trỏ).
   - Loại bỏ xoay 90 độ (`rotate(-90deg)`) nút đóng Lyrics màn hình overlay.
   - Loại bỏ transform nảy trên `.track-row` và thu gọn biên độ scale hình ảnh bìa Album/Playlist (`scale(1.08)` ➔ `scale(1.04)`).
3. **Bổ sung View Fade Transition (`main.css`, `ui.js`)**:
   - Thêm class `.active-view-fade` với animation `viewFadeIn 180ms` khi người dùng chuyển đổi giữa Trang chủ, Bài hát, Albums, Playlists.
4. **Tối ưu Synced Lyrics & Overlay (`lyrics.css`)**:
   - Rút ngắn thời gian xuất hiện Lyrics Overlay từ 450ms xuống 300ms.
   - Cuộn vị trí `#lyrics-content` trong 350ms mượt mà và zoom nhẹ câu hát active 300ms.

---

## Timestamp: 2026-08-13T15:53:30
### Tác vụ thực hiện
Triển khai Background Priority Queue Tải Lời Bài Hát Ngầm với Throttle loại bỏ hoàn toàn tình trạng tụt giảm hiệu năng khi Import lượng bài hát lớn.

### Danh sách tệp tin thay đổi
- `backend/workers/lyrics_worker.py` (MODIFIED)
- `backend/workers/scanner.py` (MODIFIED)
- `backend/services/library_service.py` (MODIFIED)
- `backend/services/player_service.py` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Background Priority Queue (`lyrics_worker.py`)**:
   - Sử dụng `queue.PriorityQueue` với 1 worker thread duy nhất (`_queue_loop`) tiêu thụ hàng đợi tuần tự ngầm.
   - Thêm `throttle_delay=0.5s` giữa mỗi request để chống quá tải API và triệt tiêu SQLite write lock contention.
   - Hỗ trợ phân cấp ưu tiên: `priority=True` (Priority 1) cho bài đang phát / sắp phát, `priority=False` (Priority 10) cho bài vừa import.
   - Lọc trùng lặp bài hát (`_queued_keys`) và kiểm tra nhanh DB cache trước khi tải.
2. **Loại Bỏ ThreadPool 4 Luồng Khi Import (`scanner.py` & `library_service.py`)**:
   - Thay thế việc gọi `ThreadPoolExecutor(max_workers=4)` dồn dập trong lúc scan bằng phương thức `lyrics_worker.enqueue_tracks(tracks, priority=False)`.
3. **Ưu Tiên Lời Cho Bài Đang Phát (`player_service.py`)**:
   - Khi phát nhạc hoặc chuyển bài, tự động đẩy bài hát hiện tại và 5 bài tiếp theo vào Queue với `priority=True`.

---

## Timestamp: 2026-08-13T15:41:00
### Tác vụ thực hiện
Dọn dẹp sạch toàn bộ cơ sở dữ liệu (`library.db`) và chạy VACUUM tối ưu đĩa.

### Danh sách tệp tin thay đổi
- `data/library.db` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Dọn Dẹp Bản Ghi CSDL (`library.db`)**: Thực thi xóa toàn bộ dữ liệu trong các bảng `playlist_tracks`, `playlists`, `tracks`, `lyrics_cache`.
2. **Tối Ưu Dung Lượng Đĩa (`VACUUM`)**: Thực hiện lệnh `VACUUM` để tái cấu trúc và giải phóng bộ nhớ lưu trữ vật lý của tệp SQLite.
3. **Kiểm Chứng Dữ Liệu**: Số lượng bản ghi trong toàn bộ các bảng xác nhận đã về `0`.

---

## Timestamp: 2026-08-13T15:40:00
### Tác vụ thực hiện
Tái cấu trúc và áp dụng thứ tự 4 cấp ưu tiên nguồn tải Lyric bài hát trong LyricsWorker.

### Danh sách tệp tin thay đổi
- `backend/workers/lyrics_worker.py` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Cấu Trúc Thứ Tự Nguồn Lyric Mới (`lyrics_worker.py`)**:
   - **Ưu tiên 1 (`local_lrc`)**: Quét tệp `.lrc` cục bộ cùng thư mục & cùng tên với bài hát.
   - **Ưu tiên 2 (`lrclib_search`)**: Gọi API LRCLIB Search (`/api/search`), chọn bản dịch khớp nhất với thời lượng (ngưỡng chênh lệch \(\le 3.0\) giây, thử tối đa 2 lần).
   - **Ưu tiên 3 (`embedded_tag`)**: Đọc thẻ nhúng trực tiếp trong file âm thanh (FLAC/MP3).
   - **Ưu tiên 4 (`syncedlyrics`)**: Tìm kiếm qua các nhà cung cấp trực tuyến Musixmatch ➔ NetEase ➔ Megalobiz (thử tối đa 2 lần).

---

## Timestamp: 2026-08-13T15:32:00
### Tác vụ thực hiện
Sửa lỗi tính năng tìm kiếm (Search) ở Trang chủ (Home View) không hoạt động.

### Danh sách tệp tin thay đổi
- `frontend/js/library.js` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Chuyển View Tự Động Khi Tìm Kiếm (`library.js`)**: Cập nhật sự kiện `input` trên `#search-input`. Khi người dùng gõ từ khóa tìm kiếm trong khi đang ở Trang chủ (`view === 'home'`) hoặc Albums View (`view === 'albums'`), ứng dụng tự động chuyển view sang `'songs'` (`playlistId = 'all'`) và tiến hành lọc danh sách toàn bộ bài hát theo từ khóa tìm kiếm. Hỗ trợ thêm phím `Escape` để xóa nhanh từ khóa.
2. **Làm Sạch Tìm Kiếm Khi Quay Về Trang Chủ (`ui.js`)**: Khi người dùng bấm về Trang chủ (`view === 'home'`), ô tìm kiếm `#search-input` và biến `searchQuery` sẽ tự động xóa sạch từ khóa cũ để sẵn sàng cho lần tìm kiếm mới.

---

## Timestamp: 2026-08-13T14:23:20
### Tác vụ thực hiện
Cập nhật văn bản mô tả Audio Engine trong Settings Modal thành WASAPI Shared Mode.

### Danh sách tệp tin thay đổi
- `frontend/index.html` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Settings Modal (`index.html`)**: Cập nhật dòng mô tả cơ chế âm thanh thành `"WASAPI Shared Mode + Zero-Latency RAM Playback (Ultra Smooth 0% Disk I/O)"` để phản ánh đúng 100% cấu hình backend đang sử dụng.

---
### Tác vụ thực hiện
Chuẩn hóa 100% văn bản Tiếng Anh cho toàn bộ giao diện (Clean Remaining Vietnamese Strings).

### Danh sách tệp tin thay đổi
- `frontend/js/home.js` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Trang Chủ (home.js)**: Chuyển đổi phụ đề của các thẻ Playlist: `"Tất cả bài hát"` ➔ `"All your local tracks"`, `"Bài hát yêu thích"` ➔ `"Your favorite tracks"`, thẻ tạo mới `"Tạo danh sách mới"` ➔ `"Create a new playlist"`, và thông báo trống `"Chưa có bài hát nào được phát gần đây."` ➔ `"No recently played tracks yet."`.
2. **Thanh bên (ui.js)**: Chuyển đổi phụ đề danh sách phát hệ thống Sidebar `"Tất cả bài hát"` ➔ `"All your local tracks"`, `"Bài hát yêu thích"` ➔ `"Your favorite tracks"`.

---
### Tác vụ thực hiện
Sửa lỗi lưu và đồng bộ trạng thái âm lượng (Volume State Persistence & Synchronization Fix).

### Danh sách tệp tin thay đổi
- `backend/services/player_service.py` (MODIFIED)
- `frontend/js/main.js` (MODIFIED)
- `frontend/js/player.js` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Khởi Tạo Âm Lượng Backend (`player_service.py`)**: Tự động lấy giá trị âm lượng lưu từ `config.json` (`config.get('volume', 0.8)`) và thiết lập cho `AudioEngine` ngay khi tạo service.
2. **Khôi Phục Trạng Thái Âm Lượng Frontend (`main.js`)**: Chuẩn hóa giá trị âm lượng dạng phần trăm (0–100%), thiết lập lại slider và thuộc tính CSS custom `--progress` trên cả 2 thanh âm lượng (`#volume-bar` và `#lyrics-volume-bar`) khi tải ứng dụng.
3. **Đồng Bộ Hai Chiều Slider (`player.js`)**: Cập nhật hàm `updateVolUI` để đồng bộ mượt mà giá trị `.value` và `--progress` giữa các slider ở thanh điều khiển chính và màn hình lời bài hát.

---
### Tác vụ thực hiện
Xóa nút 3 chấm ở Màn hình Lời bài hát & Kích hoạt các tính năng Context Menu ("Play Next", "Go to Album", "Go to Artist").

### Danh sách tệp tin thay đổi
- `backend/services/player_service.py` (MODIFIED)
- `backend/api/player_api.py` (MODIFIED)
- `frontend/js/api.js` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)
- `frontend/js/home.js` (MODIFIED)
- `task.md` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Xóa Nút 3 Đấm Màn Hình Lời Bài Hát**: Loại bỏ hoàn toàn phần tử `#lyrics-more-btn` trong `index.html` trên màn hình xem lời nhạc đồng bộ.
2. **Kích hoạt Nút 3 Đấm ở Playlist / Track List**: Thêm xử lý sự kiện click `.track-more` và right-click trên danh sách bài hát Trang chủ (`home.js`) và Thư viện (`library.js`), mở menu ngữ cảnh `#context-menu`.
3. **Triển khai Tính năng Context Menu**:
   - `Play Next`: Thêm phương thức `insert_play_next` trong `player_service.py` và API `play_next` để chèn bài hát được chọn phát tiếp theo.
   - `Go to Album`: Tự động tìm kiếm theo tên Album và chuyển sang màn hình Albums view.
   - `Go to Artist`: Tự động tìm kiếm theo tên Ca sĩ và chuyển sang màn hình Thư viện bài hát.

---

### Danh sách tệp tin thay đổi
- rontend/index.html (MODIFIED)
- rontend/js/playlists.js (MODIFIED)
- 	ask.md (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Modals & Context Menus (index.html)**: Chuyển đổi toàn bộ các văn bản tiếng Việt sang Tiếng Anh: Edit Playlist, Change Cover Image, Playlist Name:, Delete Playlist, Save Changes, Cancel, Rename Playlist, Confirm Playlist Deletion.
2. **Tooltips & Subtitles (playlists.js, index.html)**: Chuyển đổi subtitles sidebar (All your local tracks, Your favorite tracks), các tiêu đề trang chủ (Playlists, Recently Played (Last 20)), trạng thái nút bấm (Scanning..., Processing...) và thông báo cảnh báo xóa sang Tiếng Anh đồng bộ.

---

## Timestamp: 2026-08-13T13:39:38.149184
### Tác vụ thực hiện
Fix lỗi cú pháp JavaScript SyntaxError unexpected token ')' trong playlists.js.

### Danh sách tệp tin thay đổi
- rontend/js/playlists.js (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. Sửa thiếu đóng ngoặc nhọn } tại khối else gán svgContent trong phương thức init(), giải quyết triệt để lỗi syntax khi tải file playlists.js trên browser console.

---

## Timestamp: 2026-08-13T13:37:34.202788
### Tác vụ thực hiện
Ẩn 2 nút 'IMPORT FOLDER' và 'SELECT FILES' trên Playlist Header đối với riêng playlist Favorite Songs.

### Danh sách tệp tin thay đổi
- rontend/js/playlists.js (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. Trong PlaylistManager.init() (lắng nghe sự kiện đổi view playlist), kiểm tra nếu state.playlistId === 'favorites', thiết lập display: none cho #btn-playlist-import-folder và #btn-playlist-import-files.
2. Với các playlist khác (ll và custom playlists), duy trì hiển thị inline-flex như bình thường.

---

## Timestamp: 2026-08-13T13:34:20.100571
### Tác vụ thực hiện
Tối ưu giao diện Playlist Header: Thay thế 3 nút chức năng riêng lẻ bằng 1 Nút Bánh Răng duy nhất mở Modal Popup 'Chỉnh sửa Playlist' hợp nhất.

### Danh sách tệp tin thay đổi
- rontend/index.html (MODIFIED)
- rontend/js/playlists.js (MODIFIED)
- 	ask.md (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Playlist Header (index.html)**: Rút gọn 3 nút riêng biệt (Đổi tên, Đổi ảnh, Xóa) thành 1 nút Bánh Răng duy nhất (#btn-playlist-edit-header, icon ⚙️).
2. **Edit Playlist Modal (#edit-playlist-modal)**: Tạo view chỉnh sửa tập trung bao gồm Preview Bìa + Nút đổi ảnh bìa, Ô nhập tên Playlist, và Nút màu đỏ Xóa Playlist.
3. **Logic Handler (playlists.js)**: Nhấp nút Bánh Răng nạp dữ liệu của Playlist hiện tại vào Modal Edit. Xử lý đồng thời cả Đổi tên, Đổi ảnh bìa và Xác nhận xóa trong một giao diện nhất quán.

---

## Timestamp: 2026-08-13T13:29:08.909114
### Tác vụ thực hiện
Triển khai tính năng quản lý Custom Playlist (Đổi tên, Đổi ảnh đại diện, Xóa Playlist) trên giao diện Header và Sidebar Context Menu.

### Danh sách tệp tin thay đổi
- rontend/index.html (MODIFIED)
- rontend/css/main.css (MODIFIED)
- rontend/js/api.js (MODIFIED)
- rontend/js/playlists.js (MODIFIED)
- ackend/api/library_api.py (MODIFIED)
- ackend/services/library_service.py (MODIFIED)
- 	ask.md (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **HTML & Modals (index.html)**: Thêm các nút thao tác trên Playlist Header (#btn-playlist-rename-header, #btn-playlist-cover-header, #btn-playlist-delete-header), Modal Đổi tên (#rename-playlist-modal), Modal Xác nhận Xóa (#delete-playlist-modal), và Menu chuột phải Sidebar (#playlist-item-context-menu).
2. **CSS Styles (main.css)**: Thêm kiểu dáng .btn-icon-large và .context-menu-item.danger cho các nút bấm hành động và menu xóa màu đỏ với Bezier Curves.
3. **Frontend Logic (playlists.js)**: Bắt sự kiện contextmenu trên playlist sidebar item, mở Modal Đổi tên và Modal Cảnh báo Xóa, gọi các API 
enamePlaylist, deletePlaylist, updatePlaylistCover. Tự động bảo vệ danh sách hệ thống (ll, avorites) chỉ cho đổi ảnh bìa, khóa nút Đổi tên/Xóa.
4. **Backend API (library_service.py, library_api.py)**: Nâng cấp update_playlist_cover lưu ảnh bìa cho system playlists vào Config và hỗ trợ cả int/str playlist IDs.

---

## Timestamp: 2026-08-13T13:21:24.617011
### Tác vụ thực hiện
Sửa lỗi hiển thị trào lẹm và xô lệch khung của Sidebar khi thu nhỏ (Collapsed 72px state).

### Danh sách tệp tin thay đổi
- rontend/css/main.css (MODIFIED)
- 	ask.md (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **#sidebar.collapsed CSS Fix (main.css)**:
   - Ẩn hoàn toàn .library-list-text, .library-list-title, .library-list-subtitle, .library-filters, .library-actions, .library-title span bằng display: none !important khi thu nhỏ Sidebar.
   - Căn giữa 100% cho các thành phần bên trong .library-header-bar và .library-list li (justify-content: center, padding: 8px 0, margin: 0 auto).
   - Sửa hiệu ứng hover ở dạng thu nhỏ: đổi từ 	ransform: translateX(3px) (gây lẹm mép phải) sang 	ransform: scale(1.05) gọn gàng và thẩm mỹ.

---

## Timestamp: 2026-08-13T13:17:33.265642
### Tác vụ thực hiện
Nâng cấp toàn bộ hệ thống chuyển động UI/UX bằng đường cong Bezier (Bezier Curve Motion Design System).

### Danh sách tệp tin thay đổi
- rontend/css/main.css (MODIFIED)
- rontend/css/player.css (MODIFIED)
- rontend/css/lyrics.css (MODIFIED)
- rontend/css/library.css (MODIFIED)
- rontend/css/albums.css (MODIFIED)
- 	ask.md (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Design System Curve Tokens (main.css)**: Khai báo các hằng số đường cong cubic-bezier chuyên nghiệp (--ease-out-quint, --ease-out-expo, --ease-spring, --ease-spring-soft, --ease-in-out-smooth) và các biến transition có thời gian & đường cong phanh mượt.
2. **Core Layout & Components (main.css)**: Nâng cấp hiệu ứng nảy nhẹ & phanh mượt cho Sidebar collapse/expand, Top Bar Nav Buttons, Search Container focus/hover, Filter Chips, Seekbar/Volume slider thumb expansion, Buttons (Primary, Outline, Ghost) và keyframe animations cho Modal (ackdropFadeIn, modalScaleUp) & Context Menu (contextMenuPop).
3. **Player Bar (player.css)**: Áp dụng spring bounce curves cho nút Play/Pause vòng tròn (.btn-play-pause-circle), Like button, và hiệu ứng zoom ảnh bìa bài hát đang phát.
4. **Lyrics Overlay & Text Scrolling (lyrics.css)**: Nâng cấp trượt xuất hiện Lyrics Overlay bằng --ease-out-expo, Close button nảy xoay góc -90deg, hiệu ứng cuộn lời bài hát #lyrics-content lướt êm ái với cubic-bezier(0.16, 1, 0.3, 1), và dòng chữ active nâng cấp hiệu ứng scale 1.08 + dreamy glow text-shadow + blur focus.
5. **Library & Album Grid (library.css, lbums.css)**: Thêm hiệu ứng hover slide/highlight cho track rows, nút Play lớn, playlist cover zoom và album card elevation 	ranslateY(-4px) với spring bounce curves.

---

## Timestamp: 2026-08-12T21:24:00+07:00
### Tác vụ thực hiện
Dọn sạch toàn bộ dữ liệu trong cơ sở dữ liệu `library.db`.

### Danh sách tệp tin thay đổi
- `data/library.db` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. Thực hiện xóa toàn bộ dữ liệu từ các bảng `tracks`, `playlists`, `playlist_tracks`, `lyrics_cache` trong tệp `d:\ZFPlayer\data\library.db`.
2. Chạy lệnh `VACUUM` để thu hồi dung lượng tệp SQLite và đưa cấu trúc database về trạng thái rỗng ban đầu.
3. Xác minh số lượng bản ghi bằng 0 cho tất cả các bảng.

---

## Timestamp: 2026-08-11T13:25:00+07:00
### Tác vụ thực hiện
Tối ưu hóa hiệu năng ứng dụng (Scanner, Audio Engine, Virtual Scrolling).

### Danh sách tệp tin thay đổi
- `backend/workers/scanner.py` (MODIFIED)
- `backend/audio/engine.py` (MODIFIED)
- `frontend/js/library.js` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Scanner (`scanner.py`)**: Sửa vòng lặp quét file thành dạng gom lô (batching). Thay vì gọi `database.insert_track` cho từng track một làm tăng overhead I/O của SQLite, giờ đây mỗi 100 track được gom vào một list và gọi `database.bulk_insert_tracks`.
2. **Audio Engine (`engine.py`)**: Rút trích logic kiểm tra kiểu dữ liệu audio (`np.dtype`) thành một biến boolean `self._is_int_dtype` tính toán sẵn lúc `load()` bài hát. Điều này làm giảm hàng ngàn phép so sánh bên trong hàm `_audio_callback` mỗi giây khi `volume != 1.0`, tiết kiệm CPU chu kỳ.
3. **Frontend Virtual List (`library.js`)**: Viết lại hoàn toàn class `VirtualList` để sử dụng kĩ thuật DOM Pooling. Thay vì liên tục tạo phần tử mới và hủy phần tử cũ khi user cuộn (scroll), hệ thống sẽ khởi tạo một số lượng DOM node cố định che kín màn hình, sau đó dịch chuyển và cập nhật nội dung qua `transform: translateY`. Thay đổi này giúp giảm hẳn áp lực lên Garbage Collector của trình duyệt, đem lại trải nghiệm cuộn mượt mà ở 60fps. Đồng thời sử dụng Event Delegation để gắn listener cho các hàng list thay vì gắn cho từng dòng.

---

## Timestamp: 2026-08-11T15:45:00+07:00
### Tác vụ thực hiện
Sửa lỗi tính năng bấm F11 toàn màn hình & tối ưu giao diện.

### Danh sách tệp tin thay đổi
- `backend/app.py` (MODIFIED)
- `frontend/js/api.js` (MODIFIED)
- `frontend/js/main.js` (MODIFIED)
- `frontend/css/lyrics.css` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Sửa F11 Fullscreen**:
   - Thêm phương thức `toggle_fullscreen` vào class API thống nhất `ZFPlayerAPI` trong `backend/app.py` để gọi trực tiếp `webview.windows[0].toggle_fullscreen()`.
   - Khai báo ánh xạ `toggleFullscreen()` trong `ApiWrapper` ([api.js](file:///d:/ZFPlayer/frontend/js/api.js)).
   - Sửa trình lắng hệ phím F11 trong [main.js](file:///d:/ZFPlayer/frontend/js/main.js) gọi đúng hàm `window.api.toggleFullscreen()`.
2. **Tối ưu cỡ phần bên trái**: Giảm tỷ lệ flex từ 45% xuống 35% và giảm max-width ảnh bìa giúp tổng thể phần lời bên phải thoáng hơn.

---

## Timestamp: 2026-08-11T22:24:00+07:00
### Tác vụ thực hiện
Thêm nút "Thêm Album" (tự động tải lyrics lưu DB) và 2 Playlist mặc định ("All Songs", "Favorite Songs").

### Danh sách tệp tin thay đổi
- `backend/storage/database.py` (MODIFIED)
- `backend/services/library_service.py` (MODIFIED)
- `backend/app.py` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Tự động tải Lyrics khi Thêm Album/Folder**:
   - Nâng cấp `LibraryService` nhận thêm `lyrics_worker` và định nghĩa hàm `_prefetch_all_lyrics()`. Ngay khi tiến trình quét file hoàn tất, ứng dụng tự động tải trước lời nhạc ngầm cho toàn bộ các bài hát chưa có trong `lyrics_cache` DB.
2. **Playlist Mặc Định All Songs & Favorite Songs**:
   - Nâng cấp `database.py` (`get_tracks_paginated`, `get_track_count`, `get_all_track_paths`) hỗ trợ `playlist_id = 'all'` (lấy toàn bộ) và `playlist_id = 'favorites'` (lọc `is_liked = 1`).
   - Cập nhật [ui.js](file:///d:/ZFPlayer/frontend/js/ui.js) luôn hiển thị ghim 2 playlist hệ thống này lên trên cùng danh sách Sidebar.
3. **Giao diện Thêm Album**:
   - Thêm nút **Thêm Album** với biểu tượng thư mục + dấu cộng trực tiếp ở thanh Sidebar.

---

## Timestamp: 2026-08-12T00:55:00+07:00
### Tác vụ thực hiện
Loại bỏ nút Tạo Playlist và xây dựng Modal Thêm Album Tùy Chỉnh.

### Danh sách tệp tin thay đổi
- `backend/api/config_api.py` (MODIFIED)
- `backend/api/library_api.py` (MODIFIED)
- `backend/services/library_service.py` (MODIFIED)
- `backend/storage/database.py` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `frontend/js/api.js` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)

---

## Timestamp: 2026-08-12T01:14:00+07:00
### Tác vụ thực hiện
Tối ưu hóa độ nhạy và tốc độ phản hồi của thanh tua thời gian (Time Seekbar).

### Danh sách tệp tin thay đổi
- `frontend/index.html` (MODIFIED)
- `frontend/js/player.js` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Sửa thuộc tính `step` (HTML)**: Thêm `step="any"` vào `<input type="range">` của seekbar. Khắc phục tình trạng slider bị khóa vào các bước nhảy số nguyên (giật cục theo từng giây), giúp thanh trượt lướt mượt mà chuẩn xác tới từng điểm ảnh giống thanh Volume.
2. **Loại bỏ Throttled Seek**: Dừng việc gọi API tua âm thanh ngầm lúc đang giữ chuột (gây giật/nghẽn luồng Backend). Thanh trượt lúc này sẽ di chuyển trơn tru 100% bằng UI tĩnh.
3. **Mở khóa Ticker tức thì**: Sửa lỗi "đứng hình giao diện" (visual delay) khi vừa thả chuột bằng cách lập tức chuyển cờ `isDraggingSeek = false` và tái khởi động đồng hồ `ticker.sync()` độc lập, không cần phải chờ tín hiệu kết thúc từ lời gọi API `await window.api.seek()` ở Backend.

---

## Timestamp: 2026-08-12T01:25:00+07:00
### Tác vụ thực hiện
Xây dựng Màn hình Trang chủ (Home View) với tính năng ghi nhận lịch sử phát nhạc.

### Danh sách tệp tin thay đổi
- `backend/storage/database.py` (MODIFIED)
- `backend/services/library_service.py` (MODIFIED)
- `backend/services/player_service.py` (MODIFIED)
- `backend/api/library_api.py` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `frontend/css/main.css` (MODIFIED)
- `frontend/js/store.js` (MODIFIED)
- `frontend/js/api.js` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)
- `frontend/js/main.js` (MODIFIED)
- `frontend/js/home.js` (NEW)

### Mô tả chi tiết kỹ thuật
1. **Theo dõi lịch sử phát nhạc**: Bổ sung cột `last_played TIMESTAMP` vào bảng `tracks` trong SQLite. Sửa hàm `play(path)` trong `player_service.py` để mỗi lần phát nhạc sẽ ghi nhận timestamp vào DB. Bổ sung API `get_recently_played`.
2. **Giao diện Home View (`#home-view`)**: Thêm view mới kết hợp cuộn ngang thẻ ảnh bìa (horizontal scroll cards) cho các bài hát vừa nghe, và lưới hiển thị các Albums bên dưới. CSS được thiết lập ẩn thanh cuộn ngang để tối giản giao diện.
3. **Logic Home Manager**: Khởi tạo file mới `home.js` với class `HomeManager` độc lập, làm nhiệm vụ fetch data qua IPC API và đổ dữ liệu lên `#home-view`.
4. **Điều hướng (Routing)**: Cập nhật icon Home (nav-item) về đúng `data-view="home"`. Sửa đổi state mặc định ban đầu thành màn hình `home` thay vì `songs`. Sửa logic điều hướng ẩn/hiện `#home-view` bên trong `ui.js`.

---

## Timestamp: 2026-08-12T01:30:00+07:00
### Tác vụ thực hiện
Chuyển đổi tính năng "Thêm Album" trả lại thành "Tạo Danh sách phát" (Create Playlist).

### Danh sách tệp tin thay đổi
- `frontend/index.html` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Giao diện HTML**: Thay thế `#btn-sidebar-add-album` bằng `#btn-sidebar-add-playlist` với icon SVG hình dấu cộng mới phù hợp hơn với Playlist. Thay thế khối `#add-album-modal` bằng `#add-playlist-modal` nhỏ gọn, chỉ bao gồm duy nhất 1 ô nhập liệu "Tên Danh sách phát".
2. **Logic UI (`ui.js`)**: Thay thế cụm xử lý sự kiện Thêm Album sang xử lý `createPlaylist(name)`. Khi tạo thành công, modal sẽ đóng lại và UI sẽ tự động gọi hàm `loadPlaylists()` để cập nhật ngay lập tức danh sách phát mới lên Sidebar bên trái.

---

## Timestamp: 2026-08-12T01:32:00+07:00
### Tác vụ thực hiện
Thay đổi cấu trúc giao diện Trang chủ (Home View): Đưa danh sách phát (Playlists) lên trên và bài hát gần đây (Recently Played) xuống dưới.

### Danh sách tệp tin thay đổi
- `frontend/index.html` (MODIFIED)
- `frontend/js/home.js` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Thay đổi UI (`index.html`)**: Tráo đổi vị trí 2 thẻ `div` chứa lưới giao diện trong `#home-view`. Đổi tên vùng `Albums` thành `Danh Sách Phát` và chuyển ID thành `#home-playlists-grid`.
2. **Cập nhật Logic (`home.js`)**: Sửa lại class `HomeManager` để fetch danh sách các playlists thay vì albums. Dùng icon SVG động (màu đỏ cho Favorite) để biểu diễn ảnh bìa của Playlist trong giao diện thẻ ngang. Khi người dùng click vào một playlist ở trang chủ, app sẽ tự động chuyển hướng và nạp đúng playlist đó.

---

## Timestamp: 2026-08-12T01:38:00+07:00
### Tác vụ thực hiện
Nâng cấp tính năng Tạo Danh sách phát (Playlist): Bổ sung khả năng chọn thư mục tự động quét nhạc và cài đặt ảnh bìa tùy chỉnh.

### Danh sách tệp tin thay đổi
- `backend/storage/database.py` (MODIFIED)
- `backend/services/library_service.py` (MODIFIED)
- `backend/api/library_api.py` (MODIFIED)
- `frontend/index.html` (MODIFIED)
- `frontend/js/ui.js` (MODIFIED)
- `frontend/js/api.js` (MODIFIED)
- `frontend/js/home.js` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Nâng cấp CSDL (`database.py`)**: Tự động thêm 2 cột `folder_path` (đường dẫn thư mục gốc chứa nhạc) và `cover_hash` (mã băm SHA256 của ảnh bìa) vào bảng `playlists` thông qua lệnh `ALTER TABLE` tự động khi ứng dụng khởi chạy.
2. **Quét thư mục tự động (`library_service.py`)**: Khi gọi hàm `create_playlist` có kèm theo thư mục, ứng dụng sẽ chạy một luồng (thread) ngầm để: (1) Quét thư mục đó thêm vào thư viện chung nếu chưa có, (2) Tìm toàn bộ các bài hát thuộc thư mục đó, (3) Tự động chèn tất cả bài hát đó vào Playlist vừa tạo, (4) Cập nhật và lưu `cover_hash` vào hệ thống cache.
3. **Mở rộng giao diện (`ui.js` & `index.html`)**: Đưa trở lại nút chọn Thư mục (`#btn-browse-playlist-folder`) và Chọn ảnh (`#btn-browse-playlist-cover`) vào bảng Modal `#add-playlist-modal`.
4. **Hiển thị Ảnh bìa trên Trang chủ (`home.js`)**: Nếu Playlist có cài đặt ảnh bìa tùy chỉnh (tồn tại `cover_hash`), trang chủ sẽ tự động nạp thẻ `<img>` thay thế cho thẻ `<svg>` nhàm chán mặc định.

---

## Timestamp: 2026-08-12T01:42:00+07:00
### Tác vụ thực hiện
Trang trí lại giao diện Trang chủ (Home View) cho các danh sách phát.

### Danh sách tệp tin thay đổi
- `backend/services/player_service.py` (MODIFIED)
- `backend/api/player_api.py` (MODIFIED)
- `frontend/js/player.js` (MODIFIED)
- `frontend/js/library.js` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Khóa luồng phát theo Playlist (`player_service.py`)**: Phương thức `play(path, playlist_id)` lưu giữ tham số `current_playlist_id`. Hàm `_sync_playlists_and_index()` tự động lọc và truy vấn chính xác danh sách các đường dẫn bài hát thuộc duy nhất `playlist_id` đó.
2. **Hành vi Next / Prev / Auto-Next / Shuffle**:
   - Khi phát trong Playlist (ví dụ "Charlie Puth" gồm 7 bài), các thao tác chuyển bài tiếp theo / lùi lại / xáo trộn / tự động chuyển bài khi hết nhạc đều được khoanh vùng trong 7 bài của "Charlie Puth".
   - Khi `repeat: 'off'`, sau khi hát xong bài cuối cùng của Playlist, trình phát tự động dừng (`audio_engine.stop()`), không nhảy sang nhạc của Playlist khác.
## [2026-08-13] Bust PyWebView Cache
- **Files modified:** rontend/index.html`n- **Details:** Added ?v=2 query parameters to all CSS and JS imports to prevent Chromium/PyWebView from caching older versions of styles and scripts. This ensures the UI aesthetic updates and Play button logic from the previous patch are actually loaded.
## [2026-08-13] Fixed Playlist State Bug
- **Files modified:** rontend/js/playlists.js, rontend/js/library.js, rontend/index.html`n- **Details:** Fixed a state bug where clicking the 'All Songs' or 'Favorite Songs' pseudo-playlists would leave the previous playlist's header (e.g. Charlie Puth) rendered on the screen due to a missing mock object in the store.subscribe handler. Updated cache-busters to ?v=3.
## [2026-08-13] Redesign Modal UI
- **Files modified:** rontend/css/main.css, rontend/index.html`n- **Details:** Redesigned the 'Create Playlist' modal to match the dark theme and eliminate the jarring 'glassmorphism' bug that ruined text legibility. Added .text-input class to style the input box properly. Added .btn-ghost for subtle cancel buttons. Adjusted margins and gaps for a premium layout. Bumped cache buster to ?v=4.
## [2026-08-13] Global Immersive Glass UI
gba(0,0,0,0.2), 
gba(255,255,255,0.04), 
gba(255,255,255,0.08), 
gba(255,255,255,0.15)). Replaced hardcoded occurrences in library.css and main.css. This enforces a true 100% Immersive Glass UI everywhere in the app. Bumped cache to ?v=10.
## [2026-08-13] Dreamy Glow Typography

## [2026-08-13] Multi-Threaded Auto Lyrics Prefetch on Track Import & Lock-Wait Fix
- **Files modified:** `backend/workers/lyrics_worker.py`, `backend/workers/scanner.py`, `backend/services/library_service.py`, `task.md`
- **Details:** Re-architected lyrics prefetching to execute immediately upon track import/scanning. Added `threading.Condition` wait mechanism in `LyricsWorker.fetch_lyrics()` so UI requests wait up to 3.5s for ongoing background fetches to populate `lyrics_cache` instead of returning `None`. Upgraded `LibraryScanner._prefetch_lyrics_for_batch()` and `LibraryService._prefetch_all_lyrics()` to run concurrently across 4 parallel threads using `ThreadPoolExecutor(max_workers=4)`. Filtered out `Unknown` artist/title queries to prevent API rate limits.

## [2026-08-13] Wipe Database Library Data
- **Files modified:** `data/library.db`, `task.md`
- **Details:** Wiped all records from `tracks`, `playlists`, `playlist_tracks`, `lyrics_cache` tables in `d:\ZFPlayer\data\library.db` and executed `VACUUM` to return database to clean initial state. Verified 0 records across all tables.

## [2026-08-13] Enforce Strict Timestamped Synced Lyrics DB Storage & Purge Plain Text Cache
- **Files modified:** `backend/workers/lyrics_worker.py`, `data/library.db`, `task.md`
- **Details:** Upgraded `_read_embedded_lyrics()` to strictly require timestamp brackets `[mm:ss]` before treating audio tag content as synced lyrics. Embedded plain text (unsynced) lyrics are ignored so the system automatically proceeds to fetch online synced LRC lyrics from LRCLIB/Musixmatch. Purged invalid plain-text cache entries and re-fetched full synced lyrics for all tracks including "Cheating on You" (`source: lrclib_get`).

## [2026-08-13] Purge Database for User Re-testing
- **Files modified:** `data/library.db`, `task.md`
- **Details:** Wiped all records from `tracks`, `playlists`, `playlist_tracks`, `lyrics_cache` in `d:\ZFPlayer\data\library.db` and executed `VACUUM` to leave DB completely empty for user re-testing of the new synced lyrics import pipeline.

## [2026-08-13] Move Local Lyrics & Audio Tag Fallbacks to Bottom of Priority Hierarchy
- **Files modified:** `backend/workers/lyrics_worker.py`, `task.md`
- **Details:** Re-ordered `LyricsWorker.fetch_lyrics()` discovery sequence. Placed all online APIs (`LRCLIB /api/get` -> `Musixmatch` -> `LRCLIB /api/search` -> `Syncedlyrics Fallbacks`) at top priorities (1 to 4). Moved local `.lrc` sidecar files and embedded audio tags (`_read_local_lrc`, `_read_embedded_lyrics`) down to the very end (priorities 5 and 6) to serve purely as offline fallbacks.

## [2026-08-13] Purge Database for User Re-testing Online Lyrics Pipeline
- **Files modified:** `data/library.db`, `task.md`
- **Details:** Wiped all records from `tracks`, `playlists`, `playlist_tracks`, `lyrics_cache` in `d:\ZFPlayer\data\library.db` and executed `VACUUM` to leave DB completely empty for user re-testing of the new online-first lyrics hierarchy.

## [2026-08-13] Update All Songs & Favorite Songs Covers to Monochrome White SVG Without Border
- **Files modified:** `frontend/js/playlists.js`, `frontend/js/ui.js`, `frontend/js/home.js`, `frontend/css/main.css`, `frontend/index.html`
- **Details:** Replaced white background cards and colored gradient covers for "All Songs" and "Favorite Songs" system playlists with crisp, monochrome white SVG icons (`#ffffff`). Added `.system-icon` CSS class for transparent backgrounds and no borders in sidebar and home playlist cards. Bumped cache-buster version to `?v=23`.

## [2026-08-13] Sửa Lỗi Bootstrap sys.path Khi Chạy Python Direct
- **Files modified:** ackend/app.py
- **Details:** Di chuyển đoạn lệnh kiểm tra và bổ sung PROJECT_ROOT vào sys.path lên đầu ackend/app.py trước khi import ackend.*. Giúp khởi chạy python backend/app.py thành công từ bất kỳ thư mục làm việc nào.
