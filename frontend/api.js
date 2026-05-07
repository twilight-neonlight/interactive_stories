// 중앙화된 API 클라이언트 — 모든 fetch 호출은 여기를 통한다
const GameAPI = {
  _base() { return window.API_BASE; },

  // Authorization 헤더 (토큰 없으면 빈 객체)
  _auth() {
    const token = NavState.getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  },

  // 401 응답 시 토큰 삭제 후 로그인 페이지로 이동
  _handle401() {
    NavState.clearAuth();
    window.location.href = '/frontend/auth.html';
  },

  async getSaves() {
    const r = await fetch(`${this._base()}/api/saves`, {
      headers: this._auth(),
    });
    if (r.status === 401) { this._handle401(); return []; }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  async deleteSave(filename) {
    const r = await fetch(`${this._base()}/api/saves/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
      headers: this._auth(),
    });
    if (r.status === 401) { this._handle401(); return; }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  },

  async loadSave(filename) {
    const r = await fetch(`${this._base()}/api/saves/${encodeURIComponent(filename)}`, {
      headers: this._auth(),
    });
    if (r.status === 401) { this._handle401(); return null; }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  async createSave(stateJson) {
    const r = await fetch(`${this._base()}/api/saves`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...this._auth() },
      body: JSON.stringify(stateJson),
    });
    if (r.status === 401) { this._handle401(); return null; }
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

  async submitTurn(command, stateJson, history, retreat = false) {
    const r = await fetch(`${this._base()}/api/turn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, state: stateJson, history, retreat }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
      throw new Error(err.detail);
    }
    return r.json();
  },
};
window.GameAPI = GameAPI;
