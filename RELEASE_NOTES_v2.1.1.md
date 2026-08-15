# 🎵 ZennyFLAC Player v2.1.1 — Quality Assurance & Resilient Self-Healing Update

The **v2.1.1** release introduces an automated, high-speed Unit Test Suite covering 100% of the player's core engineering domains, hardens SQLite database self-healing on Windows, and guarantees zero-regression code quality.

---

## ✨ What's New & Highlights in v2.1.1

### 1. 🧪 Comprehensive Automated Unit Test Suite
* **29 Isolated Unit Tests Running in 0.65s**:
  - **Audio RingBuffer** (`test_audio_buffer.py`): Validates circular memory wrap-around, overflow protection, underrun zero-filling (anti-pop), and concurrent multi-threaded producer-consumer stability across 20,000 frames.
  - **SQLite Database & FTS5** (`test_database.py`): Validates full-text search indexing with Vietnamese diacritics, atomic bulk playlist transactions, lyrics negative caching with 7-day TTL, and self-healing.
  - **Lyrics Engine** (`test_lyrics.py`): Validates deterministic SHA-256 cache keys, 5-tier local-first resolution order, and LRCLIB integration.
  - **Library Scanner** (`test_scanner.py`): Validates incremental scanning based on `mtime` and `size`, format filters, and USB disconnect safety protection.
  - **API Controllers** (`test_api.py`): Validates playback commands, volume control, library pagination, and config management.
* **1-Click Test Runner**: Added [`run_tests.bat`](file:///d:/ZFPlayer/run_tests.bat) and [`pytest.ini`](file:///d:/ZFPlayer/pytest.ini) for instant local verification.

### 2. 🛡️ Hardened SQLite Self-Healing & File Lock Resolution
* **Guaranteed Windows File Lock Release**: Refactored `_check_and_heal_database` in [`database.py`](file:///d:/ZFPlayer/backend/storage/database.py) with strict `try...finally` connection teardown and garbage collection to eliminate `[WinError 32]` permission errors when recovering corrupted SQLite files on Windows.
* **Clean Connection Teardown**: Added a dedicated `close()` method to `Database` for graceful thread-local cleanup.

### 3. 📦 Binary & Version Metadata
* Updated Windows Executable Resource Info to **`v2.1.1.0`**.
* Single-file standalone executable remains at an ultra-compact **~33.7 MB**.

---

## 📦 Download & Run (Standalone 1-File Executable)

ZennyFLAC Player requires **no installation** and **no Python environment**. Simply download and double-click to run:

| Binary File | Operating System | File Size | Description |
| :--- | :--- | :--- | :--- |
| **`ZennyFLAC_Player.exe`** | Windows 10 / 11 (64-bit) | **~33.7 MB** | Official Standalone 1-File Executable |
| **`ZFPlayer.exe`** | Windows 10 / 11 (64-bit) | **~33.7 MB** | Short-name Alias Executable |

---
*Thank you for using **ZennyFLAC Player**!*
