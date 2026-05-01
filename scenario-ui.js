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

/** 타임스탬프 문자열에서 연도를 추출. "1403년 3월, 에디르네" → 1403. 파싱 불가 시 null. */
function _parseYear(timestamp) {
  if (!timestamp) return null;
  const m = timestamp.match(/(\d{3,4})년/);
  return m ? parseInt(m[1]) : null;
}

/** 타임스탬프 문자열에서 월을 추출. "1403년 3월, 에디르네" → 3. 파싱 불가 시 null. */
function _parseMonth(timestamp) {
  if (!timestamp) return null;
  const m = timestamp.match(/(\d{1,2})월/);
  return m ? parseInt(m[1]) : null;
}

/** 연·월을 절대 개월 수로 변환. 6개월 경과 판단 등에 사용. */
function _totalMonths(year, month) {
  if (year == null || month == null) return null;
  return year * 12 + month;
}

function _buildEventConditionContext(state, year = _parseYear(state.progress?.timestamp)) {
  const month = _parseMonth(state.progress?.timestamp);
  return {
    year,
    month,
    chapter: state.progress?.chapter ?? null,
    scene:   state.progress?.scene   ?? null,
  };
}

function _eventConditionExpr(ev) {
  if (typeof ev.trigger_condition === 'string' && ev.trigger_condition.trim()) {
    return ev.trigger_condition.trim();
  }
  if (ev.trigger_year != null) {
    return `year >= ${Number(ev.trigger_year)}`;
  }
  return null;
}

function _coerceConditionValue(token, context) {
  const key = token.trim();
  if (key in context) return context[key];
  if (/^-?\d+$/.test(key)) return Number(key);
  if ((key.startsWith('"') && key.endsWith('"')) || (key.startsWith("'") && key.endsWith("'"))) {
    return key.slice(1, -1);
  }
  if (key.toLowerCase() === 'true') return true;
  if (key.toLowerCase() === 'false') return false;
  return undefined;
}

function _evalConditionAtom(atom, context) {
  const text = atom.trim();
  if (!text) return true;

  const match = text.match(/^(.+?)\s*(>=|<=|==|!=|>|<)\s*(.+)$/);
  if (match) {
    const left  = _coerceConditionValue(match[1], context);
    const op    = match[2];
    const right = _coerceConditionValue(match[3], context);
    if (left === undefined || right === undefined) return false;
    if (op === '>=') return left >= right;
    if (op === '<=') return left <= right;
    if (op === '==') return left === right;
    if (op === '!=') return left !== right;
    if (op === '>')  return left > right;
    if (op === '<')  return left < right;
  }

  const value = _coerceConditionValue(text, context);
  return value === undefined ? false : Boolean(value);
}

function _evaluateEventCondition(expression, context) {
  if (expression == null) return true;
  const expr = expression.trim();
  if (!expr) return true;

  const orParts = expr.split(/\s*(?:\|\||\bor\b)\s*/i).filter(Boolean);
  if (orParts.length > 1) return orParts.some(part => _evaluateEventCondition(part, context));

  const andParts = expr.split(/\s*(?:&&|\band\b)\s*/i).filter(Boolean);
  if (andParts.length > 1) return andParts.every(part => _evaluateEventCondition(part, context));

  return _evalConditionAtom(expr, context);
}

/**
 * 이벤트 상태 컨텍스트 빌더.
 * id가 있는 이벤트마다 {id}_active / {id}_ended 불리언 변수를 생성해 반환.
 * baseContext만 사용해 평가하므로 순환 의존 없이 단일 패스로 동작한다.
 */
function _buildEventStateContext(events, baseContext) {
  const evCtx = {};
  for (const ev of events ?? []) {
    if (!ev.id) continue;
    const triggerExpr = _eventConditionExpr(ev);
    const triggerMet  = _evaluateEventCondition(triggerExpr, baseContext);
    const endMet      = ev.end_condition
      ? _evaluateEventCondition(ev.end_condition, baseContext)
      : false;
    evCtx[`${ev.id}_active`] = triggerMet && !endMet;
    evCtx[`${ev.id}_ended`]  = endMet;
  }
  return evCtx;
}

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
 * field_army가 없는 세력에 대해 strength_score × troopsPerPoint 로 field_army를 초기화한다.
 * 동적으로 추가된 세력(무스타파, 티무르 원정군 등)이 대상이며, 이미 field_army가 있으면 무시.
 */
function _recomputeStrengthScores(state) {
  const tpp = state.troopsPerPoint;
  if (!tpp) return;
  for (const f of state.factions.values()) {
    if (f.field_army == null && f.strength_score != null) {
      f.field_army = Math.round(f.strength_score * tpp);
    }
  }
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
  _recomputeStrengthScores(state);
}

/** troops_count 숫자를 읽기 좋은 문자열로 변환 */
function formatTroops(count) {
  if (count == null || count < 0) return '불명';
  if (count === 0) return '전멸';
  return count.toLocaleString();
}

function _hashStr(s) {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h) ^ s.charCodeAt(i);
  return Math.abs(h);
}

/**
 * strength_score + troops_per_strength_point → "약 X~Y명" 범위 문자열.
 * intel_level 0–4 → 오차 폭 ±30/25/20/15/10%.
 * 실제값은 범위 내 비대칭 위치(faction id 기반 결정론적 offset) — 단순 중앙값 역산 방지.
 */
function formatStrengthScore(score, perPoint, intelLevel = 0, factionId = '') {
  if (score == null || perPoint == null) return null;
  const base      = score * perPoint;
  const halfRange = [0.30, 0.25, 0.20, 0.15, 0.10][Math.max(0, Math.min(4, intelLevel))];
  // p: 실제값이 범위 내에서 차지하는 위치 (0=하단 끝, 1=상단 끝). 0.5 중앙값 배제.
  const pVals = [0.2, 0.25, 0.3, 0.35, 0.4, 0.6, 0.65, 0.7, 0.75, 0.8];
  const p     = pVals[_hashStr(factionId || String(score)) % 10];
  const W     = 2 * halfRange * base;
  const lo    = Math.round((base - p * W) / 500) * 500;
  const hi    = Math.round((base + (1 - p) * W) / 500) * 500;
  const fmt   = n => n >= 10000 ? `${Math.floor(n / 1000)}천` : n.toLocaleString();
  return `약 ${fmt(lo)}~${fmt(hi)}명`;
}

/** 6개월마다 intel_level > 0인 세력의 첩보 수준을 1 감쇠. 모든 시나리오에서 호출. */
function defaultOnTurnEnd(state) {
  const year  = _parseYear(state.progress?.timestamp);
  const month = _parseMonth(state.progress?.timestamp);
  const m     = _totalMonths(year, month);
  if (m == null) return;
  if (!state.flags) state.flags = {};
  for (const f of state.factions.values()) {
    if (f.defeated || (f.intel_level ?? 0) <= 0) continue;
    const key  = `intel_decay_${f.id}_last`;
    const last = state.flags[key];
    if (last == null) { state.flags[key] = m; continue; }
    if (m - last >= 6) {
      f.intel_level = Math.max(0, (f.intel_level ?? 1) - 1);
      state.flags[key] = m;
    }
  }
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
          // 플레이어 본인 병력은 추정 범위가 아니라 확인된 야전군을 우선 표시
          strength = f.field_army != null
            ? formatTroops(f.field_army)
            : (score != null && tpp != null)
              ? formatTroops(Math.round(score * tpp))
              : (STRENGTH_LABEL[f.strength] || '불명');
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
      strength = formatStrengthScore(score, tpp, friendly[0].intel_level ?? 0, friendly[0].id)
                 || STRENGTH_LABEL[friendly[0].strength] || '불명';
    }
  }

  return { name, sub, fields: [
    { key: '직위', val: title },
    { key: '병력', val: strength },
    { key: '거점', val: base },
  ]};
}

function defaultMapMarkerStyle(loc, state) {
  if (loc.controller === 'contested') return { color: '#EF9F27', statusText: '불안정' };
  const faction = state.factions.get(loc.controller);
  const color   = faction?.color || '#888780';
  const disp    = faction?.disposition;
  if (disp === '우호') {
    const char = state.characters.get(state.protagonist);
    const homeFactionId = char?.faction_id || char?.faction
      || (state.factions.has(state.protagonist) ? state.protagonist : null);
    if (homeFactionId && loc.controller === homeFactionId) {
      return { color, statusText: '본국 영토' };
    }
    return { color, statusText: '동맹 거점' };
  }
  if (disp === '적대') return { color, statusText: '적 점거' };
  return { color, statusText: '중립' };
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
    factionBarTag(faction, state) {
      if (faction.id === state?.protagonist) return '아군';
      return { 우호: '우호', 적대: '적대', 중립: '중립' }[faction.disposition] || '불명';
    },

    mapMarkerStyle: defaultMapMarkerStyle,

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

    initDispositions(_state) { /* 시나리오 데이터에 이미 설정됨 */ },
    onInit: defaultOnInit,
    onTurnEnd: defaultOnTurnEnd,
  },

  // ── 뇌제의 후계자 ─────────────────────────────────────────────
  'ottoman-interregnum': {
    tagExtras: { '경쟁': ['#faeeda', '#854f0b'], '숙적': ['#fcebeb', '#a32d2d'], '동맹': ['#e6f1fb', '#185fa5'] },

    commanderInfo: defaultCommanderInfo,

    charDotColor(char, state) {
      if (char.color) return char.color;
      const factionId = char.faction_id
        || (state.factions.has(char.id) ? char.id : null);
      return state.factions.get(factionId)?.color || '#888780';
    },
    charRelInfo(char, state) {
      if (char.id === state.protagonist) return { cls: 'rel-player', label: '플레이어' };
      // 외부 세력 소속(faction_id 또는 char.id가 세력 ID)이면 해당 세력의 외교 관계를 따름
      const externalFactionId = char.faction_id
        || (state.factions.has(char.id) ? char.id : null);
      const faction = externalFactionId ? state.factions.get(externalFactionId) : null;
      const disp = faction ? faction.disposition : (char.disposition ?? '중립');
      return (
        disp === '동맹'   ? { cls: 'rel-ally', label: '동맹' } :
        disp === '우호'   ? { cls: 'rel-coop', label: '협력' } :
        disp === '중립'   ? { cls: 'rel-unk',  label: '중립' } :
        disp === '비우호' ? { cls: 'rel-dist', label: '경쟁' } :
        disp === '적대'   ? { cls: 'rel-host', label: '숙적' } :
                            { cls: 'rel-dist', label: '불명' }
      );
    },

    /** 세력 데이터의 color 필드 사용 */
    factionBarColor(faction) { return faction.color || '#888780'; },
    factionBarTag(faction, state) {
      if (faction.id === state?.protagonist) return '아군';
      return { 동맹: '동맹', 우호: '우호', 중립: '중립', 비우호: '경쟁', 적대: '숙적' }[faction.disposition] || '불명';
    },

    mapMarkerStyle(loc, state) {
      if (loc.controller === 'contested') return { color: '#EF9F27', statusText: '불안정' };
      const faction = state.factions.get(loc.controller);
      const color   = faction?.color || '#888780';
      const disp    = faction?.disposition;
      if (disp === '동맹') return { color, statusText: '동맹 거점' };
      if (disp === '우호') return { color, statusText: '우호 거점' };
      if (disp === '비우호') return { color, statusText: '경쟁 세력' };
      if (disp === '적대')   return { color, statusText: '숙적' };
      return { color, statusText: '중립' };
    },

    /** trigger_condition / end_condition을 평가해 현재 시점에 활성화된 이벤트만 반환 */
    getEvents(state) {
      const year      = _parseYear(state.progress?.timestamp);
      const factions  = state.factions;
      const princeFactionIds = Array.from(factions.values())
        .filter(f => f.type === 'faction').map(f => f.id);
      const controllersInUse = new Set(
        Array.from(state.locations.values()).map(l => l.controller)
      );
      // 1패스: 기본 컨텍스트 (세력·진행 변수)
      const baseContext = {
        ..._buildEventConditionContext(state, year),
        active_princes: princeFactionIds
          .filter(id => id !== state.protagonist && !factions.get(id)?.defeated).length,
        has_exiled_prince: princeFactionIds.some(id => {
          if (controllersInUse.has(id)) return false;
          return (factions.get(id)?.battle_damage ?? 0) > 0;
        }),
      };
      // 무사 루멜리아 흡수 완료 여부
      baseContext.musa_rumelia_boost_applied = state.flags?.musa_rumelia_boost_applied ?? false;
      // event_context.json 의 faction_vars 목록에 따라 {id}_defeated / {id}_score 추가
      for (const id of (state.eventContext?.faction_vars ?? [])) {
        const f = factions.get(id);
        baseContext[`${id}_defeated`] = f?.defeated ?? false;
        baseContext[`${id}_score`]    = f?.diplomacy_score ?? 0;
      }
      // 2패스: 이벤트 상태 변수 ({id}_active / {id}_ended) 를 기본 컨텍스트로 평가해 병합
      const context = { ...baseContext, ..._buildEventStateContext(state.events, baseContext) };
      return (state.events ?? [])
        .filter(ev => {
          if (ev.protagonist_only?.length && state.protagonist &&
              !ev.protagonist_only.includes(state.protagonist)) return false;
          return (
            _evaluateEventCondition(_eventConditionExpr(ev), context) &&
            !(ev.end_condition && _evaluateEventCondition(ev.end_condition, context))
          );
        })
        .map(ev => {
          let rows = (ev.effects ?? []).map(e => `${e.key}:${e.desc}`).join('|');
          if (ev.end_condition?.includes('active_princes'))
            rows += `|남은 경쟁자:${context.active_princes}명`;
          return { ...ev, rows };
        });
    },

    initDispositions(state) {
      for (const [id, char] of state.characters) {
        const factionId = char.faction_id || id;
        const faction   = state.factions.get(factionId);
        // 외부 세력 소속 인물만 세력 외교 상태를 따름; 주인공 진영 내부 인물은 개별 disposition 유지
        if (faction && faction.id !== state.protagonist) {
          char.disposition = faction.disposition;
        }
      }
    },

    onInit: defaultOnInit,

    onTurnEnd(state) {
      defaultOnTurnEnd(state);
      const year  = _parseYear(state.progress?.timestamp);
      const month = _parseMonth(state.progress?.timestamp);

      // 무스타파 세력 동적 등장 (1412년 이후)
      if (year >= 1412 && !state.factions.has('mustafa')) {
        state.addFaction({
          id: 'mustafa', name: '무스타파 왕자파', type: 'faction',
          strength_score: 180, field_army: Math.round(180 * (state.troopsPerPoint ?? 78)),
          disposition: '적대', color: '#9B59B6',
          notes: '티무르 진영에서 귀환한 바야지트의 아들 무스타파. 비잔틴과 루멜리아 일부 귀족의 지원을 받아 정통 계승권을 내세우며 세력을 구축했다. 공위 분쟁을 끝낸 왕자에게도 즉각적인 도전이 된다.',
        });
      }

      // 불가리아 대봉기 동적 등장 (1415년 이후, 술레이만 외 주인공)
      if (year >= 1415 && state.protagonist !== 'suleyman' &&
          !state.factions.has('bulgarian-rebels')) {
        state.addFaction({
          id: 'bulgarian-rebels', name: '불가리아 독립 반군', type: 'rebels',
          strength_score: 220, field_army: Math.round(220 * (state.troopsPerPoint ?? 78)),
          disposition: '적대', color: '#7B4F2E',
          notes: '오스만 내전의 장기화를 틈타 조직화된 트라키아·불가리아 기독교 귀족 연합. 초기 산발적 불만이 전면 봉기로 발전했으며, 루멜리아를 차지한 세력에게는 즉각적인 후방 위협이 된다.',
        });
      }

      const protagonist = state.factions.get(state.protagonist);
      if (!protagonist || protagonist.type === 'sultanate') return;
      // on_end_boost: 이벤트 시한 만료 시 생존 세력 전력 1회 증폭
      if (!state.flags) state.flags = {};
      for (const ev of state.events ?? []) {
        if (!ev.id || !ev.effects) continue;
        const flagKey = `${ev.id}_end_boost_applied`;
        if (state.flags[flagKey]) continue;
        for (const effect of ev.effects) {
          if (effect.type !== 'on_end_boost') continue;
          if (!_evaluateEventCondition(effect.trigger, { year })) continue;
          state.flags[flagKey] = true;
          for (const id of effect.targets ?? []) {
            const f = state.factions.get(id);
            if (f && !f.defeated) f.field_army = Math.round((f.field_army ?? 0) * (1 + effect.value));
          }
        }
      }

      // 활성 이벤트 목록 — 이하 여러 로직에서 재사용
      const activeEvents = this.getEvents(state);

      // 무사: 루멜리아 거점 확보 후 3개월 생존 → 술레이만 반대파 흡수
      if (state.protagonist === 'musa' && !state.flags.musa_rumelia_boost_applied) {
        const inRumelia = Array.from(state.locations.values())
          .some(l => l.continent === '루멜리아' && l.controller === 'musa');
        if (inRumelia) {
          state.flags.musa_rumelia_arrival_months ??= _totalMonths(year, month);
        }
        const am = state.flags.musa_rumelia_arrival_months;
        const cm = _totalMonths(year, month);
        if (am != null && cm != null && cm >= am + 3) {
          state.flags.musa_rumelia_boost_applied = true;
          const musa = state.factions.get('musa');
          if (musa) musa.field_army = (musa.field_army ?? 0) + Math.round(100 * (state.troopsPerPoint ?? 78));
        }
      }

      // 티무르 경고 6개월 방치 → 원정군 등장
      if (!state.flags.timur_expedition_triggered) {
        if (activeEvents.some(ev => ev.id === 'timur_warning')) {
          state.flags.timur_warning_total_months ??= _totalMonths(year, month);
        }
        const wm = state.flags.timur_warning_total_months;
        const cm = _totalMonths(year, month);
        if (wm != null && cm != null && cm >= wm + 6 &&
            !state.factions.has('timur_expedition')) {
          state.flags.timur_expedition_triggered = true;
          // 플레이어와 적대하는 원정군 등장; 우호 세력도 진격 경로에서 위협받음
          const alliedIds = Array.from(state.factions.values())
            .filter(f => f.disposition === '우호' || f.disposition === '동맹')
            .map(f => f.id);
          state.addFaction({
            id: 'timur_expedition', name: '티무르 원정군', type: 'empire',
            strength_score: 700, field_army: Math.round(700 * (state.troopsPerPoint ?? 78)),
            disposition: '적대', color: '#5C2A0A', is_dynamic: true,
            notes: `경고를 묵살한 왕자를 응징하기 위해 사마르칸트에서 출발한 티무르의 원정군. 아나톨리아 어느 세력보다 압도적인 전력을 보유하며, 진격 경로의 세력(${alliedIds.join('·') || '동맹 없음'})도 위협 대상이다. 정면 대결은 전멸, 외교적 복속 또는 연합 방어만이 생존 가능성을 열어준다.`,
          });
          state.flags.pendingCrisis = {
            scene_override: [
              '**[긴급] 티무르의 원정군이 아나톨리아 국경을 돌파했다**',
              '',
              '경고를 묵살한 대가가 현실이 됐다. 사마르칸트에서 출발한 티무르의 응징군이 동부 국경을 넘었다는 급보가 각지에서 동시에 전해졌다. 전력 700 — 지금의 아나톨리아 어느 세력도 홀로 맞설 수 없는 규모다. 진격 경로에 놓인 우방들도 공포에 떨며 입장 표명을 미루고 있다.',
              '',
              '정면 충돌은 전멸과 같다. **지금 이 순간 어떻게 대응할 것인가?**',
            ].join('\n'),
            user_prompt_hint: '티무르 원정군에 대한 즉각 대응책을 결정한다.',
          };
        }
      }

      // 활성 이벤트의 faction_growth 효과 적용
      for (const ev of activeEvents) {
        for (const effect of ev.effects ?? []) {
          if (effect.type !== 'faction_growth') continue;
          // annual: 해당 연도에 이미 적용했으면 스킵
          if (effect.frequency === 'annual') {
            const flagKey = `${ev.id}_${effect.target}_growth_year`;
            if (state.flags[flagKey] === year) continue;
            state.flags[flagKey] = year;
          }
          const f = state.factions.get(effect.target);
          if (f && !f.defeated) f.field_army = (f.field_army ?? 0) + Math.round(effect.value * (state.troopsPerPoint ?? 78));
        }
      }

      // 경쟁 왕자가 남아 있으면 스킵 (공위 분쟁 진행 중)
      const remainingPrinces = Array.from(state.factions.values())
        .filter(f => f.type === 'faction' && !f.defeated && f.id !== state.protagonist).length;
      if (remainingPrinces > 0) return;
      Object.assign(protagonist, {
        name:  '오스만 술탄국',
        type:  'sultanate',
        color: '#8B1A1A',
        notes: '공위 분쟁을 종식하고 세워진 통합 오스만 술탄국. 왕좌의 정통성은 확립됐으나, 아나톨리아 재건과 잔존 베이릭 복속이 새로운 과제로 떠오른다.',
      });
    },
  },
};

// ── 공개 API ─────────────────────────────────────────────────────
window.getScenarioUI      = function (scenarioId) {
  return CONFIGS[scenarioId] || CONFIGS['great-heathen-army'];
};
window.formatTroops       = formatTroops;
window.formatStrengthScore = formatStrengthScore;

})();
