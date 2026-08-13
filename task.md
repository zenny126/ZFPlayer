# Danh Sách Nhiệm Vụ: Dọn Sạch Cơ Sở Dữ Liệu (`library.db`) Để Thử Lại

- [x] **1. Kế Hoạch & Phê Duyệt (Planning)** <!-- id: 0 -->
    - [x] Kiểm tra hiện trạng các bảng trong `library.db` <!-- id: 1 -->
    - [x] Tạo `implementation_plan.md` & `task.md` <!-- id: 2 -->
    - [x] Chờ User phê duyệt kế hoạch xóa dữ liệu DB <!-- id: 3 -->

- [x] **2. Thực Thi & Kiểm Thu (Execution & QA)** <!-- id: 4 -->
    - [x] Xóa toàn bộ bản ghi các bảng `tracks`, `playlists`, `playlist_tracks`, `lyrics_cache` <!-- id: 5 -->
    - [x] Chạy lệnh `VACUUM` tối ưu dung lượng tệp DB <!-- id: 6 -->
    - [x] Xác minh số lượng bản ghi = 0 <!-- id: 7 -->
    - [x] Cập nhật `DEV_LOG.md` & `walkthrough.md` <!-- id: 8 -->
