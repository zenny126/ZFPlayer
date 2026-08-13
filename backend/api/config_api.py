import logging
import webview
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ConfigAPI:
    def __init__(self, config, audio_engine=None):
        self.config = config
        self.audio_engine = audio_engine

    def get_config(self) -> Dict[str, Any]:
        return self.config._data

    def set_config(self, key: str, value: Any) -> Dict[str, Any]:
        self.config.set(key, value)
        if key == 'audio_mode' and self.audio_engine:
            self.audio_engine.set_audio_mode(value)
        return self.get_config()

    def set_audio_mode(self, mode: str) -> Dict[str, Any]:
        if self.audio_engine:
            active_mode = self.audio_engine.set_audio_mode(mode)
        else:
            self.config.set('audio_mode', mode)
            active_mode = mode
        return {"status": "success", "audio_mode": active_mode}

    def select_music_dir(self) -> Optional[str]:
        # Use webview window to create file dialog
        windows = webview.windows
        if not windows:
            return None
            
        window = windows[0]
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        
        if result and len(result) > 0:
            return result[0]
        return None

    def select_music_file(self) -> Optional[str]:
        windows = webview.windows
        if not windows:
            return None
        result = windows[0].create_file_dialog(webview.OPEN_DIALOG, file_types=('Audio Files (*.flac;*.mp3;*.wav;*.ogg)', 'All files (*.*)'))
        if result and len(result) > 0:
            return result[0]
        return None

    def select_music_files(self) -> Optional[List[str]]:
        windows = webview.windows
        if not windows:
            return None
        result = windows[0].create_file_dialog(webview.OPEN_DIALOG, file_types=('Audio Files (*.flac;*.mp3;*.wav;*.ogg)', 'All files (*.*)'), allow_multiple=True)
        if result and len(result) > 0:
            return list(result)
        return None

    def select_cover_image(self) -> Optional[str]:
        windows = webview.windows
        if not windows:
            return None
        result = windows[0].create_file_dialog(webview.OPEN_DIALOG, file_types=('Image Files (*.jpg;*.jpeg;*.png;*.webp)', 'All files (*.*)'))
        if result and len(result) > 0:
            return result[0]
        return None
