import json
import os
import threading
from typing import Any

class Config:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(Config, cls).__new__(cls)
            return cls._instance

    def __init__(self, config_path: str = r"d:\ZFPlayer\config\config.json"):
        if not hasattr(self, 'initialized'):
            self.config_path = config_path
            self._data = {}
            self._save_timer = None
            self.load()
            self.initialized = True

    def load(self):
        default_config = {
            "music_dirs": [],
            "volume": 0.8,
            "repeat": "off",
            "shuffle": False,
            "theme": "dark",
            "last_track": None,
            "last_position": 0
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._data = {**default_config, **data}
            except Exception as e:
                print(f"Error loading config: {e}")
                self._data = default_config.copy()
        else:
            self._data = default_config.copy()
            self._schedule_save()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self._schedule_save()

    def _schedule_save(self):
        if self._save_timer is not None:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(0.5, self._save)
        self._save_timer.start()

    def _save(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        temp_path = self.config_path + ".tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2)
            os.replace(temp_path, self.config_path)
        except Exception as e:
            print(f"Error saving config: {e}")
