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
    this.bindEvents();
  }

  bindEvents() {
    document.getElementById('btn-lyrics-toggle').addEventListener('click', () => this.toggle());
    document.getElementById('btn-close-lyrics')?.addEventListener('click', () => this.hide());
    this.toggleLyricsBtn?.addEventListener('click', () => this.toggleLyricsView());
    
    if (window.store) {
      window.store.subscribe('currentTrack', () => {
        if (!this.overlay.classList.contains('hidden')) {
          this.show();
        }
      });
    }
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
      this.show();
    } else {
      this.hide();
    }
  }

  async show() {
    this.overlay.classList.remove('hidden');
    if (this.noLyricsTimer) {
      clearTimeout(this.noLyricsTimer);
      this.noLyricsTimer = null;
    }

    // Restore view mode based on user preference
    if (this.userDisabledLyrics) {
      this.applyLyricsViewState(false);
    } else {
      this.applyLyricsViewState(true);
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
      
      // Prevent race conditions: Ensure this response still belongs to the currently active track
      if (this._currentTrackPath !== track.path) {
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
    const lines = lrcText.split('\n');
    const result = [];
    const timeRegex = /\[(\d{1,2}):(\d{2})(?:\.(\d{2,3}))?\]/;
    
    for (const line of lines) {
      const match = timeRegex.exec(line);
      if (match) {
        const m = parseInt(match[1]);
        const s = parseInt(match[2]);
        const ms = match[3] ? parseInt(match[3]) : 0;
        const time = m * 60 + s + (ms / (match[3] && match[3].length === 2 ? 100 : 1000));
        const text = line.replace(timeRegex, '').trim();
        if (text) {
          result.push({ time, text });
        }
      }
    }
    return result.sort((a, b) => a.time - b.time);
  }

  setLyrics(lyricsArr) {
    this.lyrics = lyricsArr;
    this.activeIndex = -1;
    if (this.container) {
      this.container.style.transform = 'translateY(0)';
    }
    this.render();
  }

  render() {
    this.container.innerHTML = '';
    this.lyrics.forEach((line, idx) => {
      const el = document.createElement('div');
      el.className = 'lyrics-line';
      el.textContent = line.text;
      el.dataset.index = idx;
      el.style.setProperty('--stagger-delay', `${Math.min(idx * 45, 550)}ms`);
      el.addEventListener('click', () => {
        if (window.playerController && line.time >= 0) {
          // Immediately highlight & scroll to selected lyric line before seek IPC responds
          this.update(line.time);
          window.playerController.seek(line.time);
        }
      });
      this.container.appendChild(el);
    });
  }

  update(currentTime) {
    if (!this.lyrics.length || this.overlay.classList.contains('hidden')) return;

    let newIndex = -1;
    for (let i = this.lyrics.length - 1; i >= 0; i--) {
      if (currentTime >= this.lyrics[i].time) {
        newIndex = i;
        break;
      }
    }

    if (newIndex !== this.activeIndex && newIndex !== -1) {
      const isFarJump = this.activeIndex >= 0 && Math.abs(newIndex - this.activeIndex) > 3;
      const lines = this.container.children;
      
      for (let i = 0; i < lines.length; i++) {
        if (lines[i]) {
          lines[i].classList.remove('active', 'passed');
          if (i < newIndex) {
            lines[i].classList.add('passed');
          }
        }
      }
      
      if (lines[newIndex]) {
        lines[newIndex].classList.add('active');
        this.scrollToLine(newIndex, isFarJump);
      }

      this.activeIndex = newIndex;
    }
  }

  scrollToLine(index, isFarJump = false) {
    const lineEl = this.container.children[index];
    if (!lineEl) return;

    if (isFarJump) {
      this.container.classList.add('far-jump');
    } else {
      this.container.classList.remove('far-jump');
    }

    const containerHeight = this.container.parentElement.clientHeight;
    const offsetTop = lineEl.offsetTop;
    // Neo ở vị trí 40% từ đỉnh xuống
    const targetAnchor = containerHeight * 0.40;
    const scrollAmount = targetAnchor - offsetTop - (lineEl.clientHeight / 2);
    
    // Set variable for individual child transforms (True staggered parallax)
    this.container.style.setProperty('--scroll-y', `${scrollAmount}px`);
  }
}

window.LyricsRenderer = LyricsRenderer;
