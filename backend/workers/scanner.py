import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Callable, Optional
from backend.workers.metadata_worker import MetadataWorker
from backend.storage.database import Database
from backend.storage.cache import CacheManager

class LibraryScanner:
    def __init__(self, database: Database, cache_manager: CacheManager, lyrics_worker=None):
        self.database = database
        self.cache_manager = cache_manager
        self.lyrics_worker = lyrics_worker
        self.metadata_worker = MetadataWorker()
        self.stop_event = threading.Event()
        self.supported_exts = {'.flac', '.wav', '.mp3', '.ogg', '.aiff'}

    def scan(self, music_dirs: List[str], progress_callback: Optional[Callable[[int, int, str], None]] = None, handle_deletions: bool = True):
        self.stop_event.clear()
        
        all_files = []
        for d in music_dirs:
            for root, _, files in os.walk(d):
                if self.stop_event.is_set():
                    return
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in self.supported_exts:
                        all_files.append(os.path.join(root, f))
                        
        total = len(all_files)
        if total == 0:
            if progress_callback:
                progress_callback(0, 0, "")
            if handle_deletions:
                for path in self.database.get_all_tracks():
                    self.database.delete_track(path['path'])
            return

        existing_tracks = {t['path']: t for t in self.database.get_all_tracks()}
        to_process = []
        
        for path in all_files:
            if self.stop_event.is_set():
                return
            try:
                mtime = os.path.getmtime(path)
                size = os.path.getsize(path)
                
                existing = existing_tracks.get(path)
                if not existing or existing['mtime'] != mtime or existing['size'] != size:
                    to_process.append((path, mtime, size))
            except Exception:
                pass
                
        # Handle deletions
        if handle_deletions:
            disk_paths = set(all_files)
            for path in existing_tracks:
                if path not in disk_paths:
                    self.database.delete_track(path)

        scanned = 0
        batch = []
        batch_size = 100

        def _process_file(args):
            path, mtime, size = args
            if self.stop_event.is_set():
                return None
            track_dict = self.metadata_worker.extract(path)
            if track_dict:
                track_dict['mtime'] = mtime
                track_dict['size'] = size
                
                cover_bytes = track_dict.pop('_cover_bytes', None)
                if cover_bytes and track_dict.get('cover_hash'):
                    self.cache_manager.save_cover(cover_bytes, track_dict['cover_hash'])
                    self.cache_manager.save_thumbnail(cover_bytes, track_dict['cover_hash'])
                    
            return track_dict

        def _prefetch_lyrics_for_batch(track_batch):
            if not self.lyrics_worker: return
            self.lyrics_worker.enqueue_tracks(track_batch, priority=False)

        with ThreadPoolExecutor(max_workers=4) as executor:
            for track_dict in executor.map(_process_file, to_process):
                if self.stop_event.is_set():
                    break
                scanned += 1
                if track_dict:
                    batch.append(track_dict)
                    if len(batch) >= batch_size:
                        self.database.bulk_insert_tracks(batch)
                        threading.Thread(target=_prefetch_lyrics_for_batch, args=(list(batch),), daemon=True).start()
                        batch.clear()
                if progress_callback and track_dict:
                    progress_callback(scanned, len(to_process), track_dict.get('path', ''))
            
            if batch:
                self.database.bulk_insert_tracks(batch)
                threading.Thread(target=_prefetch_lyrics_for_batch, args=(list(batch),), daemon=True).start()

    def stop(self):
        self.stop_event.set()
