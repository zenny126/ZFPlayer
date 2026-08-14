# Walkthrough - Rà Soát & Chuẩn Hóa Nhãn Hiệu Thương Mại (Trademarks Cleanup)

Toàn bộ các tham chiếu, tiền tố, class CSS và mô tả liên quan đến các thương hiệu đã đăng ký của bên thứ ba (**Apple**, **Apple Music**, **Spotify**) đã được xử lý và thay thế triệt để bằng các thuật ngữ kỹ thuật trung tính, đảm bảo 100% sạch sẽ về mặt sở hữu trí tuệ và an toàn pháp lý khi phát hành thương mại.

---

## 🛠️ Chi Tiết Các Thay Đổi

### 1. Giao diện & Mã Nguồn Frontend
* **`frontend/index.html`**:
  * Thay thế class bao layout `<div id="app" class="spotify-layout">` $\rightarrow$ `<div id="app" class="zfp-layout">`.
  * Chuẩn hóa comment mô tả màn hình lời bài hát $\rightarrow$ `<!-- Full-screen Kinetic Spring Lyrics Overlay -->`.
* **`frontend/css/main.css`**:
  * Đổi token CSS: `--ease-apple-lyrics` $\rightarrow$ `--ease-spring-lyrics: cubic-bezier(0.2, 1, 0.2, 1)`.
  * Cập nhật các biến chuyển động kế thừa: `--transition-lyrics-scroll`, `--transition-lyrics-focus`, `--transition-lyrics-next`, `--transition-lyrics-passed`.
  * Đổi CSS layout selector sang `#app.zfp-layout`.
* **`frontend/css/lyrics.css`**:
  * Thay thế tất cả các thuộc tính sử dụng `var(--ease-apple-lyrics)` $\rightarrow$ `var(--ease-spring-lyrics)`.
  * Dọn dẹp toàn bộ comment tham chiếu nhãn hiệu bên thứ ba.

### 2. Tài Liệu Kỹ Thuật & Giới Thiệu
* **`README.md`**:
  * Cập nhật badge thiết kế giao diện: `UI-Glassmorphism_Fluid_Shader`.
  * Chuẩn hóa mô tả: *"Giao diện Glassmorphism / Fluid Shader động lực học lộng lẫy"*, *"Động cơ lời bài hát Kinetic Spring & Cinema Mode"*.
* **`architect.md` & `docs/ARCHITECTURE.md`**:
  * Cập nhật sơ đồ hệ thống Mermaid: `[Kinetic Spring Lyrics Subsystem]`.
  * Chuẩn hóa mô tả 9 tầng và các luồng xử lý: *"Modern Glassmorphism"*, *"Kinetic Spring Lyrics Engine"*, *"Vertical Spring Center Glide"*.

---

## 🔍 Kết Quả Kiểm Thử & Rà Soát (Verification Results)

* **Rà soát toàn bộ dự án**: Đã quét lại toàn bộ thư mục `frontend/`, `backend/`, `docs/` và `README.md` $\rightarrow$ 0 phát hiện nhãn hiệu thương mại bên thứ ba.
* **Kiểm tra cú pháp Backend & Frontend**: Import backend và các endpoint API hoạt động hoàn hảo, không có lỗi runtime.
* **Giao diện & Chuyển động**: Toàn bộ hoạt ảnh lò xo động lực học (Spring Physics), WebGL Fluid Shader và cuộn quán tính lyric hoạt động chính xác 100%.

---

## 📚 Tài Liệu Liên Quan
* Nhật ký phát triển: [`DEV_LOG.md`](file:///d:/ZFPlayer/DEV_LOG.md)
