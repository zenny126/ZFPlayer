class ApiWrapper {
  constructor() {
    this.isReady = false;
    this.readyPromise = new Promise(resolve => {
      window.addEventListener('pywebviewready', () => {
        this.isReady = true;
        resolve();
      });
      // Fallback
      setTimeout(() => { if (!this.isReady) resolve(); }, 2000);
    });
  }

  async call(method, ...args) {
    await this.readyPromise;
    if (!window.pywebview || !window.pywebview.api) {
      console.warn(`pywebview.api not found. Mocking ${method}`);
      return this.mockResponse(method, args);
    }
    
    try {
      return await window.pywebview.api[method](...args);
    } catch (e) {
      console.error(`API Error (${method}):`, e);
      try {
        return await window.pywebview.api[method](...args);
      } catch (retryError) {
        throw retryError;
      }
    }
  }

  // API Methods
  getTrackInfo(path) { return this.call('get_track_info', path); }
  getTracks(offset, limit, search, sortBy, sortDir, playlistId = null) { return this.call('get_tracks', offset, limit, search, sortBy, sortDir, playlistId); }
  getTrackCount(search, playlistId = null) { return this.call('get_track_count', search, playlistId); }

  play(path, playlistId = null) { return this.call('play', path, playlistId); }
  playNext(path) { return this.call('play_next', path); }
  pause() { return this.call('pause'); }
  resume() { return this.call('resume'); }
  stop() { return this.call('stop'); }
  seek(seconds) { return this.call('seek', seconds); }
  setVolume(level) { return this.call('set_volume', level); }
  getPlayerState() { return this.call('get_player_state'); }
  nextTrack() { return this.call('next_track'); }
  prevTrack() { return this.call('prev_track'); }
  scanLibrary() { return this.call('scan_library'); }
  getScanProgress() { return this.call('get_scan_progress'); }
  getAlbums() { return this.call('get_albums'); }
  getRecentlyPlayed(limit = 20) { return this.call('get_recently_played', limit); }

  getLyrics(artist, title, album, duration, path) { return this.call('get_lyrics', artist, title, album, duration, path); }
  getConfig() { return this.call('get_config'); }
  setConfig(key, value) { return this.call('set_config', key, value); }
  selectMusicDir() { return this.call('select_music_dir'); }
  selectMusicFile() { return this.call('select_music_file'); }
  selectCoverImage() { return this.call('select_cover_image'); }
  addAlbum(folderPath, albumName, coverImagePath) { return this.call('add_album', folderPath, albumName, coverImagePath); }
  toggleLike(path) { return this.call('toggle_like', path); }
  toggleFullscreen() { return this.call('toggle_fullscreen'); }

  // Playlist Methods
  createPlaylist(name, folderPath = null) { return this.call('create_playlist', name, folderPath); }
  deletePlaylist(playlistId) { return this.call('delete_playlist', playlistId); }
  renamePlaylist(playlistId, newName) { return this.call('rename_playlist', playlistId, newName); }
  getPlaylists() { return this.call('get_playlists'); }
  addToPlaylist(playlistId, trackPath) { return this.call('add_to_playlist', playlistId, trackPath); }
  removeFromPlaylist(playlistId, trackPath) { return this.call('remove_from_playlist', playlistId, trackPath); }
  importFolderToPlaylist(playlistId, folderPath) { return this.call('import_folder_to_playlist', playlistId, folderPath); }
  importFilesToPlaylist(playlistId, filePaths) { return this.call('import_files_to_playlist', playlistId, filePaths); }
  updatePlaylistCover(playlistId, coverImagePath) { return this.call('update_playlist_cover', playlistId, coverImagePath); }
  getSystemPlaylistCovers() { return this.call('get_system_playlist_covers'); }
  selectMusicFiles() { return this.call('select_music_files'); }
  setActivePlaylist(playlistId) { return this.call('set_active_playlist', playlistId); }
  set_active_playlist(playlistId) { return this.call('set_active_playlist', playlistId); }

  mockResponse(method, args) {
    if (method === 'get_track_count') return Promise.resolve(0);
    if (method === 'get_tracks') return Promise.resolve([]);
    if (method === 'get_player_state') return Promise.resolve({ position: 0, duration: 0, is_playing: false, volume: 80, track_path: null });
    return Promise.resolve(null);
  }
}

window.api = new ApiWrapper();
