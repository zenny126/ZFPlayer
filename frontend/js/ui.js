class UIController {
  constructor() {
    this.bindEvents();
  }

  bindEvents() {
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', (e) => {
        const target = e.currentTarget;
        if (target.dataset.view) {
           window.store.setState({ view: target.dataset.view });
        }
      });
    });

    // Sidebar toggle
    const toggleSidebarBtn = document.getElementById('btn-toggle-sidebar');
    if (toggleSidebarBtn) {
      toggleSidebarBtn.addEventListener('click', () => {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
          sidebar.classList.toggle('collapsed');
        }
      });
    }

    // Settings Modal
    const audioModeDetails = {
      shared: `
        <div><span class="info-tag info-pro">PROS</span> High stability, allows multi-application background audio simultaneously.</div>
        <div style="margin-top: 4px;"><span class="info-tag info-con">CONS</span> Audio is resampled and software-mixed by Windows System Mixer.</div>
        <div style="margin-top: 4px;"><span class="info-tag info-req">BEST FOR</span> Daily casual listening, web browsing & background music.</div>
      `,
      exclusive: `
        <div><span class="info-tag info-pro">PROS</span> Bit-perfect 1:1 direct hardware playback, bypasses Windows OS mixer completely.</div>
        <div style="margin-top: 4px;"><span class="info-tag info-con">CONS</span> Mutes audio from all other Windows applications during playback.</div>
        <div style="margin-top: 4px;"><span class="info-tag info-req">BEST FOR</span> USB DACs, soundcards & Hi-Res Audiophile listening.</div>
      `
    };
    audioModeDetails.exclusive_push = audioModeDetails.exclusive;

    const updateAudioModeInfo = (mode) => {
      const infoCard = document.getElementById('audio-mode-info');
      const targetMode = (mode === 'exclusive_push' || mode === 'exclusive_event') ? 'exclusive' : mode;
      if (infoCard && audioModeDetails[targetMode]) {
        infoCard.innerHTML = audioModeDetails[targetMode];
      }
    };

    const updateDbStats = async () => {
      if (window.api) {
        try {
          const count = await window.api.getTrackCount('');
          const playlists = await window.api.getPlaylists() || [];
          const countEl = document.getElementById('settings-db-track-count');
          const plCountEl = document.getElementById('settings-db-playlist-count');
          if (countEl) countEl.textContent = `${count} tracks`;
          if (plCountEl) plCountEl.textContent = `${playlists.length} playlists`;
        } catch (e) {
          console.warn('Failed to load DB stats:', e);
        }
      }
    };

    const btnSettings = document.getElementById('btn-settings');
    if (btnSettings) {
      btnSettings.addEventListener('click', async () => {
        const selectMode = document.getElementById('select-audio-mode');
        if (selectMode && window.api) {
          try {
            const config = await window.api.getConfig();
            let currentMode = (config && config.audio_mode) ? config.audio_mode : 'shared';
            if (currentMode === 'exclusive_push' || currentMode === 'exclusive_event') currentMode = 'exclusive';
            selectMode.value = currentMode;
            updateAudioModeInfo(currentMode);
          } catch (e) {
            console.error('Failed to load audio_mode config:', e);
          }
        }
        if (window.shortcutsManager) {
          window.shortcutsManager.renderShortcutsUI();
        }
        updateDbStats();
        document.getElementById('settings-modal').classList.remove('hidden');
      });
    }

    // Settings Modal Tabs Switching
    const settingsTabBtns = document.querySelectorAll('.settings-tab-btn');
    settingsTabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        settingsTabBtns.forEach(b => b.classList.toggle('active', b === btn));

        const audioPane = document.getElementById('settings-tab-audio');
        const shortcutsPane = document.getElementById('settings-tab-shortcuts');
        const libraryPane = document.getElementById('settings-tab-library');
        if (audioPane) audioPane.style.display = tab === 'audio' ? 'block' : 'none';
        if (shortcutsPane) {
          shortcutsPane.style.display = tab === 'shortcuts' ? 'flex' : 'none';
          if (tab === 'shortcuts' && window.shortcutsManager) {
            window.shortcutsManager.renderShortcutsUI();
          }
        }
        if (libraryPane) {
          libraryPane.style.display = tab === 'library' ? 'block' : 'none';
          if (tab === 'library') {
            updateDbStats();
          }
        }
      });
    });

    // Reset all shortcuts button
    const btnResetShortcuts = document.getElementById('btn-reset-shortcuts');
    if (btnResetShortcuts) {
      btnResetShortcuts.addEventListener('click', async () => {
        if (window.shortcutsManager) {
          await window.shortcutsManager.resetAll();
        }
      });
    }

    // Library Rescan button in Settings
    const btnSettingsRescan = document.getElementById('btn-settings-rescan');
    if (btnSettingsRescan) {
      btnSettingsRescan.addEventListener('click', async () => {
        if (window.api && window.api.scanLibrary) {
          document.getElementById('settings-modal')?.classList.add('hidden');
          const scanModal = document.getElementById('scan-modal');
          if (scanModal) scanModal.classList.remove('hidden');
          await window.api.scanLibrary();
          if (window.libraryManager) this.startScanProgressPolling();
        }
      });
    }

    // Clear Database Danger Action & Confirmation Modal
    const btnClearDb = document.getElementById('btn-settings-clear-db');
    const modalConfirmClear = document.getElementById('confirm-clear-db-modal');
    const btnCancelClear = document.getElementById('btn-cancel-clear-db');
    const btnConfirmClear = document.getElementById('btn-confirm-clear-db');
    const checkboxClearCache = document.getElementById('checkbox-clear-cache');

    if (btnClearDb && modalConfirmClear) {
      btnClearDb.addEventListener('click', () => {
        modalConfirmClear.classList.remove('hidden');
      });
    }

    if (btnCancelClear && modalConfirmClear) {
      btnCancelClear.addEventListener('click', () => {
        modalConfirmClear.classList.add('hidden');
      });
    }

    if (btnConfirmClear && modalConfirmClear) {
      btnConfirmClear.addEventListener('click', async () => {
        const originalText = btnConfirmClear.textContent;
        btnConfirmClear.textContent = 'Cleaning Database...';
        btnConfirmClear.disabled = true;

        const clearCache = checkboxClearCache ? checkboxClearCache.checked : true;

        try {
          // Stop playback first
          if (window.playerController && typeof window.playerController.stop === 'function') {
            await window.playerController.stop();
          } else if (window.api && typeof window.api.stop === 'function') {
            await window.api.stop();
          }

          // Call API to clear database
          const res = await window.api.clearDatabase(clearCache);

          // Reset store state
          window.store.setState({
            currentTrack: null,
            isPlaying: false,
            playlist: [],
            playlistId: 'all'
          });

          // Reload all managers
          if (window.libraryManager) await window.libraryManager.reload();
          if (window.playlistManager) await window.playlistManager.loadPlaylists();
          if (window.albumsManager) await window.albumsManager.loadAlbums();
          if (window.homeManager) await window.homeManager.loadHome();

          modalConfirmClear.classList.add('hidden');
          document.getElementById('settings-modal')?.classList.add('hidden');

          this.showToast(res?.message || 'Database has been cleaned successfully.');
        } catch (err) {
          console.error('Error clearing database:', err);
          this.showToast('Failed to clean database: ' + err.message);
        } finally {
          btnConfirmClear.textContent = originalText;
          btnConfirmClear.disabled = false;
        }
      });
    }

    const selectMode = document.getElementById('select-audio-mode');
    if (selectMode) {
      selectMode.addEventListener('change', async (e) => {
        const selectedMode = e.target.value;
        updateAudioModeInfo(selectedMode);
        if (window.api) {
          try {
            if (window.api.setAudioMode) {
              await window.api.setAudioMode(selectedMode);
            } else if (window.api.setConfig) {
              await window.api.setConfig('audio_mode', selectedMode);
            }
            const modeLabels = {
              shared: 'WASAPI Shared Mode',
              exclusive: 'WASAPI Exclusive Mode (Push Driven)'
            };
            this.showToast(`Audio mode set to: ${modeLabels[selectedMode] || selectedMode}`);
          } catch (err) {
            console.error('Failed to update audio mode:', err);
            this.showToast('Failed to switch WASAPI audio mode');
          }
        }
      });
    }

    const btnCloseSettings = document.getElementById('btn-close-settings');
    if (btnCloseSettings) {
      btnCloseSettings.addEventListener('click', () => {
        if (window.shortcutsManager) {
          window.shortcutsManager.stopRecording();
        }
        document.getElementById('settings-modal').classList.add('hidden');
      });
    }

    const settingsModal = document.getElementById('settings-modal');
    if (settingsModal) {
      settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
          if (window.shortcutsManager) {
            window.shortcutsManager.stopRecording();
          }
          settingsModal.classList.add('hidden');
        }
      });
    }

    window.store.subscribe(['view', 'playlistId'], (state) => {
      // Sync nav items visually
      document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
      document.querySelectorAll(`.nav-item[data-view="${state.view}"]`).forEach(nav => nav.classList.add('active'));
      
      const libraryView = document.getElementById('library-view');
      const albumsView = document.getElementById('albums-view');
      const homeView = document.getElementById('home-view');
      
      const activateView = (v) => {
        if (!v) return;
        v.classList.remove('hidden');
        v.classList.add('active');
        v.classList.remove('active-view-fade');
        void v.offsetWidth;
        v.classList.add('active-view-fade');
      };

      // Helper to hide all views
      [libraryView, albumsView, homeView].forEach(v => {
        if (v) { v.classList.add('hidden'); v.classList.remove('active', 'active-view-fade'); }
      });

      if (state.view === 'home') {
        activateView(homeView);
        const searchInput = document.getElementById('search-input');
        if (searchInput) searchInput.value = '';
        if (window.libraryManager) window.libraryManager.searchQuery = '';
        if (window.homeManager) window.homeManager.loadHome();
      } else if (state.view === 'songs') {
        activateView(libraryView);
        if (window.libraryManager) {
          window.libraryManager.currentPlaylistId = 'all';
          window.libraryManager.reload();
          if (window.api) {
            if (window.api.setActivePlaylist) window.api.setActivePlaylist('all');
            else if (window.api.set_active_playlist) window.api.set_active_playlist('all');
          }
        }
      } else if (state.view === 'albums') {
        activateView(albumsView);
        
        if (window.albumsManager && window.albumsManager.albums.length === 0) {
          window.albumsManager.loadAlbums();
        }
      } else if (state.view === 'playlist') {
        activateView(libraryView);
        if (window.libraryManager) {
          window.libraryManager.currentPlaylistId = state.playlistId;
          window.libraryManager.reload();
          if (window.api) {
            if (window.api.setActivePlaylist) window.api.setActivePlaylist(state.playlistId);
            else if (window.api.set_active_playlist) window.api.set_active_playlist(state.playlistId);
          }
        }
      }
    });

    // Context Menu item handlers
    document.getElementById('ctx-play-next')?.addEventListener('click', async () => {
      const menu = document.getElementById('context-menu');
      const path = menu?.dataset.trackPath;
      if (path && window.api && window.api.playNext) {
        await window.api.playNext(path);
      }
      menu?.classList.add('hidden');
    });

    document.getElementById('ctx-go-album')?.addEventListener('click', () => {
      const menu = document.getElementById('context-menu');
      const album = menu?.dataset.trackAlbum;
      menu?.classList.add('hidden');
      if (album) {
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
          searchInput.value = album;
          searchInput.dispatchEvent(new Event('input'));
        }
        window.store.setState({ view: 'albums' });
      }
    });

    document.getElementById('ctx-go-artist')?.addEventListener('click', () => {
      const menu = document.getElementById('context-menu');
      const artist = menu?.dataset.trackArtist;
      menu?.classList.add('hidden');
      if (artist) {
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
          searchInput.value = artist;
          searchInput.dispatchEvent(new Event('input'));
        }
        window.store.setState({ view: 'songs' });
      }
    });

    // Global click to close context menu
    document.addEventListener('click', (e) => {
      const menu = document.getElementById('context-menu');
      if (menu && !menu.classList.contains('hidden')) {
        menu.classList.add('hidden');
      }
      
      const pMenu = document.getElementById('playlist-context-menu');
      if (pMenu && !pMenu.classList.contains('hidden')) {
        pMenu.classList.add('hidden');
      }
    });
  }

  async loadPlaylists() {
    try {
      const container = document.getElementById('playlist-container');
      if (!container) return;
      
      container.innerHTML = '';
      const state = window.store.getState();

      // System Default Playlists
      const systemPlaylists = [
        {
          id: 'all',
          name: 'All Songs',
          subtitle: 'All your local tracks',
          icon: `<svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 24px; height: 24px; color: #ffffff;"><path d="M9 18V5l12-2v13 M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"></path></svg>`
        },
        {
          id: 'favorites',
          name: 'Favorite Songs',
          subtitle: 'Your favorite tracks',
          icon: `<svg viewBox="0 0 24 24" fill="#ffffff" stroke="none" style="width: 24px; height: 24px; color: #ffffff;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`
        }
      ];

      systemPlaylists.forEach(pl => {
        const li = document.createElement('li');
        li.dataset.id = pl.id;
        if (state.view === 'playlist' && state.playlistId === pl.id) {
          li.classList.add('active');
        }
        li.innerHTML = `
          <div class="icon-placeholder system-icon">${pl.icon}</div>
          <div class="library-list-text">
            <div class="library-list-title">${pl.name}</div>
            <div class="library-list-subtitle">${pl.subtitle}</div>
          </div>
        `;
        li.addEventListener('click', () => {
          document.querySelectorAll('#playlist-container li').forEach(item => item.classList.remove('active'));
          li.classList.add('active');
          window.store.setState({ view: 'playlist', playlistId: pl.id });
        });
        container.appendChild(li);
      });
    } catch (e) {
      console.error("Failed to load playlists", e);
    }
  }

  showContextMenu(e, track) {
    if (!track) return;
    e.preventDefault();
    e.stopPropagation();
    const menu = document.getElementById('context-menu');
    if (!menu) return;

    // Position menu at cursor
    let x = e.clientX;
    let y = e.clientY;

    // Basic bounds checking
    menu.style.display = 'flex'; // temp display to get dims
    const rect = menu.getBoundingClientRect();
    if (x + rect.width > window.innerWidth) x = window.innerWidth - rect.width - 8;
    if (y + rect.height > window.innerHeight) y = window.innerHeight - rect.height - 8;
    menu.style.display = ''; // reset

    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.classList.remove('hidden');

    // Store track info
    menu.dataset.trackPath = track.path || '';
    menu.dataset.trackAlbum = track.album || '';
    menu.dataset.trackArtist = track.artist || '';
    
    // Show/hide "Remove from Playlist"
    const btnRemove = document.getElementById('ctx-remove-from-playlist');
    if (btnRemove) {
        const state = window.store.getState();
        if (state.view === 'playlist' && state.playlistId && state.playlistId !== 'all' && state.playlistId !== 'favorites') {
            btnRemove.classList.remove('hidden');
        } else {
            btnRemove.classList.add('hidden');
        }
    }
  }

  showToast(message, duration = 3000) {
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.id = 'toast-container';
      toastContainer.style.cssText = 'position: fixed; bottom: 84px; right: 24px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; pointer-events: none;';
      document.body.appendChild(toastContainer);
    }
    const toast = document.createElement('div');
    toast.style.cssText = 'background: rgba(24, 24, 27, 0.95); color: #fff; border: 1px solid rgba(255, 255, 255, 0.15); backdrop-filter: blur(12px); border-radius: 8px; padding: 12px 20px; font-size: 0.9rem; font-weight: 500; box-shadow: 0 8px 24px rgba(0,0,0,0.4); opacity: 0; transform: translateY(10px); transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); pointer-events: auto;';
    toast.textContent = message;
    toastContainer.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
}

window.UIController = UIController;

// Color Extraction for Fluid Background with Caching and Cancellation
const colorCache = new Map();
let currentExtractImg = null;
let sharedCanvas = null;
let sharedCtx = null;

function extractDominantColors(imageUrl, callback) {
  const defaultPalette = ['#000000', '#8a2be2', '#00d2ff', '#ff007f'];
  
  if (!imageUrl || imageUrl === 'none') {
    callback(defaultPalette);
    return;
  }
  
  let finalUrl = imageUrl;
  if (imageUrl.startsWith('url(')) {
    finalUrl = imageUrl.slice(4, -1).replace(/['"]/g, '');
  }
  
  // 1. Fast path: Return cached result immediately if available
  if (colorCache.has(finalUrl)) {
    callback(colorCache.get(finalUrl));
    return;
  }
  
  // 2. Abort previous pending image loading to prevent wasted GPU/CPU processing
  if (currentExtractImg) {
    currentExtractImg.onload = null;
    currentExtractImg.onerror = null;
    currentExtractImg = null;
  }
  
  const img = new Image();
  img.crossOrigin = "Anonymous";
  currentExtractImg = img;
  
  img.onload = () => {
    if (currentExtractImg !== img) return; // Discard if aborted by newer request
    
    // Reuse single offscreen canvas
    if (!sharedCanvas) {
      sharedCanvas = document.createElement('canvas');
      sharedCanvas.width = 64;
      sharedCanvas.height = 64;
      sharedCtx = sharedCanvas.getContext('2d', { willReadFrequently: true });
    }
    
    sharedCtx.drawImage(img, 0, 0, 64, 64);
    const imageData = sharedCtx.getImageData(0, 0, 64, 64).data;
    const colors = [];
    
    // Sample pixels for bubble candidates
    for (let i = 0; i < imageData.length; i += 4 * 16) {
      const r = imageData[i];
      const g = imageData[i+1];
      const b = imageData[i+2];
      
      const maxC = Math.max(r, g, b);
      const minC = Math.min(r, g, b);
      const saturation = maxC - minC;
      
      if (maxC >= 50 && maxC <= 215 && saturation >= 45) {
        colors.push({r, g, b, saturation, maxC});
      }
    }
    
    const selectedColorsRgb = [{r: 0, g: 0, b: 0}];
    
    if (colors.length > 0) {
      colors.sort((c1, c2) => c2.saturation - c1.saturation);
      for (let i = 0; i < colors.length; i++) {
        let c = colors[i];
        let isDistinct = true;
        for (let j = 1; j < selectedColorsRgb.length; j++) {
          let existing = selectedColorsRgb[j];
          let dist = Math.sqrt(Math.pow(c.r - existing.r, 2) + Math.pow(c.g - existing.g, 2) + Math.pow(c.b - existing.b, 2));
          if (dist < 50) {
            isDistinct = false;
            break;
          }
        }
        if (isDistinct) selectedColorsRgb.push(c);
        if (selectedColorsRgb.length === 4) break;
      }
    }
    
    const fallbackVibrant = [
      {r: 138, g: 43, b: 226},
      {r: 0, g: 210, b: 255},
      {r: 255, g: 0, b: 127}
    ];
    let fallbackIdx = 0;
    while (selectedColorsRgb.length < 4 && fallbackIdx < fallbackVibrant.length) {
      selectedColorsRgb.push(fallbackVibrant[fallbackIdx++]);
    }
    
    const selectedColors = selectedColorsRgb.map(c => 
      `#${c.r.toString(16).padStart(2,'0')}${c.g.toString(16).padStart(2,'0')}${c.b.toString(16).padStart(2,'0')}`
    );
    
    // Save to cache for instant future retrieval (up to 100 entries)
    if (colorCache.size > 100) {
      const firstKey = colorCache.keys().next().value;
      colorCache.delete(firstKey);
    }
    colorCache.set(finalUrl, selectedColors);
    
    currentExtractImg = null;
    callback(selectedColors);
  };
  
  img.onerror = () => {
    if (currentExtractImg === img) currentExtractImg = null;
    callback(defaultPalette);
  };
  
  img.src = finalUrl;
}
window.extractDominantColors = extractDominantColors;
