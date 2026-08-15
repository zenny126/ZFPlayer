import logging
import threading
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class LibraryService:
    def __init__(self, database, cache_manager, scanner, lyrics_worker=None, config=None):
        self.db = database
        self.cache = cache_manager
        self.scanner = scanner
        self.lyrics_worker = lyrics_worker
        self.config = config
        
        self._scan_state = {
            'is_scanning': False,
            'scanned': 0,
            'total': 0,
            'current_file': ''
        }

    def get_tracks(self, offset: int = 0, limit: int = 50, search: str = '', sort_by: str = 'title', sort_dir: str = 'ASC', is_favorites: bool = False, playlist_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.db.get_tracks_paginated(offset, limit, search, sort_by, sort_dir, is_favorites, playlist_id)

    def get_recently_played(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.db.get_recently_played(limit)

    def get_all_track_paths(self, is_favorites: bool = False, playlist_id: Optional[int] = None) -> List[str]:
        return self.db.get_all_track_paths(is_favorites, playlist_id)

    def get_track_count(self, search: str = '', is_favorites: bool = False, playlist_id: Optional[int] = None) -> int:
        return self.db.get_track_count(search, is_favorites, playlist_id)

    def get_track_info(self, path: str) -> Optional[Dict[str, Any]]:
        track = self.db.get_track_by_path(path)
        if not track:
            return None
            
        # Get cached cover path URL equivalent (we'll format it as an API URL for frontend)
        cover_hash = track.get('cover_hash')
        if cover_hash:
            track['cover_url'] = f"/api/covers/{cover_hash}_thumb.jpg"
        else:
            track['cover_url'] = None
            
        return track

    def get_albums(self) -> List[Dict[str, Any]]:
        albums = self.db.get_albums()
        for album in albums:
            cover_hash = album.get('cover_hash')
            if cover_hash:
                album['cover_url'] = f"/api/covers/{cover_hash}_thumb.jpg"
            else:
                album['cover_url'] = None
        return albums

    def _internal_progress_callback(self, scanned: int, total: int, current_file: str) -> None:
        self._scan_state['scanned'] = scanned
        self._scan_state['total'] = total
        self._scan_state['current_file'] = current_file

    def scan_library(self, progress_callback=None) -> None:
        if self._scan_state['is_scanning']:
            logger.warning("Scan already in progress")
            return

        music_dirs = self.config.get('music_dirs', [])

        self._scan_state['is_scanning'] = True
        self._scan_state['scanned'] = 0
        self._scan_state['total'] = 0
        
        def run_scan():
            try:
                def composite_callback(scanned, total, current_file):
                    self._internal_progress_callback(scanned, total, current_file)
                    if progress_callback:
                        progress_callback(scanned, total, current_file)
                        
                self.scanner.scan(music_dirs, progress_callback=composite_callback)
                self._prefetch_all_lyrics()
            except Exception as e:
                logger.error(f"Error during library scan: {e}")
            finally:
                self._scan_state['is_scanning'] = False
                
        thread = threading.Thread(target=run_scan, daemon=True)
        thread.start()

    def _prefetch_all_lyrics(self):
        if not self.lyrics_worker:
            return
        tracks = self.db.get_all_tracks()
        if not tracks:
            return
        logger.info(f"Enqueuing auto lyrics prefetch for {len(tracks)} tracks into background queue...")
        self.lyrics_worker.enqueue_tracks(tracks, priority=False)

    def get_scan_progress(self) -> Dict[str, Any]:
        return self._scan_state.copy()

    def add_album(self, folder_path: str, album_name: str = '', cover_image_path: str = '', config=None) -> Dict[str, Any]:
        if not folder_path:
            return {'status': 'error', 'message': 'Folder path is required.'}

        # 1. Update config music_dirs
        if config:
            dirs = config.get('music_dirs', [])
            if folder_path not in dirs:
                dirs.append(folder_path)
                config.set('music_dirs', dirs)

        # 2. Process custom cover image if provided
        cover_hash = None
        if cover_image_path and os.path.exists(cover_image_path):
            try:
                import hashlib
                with open(cover_image_path, 'rb') as f:
                    image_bytes = f.read()
                if image_bytes:
                    cover_hash = hashlib.sha256(image_bytes).hexdigest()
                    self.cache.save_cover(image_bytes, cover_hash)
                    self.cache.save_thumbnail(image_bytes, cover_hash)
            except Exception as e:
                logger.error(f"Error processing custom album cover: {e}")

        # 3. Perform scan on the folder
        def _scan_and_update():
            try:
                self.scanner.scan([folder_path])
                
                # Apply custom album name / cover hash updates
                updates = {}
                if album_name:
                    updates['album'] = album_name
                if cover_hash:
                    updates['cover_hash'] = cover_hash
                    
                if updates:
                    self.db.update_tracks_in_folder(folder_path, updates)

                # Auto prefetch lyrics
                self._prefetch_all_lyrics()
            except Exception as e:
                logger.error(f"Error in add_album background task: {e}")

        thread = threading.Thread(target=_scan_and_update, daemon=True)
        thread.start()

        return {'status': 'success', 'message': 'Album added and scan started.'}

    # --- Playlist Methods ---
    def create_playlist(self, name: str, folder_path: str = None) -> int:
        return self.db.create_playlist(name, folder_path)

    def delete_playlist(self, playlist_id: int):
        self.db.delete_playlist(playlist_id)

    def rename_playlist(self, playlist_id: int, new_name: str):
        self.db.rename_playlist(playlist_id, new_name)

    def update_playlist_cover(self, playlist_id: Any, cover_image_path: str) -> Dict[str, Any]:
        if not cover_image_path or not os.path.exists(cover_image_path):
            return {'status': 'error', 'message': 'Cover image not found'}
        try:
            import hashlib
            with open(cover_image_path, 'rb') as f:
                image_bytes = f.read()
            if image_bytes:
                cover_hash = hashlib.sha256(image_bytes).hexdigest()
                self.cache.save_cover(image_bytes, cover_hash)
                self.cache.save_thumbnail(image_bytes, cover_hash)
                cover_url = f"/api/covers/{cover_hash}_thumb.jpg"
                pid_str = str(playlist_id)
                if pid_str in ['all', 'favorites']:
                    from backend.storage.config import Config
                    cfg = self.config or Config()
                    cfg.set(f"cover_{pid_str}", cover_url)
                    return {'status': 'success', 'cover_hash': cover_hash, 'cover_url': cover_url}
                elif pid_str.isdigit():
                    self.db.update_playlist_cover(int(pid_str), cover_hash)
                    return {'status': 'success', 'cover_hash': cover_hash, 'cover_url': cover_url}
        except Exception as e:
            logger.error(f"Error updating playlist cover: {e}")
            return {'status': 'error', 'message': str(e)}
        return {'status': 'error', 'message': 'Invalid playlist id'}

    def get_system_playlist_covers(self) -> Dict[str, Any]:
        from backend.storage.config import Config
        cfg = self.config or Config()
        return {
            'all': cfg.get("cover_all"),
            'favorites': cfg.get("cover_favorites")
        }

    def get_playlists(self) -> List[Dict[str, Any]]:
        playlists = self.db.get_playlists()
        for p in playlists:
            cover_hash = p.get('cover_hash')
            if cover_hash:
                p['cover_url'] = f"/api/covers/{cover_hash}_thumb.jpg"
            else:
                p['cover_url'] = None
        return playlists

    def add_track_to_playlist(self, playlist_id: int, track_path: str):
        self.db.add_track_to_playlist(playlist_id, track_path)

    def remove_track_from_playlist(self, playlist_id: int, track_path: str):
        self.db.remove_track_from_playlist(playlist_id, track_path)

    def import_folder_to_playlist(self, playlist_id: int, folder_path: str) -> Dict[str, Any]:
        if not folder_path:
            return {'status': 'error', 'message': 'Folder path is required'}
            
        self._scan_state['is_scanning'] = True
        self._scan_state['scanned'] = 0
        self._scan_state['total'] = 0
        self._scan_state['current_file'] = ''

        def progress_cb(scanned, total, current_file):
            self._internal_progress_callback(scanned, total, current_file)

        try:
            # 1. Scan folder to ensure tracks are in DB
            self.scanner.scan([folder_path], progress_callback=progress_cb, handle_deletions=False)
            
            # 2. Add all tracks in folder to playlist in a single atomic bulk transaction
            paths = self.db.get_tracks_in_folder(folder_path)
            added_count = self.db.add_tracks_to_playlist_bulk(playlist_id, paths)
                
            # 3. Trigger async lyrics prefetch
            threading.Thread(target=self._prefetch_all_lyrics, daemon=True).start()
            
            return {'status': 'success', 'message': f'Successfully imported {added_count} tracks', 'added_count': added_count}
        except Exception as e:
            logger.error(f"Error importing folder to playlist: {e}")
            return {'status': 'error', 'message': str(e)}
        finally:
            self._scan_state['is_scanning'] = False

    def import_files_to_playlist(self, playlist_id: int, file_paths: List[str]) -> Dict[str, Any]:
        if not file_paths:
            return {'status': 'error', 'message': 'No files provided'}
            
        self._scan_state['is_scanning'] = True
        self._scan_state['scanned'] = 0
        self._scan_state['total'] = len(file_paths)
        self._scan_state['current_file'] = ''

        def progress_cb(scanned, total, current_file):
            self._internal_progress_callback(scanned, total, current_file)

        try:
            # Group files by directory to scan efficiently
            dirs_to_scan = set(os.path.dirname(p) for p in file_paths)
            self.scanner.scan(list(dirs_to_scan), progress_callback=progress_cb, handle_deletions=False)
            
            # Add tracks in a single atomic bulk transaction
            added_count = self.db.add_tracks_to_playlist_bulk(playlist_id, file_paths)
                
            # Trigger async lyrics prefetch
            threading.Thread(target=self._prefetch_all_lyrics, daemon=True).start()
            
            return {'status': 'success', 'message': f'Successfully imported {added_count} tracks', 'added_count': added_count}
        except Exception as e:
            logger.error(f"Error importing files to playlist: {e}")
            return {'status': 'error', 'message': str(e)}
        finally:
            self._scan_state['is_scanning'] = False

    def get_bootstrap_data(self, player_service=None) -> Dict[str, Any]:
        config_data = self.config._data if self.config else {}
        player_state = player_service.get_state() if player_service else None
        playlists = self.get_playlists()
        system_covers = self.get_system_playlist_covers()
        recently_played = self.get_recently_played(20)
        total_tracks = self.get_track_count()
        
        return {
            'config': config_data,
            'player_state': player_state,
            'playlists': playlists,
            'system_covers': system_covers,
            'recently_played': recently_played,
            'total_tracks': total_tracks
        }

    def update_track(self, path: str, updates: Dict[str, Any]):
        self.db.update_track(path, updates)

    def clear_database(self, clear_cache: bool = True) -> Dict[str, Any]:
        try:
            self.db.clear_database()
            if clear_cache and hasattr(self, 'cache'):
                self.cache.clear_all()
            return {'status': 'success', 'message': 'Database and library cleared successfully'}
        except Exception as e:
            logger.error(f"Error clearing database: {e}")
            return {'status': 'error', 'message': str(e)}
