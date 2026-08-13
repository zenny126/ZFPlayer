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
        self._fetching_condition = threading.Condition(self._fetching_lock)

    def _get_cache_key(self, artist: str, title: str, album: str, duration: float) -> str:
        s = f"{artist}|{title}|{album}|{duration}"
        return hashlib.sha256(s.encode('utf-8')).hexdigest()

    def _read_local_lrc(self, path: str) -> Optional[str]:
        if not path or not os.path.exists(path):
            return None
        lrc_path = os.path.splitext(path)[0] + '.lrc'
        if os.path.exists(lrc_path):
            try:
                with open(lrc_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                    if content and ('[' in content and ']' in content):
                        logger.info(f"Found local .lrc file: {lrc_path}")
                        return content
            except Exception as e:
                logger.debug(f"Error reading local lrc {lrc_path}: {e}")
        return None

    def _read_embedded_lyrics(self, path: str) -> Optional[str]:
        if not path or not os.path.exists(path):
            return None
        try:
            import mutagen
            f = mutagen.File(path)
            if f is None:
                return None
            
            # 1. Check FLAC / Vorbis comment tags (Must contain [mm:ss] timestamps to be considered synced lyrics)
            if hasattr(f, 'get'):
                for key in ['syncedlyrics', 'lyrics_synced', 'lyrics', 'unsyncedlyrics']:
                    val = f.get(key)
                    if val and isinstance(val, list) and val[0]:
                        text = str(val[0]).strip()
                        if text and ('[' in text and ':' in text):
                            logger.info(f"Found embedded synced FLAC lyrics ({key}) in: {path}")
                            return text
            
            # 2. Check MP3 ID3 tags (Must contain [mm:ss] timestamps to be considered synced lyrics)
            if hasattr(f, 'tags') and f.tags:
                for key, tag in f.tags.items():
                    if key.startswith('SYLT') or key.startswith('USLT') or key.startswith('ULT'):
                        text = getattr(tag, 'text', '') or str(tag)
                        text = text.strip()
                        if text and ('[' in text and ':' in text):
                            logger.info(f"Found embedded synced MP3 lyrics ({key}) in: {path}")
                            return text
        except Exception as e:
            logger.debug(f"Error extracting embedded lyrics from {path}: {e}")
        return None

    def fetch_lyrics(self, artist: str, title: str, album: str = '', duration: float = 0.0, path: str = '') -> Optional[Dict[str, str]]:
        cache_key = self._get_cache_key(artist, title, album, duration)
        
        with self._fetching_condition:
            db_cache = self.database.get_lyrics(cache_key)
            if db_cache:
                if db_cache.get('synced_lyrics') == '[NO_LYRICS]':
                    return {'synced_lyrics': '', 'plain_lyrics': '', 'source': 'none'}
                return db_cache

            if cache_key in self._fetching_keys:
                logger.debug(f"Waiting for ongoing lyrics fetch for: {title} - {artist}")
                self._fetching_condition.wait(timeout=3.5)
                db_cache = self.database.get_lyrics(cache_key)
                if db_cache:
                    if db_cache.get('synced_lyrics') == '[NO_LYRICS]':
                        return {'synced_lyrics': '', 'plain_lyrics': '', 'source': 'none'}
                    return db_cache

            self._fetching_keys.add(cache_key)
            
        try:
            db_cache = self.database.get_lyrics(cache_key)
            if db_cache:
                if db_cache.get('synced_lyrics') == '[NO_LYRICS]':
                    return {'synced_lyrics': '', 'plain_lyrics': '', 'source': 'none'}
                return db_cache

            lyrics_text = None
            source_name = None
            api_reached = False

            # Priority 1: Try LRCLIB /api/get (Instant exact match online)
            if artist and title and artist.strip().lower() not in ['unknown', 'unknown artist'] and title.strip().lower() != 'unknown':
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
                    pass # Network error / timeout

                # Priority 2: Try Musixmatch via syncedlyrics (Spotify Official Provider)
                if not lyrics_text:
                    try:
                        search_query = f"{artist} - {title}"
                        lrc = syncedlyrics.search(search_query, providers=["Musixmatch"])
                        api_reached = True
                        if lrc:
                            lyrics_text = lrc
                            source_name = 'musixmatch'
                    except Exception as e:
                        logger.debug(f"Musixmatch fetch failed for {artist} - {title}: {e}")

                # Priority 3: Try LRCLIB /api/search (Search fallback with duration filtering)
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

                # Priority 4: Try Fallback Providers in syncedlyrics (NetEase, Megalobiz, Genius)
                if not lyrics_text:
                    try:
                        search_query = f"{artist} - {title}"
                        lrc = syncedlyrics.search(search_query, providers=["NetEase", "Megalobiz", "Genius"])
                        api_reached = True
                        if lrc:
                            lyrics_text = lrc
                            source_name = 'syncedlyrics_fallback'
                    except Exception as e:
                        logger.debug(f"Fallback providers fetch failed for {artist} - {title}: {e}")

            # Priority 5 (Local Fallback 1): Check Local .lrc Sidecar File
            if not lyrics_text and path:
                lyrics_text = self._read_local_lrc(path)
                if lyrics_text:
                    source_name = 'local_lrc'

            # Priority 6 (Local Fallback 2): Check Embedded Audio Tags (FLAC/MP3)
            if not lyrics_text and path:
                lyrics_text = self._read_embedded_lyrics(path)
                if lyrics_text:
                    source_name = 'embedded_tag'

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
            with self._fetching_condition:
                self._fetching_keys.discard(cache_key)
                self._fetching_condition.notify_all()

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
