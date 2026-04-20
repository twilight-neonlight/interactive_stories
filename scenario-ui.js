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

/**
 * 가중치 기반 다양성 픽업.
 * 1차 패스: 우호·중립·적대 각 한 명씩 확보 (성향 다양성 보장)
 * 2차 패스: 남은 슬롯을 가중치 랜덤으로 채움
 */
function weightedPickDiverse(pool, count) {
  if (!pool.length) return [];

  function weightedPick(candidates) {
    const total = candidates.reduce((s, n) => s + (n.weight ?? 1), 0);
    let r = Math.random() * total;
    for (const n of candidates) { r -= (n.weight ?? 1); if (r <= 0) return n; }
    return candidates[candidates.length - 1];
  }

  const result = [];
  const remaining = [...pool];

  for (const disp of ['우호', '중립', '적대']) {
    if (result.length >= count) break;
    const group = remaining.filter(n => n.disposition === disp);
    if (!group.length) continue;
    const chosen = weightedPick(group);
    result.push(chosen);
    remaining.splice(remaining.indexOf(chosen), 1);
  }

  while (result.length < count && remaining.length) {
    const chosen = weightedPick(remaining);
    result.push(chosen);
    remaining.splice(remaining.indexOf(chosen), 1);
  }

  return result;
}

/**
 * 게임 시작 시 NPC 풀에서 휘하 인물을 생성한다.
 * - 군주/영주(faction type: kingdom·faction·empire, 또는 title에 왕·군주 등): 3–5명 (성향 다양)
 * - 일반 장군·지휘관: 1–2명
 * - start_eligible: false 항목과 require_location 조건 미충족 항목은 제외
 *   (require_location 항목은 이벤트 중 AI가 npc-pool을 참조해 별도 등장)
 */
function defaultOnInit(state) {
  const key  = state.protagonist || 'default';
  const pool = (state.npcPool ?? {})[key] ?? (state.npcPool ?? {})['default'] ?? [];
  if (!pool.length) return;

  const char = state.characters.get(state.protagonist);
  const homeFactionId = char?.faction_id || char?.faction
    || (state.factions.has(state.protagonist) ? state.protagonist : null);
  const ownFaction    = state.factions.get(homeFactionId);

  const lordTitles = ['왕', '군주', '영주', '왕자', '칼리프', '술탄', '황제'];
  const isMonarch  = lordTitles.some(t => char?.title?.includes(t))
    || ['kingdom', 'faction', 'empire'].includes(ownFaction?.type);
  const count = isMonarch
    ? 3 + Math.floor(Math.random() * 3)  // 3–5명
    : 1 + Math.floor(Math.random() * 2); // 1–2명

  const eligible = pool.filter(npc => {
    if (npc.start_eligible === false) return false;
    if (npc.require_location?.length) {
      return npc.require_location.some(
        locId => state.locations.get(locId)?.controller === homeFactionId
      );
    }
    return true;
  });

  for (const pick of weightedPickDiverse(eligible, count)) {
    state.addCharacter(structuredClone(pick));
  }
}

/** 백엔드 opening에서 protagonist(또는 'default')키의 오프닝 콘텐츠를 반환 */
function defaultGetOpeningContent(state) {
  const key = state.protagonist || 'default';
  const o   = state.opening ?? {};
  return o[key] ?? o['default'] ?? null;
}

/** troops_count 숫자를 읽기 좋은 문자열로 변환 */
function formatTroops(count) {
  if (count == null || count < 0) return '불명';
  if (count === 0) return '전멸';
  if (count >= 10000) return `${Math.floor(count / 1000)}천+`;
  if (count >= 1000)  return `${+(count / 1000).toFixed(1)}천`;
  return `${count}명`;
}

/** strength_score + troops_per_strength_point → "약 X~Y명" 범위 문자열 */
function formatStrengthScore(score, perPoint) {
  if (score == null || perPoint == null) return null;
  const base = score * perPoint;
  const lo   = Math.round(base * 0.8 / 500) * 500;
  const hi   = Math.round(base * 1.2 / 500) * 500;
  const fmt  = n => n >= 10000 ? `${Math.floor(n / 1000)}천` : n.toLocaleString();
  return `약 ${fmt(lo)}~${fmt(hi)}명`;
}

/**
 * 범용 지휘관 정보 빌더.
 * - 세력 조회: char.faction_id / char.faction 우선, 없으면 factions.get(protagonist) (오스만 방식)
 * - 동맹: 우호 세력 중 본인 세력 제외
 * - 표시 필드: 직위 / 병력 / 거점 / 동맹
 */
function defaultCommanderInfo(state) {
  let name = '불명', sub = '—', title = '불명', strength = '불명', base = '불명';
  let ownFactionId = null;

  if (state.protagonist) {
    const char = state.characters.get(state.protagonist);
    if (char) {
      name         = char.name;
      title        = char.birth_label || char.title || char.epithet || '불명';
      base         = char.base ? char.base.split(' — ')[0] : '불명';
      const tpp = state.troopsPerPoint ?? null;
      if (char.troops_count != null) {
        strength = formatTroops(char.troops_count);
      } else {
        strength = char.troops || STRENGTH_LABEL[char.strength] || '불명';
      }
      ownFactionId = char.faction_id || char.faction || null;
    }
    // 오스만 방식: protagonist id = faction id
    if (!ownFactionId && state.factions.has(state.protagonist)) {
      ownFactionId = state.protagonist;
    }
    if (ownFactionId) {
      const f   = state.factions.get(ownFactionId);
      const tpp = state.troopsPerPoint ?? null;
      if (f) {
        sub = f.name;
        if (strength === '불명') {
          const score = f.strength_score != null
            ? f.strength_score - (f.battle_damage ?? 0) : null;
          strength = formatStrengthScore(score, tpp)
                     || STRENGTH_LABEL[f.strength] || '불명';
        }
      }
    }
  }

  // protagonist 정보가 없을 때 우호 세력에서 보완
  if (name === '불명' || sub === '—' || strength === '불명') {
    const friendly = Array.from(state.factions.values())
      .filter(f => f.disposition === '우호' && f.id !== ownFactionId);
    if (name     === '불명' && friendly.length > 0) name = friendly[0].name;
    if (sub      === '—'   && friendly.length > 0) sub  = friendly[0].name;
    if (strength === '불명' && friendly.length > 0) {
      const tpp   = state.troopsPerPoint ?? null;
      const score = friendly[0].strength_score != null
        ? friendly[0].strength_score - (friendly[0].battle_damage ?? 0) : null;
      strength = formatStrengthScore(score, tpp)
                 || STRENGTH_LABEL[friendly[0].strength] || '불명';
    }
  }

  return { name, sub, fields: [
    { key: '직위', val: title },
    { key: '병력', val: strength },
    { key: '거점', val: base },
  ]};
}

// ════════════════════════════════════════════════════════════════
const CONFIGS = {

  // ── 대군세의 시대 ─────────────────────────────────────────────
  'great-heathen-army': {
    tagExtras: {},

    commanderInfo: defaultCommanderInfo,

    charDotColor(char, state) {
      if (char.id === state.protagonist) return '#3A9E5F';
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
      if (disp === '우호') {
        const char = state.characters.get(state.protagonist);
        const homeFactionId = char?.faction_id || char?.faction
          || (state.factions.has(state.protagonist) ? state.protagonist : null);
        if (homeFactionId && loc.controller === homeFactionId) {
          return { color: '#5DBB8B', statusText: '본국 영토' };
        }
        return { color: '#378ADD', statusText: '동맹 거점' };
      }
      if (disp === '적대') return { color: '#E24B4A', statusText: '적 점거' };
      return { color: '#888780', statusText: '중립' };
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

    commanderInfo: defaultCommanderInfo,

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
