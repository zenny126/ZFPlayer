class AlbumsManager {
  constructor() {
    this.container = document.getElementById('albums-view');
    this.albums = [];
  }

  async loadAlbums() {
    try {
      this.albums = await window.api.getAlbums();
      this.render();
    } catch (e) {
      console.error('Failed to load albums:', e);
      this.container.innerHTML = `<div style="padding: 24px; color: var(--error);">Error loading albums</div>`;
    }
  }

  render() {
    if (!this.albums || this.albums.length === 0) {
      this.container.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="empty-icon"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg>
          <div class="empty-title">No Albums Found</div>
          <div class="empty-subtitle">Add some music to your library first.</div>
        </div>
      `;
      return;
    }

    let html = '<div class="albums-container"><div class="albums-grid">';
    
    this.albums.forEach(album => {
      const coverUrl = album.cover_url || 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%23666" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>';
      
      const albumName = album.album || 'Unknown Album';
      const artistName = album.artist || 'Unknown Artist';
      const titleEscaped = albumName.toString().replace(/"/g, '&quot;');
      const artistEscaped = artistName.toString().replace(/"/g, '&quot;');
      
      html += `
        <div class="album-card" data-album="${titleEscaped}" data-artist="${artistEscaped}">
          <div class="album-cover-container">
            <img src="${coverUrl}" class="album-cover" loading="lazy" alt="Cover" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' viewBox=\\'0 0 24 24\\' fill=\\'none\\' stroke=\\'%23666\\' stroke-width=\\'1\\' stroke-linecap=\\'round\\' stroke-linejoin=\\'round\\'><rect x=\\'3\\' y=\\'3\\' width=\\'18\\' height=\\'18\\' rx=\\'2\\' ry=\\'2\\'></rect><circle cx=\\'8.5\\' cy=\\'8.5\\' r=\\'1.5\\'></circle><polyline points=\\'21 15 16 10 5 21\\'></polyline></svg>'">
          </div>
          <div class="album-info">
            <div class="album-title" title="${titleEscaped}">${albumName}</div>
            <div class="album-artist" title="${artistEscaped}">${artistName}</div>
            <div class="album-meta">${album.track_count} song${album.track_count !== 1 ? 's' : ''}</div>
          </div>
        </div>
      `;
    });
    
    html += '</div></div>';
    this.container.innerHTML = html;
    
    // Bind click events
    const cards = this.container.querySelectorAll('.album-card');
    cards.forEach(card => {
      card.addEventListener('click', () => {
        const albumName = card.dataset.album;
        // Search and switch to songs view
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
          searchInput.value = albumName;
          // Dispatch input event to trigger search
          searchInput.dispatchEvent(new Event('input'));
        }
        window.store.setState({ view: 'songs' });
      });
    });
  }
}

window.AlbumsManager = AlbumsManager;
