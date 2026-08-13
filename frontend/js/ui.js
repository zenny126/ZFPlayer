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
      
      // Helper to hide all views
      [libraryView, albumsView, homeView].forEach(v => {
        if (v) { v.classList.add('hidden'); v.classList.remove('active'); }
      });

      if (state.view === 'home') {
        homeView?.classList.remove('hidden');
        homeView?.classList.add('active');
        if (window.homeManager) window.homeManager.loadHome();
      } else if (state.view === 'songs') {
        libraryView?.classList.remove('hidden');
        libraryView?.classList.add('active');
        if (window.libraryManager) {
          window.libraryManager.currentPlaylistId = 'all';
          window.libraryManager.reload();
          if (window.api) {
            if (window.api.setActivePlaylist) window.api.setActivePlaylist('all');
            else if (window.api.set_active_playlist) window.api.set_active_playlist('all');
          }
        }
      } else if (state.view === 'albums') {
        albumsView?.classList.remove('hidden');
        albumsView?.classList.add('active');
        
        if (window.albumsManager && window.albumsManager.albums.length === 0) {
          window.albumsManager.loadAlbums();
        }
      } else if (state.view === 'playlist') {
        libraryView?.classList.remove('hidden');
        libraryView?.classList.add('active');
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
          subtitle: 'Tất cả bài hát',
          icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 22px; height: 22px; color: var(--accent);"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`
        },
        {
          id: 'favorites',
          name: 'Favorite Songs',
          subtitle: 'Bài hát yêu thích',
          icon: `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" style="width: 22px; height: 22px; color: #e74c3c;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`
        }
      ];

      systemPlaylists.forEach(pl => {
        const li = document.createElement('li');
        if (state.view === 'playlist' && state.playlistId === pl.id) {
          li.classList.add('active');
        }
        li.innerHTML = `
          <div class="icon-placeholder">${pl.icon}</div>
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
    menu.dataset.trackPath = track.path;
    
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
}

window.UIController = UIController;
