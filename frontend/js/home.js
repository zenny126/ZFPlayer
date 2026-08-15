class HomeManager {
  constructor() {
    this.recentContainer = document.getElementById('home-recent-grid');
    this.playlistsContainer = document.getElementById('home-playlists-grid');
    this.loaded = false;
    this.lastRecentPaths = [];
    this.renderedTracks = [];
  }

  async loadHome() {
    if (this.loaded) {
      this.loadRecent();
      return;
    }
    
    await Promise.all([
      this.loadPlaylists(),
      this.loadRecent()
    ]);
    this.loaded = true;
  }

  async loadPlaylists() {
    if (!this.playlistsContainer) return;
    try {
      this.playlistsContainer.innerHTML = '';
      
      const playlists = [
        { id: 'all', name: 'All Songs', subtitle: 'All your local tracks', icon: 'M9 18V5l12-2v13 M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', bg: 'transparent', color: '#ffffff', fill: 'none' },
        { id: 'favorites', name: 'Favorite Songs', subtitle: 'Your favorite tracks', icon: 'M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z', bg: 'transparent', color: '#ffffff', fill: 'currentColor' }
      ];

      // Fetch custom playlists
      const customPlaylists = await window.api.getPlaylists() || [];
      customPlaylists.forEach(p => {
        playlists.push({
          id: p.id,
          name: p.name,
          subtitle: `${p.track_count || 0} tracks`,
          cover_url: p.cover_url,
          icon: 'M9 18V5l12-2v13 M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
          bg: 'transparent',
          color: '#ffffff'
        });
      });

      // Add "Create Playlist" card
      playlists.push({
        id: 'create',
        name: 'Create Playlist',
        subtitle: 'Create a new playlist',
        icon: 'M12 5v14M5 12h14',
        bg: 'rgba(255,255,255,0.05)',
        color: '#888'
      });
      
      const fragment = document.createDocumentFragment();

      playlists.forEach(pl => {
        const card = document.createElement('div');
        card.className = 'album-card';
        
        let coverHtml = '';
        if (pl.cover_url) {
          coverHtml = `<img src="${pl.cover_url}" style="width: 100%; height: 100%; object-fit: cover;" alt="">`;
        } else {
          coverHtml = `<svg viewBox="0 0 24 24" fill="${pl.fill || 'none'}" stroke="${pl.fill === 'currentColor' ? 'none' : 'currentColor'}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 48px; height: 48px; color: ${pl.color};"><path d="${pl.icon}"></path></svg>`;
        }
        
        card.innerHTML = `
          <div class="album-cover-container" style="display: flex; align-items: center; justify-content: center; background: ${pl.bg}; overflow: hidden;">
            ${coverHtml}
          </div>
          <div class="album-info">
            <div class="album-title" title="${pl.name}">${pl.name}</div>
            <div class="album-artist">${pl.subtitle}</div>
          </div>
        `;
        
        card.addEventListener('click', () => {
          if (pl.id === 'create') {
            document.getElementById('input-playlist-name').value = '';
            document.getElementById('create-playlist-modal').classList.remove('hidden');
            document.getElementById('input-playlist-name').focus();
          } else {
            document.querySelectorAll('#playlist-container li').forEach(item => item.classList.remove('active'));
            const sideItem = document.querySelector(`#playlist-container li[data-id="${pl.id}"]`);
            if (sideItem) sideItem.classList.add('active');
            window.store.setState({ view: 'playlist', playlistId: pl.id });
          }
        });
        
        fragment.appendChild(card);
      });

      this.playlistsContainer.appendChild(fragment);
    } catch (e) {
      console.error("Failed to load playlists", e);
    }
  }

  formatTime(seconds) {
    if (!seconds) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

  async loadRecent() {
    if (!this.recentContainer) return;
    try {
      const tracks = await window.api.getTracks(0, 20, "", "last_played", "DESC", null);
      if (!tracks || tracks.length === 0) {
        this.recentContainer.innerHTML = '<div style="color: var(--text-subdued); padding: 16px;">No recently played tracks yet.</div>';
        this.lastRecentPaths = [];
        return;
      }

      const currentTrack = window.store.getState().currentTrack;
      const currentTrackPath = currentTrack ? currentTrack.path : null;
      const newPaths = tracks.map(t => t.path);

      // Fast Path: If track order hasn't changed, only update active highlight without recreating DOM
      if (this.lastRecentPaths.length === newPaths.length && this.lastRecentPaths.every((p, i) => p === newPaths[i])) {
        const rows = this.recentContainer.querySelectorAll('.track-row');
        rows.forEach((row, i) => {
          const track = tracks[i];
          if (track && track.path === currentTrackPath) {
            row.classList.add('active');
          } else {
            row.classList.remove('active');
          }
        });
        return;
      }

      this.lastRecentPaths = newPaths;
      this.recentContainer.innerHTML = '';
      const fragment = document.createDocumentFragment();

      tracks.forEach((track, index) => {
        const row = document.createElement('div');
        row.className = 'track-row track-row-static';
        if (currentTrackPath === track.path) {
          row.classList.add('active');
        }
        
        let coverUrl = track.cover_hash ? `/api/covers/${track.cover_hash}_thumb.jpg` : 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI1NiIgaGVpZ2h0PSI1NiI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0iIzMzMyIvPjwvc3ZnPg==';
        
        const dateStr = track.mtime ? new Date(track.mtime * 1000).toLocaleDateString() : '';
        const isLiked = track.is_liked === 1;
        const likeIconEmpty = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
        const likeIconFilled = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
        const likeIcon = isLiked ? likeIconFilled : likeIconEmpty;
        const playIcon = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 14px; height: 14px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
        const moreIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle></svg>`;

        const fallbackAttr = track.cover_hash ? `onerror="this.onerror=null;this.src='/api/covers/${track.cover_hash}.jpg';"` : '';

        row.innerHTML = `
          <div class="track-number">${index + 1}</div>
          <div class="play-icon">${playIcon}</div>
          <div class="track-title">
             <img src="${coverUrl}" class="track-thumbnail" alt="" ${fallbackAttr}>
             <div class="track-title-text">
               <div class="track-title-name">${track.title || 'Unknown Title'}</div>
               <div class="track-title-artist">${track.artist || 'Unknown Artist'}</div>
             </div>
          </div>
          <div class="track-album">${track.album || 'Unknown Album'}</div>
          <div class="track-date">${dateStr}</div>
          <div class="track-like ${isLiked ? 'liked' : ''}" data-path="${track.path}">${likeIcon}</div>
          <div class="track-more">${moreIcon}</div>
          <div class="track-duration">${this.formatTime(track.duration)}</div>
        `;
        
        row.addEventListener('click', (e) => {
          if (e.target.closest('.track-like')) {
            window.api.toggleLike(track.path).then(res => {
              track.is_liked = res.is_liked ? 1 : 0;
              const likeBtn = row.querySelector('.track-like');
              likeBtn.className = `track-like ${track.is_liked ? 'liked' : ''}`;
              likeBtn.innerHTML = track.is_liked ? likeIconFilled : likeIconEmpty;
            });
            return;
          }
          if (e.target.closest('.track-more')) {
            e.stopPropagation();
            if (window.uiController) window.uiController.showContextMenu(e, track);
            return;
          }
          if (window.playerController) {
            window.playerController.playTrack(track);
          }
        });
        
        row.addEventListener('contextmenu', (e) => {
          e.preventDefault();
          if (window.uiController) window.uiController.showContextMenu(e, track);
        });
        
        fragment.appendChild(row);
      });

      this.recentContainer.appendChild(fragment);
    } catch (e) {
      console.error("Failed to load recent tracks", e);
    }
  }
}

window.homeManager = new HomeManager();
