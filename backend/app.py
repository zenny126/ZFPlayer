import os
import sys
import logging
import threading
import webview
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server, WSGIServer
from bottle import Bottle, static_file, request, response

from backend.utils.path_utils import get_bundle_dir

# Ensure project root is in sys.path when run directly
PROJECT_ROOT = get_bundle_dir()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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

# Setup Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- Threading WSGI Server for Bottle ---
class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True

def make_threaded_server(host, port, app):
    return make_server(host, port, app, ThreadingWSGIServer)

# --- Unified API Class ---
class ZFPlayerAPI(PlayerAPI, LibraryAPI, LyricsAPI, ConfigAPI):
    def __init__(self, player_service, library_service, lyrics_worker, config):
        PlayerAPI.__init__(self, player_service)
        LibraryAPI.__init__(self, library_service, config)
        LyricsAPI.__init__(self, lyrics_worker)
        ConfigAPI.__init__(self, config)

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
    logger.info("Starting ZeroFLAC Player Backend...")

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
    library_service = LibraryService(database, cache_manager, scanner, lyrics_worker)
    player_service = PlayerService(audio_engine, library_service, config, lyrics_worker)

    # 4. Initialize Unified API
    api = ZFPlayerAPI(player_service, library_service, lyrics_worker, config)

    # 5. Setup Bottle Server
    app = Bottle()
    
    # Frontend Paths
    frontend_dir = PROJECT_ROOT / 'frontend'
    covers_dir = Path(cache_manager.cache_dir) / 'covers' if hasattr(cache_manager, 'cache_dir') else PROJECT_ROOT / 'cache' / 'covers'
    
    # Create covers dir if not exists
    os.makedirs(covers_dir, exist_ok=True)

    @app.route('/')
    def serve_index():
        return static_file('index.html', root=str(frontend_dir))

    @app.route('/css/<filename:path>')
    def serve_css(filename):
        return static_file(filename, root=str(frontend_dir / 'css'))

    @app.route('/js/<filename:path>')
    def serve_js(filename):
        return static_file(filename, root=str(frontend_dir / 'js'))

    @app.route('/api/covers/<filename:path>')
    def serve_covers(filename):
        return static_file(filename, root=str(covers_dir))

    # Start Bottle Server in background thread
    port = get_free_port()
    server = make_threaded_server('127.0.0.1', port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    logger.info(f"Bottle server running on http://127.0.0.1:{port}")

    # 6. PyWebView Window setup
    window = webview.create_window(
        'ZeroFLAC Player',
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
        audio_engine.stop()
        if hasattr(database, 'close'):
            database.close()
        server.shutdown()

    window.events.loaded += on_loaded
    window.events.closed += on_closed

    # Start PyWebView (Debug enabled only when --debug flag or ZFPLAYER_DEBUG=1 is set)
    debug_mode = "--debug" in sys.argv or os.environ.get("ZFPLAYER_DEBUG") == "1"
    webview.start(debug=debug_mode)

if __name__ == '__main__':
    main()
