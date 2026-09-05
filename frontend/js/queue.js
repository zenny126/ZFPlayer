/**
 * QueueManager - Playback Queue Controller for ZFPlayer
 * Manages the slide-out glassmorphic Queue drawer, active track status,
 * priority user queue items, and upcoming playlist tracks.
 */
class QueueManager {
  constructor() {
    this.panel = document.getElementById('queue-panel');
    this.toggleBtn = document.getElementById('btn-queue-toggle');
    this.closeBtn = document.getElementById('btn-queue-close');
    this.clearBtn = document.getElementById('btn-queue-clear');
    this.badge = document.getElementById('queue-badge');

    this.nowPlayingSection = document.getElementById('queue-now-playing-section');
    this.nowPlayingList = document.getElementById('queue-now-playing-list');
    this.userSection = document.getElementById('queue-user-section');
    this.userList = document.getElementById('queue-user-list');
    this.upcomingSection = document.getElementById('queue-upcoming-section');
    this.upcomingList = document.getElementById('queue-upcoming-list');
    this.emptyState = document.getElementById('queue-empty-state');

    this.isOpen = false;
    this.cachedQueue = null;
    this._refreshTimer = null;
    this._reqToken = 0;
    this._lastRenderSignature = '';
  }

  init() {
    this.toggleBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggle();
    });

    this.closeBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.close();
    });

    this.clearBtn?.addEventListener('click', async (e) => {
      e.stopPropagation();
      await this.handleClearQueue();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });
  }

  toggle() {
    if (this.isOpen) {
      this.close();
      return;
    }
    this.open();
  }

  open() {
    this.isOpen = true;
    this.panel?.classList.remove('collapsed');
    this.panel?.classList.remove('hidden');
    this.toggleBtn?.classList.add('active');
    this.refreshQueue();
  }

  close() {
    this.isOpen = false;
    clearTimeout(this._refreshTimer);
    this.panel?.classList.add('collapsed');
    this.toggleBtn?.classList.remove('active');
  }

  async refreshQueue() {
    if (!window.api || !window.api.getQueue) return;
    const token = ++this._reqToken;
    try {
      const data = await window.api.getQueue(25);
      if (token !== this._reqToken) return;
      this.cachedQueue = data;
      this.render(data);
    } catch (err) {
      console.warn('Failed to refresh queue data:', err);
    }
  }

  onTrackChange() {
    if (!this.isOpen) return;
    clearTimeout(this._refreshTimer);
    this._refreshTimer = setTimeout(() => {
      this.refreshQueue();
    }, 100);
  }

  render(data) {
    if (!data) return;
    const current = data.current;
    const userQueue = data.user_queue || [];
    const upcoming = data.upcoming || [];

    const nowPath = current ? current.path : '';
    const uqSig = userQueue.map(t => t.path).join(',');
    const upSig = upcoming.map(t => t.path).join(',');
    const signature = `${nowPath}::${uqSig}::${upSig}`;
    if (this._lastRenderSignature === signature) return;
    this._lastRenderSignature = signature;

    const totalTracks = (current ? 1 : 0) + userQueue.length + upcoming.length;
    this._updateHeaderAndBadge(totalTracks, userQueue.length);

    if (totalTracks === 0) {
      this._showEmptyState();
      return;
    }

    this.emptyState?.classList.add('hidden');
    this._renderNowPlaying(current);
    this._renderUserQueue(userQueue);
    this._renderUpcoming(upcoming);
  }

  _updateHeaderAndBadge(totalTracks, userQueueCount) {
    if (this.badge) {
      this.badge.textContent = `${totalTracks} track${totalTracks === 1 ? '' : 's'}`;
    }
    if (this.clearBtn) {
      if (userQueueCount > 0) {
        this.clearBtn.classList.remove('hidden');
      } else {
        this.clearBtn.classList.add('hidden');
      }
    }
  }

  _showEmptyState() {
    this.nowPlayingSection?.classList.add('hidden');
    this.userSection?.classList.add('hidden');
    this.upcomingSection?.classList.add('hidden');
    this.emptyState?.classList.remove('hidden');
  }

  _renderNowPlaying(current) {
    if (!this.nowPlayingSection || !this.nowPlayingList) return;
    if (!current) {
      this.nowPlayingSection.classList.add('hidden');
      this.nowPlayingList.innerHTML = '';
      return;
    }

    this.nowPlayingSection.classList.remove('hidden');
    this.nowPlayingList.innerHTML = '';
    const itemEl = this._createTrackItem(current, { isPlaying: true, isUserQueue: false });
    this.nowPlayingList.appendChild(itemEl);
  }

  _renderUserQueue(userQueue) {
    if (!this.userSection || !this.userList) return;
    if (!userQueue || userQueue.length === 0) {
      this.userSection.classList.add('hidden');
      this.userList.innerHTML = '';
      return;
    }

    this.userSection.classList.remove('hidden');
    this.userList.innerHTML = '';
    const fragment = document.createDocumentFragment();
    userQueue.forEach((track) => {
      const itemEl = this._createTrackItem(track, { isPlaying: false, isUserQueue: true });
      fragment.appendChild(itemEl);
    });
    this.userList.appendChild(fragment);
  }

  _renderUpcoming(upcoming) {
    if (!this.upcomingSection || !this.upcomingList) return;
    if (!upcoming || upcoming.length === 0) {
      this.upcomingSection.classList.add('hidden');
      this.upcomingList.innerHTML = '';
      return;
    }

    this.upcomingSection.classList.remove('hidden');
    this.upcomingList.innerHTML = '';
    const fragment = document.createDocumentFragment();
    upcoming.forEach((track) => {
      const itemEl = this._createTrackItem(track, { isPlaying: false, isUserQueue: false });
      fragment.appendChild(itemEl);
    });
    this.upcomingList.appendChild(fragment);
  }

  _createTrackItem(track, options = {}) {
    const isPlaying = Boolean(options.isPlaying);
    const isUserQueue = Boolean(options.isUserQueue);

    const div = document.createElement('div');
    div.className = `queue-track-item ${isPlaying ? 'active' : ''}`;
    div.dataset.path = track.path || '';

    const coverSrc = track.cover_url || 'covers/default_cover.png';
    const durationStr = this._formatDuration(track.duration);

    div.innerHTML = `
      <img src="${coverSrc}" class="queue-track-thumb" alt="" loading="lazy" onerror="this.src='covers/default_cover.png'">
      <div class="queue-track-info">
        <span class="queue-track-title">${track.title || 'Unknown Track'}</span>
        <span class="queue-track-meta">${track.artist || 'Unknown Artist'}</span>
      </div>
      ${isPlaying ? '<div class="queue-soundwave"><span></span><span></span><span></span></div>' : ''}
      ${isUserQueue ? '<button class="btn-queue-remove" title="Remove from queue" aria-label="Remove"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon" style="width: 14px; height: 14px;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>' : ''}
      <span class="queue-track-duration">${durationStr}</span>
    `;

    div.addEventListener('click', (e) => {
      if (e.target.closest('.btn-queue-remove')) {
        e.stopPropagation();
        this.handleRemove(track.path);
        return;
      }
      this._playTrackDirectly(track);
    });

    return div;
  }

  _playTrackDirectly(track) {
    if (!track || !track.path) return;
    if (window.playerController && window.playerController.playTrack) {
      window.playerController.playTrack(track);
      setTimeout(() => this.refreshQueue(), 200);
      return;
    }
    if (window.api && window.api.play) {
      const state = window.store ? window.store.getState() : {};
      window.api.play(track.path, state.playlistId || null);
      setTimeout(() => this.refreshQueue(), 200);
    }
  }

  async handleRemove(path) {
    if (!path || !window.api || !window.api.removeFromQueue) return;
    try {
      await window.api.removeFromQueue(path);
      if (window.uiController && window.uiController.showToast) {
        window.uiController.showToast('Removed from queue');
      }
      await this.refreshQueue();
    } catch (err) {
      console.warn('Failed to remove track from queue:', err);
    }
  }

  async handleClearQueue() {
    if (!window.api || !window.api.clearQueue) return;
    try {
      await window.api.clearQueue();
      if (window.uiController && window.uiController.showToast) {
        window.uiController.showToast('Queue cleared');
      }
      await this.refreshQueue();
    } catch (err) {
      console.warn('Failed to clear queue:', err);
    }
  }

  _formatDuration(seconds) {
    if (!seconds || isNaN(seconds) || seconds <= 0) return '0:00';
    const totalSec = Math.floor(seconds);
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  }
}

window.QueueManager = QueueManager;
