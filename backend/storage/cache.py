import os
import io
import json
from PIL import Image
from typing import Optional, Dict, Any, Tuple
from functools import lru_cache

from backend.utils.path_utils import get_cache_dir

class CacheManager:
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or get_cache_dir()
        self.covers_dir = os.path.join(self.cache_dir, "covers")
        self.lyrics_dir = os.path.join(self.cache_dir, "lyrics")
        self._cover_path_cache = {}
        
        os.makedirs(self.covers_dir, exist_ok=True)
        os.makedirs(self.lyrics_dir, exist_ok=True)

    def get_cover_path(self, cover_hash: str) -> Optional[str]:
        if not cover_hash:
            return None
        if cover_hash in self._cover_path_cache:
            return self._cover_path_cache[cover_hash]
        path = os.path.join(self.covers_dir, f"{cover_hash}.jpg")
        if os.path.exists(path):
            self._cover_path_cache[cover_hash] = path
            return path
        return None

    def save_cover(self, image_bytes: bytes, cover_hash: str) -> str:
        path = os.path.join(self.covers_dir, f"{cover_hash}.jpg")
        if not os.path.exists(path):
            try:
                img = Image.open(io.BytesIO(image_bytes))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(path, 'JPEG', quality=90, optimize=True)
            except Exception as e:
                print(f"Error saving cover: {e}")
                return ""
        self._cover_path_cache[cover_hash] = path
        return path

    def save_thumbnail(self, image_bytes: bytes, cover_hash: str, size: Tuple[int, int] = (300, 300)) -> str:
        thumb_hash = f"{cover_hash}_thumb"
        path = os.path.join(self.covers_dir, f"{thumb_hash}.jpg")
        if not os.path.exists(path):
            try:
                img = Image.open(io.BytesIO(image_bytes))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail(size)
                img.save(path, 'JPEG', quality=85, optimize=True)
            except Exception as e:
                print(f"Error saving thumbnail: {e}")
                return ""
        return path

    def get_lyrics_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.lyrics_dir, f"{cache_key}.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def save_lyrics_cache(self, cache_key: str, data: Dict[str, Any]):
        path = os.path.join(self.lyrics_dir, f"{cache_key}.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving lyrics cache: {e}")
