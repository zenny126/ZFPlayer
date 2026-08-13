import hashlib
import threading
import os
import json
import urllib.request
import urllib.parse
import urllib.error
from mutagen.flac import FLAC
from typing import Optional, Dict, Any
import logging

from backend.storage.database import Database
from backend.storage.cache import CacheManager
import syncedlyrics

logger = logging.getLogger(__name__)

class LyricsWorker:
    def __init__(self, database: Database, cache_manager: CacheManager):
        self.database = database
        self.cache_manager = cache_manager
        self._fetching_keys = set()
        self._fetching_lock = threading.Lock()

    def _get_cache_key(self, artist: str, title: str, album: str, duration: float) -> str:
        s = f"{artist}|{title}|{album}|{duration}"
        return hashlib.sha256(s.encode('utf-8')).hexdigest()

    def fetch_lyrics(self, artist: str, title: str, album: str = '', duration: float = 0.0, path: str = '') -> Optional[Dict[str, str]]:
        cache_key = self._get_cache_key(artist, title, album, duration)
        
        with self._fetching_lock:
            if cache_key in self._fetching_keys:
                logger.debug(f"Skipping fetch, already fetching lyrics for: {title} - {artist}")
                return None
            self._fetching_keys.add(cache_key)
            
        try:
            db_cache = self.database.get_lyrics(cache_key)
            if db_cache:
                if db_cache.get('synced_lyrics') == '[NO_LYRICS]':
                    return {'synced_lyrics': '', 'plain_lyrics': '', 'source': 'none'}
                return db_cache

            api_reached = False
            lyrics_text = None
            source_name = None

            if artist and title and artist != 'Unknown Artist':
                # 1. Try /api/get (Instant exact match)
                try:
                    params = urllib.parse.urlencode({
                        'track_name': title,
                        'artist_name': artist,
                        'album_name': album,
                        'duration': int(duration) if duration > 0 else 0
                    })
                    url = f'https://lrclib.net/api/get?{params}'
                    req = urllib.request.Request(url, headers={'User-Agent': 'ZeroFLACPlayer/2.0'})
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        api_reached = True
                        res = json.loads(resp.read().decode('utf-8'))
                        if res and res.get('syncedLyrics'):
                            lyrics_text = res['syncedLyrics']
                            source_name = 'lrclib_get'
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        api_reached = True # Reached API, confirmed no exact match exists
                except Exception:
                    pass # Network error / timeout, we do NOT set api_reached = True

                # 2. Try /api/search (Search fallback)
                if not lyrics_text:
                    for attempt in range(2):
                        try:
                            params = urllib.parse.urlencode({'track_name': title, 'artist_name': artist})
                            url = f'https://lrclib.net/api/search?{params}'
                            req = urllib.request.Request(url, headers={'User-Agent': 'ZeroFLACPlayer/2.0'})
                            with urllib.request.urlopen(req, timeout=3) as resp:
                                api_reached = True
                                results = json.loads(resp.read().decode('utf-8'))
                                if results:
                                    best_match = None
                                    min_diff = float('inf')
                                    for res in results:
                                        if not res.get('syncedLyrics'):
                                            continue
                                        res_dur = res.get('duration', 0)
                                        diff = abs(res_dur - duration) if duration > 0 else 0
                                        if diff < min_diff:
                                            min_diff = diff
                                            best_match = res
                                    
                                    if best_match and (duration == 0 or min_diff <= 5.0):
                                        lyrics_text = best_match['syncedLyrics']
                                        source_name = 'lrclib_search'
                            break
                        except urllib.error.HTTPError as e:
                            if e.code == 404:
                                api_reached = True
                            break
                        except Exception:
                            import time
                            time.sleep(0.3)

                # 3. Try syncedlyrics fallback
                if not lyrics_text:
                    try:
                        # If syncedlyrics runs and returns None or empty, the API was reached successfully
                        lrc = syncedlyrics.search(f"{artist} - {title}", providers=["lrclib", "musixmatch", "netease"])
                        api_reached = True
                        if lrc:
                            lyrics_text = lrc
                            source_name = 'syncedlyrics'
                    except Exception:
                        pass

            # Final Cache Decision
            if lyrics_text:
                result = {'synced_lyrics': lyrics_text, 'plain_lyrics': '', 'source': source_name}
                self.database.save_lyrics(cache_key, lyrics_text, '', source_name)
                self.cache_manager.save_lyrics_cache(cache_key, result)
                return result
            elif api_reached:
                # Reached APIs successfully but no lyrics exist. Save negative cache.
                logger.info(f"No lyrics found online for: {title} - {artist}. Saving negative cache.")
                self.database.save_lyrics(cache_key, '[NO_LYRICS]', '', 'none')
                return {'synced_lyrics': '', 'plain_lyrics': '', 'source': 'none'}

            return None
        finally:
            with self._fetching_lock:
                self._fetching_keys.discard(cache_key)

    def preload(self, track_info: Dict[str, Any]):
        def _fetch():
            self.fetch_lyrics(
                track_info.get('artist', ''),
                track_info.get('title', ''),
                track_info.get('album', ''),
                track_info.get('duration', 0.0),
                track_info.get('path', '')
            )
        
        t = threading.Thread(target=_fetch, daemon=True)
        t.start()
