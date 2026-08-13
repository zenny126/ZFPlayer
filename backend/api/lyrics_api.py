import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LyricsAPI:
    def __init__(self, lyrics_worker):
        self.lyrics_worker = lyrics_worker

    def get_lyrics(self, artist: str, title: str, album: str = '', duration: float = 0.0, path: str = '') -> Dict[str, Any]:
        lyrics = self.lyrics_worker.fetch_lyrics(artist, title, album, duration, path)
        return lyrics if lyrics else {}

