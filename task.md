# Danh sách Nhiệm vụ: Triển khai Quản lý Custom Playlist (Đổi tên, Đổi ảnh đại diện, Xóa Playlist)

- [x] **1. Cập nhật HTML Modals & Context Menu (`index.html`)** <!-- id: 0 -->
  - [x] Thêm Modal Popup Đổi tên Playlist (`#rename-playlist-modal`) trong [index.html](file:///d:/ZFPlayer/frontend/index.html) <!-- id: 1 -->
  - [x] Thêm Modal Popup Xác nhận Xóa Playlist (`#delete-playlist-modal`) trong [index.html](file:///d:/ZFPlayer/frontend/index.html) <!-- id: 2 -->
  - [x] Thêm Context Menu chuột phải Sidebar (`#playlist-context-menu`) trong [index.html](file:///d:/ZFPlayer/frontend/index.html) <!-- id: 3 -->
  - [x] Thêm các nút bấm Đổi tên, Đổi ảnh, Xóa vào Playlist Header (`#playlist-header-actions`) <!-- id: 4 -->

- [x] **2. Cập nhật Backend API hỗ trợ Cover Playlist Mặc định (`library_api.py`, `library_service.py`)** <!-- id: 5 -->
  - [x] Nâng cấp `update_playlist_cover` xử lý ảnh bìa cho `all` và `favorites` trong [library_service.py](file:///d:/ZFPlayer/backend/services/library_service.py) <!-- id: 6 -->

- [x] **3. Cập nhật CSS Styles (`main.css`, `library.css`)** <!-- id: 7 -->
  - [x] Thêm styles cho các nút thao tác trên Playlist Header và các mục menu chuột phải `.context-menu-item.danger` trong [main.css](file:///d:/ZFPlayer/frontend/css/main.css) <!-- id: 8 -->

- [x] **4. Triển khai Logic Frontend (`playlists.js`, `ui.js`)** <!-- id: 9 -->
  - [x] Bắt sự kiện `contextmenu` (chuột phải) trên Playlist Item ở Sidebar trong [playlists.js](file:///d:/ZFPlayer/frontend/js/playlists.js) <!-- id: 10 -->
  - [x] Triển khai handler Đổi tên Playlist với Modal trong [playlists.js](file:///d:/ZFPlayer/frontend/js/playlists.js) <!-- id: 11 -->
  - [x] Triển khai handler Xóa Playlist với Modal Xác nhận trong [playlists.js](file:///d:/ZFPlayer/frontend/js/playlists.js) <!-- id: 12 -->
  - [x] Tích hợp đồng bộ giao diện Playlist Header và Sidebar sau khi Đổi tên / Đổi ảnh / Xóa <!-- id: 13 -->

- [x] **5. Kiểm thử & Ghi Nhật ký Phát triển** <!-- id: 14 -->
  - [x] Kiểm tra cú pháp backend & frontend (Self-healing QA) <!-- id: 15 -->
  - [x] Cập nhật [DEV_LOG.md](file:///d:/ZFPlayer/DEV_LOG.md) và [walkthrough.md](file:///C:/Users/Zenny/.gemini/antigravity/brain/bdb776d4-86e9-4b44-9b9e-439857be8f7e/walkthrough.md) <!-- id: 16 -->
