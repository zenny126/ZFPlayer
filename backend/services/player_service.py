import logging
import random
import threading
from typing import Dict, Optional, Any, List, Tuple

logger = logging.getLogger(__name__)


class PlayerService:
    """Core audio player coordination service managing playback, queues, and sync."""

    def __init__(self, audio_engine, library_service, config, lyrics_worker=None):
        self.audio_engine = audio_engine
        self.library_service = library_service
        self.config = config
        self.lyrics_worker = lyrics_worker
        self.current_path = self.config.get('last_track')
        self.user_queue: List[str] = []
        self.normal_playlist: List[str] = []
        self.shuffled_playlist: List[str] = []
        self.current_playlist_id = self.config.get('last_playlist_id', 'all')
        self.loaded_playlist_id: Optional[str] = None
        self.current_playlist_index = 0
        self._load_token = 0
        self._vol_save_timer = None
        self._load_timer = None
        self._consecutive_load_failures = 0

        # In-memory active track cache (eliminates 3,600 SQLite queries/hour during polling)
        self._cached_track_path = None
        self._cached_track_info = None

        # High-performance O(1) index maps & monotonic playlist versioning
        self._normal_index_map: Dict[str, int] = {}
        self._shuffled_index_map: Dict[str, int] = {}
        self._playlist_version = 0
        self._shuffled_version = -1

        # Restore saved volume level
        saved_vol = self.config.get('volume', 0.8)
        self.audio_engine.set_volume(saved_vol)

        # Set up auto-next on track end
        self.audio_engine.on_track_end = lambda: self.next_track(user_initiated=False)

    # -------------------------------------------------------------------------
    # Index Map & Queue Management
    # -------------------------------------------------------------------------

    @staticmethod
    def _rebuild_index_map(tracks: List[str]) -> Dict[str, int]:
        """Build an O(1) dictionary mapping track path to its first index."""
        index_map: Dict[str, int] = {}
        for idx, track_path in enumerate(tracks):
            if track_path not in index_map:
                index_map[track_path] = idx
        return index_map

    def _set_normal_playlist(self, tracks: List[str]) -> None:
        """Update normal playlist, bump monotonic version, and rebuild O(1) index map."""
        self.normal_playlist = list(tracks)
        self._normal_index_map = self._rebuild_index_map(self.normal_playlist)
        self._playlist_version += 1

    def _set_shuffled_playlist(self, tracks: List[str]) -> None:
        """Update shuffled playlist, sync version, and rebuild O(1) index map."""
        self.shuffled_playlist = list(tracks)
        self._shuffled_index_map = self._rebuild_index_map(self.shuffled_playlist)
        self._shuffled_version = self._playlist_version

    def _get_active_playlist_and_map(self) -> Tuple[List[str], Dict[str, int]]:
        """Return the active playlist list and O(1) index map according to shuffle setting."""
        shuffle_mode = self.config.get('shuffle', False)
        if shuffle_mode:
            return self.shuffled_playlist, self._shuffled_index_map
        return self.normal_playlist, self._normal_index_map

    # -------------------------------------------------------------------------
    # Playlist Synchronization (Decomposed Helpers <= 50 Lines)
    # -------------------------------------------------------------------------

    def _resolve_playlist_id(self, playlist_id: Any = None) -> Tuple[Any, bool]:
        """Resolve current playlist ID and determine if it has changed from loaded playlist."""
        if playlist_id is not None:
            self.current_playlist_id = playlist_id
            self.config.set('last_playlist_id', playlist_id)
        elif not self.current_playlist_id:
            self.current_playlist_id = self.config.get('last_playlist_id', 'all')

        resolved_pid = self.current_playlist_id
        is_changed = str(self.loaded_playlist_id) != str(resolved_pid)
        return resolved_pid, is_changed

    def _reload_playlist_if_needed(self, playlist_id: Any, path: str, playlist_changed: Any = False) -> None:
        """Fetch track paths from library service if playlist changed or path is missing."""
        needs_reload = (
            bool(playlist_changed)
            or not self.normal_playlist
            or str(self.loaded_playlist_id) != str(playlist_id)
            or (bool(path) and path not in self._normal_index_map)
        )
        if not needs_reload:
            return

        is_favorites = str(playlist_id) in ('favorites', '-1')
        target_pid = None
        if isinstance(playlist_id, str) and playlist_id.startswith('album:'):
            target_pid = playlist_id
        elif playlist_id is not None and str(playlist_id).isdigit():
            target_pid = int(playlist_id)

        try:
            paths = self.library_service.get_all_track_paths(favorites_only=is_favorites, playlist_id=target_pid)
            if not paths and not is_favorites and target_pid is None:
                paths = self.library_service.get_all_track_paths()
        except (AttributeError, RuntimeError, OSError) as e:
            logger.warning(f"Failed to load track paths from library: {e}")
            paths = []

        if not paths:
            return

        self._set_normal_playlist(paths)
        self._set_shuffled_playlist([])
        self.loaded_playlist_id = str(playlist_id)

    def _reshuffle_playlist(self, current_path: Optional[str] = None) -> None:
        """Force a fresh, non-deterministic Fisher-Yates shuffle of the playlist."""
        paths = self.normal_playlist
        if not paths:
            self._set_shuffled_playlist([])
            return

        curr = current_path if (current_path and current_path in self._normal_index_map) else None
        remaining = [p for p in paths if p != curr]
        random.shuffle(remaining)
        shuffled = [curr] + remaining if curr else remaining
        self._set_shuffled_playlist(shuffled)
        self._update_active_playlist_index(curr or '')

    def _sync_shuffled_playlist(self, current_path: str) -> None:
        """Reshuffle playlist in O(N) only if version mismatch or length mismatch."""
        paths = self.normal_playlist
        if not paths:
            self._set_shuffled_playlist([])
            return

        is_dirty = (
            self._shuffled_version != self._playlist_version
            or len(self.shuffled_playlist) != len(paths)
        )
        if not is_dirty:
            return

        self._reshuffle_playlist(current_path)

    def set_shuffle(self, state=None) -> Dict[str, Any]:
        """Enable or disable shuffle mode. Every time shuffle is enabled, generates a fresh random sequence."""
        is_active = bool(state) if state is not None else not self.config.get('shuffle', False)
        self.config.set('shuffle', is_active)
        if is_active:
            self._reshuffle_playlist(self.current_path)
        else:
            self._update_active_playlist_index(self.current_path or '')
        return self.get_state()

    def _update_active_playlist_index(self, path: str) -> None:
        """Update current_playlist_index based on shuffle state via O(1) index map lookup."""
        _, active_map = self._get_active_playlist_and_map()
        self.current_playlist_index = active_map.get(path, 0)

    def _sync_playlists_and_index(self, path: str, playlist_id: Any = None) -> None:
        """Synchronize normal and shuffled playlists and maintain O(1) track index."""
        resolved_pid, playlist_changed = self._resolve_playlist_id(playlist_id)
        self._reload_playlist_if_needed(resolved_pid, path, playlist_changed=playlist_changed)

        if not self.normal_playlist:
            return

        self._sync_shuffled_playlist(path)
        self._update_active_playlist_index(path)

    # -------------------------------------------------------------------------
    # Lyrics Background Preload
    # -------------------------------------------------------------------------

    def _preload_next_tracks_lyrics(self, current_path: str) -> None:
        """Preload lyrics for current track and next 5 queue items in background."""
        if not self.lyrics_worker:
            return

        try:
            current_track = self.library_service.get_track_info(current_path)
            if current_track:
                self.lyrics_worker.enqueue_track(current_track, priority=True)

            active_list, active_map = self._get_active_playlist_and_map()
            if not active_list:
                active_list = self.library_service.get_all_track_paths()
                active_map = self._rebuild_index_map(active_list)
            if not active_list:
                return

            current_idx = active_map.get(current_path, 0)
            next_tracks = []
            for offset in range(1, 6):
                next_idx = (current_idx + offset) % len(active_list)
                next_path = active_list[next_idx]
                track_info = self.library_service.get_track_info(next_path)
                if track_info:
                    next_tracks.append(track_info)

            if next_tracks:
                self.lyrics_worker.enqueue_tracks(next_tracks, priority=True)
        except (AttributeError, KeyError, ValueError, RuntimeError, OSError) as e:
            logger.debug(f"Failed to enqueue next tracks lyrics: {e}")

    # -------------------------------------------------------------------------
    # Playback Loading & Execution (Decomposed Helpers <= 50 Lines)
    # -------------------------------------------------------------------------

    def _record_track_selection(self, path: str, playlist_id: Any = None) -> None:
        """Persist track selection, update RAM cache, and record play history."""
        if playlist_id is not None:
            self.current_playlist_id = playlist_id

        self.current_path = path
        self.config.set('last_track', path)
        self._cached_track_path = path

        if hasattr(self, 'user_queue') and path in self.user_queue:
            self.user_queue.remove(path)

        try:
            self._cached_track_info = self.library_service.get_track_info(path)
        except (AttributeError, KeyError, ValueError, OSError) as e:
            logger.debug(f"Non-fatal track_info cache error: {e}")

        try:
            if hasattr(self.library_service, 'db'):
                self.library_service.db.update_last_played(path)
        except (AttributeError, RuntimeError, OSError) as e:
            logger.debug(f"Non-fatal update_last_played error: {e}")

        try:
            self._sync_playlists_and_index(path, playlist_id)
        except (KeyError, ValueError, RuntimeError, OSError) as e:
            logger.warning(f"Error syncing playlist in play(): {e}")

    def _handle_load_failure(self, target_path: str, token: int, error: Exception) -> None:
        """Handle playback failure with auto-skip and max consecutive failure guard."""
        logger.error(f"Playback load failed for {target_path}: {error}")
        if token != self._load_token or self.current_path != target_path:
            return

        self._consecutive_load_failures = getattr(self, '_consecutive_load_failures', 0) + 1
        if self._consecutive_load_failures >= 10:
            logger.warning("Stopped auto-skipping: 10 consecutive load failures detected")
            self.stop()
            return

        logger.info(f"Auto-advancing to next track (failure {self._consecutive_load_failures}/10)")
        self.next_track(user_initiated=False)

    def _execute_load_track(self, target_path: str, token: int) -> None:
        """Execute audio load and playback if token and active track are still valid."""
        if token != self._load_token or self.current_path != target_path:
            return

        try:
            self.audio_engine.load(target_path)
            if token != self._load_token or self.current_path != target_path:
                self.audio_engine.stop()
                return

            self.audio_engine.play()
            self._consecutive_load_failures = 0
            threading.Thread(
                target=self._preload_next_tracks_lyrics,
                args=(target_path,),
                daemon=True
            ).start()
        except (RuntimeError, OSError, ValueError) as e:
            self._handle_load_failure(target_path, token, e)

    def _schedule_track_load(self, path: str, token: int, immediate: Any = False) -> None:
        """Dispatch immediate load or debounced timer for rapid clicking."""
        if hasattr(self, '_load_timer') and self._load_timer:
            self._load_timer.cancel()

        self.audio_engine.stop()

        if bool(immediate):
            self._execute_load_track(path, token)
            return

        self._load_timer = threading.Timer(0.3, self._execute_load_track, args=(path, token))
        self._load_timer.start()

    def play(self, path: str, playlist_id: Any = None, immediate: Any = False) -> Dict[str, Any]:
        """Start or queue playback of a track with debounced loading."""
        logger.info(f"Playing track: {path} (playlist_id={playlist_id}, immediate={immediate})")
        self._record_track_selection(path, playlist_id)

        self._load_token += 1
        self._schedule_track_load(path, self._load_token, immediate=immediate)
        return self.get_state()

    # -------------------------------------------------------------------------
    # Playback Controls
    # -------------------------------------------------------------------------

    def pause(self) -> Dict[str, Any]:
        """Pause current audio playback."""
        logger.info("Pausing playback")
        self.audio_engine.pause()
        return self.get_state()

    def resume(self) -> Dict[str, Any]:
        """Resume playback or start active track if idle."""
        logger.info("Resuming playback")
        if self.audio_engine.state.name in ('IDLE', 'STOPPED') and self.current_path:
            return self.play(self.current_path, self.current_playlist_id)
        self.audio_engine.resume()
        return self.get_state()

    def stop(self) -> Dict[str, Any]:
        """Stop audio playback and reset engine state."""
        logger.info("Stopping playback")
        self.audio_engine.stop()
        return self.get_state()

    def seek(self, seconds: float) -> Dict[str, Any]:
        """Seek to specified position in seconds."""
        logger.info(f"Seeking to {seconds}s")
        self.audio_engine.seek(seconds)
        return self.get_state()

    def set_volume(self, level: float) -> None:
        """Set volume level (0.0 to 1.0) and debounce config persistence."""
        clamped = max(0.0, min(1.0, float(level)))
        self.audio_engine.set_volume(clamped)

        if hasattr(self, '_vol_save_timer') and self._vol_save_timer:
            self._vol_save_timer.cancel()
        self._vol_save_timer = threading.Timer(0.3, lambda: self.config.set('volume', clamped))
        self._vol_save_timer.daemon = True
        self._vol_save_timer.start()

    # -------------------------------------------------------------------------
    # Queue Modification & State
    # -------------------------------------------------------------------------

    def _find_queue_insertion_index(self, target_list: List[str], current_index: int, track_path: str) -> int:
        """Calculate next insertion position following current track and active user queue."""
        insert_pos = current_index + 1
        queue = getattr(self, 'user_queue', [])
        for q_item in queue:
            if q_item == track_path or q_item not in target_list:
                continue
            q_idx = target_list.index(q_item)
            if q_idx >= insert_pos:
                insert_pos = q_idx + 1
        return insert_pos

    def _insert_after_current(self, target_list: List[str], target_map: Dict[str, int], track_path: str) -> List[str]:
        """Insert track directly after self.current_path (and any already queued user items) in target_list."""
        new_list = [p for p in target_list if p != track_path]
        if not self.current_path or self.current_path not in target_map:
            new_list.insert(0, track_path)
            return new_list

        for idx, item in enumerate(new_list):
            if item == self.current_path:
                insert_pos = self._find_queue_insertion_index(new_list, idx, track_path)
                new_list.insert(insert_pos, track_path)
                return new_list

        logger.debug(f"Current track {self.current_path} not found in new list; placing at index 0")
        new_list.insert(0, track_path)
        return new_list

    def insert_play_next(self, path: str) -> Dict[str, Any]:
        """Queue a track to be played immediately after the current track."""
        logger.info(f"Queuing track to play next: {path}")
        if not path:
            return {"status": "error", "message": "Invalid track path"}

        if not hasattr(self, 'user_queue'):
            self.user_queue = []

        if path in self.user_queue:
            self.user_queue.remove(path)
        self.user_queue.append(path)

        self._sync_playlists_and_index(self.current_path or '', self.current_playlist_id)

        new_normal = self._insert_after_current(self.normal_playlist, self._normal_index_map, path)
        self._set_normal_playlist(new_normal)

        new_shuffled = self._insert_after_current(self.shuffled_playlist, self._shuffled_index_map, path)
        self._set_shuffled_playlist(new_shuffled)

        return {"status": "success", "message": "Track queued as next"}

    def _resolve_track_metadata(self, path: str) -> Dict[str, Any]:
        """Resolve track metadata from library service or fallback to path-derived info."""
        try:
            info = self.library_service.get_track_info(path)
            if info:
                return info
        except (AttributeError, KeyError, ValueError, OSError) as e:
            logger.debug(f"Error fetching track metadata for {path}: {e}")

        clean_title = path.replace('\\', '/').split('/')[-1]
        if '.' in clean_title:
            clean_title = '.'.join(clean_title.split('.')[:-1])
        return {
            "path": path,
            "title": clean_title or "Unknown Track",
            "artist": "Unknown Artist",
            "album": "Unknown Album",
            "duration": 0,
            "cover_url": None,
        }

    def _collect_upcoming_tracks(
        self, active_list: List[str], cur_idx: int, excluded_paths: set, limit: int
    ) -> List[Dict[str, Any]]:
        """Slice upcoming tracks after cur_idx up to limit with batch metadata resolution."""
        needed_paths: List[str] = []
        for i in range(cur_idx + 1, len(active_list)):
            p = active_list[i]
            if p in excluded_paths or p == self.current_path:
                continue
            needed_paths.append(p)
            if len(needed_paths) >= limit:
                break

        if not needed_paths:
            return []

        batch_map = {}
        if hasattr(self.library_service, 'get_tracks_by_paths'):
            batch_map = self.library_service.get_tracks_by_paths(needed_paths)

        upcoming: List[Dict[str, Any]] = []
        for p in needed_paths:
            track_info = batch_map.get(p) or self._resolve_track_metadata(p)
            upcoming.append(track_info)
        return upcoming

    def get_queue(self, limit: int = 25) -> Dict[str, Any]:
        """Return the current track, explicit user queue, and upcoming playlist tracks."""
        current_track = self._resolve_track_metadata(self.current_path) if self.current_path else None

        user_queue_tracks: List[Dict[str, Any]] = []
        user_queue_set = set()
        user_paths = [p for p in getattr(self, 'user_queue', []) if p != self.current_path]
        if user_paths:
            user_batch = {}
            if hasattr(self.library_service, 'get_tracks_by_paths'):
                user_batch = self.library_service.get_tracks_by_paths(user_paths)
            for p in user_paths:
                track_info = user_batch.get(p) or self._resolve_track_metadata(p)
                user_queue_tracks.append(track_info)
                user_queue_set.add(p)

        active_list, active_map = self._get_active_playlist_and_map()
        cur_idx = active_map.get(self.current_path) if (active_list and self.current_path) else None

        upcoming_tracks = []
        if cur_idx is not None and active_list:
            upcoming_tracks = self._collect_upcoming_tracks(active_list, cur_idx, user_queue_set, limit)

        return {
            "current": current_track,
            "user_queue": user_queue_tracks,
            "upcoming": upcoming_tracks,
        }

    def remove_from_queue(self, path: str) -> Dict[str, Any]:
        """Remove a track from user_queue and active playlist if it was inserted."""
        logger.info(f"Removing track from queue: {path}")
        if hasattr(self, 'user_queue') and path in self.user_queue:
            self.user_queue.remove(path)

        new_normal = [p for p in self.normal_playlist if p != path]
        self._set_normal_playlist(new_normal)

        new_shuffled = [p for p in self.shuffled_playlist if p != path]
        self._set_shuffled_playlist(new_shuffled)

        self._update_active_playlist_index(self.current_path or '')
        return {"status": "success", "message": "Removed from queue"}

    def clear_queue(self) -> Dict[str, Any]:
        """Clear all tracks from user_queue and clean up queued entries."""
        logger.info("Clearing all tracks from user queue")
        queued_paths = set(getattr(self, 'user_queue', []))
        self.user_queue = []

        if queued_paths:
            new_normal = [p for p in self.normal_playlist if p not in queued_paths or p == self.current_path]
            self._set_normal_playlist(new_normal)

            new_shuffled = [p for p in self.shuffled_playlist if p not in queued_paths or p == self.current_path]
            self._set_shuffled_playlist(new_shuffled)

            self._update_active_playlist_index(self.current_path or '')

        return {"status": "success", "message": "Queue cleared"}

    def set_active_playlist(self, playlist_id: Any) -> Dict[str, Any]:
        """Switch active playlist scope and re-synchronize indices."""
        logger.info(f"Setting active playlist scope to: {playlist_id}")
        self.current_playlist_id = playlist_id
        self.config.set('last_playlist_id', playlist_id)
        self._sync_playlists_and_index(self.current_path or '', playlist_id)
        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        """Return current playback engine state and cached active track metadata."""
        state = self.audio_engine.get_state()

        if hasattr(self, '_load_timer') and self._load_timer and self._load_timer.is_alive():
            state['is_playing'] = True

        if not self.current_path:
            state['track'] = None
            return state

        if self._cached_track_path != self.current_path or self._cached_track_info is None:
            try:
                self._cached_track_info = self.library_service.get_track_info(self.current_path)
            except (AttributeError, KeyError, ValueError, OSError) as e:
                logger.debug(f"Error fetching track info in get_state: {e}")
                self._cached_track_info = None
            self._cached_track_path = self.current_path

        state['track'] = self._cached_track_info
        return state

    # -------------------------------------------------------------------------
    # Track Navigation
    # -------------------------------------------------------------------------

    def next_track(self, user_initiated: Any = True) -> Optional[Dict[str, Any]]:
        """Skip to the next track in the active playlist sequence."""
        is_user = bool(user_initiated)
        immediate = not is_user
        logger.info(f"Skipping to next track (active playlist_id={self.current_playlist_id})")

        if not self.current_path:
            self._sync_playlists_and_index('', self.current_playlist_id)
            active_list, _ = self._get_active_playlist_and_map()
            if not active_list:
                return None
            return self.play(active_list[0], self.current_playlist_id, immediate=immediate)

        repeat_mode = self.config.get('repeat', 'off')
        if not is_user and repeat_mode == 'one':
            return self.play(self.current_path, self.current_playlist_id, immediate=True)

        self._sync_playlists_and_index(self.current_path, self.current_playlist_id)
        active_list, active_map = self._get_active_playlist_and_map()
        if not active_list:
            return None

        cur_idx = active_map.get(self.current_path)
        next_index = (cur_idx + 1) if cur_idx is not None else 0

        if next_index >= len(active_list):
            if not is_user and repeat_mode != 'all':
                self.stop()
                return self.get_state()
            next_index = 0

        self.current_playlist_index = next_index
        return self.play(active_list[next_index], self.current_playlist_id, immediate=immediate)

    def prev_track(self) -> Optional[Dict[str, Any]]:
        """Skip to the previous track or seek to beginning if >3.0s elapsed."""
        logger.info(f"Skipping to previous track (active playlist_id={self.current_playlist_id})")
        current_state = self.audio_engine.get_state()
        if current_state.get('position_seconds', 0.0) > 3.0:
            return self.seek(0.0)

        if not self.current_path:
            self._sync_playlists_and_index('', self.current_playlist_id)
            active_list, _ = self._get_active_playlist_and_map()
            if not active_list:
                return None
            return self.play(active_list[-1], self.current_playlist_id)

        self._sync_playlists_and_index(self.current_path, self.current_playlist_id)
        active_list, active_map = self._get_active_playlist_and_map()
        if not active_list:
            return None

        cur_idx = active_map.get(self.current_path)
        prev_index = (cur_idx - 1) if cur_idx is not None else (len(active_list) - 1)
        if prev_index < 0:
            prev_index = len(active_list) - 1

        self.current_playlist_index = prev_index
        return self.play(active_list[prev_index], self.current_playlist_id)
