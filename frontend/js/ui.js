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

    // Settings
    document.getElementById('btn-settings').addEventListener('click', () => {
      document.getElementById('settings-modal').classList.remove('hidden');
    });

    document.getElementById('btn-close-settings').addEventListener('click', () => {
      document.getElementById('settings-modal').classList.add('hidden');
    });
    document.addEventListener('click', (e) => {
    });

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
