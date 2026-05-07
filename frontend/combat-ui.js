// combat-ui.js — 전투 전용 오버레이 모듈

let _combatEndContent    = null;
let _combatEndResolution = null;

function _combatSideStats(cs, fid, strengthKey) {
  const base = Number(cs?.[strengthKey] ?? 0);
  const pending = Number((cs?.pending_battle_damage || {})[fid] || 0);
  const remaining = Math.max(0, base - pending);
  const pct = base > 0 ? Math.max(0, Math.round(remaining / base * 100)) : 100;
  return { base, pending, remaining, pct };
}

function _renderCombatDebugPanel(container, resolution, debugData) {
  if (typeof renderDebugPanel === 'function') {
    renderDebugPanel(container, resolution, debugData);
  }
}

// ── 오버레이 열기 (전투 준비 단계 완료 시)
function openCombatOverlay(content, resolution, debugData = null) {
  const cs = _state.combatState;
  if (!cs) return;

  const pF     = _state.factions.get(cs.player_faction_id) || {};
  const eF     = _state.factions.get(cs.enemy_faction_id)  || {};
  const pName  = pF.name  || cs.player_faction_id || '아군';
  const eName  = eF.name  || cs.enemy_faction_id  || '적군';
  const pColor = pF.color || '#5DBB8B';
  const eColor = eF.color || '#E24B4A';

  const pCoalition = cs.player_coalition || [];
  const eCoalition = cs.enemy_coalition  || [];
  const pLabel = pCoalition.length ? pCoalition.join(' / ') : pName;
  const eLabel = eCoalition.length ? eCoalition.join(' / ') : eName;
  const pStats = _combatSideStats(cs, cs.player_faction_id, 'player_strength');
  const eStats = _combatSideStats(cs, cs.enemy_faction_id, 'enemy_strength');
  const phaseText = cs.max_phases
    ? `준비 완료 / 최대 ${cs.max_phases}페이즈`
    : `준비 완료 / 페이즈 ${cs.phase_number || 1}`;

  const locName  = cs.battle_location_name || null;
  const isSiege  = !!cs.is_siege;
  const battleTypeLabel = isSiege ? '공성전' : '전투';
  const locationTitle = locName
    ? `<div class="combat-location-title">${locName} ${battleTypeLabel}</div>`
    : '';

  const overlay = document.getElementById('combat-overlay');
  overlay.innerHTML = `
    <div class="combat-shell">
      <div>
        ${locationTitle}
        <div class="combat-title-row">
          <span class="combat-icon">⚔</span>
          <span class="combat-title-text">전투</span>
          <div class="combat-matchup">
            <span class="combat-fname" style="color:${pColor}">${pLabel}</span>
            <span class="combat-vs">vs</span>
            <span class="combat-fname" style="color:${eColor}">${eLabel}</span>
          </div>
          <span class="combat-phase-info" id="c-phase-info">${phaseText}</span>
          <button class="combat-retreat-btn" id="c-retreat-btn" onclick="combatRetreat()">후퇴</button>
        </div>
        <div class="combat-morale">
          <div class="morale-row">
            <span class="morale-label" style="color:${pColor}">아군 전력</span>
            <div class="morale-bar-wrap">
              <div class="morale-bar" id="c-player-bar" style="width:${pStats.pct}%;background:${pColor}"></div>
            </div>
            <span class="morale-val" id="c-player-val">${pStats.remaining}/${pStats.base}</span>
          </div>
          <div class="morale-row">
            <span class="morale-label" style="color:${eColor}">적군 전력</span>
            <div class="morale-bar-wrap">
              <div class="morale-bar" id="c-enemy-bar" style="width:${eStats.pct}%;background:${eColor}"></div>
            </div>
            <span class="morale-val" id="c-enemy-val">${eStats.remaining}/${eStats.base}</span>
          </div>
        </div>
      </div>

      <div class="combat-body">
        <div class="combat-log-col">
          <div class="combat-log-label">교전 기록</div>
          <div class="combat-log" id="c-log">
            <div style="color:var(--text-tertiary);font-size:11px;font-family:sans-serif;padding:4px 0">준비 단계</div>
          </div>
        </div>
        <div class="combat-scene-col">
          <div class="combat-res-badge" id="c-res-badge"></div>
          <div class="scene-body" id="c-scene" style="flex:1;min-height:0;overflow-y:auto;"></div>
        </div>
      </div>

      <div class="combat-footer" id="c-footer">
        <div class="choice-list" id="c-choices"></div>
        <hr class="divider">
        <div class="input-wrap">
          <textarea placeholder="전술 명령을 입력하세요…" id="c-cmd" maxlength="2000"></textarea>
          <button class="send-btn" id="c-send" onclick="submitCombatTurn()">전송</button>
        </div>
      </div>
    </div>
  `;

  overlay.classList.add('active');
  _combatEndContent    = null;
  _combatEndResolution = null;

  _renderCombatScene(content, resolution);
  _renderCombatDebugPanel(document.getElementById('c-scene'), resolution, debugData);

  document.getElementById('c-cmd')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitCombatTurn(); }
  });
}

// ── 오버레이 닫기 → 메인 게임으로 복귀 (일반 시나리오 전용)
function closeCombatOverlay() {
  document.getElementById('combat-overlay')?.classList.remove('active');

  if (_combatEndContent !== null) {
    renderAll(_state);
    renderResolution(_combatEndResolution);
    const content = _combatEndContent;
    if (_state.progress.isChapterEnd) {
      renderChapterClose(content);
    } else {
      renderSceneBody(markdownToHtml(extractNarrative(content)));
      renderChoices(extractChoices(content));
    }
    _combatEndContent    = null;
    _combatEndResolution = null;
  }
}

// ── 빠른 전투: 메인 화면으로
function qbGoMain() { window.location.href = 'main_menu.html'; }
// ── 빠른 전투: 다시 하기
function qbReplay() { window.location.href = 'quick-battle.html'; }

// ── 씬 텍스트 + 판정 배지 + 선택지
function _renderCombatScene(content, resolution) {
  const scene = document.getElementById('c-scene');
  if (scene) scene.innerHTML = markdownToHtml(extractNarrative(content));

  const badge = document.getElementById('c-res-badge');
  if (badge) {
    if (resolution && RESOLUTION_STYLE[resolution.tier_en]) {
      const s = RESOLUTION_STYLE[resolution.tier_en];
      badge.style.cssText = `display:inline-block;color:${s.color};border-color:${s.color};`;
      const luckShift = resolution.luck_shift ?? resolution.net;
      badge.textContent = resolution.tier_en === 'combat_luck'
        ? `${s.label} ${luckShift >= 0 ? '+' : ''}${luckShift}`
        : s.label;
      const modStr = resolution.modifiers?.length
        ? ' [' + resolution.modifiers.map(([l, v]) => `${l} ${v > 0 ? '+' : ''}${v}`).join(', ') + ']'
        : '';
      badge.title = resolution.roll != null
        ? resolution.tier_en === 'combat_luck'
          ? `1d100 ${resolution.roll} → ${resolution.luck_label || resolution.tier} (${luckShift >= 0 ? '+' : ''}${luckShift})`
          : `주사위 ${resolution.roll} → 보정 후 ${resolution.net}${modStr}`
        : modStr ? modStr.slice(2) : '';
    } else {
      badge.style.display = 'none';
    }
  }

  const choices    = extractChoices(content);
  const choiceList = document.getElementById('c-choices');
  if (choiceList) {
    choiceList.innerHTML = choices.map(c => {
      const type = _choiceActionType(c);
      const cls  = type ? `choice-btn choice-btn--${type}` : 'choice-btn';
      return `<button class="${cls}" onclick="selectCombatChoice(this)">${c}</button>`;
    }).join('');
  }
}

// ── 선택지 클릭
function selectCombatChoice(btn) {
  document.querySelectorAll('#c-choices .choice-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  const cmd = document.getElementById('c-cmd');
  if (cmd) cmd.value = btn.textContent.trim();
}

// ── 사기 바 + 페이즈 정보 갱신
function _renderCombatMomentum(cs) {
  const pStats = _combatSideStats(cs, cs.player_faction_id, 'player_strength');
  const eStats = _combatSideStats(cs, cs.enemy_faction_id, 'enemy_strength');

  const pBar = document.getElementById('c-player-bar');
  const eBar = document.getElementById('c-enemy-bar');
  if (pBar) pBar.style.width = `${pStats.pct}%`;
  if (eBar) eBar.style.width = `${eStats.pct}%`;

  const pVal = document.getElementById('c-player-val');
  const eVal = document.getElementById('c-enemy-val');
  if (pVal) pVal.textContent = `${pStats.remaining}/${pStats.base}`;
  if (eVal) eVal.textContent = `${eStats.remaining}/${eStats.base}`;

  const phaseInfo = document.getElementById('c-phase-info');
  if (phaseInfo) {
    if (cs.ended) {
      phaseInfo.textContent = '전투 종결';
    } else {
      const phase = cs.phase_number || 1;
      phaseInfo.textContent = cs.max_phases
        ? `${phase} / ${cs.max_phases} 페이즈`
        : `페이즈 ${phase}`;
    }
  }
}

// ── 교전 기록 갱신
const _LOG_COLOR = {
  critical_success: '#C5932A',
  success:          '#5DBB8B',
  partial:          '#EF9F27',
  failure:          '#E24B4A',
  critical_failure: '#8B2020',
  combat_luck:      '#7F77DD',
};
const _LOG_LABEL = {
  critical_success: '대성공',
  success:          '성공',
  partial:          '부분',
  failure:          '실패',
  critical_failure: '대실패',
  combat_luck:      '우연',
};

function _renderCombatLog(cs) {
  const log = document.getElementById('c-log');
  if (!log) return;
  const results = cs.phase_results || [];
  if (!results.length) return;
  log.innerHTML = results.map(r => {
    const color = _LOG_COLOR[r.tier_en] || '#999';
    const label = r.tier_en === 'combat_luck'
      ? `${_LOG_LABEL[r.tier_en]} ${(r.luck_shift ?? 0) >= 0 ? '+' : ''}${r.luck_shift ?? 0}`
      : _LOG_LABEL[r.tier_en] || r.tier_en;
    return `<div class="c-log-item" style="border-left-color:${color}">
      <span class="c-log-phase">P${r.phase}</span>
      <span style="color:${color};font-weight:600">${label}</span>
    </div>`;
  }).join('');
  log.scrollTop = log.scrollHeight;
}

// ── 전투 종결 화면 (푸터를 결과 패널로 교체)
function _renderCombatEnd(cs, content, resolution) {
  const tpp     = _state.troopsPerPoint || 0;
  const pending = cs.pending_battle_damage || {};
  const pFid    = cs.player_faction_id;
  const eFid    = cs.enemy_faction_id;
  const pName   = _state.factions.get(pFid)?.name || '아군';
  const eName   = _state.factions.get(eFid)?.name || '적군';
  const pDmg    = pending[pFid] || 0;
  const eDmg    = pending[eFid] || 0;

  const retreat    = cs.retreat;
  const winner     = cs.winner;
  const finalTier  = cs.final_tier || '?';
  const resultLabel = retreat
    ? '후퇴'
    : winner === 'player' ? `승리 — ${finalTier}` : `패배 — ${finalTier}`;
  const resultColor = retreat ? '#EF9F27' : winner === 'player' ? '#5DBB8B' : '#E24B4A';

  const fmtDmg = (dmg) => {
    if (!dmg) return '피해 없음';
    const troop = tpp ? ` (약 ${Math.round(dmg * tpp).toLocaleString()}명)` : '';
    return `전력 −${dmg}${troop}`;
  };

  const isQuickBattle = _state?.scenarioId === 'quick-battle';
  const actionBtns = isQuickBattle
    ? `<div class="combat-end-actions">
        <button class="combat-return-btn combat-replay-btn" onclick="qbReplay()">다시 하기</button>
        <button class="combat-return-btn" onclick="qbGoMain()">메인 화면으로</button>
      </div>`
    : `<button class="combat-return-btn" onclick="closeCombatOverlay()">전장으로 돌아가기 →</button>`;

  const footer = document.getElementById('c-footer');
  if (footer) footer.innerHTML = `
    <div class="combat-end-panel">
      <div class="combat-end-result" style="color:${resultColor}">${resultLabel}</div>
      <div class="combat-end-damages">
        <div class="combat-end-dmg">
          <span class="combat-end-dmg-label">${pName}</span>
          <span class="combat-end-dmg-val">${fmtDmg(pDmg)}</span>
        </div>
        <div class="combat-end-dmg">
          <span class="combat-end-dmg-label">${eName}</span>
          <span class="combat-end-dmg-val">${fmtDmg(eDmg)}</span>
        </div>
      </div>
      ${actionBtns}
    </div>
  `;

  const retreatBtn = document.getElementById('c-retreat-btn');
  if (retreatBtn) retreatBtn.style.display = 'none';

  _renderCombatScene(content, resolution);
}

// ── 전투 페이즈 턴 제출
async function submitCombatTurn() {
  const cmd = document.getElementById('c-cmd')?.value.trim();
  if (!cmd || !_state) return;

  document.getElementById('c-cmd').value = '';
  document.querySelectorAll('#c-choices .choice-btn').forEach(b => b.classList.remove('selected'));

  const scene = document.getElementById('c-scene');
  if (scene) scene.innerHTML = '<div class="scene-loading">처리 중…</div>';

  const sendBtn = document.getElementById('c-send');
  if (sendBtn) sendBtn.disabled = true;

  try {
    const { content, state_updates: su, resolution, _debug } =
      await GameAPI.submitTurn(cmd, _state.toJSON(), _state.getHistory());

    _state.pushHistory('user', cmd);
    _state.pushHistory('assistant', content);

    applyStateUpdates(su);

    _ui.onTurnEnd?.(_state);
    _manager._state = _state;
    _manager.save();

    const cs = _state.combatState;
    if (cs) {
      _renderCombatMomentum(cs);
      _renderCombatLog(cs);
    }

    if (cs?.ended) {
      _combatEndContent    = content;
      _combatEndResolution = resolution;
      _renderCombatEnd(cs, content, resolution);
    } else {
      _renderCombatScene(content, resolution);
    }

    _renderCombatDebugPanel(document.getElementById('c-scene'), resolution, _debug);

  } catch (err) {
    const scene = document.getElementById('c-scene');
    if (scene) scene.innerHTML =
      `<p style="color:var(--text-secondary);font-family:sans-serif;font-size:12px;">⚠ 오류: ${err.message}</p>`;
  } finally {
    const btn = document.getElementById('c-send');
    if (btn) btn.disabled = false;
  }
}

// ── 후퇴
async function combatRetreat() {
  const retreatBtn = document.getElementById('c-retreat-btn');
  if (retreatBtn) { retreatBtn.disabled = true; retreatBtn.textContent = '후퇴 중…'; }

  const scene = document.getElementById('c-scene');
  if (scene) scene.innerHTML = '<div class="scene-loading">후퇴 중…</div>';

  try {
    const { content, state_updates: su, resolution, _debug } =
      await GameAPI.submitTurn('후퇴', _state.toJSON(), _state.getHistory(), true);

    _state.pushHistory('user', '후퇴');
    _state.pushHistory('assistant', content);

    applyStateUpdates(su);

    _manager._state = _state;
    _manager.save();

    const cs = _state.combatState;
    if (cs) { _renderCombatMomentum(cs); _renderCombatLog(cs); }

    _combatEndContent    = content;
    _combatEndResolution = resolution;
    _renderCombatDebugPanel(document.getElementById('c-scene'), resolution, _debug);
    _renderCombatEnd(
      cs || { retreat: true, winner: 'enemy', final_tier: '실패', pending_battle_damage: {} },
      content, resolution
    );

  } catch (err) {
    if (retreatBtn) { retreatBtn.disabled = false; retreatBtn.textContent = '후퇴'; }
  }
}
