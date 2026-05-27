// ── 미저장 상태 추적
// commitTurn 호출 시 true, 서버 저장 성공 시 false
window._serverUnsaved = false;
let _pendingNavTarget = null;

// ── 미저장 경고 모달 ─────────────────────────────────────────────────────────

function showUnsavedModal(target) {
  _pendingNavTarget = target;
  const btn = document.getElementById('unsaved-save-btn');
  if (btn) { btn.textContent = '저장 후 나가기'; btn.disabled = false; }
  document.getElementById('unsaved-backdrop').classList.add('active');
}

function closeUnsavedModal() {
  document.getElementById('unsaved-backdrop').classList.remove('active');
  _pendingNavTarget = null;
}

function confirmExit() {
  window._serverUnsaved = false;  // beforeunload / popstate 재발동 방지
  closeUnsavedModal();
  if (_pendingNavTarget === '__back__') {
    history.go(-2);               // 가드 스테이트 2개를 건너뛰어 이전 페이지로
  } else {
    window.location.href = _pendingNavTarget || 'main_menu.html';
  }
}

async function saveAndExit() {
  if (!_state) { confirmExit(); return; }
  const btn = document.getElementById('unsaved-save-btn');
  btn.textContent = '저장 중…'; btn.disabled = true;
  try {
    await GameAPI.createSave(_state.toJSON());
    window._serverUnsaved = false;
    // save-btn 텍스트도 동기화
    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) saveBtn.textContent = '저장됨 ✓';
    closeUnsavedModal();
    if (_pendingNavTarget === '__back__') {
      history.go(-2);
    } else {
      window.location.href = _pendingNavTarget || 'main_menu.html';
    }
  } catch {
    btn.textContent = '저장 실패';
    setTimeout(() => { btn.textContent = '저장 후 나가기'; btn.disabled = false; }, 1800);
  }
}

/** 메뉴 버튼 클릭 핸들러 — 미저장이면 모달, 아니면 바로 이동 */
function tryNavigateToMenu() {
  if (window._serverUnsaved) {
    showUnsavedModal('main_menu.html');
  } else {
    window.location.href = 'main_menu.html';
  }
}

// ── 저장
async function saveToServer() {
  if (!_state) return;
  const btn = document.getElementById('save-btn');
  btn.textContent = '저장 중…'; btn.disabled = true;
  try {
    await GameAPI.createSave(_state.toJSON());
    window._serverUnsaved = false;
    btn.textContent = '저장됨 ✓';
    setTimeout(() => { btn.textContent = '저장'; btn.disabled = false; }, 1800);
  } catch {
    btn.textContent = '저장 실패';
    setTimeout(() => { btn.textContent = '저장'; btn.disabled = false; }, 1800);
  }
}

// ── 선택지
let _selectedActionType = null;

function selectChoice(btn) {
  document.querySelectorAll('.choice-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  document.getElementById('cmd').value = btn.textContent.trim();
  _selectedActionType = btn.dataset.actionType || null;
}

// ── LLM 생성 NPC 외정 스탯 자동 배정 (정규분포, 중심 C)
const _EXT_STAT_KEYS = ['통솔', '지략', '외교', '무력'];
// _GRADE_SCALE은 /api/config에서 로드 (resolver.py의 _GRADE_SCALE과 동기).
// loadGameConfig() 실패 시 fallback으로 내장 값 사용.
const _GRADE_SCALE_FALLBACK = ['F','E-','E','E+','D-','D','D+','C-','C','C+','B-','B','B+','A-','A','A+','S'];
const _GRADE_CENTER = 8; // C 인덱스 (resolver.py: _GRADE_BASELINE = 8)
const _GRADE_STD    = 3;

function _getGradeScale() {
  return window._gameConfig?.gradeScale ?? _GRADE_SCALE_FALLBACK;
}

function _gauss() {
  let u, v;
  do { u = Math.random(); } while (u === 0);
  do { v = Math.random(); } while (v === 0);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function _randomGrade() {
  const scale = _getGradeScale();
  const idx   = Math.round(_GRADE_CENTER + _GRADE_STD * _gauss());
  return scale[Math.max(0, Math.min(scale.length - 1, idx))];
}

function _assignExternalStats(char) {
  if (!char.stats) char.stats = {};
  for (const key of _EXT_STAT_KEYS) {
    if (char.stats[key] == null) char.stats[key] = _randomGrade();
  }
}

// ── 공통 상태 업데이트 (submitTurn + combat-ui.js 가 공유)
function applyStateUpdates(su) {
  Object.assign(_state.progress, {
    timestamp:    su.timestamp     || _state.progress.timestamp,
  });

  if (Array.isArray(su.new_characters)) {
    for (const c of su.new_characters) {
      if (c.id && !_state.characters.has(c.id)) {
        _assignExternalStats(c);
        _state.addCharacter(c);
      }
    }
  }
  if (Array.isArray(su.dead_characters)) {
    for (const id of su.dead_characters) {
      if (_state.characters.has(id)) _state.killCharacter(id);
    }
  }
  if (Array.isArray(su.defeated_factions)) {
    for (const id of su.defeated_factions) _state.defeatFaction(id);
  }
  if (Array.isArray(su.new_factions)) {
    for (const f of su.new_factions) {
      if (f.id && !_state.factions.has(f.id)) _state.addFaction(f);
    }
  }
  if (Array.isArray(su.faction_field_army_changes)) {
    for (const fc of su.faction_field_army_changes) {
      const faction = _state.factions.get(fc.id);
      if (faction && fc.delta != null) faction.field_army = Math.max(0, (faction.field_army ?? 0) + fc.delta);
    }
  }
  if (su.faction_strength_overrides && typeof su.faction_strength_overrides === 'object') {
    for (const [fid, score] of Object.entries(su.faction_strength_overrides)) {
      const faction = _state.factions.get(fid);
      if (faction) faction.strength_score = score;
    }
  }
  if (Array.isArray(su.faction_battle_damage)) {
    for (const fc of su.faction_battle_damage) {
      if (fc.id && fc.damage != null) _state.addFactionBattleDamage(fc.id, fc.damage);
    }
  }
  if (Array.isArray(su.faction_battle_recovery)) {
    for (const fc of su.faction_battle_recovery) {
      if (fc.id && fc.amount != null) _state.recoverFactionBattleDamage(fc.id, fc.amount);
    }
  }
  if (Array.isArray(su.character_troop_changes)) {
    for (const tc of su.character_troop_changes) {
      if (tc.id && tc.delta != null) _state.updateCharacterTroops(tc.id, tc.delta);
    }
  }
  if (Array.isArray(su.new_locations)) {
    for (const l of su.new_locations) {
      if (l.id && !_state.locations.has(l.id)) _state.addLocation(l);
    }
  }
  if (Array.isArray(su.location_changes)) {
    for (const lc of su.location_changes) {
      const loc = _state.locations.get(lc.id);
      if (!loc) continue;
      if (lc.controller && _state.factions.has(lc.controller)) loc.controller = lc.controller;
      if (typeof lc.garrison_modifier === 'number') loc.garrison_modifier = lc.garrison_modifier;
      if (typeof lc.garrison === 'number') loc.garrison = lc.garrison;
      if ('conquered_at' in lc) {
        if (lc.conquered_at === null) delete loc.conquered_at;
        else loc.conquered_at = lc.conquered_at;
      }
      if ('conquest_disposition' in lc) {
        if (lc.conquest_disposition === null) delete loc.conquest_disposition;
        else loc.conquest_disposition = lc.conquest_disposition;
      }
    }
  }
  if (Array.isArray(su.faction_diplomacy_changes)) {
    for (const fc of su.faction_diplomacy_changes) {
      if (fc.id && fc.delta != null) _state.updateFactionDiplomacy(fc.id, fc.delta);
    }
  }
  if (Array.isArray(su.character_disposition_changes)) {
    for (const cc of su.character_disposition_changes) {
      const char = _state.characters.get(cc.id);
      if (char && cc.disposition) char.disposition = cc.disposition;
      const faction = _state.factions.get(cc.id);
      if (faction && cc.disposition) {
        faction.disposition     = cc.disposition;
        faction.diplomacy_score = GameState._dispositionToScore(cc.disposition);
      }
    }
  }
  if (Array.isArray(su.character_title_changes)) {
    for (const tc of su.character_title_changes) {
      const char = _state.characters.get(tc.id);
      if (char && tc.title) char.title = tc.title;
    }
  }
  if (Array.isArray(su.faction_intel_changes)) {
    for (const ic of su.faction_intel_changes) {
      if (ic.id && ic.delta != null) _state.updateFactionIntel(ic.id, ic.delta);
    }
  }
  if (Array.isArray(su.faction_income_changes)) {
    for (const ic of su.faction_income_changes) {
      const faction = _state.factions.get(ic.id);
      if (!faction) continue;
      if (ic.income_mult_delta != null)
        faction.income_mult = Math.max(0, (faction.income_mult ?? 1.0) + ic.income_mult_delta);
      if (ic.income_flat_delta != null)
        faction.income_flat = (faction.income_flat ?? 0) + ic.income_flat_delta;
    }
  }
  if (su.treasury_update && typeof su.treasury_update === 'object') {
    const faction = _state.factions.get(su.treasury_update.id);
    if (faction && su.treasury_update.value != null)
      faction.treasury = su.treasury_update.value;
  }
  if (typeof su.player_location_id === 'string' && _state.locations.has(su.player_location_id)) {
    _state.progress.playerLocationId = su.player_location_id;
  }
  if (su.combat_state !== undefined) {
    _state.combatState = su.combat_state;
  }
  if (su.diplomacy_state !== undefined) {
    _state.diplomacyState = su.diplomacy_state;
  }
  if (typeof su.weather === 'string') {
    _state.weather = su.weather;
  }
  if (su.event_state_changes && typeof su.event_state_changes === 'object') {
    _state.eventStates = { ...su.event_state_changes };
  }
  if (Array.isArray(su.pending_conquest_dispositions)) {
    _state.pendingConquestDispositions = su.pending_conquest_dispositions;
  }
  if (su.lost_battles && typeof su.lost_battles === 'object') {
    _state.lostBattles = { ..._state.lostBattles, ...su.lost_battles };
  }
  if (su.flags_update && typeof su.flags_update === 'object') {
    _state.flags = { ...(_state.flags || {}), ...su.flags_update };
  }
}

// ── 턴 전진
async function submitTurn() {
  const cmd = document.getElementById('cmd').value.trim();
  if (!cmd || !_state || !_manager) return;

  const actionType = _selectedActionType;
  _selectedActionType = null;

  document.getElementById('cmd').value = '';
  document.querySelectorAll('.choice-btn').forEach(b => b.classList.remove('selected'));
  showLoading();

  try {
    const { content, state_updates: su, resolution, _debug } = await GameAPI.submitTurn(cmd, _state.toJSON(), _state.getHistory(), false, false, actionType);
    renderResolution(resolution);

    commitTurn(cmd, content, su);

    renderAll(_state);

    // 외교 전용 UI 미완성 — diplomacy_state가 반환되어도 일반 씬으로 렌더링
    // TODO: 외교 시스템 완성 후 아래 블록으로 교체
    // if (su.diplomacy_state != null) {
    //   openDiplomacyOverlay(content, resolution, _debug);
    //   return;
    // }

    // 전투 돌입 감지 → 전투 오버레이 열기
    if (_state.combatState?.active) {
      openCombatOverlay(content, resolution, _debug);
      return;
    }

    // 일반 턴 렌더링
    const pendingCrisis = _state.flags?.pendingCrisis;
    if (pendingCrisis) {
      delete _state.flags.pendingCrisis;
      renderSceneBody(markdownToHtml(pendingCrisis.scene_override));
      renderChoices([]);
      const cmdEl = document.getElementById('cmd');
      if (cmdEl && pendingCrisis.user_prompt_hint) cmdEl.value = pendingCrisis.user_prompt_hint;
    } else {
      renderSceneBody(markdownToHtml(extractNarrative(content)));
      renderChoices(extractChoices(content));
    }

    renderDebugPanel(document.getElementById('scene-body'), resolution, _debug);

  } catch (err) {
    renderSceneBody(
      `<p style="color:var(--text-secondary);font-family:sans-serif;font-size:12px;padding:6px 0;">` +
      `⚠ 서버 연결 오류: ${err.message}</p>`
    );
  }
}
