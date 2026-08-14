class PlaybackTicker {
  constructor(onTick) {
    this.onTick = onTick;
    this.isPlaying = false;
    this.position = 0;
    this.duration = 0;
    this.lastSyncTime = 0;
    this.lastSyncPosition = 0;
    this.rafId = null;
  }
  
  start() {
    this.isPlaying = true;
    this.lastSyncTime = performance.now();
    this.lastSyncPosition = this.position;
    if (!this.rafId) {
      this.tick();
    }
  }
  
  stop() {
    this.isPlaying = false;
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }
  
  tick() {
    if (!this.isPlaying) {
      this.rafId = null;
      return;
    }
    
    const now = performance.now();
    const elapsed = (now - this.lastSyncTime) / 1000;
    this.position = this.lastSyncPosition + elapsed;
    
    if (this.position > this.duration) {
      this.position = this.duration;
    }
    
    this.onTick(this.position, this.duration);
    
    this.rafId = requestAnimationFrame(() => this.tick());
  }
  
  sync(position, duration, isPlaying) {
    this.position = position;
    this.duration = duration;
    this.isPlaying = isPlaying;
    this.lastSyncTime = performance.now();
    this.lastSyncPosition = position;
    
    if (isPlaying) {
      this.start();
    } else {
      this.stop();
      this.onTick(this.position, this.duration);
    }
  }
}

class PlayerController {
  constructor() {
    this.seekBar = document.getElementById('seek-bar');
    this.timeCurrent = document.getElementById('seek-time-current');
    this.timeTotal = document.getElementById('seek-time-total');
    this.isDraggingSeek = false;
    
    this.ticker = new PlaybackTicker((pos, dur) => this.updateSeekUI(pos, dur));
    this.initBindings();
    this.startSyncLoop();
  }

  initBindings() {
    document.getElementById('btn-play-pause').addEventListener('click', () => this.togglePlay());
    document.getElementById('btn-play-pause-lyrics')?.addEventListener('click', () => this.togglePlay());
    document.getElementById('btn-prev').addEventListener('click', () => this.prev());
    document.getElementById('btn-prev-lyrics')?.addEventListener('click', () => this.prev());
    document.getElementById('btn-next').addEventListener('click', () => this.next());
    document.getElementById('btn-next-lyrics')?.addEventListener('click', () => this.next());
    
    const volBar = document.getElementById('volume-bar');
    const volBarLyrics = document.getElementById('lyrics-volume-bar');
    this.updateVolUI = (val) => {
      const num = parseFloat(val);
      if (volBar) {
        volBar.value = num;
        volBar.style.setProperty('--progress', `${num}%`);
      }
      if (volBarLyrics) {
        volBarLyrics.value = num;
        volBarLyrics.style.setProperty('--progress', `${num}%`);
      }
    };
    if (volBar) {
      volBar.addEventListener('input', (e) => {
        this.setVolume(e.target.value);
        this.updateVolUI(e.target.value);
      });
    }
    if (volBarLyrics) {
      volBarLyrics.addEventListener('input', (e) => {
        this.setVolume(e.target.value);
        this.updateVolUI(e.target.value);
      });
    }
    if (volBar) this.updateVolUI(volBar.value);

    // Setup Windows SMTC / Browser MediaSession Action Handlers
    if ('mediaSession' in navigator) {
      try {
        navigator.mediaSession.setActionHandler('play', () => this.togglePlay());
        navigator.mediaSession.setActionHandler('pause', () => this.togglePlay());
        navigator.mediaSession.setActionHandler('previoustrack', () => this.prev());
        navigator.mediaSession.setActionHandler('nexttrack', () => this.next());
        navigator.mediaSession.setActionHandler('seekto', (details) => {
          if (details.seekTime !== undefined) {
            this.seek(details.seekTime);
          }
        });
      } catch (e) {
        console.warn('MediaSession action handler error:', e);
      }
    }
    
    // Real-time responsive seeking (sync both seekbars, time labels, lyrics visually while dragging, seek audio on release)
    const updateAllSeekUI = (val) => {
      const numVal = parseFloat(val);
      const mainBar = this.seekBar;
      const lyricsBar = document.getElementById('lyrics-seek-bar');
      const mainTime = this.timeCurrent;
      const lyricsTime = document.getElementById('lyrics-seek-time-current');

      if (mainBar) mainBar.value = numVal;
      if (lyricsBar) lyricsBar.value = numVal;

      const formattedTime = this.formatTime(numVal);
      if (mainTime) mainTime.textContent = formattedTime;
      if (lyricsTime) lyricsTime.textContent = formattedTime;

      const max = (mainBar && mainBar.max) ? parseFloat(mainBar.max) : (lyricsBar && lyricsBar.max ? parseFloat(lyricsBar.max) : 0);
      const pct = max > 0 ? (numVal / max) * 100 : 0;

      if (mainBar) mainBar.style.setProperty('--progress', `${pct}%`);
      if (lyricsBar) lyricsBar.style.setProperty('--progress', `${pct}%`);

      if (window.lyricsRenderer) window.lyricsRenderer.update(numVal);
    };

    const bindSeek = (bar) => {
      if (!bar) return;
      
      const startDrag = () => {
        this.isDraggingSeek = true;
      };

      const handleInput = (e) => {
        this.isDraggingSeek = true;
        const val = parseFloat(e.target.value);
        updateAllSeekUI(val); // Only update visuals smoothly during drag
      };

      const handleEnd = (e) => {
        const val = parseFloat(e.target.value);
        updateAllSeekUI(val);
        
        // Release UI immediately so it resumes ticking forward without waiting for IPC
        this.isDraggingSeek = false; 
        
        const storeState = window.store.getState();
        const duration = storeState.currentTrack ? storeState.currentTrack.duration : 0;
        this.ticker.sync(val, duration, storeState.isPlaying);

        // Seek audio in background
        this.seek(val);
      };

      bar.addEventListener('mousedown', startDrag);
      bar.addEventListener('touchstart', startDrag, { passive: true });
      bar.addEventListener('input', handleInput);
      bar.addEventListener('change', handleEnd);
    };

    bindSeek(this.seekBar);
    bindSeek(document.getElementById('lyrics-seek-bar'));

    document.getElementById('btn-shuffle').addEventListener('click', () => this.toggleShuffle());
    document.getElementById('btn-shuffle-lyrics')?.addEventListener('click', () => this.toggleShuffle());
    document.getElementById('btn-repeat').addEventListener('click', () => this.toggleRepeat());
    document.getElementById('btn-repeat-lyrics')?.addEventListener('click', () => this.toggleRepeat());

    // Player bar like button
    const playerLikeBtn = document.getElementById('player-like-btn');
    const lyricsLikeBtn = document.getElementById('lyrics-like-btn');
    
    const handleLikeClick = async (btnElement) => {
      if (!btnElement) return;
      const track = window.store.getState().currentTrack;
      if (!track) return;
      const res = await window.api.toggleLike(track.path);
      if (res && res.status === 'success') {
        // Create a NEW object reference so the store detects a change and fires syncUI
        const updatedTrack = { ...track, is_liked: res.is_liked };
        window.store.setState({ currentTrack: updatedTrack });
      }
    };

    if (playerLikeBtn) playerLikeBtn.addEventListener('click', () => handleLikeClick(playerLikeBtn));
    if (lyricsLikeBtn) lyricsLikeBtn.addEventListener('click', () => handleLikeClick(lyricsLikeBtn));

    const syncUI = (state) => {
      const btn = document.getElementById('btn-play-pause');
      const btnLyrics = document.getElementById('btn-play-pause-lyrics');
      const playIcon = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
      const pauseIcon = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>`;
      if (btn) btn.innerHTML = state.isPlaying ? pauseIcon : playIcon;
      if (btnLyrics) btnLyrics.innerHTML = state.isPlaying ? pauseIcon : playIcon;

      // Update Shuffle UI
      const shuffleActive = !!state.shuffle;
      const sBtn = document.getElementById('btn-shuffle');
      const sBtnLyrics = document.getElementById('btn-shuffle-lyrics');
      if (sBtn) sBtn.classList.toggle('active', shuffleActive);
      if (sBtnLyrics) sBtnLyrics.classList.toggle('active', shuffleActive);

      // Update Repeat UI
      const repeatMode = state.repeat || 'off';
      const rBtn = document.getElementById('btn-repeat');
      const rBtnLyrics = document.getElementById('btn-repeat-lyrics');
      if (rBtn) rBtn.classList.toggle('active', repeatMode !== 'off');
      if (rBtnLyrics) rBtnLyrics.classList.toggle('active', repeatMode !== 'off');

      const repeatIconAll = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>`;
      const repeatIconOne = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path><path d="M11 10h1v4"></path></svg>`;
      const repeatIcon = repeatMode === 'one' ? repeatIconOne : repeatIconAll;
      if (rBtn) rBtn.innerHTML = repeatIcon;
      if (rBtnLyrics) rBtnLyrics.innerHTML = repeatIcon;
      
      if (state.currentTrack) {
        document.getElementById('player-track-name').textContent = state.currentTrack.title || 'Unknown';
        document.getElementById('player-track-artist').textContent = state.currentTrack.artist || 'Unknown';
        if (this.timeTotal) this.timeTotal.textContent = this.formatTime(state.currentTrack.duration);
        const lTimeTotal = document.getElementById('lyrics-seek-time-total');
        if (lTimeTotal) lTimeTotal.textContent = this.formatTime(state.currentTrack.duration);
        if (this.seekBar) this.seekBar.max = state.currentTrack.duration || 100;
        const lSeekBar = document.getElementById('lyrics-seek-bar');
        if (lSeekBar) lSeekBar.max = state.currentTrack.duration || 100;
        let imageUrl = 'none';
        if (state.currentTrack.cover_hash) {
           const url = `/api/covers/${state.currentTrack.cover_hash}.jpg`;
           document.getElementById('player-cover').src = url;
           imageUrl = `url('${url}')`;
           document.getElementById('app').style.setProperty('--global-cover', imageUrl);
        } else {
           document.getElementById('player-cover').src = "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' width='200' height='200' xmlns='http://www.w3.org/2000/svg'><rect width='100%' height='100%' fill='%23282828'/><path d='M9 18V5l12-2v13' stroke='%23888' stroke-width='2' fill='none'/><circle cx='6' cy='18' r='3' stroke='%23888' stroke-width='2' fill='none'/><circle cx='18' cy='16' r='3' stroke='%23888' stroke-width='2' fill='none'/></svg>";
           document.getElementById('app').style.setProperty('--global-cover', 'none');
        }
        
        if (window.extractDominantColors && this.lastCoverUrl !== imageUrl) {
            this.lastCoverUrl = imageUrl;
            window.extractDominantColors(imageUrl, (colors) => {
              if (window.updateFluidColors) {
                window.updateFluidColors(colors);
              }
            });
         }
        // Update like button in player bar and lyrics view
        const likeBtn = document.getElementById('player-like-btn');
        const lyricsLikeBtnSync = document.getElementById('lyrics-like-btn');
        const likeIconEmpty = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
        const likeIconFilled = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
        
        if (likeBtn) {
          likeBtn.innerHTML = state.currentTrack.is_liked ? likeIconFilled : likeIconEmpty;
          likeBtn.classList.toggle('liked', !!state.currentTrack.is_liked);
        }
        if (lyricsLikeBtnSync) {
          lyricsLikeBtnSync.innerHTML = state.currentTrack.is_liked ? likeIconFilled : likeIconEmpty;
          lyricsLikeBtnSync.classList.toggle('liked', !!state.currentTrack.is_liked);
        }
      }

      // Sync Windows SMTC / MediaSession Metadata & Playback state
      if ('mediaSession' in navigator) {
        try {
          if (state.currentTrack) {
            const coverUrl = state.currentTrack.cover_hash
              ? `${window.location.origin}/api/covers/${state.currentTrack.cover_hash}.jpg`
              : '';
            navigator.mediaSession.metadata = new MediaMetadata({
              title: state.currentTrack.title || 'Unknown Title',
              artist: state.currentTrack.artist || 'Unknown Artist',
              album: state.currentTrack.album || 'ZennyFLAC Player',
              artwork: coverUrl ? [{ src: coverUrl, sizes: '512x512', type: 'image/jpeg' }] : []
            });
          }
          navigator.mediaSession.playbackState = state.isPlaying ? 'playing' : 'paused';
        } catch (e) {
          console.warn('MediaSession sync error:', e);
        }
      }
    };

    window.store.subscribe(['isPlaying', 'currentTrack', 'shuffle', 'repeat'], syncUI);
    // Execute immediately once to align UI with initial store state
    syncUI(window.store.getState());
  }

  async playTrack(track, playlistId = null) {
    if (!track) return;
    const pId = playlistId || window.store.getState().playlistId || 'all';
    await window.api.play(track.path, pId);
    window.store.setState({ currentTrack: track, isPlaying: true, playlistId: pId });
    this.ticker.sync(0, track.duration, true);
  }

  async togglePlay() {
    const state = window.store.getState();
    if (!state.currentTrack) return;
    
    if (state.isPlaying) {
      await window.api.pause();
      window.store.setState({ isPlaying: false });
      this.ticker.stop();
    } else {
      await window.api.resume();
      window.store.setState({ isPlaying: true });
      this.ticker.start();
    }
  }

  async seek(seconds) {
    const targetPos = parseFloat(seconds) || 0;
    const storeState = window.store.getState();
    const duration = storeState.currentTrack ? storeState.currentTrack.duration : 0;
    
    this.lastSeekTime = Date.now();
    
    // Optimistic UI Update: Sync ticker and UI elements instantly without waiting for IPC response
    this.ticker.sync(targetPos, duration, storeState.isPlaying);
    this.updateSeekUI(targetPos, duration);
    
    await window.api.seek(targetPos);
  }

  async setVolume(level) {
    const numLevel = Math.max(0, Math.min(100, Math.round(level)));
    await window.api.setVolume(numLevel / 100);
    window.store.setState({ volume: numLevel });
    if (this.updateVolUI) this.updateVolUI(numLevel);
  }

  async adjustVolume(delta) {
    const current = window.store.getState().volume !== undefined ? window.store.getState().volume : 80;
    const target = Math.max(0, Math.min(100, current + delta));
    await this.setVolume(target);
  }

  async toggleMute() {
    const current = window.store.getState().volume !== undefined ? window.store.getState().volume : 80;
    if (current > 0) {
      this._unmuteVolume = current;
      await this.setVolume(0);
    } else {
      await this.setVolume(this._unmuteVolume || 80);
    }
  }

  async next() {
    const state = await window.api.nextTrack();
    if (state && state.track) {
      window.store.setState({ currentTrack: state.track, isPlaying: true });
      this.ticker.sync(0, state.track.duration, true);
    }
  }

  async prev() {
    const state = await window.api.prevTrack();
    if (state && state.track) {
      window.store.setState({ currentTrack: state.track, isPlaying: true });
      this.ticker.sync(0, state.track.duration, true);
    }
  }
  
  async toggleShuffle() {
    const state = window.store.getState();
    const newShuffle = !state.shuffle;
    window.store.setState({ shuffle: newShuffle });
    await window.api.setConfig('shuffle', newShuffle);
  }
  
  async toggleRepeat() {
    const modes = ['off', 'all', 'one'];
    const current = window.store.getState().repeat || 'off';
    const nextMode = modes[(modes.indexOf(current) + 1) % modes.length];
    window.store.setState({ repeat: nextMode });
    await window.api.setConfig('repeat', nextMode);
  }

  updateSeekUI(pos, dur) {
    if (this.isDraggingSeek) return;
    if (this.seekBar) this.seekBar.value = pos;
    const lSeekBar = document.getElementById('lyrics-seek-bar');
    if (lSeekBar) lSeekBar.value = pos;
    if (this.timeCurrent) this.timeCurrent.textContent = this.formatTime(pos);
    const lTimeCurrent = document.getElementById('lyrics-seek-time-current');
    if (lTimeCurrent) lTimeCurrent.textContent = this.formatTime(pos);
    
    const pct = dur > 0 ? (pos / dur) * 100 : 0;
    if (this.seekBar) this.seekBar.style.setProperty('--progress', `${pct}%`);
    if (lSeekBar) lSeekBar.style.setProperty('--progress', `${pct}%`);
    
    if (window.lyricsRenderer) window.lyricsRenderer.update(pos);
  }

  formatTime(sec) {
    if (!sec || isNaN(sec)) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  }

  startSyncLoop() {
    this._isPolling = false;
    
    const poll = async () => {
      if (this._isPolling) return;
      this._isPolling = true;

      try {
        // Skip background polling override if user seeked recently (within last 1500ms)
        if (!this.lastSeekTime || Date.now() - this.lastSeekTime >= 1500) {
          const state = await window.api.getPlayerState();
          if (state) {
            const storeState = window.store.getState();
            const pos = state.position_seconds !== undefined ? state.position_seconds : state.position;
            
            // Auto-next or external track change
            if (state.track && (!storeState.currentTrack || state.track.path !== storeState.currentTrack.path)) {
              window.store.setState({ currentTrack: state.track, isPlaying: state.is_playing });
              this.ticker.sync(pos, state.duration, state.is_playing);
            } else {
              if (!this.isDraggingSeek && Math.abs(this.ticker.position - pos) > 2) {
                 this.ticker.sync(pos, state.duration, state.is_playing);
              }
              if (state.is_playing !== storeState.isPlaying) {
                window.store.setState({ isPlaying: state.is_playing });
                this.ticker.sync(pos, state.duration, state.is_playing);
              }
            }
          }
        }
      } catch (e) {
        console.warn("Polling error:", e);
      } finally {
        this._isPolling = false;
        setTimeout(poll, 500);
      }
    };

    setTimeout(poll, 500);
  }
}

window.PlayerController = PlayerController;
