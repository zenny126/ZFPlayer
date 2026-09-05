import os
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
from bottle import Bottle

from backend.app import (
    AppServices,
    QuietWSGIRequestHandler,
    _init_core_services,
    _setup_routes,
    _handle_fatal_exception,
    setup_logging,
    get_free_port,
)


def test_setup_logging():
    """Verify setup_logging initializes and returns a valid Logger."""
    app_logger = setup_logging()
    assert isinstance(app_logger, logging.Logger)


def test_quiet_wsgi_request_handler():
    """Verify QuietWSGIRequestHandler methods execute cleanly without throwing."""
    handler = QuietWSGIRequestHandler.__new__(QuietWSGIRequestHandler)
    handler.client_address = ("127.0.0.1", 54321)
    
    assert handler.address_string() == "127.0.0.1"
    # Should not throw when log_message is called
    handler.log_message("GET %s %s", "/test", "200")


def test_setup_routes(temp_dir):
    """Verify _setup_routes registers all expected static routes."""
    app = Bottle()
    frontend_dir = Path(temp_dir) / "frontend"
    covers_dir = Path(temp_dir) / "covers"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    covers_dir.mkdir(parents=True, exist_ok=True)

    _setup_routes(app, frontend_dir, covers_dir)

    routes = [r.rule for r in app.routes]
    assert "/" in routes
    assert "/css/<filename:path>" in routes
    assert "/js/<filename:path>" in routes
    assert "/api/covers/<filename:path>" in routes
    assert "/favicon.ico" in routes


def test_get_free_port():
    """Verify get_free_port returns an available positive integer port."""
    port = get_free_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535


def test_init_core_services():
    """Verify _init_core_services instantiates all necessary components in AppServices."""
    services = _init_core_services()
    assert isinstance(services, AppServices)
    assert services.database is not None
    assert services.config is not None
    assert services.cache_manager is not None
    assert services.audio_engine is not None
    assert services.lyrics_worker is not None
    assert services.metadata_worker is not None
    assert services.scanner is not None
    assert services.library_service is not None
    assert services.player_service is not None
    assert services.api is not None


def test_handle_fatal_exception(temp_dir):
    """Verify _handle_fatal_exception logs to file and displays error dialog safely."""
    with patch("backend.app.get_app_data_dir", return_value=Path(temp_dir)), \
         patch("ctypes.windll.user32.MessageBoxW", return_value=1):
        test_err = RuntimeError("Test crash scenario")
        _handle_fatal_exception(test_err)

        crash_file = Path(temp_dir) / "logs" / "crash.log"
        assert crash_file.exists()
        content = crash_file.read_text(encoding="utf-8")
        assert "Test crash scenario" in content
