/**
 * state/StateManager.js
 *
 * GameState 인스턴스를 생성·저장·불러오는 레이어.
 * 퍼시스턴스 어댑터 패턴으로 추상화되어 있어
 * SessionStorageAdapter → ApiAdapter 교체가 어댑터 한 줄 변경으로 가능합니다.
 *
 * 로드 순서: GameState.js → StateManager.js
 */

// ━━━ [LOCAL-ONLY] ━━━━━━━━━━━━━━━━━━━━━━━━━━━
// sessionStorage 기반 어댑터.
// 백엔드 연동 시 이 블록 전체를 삭제하고 [BACKEND] ApiAdapter를 활성화하세요.

class SessionStorageAdapter {
  /** @param {string} [key] */
  constructor(key = 'is_gameState') {
    this.key = key;
  }

  /** @param {import('./GameState.js').SerializedGameState} data */
  save(data) {
    sessionStorage.setItem(this.key, JSON.stringify(data));
  }

  /** @returns {import('./GameState.js').SerializedGameState|null} */
  load() {
    const raw = sessionStorage.getItem(this.key);
    return raw ? JSON.parse(raw) : null;
  }

  clear() {
    sessionStorage.removeItem(this.key);
  }
}

// ━━━ [/LOCAL-ONLY] ━━━━━━━━━━━━━━━━━━━━━━━━━━

// ━━━ [BACKEND] 백엔드 연동 시 아래 주석 해제 ━
//
// class ApiAdapter {
//   constructor(baseUrl = '/api/state') {
//     this.baseUrl = baseUrl;
//   }
//
//   async save(data) {
//     const res = await fetch(this.baseUrl, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify(data),
//     });
//     if (!res.ok) throw new Error('상태 저장에 실패했습니다.');
//   }
//
//   async load() {
//     const res = await fetch(this.baseUrl);
//     if (res.status === 404) return null;
//     if (!res.ok) throw new Error('상태 불러오기에 실패했습니다.');
//     return res.json();
//   }
//
//   async clear() {
//     await fetch(this.baseUrl, { method: 'DELETE' });
//   }
// }
//
// ━━━ [/BACKEND] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// ─────────────────────────────────────────────
// StateManager
// ─────────────────────────────────────────────

class StateManager {
  /**
   * @param {SessionStorageAdapter} [adapter]
   * 어댑터를 교체하려면 new StateManager(new ApiAdapter()) 로 생성하세요.
   */
  constructor(adapter) {
    // ── [LOCAL-ONLY] 백엔드 연동 시 SessionStorageAdapter → ApiAdapter로 교체 ──
    this.adapter = adapter ?? new SessionStorageAdapter();
    // ── [/LOCAL-ONLY] ────────────────────────────────────────────────────────
    this._state = null;
  }

  // ── 초기화 ────────────────────────────────

  /**
   * 시나리오 데이터로 새 GameState를 만들고 내부에 보관합니다.
   * @param {import('../scenarios/index.js').Scenario} scenario
   * @param {string|null} [protagonistId]
   * @returns {GameState}
   */
  init(scenario, protagonistId = null) {
    this._state = new GameState(scenario, protagonistId);
    return this._state;
  }

  // ── 상태 접근 ─────────────────────────────

  /**
   * 현재 GameState 인스턴스를 반환합니다.
   * init() 또는 load() 호출 전에는 null입니다.
   * @returns {GameState|null}
   */
  get state() {
    return this._state;
  }

  // ── 저장 / 불러오기 / 초기화 ─────────────

  /**
   * 현재 상태를 어댑터를 통해 저장합니다.
   */
  save() {
    if (!this._state) throw new Error('저장할 상태가 없습니다. init()을 먼저 호출하세요.');
    this.adapter.save(this._state.toJSON());
  }

  /**
   * 어댑터에서 상태를 불러와 GameState로 복원합니다.
   * 저장된 상태가 없으면 null을 반환합니다.
   * @returns {GameState|null}
   */
  load() {
    const data = this.adapter.load();
    if (!data) return null;
    this._state = GameState.fromJSON(data);
    return this._state;
  }

  /**
   * 메모리 상태와 어댑터 저장소를 모두 초기화합니다.
   */
  reset() {
    this._state = null;
    this.adapter.clear();
  }
}

// file:// 호환을 위해 전역 노출
// 백엔드 연동(모듈 사용) 시 이 줄을 제거하고 파일 상단에 export class StateManager 추가
window.StateManager = StateManager;

// ── 사용 예시 ─────────────────────────────────────────────
//
// const manager = new StateManager();          // SessionStorageAdapter 기본 사용
//
// // 시나리오 시작
// const scenario = window.ScenarioLoader.fetchAll().then(all => all[0]);
// manager.init(scenario, 'mehmed');            // 마흐메트로 시작
// manager.state.killCharacter('isa');          // 이사 사망 처리
// manager.save();                              // 저장
//
// // 페이지 재진입 시
// const state = manager.load();
// if (state) {
//   console.log(state.getActiveCharacters());  // 생존 캐릭터 목록
// }
