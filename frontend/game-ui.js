// ── 씬 헤더 렌더링
function renderSceneHeader(progress, scenarioTitle = '') {
  const chapterBadge = document.getElementById('chapter-badge');
  const sceneBadge   = document.getElementById('scene-badge');
  const chapterInfo  = document.getElementById('chapter-info');
  if (chapterBadge) chapterBadge.textContent = `${progress.chapter}장`;
  if (sceneBadge)   sceneBadge.textContent   = progress.isChapterEnd ? '장 종결' : `SCENE ${progress.scene}`;
  if (chapterInfo)  chapterInfo.textContent  = progress.chapterTitle || scenarioTitle;
}

function renderTimestamp(progress) {
  const span = document.getElementById('timestamp-text');
  if (span && progress.timestamp) span.textContent = progress.timestamp;
}

// ── 지휘관 패널
function renderCommanderPanel(state) {
  const panel = document.getElementById('commander-panel');
  if (!panel || !_ui) return;
  const { name, sub, fields } = _ui.commanderInfo(state);
  panel.innerHTML = `
    <div class="panel-label">지휘관</div>
    <div class="profile-block">
      <div class="avatar">${name.slice(0, 2)}</div>
      <div>
        <div class="profile-name">${name}</div>
        <div class="profile-sub">${sub}</div>
      </div>
    </div>
    ${fields.map(f => `<div class="stat-row"><span class="stat-key">${f.key}</span><span class="stat-val">${f.val}</span></div>`).join('')}`;
  rebindTooltips();
}

// ── 주요 인물
function renderCharacterList(state) {
  const container = document.getElementById('character-list');
  if (!container || !_ui) return;
  const chars = state.getActiveCharacters();
  if (chars.length === 0) {
    container.innerHTML = '<div class="char-row" style="color:var(--text-tertiary);font-size:12px;padding:8px 4px;">등록된 인물이 없습니다.</div>';
    rebindTooltips(); return;
  }
  container.innerHTML = chars.map(c => {
    const dotColor         = _ui.charDotColor(c, state);
    const { cls, label }   = _ui.charRelInfo(c, state);
    const body = c.desc || c.notes || '';
    const tag  = c.status_tag || '';
    return `<div class="char-row">
      <div class="char-dot" style="background:${dotColor};"></div>
      <div class="char-name-wrap">
        <span class="char-name" data-name="${c.name}" data-sub="${c.epithet||''}" data-body="${body}" data-tags="${tag}">${c.name}</span>
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
  container.innerHTML = Array.from(state.factions.values()).filter(f => !f.defeated).map(f => {
    const score = Math.max(0, (f.strength_score ?? 350) - (f.battle_damage ?? 0));
    const width = `${Math.min(100, Math.round(score / 7))}%`;
    const color = _ui.factionBarColor(f);
    const tag   = _ui.factionBarTag(f);
    const short = f.name.split(' ')[0];
    return `<div class="faction-item">
      <span class="faction-name" data-name="${f.name}" data-sub="${f.type||''}" data-body="${f.notes||''}" data-tags="${tag}" data-color="${color}">${short}</span>
      <div class="faction-bar-wrap"><div class="faction-bar" style="width:${width};background:${color};"></div></div>
    </div>`;
  }).join('');
  rebindTooltips();
}

// ── 플레이어 위치 파싱
function playerPosition(state) {
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
    if (loc.terrain) pin.dataset.terrain = loc.terrain;
    if (loc.notes)   pin.dataset.note    = loc.notes;
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
    pin.style.left = `${loc.x}%`;
    pin.style.top  = `${loc.y}%`;

    pin.innerHTML = `
      <div class="pin-pulse" style="border-color:${color};"></div>
      <div class="pin-dot"   style="background:${color};"></div>
      <div class="pin-label">${loc.name.split(' ')[0]}</div>`;

    layer.appendChild(pin);
  });

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
          <div class="pin-dot"   style="background:#3A9E5F;"></div>
          <div class="pin-label">진군 중</div>`;
        layer.appendChild(transitPin);
      }
      transitPin.style.left = `${mx}%`;
      transitPin.style.top  = `${my}%`;
      transitPin.style.display = '';
    }
  } else if (transitPin) {
    transitPin.style.display = 'none';
  }

  rebindTooltips();
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
  container.innerHTML = events.map(ev => `<div class="event-item"
    data-name="${ev.name}" data-sub="${ev.sub}" data-body="${ev.body}" data-rows="${ev.rows}">
    <div class="event-header">
      <div class="event-dot" style="background:${ev.dot};"></div>
      <div class="event-title">${ev.name}</div>
    </div>
    <div class="event-meta">
      <span class="event-region">${ev.region}</span>
      <span class="event-badge ${ev.badge}">${ev.badgeText}</span>
    </div>
  </div>`).join('');
  rebindTooltips();
}

// ── 전체 UI 갱신
function renderAll(state) {
  renderSceneHeader(state.progress, state.scenarioTitle);
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
};

function renderResolution(res) {
  const el = document.getElementById('resolution-badge');
  if (!el) return;
  if (!res || res.tier_en === 'narrate') { el.style.display = 'none'; return; }
  const style = RESOLUTION_STYLE[res.tier_en];
  if (!style) { el.style.display = 'none'; return; }
  const modStr = res.modifiers?.length
    ? ' · ' + res.modifiers.map(([l, v]) => `${l} ${v > 0 ? '+' : ''}${v}`).join(', ')
    : '';
  el.style.display = 'inline-flex';
  el.style.color   = style.color;
  el.style.borderColor = style.color;
  el.title = `주사위 ${res.roll} → 보정 후 ${res.net}${modStr}`;
  el.textContent = style.label;
}

// ── 씬 본문·선택지 렌더러
function renderSceneBody(html) {
  const el = document.getElementById('scene-body');
  if (el) el.innerHTML = html;
}

const _CHOICE_TYPE_KW = {
  military:   ['공격','전투','포위','진격','돌격','출격','진군','침공','공세','교전','격파',
               '기습','매복','야습','선제','방어','농성','수성','수비','진지','방비'],
  diplomatic: ['협상','외교','동맹','설득','교섭','협력','회담','제안','조건','강화','회유','타협','요청'],
  intrigue:   ['정찰','첩보','암살','침투','위장','간첩','밀서','내통','공작','염탐',
               '잠입','모략','매수','이간','선동','유언비어','교란','와해','내응'],
};

function _choiceActionType(text) {
  for (const [type, kws] of Object.entries(_CHOICE_TYPE_KW)) {
    if (kws.some(kw => text.includes(kw))) return type;
  }
  return null;
}

function renderChoices(choices) {
  const list = document.getElementById('choice-list');
  if (!list) return;
  if (!choices.length) { list.innerHTML = ''; return; }
  list.innerHTML = choices
    .map(c => {
      const type = _choiceActionType(c);
      const cls  = type ? `choice-btn choice-btn--${type}` : 'choice-btn';
      return `<button class="${cls}" onclick="selectChoice(this)">${c}</button>`;
    })
    .join('');
}

function showLoading() {
  renderSceneBody('<div class="scene-loading">생성 중…</div>');
  renderChoices([]);
}

// ── 챕터 종결 화면 렌더링
function renderChapterClose(text) {
  const body = text.replace(/^##[^\n]*\n/, '').trim();

  const summaryIdx = body.search(/\*\*\d+장 요약\*\*/);
  const assessIdx  = body.search(/\*\*총평\*\*/);
  const embersIdx  = body.search(/\*\*잔불\*\*/);

  const narrative    = summaryIdx !== -1 ? body.slice(0, summaryIdx).trim() : body;
  const summaryBlock = summaryIdx !== -1 && assessIdx !== -1 ? body.slice(summaryIdx, assessIdx).trim() : '';
  const assessBlock  = assessIdx  !== -1 && embersIdx !== -1 ? body.slice(assessIdx,  embersIdx).trim() : '';
  const embersBlock  = embersIdx  !== -1 ? body.slice(embersIdx).trim() : '';

  const embersLines = embersBlock
    .split('\n')
    .filter(l => /^- .+/.test(l.trim()))
    .map(l => `<li>${inline(l.trim().slice(2))}</li>`)
    .join('');

  renderSceneBody(`
    ${markdownToHtml(narrative)}
    ${summaryBlock ? `<p class="panel-label" style="margin:16px 0 6px;">요약</p>${markdownToHtml(summaryBlock.replace(/\*\*\d+장 요약\*\*\n?/, ''))}` : ''}
    ${assessBlock  ? `<p class="panel-label" style="margin:16px 0 6px;">총평</p>${markdownToHtml(assessBlock.replace(/\*\*총평\*\*\n?/, ''))}` : ''}
    ${embersLines  ? `<p class="panel-label" style="margin:16px 0 6px;">잔불</p><ul class="embers-list">${embersLines}</ul>` : ''}
  `);

  const list = document.getElementById('choice-list');
  if (list) list.innerHTML = '<button class="next-chapter-btn" onclick="startNextChapter()">다음 장으로 →</button>';
}

function startNextChapter() {
  if (!_state) return;
  renderSceneBody('<p style="color:var(--text-tertiary);font-family:sans-serif;font-size:13px;">다음 장의 방향을 입력하세요. (시간 경과·사건·개입 사항)</p>');
  const list = document.getElementById('choice-list');
  if (list) list.innerHTML = '';
  document.getElementById('cmd')?.focus();
}
