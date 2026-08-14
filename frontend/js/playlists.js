class PlaylistManager {
  constructor() {
    this.playlists = [];
    this.systemCovers = { all: null, favorites: null };
    this.currentPlaylistId = null;
    this.targetPlaylistId = null;
    
    // Elements
    this.container = document.getElementById('playlist-container');
    
    this.btnCreate = document.getElementById('btn-create-playlist');
    this.modalCreate = document.getElementById('create-playlist-modal');
    this.inputName = document.getElementById('input-playlist-name');
    this.btnSave = document.getElementById('btn-save-playlist');
    this.btnCancel = document.getElementById('btn-cancel-playlist');

    // Rename Modal Elements
    this.modalRename = document.getElementById('rename-playlist-modal');
    this.inputRename = document.getElementById('input-rename-playlist-name');
    this.btnSaveRename = document.getElementById('btn-save-rename-playlist');
    this.btnCancelRename = document.getElementById('btn-cancel-rename-playlist');

    // Delete Modal Elements
    this.modalDelete = document.getElementById('delete-playlist-modal');
    this.btnConfirmDelete = document.getElementById('btn-confirm-delete-playlist');
    this.btnCancelDelete = document.getElementById('btn-cancel-delete-playlist');
    
    this.btnImportFolder = document.getElementById('btn-playlist-import-folder');
    this.btnImportFiles = document.getElementById('btn-playlist-import-files');
    this.coverContainer = document.getElementById('playlist-cover-container');

    // Header Action Buttons
    this.btnHeaderEdit = document.getElementById('btn-playlist-edit-header');
    this.modalEdit = document.getElementById('edit-playlist-modal');
    this.btnSaveEdit = document.getElementById('btn-save-edit-playlist');
    this.btnCancelEdit = document.getElementById('btn-cancel-edit-playlist');
    this.btnEditChangeCover = document.getElementById('btn-edit-playlist-change-cover');
    this.editCoverContainer = document.getElementById('edit-playlist-cover-preview-container');
    this.btnEditTriggerDelete = document.getElementById('btn-edit-playlist-trigger-delete');
    this.inputEditName = document.getElementById('input-edit-playlist-name');

    this.submenu = document.getElementById('playlist-submenu');
    this.ctxAddToPlaylist = document.getElementById('ctx-add-to-playlist');
    this.ctxRemoveFromPlaylist = document.getElementById('ctx-remove-from-playlist');
    this.plContextMenu = document.getElementById('playlist-item-context-menu');

    this.init();
  }

  async init() {
    await window.api.readyPromise;
    await this.fetchSystemCovers();
    this.bindEvents();
    this.loadPlaylists();
    
    // Listen to store for UI updates
    window.store.subscribe(['view', 'playlistId'], (state) => {
      const header = document.getElementById('playlist-header');
      if (!header) return;
      
      if (state.view === 'playlist') {
        this.currentPlaylistId = state.playlistId;
        let p = this.playlists.find(x => String(x.id) === String(state.playlistId));
        
        if (state.playlistId === 'all') {
            p = { name: 'All Songs', track_count: window.libraryManager ? window.libraryManager.totalCount : 0, cover_url: this.systemCovers.all };
        } else if (state.playlistId === 'favorites') {
            p = { name: 'Favorite Songs', track_count: window.libraryManager ? window.libraryManager.totalCount : 0, cover_url: this.systemCovers.favorites };
        }

        if (p) {
          header.classList.remove('hidden');
          document.getElementById('playlist-detail-name').textContent = p.name;
          document.getElementById('playlist-detail-count').textContent = `${p.track_count || 0} tracks`;
          
          const coverEl = document.getElementById('playlist-detail-cover');
          if (state.playlistId === 'all') {
             coverEl.src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><path d='M9 18V5l12-2v13 M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z' stroke='%23ffffff' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' fill='none'/></svg>";
          } else if (state.playlistId === 'favorites') {
             coverEl.src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><path d='M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z' fill='%23ffffff'/></svg>";
          } else if (p.cover_url) {
             coverEl.src = p.cover_url;
          } else {
             coverEl.src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><rect width='100%' height='100%' fill='%23282828'/><path d='M9 18V5l12-2v13' stroke='%23888' stroke-width='2' fill='none'/><circle cx='6' cy='18' r='3' stroke='%23888' stroke-width='2' fill='none'/><circle cx='18' cy='16' r='3' stroke='%23888' stroke-width='2' fill='none'/></svg>";
          }

          // Hide import buttons for Favorite Songs playlist
          const isFavorites = (state.playlistId === 'favorites');
          if (this.btnImportFolder) this.btnImportFolder.style.display = isFavorites ? 'none' : 'inline-flex';
          if (this.btnImportFiles) this.btnImportFiles.style.display = isFavorites ? 'none' : 'inline-flex';
        }
      } else {
        header.classList.add('hidden');
      }
    });
  }

  async fetchSystemCovers() {
    if (window.api && window.api.getSystemPlaylistCovers) {
      try {
        const res = await window.api.getSystemPlaylistCovers();
        if (res) {
          this.systemCovers.all = res.all || null;
          this.systemCovers.favorites = res.favorites || null;
        }
      } catch (e) {
        console.warn("Could not fetch system playlist covers", e);
      }
    }
  }

  bindEvents() {
    // Create Playlist
    this.btnCreate?.addEventListener('click', () => {
      this.inputName.value = '';
      this.modalCreate.classList.remove('hidden');
      this.inputName.focus();
    });

    this.btnCancel?.addEventListener('click', () => {
      this.modalCreate.classList.add('hidden');
    });

    this.btnSave?.addEventListener('click', async () => {
      const name = this.inputName.value.trim();
      if (name) {
        await window.api.createPlaylist(name);
        this.modalCreate.classList.add('hidden');
        this.loadPlaylists();
      }
    });

    this.inputName?.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') this.btnSave.click();
    });

    // Single Gear Icon Button on Header -> Opens Edit Playlist Modal
    this.btnHeaderEdit?.addEventListener('click', () => {
      if (this.currentPlaylistId) {
        this.showEditModal(this.currentPlaylistId);
      }
    });

    // Edit Playlist Modal Events
    this.btnCancelEdit?.addEventListener('click', () => {
      this.modalEdit?.classList.add('hidden');
    });

    this.btnSaveEdit?.addEventListener('click', async () => {
      const isSystem = (this.targetPlaylistId === 'all' || this.targetPlaylistId === 'favorites');
      if (!isSystem && this.inputEditName && this.targetPlaylistId) {
        const newName = this.inputEditName.value.trim();
        if (newName) {
          await window.api.renamePlaylist(this.targetPlaylistId, newName);
        }
      }
      this.modalEdit?.classList.add('hidden');
      await this.loadPlaylists();
      if (String(this.currentPlaylistId) === String(this.targetPlaylistId)) {
        this.openPlaylist(this.targetPlaylistId);
      }
    });

    this.inputEditName?.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') this.btnSaveEdit?.click();
    });

    const triggerCoverChange = async () => {
      if (this.targetPlaylistId) {
        await this.changeCover(this.targetPlaylistId);
        // Refresh preview image inside edit modal
        const previewImg = document.getElementById('edit-playlist-cover-preview');
        if (previewImg) {
          if (this.targetPlaylistId === 'all') {
            previewImg.src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><path d='M9 18V5l12-2v13 M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z' stroke='%23ffffff' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' fill='none'/></svg>";
          } else if (this.targetPlaylistId === 'favorites') {
            previewImg.src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><path d='M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z' fill='%23ffffff'/></svg>";
          } else {
            let p = this.playlists.find(x => String(x.id) === String(this.targetPlaylistId));
            if (p && p.cover_url) previewImg.src = p.cover_url;
          }
        }
      }
    };

    this.btnEditChangeCover?.addEventListener('click', triggerCoverChange);
    this.editCoverContainer?.addEventListener('click', triggerCoverChange);

    this.btnEditTriggerDelete?.addEventListener('click', () => {
      if (this.targetPlaylistId && this.targetPlaylistId !== 'all' && this.targetPlaylistId !== 'favorites') {
        const p = this.playlists.find(x => String(x.id) === String(this.targetPlaylistId));
        this.modalEdit?.classList.add('hidden');
        this.showDeleteModal(this.targetPlaylistId, p ? p.name : '');
      }
    });

    // Rename Playlist Modal
    this.btnCancelRename?.addEventListener('click', () => {
      this.modalRename?.classList.add('hidden');
    });

    this.btnSaveRename?.addEventListener('click', async () => {
      const newName = this.inputRename?.value.trim();
      if (newName && this.targetPlaylistId) {
        await window.api.renamePlaylist(this.targetPlaylistId, newName);
        this.modalRename?.classList.add('hidden');
        await this.loadPlaylists();
        if (String(this.currentPlaylistId) === String(this.targetPlaylistId)) {
          this.openPlaylist(this.targetPlaylistId);
        }
      }
    });

    this.inputRename?.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') this.btnSaveRename?.click();
    });

    // Delete Playlist Modal
    this.btnCancelDelete?.addEventListener('click', () => {
      this.modalDelete?.classList.add('hidden');
    });

    this.btnConfirmDelete?.addEventListener('click', async () => {
      if (this.targetPlaylistId) {
        await window.api.deletePlaylist(this.targetPlaylistId);
        this.modalDelete?.classList.add('hidden');
        
        const deletedId = this.targetPlaylistId;
        await this.loadPlaylists();
        
        // If we just deleted the currently active playlist, switch to 'all'
        if (String(this.currentPlaylistId) === String(deletedId)) {
          window.store.setState({ view: 'playlist', playlistId: 'all' });
        }
      }
    });

    // Header Action Buttons
    this.btnHeaderRename?.addEventListener('click', () => {
      if (this.currentPlaylistId && this.currentPlaylistId !== 'all' && this.currentPlaylistId !== 'favorites') {
        const p = this.playlists.find(x => String(x.id) === String(this.currentPlaylistId));
        this.showRenameModal(this.currentPlaylistId, p ? p.name : '');
      }
    });

    this.btnHeaderCover?.addEventListener('click', () => {
      if (this.currentPlaylistId) {
        this.changeCover(this.currentPlaylistId);
      }
    });

    this.btnHeaderDelete?.addEventListener('click', () => {
      if (this.currentPlaylistId && this.currentPlaylistId !== 'all' && this.currentPlaylistId !== 'favorites') {
        const p = this.playlists.find(x => String(x.id) === String(this.currentPlaylistId));
        this.showDeleteModal(this.currentPlaylistId, p ? p.name : '');
      }
    });

    // Imports & Cover click
    this.btnImportFolder?.addEventListener('click', async () => {
      if (!this.currentPlaylistId) return;
      const folderPath = await window.api.selectMusicDir();
      if (folderPath) {
        const originalText = this.btnImportFolder.textContent;
        this.btnImportFolder.textContent = 'Scanning...';
        this.btnImportFolder.disabled = true;
        
        this.showImportProgressModal('Importing music folder...');
        this.startProgressPolling();

        try {
          const res = await window.api.importFolderToPlaylist(this.currentPlaylistId, folderPath);
          this.stopProgressPolling();
          
          const fill = document.getElementById('import-progress-fill');
          if (fill) fill.style.width = '100%';
          const percentEl = document.getElementById('import-progress-percent');
          if (percentEl) percentEl.textContent = '100%';
          await new Promise(r => setTimeout(r, 250));
          
          this.hideImportProgressModal();

          if (res && res.status === 'success') {
            if (window.uiController && window.uiController.showToast) {
              window.uiController.showToast(res.message || 'Successfully imported tracks!');
            }
          }
        } catch (err) {
          console.error("Error importing folder:", err);
          this.stopProgressPolling();
          this.hideImportProgressModal();
        } finally {
          this.btnImportFolder.textContent = originalText;
          this.btnImportFolder.disabled = false;
          if (window.libraryManager) {
            await window.libraryManager.reload();
          }
          await this.loadPlaylists();
        }
      }
    });

    this.btnImportFiles?.addEventListener('click', async () => {
      if (!this.currentPlaylistId) return;
      const filePaths = await window.api.selectMusicFiles();
      if (filePaths && filePaths.length > 0) {
        const originalText = this.btnImportFiles.textContent;
        this.btnImportFiles.textContent = 'Processing...';
        this.btnImportFiles.disabled = true;
        
        this.showImportProgressModal('Importing audio files...');
        this.startProgressPolling();

        try {
          const res = await window.api.importFilesToPlaylist(this.currentPlaylistId, filePaths);
          this.stopProgressPolling();
          
          const fill = document.getElementById('import-progress-fill');
          if (fill) fill.style.width = '100%';
          const percentEl = document.getElementById('import-progress-percent');
          if (percentEl) percentEl.textContent = '100%';
          await new Promise(r => setTimeout(r, 250));
          
          this.hideImportProgressModal();

          if (res && res.status === 'success') {
            if (window.uiController && window.uiController.showToast) {
              window.uiController.showToast(res.message || 'Successfully imported tracks!');
            }
          }
        } catch (err) {
          console.error("Error importing files:", err);
          this.stopProgressPolling();
          this.hideImportProgressModal();
        } finally {
          this.btnImportFiles.textContent = originalText;
          this.btnImportFiles.disabled = false;
          if (window.libraryManager) {
            await window.libraryManager.reload();
          }
          await this.loadPlaylists();
        }
      }
    });

    this.coverContainer?.addEventListener('click', () => {
      if (this.currentPlaylistId) {
        this.changeCover(this.currentPlaylistId);
      }
    });

    // Context Menu Event Handlers
    this.ctxRemoveFromPlaylist?.addEventListener('click', async () => {
      const menu = document.getElementById('context-menu');
      const trackPath = menu ? menu.dataset.trackPath : null;
      if (trackPath && this.currentPlaylistId) {
        await window.api.removeFromPlaylist(this.currentPlaylistId, trackPath);
        menu.classList.add('hidden');
        if (window.libraryManager) window.libraryManager.reload();
        this.loadPlaylists();
      }
    });

    // Sidebar Playlist Context Menu Handlers
    document.getElementById('ctx-pl-rename')?.addEventListener('click', () => {
      const plId = this.plContextMenu?.dataset.playlistId;
      const plName = this.plContextMenu?.dataset.playlistName;
      if (plId && plId !== 'all' && plId !== 'favorites') {
        this.showRenameModal(plId, plName);
      }
      this.plContextMenu?.classList.add('hidden');
    });

    document.getElementById('ctx-pl-cover')?.addEventListener('click', () => {
      const plId = this.plContextMenu?.dataset.playlistId;
      if (plId) {
        this.changeCover(plId);
      }
      this.plContextMenu?.classList.add('hidden');
    });

    document.getElementById('ctx-pl-delete')?.addEventListener('click', () => {
      const plId = this.plContextMenu?.dataset.playlistId;
      const plName = this.plContextMenu?.dataset.playlistName;
      if (plId && plId !== 'all' && plId !== 'favorites') {
        this.showDeleteModal(plId, plName);
      }
      this.plContextMenu?.classList.add('hidden');
    });

    // Hide sidebar playlist context menu on global click
    document.addEventListener('click', (e) => {
      if (this.plContextMenu && !this.plContextMenu.contains(e.target)) {
        this.plContextMenu.classList.add('hidden');
      }
    });

    this.ctxAddToPlaylist?.addEventListener('mouseenter', async (e) => {
      await this.showSubmenu(e);
    });
    this.ctxAddToPlaylist?.addEventListener('mouseleave', (e) => {
      setTimeout(() => {
        if (!this.submenu.matches(':hover')) {
          this.submenu.classList.add('hidden');
        }
      }, 100);
    });
    this.submenu?.addEventListener('mouseleave', () => {
      this.submenu.classList.add('hidden');
    });
  }

  showEditModal(playlistId) {
    this.targetPlaylistId = playlistId;
    const isSystem = (playlistId === 'all' || playlistId === 'favorites');
    
    let p = this.playlists.find(x => String(x.id) === String(playlistId));
    if (playlistId === 'all') {
      p = { name: 'All Songs', cover_url: this.systemCovers.all };
    } else if (playlistId === 'favorites') {
      p = { name: 'Favorite Songs', cover_url: this.systemCovers.favorites };
    }

    if (!p && !isSystem) return;
    if (!p) p = { name: 'Playlist', cover_url: null };

    const inputName = document.getElementById('input-edit-playlist-name');
    const previewImg = document.getElementById('edit-playlist-cover-preview');
    const nameSection = document.getElementById('edit-playlist-name-section');
    const deleteSection = document.getElementById('edit-playlist-delete-section');

    if (this.modalEdit) {
      if (inputName) inputName.value = p.name || '';
      
      if (previewImg) {
        if (playlistId === 'all') {
          previewImg.src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><path d='M9 18V5l12-2v13 M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z' stroke='%23ffffff' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' fill='none'/></svg>";
        } else if (playlistId === 'favorites') {
          previewImg.src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><path d='M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z' fill='%23ffffff'/></svg>";
        } else if (p.cover_url) {
          previewImg.src = p.cover_url;
        } else {
          previewImg.src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><rect width='100%' height='100%' fill='%23282828'/><path d='M9 18V5l12-2v13' stroke='%23888' stroke-width='2' fill='none'/><circle cx='6' cy='18' r='3' stroke='%23888' stroke-width='2' fill='none'/><circle cx='18' cy='16' r='3' stroke='%23888' stroke-width='2' fill='none'/></svg>";
        }
      }

      if (isSystem) {
        if (nameSection) nameSection.style.display = 'none';
        if (deleteSection) deleteSection.style.display = 'none';
      } else {
        if (nameSection) nameSection.style.display = 'flex';
        if (deleteSection) deleteSection.style.display = 'flex';
      }

      this.modalEdit.classList.remove('hidden');
      if (!isSystem && inputName) inputName.focus();
    }
  }

  showRenameModal(playlistId, currentName) {
    this.targetPlaylistId = playlistId;
    if (this.inputRename) this.inputRename.value = currentName || '';
    if (this.modalRename) {
      this.modalRename.classList.remove('hidden');
      if (this.inputRename) this.inputRename.focus();
    }
  }

  showDeleteModal(playlistId, playlistName) {
    this.targetPlaylistId = playlistId;
    const warning = document.getElementById('delete-playlist-warning-text');
    if (warning) {
      warning.textContent = `Are you sure you want to delete the playlist "${playlistName}"? This action cannot be undone.`;
    }
    if (this.modalDelete) {
      this.modalDelete.classList.remove('hidden');
    }
  }

  async changeCover(playlistId) {
    const imagePath = await window.api.selectCoverImage();
    if (imagePath) {
      const res = await window.api.updatePlaylistCover(playlistId, imagePath);
      if (res && res.status === 'success') {
        if (playlistId === 'all' || playlistId === 'favorites') {
          if (res.cover_url) {
            this.systemCovers[playlistId] = res.cover_url;
          }
        }
        await this.loadPlaylists();
        if (String(this.currentPlaylistId) === String(playlistId)) {
          this.openPlaylist(playlistId);
        }
      }
    }
  }

  showSidebarContextMenu(e, playlistId, playlistName, isSystem) {
    e.preventDefault();
    e.stopPropagation();
    if (!this.plContextMenu) return;

    this.plContextMenu.dataset.playlistId = playlistId;
    this.plContextMenu.dataset.playlistName = playlistName;

    const btnRename = document.getElementById('ctx-pl-rename');
    const btnDelete = document.getElementById('ctx-pl-delete');
    
    if (isSystem) {
      if (btnRename) btnRename.style.display = 'none';
      if (btnDelete) btnDelete.style.display = 'none';
    } else {
      if (btnRename) btnRename.style.display = 'flex';
      if (btnDelete) btnDelete.style.display = 'flex';
    }

    // Position menu at cursor
    let x = e.clientX;
    let y = e.clientY;

    this.plContextMenu.style.display = 'flex';
    const rect = this.plContextMenu.getBoundingClientRect();
    if (x + rect.width > window.innerWidth) x = window.innerWidth - rect.width - 8;
    if (y + rect.height > window.innerHeight) y = window.innerHeight - rect.height - 8;
    this.plContextMenu.style.display = '';

    this.plContextMenu.style.left = `${x}px`;
    this.plContextMenu.style.top = `${y}px`;
    this.plContextMenu.classList.remove('hidden');
  }

  async showSubmenu(e) {
    if (!this.submenu) return;
    
    this.playlists = await window.api.getPlaylists() || [];
    this.submenu.innerHTML = '';
    
    if (this.playlists.length === 0) {
      const item = document.createElement('div');
      item.className = 'context-menu-item';
      item.style.color = '#888';
      item.textContent = 'No playlists';
      this.submenu.appendChild(item);
    } else {
      this.playlists.forEach(p => {
        const item = document.createElement('div');
        item.className = 'context-menu-item';
        item.textContent = p.name;
        item.addEventListener('click', async () => {
          const menu = document.getElementById('context-menu');
          const trackPath = menu ? menu.dataset.trackPath : null;
          if (trackPath) {
            await window.api.addToPlaylist(p.id, trackPath);
            menu.classList.add('hidden');
            this.submenu.classList.add('hidden');
          }
        });
        this.submenu.appendChild(item);
      });
    }

    this.submenu.style.display = 'flex';
    const subRect = this.submenu.getBoundingClientRect();
    const subWidth = subRect.width || 180;
    const subHeight = subRect.height || 120;
    this.submenu.style.display = '';

    const rect = e.target.getBoundingClientRect();
    
    let leftPos = rect.right;
    if (leftPos + subWidth > window.innerWidth) {
      leftPos = rect.left - subWidth;
    }
    if (leftPos < 0) leftPos = 8;

    let topPos = rect.top;
    if (topPos + subHeight > window.innerHeight) {
      topPos = window.innerHeight - subHeight - 8;
    }

    this.submenu.style.left = `${leftPos}px`;
    this.submenu.style.top = `${topPos}px`;
    this.submenu.style.zIndex = '99999';
    this.submenu.classList.remove('hidden');
  }

  async loadPlaylists() {
    this.playlists = await window.api.getPlaylists() || [];
    this.renderSidebarList();
  }

  renderSidebarList() {
    if (!this.container) return;
    this.container.innerHTML = '';
    
    // Add All Songs
    const allItem = document.createElement('li');
    allItem.dataset.id = 'all';
    allItem.innerHTML = `<div class="icon-placeholder system-icon"><svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 24px; height: 24px; color: #ffffff;"><path d="M9 18V5l12-2v13 M6 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"></path></svg></div>
          <div class="library-list-text">
            <div class="library-list-title">All Songs</div>
            <div class="library-list-subtitle">All your local tracks</div>
          </div>`;
    allItem.addEventListener('click', () => {
      window.store.setState({ view: 'playlist', playlistId: 'all' });
      document.querySelectorAll('.library-list li').forEach(el => el.classList.remove('active'));
      allItem.classList.add('active');
    });
    allItem.addEventListener('contextmenu', (e) => {
      this.showSidebarContextMenu(e, 'all', 'All Songs', true);
    });
    this.container.appendChild(allItem);

    // Add Favorites
    const favItem = document.createElement('li');
    favItem.dataset.id = 'favorites';
    favItem.innerHTML = `<div class="icon-placeholder system-icon"><svg viewBox="0 0 24 24" fill="#ffffff" stroke="none" style="width: 24px; height: 24px; color: #ffffff;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></div>
          <div class="library-list-text">
            <div class="library-list-title">Favorite Songs</div>
            <div class="library-list-subtitle">Your favorite tracks</div>
          </div>`;
    favItem.addEventListener('click', () => {
      window.store.setState({ view: 'playlist', playlistId: 'favorites' });
      document.querySelectorAll('.library-list li').forEach(el => el.classList.remove('active'));
      favItem.classList.add('active');
    });
    favItem.addEventListener('contextmenu', (e) => {
      this.showSidebarContextMenu(e, 'favorites', 'Favorite Songs', true);
    });
    this.container.appendChild(favItem);

    // Custom Playlists
    this.playlists.forEach(p => {
      const li = document.createElement('li');
      li.dataset.id = p.id;
      
      const content = document.createElement('div');
      content.className = 'library-list-text';
      content.innerHTML = `<div class="library-list-title">${p.name}</div><div class="library-list-subtitle">${p.track_count || 0} tracks</div>`;
      
      const icon = document.createElement('div');
      icon.className = 'icon-placeholder';
      if (p.cover_url) {
        icon.innerHTML = `<img src="${p.cover_url}" style="width:100%;height:100%;object-fit:cover;border-radius:4px;">`;
      } else {
        icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 22px; height: 22px; color: #888;"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`;
      }
      li.appendChild(icon);
      li.appendChild(content);

      // Drag and Drop
      li.addEventListener('dragover', (e) => {
        e.preventDefault();
        li.classList.add('drag-over');
      });
      li.addEventListener('dragleave', () => li.classList.remove('drag-over'));
      li.addEventListener('drop', async (e) => {
        e.preventDefault();
        li.classList.remove('drag-over');
        const trackPath = e.dataTransfer.getData('text/plain');
        if (trackPath) {
          await window.api.addToPlaylist(p.id, trackPath);
          if (window.libraryManager) window.libraryManager.reload();
          this.loadPlaylists();
        }
      });

      li.addEventListener('click', () => {
        document.querySelectorAll('.library-list li').forEach(el => el.classList.remove('active'));
        li.classList.add('active');
        this.openPlaylist(p.id);
      });

      li.addEventListener('contextmenu', (e) => {
        this.showSidebarContextMenu(e, p.id, p.name, false);
      });

      this.container.appendChild(li);
    });
    
    // Select active based on store
    const state = window.store.getState();
    if (state.view === 'playlist') {
      const el = document.querySelector(`.library-list li[data-id="${state.playlistId}"]`);
      if (el) el.classList.add('active');
    }
    
    // Sync Home view
    if (window.homeManager && window.homeManager.loaded) {
      window.homeManager.loadPlaylists();
    }
  }

  async openPlaylist(id) {
    this.currentPlaylistId = id;
    window.store.setState({ view: 'playlist', playlistId: id });
  }

  showImportProgressModal(title) {
    const modal = document.getElementById('import-progress-modal');
    if (!modal) return;
    document.getElementById('import-progress-title').textContent = title || 'Importing tracks...';
    document.getElementById('import-progress-file').textContent = 'Preparing...';
    document.getElementById('import-progress-fill').style.width = '0%';
    document.getElementById('import-progress-status').textContent = '0 / 0';
    document.getElementById('import-progress-percent').textContent = '0%';
    modal.classList.remove('hidden');
  }

  hideImportProgressModal() {
    const modal = document.getElementById('import-progress-modal');
    if (modal) modal.classList.add('hidden');
  }

  startProgressPolling() {
    this.stopProgressPolling();
    this.progressInterval = setInterval(async () => {
      try {
        const progress = await window.api.getScanProgress();
        if (progress) {
          const fill = document.getElementById('import-progress-fill');
          const fileEl = document.getElementById('import-progress-file');
          const statusEl = document.getElementById('import-progress-status');
          const percentEl = document.getElementById('import-progress-percent');
          
          if (fileEl && progress.current_file) {
            const fileName = progress.current_file.split(/[/\\]/).pop();
            fileEl.textContent = fileName ? `Processing: ${fileName}` : progress.current_file;
          }

          if (progress.total > 0) {
            const percent = Math.min(100, Math.round((progress.scanned / progress.total) * 100));
            if (fill) fill.style.width = `${percent}%`;
            if (statusEl) statusEl.textContent = `${progress.scanned} / ${progress.total}`;
            if (percentEl) percentEl.textContent = `${percent}%`;
          } else if (progress.scanned > 0) {
            if (fill) fill.style.width = `50%`;
            if (statusEl) statusEl.textContent = `Scanned ${progress.scanned} files`;
            if (percentEl) percentEl.textContent = `...`;
          }
        }
      } catch (e) {
        console.error("Error fetching progress:", e);
      }
    }, 150);
  }

  stopProgressPolling() {
    if (this.progressInterval) {
      clearInterval(this.progressInterval);
      this.progressInterval = null;
    }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.playlistManager = new PlaylistManager();
});
