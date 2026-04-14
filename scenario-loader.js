/**
 * scenario-loader.js — 시나리오 데이터 로더
 *
 * type="module" 없이 일반 <script>로 로드합니다.
 * ScenarioLoader와 SECTIONS을 window에 전역으로 노출합니다.
 *
 * 데이터 편집: backend/scenarios/*.json 파일을 직접 수정하세요.
 */

// ─────────────────────────────────────────────
// 백엔드 URL
// ─────────────────────────────────────────────
const API_BASE = 'http://localhost:8000';

// ─────────────────────────────────────────────
// 섹션 정의 (표시 순서 및 레이블)
// ─────────────────────────────────────────────
window.SECTIONS = [
  { id: 'history', label: '역사 기반' },
  { id: 'fantasy', label: '판타지 · 창작 세계' },
];

// ─────────────────────────────────────────────
// ScenarioLoader
// ─────────────────────────────────────────────
window.ScenarioLoader = {

  async fetchAll() {
    const res = await fetch(`${API_BASE}/api/scenarios`);
    if (!res.ok) throw new Error('시나리오 목록을 불러오지 못했습니다.');
    return res.json();
  },

  async fetchOne(scenarioId) {
    const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}`);
    if (!res.ok) throw new Error(`시나리오 '${scenarioId}'를 불러오지 못했습니다.`);
    return res.json();
  },

  async fetchCharacters(scenarioId) {
    const scenario = await this.fetchOne(scenarioId);
    return scenario.characters ?? [];
  },

  async fetchGrouped() {
    const all = await this.fetchAll();
    return window.SECTIONS
      .map(section => ({
        section,
        scenarios: all.filter(s => s.section === section.id),
      }));
  },
};
