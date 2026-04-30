// 네비게이션 상태 — sessionStorage 키를 한 곳에서 관리

// ── 쿠키 내부 헬퍼 ─────────────────────────────────────────────────────────────
function _getCookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '=([^;]+)');
  return m ? decodeURIComponent(m[2]) : null;
}
function _setCookie(name, value, days) {
  const exp = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${exp}; path=/; SameSite=Lax`;
}
function _genUUID() {
  // crypto.randomUUID는 HTTPS / localhost에서만 사용 가능
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

const NavState = {
  // ── 인증 (localStorage: 세션 간 유지) ──────────────────────────────────────
  setAuth(token, username) {
    localStorage.setItem('is_token', token);
    localStorage.setItem('is_username', username);
  },
  clearAuth() {
    localStorage.removeItem('is_token');
    localStorage.removeItem('is_username');
  },
  getToken()    { return localStorage.getItem('is_token'); },
  getUsername() { return localStorage.getItem('is_username'); },

  // ── 게스트 UUID (localStorage + 쿠키 이중 저장) ────────────────────────────
  // localStorage가 삭제돼도 쿠키에서 복원, 쿠키가 삭제돼도 localStorage에서 복원
  getOrCreateGuestId() {
    let id = localStorage.getItem('is_guest_id') || _getCookie('is_guest_id');
    if (!id) {
      id = _genUUID();
    }
    // 두 저장소 모두 최신 값으로 동기화
    localStorage.setItem('is_guest_id', id);
    _setCookie('is_guest_id', id, 365);
    return id;
  },
  clearGuestId() {
    localStorage.removeItem('is_guest_id');
    _setCookie('is_guest_id', '', -1);
  },

  // ── 게임 내비게이션 ──────────────────────────────────────────────────────────
  setScenario(id) {
    sessionStorage.removeItem('is_gameState');
    sessionStorage.setItem('scenarioId', id);
  },

  setCharacter(id, name, scenarioId) {
    sessionStorage.setItem('selectedCharacterId', id);
    sessionStorage.setItem('selectedCharacterName', name);
    sessionStorage.setItem('scenario', scenarioId);
    sessionStorage.removeItem('is_gameState');
  },

  setSaveFile(filename) {
    sessionStorage.removeItem('is_gameState');
    sessionStorage.setItem('saveFile', filename);
  },

  setCustomScenario(text) {
    sessionStorage.setItem('customScenario', text);
  },

  clearGame() {
    sessionStorage.removeItem('saveFile');
    sessionStorage.removeItem('is_gameState');
  },

  getSaveFile()    { return sessionStorage.getItem('saveFile'); },
  getScenarioId()  { return sessionStorage.getItem('scenario') || sessionStorage.getItem('scenarioId'); },
  getCharacterId() { return sessionStorage.getItem('selectedCharacterId') || sessionStorage.getItem('selectedCharacter'); },
};
window.NavState = NavState;
