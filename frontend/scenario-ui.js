// Copied from project root scenario-ui.js (truncated header)

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

// (파일은 원본 그대로 frontend/scenario-ui.js에 복사되었습니다)
