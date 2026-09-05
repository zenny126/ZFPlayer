import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Callable, Optional, Dict, Any, Set, Tuple
from backend.workers.metadata_worker import MetadataWorker
from backend.storage.database import Database
from backend.storage.cache import CacheManager
import logging

logger = logging.getLogger(__name__)


class LibraryScanner:
    def __init__(self, database: Database, cache_manager: CacheManager, lyrics_worker=None):
        self.database = database
        self.cache_manager = cache_manager
        self.lyrics_worker = lyrics_worker
        self.metadata_worker = MetadataWorker()
        self.stop_event = threading.Event()
        self.supported_exts = {'.flac', '.wav', '.mp3', '.ogg', '.aiff'}
        self._seen_covers_in_scan: Set[str] = set()

    def _walk_directory_files(self, directory: str) -> List[str]:
        """Traverse a single directory and return matching audio file paths."""
        if not os.path.exists(directory):
            return []
        found_files: List[str] = []
        for root, _, files in os.walk(directory):
            if self.stop_event.is_set():
                break
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.supported_exts:
                    found_files.append(os.path.join(root, f))
        return found_files

    def _discover_audio_files(self, music_dirs: List[str]) -> List[str]:
        """Discover all supported audio files across input music directories."""
        discovered: List[str] = []
        for d in music_dirs:
            if self.stop_event.is_set():
                break
            discovered.extend(self._walk_directory_files(d))
        return discovered

    def _filter_unindexed_files(self, all_files: List[str], existing_tracks: Dict[str, Any]) -> List[Tuple[str, float, int]]:
        """Filter files requiring metadata extraction based on mtime and size comparison."""
        to_process: List[Tuple[str, float, int]] = []
        for path in all_files:
            if self.stop_event.is_set():
                break
            try:
                mtime = os.path.getmtime(path)
                size = os.path.getsize(path)
            except (OSError, PermissionError) as ex:
                logger.debug("Failed reading file stats for %s: %s", path, ex)
                continue

            existing = existing_tracks.get(path)
            if not existing or existing['mtime'] != mtime or existing['size'] != size:
                to_process.append((path, mtime, size))
        return to_process

    def _handle_deletions(self, accessible_dirs: List[str], existing_tracks: Dict[str, Any], disk_paths: Set[str]) -> None:
        """Safely delete missing records only for currently mounted, accessible directories."""
        if not accessible_dirs:
            return
        deleted_paths = [
            path for path in existing_tracks
            if path not in disk_paths and any(os.path.abspath(path).startswith(ad) for ad in accessible_dirs)
        ]
        if deleted_paths:
            logger.info("Pruning %d deleted tracks from library database", len(deleted_paths))
            self.database.delete_tracks_bulk(deleted_paths)

    def _process_single_file(self, args: Tuple[str, float, int]) -> Optional[Dict[str, Any]]:
        """Extract metadata and cache album art for a single audio file."""
        path, mtime, size = args
        if self.stop_event.is_set():
            return None
            
        track_dict = self.metadata_worker.extract(path)
        if not track_dict:
            return None

        track_dict['mtime'] = mtime
        track_dict['size'] = size
        
        cover_bytes = track_dict.pop('_cover_bytes', None)
        cover_hash = track_dict.get('cover_hash')
        if cover_bytes and cover_hash and cover_hash not in self._seen_covers_in_scan:
            self._seen_covers_in_scan.add(cover_hash)
            self.cache_manager.save_cover(cover_bytes, cover_hash)
            self.cache_manager.save_thumbnail(cover_bytes, cover_hash)
            
        return track_dict

    def _flush_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Insert track batch and enqueue lyrics prefetching into dedicated background queue."""
        if not batch:
            return
        self.database.bulk_insert_tracks(batch)
        if self.lyrics_worker:
            self.lyrics_worker.enqueue_tracks(list(batch), priority=False)
        batch.clear()

    def scan(self, music_dirs: List[str], progress_callback: Optional[Callable[[int, int, str], None]] = None, handle_deletions=True):
        self.stop_event.clear()
        self._seen_covers_in_scan.clear()

        all_files = self._discover_audio_files(music_dirs)
        total = len(all_files)
        accessible_dirs = [os.path.abspath(d) for d in music_dirs if os.path.exists(d)]
        existing_tracks = self.database.get_tracks_mtime_map()

        if total == 0:
            if progress_callback:
                progress_callback(0, 0, "")
            if handle_deletions:
                self._handle_deletions(accessible_dirs, existing_tracks, disk_paths=set())
            return

        to_process = self._filter_unindexed_files(all_files, existing_tracks)

        if handle_deletions:
            self._handle_deletions(accessible_dirs, existing_tracks, disk_paths=set(all_files))

        if not to_process:
            if progress_callback:
                progress_callback(total, total, "")
            return

        self._execute_batch_extraction(to_process, progress_callback)

    def _run_extraction_loop(self, to_process: List[Tuple[str, float, int]], progress_callback: Optional[Callable[[int, int, str], None]]) -> None:
        """Process files in parallel batches without exceeding nesting depth limits."""
        scanned = 0
        batch: List[Dict[str, Any]] = []
        batch_size = 100
        executor = ThreadPoolExecutor(max_workers=4)
        try:
            for track_dict in executor.map(self._process_single_file, to_process):
                if self.stop_event.is_set():
                    break
                scanned += 1
                if not track_dict:
                    continue
                batch.append(track_dict)
                if len(batch) >= batch_size:
                    self._flush_batch(batch)
                if progress_callback:
                    progress_callback(scanned, len(to_process), track_dict.get('path', ''))
            self._flush_batch(batch)
        finally:
            executor.shutdown(wait=False)

    def _execute_batch_extraction(self, to_process: List[Tuple[str, float, int]], progress_callback: Optional[Callable[[int, int, str], None]]) -> None:
        """Execute parallel extraction, batch inserts, and rebuild full-text search triggers."""
        self.database.disable_fts_triggers()
        try:
            self._run_extraction_loop(to_process, progress_callback)
        finally:
            self.database.enable_fts_triggers()
            self.database.rebuild_fts()

    def stop(self):
        self.stop_event.set()
