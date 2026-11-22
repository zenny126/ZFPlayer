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
    this.assigned = new Map(); // index -> pool item (O(1) lookup)
    this.freePool = [];        // available free pool items
    this.ticking = false;
    
    this.container.addEventListener('scroll', () => {
      this.scrollTop = this.container.scrollTop;
      if (!this.ticking) {
        this.ticking = true;
        requestAnimationFrame(() => {
          this.update();
          this.ticking = false;
        });
      }
    }, { passive: true });

    if (typeof ResizeObserver !== 'undefined') {
      this._resizeObserver = new ResizeObserver(() => {
        if (this.totalItems > 0) {
          this.ensurePoolCapacity();
          this.update();
        }
      });
      this._resizeObserver.observe(this.container);
    }
  }

  ensurePoolCapacity() {
    const visibleCount = Math.ceil(this.container.clientHeight / this.itemHeight) || 15;
    this.poolSize = Math.max(this.poolSize, visibleCount + 10);
    while (this.pool.length < this.poolSize) {
      const node = this.renderFn(-1);
      node.style.position = 'absolute';
      node.style.left = '0';
      node.style.right = '0';
      node.style.display = 'none';
      this.scroller.appendChild(node);
      const item = { node, index: -1 };
      this.pool.push(item);
      this.freePool.push(item);
    }
  }

  setTotalItems(total) {
    this.totalItems = total;
    this.scroller.style.height = `${total * this.itemHeight}px`;
    this.ensurePoolCapacity();
    this.refresh();
  }

  update() {
    if (this.totalItems === 0) {
      this.assigned.clear();
      this.freePool = [...this.pool];
      this.pool.forEach(p => {
        p.index = -1;
        p.node.style.display = 'none';
      });
      return;
    }
    const offsetTop = this.scroller ? this.scroller.offsetTop : 0;
    const trackScrollTop = Math.max(0, this.scrollTop - offsetTop);
    const visibleHeight = this.container.clientHeight || 600;
    const startIndex = Math.max(0, Math.floor(trackScrollTop / this.itemHeight) - 3);
    const endIndex = Math.min(this.totalItems - 1, Math.ceil((trackScrollTop + visibleHeight) / this.itemHeight) + 3);

    // 1. Free up nodes that scrolled out of visible range
    for (const [idx, item] of this.assigned.entries()) {
      if (idx < startIndex || idx > endIndex) {
        item.index = -1;
        item.node.style.display = 'none';
        this.assigned.delete(idx);
        this.freePool.push(item);
      }
    }
    
    // 2. Assign and position nodes for newly visible items in O(1)
    for (let i = startIndex; i <= endIndex; i++) {
      let item = this.assigned.get(i);
      if (!item) {
        if (this.freePool.length > 0) {
          item = this.freePool.pop();
          item.index = i;
          item.node.style.display = '';
          this.renderFn(i, item.node);
          this.assigned.set(i, item);
        }
      }
      if (item) {
        item.node.style.transform = `translateY(${i * this.itemHeight}px)`;
        item.node.style.top = '0';
      }
    }
  }
  
  refresh() {
    this.assigned.clear();
    this.freePool = [...this.pool];
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
    
    this.initControls();
    this.initStoreSubscriptions();
    this.initContainerEvents();
  }

  initStoreSubscriptions() {
    window.store.subscribe('currentTrack', () => this.vList.refresh());
    window.store.subscribe('isPlaying', (isPlaying) => this.syncPlayingState(isPlaying));
  }

  syncPlayingState(isPlaying) {
    const activeRows = this.container.querySelectorAll('.track-row.active');
    activeRows.forEach(r => r.classList.toggle('playing', !!isPlaying));
  }

  initControls() {
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

    const searchInput = document.getElementById('search-input');
    const btnClearSearch = document.getElementById('btn-clear-search');

    const updateClearBtn = (val) => {
      if (!btnClearSearch) return;
      if (val && val.length > 0) {
        btnClearSearch.classList.remove('hidden');
      } else {
        btnClearSearch.classList.add('hidden');
      }
    };

    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        updateClearBtn(e.target.value);
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
          const currentView = window.store.getState().view;
          if (currentView === 'home' || currentView === 'albums') {
            this.currentPlaylistId = 'all';
            window.store.setState({ view: 'songs' });
          }
          this.searchQuery = e.target.value;
          this.reload();
        }, 300);
      });

      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          e.target.value = '';
          updateClearBtn('');
          this.searchQuery = '';
          this.reload();
        }
      });
    }

    if (btnClearSearch) {
      btnClearSearch.addEventListener('click', () => {
        if (searchInput) {
          searchInput.value = '';
          searchInput.focus();
        }
        updateClearBtn('');
        this.searchQuery = '';
        this.reload();
      });
    }
  }

  initContainerEvents() {
    this.container.addEventListener('dblclick', async (e) => {
      const row = e.target.closest('.track-row');
      if (!row || !row.dataset.index) return;
      const track = await this.getTrack(parseInt(row.dataset.index));
      if (track && window.playerController) {
        window.playerController.playTrack(track, this.currentPlaylistId);
      }
    });

    this.container.addEventListener('click', async (e) => {
      const playIconBtn = e.target.closest('.play-icon');
      if (playIconBtn) {
        e.stopPropagation();
        await this.handleRowPlayClick(playIconBtn);
        return;
      }

      const likeBtn = e.target.closest('.track-like');
      if (likeBtn) {
        e.stopPropagation();
        await this.handleRowLikeClick(likeBtn);
        return;
      }

      const moreBtn = e.target.closest('.track-more');
      if (moreBtn) {
        e.stopPropagation();
        const row = moreBtn.closest('.track-row');
        if (!row || !row.dataset.index) return;
        const track = await this.getTrack(parseInt(row.dataset.index));
        if (track && window.uiController) window.uiController.showContextMenu(e, track);
      }
    });

    this.container.addEventListener('contextmenu', async (e) => {
      const row = e.target.closest('.track-row');
      if (!row || !row.dataset.index) return;
      e.preventDefault();
      const track = await this.getTrack(parseInt(row.dataset.index));
      if (track && window.uiController) window.uiController.showContextMenu(e, track);
    });
  }

  async handleRowPlayClick(playIconBtn) {
    const row = playIconBtn.closest('.track-row');
    if (!row || !row.dataset.index) return;
    const track = await this.getTrack(parseInt(row.dataset.index));
    if (!track || !window.playerController) return;

    const currentTrack = window.store.getState().currentTrack;
    if (currentTrack && currentTrack.path === track.path) {
      await window.playerController.togglePlay();
      return;
    }
    await window.playerController.playTrack(track, this.currentPlaylistId);
  }

  async handleRowLikeClick(likeBtn) {
    const row = likeBtn.closest('.track-row');
    if (!row || !row.dataset.index) return;
    const track = await this.getTrack(parseInt(row.dataset.index));
    if (!track || !window.api?.toggleLike) return;

    const res = await window.api.toggleLike(track.path);
    if (!res || res.status !== 'success') return;

    track.is_liked = res.is_liked;
    this.vList.refresh();
    const currentTrack = window.store.getState().currentTrack;
    if (currentTrack && currentTrack.path === track.path) {
      window.store.setState({ currentTrack: { ...currentTrack, is_liked: res.is_liked } });
    }
    if (window.uiController?.showToast) {
      const msg = res.is_liked ? 'Added to Favorite Songs' : 'Removed from Favorite Songs';
      window.uiController.showToast(msg);
    }
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

  getCachedTrack(index) {
    const pageIndex = Math.floor(index / this.pageSize);
    const page = this.cache.get(pageIndex);
    return page ? page[index % this.pageSize] : null;
  }

  _renderSkeletonRow(row, index) {
    row.innerHTML = `
      <div class="track-number"><span class="track-number-text">${index + 1}</span><div class="soundwave"><span class="soundwave-bar"></span><span class="soundwave-bar"></span><span class="soundwave-bar"></span></div></div>
      <div class="play-icon">
        <svg viewBox="0 0 24 24" fill="currentColor" class="icon-row-play" style="width: 14px; height: 14px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
        <svg viewBox="0 0 24 24" fill="currentColor" class="icon-row-pause" style="width: 14px; height: 14px;"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
      </div>
      <div class="track-title">Loading...</div>
      <div class="track-album"></div>
      <div class="track-date"></div>
      <div class="track-like"></div>
      <div class="track-more"></div>
      <div class="track-duration"></div>
    `;
  }

  _applyTrackToRow(row, index, track) {
    const currentTrack = window.store.getState().currentTrack;
    const isPlaying = !!window.store.getState().isPlaying;
    if (currentTrack && currentTrack.path === track.path) {
      row.classList.add('active');
      row.classList.toggle('playing', isPlaying);
    } else {
      row.classList.remove('active', 'playing');
    }
    
    const coverUrl = track.cover_hash ? `/api/covers/${track.cover_hash}_thumb.jpg` : 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI1NiIgaGVpZ2h0PSI1NiI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0iIzMzMyIvPjwvc3ZnPg==';
    const dateStr = track.mtime ? new Date(track.mtime * 1000).toLocaleDateString() : '';
    const isLiked = track.is_liked === 1;
    const likeClass = isLiked ? 'liked' : '';
    const likeIconEmpty = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
    const likeIconFilled = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
    const likeIcon = isLiked ? likeIconFilled : likeIconEmpty;
    const moreIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon" style="width: 18px; height: 18px;"><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle></svg>`;
    const fallbackAttr = track.cover_hash ? `onerror="this.onerror=null;this.src='/api/covers/${track.cover_hash}.jpg';"` : '';

    row.innerHTML = `
      <div class="track-number"><span class="track-number-text">${index + 1}</span><div class="soundwave"><span class="soundwave-bar"></span><span class="soundwave-bar"></span><span class="soundwave-bar"></span></div></div>
      <div class="play-icon">
        <svg viewBox="0 0 24 24" fill="currentColor" class="icon-row-play" style="width: 14px; height: 14px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
        <svg viewBox="0 0 24 24" fill="currentColor" class="icon-row-pause" style="width: 14px; height: 14px;"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
      </div>
      <div class="track-title">
         <img src="${coverUrl}" class="track-thumbnail" alt="" loading="lazy" decoding="async" ${fallbackAttr}>
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
  }

  renderTrack(index, existingRow = null) {
    const row = existingRow || document.createElement('div');
    if (!existingRow) {
      row.className = 'track-row';
      row.draggable = true;
      row.addEventListener('dragstart', (e) => {
         const idx = parseInt(row.dataset.index);
         if (isNaN(idx)) return e.preventDefault();
         const track = this.getCachedTrack(idx);
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

    // Fast Path: Synchronous single-pass render for cached tracks (0ms skeleton flicker)
    const cachedTrack = this.getCachedTrack(index);
    if (cachedTrack) {
      this._applyTrackToRow(row, index, cachedTrack);
      return row;
    }

    // Fallback: asynchronous load for uncached pages
    this._renderSkeletonRow(row, index);

    this.getTrack(index).then(track => {
      if (parseInt(row.dataset.index) !== index) return;
      if (!track) return;
      this._applyTrackToRow(row, index, track);
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
