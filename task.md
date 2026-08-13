# Tasks - Triển khai Background Priority Queue Tải Lời Bài Hát Ngầm với Throttle

- [x] Lập kế hoạch kiến trúc Background Priority Queue và trình người dùng phê duyệt <!-- id: 0 -->
- [x] Tái cấu trúc `backend/workers/lyrics_worker.py` bổ sung Queue đơn luồng, cơ chế Priority và Throttle delay 0.5s <!-- id: 1 -->
- [x] Cập nhật `backend/workers/scanner.py` và `backend/services/library_service.py` để chuyển prefetch sang Background Queue <!-- id: 2 -->
- [x] Tích hợp `backend/services/player_service.py` ưu tiên đẩy bài hát đang phát / sắp phát lên đầu Queue (`priority=True`) <!-- id: 3 -->
- [x] Kiểm chứng thực tế quá trình import bài hát và tải ngầm lyrics <!-- id: 4 -->
- [x] Ghi nhật ký phát triển vào `DEV_LOG.md` và `walkthrough.md` <!-- id: 5 -->
