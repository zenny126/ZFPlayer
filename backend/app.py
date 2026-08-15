import os
import sys
import logging
import threading
import webview
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server, WSGIServer
from bottle import Bottle, static_file, request, response

# Ensure project root is in sys.path when run directly
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(getattr(sys, '_MEIPASS', sys.executable)).resolve()
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safe stdio redirection for GUI / windowed mode on Windows
class NullWriter:
    def write(self, text):
        pass
    def flush(self):
        pass

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()

from backend.utils.path_utils import get_bundle_dir, get_cache_dir, get_app_data_dir

from backend.storage.database import Database
from backend.storage.config import Config
from backend.storage.cache import CacheManager
from backend.audio.engine import AudioEngine
from backend.workers.lyrics_worker import LyricsWorker
from backend.workers.metadata_worker import MetadataWorker
from backend.workers.scanner import LibraryScanner

from backend.services.player_service import PlayerService
from backend.services.library_service import LibraryService

from backend.api.player_api import PlayerAPI
from backend.api.library_api import LibraryAPI
from backend.api.lyrics_api import LyricsAPI
from backend.api.config_api import ConfigAPI

# Setup Dual Logging (Persistent File + Safe Stream)
_is_debug = "--debug" in sys.argv or os.environ.get("ZFPLAYER_DEBUG") == "1"
log_handlers = []

try:
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"
    file_handler = logging.FileHandler(str(log_file), mode='a', encoding='utf-8')
    log_handlers.append(file_handler)
except Exception:
    pass

if sys.stdout and not isinstance(sys.stdout, NullWriter):
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.DEBUG if _is_debug else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=log_handlers or [logging.NullHandler()]
)
logger = logging.getLogger(__name__)


# --- Fast Threading WSGI Server for Bottle (Zero DNS lookup delay) ---
from wsgiref.simple_server import WSGIRequestHandler

class QuietWSGIRequestHandler(WSGIRequestHandler):
    def address_string(self):
        # Avoid blocking reverse DNS resolution (getfqdn) which delays requests by 1-2s on Windows
        return self.client_address[0]
    
    def log_message(self, format, *args):
        # Eliminate synchronous stderr / file logging overhead on every static asset request
        pass

class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True

def make_threaded_server(host, port, app):
    return make_server(host, port, app, server_class=ThreadingWSGIServer, handler_class=QuietWSGIRequestHandler)


# --- Unified API Class ---
class ZFPlayerAPI(PlayerAPI, LibraryAPI, LyricsAPI, ConfigAPI):
    def __init__(self, player_service, library_service, lyrics_worker, config, audio_engine):
        self.player_service = player_service
        PlayerAPI.__init__(self, player_service)
        LibraryAPI.__init__(self, library_service, config)
        LyricsAPI.__init__(self, lyrics_worker)
        ConfigAPI.__init__(self, config, audio_engine)

    def toggle_fullscreen(self):
        import webview
        if webview.windows:
            webview.windows[0].toggle_fullscreen()

def get_free_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def main():
    logger.info("Starting ZennyFLAC Player Backend...")

    # 1. Initialize Core Infrastructure
    database = Database()
    config = Config()
    cache_manager = CacheManager()
    audio_engine = AudioEngine()
    
    # 2. Initialize Workers
    lyrics_worker = LyricsWorker(database, cache_manager)
    metadata_worker = MetadataWorker()
    scanner = LibraryScanner(database, cache_manager, lyrics_worker)

    # 3. Initialize Services
    library_service = LibraryService(database, cache_manager, scanner, lyrics_worker, config)
    player_service = PlayerService(audio_engine, library_service, config, lyrics_worker)

    # 4. Initialize Unified API
    api = ZFPlayerAPI(player_service, library_service, lyrics_worker, config, audio_engine)

    # 5. Setup Bottle Server
    app = Bottle()
    
    # Frontend Paths
    frontend_dir = PROJECT_ROOT / 'frontend'
    covers_dir = Path(cache_manager.cache_dir) / 'covers' if hasattr(cache_manager, 'cache_dir') else PROJECT_ROOT / 'cache' / 'covers'
    
    # Create covers dir if not exists
    os.makedirs(covers_dir, exist_ok=True)

    @app.route('/')
    def serve_index():
        return static_file('index.html', root=str(frontend_dir), headers={'Cache-Control': 'no-cache'})

    @app.route('/css/<filename:path>')
    def serve_css(filename):
        return static_file(filename, root=str(frontend_dir / 'css'), headers={'Cache-Control': 'public, max-age=86400'})

    @app.route('/js/<filename:path>')
    def serve_js(filename):
        return static_file(filename, root=str(frontend_dir / 'js'), headers={'Cache-Control': 'public, max-age=86400'})

    @app.route('/api/covers/<filename:path>')
    def serve_covers(filename):
        return static_file(filename, root=str(covers_dir), headers={'Cache-Control': 'public, max-age=31536000, immutable'})

    @app.route('/favicon.ico')
    def serve_favicon():
        return static_file('favicon.ico', root=str(frontend_dir), headers={'Cache-Control': 'public, max-age=604800'})

    # Start Bottle Server in background thread
    port = get_free_port()
    server = make_threaded_server('127.0.0.1', port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    logger.info(f"Bottle server running on http://127.0.0.1:{port}")

    # 6. PyWebView Window setup
    window = webview.create_window(
        'ZennyFLAC Player',
        url=f'http://127.0.0.1:{port}',
        js_api=api,
        width=1280,
        height=800,
        min_size=(900, 600)
    )

    def on_loaded():
        logger.info("Webview loaded, running startup tasks.")
        # Load volume
        vol = config.get('volume', 1.0)
        audio_engine.set_volume(vol)
        
        # If music dirs configured, optionally trigger a scan or at least we know library is ready
        music_dirs = config.get('music_dirs', [])
        if music_dirs:
            logger.info("Music directories found. Library ready.")
            # window.evaluate_js('console.log("Backend ready");')

    def on_closed():
        logger.info("Window closed. Cleaning up...")
        audio_engine.shutdown_hardware_stream()
        if hasattr(database, 'close'):
            database.close()
        server.shutdown()

    window.events.loaded += on_loaded
    window.events.closed += on_closed

    # Start PyWebView (Debug enabled only when --debug flag or ZFPLAYER_DEBUG=1 is set)
    debug_mode = "--debug" in sys.argv or os.environ.get("ZFPLAYER_DEBUG") == "1"
    webview_storage = Path(get_cache_dir()) / "webview"
    os.makedirs(webview_storage, exist_ok=True)
    webview.start(debug=debug_mode, private_mode=False, storage_path=str(webview_storage))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.critical(f"Fatal unhandled exception in main: {tb}")
        try:
            from backend.utils.path_utils import get_app_data_dir
            crash_file = get_app_data_dir() / "logs" / "crash.log"
            crash_file.parent.mkdir(parents=True, exist_ok=True)
            with open(str(crash_file), "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass

        # If on Windows, pop up an error box so it never crashes silently
        try:
            import ctypes
            msg = f"ZennyFLAC Player encountered an unexpected error:\n\n{e}\n\nDetailed traceback written to:\n%APPDATA%\\ZFPlayer\\logs\\crash.log"
            ctypes.windll.user32.MessageBoxW(0, msg, "ZennyFLAC Player Error", 0x10)
        except Exception:
            pass
        sys.exit(1)

