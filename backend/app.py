import os
import sys
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Tuple, List, Optional
from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
import webview
from bottle import Bottle, static_file, request, response

# Ensure project root is in sys.path when run directly
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(getattr(sys, '_MEIPASS', sys.executable)).resolve()
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Auto-bootstrap virtual environment if executed via global Python lacking dependencies
if not getattr(sys, 'frozen', False):
    _venv_py = PROJECT_ROOT / '.venv' / 'Scripts' / 'python.exe'
    if _venv_py.is_file() and Path(sys.executable).resolve() != _venv_py.resolve():
        try:
            import sounddevice  # noqa: F401
            import webview  # noqa: F401
        except ImportError:
            import subprocess
            sys.exit(subprocess.call([str(_venv_py)] + sys.argv))

# Safe stdio redirection for GUI / windowed mode on Windows
class NullWriter:
    def write(self, text: str) -> None:
        pass
    def flush(self) -> None:
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


# --- Setup Dual Logging (Persistent File + Safe Stream) ---
def setup_logging() -> logging.Logger:
    """Configure dual logging: persistent file handler and safe stdout stream."""
    is_debug = "--debug" in sys.argv or os.environ.get("ZFPLAYER_DEBUG") == "1"
    handlers: List[logging.Handler] = []
    file_init_error: Optional[Exception] = None

    try:
        log_dir = get_app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
        handlers.append(logging.FileHandler(str(log_file), mode='a', encoding='utf-8'))
    except OSError as err:
        file_init_error = err

    if sys.stdout and not isinstance(sys.stdout, NullWriter):
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.DEBUG if is_debug else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=handlers or [logging.NullHandler()]
    )
    app_logger = logging.getLogger(__name__)
    if file_init_error:
        app_logger.warning("Failed to initialize file logging handler: %s", file_init_error)
    return app_logger


logger = setup_logging()


# --- Fast Threading WSGI Server for Bottle (Zero DNS lookup delay) ---
class QuietWSGIRequestHandler(WSGIRequestHandler):
    def address_string(self) -> str:
        # Avoid blocking reverse DNS resolution (getfqdn) which delays requests by 1-2s on Windows
        return self.client_address[0]
    
    def log_message(self, format: str, *args) -> None:
        # Route synchronous request logging to debug logger instead of bare pass
        logger.debug("WSGI: " + format, *args)


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def make_threaded_server(host: str, port: int, app: Bottle) -> WSGIServer:
    return make_server(host, port, app, server_class=ThreadingWSGIServer, handler_class=QuietWSGIRequestHandler)


# --- Unified API Class ---
class ZFPlayerAPI(PlayerAPI, LibraryAPI, LyricsAPI, ConfigAPI):
    def __init__(
        self,
        player_service: PlayerService,
        library_service: LibraryService,
        lyrics_worker: LyricsWorker,
        config: Config,
        audio_engine: AudioEngine,
    ):
        self.player_service = player_service
        PlayerAPI.__init__(self, player_service)
        LibraryAPI.__init__(self, library_service, config)
        LyricsAPI.__init__(self, lyrics_worker)
        ConfigAPI.__init__(self, config, audio_engine, player_service)

    def toggle_fullscreen(self) -> None:
        if webview.windows:
            webview.windows[0].toggle_fullscreen()


def get_free_port() -> int:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --- Modular Decomposed Helpers for Main Application ---
@dataclass(frozen=True)
class AppServices:
    """Core domain services, workers, and unified API instance."""
    database: Database
    config: Config
    cache_manager: CacheManager
    audio_engine: AudioEngine
    lyrics_worker: LyricsWorker
    metadata_worker: MetadataWorker
    scanner: LibraryScanner
    library_service: LibraryService
    player_service: PlayerService
    api: ZFPlayerAPI


def _init_core_services() -> AppServices:
    """Instantiate core database, workers, audio engine, and domain services."""
    database = Database()
    config = Config()
    cache_manager = CacheManager()
    audio_engine = AudioEngine()

    lyrics_worker = LyricsWorker(database, cache_manager)
    metadata_worker = MetadataWorker()
    scanner = LibraryScanner(database, cache_manager, lyrics_worker)

    library_service = LibraryService(database, cache_manager, scanner, lyrics_worker, config)
    player_service = PlayerService(audio_engine, library_service, config, lyrics_worker)

    api = ZFPlayerAPI(player_service, library_service, lyrics_worker, config, audio_engine)
    return AppServices(
        database=database,
        config=config,
        cache_manager=cache_manager,
        audio_engine=audio_engine,
        lyrics_worker=lyrics_worker,
        metadata_worker=metadata_worker,
        scanner=scanner,
        library_service=library_service,
        player_service=player_service,
        api=api,
    )


def _setup_routes(app: Bottle, frontend_dir: Path, covers_dir: Path) -> None:
    """Register HTTP static file serving routes for frontend UI assets and covers."""
    @app.route('/')
    def serve_index():
        return static_file('index.html', root=str(frontend_dir), headers={'Cache-Control': 'no-cache'})

    @app.route('/css/<filename:path>')
    def serve_css(filename: str):
        return static_file(filename, root=str(frontend_dir / 'css'), headers={'Cache-Control': 'public, max-age=86400'})

    @app.route('/js/<filename:path>')
    def serve_js(filename: str):
        return static_file(filename, root=str(frontend_dir / 'js'), headers={'Cache-Control': 'public, max-age=86400'})

    @app.route('/api/covers/<filename:path>')
    def serve_covers(filename: str):
        return static_file(filename, root=str(covers_dir), headers={'Cache-Control': 'public, max-age=31536000, immutable'})

    @app.route('/favicon.ico')
    def serve_favicon():
        return static_file('favicon.ico', root=str(frontend_dir), headers={'Cache-Control': 'public, max-age=604800'})


def _start_server(app: Bottle) -> Tuple[WSGIServer, int]:
    """Start background threaded WSGI server on an available localhost port."""
    port = get_free_port()
    server = make_threaded_server('127.0.0.1', port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logger.info("Bottle server running on http://127.0.0.1:%d", port)
    return server, port


def _configure_webview_window(
    api: ZFPlayerAPI,
    config: Config,
    audio_engine: AudioEngine,
    database: Database,
    server: WSGIServer,
    port: int,
) -> webview.Window:
    """Create and configure the main pywebview desktop window and event lifecycle hooks."""
    window = webview.create_window(
        'ZennyFLAC Player',
        url=f'http://127.0.0.1:{port}',
        js_api=api,
        width=1280,
        height=800,
        min_size=(900, 600),
    )

    def on_loaded():
        logger.info("Webview loaded, running startup tasks.")
        vol = config.get('volume', 1.0)
        audio_engine.set_volume(vol)
        music_dirs = config.get('music_dirs', [])
        if music_dirs:
            logger.info("Music directories found. Library ready.")

    def on_closed():
        logger.info("Window closed. Cleaning up...")
        audio_engine.shutdown_hardware_stream()
        if hasattr(database, 'close'):
            database.close()
        server.shutdown()

    window.events.loaded += on_loaded
    window.events.closed += on_closed
    return window


def _start_webview() -> None:
    """Launch PyWebView main event loop with isolated webview cache directory."""
    debug_mode = "--debug" in sys.argv or os.environ.get("ZFPLAYER_DEBUG") == "1"
    webview_storage = Path(get_cache_dir()) / "webview"
    os.makedirs(webview_storage, exist_ok=True)
    webview.start(debug=debug_mode, private_mode=False, storage_path=str(webview_storage))


def _handle_fatal_exception(err: Exception) -> None:
    """Record unhandled exception details to disk and present graphical error alert."""
    import traceback
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    logger.critical("Fatal unhandled exception in main: %s", tb)

    try:
        crash_file = get_app_data_dir() / "logs" / "crash.log"
        crash_file.parent.mkdir(parents=True, exist_ok=True)
        with open(str(crash_file), "w", encoding="utf-8") as f:
            f.write(tb)
    except OSError as log_err:
        logger.error("Failed to write crash log file: %s", log_err)

    try:
        import ctypes
        msg = (
            f"ZennyFLAC Player encountered an unexpected error:\n\n{err}\n\n"
            "Detailed traceback written to:\n%APPDATA%\\ZFPlayer\\logs\\crash.log"
        )
        ctypes.windll.user32.MessageBoxW(0, msg, "ZennyFLAC Player Error", 0x10)
    except (OSError, AttributeError, RuntimeError) as dialog_err:
        logger.error("Failed to display fatal crash dialog: %s", dialog_err)


def main() -> None:
    """Application entry point: assemble core services, start HTTP server, and open GUI."""
    logger.info("Starting ZennyFLAC Player Backend...")

    services = _init_core_services()
    app = Bottle()

    frontend_dir = PROJECT_ROOT / 'frontend'
    covers_dir = (
        Path(services.cache_manager.cache_dir) / 'covers'
        if hasattr(services.cache_manager, 'cache_dir')
        else PROJECT_ROOT / 'cache' / 'covers'
    )
    os.makedirs(covers_dir, exist_ok=True)

    _setup_routes(app, frontend_dir, covers_dir)
    server, port = _start_server(app)

    _configure_webview_window(
        services.api,
        services.config,
        services.audio_engine,
        services.database,
        server,
        port,
    )
    _start_webview()


if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        _handle_fatal_exception(err)
        sys.exit(1)
