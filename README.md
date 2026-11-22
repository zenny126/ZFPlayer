<div align="center">
  <img src="app_icon.ico" alt="ZFPlayer Logo" width="128" height="128" />

  # ZFPlayer v4.0

  **Trình phát nhạc Hi-Res Lossless Audio chuẩn WASAPI Bit-Perfect gọn nhẹ cho Windows**

  [![Version](https://img.shields.io/badge/Version-4.0.0-gold.svg)]()
  [![Rust](https://img.shields.io/badge/Rust-Native_v4.0-orange.svg?logo=rust&logoColor=white)](https://www.rust-lang.org/)
  [![Audio Engine](https://img.shields.io/badge/Audio-WASAPI_Bit--Perfect_100%25-0078D6.svg?logo=windows&logoColor=white)]()
  [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
</div>

---

## 📦 1. Tải Về & Chạy Ngay (Standalone EXE)

**ZFPlayer** được đóng gói thành **1 file `ZFPlayer.exe` duy nhất (~9.6 MB)**, không cần bộ cài đặt và không phụ thuộc DLL ngoài:

| Tệp Thực Thi | Phiên Bản | Dung Lượng | Hệ Điều Hành | Mô Tả |
| :--- | :---: | :---: | :--- | :--- |
| **`ZFPlayer.exe`** | **v4.0.0** | **~9.6 MB** | Windows 10 / 11 (64-bit) | Bản chạy ngay (1-file standalone, 0 DLL ngoài) |

1. Tải **`ZFPlayer.exe`** mới nhất tại **[ZFPlayer Releases](https://github.com/zenny126/ZFPlayer/releases)**.
2. Nhấp đúp vào **`ZFPlayer.exe`** để sử dụng ngay.

---

## 💻 2. Hướng Dẫn Cài Đặt & Chạy Dự Án Từ Mã Nguồn

### Yêu Cầu Môi Trường
* **Hệ điều hành**: Windows 10 / 11 (64-bit).
* **Rust Toolchain**: `stable-x86_64-pc-windows-gnullvm` + `llvm-mingw` (tự động cài đặt qua `setup_rust.bat`).

### Các Bước Cài Đặt, Chạy & Đóng Gói
```powershell
# Bước 1: Cài đặt tự động Rust toolchain (chỉ cần chạy 1 lần đầu)
setup_rust.bat

# Bước 2: Chạy trực tiếp dự án từ mã nguồn (Release Mode)
run_dev.bat

# Bước 3: Chạy bộ kiểm thử tự động (Unit & Integration Tests)
cargo test

# Bước 4: Đóng gói thành 1 file thực thi độc lập (dist\ZFPlayer.exe)
build.bat
```

Sau khi chạy `build.bat`, file thực thi độc lập sẽ được xuất ra tại **`dist\ZFPlayer.exe`** (~9.6 MB, đã nhúng tĩnh `libunwind`, `WebView2Loader` và icon ứng dụng).

---

## 💼 3. Hướng Dẫn Chế Độ Portable 100%

Mặc định, ứng dụng lưu dữ liệu (thư viện nhạc, cấu hình, bộ nhớ đệm ảnh bìa và lời bài hát) tại `%APPDATA%\ZFPlayer`. Để chuyển sang **chế độ Portable 100%** (lưu toàn bộ dữ liệu trên USB hoặc ổ cứng di động, không ghi vào ổ `C:\`), chỉ cần làm **1 trong 2 cách** sau:

### Cách 1: Tạo thư mục `data` cạnh `ZFPlayer.exe` (Khuyến nghị)
```text
D:\USB\ZFPlayer\
├── ZFPlayer.exe
└── data\                  <-- Tạo thư mục rỗng này
```

### Cách 2: Tạo tệp `portable.txt` cạnh `ZFPlayer.exe`
```text
D:\USB\ZFPlayer\
├── ZFPlayer.exe
└── portable.txt           <-- Tạo tệp văn bản rỗng này
```

### 📂 Cấu Trúc Thư Mục Khi Chạy Portable
Sau khi mở `ZFPlayer.exe`, toàn bộ dữ liệu sẽ tự động nằm gọn trong cùng thư mục:
```text
D:\USB\ZFPlayer\
├── ZFPlayer.exe           # Ứng dụng chính (1-file standalone)
├── portable.txt           # Cờ kích hoạt Portable (hoặc thư mục data\)
├── config\
│   └── config.json        # Cấu hình âm lượng, chế độ WASAPI, phím tắt
├── data\
│   └── library.db         # Cơ sở dữ liệu SQLite thư viện nhạc & playlist
└── cache\
    ├── covers\            # Bộ nhớ đệm ảnh bìa album
    └── lyrics\            # Bộ nhớ đệm lời bài hát offline
```

---

## 📄 Giấy Phép
Phát hành theo giấy phép **Apache License 2.0** — Tác giả: **Zenny** ([@zenny126](https://github.com/zenny126)).
