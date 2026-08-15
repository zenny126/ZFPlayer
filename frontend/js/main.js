document.addEventListener('DOMContentLoaded', async () => {
  // Wait for API bridge
  await window.api.readyPromise;
  console.log("API Ready. Initializing app with fast bootstrap payload...");

  // 1. Fetch initial bootstrap payload in a single round-trip
  let bootstrap = null;
  try {
    if (window.api && window.api.getBootstrapData) {
      bootstrap = await window.api.getBootstrapData();
    }
  } catch (e) {
    console.warn("Bootstrap API fallback:", e);
  }

  // 2. Initialize Controllers
  window.shortcutsManager = new ShortcutsManager();
  if (bootstrap && bootstrap.config && bootstrap.config.shortcuts) {
    window.shortcutsManager.shortcuts = { ...window.shortcutsManager.DEFAULT_SHORTCUTS, ...bootstrap.config.shortcuts };
  } else {
    await window.shortcutsManager.init();
  }

  window.uiController = new UIController();
  window.playerController = new PlayerController();
  window.lyricsRenderer = new LyricsRenderer();
  window.libraryManager = new LibraryManager();
  window.albumsManager = new AlbumsManager();
  
  await window.libraryManager.init();
  if (window.homeManager) window.homeManager.loadHome();

  // 3. Apply Config & Volume
  const config = bootstrap ? bootstrap.config : await window.api.getConfig();
  const playerState = bootstrap ? bootstrap.player_state : await window.api.getPlayerState();
  
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

  // 4. Restore Player State
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
  
  // 5. Global Keyboard Shortcuts
  document.addEventListener('keydown', async (e) => {
    if (window.shortcutsManager) {
      await window.shortcutsManager.handleGlobalKeyDown(e);
    }
  });

  console.log("App initialized successfully.");
});
