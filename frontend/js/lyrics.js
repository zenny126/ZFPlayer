class LyricsRenderer {
  constructor() {
    this.container = document.getElementById('lyrics-content');
    this.overlay = document.getElementById('lyrics-overlay');
    this.overlayContainer = this.overlay.querySelector('.lyrics-overlay-container');
    this.toggleLyricsBtn = document.getElementById('btn-toggle-lyrics-view');
    this.lyrics = [];
    this.activeIndex = -1;
    this.userDisabledLyrics = false;
    this.noLyricsTimer = null;
    this.isUserScrolling = false;
    this.userScrollResumeTimer = null;
    this.currentScrollY = 0;
    this.targetScrollY = 0;
    this.rafId = null;
    this.cinemaIdleTimer = null;
    this.lastMouseX = -1;
    this.lastMouseY = -1;
    this.bindEvents();
  }

  bindEvents() {
    document.getElementById('btn-lyrics-toggle').addEventListener('click', () => this.toggle());
    document.getElementById('btn-close-lyrics')?.addEventListener('click', () => this.hide());
    this.toggleLyricsBtn?.addEventListener('click', () => this.toggleLyricsView());
    
    // Interactive Manual Scroll on Lyrics Container
    const lyricsContainer = this.overlay.querySelector('.lyrics-container');
    lyricsContainer?.addEventListener('wheel', (e) => this.handleWheel(e), { passive: false });
    
    // Cinema Idle Activity Tracking: Filter real mouse movements vs synthetic scroll events
    window.addEventListener('mousemove', (e) => {
      if (Math.abs(e.clientX - this.lastMouseX) >= 2 || Math.abs(e.clientY - this.lastMouseY) >= 2) {
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
        this.resetCinemaIdleTimer();
      }
    }, { passive: true });

    // Mouse/Touch triggers Cinema Idle wake-up (Keyboard operates purely in background without waking UI)
    ['mousedown', 'wheel', 'touchstart'].forEach(evt => {
      window.addEventListener(evt, () => this.resetCinemaIdleTimer(), { passive: true });
    });
    window.addEventListener('resize', () => this.resetCinemaIdleTimer(), { passive: true });

    if (window.store) {
      window.store.subscribe('currentTrack', () => {
        if (!this.overlay.classList.contains('hidden')) {
          this.show(false);
        }
      });
    }
  }

  updateCinemaIdleOffset() {
    const cover = document.getElementById('lyrics-cover');
    const meta = this.overlay.querySelector('.lyrics-metadata-row');
    const container = this.overlay.querySelector('.lyrics-overlay-container');
    if (cover && meta && container) {
      const clusterHeight = cover.offsetHeight + meta.offsetHeight + 20; // 20px gap
      const containerHeight = container.clientHeight;
      const targetTop = (containerHeight - clusterHeight) / 2;
      const offset = Math.max(0, targetTop);
      this.overlay.style.setProperty('--cinema-idle-offset', `${offset.toFixed(1)}px`);
    }
  }

  resetCinemaIdleTimer() {
    if (this.overlay.classList.contains('hidden')) return;

    this.overlay.classList.remove('cinema-idle');
    if (this.cinemaIdleTimer) {
      clearTimeout(this.cinemaIdleTimer);
      this.cinemaIdleTimer = null;
    }

    // Check if in Fullscreen or Maximized screen
    const isFullscreen = (window.innerHeight >= window.screen.height - 40) ||
                         (document.fullscreenElement != null) ||
                         (window.isFullscreen === true);

    if (isFullscreen) {
      this.updateCinemaIdleOffset();

      this.cinemaIdleTimer = setTimeout(() => {
        if (!this.overlay.classList.contains('hidden')) {
          this.overlay.classList.add('cinema-idle');
        }
      }, 3500);
    }
  }

  startScrollPhysicsLoop() {
    if (this.rafId) return;
    const updatePhysics = () => {
      if (!this.container) return;
      const diff = this.targetScrollY - this.currentScrollY;
      
      if (Math.abs(diff) > 0.1) {
        // Exponential spring lerp (60fps/120fps butter smooth inertia)
        this.currentScrollY += diff * 0.14;
        this.container.style.setProperty('--scroll-y', `${this.currentScrollY.toFixed(2)}px`);
        this.rafId = requestAnimationFrame(updatePhysics);
      } else {
        this.currentScrollY = this.targetScrollY;
        this.container.style.setProperty('--scroll-y', `${this.currentScrollY.toFixed(2)}px`);
        this.rafId = null;
      }
    };
    this.rafId = requestAnimationFrame(updatePhysics);
  }

  stopScrollPhysicsLoop() {
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  handleWheel(e) {
    if (!this.lyrics.length || this.overlay.classList.contains('hidden') || this.lyrics.length <= 1) return;
    e.preventDefault();

    this.isUserScrolling = true;
    if (this.userScrollResumeTimer) clearTimeout(this.userScrollResumeTimer);

    // Normalize wheel delta across mice & touchpads
    let delta = e.deltaY;
    if (e.deltaMode === 1) delta *= 30;
    else if (e.deltaMode === 2) delta *= 300;
    delta *= 0.9; // Sweet spot sensitivity

    this.targetScrollY -= delta;

    // Boundary protection (clamping)
    const firstLine = this.container.firstElementChild;
    const lastLine = this.container.lastElementChild;
    if (firstLine && lastLine) {
      const containerHeight = this.container.parentElement.clientHeight;
      const targetAnchor = containerHeight * 0.40;
      
      const maxScroll = targetAnchor - firstLine.offsetTop - (firstLine.clientHeight / 2);
      const minScroll = targetAnchor - lastLine.offsetTop - (lastLine.clientHeight / 2);
      
      const overscroll = 80;
      this.targetScrollY = Math.max(minScroll - overscroll, Math.min(maxScroll + overscroll, this.targetScrollY));
    }

    this.container.classList.add('manual-scrolling');
    this.startScrollPhysicsLoop();

    // Auto-resume after 3.5s of no scroll interaction
    this.userScrollResumeTimer = setTimeout(() => {
      this.isUserScrolling = false;
      this.stopScrollPhysicsLoop();
      this.container?.classList.remove('manual-scrolling');
      if (this.activeIndex >= 0) {
        this.scrollToLine(this.activeIndex, false);
      }
    }, 3500);
  }

  toggleLyricsView() {
    this.userDisabledLyrics = !this.userDisabledLyrics;
    if (this.noLyricsTimer) {
      clearTimeout(this.noLyricsTimer);
      this.noLyricsTimer = null;
    }
    this.applyLyricsViewState(!this.userDisabledLyrics);
  }

  applyLyricsViewState(showLyrics) {
    if (showLyrics) {
      if (this.container && this.container.children.length > 0) {
        const baseIdx = Math.max(0, this.activeIndex >= 0 ? this.activeIndex - 1 : 0);
        Array.from(this.container.children).forEach((child, idx) => {
          const dist = Math.max(0, idx - baseIdx);
          child.style.setProperty('--stagger-delay', `${Math.min(dist * 45, 550)}ms`);
        });
        this.container.classList.remove('stagger-in');
        void this.container.offsetWidth; // Trigger reflow to restart animation cleanly
        this.container.classList.add('stagger-in');
        if (this._staggerTimer) clearTimeout(this._staggerTimer);
        this._staggerTimer = setTimeout(() => {
          this.container?.classList.remove('stagger-in');
        }, 1400);
      }
      this.overlayContainer?.classList.remove('center-mode');
      this.toggleLyricsBtn?.classList.add('active');
      if (this.toggleLyricsBtn) this.toggleLyricsBtn.title = 'Hide Lyrics';
    } else {
      this.overlayContainer?.classList.add('center-mode');
      this.toggleLyricsBtn?.classList.remove('active');
      if (this.toggleLyricsBtn) this.toggleLyricsBtn.title = 'Show Lyrics';
      this.container?.classList.remove('stagger-in');
    }
  }

  toggle() {
    if (this.overlay.classList.contains('hidden')) {
      this.show(true);
    } else {
      this.hide();
    }
  }

  async show(isUserAction = true) {
    this.overlay.classList.remove('hidden');
    
    if (isUserAction) {
      this.userDisabledLyrics = false;
      this.resetCinemaIdleTimer();
      // Always open with full lyrics view on user open
      this.applyLyricsViewState(true);
    } else {
      // Auto track change in background while overlay is open:
      // Update centering offset dynamically without disturbing cinema-idle state
      this.updateCinemaIdleOffset();
      if (!this.overlay.classList.contains('cinema-idle')) {
        this.resetCinemaIdleTimer();
      }
    }

    if (this.noLyricsTimer) {
      clearTimeout(this.noLyricsTimer);
      this.noLyricsTimer = null;
    }

    // Hide main app components to reveal global WebGL background, without hiding lyrics-overlay which is inside #app
    document.getElementById('top-bar').style.opacity = '0';
    document.getElementById('top-bar').style.pointerEvents = 'none';
    document.querySelector('.workspace').style.opacity = '0';
    document.querySelector('.workspace').style.pointerEvents = 'none';
    document.getElementById('player-bar').style.opacity = '0';
    document.getElementById('player-bar').style.pointerEvents = 'none';
    
    const track = window.store.getState().currentTrack;
    const defaultCover = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI1NiIgaGVpZ2h0PSI1NiI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0iIzMzMyIvPjwvc3ZnPg==';
    
    if (track) {
      this._currentTrackPath = track.path;
      this._fetchToken = (this._fetchToken || 0) + 1;
      const currentToken = this._fetchToken;

      document.getElementById('lyrics-track-name').textContent = track.title || 'Unknown';
      document.getElementById('lyrics-track-artist').textContent = track.artist || 'Unknown';
      
      if (track.cover_hash) {
         const coverUrl = `/api/covers/${track.cover_hash}.jpg`;
         document.getElementById('lyrics-cover').src = coverUrl;
         this.overlay.style.setProperty('--cover-url', `url('${coverUrl}')`);
      } else {
         document.getElementById('lyrics-cover').src = defaultCover;
         this.overlay.style.setProperty('--cover-url', 'none');
      }

      this.setLyrics([{ time: 0, text: "Loading lyrics..." }]);
      
      const lrcData = await window.api.getLyrics(track.artist, track.title, track.album, track.duration, track.path);
      
      // Prevent race conditions: Ensure response belongs to the current request and active track
      if (this._fetchToken !== currentToken || this._currentTrackPath !== track.path) {
        return;
      }

      if (lrcData && lrcData.synced_lyrics) {
        const parsed = this.parseLRC(lrcData.synced_lyrics);
        if (parsed && parsed.length > 0) {
          this.setLyrics(parsed);
          if (!this.userDisabledLyrics) {
            this.applyLyricsViewState(true);
          }
          if (window.playerController && window.playerController.ticker) {
            this.update(window.playerController.ticker.position || 0);
          }
        } else {
          this.handleNoLyrics();
        }
      } else {
        this.handleNoLyrics();
      }
    } else {
      document.getElementById('lyrics-track-name').textContent = 'No Track';
      document.getElementById('lyrics-track-artist').textContent = '';
      document.getElementById('lyrics-cover').src = defaultCover;
      this.overlay.style.setProperty('--cover-url', 'none');
      this.setLyrics([{ time: 0, text: "Play a song to see lyrics." }]);
    }
  }

  handleNoLyrics() {
    this.setLyrics([{ time: 0, text: "No synced lyrics available." }]);
    if (this.noLyricsTimer) clearTimeout(this.noLyricsTimer);
    
    // Display message for 2.5s, then gracefully transition to center mode
    this.noLyricsTimer = setTimeout(() => {
      if (!this.overlay.classList.contains('hidden') && !this.userDisabledLyrics) {
        this.applyLyricsViewState(false);
      }
    }, 2500);
  }

  hide() {
    this.overlay.classList.add('hidden');
    if (this.noLyricsTimer) {
      clearTimeout(this.noLyricsTimer);
      this.noLyricsTimer = null;
    }
    if (this.userScrollResumeTimer) {
      clearTimeout(this.userScrollResumeTimer);
      this.userScrollResumeTimer = null;
    }
    if (this.cinemaIdleTimer) {
      clearTimeout(this.cinemaIdleTimer);
      this.cinemaIdleTimer = null;
    }
    this.overlay.classList.remove('cinema-idle');
    this.stopScrollPhysicsLoop();
    this.isUserScrolling = false;
    this.container?.classList.remove('manual-scrolling');

    // Restore main app components
    document.getElementById('top-bar').style.opacity = '1';
    document.getElementById('top-bar').style.pointerEvents = 'auto';
    document.querySelector('.workspace').style.opacity = '1';
    document.querySelector('.workspace').style.pointerEvents = 'auto';
    document.getElementById('player-bar').style.opacity = '1';
    document.getElementById('player-bar').style.pointerEvents = 'auto';
  }

  parseLRC(lrcText) {
    if (!lrcText) return [];
    const lines = lrcText.split(/\r?\n/);
    const result = [];
    const timeRegex = /\[(\d{1,2}):(\d{2})(?:[.:](\d{2,3}))?\]/g;
    const offsetRegex = /^\[offset:\s*([+-]?\d+)\s*\]/i;
    const karaokeTagRegex = /<\d{1,2}:\d{2}(?:[.:]\d{2,3})?>/g;
    
    let globalOffsetSec = 0;

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;

      // Parse global [offset: +/-ms] tag
      const offsetMatch = line.match(offsetRegex);
      if (offsetMatch) {
        const ms = parseInt(offsetMatch[1], 10);
        if (!isNaN(ms)) {
          globalOffsetSec = ms / 1000.0;
        }
        continue;
      }

      // Ignore ID tags like [ar:Artist], [ti:Title], [al:Album], [by:Creator], etc.
      if (/^\[(ar|ti|al|by|length|re|ve|hash):/i.test(line)) {
        continue;
      }

      const timestamps = [];
      let match;
      timeRegex.lastIndex = 0;
      while ((match = timeRegex.exec(line)) !== null) {
        const m = parseInt(match[1], 10);
        const s = parseInt(match[2], 10);
        let ms = 0;
        if (match[3]) {
          const msStr = match[3];
          ms = msStr.length === 2 ? parseInt(msStr, 10) * 10 : parseInt(msStr, 10);
        }
        const time = Math.max(0, m * 60 + s + (ms / 1000) + globalOffsetSec);
        timestamps.push(time);
      }

      if (timestamps.length > 0) {
        // Strip timestamps and inline word-by-word karaoke markers
        let text = line.replace(timeRegex, '').replace(karaokeTagRegex, '').trim();
        if (text) {
          for (const time of timestamps) {
            result.push({ time, text });
          }
        }
      }
    }
    return result.sort((a, b) => a.time - b.time);
  }

  setLyrics(lyricsArr) {
    this.lyrics = lyricsArr;
    this.activeIndex = -1;
    if (this.userScrollResumeTimer) {
      clearTimeout(this.userScrollResumeTimer);
      this.userScrollResumeTimer = null;
    }
    this.stopScrollPhysicsLoop();
    this.isUserScrolling = false;
    if (this.container) {
      this.container.classList.remove('manual-scrolling');
      this.container.style.transform = 'translateY(0)';
    }
    this.render();
  }

  render() {
    this.container.innerHTML = '';
    const fragment = document.createDocumentFragment();
    this.lyrics.forEach((line, idx) => {
      const el = document.createElement('div');
      el.className = 'lyrics-line';
      el.textContent = line.text;
      el.dataset.index = idx;
      el.style.setProperty('--stagger-delay', `${Math.min(idx * 45, 550)}ms`);
      el.addEventListener('click', () => {
        if (window.playerController && line.time >= 0) {
          if (this.userScrollResumeTimer) {
            clearTimeout(this.userScrollResumeTimer);
            this.userScrollResumeTimer = null;
          }
          this.stopScrollPhysicsLoop();
          this.isUserScrolling = false;
          this.container?.classList.remove('manual-scrolling');
          
          // Immediately highlight & scroll to selected lyric line before seek IPC responds
          this.update(line.time);
          window.playerController.seek(line.time);
        }
      });
      fragment.appendChild(el);
    });
    this.container.appendChild(fragment);
  }

  findLyricIndex(currentTime) {
    const arr = this.lyrics;
    let low = 0;
    let high = arr.length - 1;
    let result = -1;

    while (low <= high) {
      const mid = (low + high) >> 1;
      if (arr[mid].time <= currentTime) {
        result = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return result;
  }

  update(currentTime) {
    if (!this.lyrics.length || this.overlay.classList.contains('hidden')) return;

    const newIndex = this.findLyricIndex(currentTime);

    if (newIndex !== this.activeIndex && newIndex !== -1) {
      const isFarJump = this.activeIndex < 0 || Math.abs(newIndex - this.activeIndex) > 3;
      const lines = this.container.children;
      const oldIndex = this.activeIndex;
      
      if (isFarJump) {
        // Far jump / Init: Batch update all lines
        for (let i = 0; i < lines.length; i++) {
          const el = lines[i];
          if (!el) continue;
          if (i < newIndex) {
            el.classList.add('passed');
            el.classList.remove('active');
          } else if (i === newIndex) {
            el.classList.add('active');
            el.classList.remove('passed');
          } else {
            el.classList.remove('active', 'passed');
          }
        }
      } else {
        // Sequential advance: Selective O(1) update between oldIndex and newIndex
        const minIdx = Math.max(0, Math.min(oldIndex, newIndex));
        const maxIdx = Math.min(lines.length - 1, Math.max(oldIndex, newIndex));
        for (let i = minIdx; i <= maxIdx; i++) {
          const el = lines[i];
          if (!el) continue;
          if (i < newIndex) {
            el.classList.add('passed');
            el.classList.remove('active');
          } else if (i === newIndex) {
            el.classList.add('active');
            el.classList.remove('passed');
          } else {
            el.classList.remove('active', 'passed');
          }
        }
      }
      
      if (lines[newIndex] && !this.isUserScrolling) {
        this.scrollToLine(newIndex, isFarJump);
      }

      this.activeIndex = newIndex;
    }
  }

  scrollToLine(index, isFarJump = false) {
    this.stopScrollPhysicsLoop();
    const lineEl = this.container.children[index];
    if (!lineEl) return;

    if (isFarJump) {
      this.container.classList.add('far-jump');
    } else {
      this.container.classList.remove('far-jump');
    }

    const containerHeight = this.container.parentElement.clientHeight;
    const offsetTop = lineEl.offsetTop;
    // Anchor at 40% vertical viewport position from the top
    const targetAnchor = containerHeight * 0.40;
    const scrollAmount = targetAnchor - offsetTop - (lineEl.clientHeight / 2);
    
    this.currentScrollY = scrollAmount;
    this.targetScrollY = scrollAmount;
    // Set variable for individual child transforms (True staggered parallax)
    this.container.style.setProperty('--scroll-y', `${scrollAmount}px`);
  }
}

window.LyricsRenderer = LyricsRenderer;
