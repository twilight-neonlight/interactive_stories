/**
 * scenario-ui.js — 시나리오별 UI 렌더링 로직
 *
 * 데이터(SVG, 오프닝, NPC 풀, 이벤트, 색상)는 모두 backend/scenarios/{id}/ 에서 로드됩니다.
 * 이 파일에는 순수한 렌더링·게임 로직만 남습니다.
 *
 * window.getScenarioUI(scenarioId) 로 접근합니다.
 */

(function () {

// ── 공통 상수 ──────────────────────────────────────────────────────
const STRENGTH_LABEL = {
  extreme: '압도적', 'very high': '대규모', high: '강대',
  medium: '중규모', low: '소규모', 'very low': '소수', impotent: '무력',
};

const DISP_COLOR = { '우호': '#378ADD', '적대': '#E24B4A', '중립': '#888780' };

// ── 공통 헬퍼 ──────────────────────────────────────────────────────

/** 백엔드 npc_pool에서 protagonist(또는 'default')키로 한 명을 무작위 선택해 추가 */
function defaultOnInit(state) {
  const key  = state.protagonist || 'default';
  const pool = (state.npcPool ?? {})[key] ?? (state.npcPool ?? {})['default'] ?? [];
  if (!pool.length) return;
  const pick = pool[Math.floor(Math.random() * pool.length)];
  state.addCharacter(structuredClone(pick));
}

/** 백엔드 opening에서 protagonist(또는 'default')키의 오프닝 콘텐츠를 반환 */
function defaultGetOpeningContent(state) {
  const key = state.protagonist || 'default';
  const o   = state.opening ?? {};
  return o[key] ?? o['default'] ?? null;
}

// ════════════════════════════════════════════════════════════════
const CONFIGS = {

  // ── 대군세의 시대 ─────────────────────────────────────────────
  'great-heathen-army': {
    tagExtras: {},

    commanderInfo(state) {
      let name = '불명', sub = '—', title = '불명', troops = '불명', supply = '불명', ally = '없음';
      if (state.protagonist) {
        const char = state.characters.get(state.protagonist);
        if (char) {
          name   = char.name;
          title  = char.title || char.epithet || '불명';
          troops = char.troops || STRENGTH_LABEL[char.strength] || '불명';
          supply = char.supply || '불명';
          const fid = char.faction_id || char.faction;
          if (fid) { const f = state.factions.get(fid); if (f) sub = f.name; }
        }
      }
      const friendly = Array.from(state.factions.values()).filter(f => f.disposition === '우호');
      if (friendly.length > 0) {
        const pf = friendly[0];
        if (sub    === '—')    sub    = pf.name;
        if (name   === '불명') name   = pf.name;
        if (troops === '불명') troops = STRENGTH_LABEL[pf.strength] || '불명';
      }
      ally = friendly.slice(1).map(f => f.name.split(' ')[0]).join(', ') || '없음';
      return { name, sub, fields: [
        { key: '직위', val: title },
        { key: '병력', val: troops },
        { key: '보급', val: supply },
        { key: '동맹', val: ally },
      ]};
    },

    charDotColor(char, state) {
      if (char.id === state.protagonist) return '#378ADD';
      return DISP_COLOR[char.disposition] || '#888780';
    },
    charRelInfo(char, state) {
      if (char.id === state.protagonist) return { cls: 'rel-player', label: '플레이어' };
      return (
        char.disposition === '우호' ? { cls: 'rel-coop', label: '협력' } :
        char.disposition === '적대' ? { cls: 'rel-host', label: '적대' } :
        char.disposition === '중립' ? { cls: 'rel-unk',  label: '중립' } :
                                      { cls: 'rel-dist',  label: '불명' }
      );
    },

    factionBarColor(faction) { return DISP_COLOR[faction.disposition] || '#888780'; },
    factionBarTag(faction)   { return { 우호: '아군', 적대: '적대', 중립: '중립' }[faction.disposition] || '불명'; },

    mapMarkerStyle(loc, state) {
      if (loc.controller === 'contested') return { color: '#EF9F27', statusText: '불안정' };
      const faction = state.factions.get(loc.controller);
      const disp    = faction?.disposition;
      if (disp === '우호') return { color: '#378ADD', statusText: '아군 거점' };
      if (disp === '적대') return { color: '#E24B4A', statusText: '적 점거' };
      return { color: '#888780', statusText: '함락' };
    },

    /** 적대 세력의 점거 거점을 동적으로 사건 목록으로 변환 */
    getEvents(state) {
      const events = [];
      state.factions.forEach(faction => {
        if (faction.disposition !== '적대') return;
        const locs = Array.from(state.locations.values())
          .filter(l => l.controller === faction.id)
          .map(l => l.name.split(' ')[0]).join(', ');
        events.push({
          name: faction.name, sub: `세력 동향 · ${state.scenarioTitle}`,
          body: faction.notes || '', dot: '#E24B4A', region: locs || '—',
          rows: `세력:${faction.name}|상태:적대 — 교전 중`,
          badge: 'badge-active', badgeText: '진행 중',
        });
      });
      return events;
    },

    getOpeningContent: defaultGetOpeningContent,
    initDispositions(_state) { /* 시나리오 데이터에 이미 설정됨 */ },
    onInit: defaultOnInit,
  },

  // ── 뇌제의 후계자 ─────────────────────────────────────────────
  'ottoman-interregnum': {
    tagExtras: { '경쟁': ['#fcebeb', '#a32d2d'] },

    commanderInfo(state) {
      let name = '불명', sub = '—', epithet = '불명', base = '불명', strength = '불명', ally = '없음';
      if (state.protagonist) {
        const char = state.characters.get(state.protagonist);
        if (char) {
          name    = char.name;
          epithet = char.epithet || char.title || '불명';
          base    = char.base ? char.base.split(' — ')[0] : '불명';
        }
        const ownFaction = state.factions.get(state.protagonist);
        if (ownFaction) {
          sub      = ownFaction.name;
          strength = STRENGTH_LABEL[ownFaction.strength] || '불명';
        }
      }
      const allyFactions = Array.from(state.factions.values())
        .filter(f => f.disposition === '우호' && f.id !== state.protagonist);
      ally = allyFactions.map(f => f.name.split(' ')[0]).join(', ') || '없음';
      return { name, sub, fields: [
        { key: '칭호', val: epithet },
        { key: '세력', val: strength },
        { key: '거점', val: base },
        { key: '동맹', val: ally },
      ]};
    },

    /** 캐릭터 데이터의 color 필드 사용 */
    charDotColor(char) { return char.color || '#888780'; },
    charRelInfo(char, state) {
      if (char.id === state.protagonist) return { cls: 'rel-player', label: '플레이어' };
      return (
        char.disposition === '우호' ? { cls: 'rel-coop', label: '협력' } :
        char.disposition === '적대' ? { cls: 'rel-host', label: '경쟁' } :
        char.disposition === '중립' ? { cls: 'rel-unk',  label: '중립' } :
                                      { cls: 'rel-dist',  label: '불명' }
      );
    },

    /** 세력 데이터의 color 필드 사용 */
    factionBarColor(faction) { return faction.color || '#888780'; },
    factionBarTag(faction)   { return { 우호: '아군', 적대: '경쟁', 중립: '중립' }[faction.disposition] || '불명'; },

    mapMarkerStyle(loc, state) {
      if (loc.controller === 'contested') return { color: '#EF9F27', statusText: '불안정' };
      const faction = state.factions.get(loc.controller);
      const color   = faction?.color || '#888780';
      const disp    = faction?.disposition;
      if (disp === '우호') return { color, statusText: '아군 거점' };
      if (disp === '적대') return { color, statusText: '경쟁 세력' };
      return { color, statusText: '중립' };
    },

    /** events.json에서 로드된 세계 사건 목록 반환 */
    getEvents(state) { return state.events ?? []; },

    getOpeningContent: defaultGetOpeningContent,

    /** type:'faction'인 세력들을 왕자로 간주해 disposition 초기화 */
    initDispositions(state) {
      const princes = Array.from(state.factions.values())
        .filter(f => f.type === 'faction')
        .map(f => f.id);
      const pid = state.protagonist;
      princes.forEach(id => {
        const f = state.factions.get(id);
        if (f) f.disposition = (id === pid) ? '우호' : '적대';
      });
      for (const [id, char] of state.characters) {
        if (id === pid)              char.disposition = '우호';
        else if (princes.includes(id)) char.disposition = '적대';
        else char.disposition = char.disposition ?? '중립';
      }
    },

    onInit: defaultOnInit,
  },
};

// ── 공개 API ─────────────────────────────────────────────────────
window.getScenarioUI = function (scenarioId) {
  return CONFIGS[scenarioId] || CONFIGS['great-heathen-army'];
};

})();
