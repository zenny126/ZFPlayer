import logging
import random
import threading
import time
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class PlayerService:
    def __init__(self, audio_engine, library_service, config, lyrics_worker=None):
        self.audio_engine = audio_engine
        self.library_service = library_service
        self.config = config
        self.lyrics_worker = lyrics_worker
        self.current_path = self.config.get('last_track')
        self.normal_playlist = []
        self.shuffled_playlist = []
        self.current_playlist_id = self.config.get('last_playlist_id', 'all')
        self._load_token = 0
        self._vol_save_timer = None
        
        # In-memory active track cache (eliminates 3,600 SQLite queries/hour during polling)
        self._cached_track_path = None
        self._cached_track_info = None
        
        # Restore saved volume level
        saved_vol = self.config.get('volume', 0.8)
        self.audio_engine.set_volume(saved_vol)
        
        # Set up auto-next on track end
        self.audio_engine.on_track_end = lambda: self.next_track(user_initiated=False)

    def _preload_next_tracks_lyrics(self, current_path: str):
        if not self.lyrics_worker:
            return
        try:
            # 1. High Priority: Current track
            current_track = self.library_service.get_track_info(current_path)
            if current_track:
                self.lyrics_worker.enqueue_track(current_track, priority=True)

            # 2. High Priority: Next 5 tracks in playlist
            shuffle_mode = self.config.get('shuffle', False)
            active_list = self.shuffled_playlist if shuffle_mode else self.normal_playlist
            if not active_list:
                active_list = self.library_service.get_all_track_paths()
            if not active_list:
                return
                
            try:
                current_idx = active_list.index(current_path)
            except ValueError:
                current_idx = 0
                
            next_tracks = []
            for offset in range(1, 6):
                next_idx = (current_idx + offset) % len(active_list)
                next_path = active_list[next_idx]
                track_info = self.library_service.get_track_info(next_path)
                if track_info:
                    next_tracks.append(track_info)
                    
            if next_tracks:
                self.lyrics_worker.enqueue_tracks(next_tracks, priority=True)
        except Exception as e:
            logger.debug(f"Failed to enqueue next tracks lyrics: {e}")

    def _sync_playlists_and_index(self, path: str, playlist_id: Any = None):
        prev_pid = getattr(self, 'current_playlist_id', None)
        if playlist_id is not None:
            self.current_playlist_id = playlist_id
            self.config.set('last_playlist_id', playlist_id)
        else:
            if not getattr(self, 'current_playlist_id', None):
                self.current_playlist_id = self.config.get('last_playlist_id', 'all')
            playlist_id = self.current_playlist_id

        # Lazy check: If playlist ID hasn't changed and normal_playlist already has tracks and contains path, avoid querying SQLite
        needs_reload = (
            str(prev_pid) != str(playlist_id) or
            not self.normal_playlist or
            (path and path not in self.normal_playlist)
        )

        if needs_reload:
            is_favorites = str(playlist_id) in ['favorites', '-1']
            real_playlist_id = int(playlist_id) if playlist_id is not None and str(playlist_id).isdigit() else None
            
            paths = self.library_service.get_all_track_paths(is_favorites=is_favorites, playlist_id=real_playlist_id)
            if not paths:
                paths = self.library_service.get_all_track_paths()
                
            if not paths:
                return
                
            self.normal_playlist = list(paths)
            self.shuffled_playlist = []
            
        paths = self.normal_playlist
        if not paths:
            return

        shuffle_mode = self.config.get('shuffle', False)
        
        if not self.shuffled_playlist or len(self.shuffled_playlist) != len(paths) or set(self.shuffled_playlist) - set(paths):
            remaining = [p for p in paths if p != path]
            random.shuffle(remaining)
            self.shuffled_playlist = [path] + remaining if path in paths else remaining
            
        if shuffle_mode:
            if path in self.shuffled_playlist:
                self.current_playlist_index = self.shuffled_playlist.index(path)
            else:
                self.current_playlist_index = 0
        else:
            if path in self.normal_playlist:
                self.current_playlist_index = self.normal_playlist.index(path)
            else:
                self.current_playlist_index = 0

    def play(self, path: str, playlist_id: Any = None, immediate: bool = False) -> Dict[str, Any]:
        logger.info(f"Playing track: {path} (playlist_id={playlist_id}, immediate={immediate})")
        if playlist_id is not None:
            self.current_playlist_id = playlist_id
        
        self.current_path = path
        self.config.set('last_track', path)
        
        # Cache current track metadata in RAM safely
        self._cached_track_path = path
        try:
            self._cached_track_info = self.library_service.get_track_info(path)
        except Exception as e:
            logger.debug(f"Non-fatal track_info cache error: {e}")
        
        # Record play history safely
        try:
            if hasattr(self.library_service, 'db'):
                self.library_service.db.update_last_played(path)
        except Exception as e:
            logger.debug(f"Non-fatal update_last_played error: {e}")
        
        # Keep playlist indices in sync for the scoped playlist
        try:
            self._sync_playlists_and_index(path, playlist_id)
        except Exception as e:
            logger.warning(f"Error syncing playlist in play(): {e}")


        # Cancel any existing load timer
        if hasattr(self, '_load_timer') and self._load_timer:
            self._load_timer.cancel()
            
        # Stop current playback immediately
        self.audio_engine.stop()

        self._load_token += 1
        current_token = self._load_token

        def do_load(target_path: str, token: int):
            try:
                # Abort if the token is stale
                if token != self._load_token:
                    return
                # Abort if the user skipped again while waiting
                if self.current_path != target_path:
                    return
                self.audio_engine.load(target_path)
                
                # Double check after loading (which can take some time)
                if token != self._load_token or self.current_path != target_path:
                    self.audio_engine.stop()
                    return
                self.audio_engine.play()
                self._consecutive_load_failures = 0
                
                # Asynchronously preload the next 5 tracks' lyrics
                threading.Thread(target=self._preload_next_tracks_lyrics, args=(target_path,), daemon=True).start()
            except Exception as e:
                logger.error(f"Playback load failed for {target_path}: {e}")
                # Auto-skip unplayable/missing files if this load is still the active one
                if token == self._load_token and self.current_path == target_path:
                    self._consecutive_load_failures = getattr(self, '_consecutive_load_failures', 0) + 1
                    if self._consecutive_load_failures >= 10:
                        logger.warning("Stopped auto-skipping: 10 consecutive load failures detected")
                        self.stop()
                    else:
                        logger.info(f"Auto-advancing to next track (failure {self._consecutive_load_failures}/10)")
                        self.next_track(user_initiated=False)

        if immediate:
            # Auto-advance: load directly, no debounce needed
            do_load(path, current_token)
        else:
            # User-initiated: 0.3s debounce for rapid clicking
            self._load_timer = threading.Timer(0.3, do_load, args=(path, current_token))
            self._load_timer.start()
        
        return self.get_state()

    def pause(self) -> Dict[str, Any]:
        logger.info("Pausing playback")
        self.audio_engine.pause()
        return self.get_state()

    def resume(self) -> Dict[str, Any]:
        logger.info("Resuming playback")
        if self.audio_engine.state.name in ('IDLE', 'STOPPED'):
            if self.current_path:
                return self.play(self.current_path, self.current_playlist_id)
        self.audio_engine.resume()
        return self.get_state()

    def stop(self) -> Dict[str, Any]:
        logger.info("Stopping playback")
        self.audio_engine.stop()
        return self.get_state()

    def seek(self, seconds: float) -> Dict[str, Any]:
        logger.info(f"Seeking to {seconds}s")
        self.audio_engine.seek(seconds)
        return self.get_state()

    def set_volume(self, level: float) -> None:
        level = max(0.0, min(1.0, float(level)))
        self.audio_engine.set_volume(level)
        
        # Debounce disk I/O config save by 0.3s
        if hasattr(self, '_vol_save_timer') and self._vol_save_timer:
            self._vol_save_timer.cancel()
        self._vol_save_timer = threading.Timer(0.3, lambda: self.config.set('volume', level))
        self._vol_save_timer.daemon = True
        self._vol_save_timer.start()

    def insert_play_next(self, path: str) -> Dict[str, Any]:
        logger.info(f"Queuing track to play next: {path}")
        if not path:
            return {"status": "error", "message": "Invalid track path"}
            
        self._sync_playlists_and_index(self.current_path or '', self.current_playlist_id)

        # Insert after current_path in normal_playlist
        if path in self.normal_playlist:
            self.normal_playlist.remove(path)
        if self.current_path and self.current_path in self.normal_playlist:
            idx = self.normal_playlist.index(self.current_path)
            self.normal_playlist.insert(idx + 1, path)
        else:
            self.normal_playlist.insert(0, path)

        # Insert after current_path in shuffled_playlist
        if path in self.shuffled_playlist:
            self.shuffled_playlist.remove(path)
        if self.current_path and self.current_path in self.shuffled_playlist:
            idx = self.shuffled_playlist.index(self.current_path)
            self.shuffled_playlist.insert(idx + 1, path)
        else:
            self.shuffled_playlist.insert(0, path)

        return {"status": "success", "message": "Track queued as next"}

    def set_active_playlist(self, playlist_id: Any) -> Dict[str, Any]:
        logger.info(f"Setting active playlist scope to: {playlist_id}")
        self.current_playlist_id = playlist_id
        self.config.set('last_playlist_id', playlist_id)
        if self.current_path:
            self._sync_playlists_and_index(self.current_path, playlist_id)
        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        state = self.audio_engine.get_state()
        
        # If we are currently debouncing a track load, pretend we are playing
        # so the UI Play/Pause button doesn't flicker to 'Paused'
        if hasattr(self, '_load_timer') and self._load_timer and self._load_timer.is_alive():
            state['is_playing'] = True
            
        if self.current_path:
            # Use cached track metadata in memory (Zero SQLite queries during continuous 1Hz polling)
            if self._cached_track_path != self.current_path or self._cached_track_info is None:
                self._cached_track_info = self.library_service.get_track_info(self.current_path)
                self._cached_track_path = self.current_path
            state['track'] = self._cached_track_info
        else:
            state['track'] = None
        return state

    def next_track(self, user_initiated: bool = True) -> Optional[Dict[str, Any]]:
        logger.info(f"Skipping to next track (active playlist_id={self.current_playlist_id})")
        immediate = not user_initiated  # Auto-advance skips debounce
        if not self.current_path:
            # If no track is loaded, start from the first track of active playlist
            self._sync_playlists_and_index('', self.current_playlist_id)
            shuffle_mode = self.config.get('shuffle', False)
            active_list = self.shuffled_playlist if shuffle_mode else self.normal_playlist
            if active_list:
                return self.play(active_list[0], self.current_playlist_id, immediate=immediate)
            return None
            
        repeat_mode = self.config.get('repeat', 'off')
        if not user_initiated and repeat_mode == 'one':
            return self.play(self.current_path, self.current_playlist_id, immediate=True)
            
        self._sync_playlists_and_index(self.current_path, self.current_playlist_id)
        
        shuffle_mode = self.config.get('shuffle', False)
        active_list = self.shuffled_playlist if shuffle_mode else self.normal_playlist
        if not active_list:
            return None
        
        # Calculate current index dynamically inside active_list
        if self.current_path in active_list:
            cur_idx = active_list.index(self.current_path)
            next_index = cur_idx + 1
        else:
            next_index = 0
            
        if next_index >= len(active_list):
            if repeat_mode == 'all' or user_initiated:
                next_index = 0
            else:
                self.stop()
                return self.get_state()
                
        self.current_playlist_index = next_index
        return self.play(active_list[next_index], self.current_playlist_id, immediate=immediate)

    def prev_track(self) -> Optional[Dict[str, Any]]:
        logger.info(f"Skipping to previous track (active playlist_id={self.current_playlist_id})")
        # Standard UX: If current track has played for > 3.0s, seek back to 0:00 instead of skipping track
        current_state = self.audio_engine.get_state()
        if current_state.get('position_seconds', 0.0) > 3.0:
            return self.seek(0.0)

        if not self.current_path:
            self._sync_playlists_and_index('', self.current_playlist_id)
            shuffle_mode = self.config.get('shuffle', False)
            active_list = self.shuffled_playlist if shuffle_mode else self.normal_playlist
            if active_list:
                return self.play(active_list[-1], self.current_playlist_id)
            return None
            
        self._sync_playlists_and_index(self.current_path, self.current_playlist_id)
        
        shuffle_mode = self.config.get('shuffle', False)
        active_list = self.shuffled_playlist if shuffle_mode else self.normal_playlist
        if not active_list:
            return None
            
        if self.current_path in active_list:
            cur_idx = active_list.index(self.current_path)
            prev_index = cur_idx - 1
        else:
            prev_index = len(active_list) - 1
            
        if prev_index < 0:
            prev_index = len(active_list) - 1
            
        self.current_playlist_index = prev_index
        return self.play(active_list[prev_index], self.current_playlist_id)
