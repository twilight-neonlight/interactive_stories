// 준비 중 알림 토스트
function showComingSoon(label) {
  const toast = document.createElement('div');
  toast.innerHTML = `<strong>${label}</strong>은(는) 아직 준비 중입니다`;
  Object.assign(toast.style, {
    position: 'fixed', bottom: '32px', left: '50%',
    transform: 'translateX(-50%) translateY(8px)',
    background: 'var(--bg-primary)', border: '1px solid var(--border-strong)',
    borderRadius: '8px', padding: '11px 22px',
    fontFamily: "'Noto Serif KR',serif", fontSize: '13px',
    color: 'var(--text-secondary)',
    boxShadow: '0 4px 18px rgba(0,0,0,0.10)',
    opacity: '0', transition: 'opacity 0.22s, transform 0.22s',
    zIndex: '300', whiteSpace: 'nowrap',
  });
  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateX(-50%) translateY(0)';
  });
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(-50%) translateY(8px)';
    setTimeout(() => toast.remove(), 300);
  }, 2300);
}

// ── 백엔드 /api/config 에서 로드되는 게임 메타데이터 ─────────────────────────
// 초기화 전에 접근하면 안 되는 값. game-init.js의 loadGameConfig()가 채운다.
window._gameConfig = {
  gradeScale:  null,  // string[] — E-…S+ (resolver.py 기준, 18개)
  weatherMeta: null,  // { [key]: { label, atk, def, effect } }
  terrainMeta: null,  // { [key]: { label, def_bonus, atk_penalty, effect } }
};

// ── 판정 수정자 배열 → 포맷 문자열 ───────────────────────────────────────────
// res.modifiers: [[label, value], ...] 형태
// separator: 항목 구분자 (debug panel은 ', ', badge는 ' · ')
function formatModifiers(modifiers, separator = ', ') {
  if (!modifiers?.length) return null;
  return modifiers.map(([l, v]) => `${l} ${v > 0 ? '+' : ''}${v}`).join(separator);
}

// 체스 기보 품질 표기 (!!, !, =, ?, ??) 추출
function extractQualityMark(modifiers) {
  return modifiers?.map(([l]) => l?.match(/\([!?=]{1,2}\)/)?.[0]).find(Boolean) ?? null;
}

// ── 선택지 버튼 HTML 생성 ─────────────────────────────────────────────────────
// choices: { text, type }[], onClickFn: 문자열 함수명 (onclick 속성에 주입)
const _CHOICE_TYPE_CSS = {
  attack: 'military', surprise: 'military', defense: 'military', siege: 'military',
  diplomatic: 'diplomatic',
  intrigue: 'intrigue',
};

function renderChoiceButtons(choices, onClickFn) {
  return choices.map(c => {
    const css = _CHOICE_TYPE_CSS[c.type];
    const cls = css ? `choice-btn choice-btn--${css}` : 'choice-btn';
    return `<button class="${cls}" data-action-type="${c.type || ''}" onclick="${onClickFn}(this)">${c.text}</button>`;
  }).join('');
}

// ── 턴 완료 공통 처리 ─────────────────────────────────────────────────────────
// submitTurn / submitCombatTurn / submitDiplomacyTurn 에서 공유.
// _state, _manager, _ui 는 game-init.js 의 전역 변수를 참조한다.
function commitTurn(cmd, content, su) {
  _state.pushHistory('user', cmd);
  _state.pushHistory('assistant', content);
  applyStateUpdates(su);
  _manager._state = _state;
  _manager.save();
}
