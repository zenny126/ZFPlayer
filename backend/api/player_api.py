import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PlayerAPI:
    def __init__(self, player_service):
        self.player_service = player_service

    def play(self, path: str, playlist_id: Optional[Any] = None) -> Dict[str, Any]:
        return self.player_service.play(path, playlist_id)

    def pause(self) -> Dict[str, Any]:
        return self.player_service.pause()

    def resume(self) -> Dict[str, Any]:
        return self.player_service.resume()

    def stop(self) -> Dict[str, Any]:
        return self.player_service.stop()

    def seek(self, seconds: float) -> Dict[str, Any]:
        return self.player_service.seek(seconds)

    def set_volume(self, level: float) -> Dict[str, Any]:
        self.player_service.set_volume(level)
        return self.player_service.get_state()

    def get_player_state(self) -> Dict[str, Any]:
        return self.player_service.get_state()

    def next_track(self) -> Optional[Dict[str, Any]]:
        return self.player_service.next_track()

    def prev_track(self) -> Optional[Dict[str, Any]]:
        return self.player_service.prev_track()

    def set_active_playlist(self, playlist_id: Any) -> Dict[str, Any]:
        return self.player_service.set_active_playlist(playlist_id)

    def setActivePlaylist(self, playlist_id: Any) -> Dict[str, Any]:
        return self.player_service.set_active_playlist(playlist_id)
