class VirtualList {
  constructor(container, itemHeight, renderFn) {
    this.container = container;
    this.scroller = container.querySelector('.library-scroller');
    this.itemHeight = itemHeight;
    this.renderFn = renderFn;
    this.totalItems = 0;
    this.scrollTop = 0;
    this.pool = [];
    this.poolSize = 0;
    
    this.container.addEventListener('scroll', () => {
      this.scrollTop = this.container.scrollTop;
      requestAnimationFrame(() => this.update());
    });
  }

  setTotalItems(total) {
    this.totalItems = total;
    this.scroller.style.height = `${total * this.itemHeight}px`;
    
    // Initialize pool
    const visibleCount = Math.ceil(this.container.clientHeight / this.itemHeight) || 15;
    this.poolSize = Math.max(this.poolSize, visibleCount + 10);
    
    while (this.pool.length < this.poolSize) {
      const node = this.renderFn(-1);
      node.style.position = 'absolute';
      node.style.left = '0';
      node.style.right = '0';
      node.style.display = 'none';
      this.scroller.appendChild(node);
      this.pool.push({ node, index: -1 });
    }
    
    this.refresh();
  }

  update() {
    if (this.totalItems === 0) {
       this.pool.forEach(p => p.node.style.display = 'none');
       return;
    }
    const offsetTop = this.scroller ? this.scroller.offsetTop : 0;
    const trackScrollTop = Math.max(0, this.scrollTop - offsetTop);
    const visibleHeight = this.container.clientHeight;
    const startIndex = Math.max(0, Math.floor(trackScrollTop / this.itemHeight) - 3);
    const endIndex = Math.min(this.totalItems - 1, Math.ceil((trackScrollTop + visibleHeight) / this.itemHeight) + 3);

    const needed = new Set();
    for (let i = startIndex; i <= endIndex; i++) needed.add(i);
    
    this.pool.forEach(p => {
       if (p.index !== -1 && !needed.has(p.index)) {
          p.index = -1;
          p.node.style.display = 'none';
       }
    });
    
    for (let i = startIndex; i <= endIndex; i++) {
       let assigned = this.pool.find(p => p.index === i);
       if (!assigned) {
          let free = this.pool.find(p => p.index === -1);
          if (free) {
             free.index = i;
             free.node.style.display = '';
             this.renderFn(i, free.node);
             assigned = free;
          }
       }
       if (assigned) {
          assigned.node.style.transform = `translateY(${i * this.itemHeight}px)`;
          assigned.node.style.top = '0';
       }
    }
  }
  
  refresh() {
    this.pool.forEach(p => {
      p.index = -1;
      p.node.style.display = 'none';
    });
    this.update();
  }
}

class LibraryManager {
  constructor() {
    this.container = document.getElementById('library-container');
    this.cache = new Map(); // pageIndex -> array of tracks
    this.loading = new Map();
    this.pageSize = 50;
    this.totalCount = 0;
    this.searchQuery = '';
    this.currentPlaylistId = null;
    this.sortBy = 'title';
    this.sortDir = 'ASC';
    
    this.vList = new VirtualList(this.container, 56, (index, node) => this.renderTrack(index, node));
    
    document.getElementById('btn-playlist-import-files').addEventListener('click', () => {
      window.api.selectMusicFiles().then(files => {
        if (files && files.length > 0) window.api.importFilesToPlaylist(this.currentPlaylistId, files).then(() => this.reloadCurrent());
      });
    });

    document.getElementById('btn-playlist-import-folder').addEventListener('click', () => {
      window.api.selectMusicDir().then(folder => {
        if (folder) window.api.importFolderToPlaylist(this.currentPlaylistId, folder).then(() => this.reloadCurrent());
      });
    });

    const btnPlay = document.getElementById('btn-playlist-play');
    if (btnPlay) {
      btnPlay.addEventListener('click', () => {
        if (this.totalCount > 0) {
          this.getTrack(0).then(track => {
            if (track && window.playerController) {
              window.playerController.playTrack(track, this.currentPlaylistId);
            }
          });
        }
      });
    }
    
    document.getElementById('search-input').addEventListener('input', (e) => {
      clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => {
        this.searchQuery = e.target.value;
        this.reload();
      }, 300);
    });
    
    window.store.subscribe('currentTrack', () => this.vList.refresh());

    // Event delegation for performance
    this.container.addEventListener('dblclick', (e) => {
        const row = e.target.closest('.track-row');
        if (row && row.dataset.index) {
            this.getTrack(parseInt(row.dataset.index)).then(track => {
                if (track && window.playerController) window.playerController.playTrack(track, this.currentPlaylistId);
            });
        }
    });

    this.container.addEventListener('click', async (e) => {
        const likeBtn = e.target.closest('.track-like');
        if (likeBtn) {
            e.stopPropagation();
            const row = likeBtn.closest('.track-row');
            if (!row || !row.dataset.index) return;
            const track = await this.getTrack(parseInt(row.dataset.index));
            if (track && window.api && window.api.toggleLike) {
               const res = await window.api.toggleLike(track.path);
               if (res && res.status === 'success') {
                  track.is_liked = res.is_liked;
                  this.vList.refresh();
                  // Sync with store if it's the currently playing track
                  const currentTrack = window.store.getState().currentTrack;
                  if (currentTrack && currentTrack.path === track.path) {
                    window.store.setState({ currentTrack: { ...currentTrack, is_liked: res.is_liked } });
                  }
               }
            }
            return;
        }

        const moreBtn = e.target.closest('.track-more');
        if (moreBtn) {
            e.stopPropagation();
            const row = moreBtn.closest('.track-row');
            if (!row || !row.dataset.index) return;
            const track = await this.getTrack(parseInt(row.dataset.index));
            if (track && window.uiController) window.uiController.showContextMenu(e, track);
            return;
        }
    });
    
    this.container.addEventListener('contextmenu', async (e) => {
        const row = e.target.closest('.track-row');
        if (row && row.dataset.index) {
            e.preventDefault();
            const track = await this.getTrack(parseInt(row.dataset.index));
            if (track && window.uiController) window.uiController.showContextMenu(e, track);
        }
    });
  }

  async init() {
    await this.reload();
  }

  async reload() {
    this.cache.clear();
    this.container.scrollTop = 0;
    
    this.totalCount = await window.api.getTrackCount(this.searchQuery, this.currentPlaylistId);
    this.vList.setTotalItems(this.totalCount);
    this.updateHeader();
  }

  async updateHeader() {
    const el = document.getElementById('playlist-detail-count');
    if (el) {
        el.textContent = `${this.totalCount} tracks`;
    }
  }

  async getTrack(index) {
    const pageIndex = Math.floor(index / this.pageSize);
    const itemIndex = index % this.pageSize;
    
    if (!this.cache.has(pageIndex)) {
      if (!this.loading.has(pageIndex)) {
        const loadPromise = window.api.getTracks(pageIndex * this.pageSize, this.pageSize, this.searchQuery, this.sortBy, this.sortDir, this.currentPlaylistId)
          .then(tracks => {
            this.cache.set(pageIndex, tracks);
            this.loading.delete(pageIndex);
          })
          .catch(err => {
            this.loading.delete(pageIndex);
            console.error(err);
          });
        this.loading.set(pageIndex, loadPromise);
      }
      await this.loading.get(pageIndex);
    }
    
    const page = this.cache.get(pageIndex);
    return page ? page[itemIndex] : null;
  }

  renderTrack(index, existingRow = null) {
    const row = existingRow || document.createElement('div');
    if (!existingRow) {
      row.className = 'track-row';
      row.draggable = true;
      row.addEventListener('dragstart', (e) => {
         const idx = parseInt(row.dataset.index);
         if (isNaN(idx)) {
           e.preventDefault();
           return;
         }
         const page = this.cache.get(Math.floor(idx / this.pageSize));
         const track = page ? page[idx % this.pageSize] : null;
         if (track && track.path) {
            e.dataTransfer.setData('text/plain', track.path);
            e.dataTransfer.effectAllowed = 'copy';
         } else {
            e.preventDefault();
         }
      });
    }
    
    if (index === -1) {
       row.innerHTML = '';
       row.dataset.index = '';
       return row;
    }
    
    row.dataset.index = index;

    // Quick sync layout
    row.innerHTML = `
      <div class="track-number">${index + 1}</div>
      <div class="play-icon">▶</div>
      <div class="track-title">Loading...</div>
      <div class="track-album"></div>
      <div class="track-date"></div>
      <div class="track-like"></div>
      <div class="track-more"></div>
      <div class="track-duration"></div>
    `;

    this.getTrack(index).then(track => {
      // Check if this row is STILL representing this index after async load
      if (parseInt(row.dataset.index) !== index) return;
      
      if (!track) return;
      const currentTrack = window.store.getState().currentTrack;
      if (currentTrack && currentTrack.path === track.path) {
        row.classList.add('active');
      } else {
        row.classList.remove('active');
      }
      
      let coverUrl = track.cover_hash ? `/api/covers/${track.cover_hash}.jpg` : 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI1NiIgaGVpZ2h0PSI1NiI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0iIzMzMyIvPjwvc3ZnPg==';
      
      const dateStr = track.mtime ? new Date(track.mtime * 1000).toLocaleDateString() : '';
      
      const isLiked = track.is_liked === 1;
      const likeClass = isLiked ? 'liked' : '';
      const likeIconEmpty = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
      const likeIconFilled = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
      const likeIcon = isLiked ? likeIconFilled : likeIconEmpty;
      
      const playIcon = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 14px; height: 14px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
      const moreIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle></svg>`;
      
      row.innerHTML = `
        <div class="track-number">${index + 1}</div>
        <div class="play-icon">${playIcon}</div>
        <div class="track-title">
           <img src="${coverUrl}" class="track-thumbnail" alt="">
           <div class="track-title-text">
             <div class="track-title-name">${track.title || 'Unknown Title'}</div>
             <div class="track-title-artist">${track.artist || 'Unknown Artist'}</div>
           </div>
        </div>
        <div class="track-album">${track.album || 'Unknown Album'}</div>
        <div class="track-date">${dateStr}</div>
        <div class="track-like ${likeClass}" data-path="${track.path}">${likeIcon}</div>
        <div class="track-more">${moreIcon}</div>
        <div class="track-duration">${this.formatTime(track.duration)}</div>
      `;
    });
    
    return row;
  }
  
  formatTime(sec) {
    if (!sec) return '';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  }
}

window.LibraryManager = LibraryManager;
