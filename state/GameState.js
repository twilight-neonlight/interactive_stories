/**
 * state/GameState.js
 *
 * 시나리오 초기 데이터를 받아 게임 상태를 초기화하는 클래스.
 * characters, factions, locations를 각각 Map<id, object>으로 관리합니다.
 */

// ─────────────────────────────────────────────
// @typedef
// ─────────────────────────────────────────────

/**
 * @typedef {'alive'|'dead'|'unknown'|'exiled'} CharacterStatus
 */

/**
 * @typedef {Object} StateCharacter
 * @property {string}          id         - 고유 식별자
 * @property {string}          name       - 이름
 * @property {CharacterStatus} status     - 현재 상태
 * @property {boolean}         [is_dynamic] - true: 게임 중 동적으로 추가된 인물
 * @property {*}               [...]      - scenarios의 Character 필드 그대로 포함
 */

/**
 * @typedef {Object} StateFaction
 * @property {string}  id          - 고유 식별자
 * @property {string}  name        - 세력명
 * @property {string}  disposition - 플레이어에 대한 현재 태도
 * @property {boolean} [is_dynamic] - true: 게임 중 동적으로 추가된 세력
 * @property {*}       [...]       - scenarios의 Faction 필드 그대로 포함
 */

/**
 * @typedef {Object} StateLocation
 * @property {string}  id          - 고유 식별자
 * @property {string}  name        - 지명
 * @property {string}  controller  - 현재 지배 세력
 * @property {boolean} [is_dynamic] - true: 게임 중 동적으로 추가된 거점
 * @property {*}       [...]       - scenarios의 Location 필드 그대로 포함
 */

/**
 * @typedef {Object} SceneProgress
 * @property {number}  chapter       - 현재 장 번호 (1부터)
 * @property {number}  scene         - 현재 씬 번호 (1부터, LLM이 직접 지정)
 * @property {string}  chapterTitle  - 현재 장 제목 (LLM 응답에서 추출)
 * @property {string}  timestamp     - 현재 씬 시각·장소 (예: "868년 9월, 노팅엄 외곽")
 * @property {boolean} isChapterEnd  - 장 종결 여부
 */

/**
 * @typedef {Object} SerializedGameState
 * @property {string}        scenarioId
 * @property {string}        scenarioTitle
 * @property {string|null}   protagonist  - 선택된 캐릭터 id (fixed 시나리오는 null)
 * @property {SceneProgress} progress
 * @property {Object<string, StateCharacter>} characters
 * @property {Object<string, StateFaction>}   factions
 * @property {Object<string, StateLocation>}  locations
 */

// ─────────────────────────────────────────────
// GameState
// ─────────────────────────────────────────────

class GameState {
  /**
   * @param {import('../scenarios/index.js').Scenario} scenario
   * @param {string|null} [protagonistId]
   */
  constructor(scenario, protagonistId = null) {
    this.scenarioId    = scenario.id;
    this.scenarioTitle = scenario.title;
    this.protagonist   = protagonistId;

    /** @type {SceneProgress} */
    this.progress = {
      chapter:      1,
      scene:        1,
      chapterTitle: '',
      timestamp:    '',
      isChapterEnd: false,
    };

    /**
     * 대화 히스토리. API 호출 시 messages 배열로 그대로 전달합니다.
     * @type {{role: 'user'|'assistant', content: string}[]}
     */
    this.history = [];

    /** @type {Map<string, StateCharacter>} */
    this.characters = new Map();
    /** @type {Map<string, StateFaction>} */
    this.factions   = new Map();
    /** @type {Map<string, StateLocation>} */
    this.locations  = new Map();

    // 시나리오 UI 데이터 (직렬화하지 않음 — 게임 진입 시 매번 재주입)
    this.mapSvg  = scenario.map_svg  ?? '';
    this.opening = scenario.opening  ?? {};
    this.npcPool = scenario.npc_pool ?? {};

    /** @type {Array} 동시 진행 세계 사건 (events.json) */
    this.events  = scenario.events   ?? [];

    // 시나리오 초기값을 깊은 복사해서 Map으로 변환
    for (const char of scenario.characters ?? []) {
      this.characters.set(char.id, {
        ...structuredClone(char),
        status: 'alive',
      });
    }
    for (const faction of scenario.factions ?? []) {
      this.factions.set(faction.id, structuredClone(faction));
    }
    for (const location of scenario.locations ?? []) {
      this.locations.set(location.id, structuredClone(location));
    }
  }

  // ── 장/씬 ─────────────────────────────────

  /**
   * LLM이 내려준 씬 번호로 progress.scene을 직접 설정합니다.
   * @param {number} n
   */
  advanceScene(n) {
    this.progress.scene = n;
  }

  /**
   * 다음 장으로 넘어갑니다.
   * @param {string} title - 새 장의 제목 (LLM 응답에서 추출)
   */
  advanceChapter(title) {
    this.progress.chapter     += 1;
    this.progress.scene        = 1;
    this.progress.chapterTitle = title;
    this.progress.isChapterEnd = false;
  }

  /**
   * 현재 장을 종결 상태로 표시합니다.
   */
  markChapterEnd() {
    this.progress.isChapterEnd = true;
  }

  /**
   * 현재 씬의 시각·장소 문자열을 설정합니다.
   * @param {string} str - 예: "868년 9월, 노팅엄 외곽"
   */
  setTimestamp(str) {
    this.progress.timestamp = str;
  }

  // ── 히스토리 ──────────────────────────────

  /**
   * 대화 히스토리에 메시지를 추가합니다.
   * @param {'user'|'assistant'} role
   * @param {string} content
   */
  pushHistory(role, content) {
    this.history.push({ role, content });
  }

  /**
   * 대화 히스토리 전체를 반환합니다. API 호출 시 messages 배열로 사용합니다.
   * @returns {{role: 'user'|'assistant', content: string}[]}
   */
  getHistory() {
    return this.history;
  }

  // ── 캐릭터 ────────────────────────────────

  /**
   * 게임 중 새 인물을 동적으로 추가합니다.
   * @param {Omit<StateCharacter, 'is_dynamic'>} character
   */
  addCharacter(character) {
    this.characters.set(character.id, {
      ...structuredClone(character),
      status: character.status ?? 'alive',
      is_dynamic: true,
    });
  }

  /**
   * 인물의 상태를 'dead'로 변경합니다.
   * @param {string} id
   */
  killCharacter(id) {
    const char = this.characters.get(id);
    if (!char) throw new Error(`캐릭터 '${id}'를 찾을 수 없습니다.`);
    char.status = 'dead';
  }

  /**
   * status가 'alive'인 캐릭터만 반환합니다.
   * @returns {StateCharacter[]}
   */
  getActiveCharacters() {
    return Array.from(this.characters.values()).filter(c => c.status === 'alive');
  }

  // ── 세력 ──────────────────────────────────

  /**
   * 게임 중 새 세력을 동적으로 추가합니다.
   * @param {Omit<StateFaction, 'is_dynamic'>} faction
   */
  addFaction(faction) {
    this.factions.set(faction.id, {
      ...structuredClone(faction),
      is_dynamic: true,
    });
  }

  // ── 거점 ──────────────────────────────────

  /**
   * 게임 중 새 거점을 동적으로 추가합니다.
   * @param {Omit<StateLocation, 'is_dynamic'>} location
   */
  addLocation(location) {
    this.locations.set(location.id, {
      ...structuredClone(location),
      is_dynamic: true,
    });
  }

  // ── 직렬화 ────────────────────────────────

  /**
   * Map을 plain object로 변환해 직렬화 가능한 형태로 반환합니다.
   * @returns {SerializedGameState}
   */
  toJSON() {
    return {
      scenarioId:    this.scenarioId,
      scenarioTitle: this.scenarioTitle,
      protagonist:   this.protagonist,
      progress:      { ...this.progress },
      history:       this.history.slice(),
      characters:    Object.fromEntries(this.characters),
      factions:      Object.fromEntries(this.factions),
      locations:     Object.fromEntries(this.locations),
      events:        this.events.slice(),
    };
  }

  /**
   * 직렬화된 데이터로부터 GameState 인스턴스를 복원합니다.
   * @param {SerializedGameState} data
   * @returns {GameState}
   */
  static fromJSON(data) {
    const state           = Object.create(GameState.prototype);
    state.scenarioId      = data.scenarioId;
    state.scenarioTitle   = data.scenarioTitle;
    state.protagonist     = data.protagonist;
    state.progress        = {
      chapter:      data.progress?.chapter      ?? 1,
      scene:        data.progress?.scene        ?? 1,
      chapterTitle: data.progress?.chapterTitle ?? '',
      timestamp:    data.progress?.timestamp    ?? '',
      isChapterEnd: data.progress?.isChapterEnd ?? false,
    };
    state.history         = Array.isArray(data.history) ? data.history.slice() : [];
    state.characters      = new Map(Object.entries(data.characters));
    state.factions        = new Map(Object.entries(data.factions));
    state.locations       = new Map(Object.entries(data.locations));
    state.events          = Array.isArray(data.events) ? data.events.slice() : [];
    // UI 전용 데이터는 직렬화 대상 아님 — game.html에서 scenario fetch 후 재주입
    state.opening = {};
    state.npcPool = {};
    return state;
  }
}

// file:// 호환을 위해 전역 노출
// 백엔드 연동(모듈 사용) 시 이 줄을 제거하고 파일 상단에 export class GameState 추가
window.GameState = GameState;
