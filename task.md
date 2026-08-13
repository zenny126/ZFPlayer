# Tasks: Đóng gói EXE & Tích hợp Windows SMTC

- [x] **1. Chuẩn hóa đường dẫn hệ thống cho PyInstaller** <!-- id: 0 -->
  - [x] Cập nhật `PROJECT_ROOT` trong `backend/app.py` để hỗ trợ `sys._MEIPASS` <!-- id: 1 -->
  - [x] Cấu hình đường dẫn lưu CSDL, Config, Cache vào `%APPDATA%/ZFPlayer` khi chạy đóng gói <!-- id: 2 -->
- [x] **2. Tích hợp Windows SMTC (System Media Transport Controls) & Media Keys** <!-- id: 3 -->
  - [x] Thêm đồng bộ `navigator.mediaSession` trong Frontend (`main.js` / `api.js` / `player.js`) <!-- id: 4 -->
  - [x] Thêm xử lý phím bấm bàn phím phần cứng và đồng bộ trạng thái Windows SMTC <!-- id: 5 -->
- [x] **3. Cấu hình & Tệp Script Đóng Gói (PyInstaller)** <!-- id: 6 -->
  - [x] Cài đặt PyInstaller <!-- id: 7 -->
  - [x] Tạo tệp `zfplayer.spec` bao gồm đầy đủ frontend, soundfile DLLs, dependencies <!-- id: 8 -->
  - [x] Tạo tệp script `build_exe.py` tự động đóng gói <!-- id: 9 -->
- [x] **4. Kiểm thử & Xác nhận** <!-- id: 10 -->
  - [x] Chạy build thử nghiệm và kiểm tra ứng dụng đóng gói `.exe` ([`dist/ZFPlayer/ZFPlayer.exe`](file:///d:/ZFPlayer/dist/ZFPlayer/ZFPlayer.exe)) <!-- id: 11 -->
  - [x] Cập nhật `DEV_LOG.md` và `walkthrough.md` <!-- id: 12 -->

- [x] **5. Tắt cửa sổ DevTools khi mở ứng dụng** <!-- id: 13 -->
  - [x] Sửa `backend/app.py`: Đổi `webview.start(debug=True)` thành `debug=False` (hoặc kiểm tra cờ `--debug`) <!-- id: 14 -->

- [x] **6. Chuyển sang đóng gói Đơn Tệp (--onefile) & Build** <!-- id: 15 -->
  - [x] Sửa `zfplayer.spec` chuyển chế độ sang Single File Executable <!-- id: 16 -->
  - [x] Sửa `build_exe.py` để trỏ vào `dist/ZFPlayer.exe` <!-- id: 17 -->
  - [x] Chạy build PyInstaller và kiểm tra file `.exe` độc lập ([`dist/ZFPlayer.exe`](file:///d:/ZFPlayer/dist/ZFPlayer.exe)) <!-- id: 18 -->


