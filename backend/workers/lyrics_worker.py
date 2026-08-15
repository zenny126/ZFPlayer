import hashlib
import threading
import os
import json
import queue
import time
import unicodedata
import requests
from requests.adapters import HTTPAdapter
from typing import Optional, Dict, Any, List
import logging

from backend.storage.database import Database
from backend.storage.cache import CacheManager
import syncedlyrics

logger = logging.getLogger(__name__)

class LyricsWorker:
    def __init__(self, database: Database, cache_manager: Optional[CacheManager] = None, throttle_delay: float = 0.4):
        self.database = database
        self.cache_manager = cache_manager
        self.throttle_delay = throttle_delay
        self._fetching_keys = set()
        self._fetching_lock = threading.Lock()
        self._fetching_condition = threading.Condition(self._fetching_lock)

        # Persistent HTTP session with connection pooling and keep-alive
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'ZennyFLACPlayer/2.0 (AudioCraftsmanship/1.0; https://github.com/zenny126/ZFPlayer)',
            'Accept': 'application/json'
        })
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=1)
        self._session.mount('https://', adapter)
        self._session.mount('http://', adapter)

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
        self._worker_thread = threading.Thread(target=self._queue_loop, daemon=True, name="LyricsQueueWorker")
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
                
                # Check DB cache first before performing any fetch
                db_cache = self.database.get_lyrics(cache_key)
                if not db_cache:
                    prio_name = "High" if priority_val < 5 else "Low"
                    logger.info(f"[Lyrics Worker] Fetching [{prio_name}]: {title} - {artist}")
                    self.fetch_lyrics(artist, title, album, duration, path)
                    
                    # Apply polite throttling only for bulk background scan tasks
                    if priority_val >= 5:
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

    @staticmethod
    def normalize_string(text: str) -> str:
        if not text:
            return ""
        norm = unicodedata.normalize('NFKC', str(text)).strip().lower()
        return " ".join(norm.split())

    def _get_cache_key(self, artist: str, title: str, album: str = '', duration: float = 0.0) -> str:
        norm_artist = self.normalize_string(artist)
        norm_title = self.normalize_string(title)
        norm_dur = round(float(duration or 0))
        s = f"{norm_artist}|{norm_title}|{norm_dur}"
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

    def _fetch_lrclib_exact(self, artist: str, title: str, album: str = '', duration: float = 0.0) -> Optional[str]:
        try:
            params = {
                'artist_name': artist,
                'track_name': title
            }
            if album:
                params['album_name'] = album
            if duration > 0:
                params['duration'] = round(duration)
                
            resp = self._session.get('https://lrclib.net/api/get', params=params, timeout=(1.5, 2.5))
            if resp.status_code == 200:
                data = resp.json()
                if data and data.get('syncedLyrics'):
                    return data['syncedLyrics']
        except Exception as e:
            logger.debug(f"LRCLIB exact get failed for {artist} - {title}: {e}")
        return None

    def _fetch_lrclib_search(self, artist: str, title: str, duration: float = 0.0) -> Optional[str]:
        try:
            params = {'artist_name': artist, 'track_name': title}
            resp = self._session.get('https://lrclib.net/api/search', params=params, timeout=(1.5, 3.0))
            if resp.status_code == 200:
                results = resp.json()
                if results and isinstance(results, list):
                    best_match = None
                    min_diff = float('inf')
                    for res in results:
                        synced = res.get('syncedLyrics')
                        if not synced:
                            continue
                        res_dur = res.get('duration', 0)
                        diff = abs(res_dur - duration) if duration > 0 else 0
                        if diff < min_diff:
                            min_diff = diff
                            best_match = res
                    
                    if best_match and (duration == 0 or min_diff <= 3.5):
                        return best_match.get('syncedLyrics')
        except Exception as e:
            logger.debug(f"LRCLIB search failed for {artist} - {title}: {e}")
        return None

    def _fetch_syncedlyrics_fallback(self, artist: str, title: str) -> Optional[str]:
        try:
            search_query = f"{title} {artist}"
            lrc = syncedlyrics.search(search_query, providers=["Musixmatch", "NetEase", "Megalobiz"])
            if lrc and ('[' in lrc and ':' in lrc):
                return lrc
        except Exception as e:
            logger.debug(f"syncedlyrics fetch failed for {artist} - {title}: {e}")
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
            # Re-check cache in case another thread just stored it
            db_cache = self.database.get_lyrics(cache_key)
            if db_cache:
                if db_cache.get('synced_lyrics') == '[NO_LYRICS]':
                    return {'synced_lyrics': '', 'plain_lyrics': '', 'source': 'none'}
                return db_cache

            lyrics_text = None
            source_name = None
            api_reached = False

            # --- LOCAL-FIRST TIER 1: Check Local .lrc Sidecar File (< 1ms) ---
            if not lyrics_text and path:
                lyrics_text = self._read_local_lrc(path)
                if lyrics_text:
                    source_name = 'local_lrc'

            # --- LOCAL-FIRST TIER 2: Check Embedded Audio Tags (< 5ms) ---
            if not lyrics_text and path:
                lyrics_text = self._read_embedded_lyrics(path)
                if lyrics_text:
                    source_name = 'embedded_tag'

            is_valid_meta = (
                bool(artist) and bool(title) and
                artist.strip().lower() not in ['unknown', 'unknown artist'] and
                title.strip().lower() != 'unknown'
            )

            # --- NETWORK TIER 3: LRCLIB Exact Match Fast-Path (~30-100ms) ---
            if not lyrics_text and is_valid_meta:
                lyrics_text = self._fetch_lrclib_exact(artist, title, album, duration)
                if lyrics_text:
                    source_name = 'lrclib_exact'
                    api_reached = True
                else:
                    # If exact match failed, we still reached the API server
                    api_reached = True

            # --- NETWORK TIER 4: LRCLIB Fuzzy Search Fallback (~200-500ms) ---
            if not lyrics_text and is_valid_meta:
                lyrics_text = self._fetch_lrclib_search(artist, title, duration)
                if lyrics_text:
                    source_name = 'lrclib_search'
                    api_reached = True

            # --- NETWORK TIER 5: Multi-provider fallback via syncedlyrics ---
            if not lyrics_text and is_valid_meta:
                lyrics_text = self._fetch_syncedlyrics_fallback(artist, title)
                if lyrics_text:
                    source_name = 'syncedlyrics'
                    api_reached = True

            # --- PERSIST RESULT TO CACHE ---
            if lyrics_text:
                result = {'synced_lyrics': lyrics_text, 'plain_lyrics': '', 'source': source_name}
                self.database.save_lyrics(cache_key, lyrics_text, '', source_name)
                return result
            elif api_reached:
                # Online lookup completed with no lyrics found -> Save negative cache with TTL
                logger.info(f"No lyrics found for: {title} - {artist}. Saving negative cache.")
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
