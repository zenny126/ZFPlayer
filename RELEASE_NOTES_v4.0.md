# 🎵 ZFPlayer v4.0 — Pure Rust Native Edition

**ZFPlayer v4.0** marks the transition to a **100% Pure Rust backend & audio engine**, delivering ultra-low memory and CPU/GPU footprint in a **single standalone `ZFPlayer.exe` (~9.6 MB)** with **zero external DLL dependencies**.

---

## 🌟 Highlights in v4.0

* **Pure Rust Native Audio Pipeline (`wasapi` + `symphonia` + `lofty`)**:
  * **Event-Driven WASAPI Shared & Exclusive Bit-Perfect** output (`StreamMode::EventsShared` / `EventsExclusive` with automatic fallback to polling), zero-allocation `AudioRingBuffer`, and hardware stream auto-release when paused or stopped.
  * **Zero-CPU Idle**: Both `wasapi_render_loop` and `StreamingDecoder` sleep on `Condvar` when idle/paused/EOF instead of polling.
  * Native multi-format decoding (`FLAC`, `WAV`, `MP3`, `OGG`, `AIFF`, `M4A`, `AAC`) with VBR duration fallback and `Int24In32` bit-accurate packing.
* **Truly Standalone 1-File Executable (`ZFPlayer.exe`)**:
  * Statically links `libunwind.a` (`gnullvm`) and embeds `WebView2Loader.dll` via a compiled static C shim (`build.rs`) — zero missing DLL errors on fresh Windows installations or **Windows Sandbox**.
  * Automatically falls back to **Zero-WebView2 App Mode** (`msedge.exe --app=...`) when WebView2 Runtime is unavailable.
  * Embedded `ZFP` application & window icon (`.rsrc` + `WindowBuilder::with_window_icon`).
* **32-bit `RGBA_8888` Smooth Visuals & Low-Power GPU Optimization**:
  * Band-free WebGL fluid background using `highp` float + Triangular Interleaved Gradient Noise (IGN) dithering, linear-light color transitions, hoisted frame uniforms, and adaptive FPS (`60 FPS` color transitions → `24 FPS` playing → `0 FPS` paused/occluded).
  * Restored full 32-bit compositor layers for smooth album `box-shadow` and active lyric `text-shadow` halos.
  * Measured idle footprint: **`~1.06%` CPU**, **`0%` GPU**, **`~6.4 MB` Rust host private memory**.
* **Hardened Storage & Security**:
  * Thread-local SQLite connection pooling (`64MB` MMAP + `WAL` + `FTS5`), `ON CONFLICT(path) DO UPDATE` upserts preserving track IDs, likes, and playlist links, and 7-day TTL negative lyrics cache.
  * Percent-decoded path traversal guard (`sanitize_rel_path`), Unicode NFKC lyrics normalization, and in-flight deduplication.

---

## 📦 Download & Run
1. Download **`ZFPlayer.exe`** from the release assets below.
2. Double-click to run — no installer, no Python, no external DLLs required.
3. Optional portable mode: place an empty `portable.txt` file (or `data/` folder) next to `ZFPlayer.exe`.
