document.addEventListener('DOMContentLoaded', async () => {
  // Wait for API
  await window.api.readyPromise;
  console.log("API Ready. Initializing app...");

  // Init components
  window.uiController = new UIController();
  window.playerController = new PlayerController();
  window.lyricsRenderer = new LyricsRenderer();
  window.libraryManager = new LibraryManager();
  window.albumsManager = new AlbumsManager();
  
  await window.libraryManager.init();
  // window.uiController.loadPlaylists() is now handled by playlists.js
  if (window.homeManager) window.homeManager.loadHome();

  // Load config & sync player state on startup
  const config = await window.api.getConfig();
  const playerState = await window.api.getPlayerState();
  
  if (config) {
    if (config.volume !== undefined) {
      const volVal = typeof config.volume === 'number' ? config.volume : parseFloat(config.volume);
      const volPercent = Math.round(volVal <= 1 ? volVal * 100 : volVal);
      window.store.setState({ volume: volPercent });
      
      const volBar = document.getElementById('volume-bar');
      const volBarLyrics = document.getElementById('lyrics-volume-bar');
      if (volBar) {
        volBar.value = volPercent;
        volBar.style.setProperty('--progress', `${volPercent}%`);
      }
      if (volBarLyrics) {
        volBarLyrics.value = volPercent;
        volBarLyrics.style.setProperty('--progress', `${volPercent}%`);
      }
    }
    
    if (config.shuffle !== undefined) {
      window.store.setState({ shuffle: config.shuffle });
    }
    
    if (config.repeat !== undefined) {
      window.store.setState({ repeat: config.repeat });
    }
  }

  // Restore player state from backend if active, else fall back to last track / first track
  if (playerState && playerState.track) {
    window.store.setState({ 
      currentTrack: playerState.track,
      isPlaying: playerState.is_playing 
    });
    const pos = playerState.position_seconds !== undefined ? playerState.position_seconds : playerState.position;
    window.playerController.ticker.sync(pos, playerState.duration, playerState.is_playing);
  } else if (config && config.last_track) {
    try {
      const trackInfo = await window.api.getTrackInfo(config.last_track);
      if (trackInfo && trackInfo.path) {
        window.store.setState({ currentTrack: trackInfo, isPlaying: false });
        window.playerController.ticker.sync(0, trackInfo.duration, false);
      } else {
        const firstPage = await window.api.getTracks(0, 1, '', 'title', 'ASC');
        if (firstPage && firstPage.length > 0) {
          window.store.setState({ currentTrack: firstPage[0], isPlaying: false });
          window.playerController.ticker.sync(0, firstPage[0].duration, false);
        }
      }
    } catch(e) {
      console.error("Error loading last track:", e);
    }
  } else {
    try {
      const firstPage = await window.api.getTracks(0, 1, '', 'title', 'ASC');
      if (firstPage && firstPage.length > 0) {
        window.store.setState({ currentTrack: firstPage[0], isPlaying: false });
        window.playerController.ticker.sync(0, firstPage[0].duration, false);
      }
    } catch(e) {
      console.error("Error loading fallback track:", e);
    }
  }
  
  // Global Keyboard Shortcuts
  document.addEventListener('keydown', async (e) => {
    // Ignore keystrokes when typing inside inputs or textareas
    const targetTag = e.target.tagName ? e.target.tagName.toLowerCase() : '';
    if (targetTag === 'input' || targetTag === 'textarea' || e.target.isContentEditable) {
      if (e.key === 'Escape') {
        e.target.blur();
      }
      return;
    }

    if (e.key === ' ' || e.code === 'Space') {
      e.preventDefault();
      if (window.playerController) {
        await window.playerController.togglePlay();
      }
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      if (window.playerController && window.playerController.ticker) {
        const cur = window.playerController.ticker.position || 0;
        await window.playerController.seek(Math.max(0, cur - 5));
      }
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      if (window.playerController && window.playerController.ticker) {
        const cur = window.playerController.ticker.position || 0;
        const dur = window.playerController.ticker.duration || 0;
        await window.playerController.seek(Math.min(dur, cur + 5));
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (window.playerController) {
        await window.playerController.adjustVolume(5);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (window.playerController) {
        await window.playerController.adjustVolume(-5);
      }
    } else if (e.key === 'm' || e.key === 'M') {
      e.preventDefault();
      if (window.playerController) {
        await window.playerController.toggleMute();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      const lyricsOverlay = document.getElementById('lyrics-overlay');
      if (lyricsOverlay && !lyricsOverlay.classList.contains('hidden')) {
        if (window.lyricsRenderer) window.lyricsRenderer.hide();
      } else {
        // Close any active context menus or modals
        document.querySelectorAll('.context-menu').forEach(m => m.classList.add('hidden'));
        document.querySelectorAll('.modal:not(.hidden)').forEach(m => m.classList.add('hidden'));
      }
    } else if (e.key === 'F11') {
      e.preventDefault();
      try {
        if (window.api && window.api.toggleFullscreen) {
          await window.api.toggleFullscreen();
        }
      } catch (err) {
        console.error("PyWebView toggleFullscreen error:", err);
      }
    }
  });

  console.log("App initialized.");
});
