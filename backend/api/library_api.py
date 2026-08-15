import logging

logger = logging.getLogger(__name__)

class LibraryAPI:
    def __init__(self, library_service, config):
        self.library_service = library_service
        self.config = config

    def get_bootstrap_data(self):
        player_service = getattr(self, 'player_service', None)
        return self.library_service.get_bootstrap_data(player_service)

    def get_tracks(self, offset=0, limit=50, search='', sort_by='title', sort_dir='ASC', playlist_id=None):
        is_favorites = str(playlist_id) in ['favorites', '-1']
        is_album = isinstance(playlist_id, str) and playlist_id.startswith('album:')
        real_playlist_id = playlist_id if is_album else (int(playlist_id) if playlist_id is not None and str(playlist_id).isdigit() else None)
        return self.library_service.get_tracks(offset, limit, search, sort_by, sort_dir, is_favorites, real_playlist_id)

    def get_track_count(self, search='', playlist_id=None):
        is_favorites = str(playlist_id) in ['favorites', '-1']
        is_album = isinstance(playlist_id, str) and playlist_id.startswith('album:')
        real_playlist_id = playlist_id if is_album else (int(playlist_id) if playlist_id is not None and str(playlist_id).isdigit() else None)
        return self.library_service.get_track_count(search, is_favorites, real_playlist_id)

    def get_recently_played(self, limit=20):
        return self.library_service.get_recently_played(limit)

    def get_albums(self):
        return self.library_service.get_albums()



    def get_track_info(self, path):
        info = self.library_service.get_track_info(path)
        return info if info else {}

    def toggle_like(self, path):
        track_info = self.library_service.get_track_info(path)
        if track_info:
            new_status = 1 if not track_info.get('is_liked') else 0
            self.library_service.update_track(path, {'is_liked': new_status})
            return {'status': 'success', 'is_liked': new_status}
        return {'status': 'error', 'message': 'Track not found'}


    def scan_library(self):
        self.library_service.scan_library()
        return {'status': 'success'}

    def get_scan_progress(self):
        return self.library_service.get_scan_progress()

    def add_album(self, folder_path, album_name='', cover_image_path=''):
        return self.library_service.add_album(folder_path, album_name, cover_image_path, self.config)

    # --- Playlist API ---
    def create_playlist(self, name, folder_path=None):
        pid = self.library_service.create_playlist(name, folder_path)
        return {'status': 'success', 'playlist_id': pid}

    def delete_playlist(self, playlist_id):
        self.library_service.delete_playlist(int(playlist_id))
        return {'status': 'success'}

    def rename_playlist(self, playlist_id, new_name):
        self.library_service.rename_playlist(int(playlist_id), new_name)
        return {'status': 'success'}

    def get_playlists(self):
        return self.library_service.get_playlists()

    def add_to_playlist(self, playlist_id, track_path):
        self.library_service.add_track_to_playlist(int(playlist_id), track_path)
        return {'status': 'success'}

    def remove_from_playlist(self, playlist_id, track_path):
        self.library_service.remove_track_from_playlist(int(playlist_id), track_path)
        return {'status': 'success'}

    def import_folder_to_playlist(self, playlist_id, folder_path):
        return self.library_service.import_folder_to_playlist(int(playlist_id), folder_path)

    def import_files_to_playlist(self, playlist_id, file_paths):
        return self.library_service.import_files_to_playlist(int(playlist_id), file_paths)

    def update_playlist_cover(self, playlist_id, cover_image_path):
        return self.library_service.update_playlist_cover(playlist_id, cover_image_path)

    def get_system_playlist_covers(self):
        return self.library_service.get_system_playlist_covers()

    def clear_database(self, clear_cache=True):
        return self.library_service.clear_database(clear_cache=clear_cache)
