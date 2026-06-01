// ── 디버그 모드 (?debug URL 파라미터 또는 메인 메뉴 비밀번호 인증으로 활성화)
const _debugMode = new URLSearchParams(window.location.search).has('debug') || sessionStorage.getItem('is_debugMode') === '1';

function renderDebugPanel(container, resolution, debugData) {
  if (!_debugMode || !container) return;

  container.querySelector('.debug-panel')?.remove();

  const res    = resolution || {};
  const extra  = debugData?.state_update || {};
  const qm     = debugData?.quality_mod;

  // ── 판정 요약 ────────────────────────────────────────────────────────────
  let resLines;
  if (res.tier_en === 'phase_dice') {
    const detail = res.roll_detail || {};
    const modStr = formatModifiers(res.modifiers) ?? '없음';
    resLines = [
      `type      : phase_dice`,
      `roll      : 아군 ${detail.ally ?? '?'} vs 적 ${detail.enemy ?? '?'} → ${res.roll >= 0 ? '+' : ''}${res.roll}`,
      `net       : ${res.net}`,
      `outcome   : ${res.phase_outcome || res.tier || '—'}`,
      `수정자    : ${modStr}`,
      `품질 보정 : ${qm != null ? qm : '—'}`,
    ];
  } else if (res.tier_en === 'combat_luck') {
    resLines = [
      `type      : combat_luck`,
      `roll      : ${res.roll}`,
      `luck_shift: ${res.luck_shift ?? res.net}`,
      `label     : ${res.luck_label || res.tier || '—'}`,
      `행동 유형 : ${res.action_type || '—'}`,
    ];
  } else if (res.tier_en) {
    const modStr = formatModifiers(res.modifiers) ?? '없음';
    resLines = [
      `tier      : ${res.tier_en}`,
      `roll / net: ${res.roll} → ${res.net}`,
      `수정자    : ${modStr}`,
      `품질 보정 : ${qm != null ? qm : '—'}`,
      `행동 유형 : ${res.action_type || '—'}`,
    ];
  } else {
    resLines = ['판정 없음'];
  }

  // ── 헬퍼 ─────────────────────────────────────────────────────────────────
  const _esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const _section = (label, content, open = false) => `
    <details ${open ? 'open' : ''} style="margin-top:8px;">
      <summary style="cursor:pointer;color:#6a8a60;font-size:10px;letter-spacing:0.08em;
        user-select:none;list-style:none;padding:2px 0;">${label}</summary>
      ${content}
    </details>`;
  const _pre = (text, color = '#888') =>
    `<pre style="margin:4px 0 0;color:${color};white-space:pre-wrap;font-size:10px;
      background:#111;padding:8px;border-radius:4px;overflow-x:auto;max-height:400px;overflow-y:auto;">${_esc(text)}</pre>`;
  const _json = (obj, color) => _pre(JSON.stringify(obj, null, 2), color);

  // ── 적 예고 행동 ─────────────────────────────────────────────────────────
  const enemyAction = extra.enemy_next_action;
  const enemyHtml = enemyAction
    ? _section('적 예고 행동 (비공개)', _pre(enemyAction, '#c87a3a'), true)
    : '';

  // ── LLM STATE_UPDATE (enemy_next_action 제외) ────────────────────────────
  const filteredExtra = Object.fromEntries(
    Object.entries(extra).filter(([k, v]) => {
      if (k === 'enemy_next_action') return false;
      return Array.isArray(v) ? v.length > 0 : v != null && v !== '';
    })
  );

  // ── 최종 state_updates (빈 배열 제외) ────────────────────────────────────
  const finalUpdates = Object.fromEntries(
    Object.entries(debugData?.state_updates_final || {}).filter(([, v]) =>
      Array.isArray(v) ? v.length > 0 : v != null
    )
  );

  const el = document.createElement('details');
  el.className = 'debug-panel';
  el.open = true;
  el.style.cssText = 'margin-top:16px;border-top:1px solid #2a2a2a;padding-top:8px;';
  el.innerHTML = `
    <summary style="cursor:pointer;font-size:11px;font-family:monospace;color:#555;
      user-select:none;list-style:none;">🛠 DEBUG</summary>
    <div style="margin-top:6px;font-family:monospace;font-size:11px;line-height:1.7;">
      ${_section('판정', _pre(resLines.join('\n')), true)}
      ${enemyHtml}
      ${_section('LLM STATE_UPDATE', _json(filteredExtra), true)}
      ${_section('최종 state_updates', _json(finalUpdates, '#7a9a88'), true)}
      ${_section('LLM 원본 응답', _pre(debugData?.llm_raw ?? '—', '#aaa'))}
      ${_section('시스템 프롬프트', _pre(debugData?.system_prompt ?? '—', '#777'))}
    </div>`;
  container.appendChild(el);
}
window.renderDebugPanel = renderDebugPanel;

// ── 영토 레이어 색상 갱신 ─────────────────────────────────────────────────────
function _hexToRgba(hex, alpha) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function renderTerritoryLayer(state) {
  const svg = document.querySelector('#territory-layer svg');
  if (!svg) return;

  svg.querySelectorAll('[data-id]').forEach(path => {
    // data-locations="id1,id2,..." 또는 단일 data-id
    const ids = path.dataset.locations
      ? path.dataset.locations.split(',').map(s => s.trim()).filter(Boolean)
      : [path.dataset.id];

    const controllers = new Set(
      ids.map(id => state.locations.get(id)?.controller).filter(Boolean)
    );

    if (controllers.size === 0) return;

    const isSplit = controllers.size > 1 || controllers.has('contested');
    if (isSplit) {
      path.style.fill   = 'rgba(255,200,50,0.13)';
      path.style.stroke = 'rgba(255,200,50,0.45)';
      path.dataset.territoryStatus = '분할 지배 중';
    } else {
      const controller = [...controllers][0];
      const color = state.factions.get(controller)?.color ?? '#888888';
      path.style.fill   = _hexToRgba(color, 0.2);
      path.style.stroke = _hexToRgba(color, 0.5);
      path.dataset.territoryStatus = state.factions.get(controller)?.name ?? controller;
    }
    path.style.strokeWidth = '0.3';
  });
}

function renderTimestamp(progress) {
  const span = document.getElementById('timestamp-text');
  if (span && progress.timestamp) span.textContent = progress.timestamp;
}

// ── 지휘관 패널
const _ABILITY_KEYS = ['통솔', '지략', '외교', '행정', '무력'];
const _GRADE_COLOR  = { S: '#c084fc', A: '#e8a838', B: '#5ba0d8' };

function _gradeHtml(grade) {
  if (!grade) return `<span class="ability-grade">—</span>`;
  const color = _GRADE_COLOR[grade[0].toUpperCase()];
  return `<span class="ability-grade"${color ? ` style="color:${color}"` : ''}>${grade}</span>`;
}

function renderCommanderPanel(state) {
  const panel = document.getElementById('commander-panel');
  if (!panel || !_ui) return;
  const { name, sub, strength, stats } = _ui.commanderInfo(state);

  const statsHtml = stats
    ? `<div class="ability-grid">${_ABILITY_KEYS.map(k =>
        `<div class="ability-cell"><div class="ability-cell-key">${k}</div>${_gradeHtml(stats[k])}</div>`
      ).join('')}</div>`
    : '';

  panel.innerHTML = `
    <div class="panel-label">지휘관</div>
    <div class="profile-block">
      <div class="avatar">${name.slice(0, 2)}</div>
      <div>
        <div class="profile-name">${name}</div>
        <div class="profile-sub">${sub}</div>
        <div class="profile-sub">병력 ${strength}</div>
      </div>
    </div>
    ${statsHtml}`;
  rebindTooltips();
}

// ── 주요 인물
function renderCharacterList(state) {
  const container = document.getElementById('character-list');
  if (!container || !_ui) return;
  const chars = state.getActiveCharacters()
    .sort((a, b) => (b.id === state.protagonist) - (a.id === state.protagonist));
  if (chars.length === 0) {
    container.innerHTML = '<div class="char-row" style="color:var(--text-tertiary);font-size:12px;padding:8px 4px;">등록된 인물이 없습니다.</div>';
    rebindTooltips(); return;
  }
  const _injuryCls   = { '경상': 'light', '중상': 'moderate', '극도': 'critical' };
  const _statusLabel = { '포로': '포로', '실종': '실종' };
  container.innerHTML = chars.map(c => {
    const dotColor         = _ui.charDotColor(c, state);
    const { cls, label }   = _ui.charRelInfo(c, state);
    const body = c.desc || c.notes || '';
    const tag  = c.status_tag || '';
    const injuryBadge = c.injury
      ? `<span class="injury-badge injury-badge--${_injuryCls[c.injury] || 'light'}">${c.injury}</span>`
      : '';
    const rawStatus = c.status && c.status !== 'alive' ? c.status : null;
    const statusLabel = rawStatus === '실종' && c.id === state.protagonist ? '은둔' : rawStatus;
    const statusBadge = statusLabel
      ? `<span class="char-status-badge char-status--${rawStatus === '포로' ? 'prisoner' : 'missing'}">${statusLabel}</span>`
      : '';
    return `<div class="char-row">
      <div class="char-dot" style="background:${dotColor};"></div>
      <div class="char-name-wrap">
        <span class="char-name" data-name="${c.name}" data-sub="${c.epithet||''}" data-body="${body}" data-tags="${tag}">${c.name}</span>
        ${injuryBadge}${statusBadge}
      </div>
      <div class="rel-badge ${cls}">${label}</div>
    </div>`;
  }).join('');
  rebindTooltips();
}

// ── 세력 현황 바
function renderFactionBars(state) {
  const container = document.getElementById('faction-bars');
  if (!container || !_ui) return;
  const tpp = state.troopsPerPoint ?? null;
  const INTEL_LABEL = ['없음', '하', '중', '상', '정밀'];

  // protagonist 캐릭터의 faction_id로 플레이어 세력 판별 (오스만 방식 fallback 포함)
  const _pChar = state.characters.get(state.protagonist);
  const playerFactionId = _pChar?.faction_id
    || (state.factions.has(state.protagonist) ? state.protagonist : null);

  const _factions = Array.from(state.factions.values()).filter(f => !f.defeated);
  const _playerType = _factions.find(f => f.id === playerFactionId)?.type;
  _factions.sort((a, b) => {
    const sA = Math.max(0, (a.strength_score ?? 350) - (a.battle_damage ?? 0));
    const sB = Math.max(0, (b.strength_score ?? 350) - (b.battle_damage ?? 0));
    const rA = a.id === playerFactionId ? 0 : a.type === _playerType ? 1 : 2;
    const rB = b.id === playerFactionId ? 0 : b.type === _playerType ? 1 : 2;
    return rA !== rB ? rA - rB : sB - sA;
  });
  container.innerHTML = _factions.map(f => {
    const score = Math.max(0, (f.strength_score ?? 350) - (f.battle_damage ?? 0));
    const width = `${Math.min(100, Math.round(score / 7))}%`;
    const color = _ui.factionBarColor(f);
    const tag   = _ui.factionBarTag(f, state);
    const short = f.name.split(' ')[0];

    const parts = [];
    if (f.notes) parts.push(f.notes);
    if (tpp) {
      if (f.id === playerFactionId) {
        const ownTroops = f.field_army != null ? f.field_army : Math.round(score * tpp);
        parts.push(`병력: ${window.formatTroops(ownTroops)}`);
      } else {
        const disp  = f.disposition ?? '';
        const intel = f.intel_level ?? 0;
        let effectiveIntel = intel;
        if (disp === '동맹') effectiveIntel = Math.max(intel, 3);
        else if (disp === '우호') effectiveIntel = Math.max(intel, 1);
        const est = window.formatStrengthScore(score, tpp, effectiveIntel, f.id, f.field_army ?? null);
        if (est) parts.push(`병력 추정: ${est}`);
        parts.push(`첩보: ${INTEL_LABEL[intel]}`);
      }
    }
    const body = parts.join(' | ');

    return `<div class="faction-item">
      <span class="faction-name" data-name="${f.name}" data-sub="${f.type||''}" data-body="${body}" data-tags="${tag}" data-color="${color}">${short}</span>
      <div class="faction-bar-wrap"><div class="faction-bar" style="width:${width};background:${color};"></div></div>
    </div>`;
  }).join('');
  rebindTooltips();
}

// ── 플레이어 위치 결정 (명시적 STATE_UPDATE 우선, 타임스탬프 파싱 폴백)
function playerPosition(state) {
  const locId = state.progress?.playerLocationId;
  if (locId && state.locations.has(locId)) return { type: 'fixed', id: locId };

  const ts = state.progress?.timestamp || '';
  const m  = ts.match(/[,，]\s*(.+)$/) || ts.match(/\d년[^,，]*\s+(.+)$/);
  if (!m) return null;
  const segment = m[1].trim();

  const hits = [];
  for (const [id, loc] of state.locations) {
    const short = loc.name?.split(' ')[0];
    if (!short) continue;
    const idx = segment.indexOf(short);
    if (idx !== -1) hits.push({ id, idx });
  }
  hits.sort((a, b) => a.idx - b.idx);

  if (hits.length >= 2) return { type: 'transit', fromId: hits[0].id, toId: hits[hits.length - 1].id };
  if (hits.length === 1) return { type: 'fixed', id: hits[0].id };
  return null;
}

// ── 지도 마커 갱신
function renderMapMarkers(state) {
  if (!_ui) return;
  const layer = document.getElementById('map-markers-layer');
  if (!layer) return;

  const pos = playerPosition(state);

  layer.querySelectorAll('.map-pin[data-id]').forEach(pin => {
    const loc = state.locations.get(pin.dataset.id);
    if (!loc) return;
    const { color, statusText } = _ui.mapMarkerStyle(loc, state);
    const dot   = pin.querySelector('.pin-dot');
    const pulse = pin.querySelector('.pin-pulse');
    if (dot)   dot.style.background   = color;
    if (pulse) pulse.style.borderColor = color;
    const factionName = state.factions.get(loc.controller)?.name || loc.controller;
    pin.dataset.faction = factionName;
    pin.dataset.status  = statusText;
    pin.dataset.color   = color;
    if (loc.terrain)  pin.dataset.terrain  = loc.terrain;
    if (loc.notes)    pin.dataset.note     = loc.notes;
    if (loc.garrison) pin.dataset.garrison = `${loc.garrison.toLocaleString()}명`;
    pin.classList.toggle('is-player', pos?.type === 'fixed' && pin.dataset.id === pos.id);
  });

  state.locations.forEach((loc, id) => {
    if (loc.x == null || loc.y == null) return;
    if (layer.querySelector(`.map-pin[data-id="${id}"]`)) return;

    const { color, statusText } = _ui.mapMarkerStyle(loc, state);
    const factionName = state.factions.get(loc.controller)?.name || loc.controller || '—';

    const pin = document.createElement('div');
    pin.className = 'map-marker map-pin';
    if (pos?.type === 'fixed' && id === pos.id) pin.classList.add('is-player');
    pin.dataset.id      = id;
    pin.dataset.city    = loc.name;
    pin.dataset.faction = factionName;
    pin.dataset.terrain = loc.terrain || '';
    pin.dataset.status  = statusText;
    pin.dataset.color   = color;
    pin.dataset.note    = loc.notes || '';
    pin.dataset.tier    = loc.tier  || '';
    if (loc.garrison) pin.dataset.garrison = `${loc.garrison.toLocaleString()}명`;
    pin.style.left = `${loc.x}%`;
    pin.style.top  = `${loc.y}%`;

    pin.innerHTML = `
      <div class="pin-pulse" style="border-color:${color};"></div>
      <div class="pin-dot"   style="background:${color};"></div>`;

    layer.appendChild(pin);
  });

  // 고정 위치일 때 마지막 확인 위치 저장
  if (pos?.type === 'fixed') {
    if (!state.flags) state.flags = {};
    state.flags.lastKnownLocationId = pos.id;
  }

  let transitPin = layer.querySelector('#player-transit-pin');
  if (pos?.type === 'transit') {
    const from = state.locations.get(pos.fromId);
    const to   = state.locations.get(pos.toId);
    if (from?.x != null && to?.x != null) {
      const mx = (from.x + to.x) / 2;
      const my = (from.y + to.y) / 2;
      if (!transitPin) {
        transitPin = document.createElement('div');
        transitPin.id        = 'player-transit-pin';
        transitPin.className = 'map-marker map-pin is-player is-transit';
        transitPin.innerHTML = `
          <div class="pin-pulse" style="border-color:#3A9E5F;"></div>
          <div class="pin-dot"   style="background:#3A9E5F;"></div>`;
        layer.appendChild(transitPin);
      }
      transitPin.style.left = `${mx}%`;
      transitPin.style.top  = `${my}%`;
      transitPin.style.display = '';
      const regionText = from.region === to.region
        ? `${from.region} 지방`
        : `${from.region} → ${to.region}`;
      transitPin.dataset.city    = regionText;
      transitPin.dataset.status  = '이동 중';
      transitPin.dataset.faction = state.factions.get(state.protagonist)?.name || '';
      transitPin.dataset.color   = '#3A9E5F';
    }
  } else if (transitPin) {
    transitPin.style.display = 'none';
  }

  // 미등록 장소: 타임스탬프 원문 + 마지막 확인 도시 인근에 임시 마커
  let unknownPin = layer.querySelector('#player-unknown-pin');
  if (pos === null) {
    const anchorId = state.flags?.lastKnownLocationId;
    const anchor   = anchorId ? state.locations.get(anchorId) : null;
    const ts = state.progress?.timestamp || '';
    const m  = ts.match(/[,，]\s*(.+)$/) || ts.match(/\d년[^,，]*\s+(.+)$/);
    const locationText = m ? m[1].trim() : '미상';
    if (anchor?.x != null) {
      if (!unknownPin) {
        unknownPin = document.createElement('div');
        unknownPin.id        = 'player-unknown-pin';
        unknownPin.className = 'map-marker map-pin is-player is-unknown';
        unknownPin.innerHTML = `
          <div class="pin-pulse" style="border-color:#3A9E5F;"></div>
          <div class="pin-dot"   style="background:#3A9E5F;"></div>`;
        layer.appendChild(unknownPin);
      }
      // 장소 이름 기반의 결정론적 오프셋 (같은 이름이면 항상 같은 위치)
      const hash = [...locationText].reduce((acc, c) => acc + c.charCodeAt(0), 0);
      const dx = ((hash % 7) - 3) * 0.9;
      const dy = ((hash % 5) - 2) * 0.9;
      unknownPin.style.left    = `${anchor.x + dx}%`;
      unknownPin.style.top     = `${anchor.y + dy}%`;
      unknownPin.style.display = '';
      unknownPin.dataset.city    = locationText;
      unknownPin.dataset.status  = '야전 주둔';
      unknownPin.dataset.faction = state.factions.get(state.protagonist)?.name || '';
      unknownPin.dataset.color   = '#3A9E5F';
      unknownPin.dataset.note    = `${anchor.name.split(' ')[0]} 인근 (미등록 위치)`;
    }
  } else if (unknownPin) {
    unknownPin.style.display = 'none';
  }

  rebindTooltips();
  renderTerritoryLayer(state);
}

// ── 동시 진행 사건
function renderEventList(state) {
  const container = document.getElementById('event-list');
  if (!container || !_ui) return;
  const events = _ui.getEvents(state);
  if (events.length === 0) {
    container.innerHTML = '<div style="color:var(--text-tertiary);font-size:12px;padding:8px 4px;">진행 중인 사건이 없습니다.</div>';
    rebindTooltips(); return;
  }
  container.innerHTML = events.map(ev => {
    return `<div class="event-item"
    data-name="${ev.name}" data-sub="${ev.sub}" data-body="${ev.body}" data-rows="${ev.rows}">
    <div class="event-header">
      <div class="event-dot" style="background:${ev.dot};"></div>
      <div class="event-title">${ev.name}</div>
    </div>
  </div>`;
  }).join('');
  rebindTooltips();
}

// ── 전체 UI 갱신
function renderAll(state) {
  renderTimestamp(state.progress);
  renderCommanderPanel(state);
  renderCharacterList(state);
  renderFactionBars(state);
  renderMapMarkers(state);
  renderEventList(state);
}

// ── 행동 판정 배지
const RESOLUTION_STYLE = {
  critical_success: { label: '대성공', color: '#C5932A' },
  success:          { label: '성공',   color: '#5DBB8B' },
  partial:          { label: '부분 성공', color: '#EF9F27' },
  failure:          { label: '실패',   color: '#E24B4A' },
  critical_failure: { label: '대실패', color: '#8B2020' },
  combat_luck:      { label: '우연 변수', color: '#7F77DD' },
};

function renderResolution(res) {
  const el = document.getElementById('resolution-badge');
  if (!el) return;
  if (!res || res.tier_en === 'narrate') { el.style.display = 'none'; return; }
  const style = RESOLUTION_STYLE[res.tier_en];
  if (!style) { el.style.display = 'none'; return; }
  const modStr  = formatModifiers(res.modifiers, ' · ');
  const qMatch  = extractQualityMark(res.modifiers);
  el.style.display = 'inline-flex';
  el.style.color   = style.color;
  el.style.borderColor = style.color;
  el.title = res.roll != null
    ? `주사위 ${res.roll} → 보정 후 ${res.net}${modStr ? ' · ' + modStr : ''}`
    : modStr ?? '';
  el.textContent = qMatch ? `${style.label} ${qMatch}` : style.label;
}

// ── 씬 본문·선택지 렌더러
function renderSceneBody(html) {
  const el = document.getElementById('scene-body');
  if (el) el.innerHTML = html;
}

function renderChoices(choices) {
  const list = document.getElementById('choice-list');
  if (!list) return;
  if (!choices.length) { list.innerHTML = ''; return; }
  list.innerHTML = renderChoiceButtons(choices, 'selectChoice');
}

function showLoading() {
  renderSceneBody('<div class="scene-loading">생성 중…</div>');
  renderChoices([]);
}

// ── 게임 오버 오버레이
function renderGameOver(type, message) {
  document.getElementById('choice-list').innerHTML  = '';
  document.getElementById('cmd').disabled           = true;
  document.querySelector('.send-btn')?.setAttribute('disabled', '');

  const isVictory = type === 'victory';
  const overlay   = document.createElement('div');
  overlay.id        = 'game-over-overlay';
  overlay.innerHTML = `
    <div class="game-over-box ${isVictory ? 'game-over--victory' : 'game-over--defeat'}">
      <div class="game-over-icon">${isVictory ? '👑' : '☠'}</div>
      <div class="game-over-title">${isVictory ? '승리' : '패배'}</div>
      <div class="game-over-message">${message}</div>
      <button class="game-over-btn" onclick="location.href='main_menu.html'">메인 메뉴로</button>
    </div>`;
  document.getElementById('scene-body').appendChild(overlay);
}
window.renderGameOver = renderGameOver;
