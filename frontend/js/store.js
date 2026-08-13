class Store {
  constructor(initialState) {
    this.state = { ...initialState };
    this.listeners = new Map();
  }
  getState() { return this.state; }
  get(key) { return this.state[key]; }
  
  setState(partial) {
    const changed = Object.keys(partial).filter(k => this.state[k] !== partial[k]);
    if (changed.length === 0) return;
    this.state = { ...this.state, ...partial };
    this.notify(changed);
  }
  
  subscribe(keys, callback) {
    if (typeof keys === 'string') keys = [keys];
    keys.forEach(key => {
      if (!this.listeners.has(key)) this.listeners.set(key, new Set());
      this.listeners.get(key).add(callback);
    });
    return () => keys.forEach(k => this.listeners.get(k)?.delete(callback));
  }
  
  notify(changedKeys) {
    const notified = new Set();
    changedKeys.forEach(key => {
      this.listeners.get(key)?.forEach(cb => {
        if (!notified.has(cb)) { notified.add(cb); cb(this.state); }
      });
    });
  }
}

window.store = new Store({
  currentTrack: null,
  playlist: [],
  volume: 80,
  repeat: 'off',
  shuffle: false,
  isPlaying: false,
  view: 'home',
});
