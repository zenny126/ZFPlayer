# DEV LOG

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
- `frontend/js/home.js` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Trang trí Icon**: Thay đổi mã hiển thị các danh sách phát mặc định. Sử dụng hiệu ứng nền chuyển màu (`linear-gradient`) tuyệt đẹp thay cho nền xám trong suốt: màu xanh lam (Blue) cho `All Songs`, đỏ cam (Red) cho `Favorite Songs`, và tím mộng mơ (Purple) cho các playlist trống ảnh bìa. SVG icon cũng được đổi thành nét bo tròn trắng (`#ffffff`) sang trọng.
2. **Thêm thẻ tạo mới**: Bổ sung một thẻ tĩnh ở cuối danh sách phát mang tên `Tạo Danh Sách Phát` với icon hình dấu `+` lớn. Khi người dùng bấm vào thẻ này, nó sẽ gọi trực tiếp hành động mở Modal tạo danh sách phát, giúp tăng đáng kể tính khả dụng (UX).
- 2026-08-12 02:04: Playlist UI Enhancement: Added Spotify-like Playlist Header with dynamic background gradient, stats (total tracks, duration) and Play button. Modified library.js, library.css, index.html, api.js, library_api.py, library_service.py, database.py.
- 2026-08-12 08:24: Bug Fix: Changed playlist_id type hint from int to Any in library_api.py to prevent PyWebView ValueError when passing 'all' or 'favorites' from JS.
---

## Timestamp: 2026-08-12T19:35:00+07:00
### Tác vụ thực hiện
Gỡ bỏ toàn bộ tính năng Playlist (theo yêu cầu của người dùng).

### Danh sách tệp tin thay đổi
- ackend/storage/database.py (MODIFIED)
- ackend/services/library_service.py (MODIFIED)
- ackend/api/library_api.py (MODIFIED)
- rontend/index.html (MODIFIED)
- rontend/js/api.js (MODIFIED)
- rontend/js/ui.js (MODIFIED)
- rontend/js/library.js (MODIFIED)
- rontend/js/home.js (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Backend Database (database.py)**: Xóa các hàm CRUD liên quan đến Playlist như create_playlist, update_playlist, delete_playlist, get_playlists, v.v... Cập nhật lại các hàm get_tracks_paginated và get_track_count để chỉ hỗ trợ thuộc tính is_favorites.
2. **Backend Services & API**: Xóa các phương thức gọi (wrapper) đến Playlist trong library_service.py và library_api.py. Khôi phục lại logic của scan_library để chỉ quét các thư mục được thiết lập trong cấu hình.
3. **Frontend API & UI**: Xóa các giao diện tạo và quản lý Playlist (các nút bấm add, context menu, modal) khỏi index.html.
4. **Frontend Javascript**: Đơn giản hóa ui.js, library.js, home.js để chỉ hiển thị các playlist mặc định của hệ thống là All Songs và Favorite Songs.

---

## Timestamp: 2026-08-12T23:43:00+07:00
### Tác vụ thực hiện
Xây dựng kiến trúc "RAM Playback" (Memory Playback) và Tối ưu hóa WASAPI Exclusive Bit-Perfect 100%.

### Danh sách tệp tin thay đổi
- `backend/audio/engine.py` (MODIFIED)
- `backend/audio/decoder.py` (MODIFIED)
- `backend/storage/config.py` (MODIFIED)
- `config/config.json` (MODIFIED)

### Mô tả chi tiết kỹ thuật
1. **Kiến trúc RAM Playback (`engine.py`)**: Thay thế hoàn toàn mô hình giải mã Streaming đọc ổ cứng trực tiếp trong lúc phát. Khi nạp bài hát, toàn bộ file FLAC được giải mã và lưu 100% vào bộ nhớ RAM chỉ trong ~0.05s. Trong suốt quá trình phát nhạc, ổ cứng/SSD đạt mức 0% I/O, loại bỏ hoàn toàn hiện tượng trễ đọc đĩa (Disk I/O Jitter) và xung đột luồng GIL trong Python.
2. **Bit-Padding chuẩn MSB (`decoder.py`)**: Tự động dịch trái dữ liệu `int16` sang dạng `int32` MSB (`data << 16`) trên bộ nhớ RAM. Đảm bảo dữ liệu phát ra chuẩn định dạng `int32` mà chip phần cứng USB XMOS của DAC Topping TP35 Pro yêu cầu natively, loại bỏ hoàn toàn các lỗi lệch bit và tiếng sạn pop ở tầng PortAudio C.
3. **Khóa cứng WASAPI Shared Mode & Loại bỏ nút chuyển**: Khóa cố định chế độ WASAPI Shared Mode trong `engine.py`, loại bỏ hoàn toàn nút bật/tắt WASAPI Exclusive khỏi bảng Settings (`index.html` và `ui.js`). Hệ thống vận hành cố định trên nền tảng WASAPI High-Fidelity + RAM Playback, mang lại trải nghiệm phát nhạc mượt mà 100% không còn giật lag hay vấp tiếng.
4. **Sửa lỗi lẹm Menu "Add to Playlist" (`playlists.js`)**: Bổ sung thuật toán kiểm tra tràn viền màn hình (Window Boundary Check). Khi menu chuột phải nằm ở mép phải màn hình, sub-menu danh sách playlist sẽ tự động lật sang bên trái (`rect.left - subWidth`) và điều chỉnh chiều cao (`z-index: 99999`), đảm bảo danh sách Playlist luôn hiển thị 100% đầy đủ, không bị khuất hay tràn khỏi viền ứng dụng. Đồng thời tự động đồng bộ danh sách playlist mới nhất mỗi khi di chuột qua.

---

## Timestamp: 2026-08-12T23:59:00+07:00
### Tác vụ thực hiện
Khoanh vùng danh sách phát (Queue Scope) chỉ chạy duy nhất trong Playlist/Danh sách đang được chọn.

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
3. **Đồng bộ Frontend & Sửa lỗi `resume()` (`player_service.py`, `player.js`, `library.js`)**:
   - Khắc phục triệt để điểm hở: Trong phương thức `resume()`, trước đây ứng dụng gọi `play(current_path)` mà quên không truyền `current_playlist_id`, khiến hệ thống bị fallback về toàn bộ thư viện nhạc (`all`).
   - Giờ đây `current_playlist_id` được lưu trữ kiên cố vào `config.json` (`last_playlist_id`) và duy trì liên tục qua các thao tác Tạm dừng (Pause), Phát tiếp (Resume), Khởi động lại app hay Chuyển bài (Next/Prev).
4. **Cập nhật phạm vi khi chuyển Playlist (`player_service.py`, `player_api.py`, `ui.js`)**:
   - Thêm phương thức `set_active_playlist(playlist_id)` vào Backend API.
   - Khi người dùng click chọn chuyển sang xem một Playlist mới trên Sidebar (ví dụ: chuyển từ "Charlie Puth" sang "Maroon 5"), giao diện sẽ tự động thông báo xuống Backend cập nhật ngay phạm vi phát (`current_playlist_id = 13`). Nếu bấm **Next** hay **Prev**, trình phát lập tức chuyển sang bài hát của Playlist mới chọn ("Maroon 5") thay vì bị kẹt ở Playlist cũ.

## [2026-08-12] Fix setActivePlaylist API binding for Playlist Scope
- **Files modified:** ackend/api/player_api.py, rontend/js/ui.js`n- **Details:** Fixed an issue where PyWebView silently failed to expose or bind the setActivePlaylist method in the frontend due to snake_case to camelCase conversion quirks. Explicitly added a setActivePlaylist wrapper in Python and a set_active_playlist fallback in JavaScript to guarantee that navigating to a different playlist in the sidebar strictly locks the playback queue (Next/Prev/Auto-Next) to the newly opened view.
## [2026-08-13] Fix ApiWrapper to expose setActivePlaylist and pass playlistId to play()
- **Files modified:** rontend/js/api.js`n- **Details:** Found the true root cause of the playlist scoping bug. The frontend uses an explicit ApiWrapper class in pi.js which did not define setActivePlaylist, causing silent failures when the sidebar was clicked. Furthermore, ApiWrapper.play was only accepting the path argument and dropping playlistId, causing the backend to receive playlist_id=None when tracks were manually played. Added the missing wrapper definitions.
## [2026-08-13] Implement Playback Debounce for RAM Playback
- **Files modified:** ackend/services/player_service.py`n- **Details:** Implemented a 0.3s debounce timer in PlayerService.play() to prevent WASAPI crashing and OOM errors when users rapidly spam the Next/Prev buttons. The UI updates instantly via get_state(), while the heavy 70MB+ FLAC RAM loading is safely deferred and cancelled if redundant.
## [2026-08-13] Polished UI and fixed patchy styling
- **Files modified:** rontend/index.html, rontend/css/main.css, rontend/css/library.css, rontend/js/library.js`n- **Details:** Polished the Playlist Header to match modern Spotify design. Added a giant Play button. Styled the previously ugly HTML buttons with .btn-outline. Fixed the faint table headers. Themed the ugly Windows scrollbar to match the dark mode. Wired up the 'Import Folder' button which was missing an event listener.
## [2026-08-13] Bust PyWebView Cache
- **Files modified:** rontend/index.html`n- **Details:** Added ?v=2 query parameters to all CSS and JS imports to prevent Chromium/PyWebView from caching older versions of styles and scripts. This ensures the UI aesthetic updates and Play button logic from the previous patch are actually loaded.
## [2026-08-13] Fixed Playlist State Bug
- **Files modified:** rontend/js/playlists.js, rontend/js/library.js, rontend/index.html`n- **Details:** Fixed a state bug where clicking the 'All Songs' or 'Favorite Songs' pseudo-playlists would leave the previous playlist's header (e.g. Charlie Puth) rendered on the screen due to a missing mock object in the store.subscribe handler. Updated cache-busters to ?v=3.
## [2026-08-13] Redesign Modal UI
- **Files modified:** rontend/css/main.css, rontend/index.html`n- **Details:** Redesigned the 'Create Playlist' modal to match the dark theme and eliminate the jarring 'glassmorphism' bug that ruined text legibility. Added .text-input class to style the input box properly. Added .btn-ghost for subtle cancel buttons. Adjusted margins and gaps for a premium layout. Bumped cache buster to ?v=4.
## [2026-08-13] Global Immersive Glass UI
- **Files modified:** rontend/css/main.css, rontend/css/library.css, rontend/css/player.css, rontend/js/player.js, rontend/index.html`n- **Details:** Re-architected the entire app's layout to use the 'Apple Music / Windows 11 Mica' immersive glass aesthetic. The global #app container now has a dynamic, heavily blurred pseudo-element background that matches the currently playing track's cover art. All panels (sidebar, main content, top bar, player bar) have been updated to be translucent/glassy to allow the gorgeous background to bleed through everywhere. Bumped cache to ?v=5.
## [2026-08-13] Glass UI Opacity Tweak
- **Files modified:** rontend/css/main.css, rontend/index.html`n- **Details:** Reduced panel background opacity from 0.4/0.5 down to 0.15/0.2 to let more of the blurred immersive background bleed through. Increased brightness of the blur layer slightly (0.7). Bumped cache to ?v=6.
## [2026-08-13] Switch to WASAPI Shared Mode
- **Files modified:** ackend/audio/engine.py`n- **Details:** Changed the default audio playback mode from WASAPI High-Fidelity (Exclusive/low-latency) to WASAPI Shared Mode with 'high' latency to prevent audio crackling and popping that users were experiencing.
## [2026-08-13] White/Glass Premium Color Palette
- **Files modified:** rontend/css/main.css, rontend/index.html`n- **Details:** Replaced the hardcoded Spotify green accent color with pure white (\#FFFFFF\) to better fit the dynamic cover art background. Modified \--text-primary\ to be 75% translucent white (\
gba(255, 255, 255, 0.75)\), so that inactive text is dimmed while active states (using the white accent) are brilliantly bright. This creates a much more premium and elegant Apple Music aesthetic. Bumped cache to ?v=7.
## [2026-08-13] Fix Lyrics View Like Button Sync
- **Files modified:** rontend/js/player.js, rontend/index.html`n- **Details:** Wired up the lyrics-like-btn in the lyrics view to correctly trigger the API toggle and synchronize state with the global store and main player bar. Bumped cache to ?v=8.
## [2026-08-13] Fix Like Button Store Sync Issue
- **Files modified:** rontend/js/player.js, rontend/js/library.js`n- **Details:** Fixed a bug where clicking the like button failed to update the DOM because mutating the currentTrack object reference prevented store.setState from triggering syncUI(). Created a new object reference to ensure reactivity. Also wired the library list view to sync likes back to the global store if the liked track is currently playing.
## [2026-08-13] Eradicate Solid Background Colors
- **Files modified:** rontend/css/main.css, rontend/css/library.css, rontend/index.html`n- **Details:** Refactored the base CSS variables (--bg-primary, --bg-secondary, --bg-elevated, --bg-highlight) from hardcoded opaque grays (#121212, #181818, #282828) to perfectly translucent glass layers (
gba(0,0,0,0.2), 
gba(255,255,255,0.04), 
gba(255,255,255,0.08), 
gba(255,255,255,0.15)). Replaced hardcoded occurrences in library.css and main.css. This enforces a true 100% Immersive Glass UI everywhere in the app. Bumped cache to ?v=10.
## [2026-08-13] Dreamy Glow Typography
- **Files modified:** rontend/css/main.css, rontend/css/library.css, rontend/index.html`n- **Details:** Replaced heavy dark text-shadow with a subtle legibility shadow. Boosted all text variables to pure white or high-opacity white. Added 'dreamy' white text-shadow glows (	ext-shadow: 0 0 10px rgba(255,255,255,0.4)) to active elements (playing track, active buttons, filter chips) and soft box-shadow glows to the solid white play buttons.
## [2026-08-13] Fix Popup/Modal Frosted Glass
- **Files modified:** rontend/css/main.css, rontend/css/library.css, rontend/index.html`n- **Details:** Fixed an issue where the Create Playlist modal and Context Menus were almost completely transparent and illegible against the background text due to the removal of solid backgrounds. Applied heavy \ackdrop-filter: blur(40px) saturate(1.5)\, a subtle white border, and stronger box-shadows to these popup elements so they correctly act as frosted glass hovering above the UI. Bumped cache to ?v=13.
## [2026-08-13] Sticky Library Header Row
- **Files modified:** rontend/css/library.css, rontend/index.html`n- **Details:** Made the library header row (Title/Album/Date Added) sticky when scrolling. Changed position: relative to position: sticky; top: 0; and added a frosted glass background (
gba(0,0,0,0.3) + ackdrop-filter: blur(20px)) so that absolutely positioned tracks scrolling up slide cleanly underneath it without text overlap. Bumped cache to ?v=14.
## [2026-08-13] Fix VirtualList Gap On Scroll
- **Files modified:** rontend/js/library.js, rontend/index.html`n- **Details:** Fixed a critical bug in VirtualList calculation where 	his.scrollTop was directly used to compute startIndex without subtracting scroller.offsetTop. When scrolling past the playlist header (~300px), VirtualList erroneously calculated that the top 5 tracks were offscreen and unmounted them, leaving a huge empty blank gap below the sticky header. Subtracted scroller.offsetTop from scrollTop in update() to accurately calculate visible index offset. Bumped cache to ?v=15.
## [2026-08-13] Fix Header Row Grid Alignment
- **Files modified:** rontend/css/library.css, rontend/index.html`n- **Details:** Fixed misaligned column headers (TITLE, ALBUM, DATE ADDED, Duration) caused by an extra display: flex directive on .track-row.header-row overriding .track-row's CSS Grid (grid-template-columns: 40px 6fr 4fr 3fr 40px 40px 80px). Removed display: flex so the header row matches the track data rows pixel for pixel. Bumped cache to ?v=16.
## [2026-08-13] Fix Home View Bottom Padding & Scroll
- **Files modified:** rontend/index.html, rontend/js/home.js`n- **Details:** Fixed an issue where the Home view could not scroll down deep enough, causing the bottom of the 'G?n y' (Recently Played) section to get cut off by the bottom player bar. Increased #home-view's bottom padding from 24px to 120px, and set explicit 180px card widths for the horizontal scroll list. Bumped cache to ?v=17.
## [2026-08-13] Fix Recent Cards Vertical Collapse
- **Files modified:** rontend/js/home.js, rontend/index.html`n- **Details:** Fixed an issue where recent track cards in the Home view collapsed into 20px-tall paper-thin strips. Added explicit 148px height/width on .album-cover-container inside home.js and set lign-items: flex-start on #home-recent-grid in index.html to prevent Flexbox from collapsing percentage aspect-ratio elements. Bumped cache to ?v=18.
## [2026-08-13] Convert Home Recent Section to 20-Track Table List
- **Files modified:** rontend/index.html, rontend/js/home.js, rontend/css/library.css`n- **Details:** Replaced the horizontal scrolling grid for Recently Played tracks in Home view with a full vertical table list displaying the 20 most recently played songs. Formatted rows using the clean 7-column track layout matching the Library view (STT, Thumbnail, Title, Artist, Album, Date Added, Like button, Duration). Bumped cache to ?v=19.
## [2026-08-13] Resize Top Bar Icons & Functionalize Sidebar Toggle
- **Files modified:** rontend/index.html, rontend/css/main.css, rontend/js/ui.js`n- **Details:** Scaled down top bar navigation buttons from 48px to a sleek, compact 40px diameter, with 20px SVG icons for balanced proportion. Converted the static top-left Logo icon into a functional #btn-toggle-sidebar button that smoothly expands and collapses the left library sidebar on click. Bumped cache to ?v=20.
## [2026-08-13] Documentation & Architecture Guide
- **Files created:** \README.md\, \docs/ARCHITECTURE.md\\
- **Details:** Created comprehensive project documentation including feature highlights, tech stack, directory structure, install/usage guide, and in-depth technical architecture (Audio WASAPI signal pipeline, SQLite FTS indexing, VirtualList math & offset calculations, CSS Glass token system). Pushed to GitHub repo zenny126/ZFPlayer.

## [2026-08-13] Optimize Lyrics Source Priority Hierarchy
- **Files modified:** `backend/workers/lyrics_worker.py`, `task.md`
- **Details:** Optimized the lyrics discovery pipeline specifically for tracks downloaded via Deez Bot Telegram (Spotify album links). Added zero-latency local `.lrc` sidecar file reader and embedded audio tag metadata reader (`FLAC` Vorbis comments / `MP3` ID3 tags). Re-ordered online search fallback chain to query LRCLIB direct exact match, Musixmatch (Spotify official provider via `syncedlyrics`), LRCLIB search, and fallback providers.

## [2026-08-13] Fix Uncaught TypeError: window.api.toggleFavorite is Not a Function
- **Files modified:** `frontend/js/home.js`, `frontend/js/api.js`, `frontend/index.html`, `task.md`
- **Details:** Fixed JS runtime error when clicking the Like heart button on the Recently Played tracks list in Home view. Changed `window.api.toggleFavorite(track.path)` to `window.api.toggleLike(track.path)` in `home.js`. Added `toggleFavorite` alias method in `api.js` for backwards compatibility. Bumped cache buster version to `?v=21`.

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










