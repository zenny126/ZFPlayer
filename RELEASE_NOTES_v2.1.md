# 🎵 ZennyFLAC Player v2.1 — Standalone Performance & Zero-Lag Update

The **v2.1** release brings massive performance optimizations for the standalone single `.exe` distribution, eliminates all internal server request latencies, and hardens the audio playback pipeline with complete native DLL bundling and database self-healing.

---

## ✨ What's New & Highlights

### 1. ⚡ Instant UI Boot & Zero-DNS WSGI Latency
* **Eliminated Reverse DNS Lookup Delays**: Overrode WSGI request handler address resolution to bypass blocking Windows DNS subsystem calls (`socket.getfqdn`), dropping local asset/cover loading times from **1.5s per request** down to **< 0.2ms (Instantaneous)**.
* **Instant Cold-Start**: The application window now opens and renders in **< 0.5s**.

### 2. 🛡️ 100% Self-Contained Standalone Executable
* **Complete Native DLL Bundling**: Embedded 109 Dynamic C/C++ Libraries and 136 Data Files directly into the single executable:
  - `_sounddevice_data` (PortAudio WASAPI Bit-Perfect C-driver)
  - `_soundfile_data` (libsndfile C-decoder)
  - `webview` & `clr_loader` & `pythonnet` (WebView2Loader x64 runtime & CLR interop)
  - `certifi` (SSL certificates for LRCLIB/Spotify lyric fetching)
* **Safe Windowed Stdio Redirection**: Integrated safe `NullWriter` wrappers to eliminate `NoneType` stdio errors in `console=False` mode on Windows.
* **Windows Version Info Resource**: Embedded official Windows metadata (`ZennyFLAC Player v2.1.0.0`, CompanyName, Description, Copyright) for trusted system recognition and clean properties display.

### 3. 💾 Self-Healing SQLite Engine & Resilient Playback
* **Integrity Self-Healing (`_check_and_heal_database`)**: Automatically detects database corruption and restores a clean library state without crashing.
* **Extended Busy Timeout**: Increased SQLite busy timeout to 30,000ms (`PRAGMA busy_timeout = 30000`) to prevent `database is locked` errors during simultaneous playback and scanning.
* **Fault-Tolerant Play Pipeline**: Defensively isolated playlist history queries so audio playback and decoding always start reliably.

### 4. 🎨 UI & UX Refinements
* **Settings Modal Optimization**: Streamlined modal dimensions to fit all tabs (Library, Audio Engine, Shortcuts) without unwanted scrollbars.
* **Focus Ring & Key Trap Fix**: Removed default browser slider focus rings and added automatic `blur()` on Seekbar and Volume sliders to prevent hotkey capture bugs.
* **Lyrics Text Toggle Hotkey (`T`)**: Quick hotkey to toggle between centered album art mode and lyrics display.

---

## 📦 Download & Run (Standalone 1-File Executable)

ZennyFLAC Player requires **no installation** and **no Python environment**. Simply download and double-click to run:

| Binary File | Operating System | File Size | Description |
| :--- | :--- | :--- | :--- |
| **`ZennyFLAC_Player.exe`** | Windows 10 / 11 (64-bit) | **~33.7 MB** | Official Standalone 1-File Executable |
| **`ZFPlayer.exe`** | Windows 10 / 11 (64-bit) | **~33.7 MB** | Short-name Alias Executable |

---
*Thank you for supporting **ZennyFLAC Player**!*
