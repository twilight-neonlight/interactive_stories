// diplomacy-ui.js — 외교 회담 오버레이 모듈

let _diplomacyEndContent    = null;
let _diplomacyEndResolution = null;

const _ROUND_COLOR = {
  critical_success: '#C5932A',
  success:          '#5DBB8B',
  partial:          '#7F77DD',
  failure:          '#E09060',
  critical_failure: '#E24B4A',
};

function _findDiplomacyTarget(ds) {
  if (!_state) return null;
  if (ds.target_character_id) {
    const char = _state.characters.get(ds.target_character_id);
    if (char) return { name: char.name, color: null };
  }
  if (ds.target_faction_id) {
    const faction = _state.factions.get(ds.target_faction_id);
    if (faction) return { name: faction.name, color: faction.color || null };
  }
  return null;
}

// ── 오버레이 열기
function openDiplomacyOverlay(content, resolution, debugData = null) {
  const ds = _state?.diplomacyState;
  if (!ds) return;

  const playerF    = _state.factions.get(ds.player_faction_id) || {};
  const playerName = playerF.name  || '아군';
  const playerColor = playerF.color || '#5DBB8B';

  const target     = _findDiplomacyTarget(ds);
  const targetName = target?.name || '상대';
  const targetColor = target?.color || '#C5932A';

  const label = ds.session_label || '외교 협상';

  const overlay = document.getElementById('diplomacy-overlay');
  overlay.innerHTML = `
    <div class="dipl-shell">
      <div>
        <div class="dipl-title-row">
          <button class="dipl-close-btn" id="d-close-btn" onclick="diplomacyWithdraw()">×</button>
          <span class="dipl-title-text">${label}</span>
          <div class="dipl-matchup">
            <div class="dipl-faction-col">
              <span class="dipl-faction-role">우리 측</span>
              <span class="dipl-fname" style="color:${playerColor}">${playerName}</span>
            </div>
            <span class="dipl-vs">↔</span>
            <div class="dipl-faction-col">
              <span class="dipl-faction-role">상대 측</span>
              <span class="dipl-fname" style="color:${targetColor}">${targetName}</span>
            </div>
          </div>
          <span class="dipl-round-info" id="d-round-info">라운드 1</span>
          <button class="dipl-withdraw-btn" id="d-withdraw-btn" onclick="diplomacyWithdraw()">회담 중단</button>
        </div>
      </div>

      <div class="dipl-body">
        <div class="dipl-log-col">
          <div class="dipl-log-label">교섭 기록</div>
          <div class="dipl-log" id="d-log">
            <div style="color:var(--text-tertiary);font-size:11px;font-family:sans-serif;padding:4px 0">개회</div>
          </div>
        </div>
        <div class="dipl-scene-col">
          <div class="dipl-res-badge" id="d-res-badge"></div>
          <div class="scene-body" id="d-scene" style="flex:1;min-height:0;overflow-y:auto;"></div>
        </div>
      </div>

      <div class="dipl-footer" id="d-footer">
        <div class="choice-list" id="d-choices"></div>
        <hr class="divider">
        <div class="input-wrap">
          <textarea placeholder="외교적 제안이나 발언을 입력하세요…" id="d-cmd" maxlength="2000"></textarea>
          <button class="send-btn" id="d-send" onclick="submitDiplomacyTurn()">전송</button>
        </div>
      </div>
    </div>
  `;

  overlay.classList.add('active');
  _diplomacyEndContent    = null;
  _diplomacyEndResolution = null;

  if (ds?.ended) {
    // 개회 턴 즉시 결론 또는 저장 복원 시 already-ended 상태
    _diplomacyEndContent    = content;
    _diplomacyEndResolution = resolution;
    _renderDiplomacyEnd(ds, content, resolution);
  } else {
    _renderDiplomacyScene(content, resolution);
    document.getElementById('d-cmd')?.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitDiplomacyTurn(); }
    });
  }
}

// ── 오버레이 닫기 → 메인 게임으로 복귀
function closeDiplomacyOverlay() {
  document.getElementById('diplomacy-overlay')?.classList.remove('active');

  if (_diplomacyEndContent !== null) {
    renderAll(_state);
    renderResolution(_diplomacyEndResolution);
    const content = _diplomacyEndContent;
    renderSceneBody(markdownToHtml(extractNarrative(content)));
    renderChoices(extractChoices(content));
    _diplomacyEndContent    = null;
    _diplomacyEndResolution = null;
  }
}

// ── 씬 텍스트 + 판정 배지 + 선택지
function _renderDiplomacyScene(content, resolution) {
  const scene = document.getElementById('d-scene');
  if (scene) scene.innerHTML = markdownToHtml(extractNarrative(content));

  const badge = document.getElementById('d-res-badge');
  if (badge) {
    if (resolution && RESOLUTION_STYLE[resolution.tier_en]) {
      const s      = RESOLUTION_STYLE[resolution.tier_en];
      const modStr = formatModifiers(resolution.modifiers);
      badge.style.cssText = `display:inline-block;color:${s.color};border-color:${s.color};`;
      badge.textContent = s.label;
      badge.title = resolution.roll != null
        ? `주사위 ${resolution.roll} → 보정 후 ${resolution.net}${modStr ? ' [' + modStr + ']' : ''}`
        : modStr ?? '';
    } else {
      badge.style.display = 'none';
    }
  }

  const choices    = extractChoices(content);
  const choiceList = document.getElementById('d-choices');
  if (choiceList) {
    choiceList.innerHTML = renderChoiceButtons(choices, 'selectDiplomacyChoice');
  }
}

// ── 선택지 클릭
let _diplomacySelectedActionType = null;

function selectDiplomacyChoice(btn) {
  document.querySelectorAll('#d-choices .choice-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  const cmd = document.getElementById('d-cmd');
  if (cmd) cmd.value = btn.textContent.trim();
  _diplomacySelectedActionType = btn.dataset.actionType || null;
}

// ── 라운드 정보 갱신
function _renderDiplomacyRoundInfo(ds) {
  const roundInfo = document.getElementById('d-round-info');
  if (roundInfo) {
    roundInfo.textContent = ds.ended ? '회담 종결' : `라운드 ${ds.round_number || 1}`;
  }
}

// ── 교섭 기록 갱신
function _renderDiplomacyLog(ds) {
  const log = document.getElementById('d-log');
  if (!log) return;
  const results = ds.round_results || [];
  if (!results.length) return;
  log.innerHTML = results.map(r => {
    const color = _ROUND_COLOR[r.tier_en] || '#999';
    return `<div class="d-log-item" style="border-left-color:${color}">
      <span class="d-log-round">R${r.round}</span>
      <span style="color:${color};font-weight:600">${r.tier}</span>
    </div>`;
  }).join('');
  log.scrollTop = log.scrollHeight;
}

// ── 회담 종결 화면
function _renderDiplomacyEnd(ds, content, resolution) {
  const outcome    = ds?.outcome;
  const withdrawal = ds?.withdrawal;

  let resultLabel, resultColor;
  if (withdrawal) {
    resultLabel = '회담 중단';
    resultColor = '#E09060';
  } else if (outcome === 'agreement') {
    resultLabel = '합의 성립';
    resultColor = '#5DBB8B';
  } else {
    resultLabel = '회담 결렬';
    resultColor = '#E24B4A';
  }

  const footer = document.getElementById('d-footer');
  if (footer) footer.innerHTML = `
    <div class="dipl-end-panel">
      <div class="dipl-end-result" style="color:${resultColor}">${resultLabel}</div>
      <button class="combat-return-btn" onclick="closeDiplomacyOverlay()">회담장을 떠나다 →</button>
    </div>
  `;

  document.getElementById('d-withdraw-btn')?.style.setProperty('display', 'none');
  document.getElementById('d-close-btn')?.style.setProperty('display', 'none');

  _renderDiplomacyScene(content, resolution);
}

// ── 외교 라운드 제출
async function submitDiplomacyTurn() {
  const cmd = document.getElementById('d-cmd')?.value.trim();
  if (!cmd || !_state) return;

  const actionType = _diplomacySelectedActionType;
  _diplomacySelectedActionType = null;

  document.getElementById('d-cmd').value = '';
  document.querySelectorAll('#d-choices .choice-btn').forEach(b => b.classList.remove('selected'));

  const scene = document.getElementById('d-scene');
  if (scene) scene.innerHTML = '<div class="scene-loading">처리 중…</div>';

  const sendBtn = document.getElementById('d-send');
  if (sendBtn) sendBtn.disabled = true;

  try {
    const { content, state_updates: su, resolution, _debug } =
      await GameAPI.submitTurn(cmd, _state.toJSON(), _state.getHistory(), false, false, actionType);

    commitTurn(cmd, content, su);

    const ds = _state.diplomacyState;
    if (ds) {
      _renderDiplomacyRoundInfo(ds);
      _renderDiplomacyLog(ds);
    }

    if (ds?.ended) {
      _diplomacyEndContent    = content;
      _diplomacyEndResolution = resolution;
      _renderDiplomacyEnd(ds, content, resolution);
    } else {
      _renderDiplomacyScene(content, resolution);
    }

  } catch (err) {
    const scene = document.getElementById('d-scene');
    if (scene) scene.innerHTML =
      `<p style="color:var(--text-secondary);font-family:sans-serif;font-size:12px;">⚠ 오류: ${err.message}</p>`;
  } finally {
    const btn = document.getElementById('d-send');
    if (btn) btn.disabled = false;
  }
}

// ── 회담 중단
async function diplomacyWithdraw() {
  const withdrawBtn = document.getElementById('d-withdraw-btn');
  if (withdrawBtn) { withdrawBtn.disabled = true; withdrawBtn.textContent = '중단 중…'; }
  const closeBtn = document.getElementById('d-close-btn');
  if (closeBtn) closeBtn.disabled = true;

  const scene = document.getElementById('d-scene');
  if (scene) scene.innerHTML = '<div class="scene-loading">회담을 중단하는 중…</div>';

  try {
    const { content, state_updates: su, resolution } =
      await GameAPI.submitTurn('회담 중단', _state.toJSON(), _state.getHistory(), false, true);

    commitTurn('회담 중단', content, su);

    const ds = _state.diplomacyState;
    if (ds) { _renderDiplomacyRoundInfo(ds); _renderDiplomacyLog(ds); }

    _diplomacyEndContent    = content;
    _diplomacyEndResolution = resolution;
    _renderDiplomacyEnd(
      ds || { outcome: 'breakdown', withdrawal: true },
      content, resolution
    );

  } catch {
    if (withdrawBtn) { withdrawBtn.disabled = false; withdrawBtn.textContent = '회담 중단'; }
    if (closeBtn) closeBtn.disabled = false;
  }
}
