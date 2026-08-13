# Danh sách Nhiệm vụ: Nâng cấp Chuyển động bằng Curve (Bezier Motion Design System)

- [x] **1. Thiết lập Hệ thống Bezier Curve Tokens** <!-- id: 0 -->
  - [x] Khai báo các biến đường cong Bezier toàn cục (`--ease-out-quint`, `--ease-out-expo`, `--ease-spring`, `--ease-in-out-smooth`) trong [main.css](file:///d:/ZFPlayer/frontend/css/main.css) <!-- id: 1 -->
  - [x] Khai báo các biến transition mới với thời gian và đường cong phanh mượt (`--transition-spring`, `--transition-fluid`, `--transition-fast`, `--transition-normal`, `--transition-slow`) <!-- id: 2 -->

- [x] **2. Cập nhật Motion cho Layout Core & Control Elements** <!-- id: 3 -->
  - [x] Cập nhật hiệu ứng nảy/co giãn của Sidebar, Top Bar Buttons, Search Bar trong [main.css](file:///d:/ZFPlayer/frontend/css/main.css) <!-- id: 4 -->
  - [x] Cập nhật animation xuất hiện Modal & Context Menu với keyframes cubic-bezier (`@keyframes modalEnter`, `@keyframes contextMenuPop`) <!-- id: 5 -->
  - [x] Cập nhật Seekbar thumb, Volume slider thumb, Filter chips, Buttons primary/outline/ghost <!-- id: 6 -->

- [x] **3. Nâng cấp Chuyển động trong Player Bar** <!-- id: 7 -->
  - [x] Thêm hiệu ứng Spring Bounce cho nút Play/Pause vòng tròn (`.btn-play-pause-circle`) trong [player.css](file:///d:/ZFPlayer/frontend/css/player.css) <!-- id: 8 -->
  - [x] Cập nhật hiệu ứng cho các nút Like, Shuffle, Repeat và ảnh bìa bài hát đang phát <!-- id: 9 -->

- [x] **4. Nâng cấp Chuyển động Lyrics Overlay & Chữ cuộn** <!-- id: 10 -->
  - [x] Cập nhật hiệu ứng mở/đóng Lyrics Overlay trượt với đường cong `--ease-out-expo` trong [lyrics.css](file:///d:/ZFPlayer/frontend/css/lyrics.css) <!-- id: 11 -->
  - [x] Nâng cấp cuộn lời bài hát `#lyrics-content` dùng đường cong `cubic-bezier(0.16, 1, 0.3, 1)` giúp chữ lướt êm ái <!-- id: 12 -->
  - [x] Cập nhật hiệu ứng Zoom scale, Blur và Glow cho dòng chữ active (`.lyrics-line.active`) <!-- id: 13 -->

- [x] **5. Nâng cấp Chuyển động Library & Album Grid Cards** <!-- id: 14 -->
  - [x] Nâng cấp hiệu ứng hover trên các dòng danh sách bài hát (`.track-row`) và nút Play lớn trong [library.css](file:///d:/ZFPlayer/frontend/css/library.css) <!-- id: 15 -->
  - [x] Nâng cấp Card Album (`.album-card`) và bìa Album (`.album-cover`) với spring curve trong [albums.css](file:///d:/ZFPlayer/frontend/css/albums.css) <!-- id: 16 -->

- [x] **6. Kiểm thử & Ghi Dev Log** <!-- id: 17 -->
  - [x] Kiểm tra cú pháp và khả năng vận hành tự động (Self-healing QA) <!-- id: 18 -->
  - [x] Cập nhật [DEV_LOG.md](file:///d:/ZFPlayer/DEV_LOG.md) và [walkthrough.md](file:///C:/Users/Zenny/.gemini/antigravity/brain/bdb776d4-86e9-4b44-9b9e-439857be8f7e/walkthrough.md) <!-- id: 19 -->
