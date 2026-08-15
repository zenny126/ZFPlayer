const KEY_SYMBOLS = {
  Space: 'Space',
  ArrowLeft: '←',
  ArrowRight: '→',
  ArrowUp: '↑',
  ArrowDown: '↓'
};

function formatKeyLabel(key) {
  if (KEY_SYMBOLS[key]) return KEY_SYMBOLS[key];
  if (key.startsWith('Key')) return key.slice(3);
  if (key.startsWith('Digit')) return key.slice(5);
  return key;
}

/**
 * ShortcutsManager - Comprehensive Keyboard Shortcut & Combination Manager for ZFPlayer
 * Supports single keys, multi-modifier combinations, live key recording, persistence & reset.
 */
class ShortcutsManager {
  constructor() {
    this.DEFAULT_SHORTCUTS = {
      play_pause: 'Space',
      prev_track: 'Ctrl+ArrowLeft',
      next_track: 'Ctrl+ArrowRight',
      seek_backward: 'ArrowLeft',
      seek_forward: 'ArrowRight',
      volume_up: 'ArrowUp',
      volume_down: 'ArrowDown',
      toggle_mute: 'KeyM',
      toggle_lyrics: 'KeyL',
      toggle_shuffle: 'KeyS',
      toggle_repeat: 'KeyR',
      toggle_fullscreen: 'F11'
    };

    this.ACTION_DEFINITIONS = [
      { id: 'play_pause', name: 'Play / Pause', desc: 'Toggle audio playback' },
      { id: 'prev_track', name: 'Previous Track', desc: 'Play previous song in queue' },
      { id: 'next_track', name: 'Next Track', desc: 'Play next song in queue' },
      { id: 'seek_backward', name: 'Seek Backward (-5s)', desc: 'Rewind playback by 5 seconds' },
      { id: 'seek_forward', name: 'Seek Forward (+5s)', desc: 'Fast-forward playback by 5 seconds' },
      { id: 'volume_up', name: 'Volume Up (+5%)', desc: 'Increase output volume' },
      { id: 'volume_down', name: 'Volume Down (-5%)', desc: 'Decrease output volume' },
      { id: 'toggle_mute', name: 'Mute / Unmute', desc: 'Toggle sound output' },
      { id: 'toggle_lyrics', name: 'Toggle Lyrics', desc: 'Open / close full-screen lyrics' },
      { id: 'toggle_shuffle', name: 'Toggle Shuffle', desc: 'Switch random playback mode' },
      { id: 'toggle_repeat', name: 'Toggle Repeat', desc: 'Cycle repeat mode (Off / All / One)' },
      { id: 'toggle_fullscreen', name: 'Toggle Fullscreen', desc: 'Switch full screen window' }
    ];

    this.shortcuts = { ...this.DEFAULT_SHORTCUTS };
    this.recordingAction = null;
    this.recordingModifiers = [];
  }

  /**
   * Load saved shortcut bindings from backend config
   */
  async init() {
    try {
      if (window.api && window.api.getConfig) {
        const config = await window.api.getConfig();
        if (config && config.shortcuts && typeof config.shortcuts === 'object') {
          this.shortcuts = { ...this.DEFAULT_SHORTCUTS, ...config.shortcuts };
        }
      }
    } catch (e) {
      console.warn('Failed to load shortcuts from config, using defaults:', e);
    }
  }

  /**
   * Save current shortcuts to config file
   */
  async save() {
    try {
      if (window.api && window.api.setConfig) {
        await window.api.setConfig('shortcuts', this.shortcuts);
      }
    } catch (e) {
      console.error('Failed to save shortcuts to config:', e);
    }
  }

  /**
   * Reset all shortcuts to factory defaults
   */
  async resetAll() {
    this.shortcuts = { ...this.DEFAULT_SHORTCUTS };
    await this.save();
    this.renderShortcutsUI();
    if (window.uiController && window.uiController.showToast) {
      window.uiController.showToast('Restored all shortcuts to defaults');
    }
  }

  /**
   * Reset a single action to default
   */
  async resetAction(actionId) {
    if (this.DEFAULT_SHORTCUTS[actionId]) {
      this.shortcuts[actionId] = this.DEFAULT_SHORTCUTS[actionId];
      await this.save();
      this.renderShortcutsUI();
      if (window.uiController && window.uiController.showToast) {
        const def = this.ACTION_DEFINITIONS.find(a => a.id === actionId);
        window.uiController.showToast(`Reset shortcut for "${def ? def.name : actionId}"`);
      }
    }
  }

  /**
   * Parse a KeyboardEvent into a normalized combo string
   */
  parseKeyEvent(e) {
    const modifiers = [];
    if (e.ctrlKey) modifiers.push('Ctrl');
    if (e.altKey) modifiers.push('Alt');
    if (e.shiftKey) modifiers.push('Shift');
    if (e.metaKey) modifiers.push('Meta');

    const key = e.key;
    if (['Control', 'Shift', 'Alt', 'Meta', 'AltGraph'].includes(key)) {
      return { isModifierOnly: true, modifiers, primary: '', combo: '' };
    }

    let primary = e.code || e.key;
    if (primary === 'Space' || key === ' ') primary = 'Space';
    else if (/^F\d{1,2}$/i.test(key)) primary = key.toUpperCase();
    else if (key.startsWith('Arrow')) primary = key;

    const parts = [...modifiers];
    if (primary) parts.push(primary);
    return {
      isModifierOnly: false,
      modifiers,
      primary,
      combo: parts.join('+')
    };
  }

  /**
   * Format combo string into beautiful HTML <kbd> tags
   */
  formatComboHTML(combo) {
    if (!combo) return '<span class="shortcut-unassigned">None</span>';
    return combo.split('+').map(part => `<kbd class="shortcut-key">${formatKeyLabel(part)}</kbd>`).join('<span class="shortcut-plus">+</span>');
  }

  /**
   * Format combo string into readable text
   */
  formatComboText(combo) {
    if (!combo) return 'None';
    return combo.split('+').map(formatKeyLabel).join(' + ');
  }

  /**
   * Normalize an event or configured shortcut for matching
   */
  matchesEvent(configuredCombo, e) {
    if (!configuredCombo) return false;
    
    const { isModifierOnly, combo, modifiers } = this.parseKeyEvent(e);
    if (isModifierOnly) return false;
    if (configuredCombo === combo) return true;

    // Fallback loose match for single letter keys (e.g. 'KeyM' vs 'm' / 'M' without modifiers)
    if (modifiers.length === 0 && !configuredCombo.includes('+')) {
      const upper = e.key.toUpperCase();
      return configuredCombo === `Key${upper}` || configuredCombo === upper || configuredCombo === e.code;
    }

    return false;
  }

  /**
   * Render the Shortcuts tab inside Settings Modal
   */
  renderShortcutsUI() {
    const container = document.getElementById('shortcuts-list-container');
    if (!container) return;

    if (!this._isDelegationBound) {
      this._isDelegationBound = true;
      container.addEventListener('click', async (e) => {
        const pillBtn = e.target.closest('.btn-shortcut-pill');
        if (pillBtn && pillBtn.dataset.action) {
          e.stopPropagation();
          this.startRecording(pillBtn.dataset.action);
          return;
        }

        const resetBtn = e.target.closest('.btn-shortcut-reset');
        if (resetBtn && resetBtn.dataset.action) {
          e.stopPropagation();
          await this.resetAction(resetBtn.dataset.action);
          return;
        }
      });
    }

    let html = '';
    this.ACTION_DEFINITIONS.forEach(action => {
      const currentCombo = this.shortcuts[action.id] || '';
      const isCustomized = currentCombo !== this.DEFAULT_SHORTCUTS[action.id];
      const isRecording = this.recordingAction === action.id;

      let btnContent = isRecording
        ? '<span class="recording-dot"></span> Press keys...'
        : this.formatComboHTML(currentCombo);

      html += `
        <div class="shortcut-row" data-action="${action.id}">
          <div class="shortcut-info">
            <div class="shortcut-name">${action.name}</div>
            <div class="shortcut-desc">${action.desc}</div>
          </div>
          <div class="shortcut-controls">
            <button class="btn-shortcut-pill ${isRecording ? 'recording' : ''}" data-action="${action.id}" title="Click to record new shortcut">
              ${btnContent}
            </button>
            ${isCustomized ? `
              <button class="btn-shortcut-reset" data-action="${action.id}" title="Reset to default (${this.formatComboText(this.DEFAULT_SHORTCUTS[action.id])})">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon" style="width: 14px; height: 14px;"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>
              </button>
            ` : ''}
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  }

  /**
   * Start recording shortcut for a specific action
   */
  startRecording(actionId) {
    this.recordingAction = actionId;
    this.recordingModifiers = [];
    this.renderShortcutsUI();

    const currentPill = document.querySelector(`.btn-shortcut-pill[data-action="${actionId}"]`);
    if (currentPill) {
      currentPill.focus();
    }
  }

  /**
   * Stop recording mode
   */
  stopRecording() {
    this.recordingAction = null;
    this.recordingModifiers = [];
    this.renderShortcutsUI();
  }

  /**
   * Global keydown handler when recording is active
   */
  handleRecordingKeyDown(e) {
    if (!this.recordingAction) return false;

    e.preventDefault();
    e.stopPropagation();

    // Cancel on Escape
    if (e.key === 'Escape') {
      this.stopRecording();
      return true;
    }

    const { isModifierOnly, modifiers, combo } = this.parseKeyEvent(e);

    // If only modifier keys are pressed, update button preview
    if (isModifierOnly) {
      this.recordingModifiers = modifiers;
      const currentPill = document.querySelector(`.btn-shortcut-pill[data-action="${this.recordingAction}"]`);
      if (currentPill) {
        currentPill.innerHTML = `<span class="recording-dot"></span> ${modifiers.join(' + ')} + ...`;
      }
      return true;
    }

    // A complete key combination has been pressed
    if (combo) {
      const actionId = this.recordingAction;
      
      // Check for conflict with other actions
      let conflictActionId = null;
      for (const [id, assignedCombo] of Object.entries(this.shortcuts)) {
        if (id !== actionId && assignedCombo === combo) {
          conflictActionId = id;
          break;
        }
      }

      this.shortcuts[actionId] = combo;
      
      // If conflict found, clear previous assignment or warn
      if (conflictActionId) {
        this.shortcuts[conflictActionId] = '';
        const conflictDef = this.ACTION_DEFINITIONS.find(a => a.id === conflictActionId);
        if (window.uiController && window.uiController.showToast) {
          window.uiController.showToast(`Reassigned combo from "${conflictDef ? conflictDef.name : conflictActionId}"`);
        }
      }

      this.save();
      this.stopRecording();

      const actionDef = this.ACTION_DEFINITIONS.find(a => a.id === actionId);
      if (window.uiController && window.uiController.showToast) {
        window.uiController.showToast(`Updated shortcut for ${actionDef ? actionDef.name : actionId}: ${this.formatComboText(combo)}`);
      }
      return true;
    }

    return true;
  }

  /**
   * Global application keydown dispatcher
   */
  async handleGlobalKeyDown(e) {
    // 1. If currently recording a shortcut in Settings, prioritize that
    if (this.recordingAction) {
      this.handleRecordingKeyDown(e);
      return;
    }

    // 2. Ignore keystrokes when typing inside inputs, textareas or contenteditable elements
    const targetTag = e.target.tagName ? e.target.tagName.toLowerCase() : '';
    if (targetTag === 'input' || targetTag === 'textarea' || e.target.isContentEditable) {
      if (e.key === 'Escape') {
        e.target.blur();
        document.querySelectorAll('.context-menu').forEach(m => m.classList.add('hidden'));
        document.querySelectorAll('.modal:not(.hidden)').forEach(m => m.classList.add('hidden'));
      }
      return;
    }

    // 3. Close modals/context menus on Escape, and isolate shortcut triggers when modal/context menu is active
    const activeModals = document.querySelectorAll('.modal:not(.hidden)');
    const activeContextMenus = document.querySelectorAll('.context-menu:not(.hidden)');
    if (activeModals.length > 0 || activeContextMenus.length > 0) {
      if (e.key === 'Escape') {
        document.querySelectorAll('.context-menu').forEach(m => m.classList.add('hidden'));
        document.querySelectorAll('.modal:not(.hidden)').forEach(m => m.classList.add('hidden'));
      }
      return;
    }

    if (e.key === 'Escape') {
      const lyricsOverlay = document.getElementById('lyrics-overlay');
      if (lyricsOverlay && !lyricsOverlay.classList.contains('hidden')) {
        if (window.lyricsRenderer) window.lyricsRenderer.hide();
        return;
      }
      return;
    }

    // 4. Dispatch configured shortcut action
    const player = window.playerController;
    const lyrics = window.lyricsRenderer;
    const actions = {
      play_pause: () => player?.togglePlay(),
      prev_track: () => player?.prev(),
      next_track: () => player?.next(),
      seek_backward: () => player && player.ticker && player.seek(Math.max(0, (player.ticker.position || 0) - 5)),
      seek_forward: () => player && player.ticker && player.seek(Math.min(player.ticker.duration || 0, (player.ticker.position || 0) + 5)),
      volume_up: () => player?.adjustVolume(5),
      volume_down: () => player?.adjustVolume(-5),
      toggle_mute: () => player?.toggleMute(),
      toggle_lyrics: () => lyrics?.toggle(),
      toggle_shuffle: () => player?.toggleShuffle(),
      toggle_repeat: () => player?.toggleRepeat(),
      toggle_fullscreen: () => window.api?.toggleFullscreen?.()
    };

    for (const [actionId, handler] of Object.entries(actions)) {
      if (this.matchesEvent(this.shortcuts[actionId], e)) {
        e.preventDefault();
        await handler();
        break;
      }
    }
  }
}

window.ShortcutsManager = ShortcutsManager;
