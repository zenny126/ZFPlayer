import hashlib
import threading
import os
import json
import queue
import time
import urllib.request
import urllib.parse
import urllib.error
from mutagen.flac import FLAC
from typing import Optional, Dict, Any, List
import logging

from backend.storage.database import Database
from backend.storage.cache import CacheManager
import syncedlyrics

logger = logging.getLogger(__name__)

class LyricsWorker:
    def __init__(self, database: Database, cache_manager: CacheManager, throttle_delay: float = 0.5):
        self.database = database
        self.cache_manager = cache_manager
        self.throttle_delay = throttle_delay
        self._fetching_keys = set()
        self._fetching_lock = threading.Lock()
        self._fetching_condition = threading.Condition(self._fetching_lock)

        # Background Priority Queue for low-impact background lyrics fetching
        # Item format: (priority_level, seq, track_info) where priority_level 1 = High, 10 = Low
        self._queue = queue.PriorityQueue()
        self._queued_keys = set()
        self._queue_lock = threading.Lock()
        self._seq = 0
        self._worker_running = False
        self._start_queue_worker()

    def _start_queue_worker(self):
        if self._worker_running:
            return
        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._queue_loop, daemon=True)
        self._worker_thread.start()

    def _queue_loop(self):
        while True:
            cache_key = None
            try:
                priority_val, seq, track_info = self._queue.get()
                artist = track_info.get('artist', '')
                title = track_info.get('title', '')
                album = track_info.get('album', '')
                duration = track_info.get('duration', 0.0)
                path = track_info.get('path', '')
                
                cache_key = self._get_cache_key(artist, title, album, duration)
                
                # Double check DB cache fast before calling fetch
                db_cache = self.database.get_lyrics(cache_key)
                if not db_cache:
                    prio_name = "High" if priority_val < 5 else "Low"
                    logger.info(f"[Lyrics Queue Worker] Fetching [{prio_name} Priority]: {title} - {artist}")
                    self.fetch_lyrics(artist, title, album, duration, path)
                    time.sleep(self.throttle_delay)
            except Exception as e:
                logger.error(f"Error in lyrics queue worker: {e}")
            finally:
                if cache_key:
                    with self._queue_lock:
                        self._queued_keys.discard(cache_key)
                self._queue.task_done()

    def enqueue_tracks(self, tracks: List[Dict[str, Any]], priority: bool = False):
        for track in tracks:
            self.enqueue_track(track, priority=priority)

    def enqueue_track(self, track_info: Dict[str, Any], priority: bool = False):
        if not track_info:
            return
        artist = track_info.get('artist', '')
        title = track_info.get('title', '')
        if not artist or not title or artist.strip().lower() in ['unknown', 'unknown artist'] or title.strip().lower() == 'unknown':
            return
            
        album = track_info.get('album', '')
        duration = track_info.get('duration', 0.0)
        cache_key = self._get_cache_key(artist, title, album, duration)
        
        # Check DB cache fast
        db_cache = self.database.get_lyrics(cache_key)
        if db_cache:
            return
            
        with self._queue_lock:
            if cache_key in self._queued_keys and not priority:
                return
            self._queued_keys.add(cache_key)
            self._seq += 1
            priority_val = 1 if priority else 10
            self._queue.put((priority_val, self._seq, track_info))

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

            # Priority 1: Check Local .lrc Sidecar File (Same folder, same name)
            if not lyrics_text and path:
                lyrics_text = self._read_local_lrc(path)
                if lyrics_text:
                    source_name = 'local_lrc'

            # Priority 2: Try LRCLIB Search API (track_name & artist_name, min_diff <= 3.0s, max 2 attempts)
            if not lyrics_text and artist and title and artist.strip().lower() not in ['unknown', 'unknown artist'] and title.strip().lower() != 'unknown':
                for attempt in range(2):
                    try:
                        params = urllib.parse.urlencode({'track_name': title, 'artist_name': artist})
                        url = f'https://lrclib.net/api/search?{params}'
                        req = urllib.request.Request(url, headers={'User-Agent': 'ZennyFLACPlayer/2.0'})
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
                                
                                if best_match and (duration == 0 or min_diff <= 3.0):
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

            # Priority 3: Check Embedded Audio Tags (FLAC/MP3 lyrics)
            if not lyrics_text and path:
                lyrics_text = self._read_embedded_lyrics(path)
                if lyrics_text:
                    source_name = 'embedded_tag'

            # Priority 4: Try syncedlyrics library (Musixmatch, NetEase, Megalobiz, max 2 attempts)
            if not lyrics_text and artist and title and artist.strip().lower() not in ['unknown', 'unknown artist'] and title.strip().lower() != 'unknown':
                for attempt in range(2):
                    try:
                        search_query = f"{title} {artist}"
                        lrc = syncedlyrics.search(search_query, providers=["Musixmatch", "NetEase", "Megalobiz"])
                        api_reached = True
                        if lrc:
                            lyrics_text = lrc
                            source_name = 'syncedlyrics'
                        break
                    except Exception as e:
                        logger.debug(f"syncedlyrics fetch failed attempt {attempt} for {artist} - {title}: {e}")
                        import time
                        time.sleep(0.3)

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
