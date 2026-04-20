// 중앙화된 API 클라이언트 — 모든 fetch 호출은 여기를 통한다
const GameAPI = {
  _base() { return window.API_BASE; },

  async getSaves() {
    const r = await fetch(`${this._base()}/api/saves`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  async deleteSave(filename) {
    const r = await fetch(`${this._base()}/api/saves/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  },

  async loadSave(filename) {
    const r = await fetch(`${this._base()}/api/saves/${encodeURIComponent(filename)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  async createSave(stateJson) {
    const r = await fetch(`${this._base()}/api/saves`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(stateJson),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  async getOpening(stateJson) {
    const r = await fetch(`${this._base()}/api/opening`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: stateJson }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  async submitTurn(command, stateJson, history) {
    const r = await fetch(`${this._base()}/api/turn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, state: stateJson, history }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
      throw new Error(err.detail);
    }
    return r.json();
  },
};
window.GameAPI = GameAPI;
