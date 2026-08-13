class LyricsRenderer {
  constructor() {
    this.container = document.getElementById('lyrics-content');
    this.overlay = document.getElementById('lyrics-overlay');
    this.lyrics = [];
    this.activeIndex = -1;
    this.bindEvents();
  }

  bindEvents() {
    document.getElementById('btn-lyrics-toggle').addEventListener('click', () => this.toggle());
    document.getElementById('btn-close-lyrics')?.addEventListener('click', () => this.hide());
    
    if (window.store) {
      window.store.subscribe('currentTrack', () => {
        if (!this.overlay.classList.contains('hidden')) {
          this.show();
        }
      });
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
    const track = window.store.getState().currentTrack;
    const defaultCover = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI1NiIgaGVpZ2h0PSI1NiI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0iIzMzMyIvPjwvc3ZnPg==';
    
    if (track) {
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
      if (lrcData && lrcData.synced_lyrics) {
        const parsed = this.parseLRC(lrcData.synced_lyrics);
        if (parsed && parsed.length > 0) {
          this.setLyrics(parsed);
          if (window.playerController) {
            this.update(window.playerController.currentTime || 0);
          }
        } else {
          this.setLyrics([{ time: 0, text: "No synced lyrics available." }]);
        }
      } else {
        this.setLyrics([{ time: 0, text: "No synced lyrics available." }]);
      }
    } else {
      document.getElementById('lyrics-track-name').textContent = 'No Track';
      document.getElementById('lyrics-track-artist').textContent = '';
      document.getElementById('lyrics-cover').src = defaultCover;
      this.overlay.style.setProperty('--cover-url', 'none');
      this.setLyrics([{ time: 0, text: "Play a song to see lyrics." }]);
    }
  }

  hide() {
    this.overlay.classList.add('hidden');
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
        if (lines[i]) lines[i].classList.remove('next');
      }

      if (this.activeIndex >= 0 && lines[this.activeIndex]) {
        lines[this.activeIndex].classList.remove('active');
        lines[this.activeIndex].classList.add('passed');
      }
      
      for (let i = 0; i < newIndex; i++) {
         if (lines[i]) { lines[i].classList.remove('active'); lines[i].classList.add('passed'); }
      }
      
      if (lines[newIndex]) {
        lines[newIndex].classList.add('active');
        lines[newIndex].classList.remove('passed');
        this.scrollToLine(newIndex, isFarJump);
      }

      if (lines[newIndex + 1]) {
        lines[newIndex + 1].classList.add('next');
      }

      this.activeIndex = newIndex;
    }
  }

  scrollToLine(index, isFarJump = false) {
    const lineEl = this.container.children[index];
    if (!lineEl) return;

    if (isFarJump) {
      this.container.style.transition = 'transform 450ms cubic-bezier(0.25, 1, 0.35, 1)';
    } else {
      this.container.style.transition = '';
    }

    const containerHeight = this.container.parentElement.clientHeight;
    const offsetTop = lineEl.offsetTop;
    const halfHeight = containerHeight / 2;
    const scrollAmount = halfHeight - offsetTop - (lineEl.clientHeight / 2);
    this.container.style.transform = `translateY(${scrollAmount}px)`;
  }
}

window.LyricsRenderer = LyricsRenderer;
