// ── 전역 상태 참조
let _manager = null;
let _state   = null;
let _ui      = null;

// ── 백엔드 메타 설정 로드 (/api/config)
// game.html 로드 초기에 한 번만 호출. 실패해도 게임은 동작하나 weather/terrain 배지 fallback 사용.
async function loadGameConfig() {
  try {
    const r = await fetch(`${window.API_BASE}/api/config`);
    if (!r.ok) return;
    const data = await r.json();
    window._gameConfig.gradeScale  = data.grade_scale  ?? null;
    window._gameConfig.weatherMeta = data.weather_meta ?? null;
    window._gameConfig.terrainMeta = data.terrain_meta ?? null;
  } catch (_) {
    // 서버 미연결 등 — fallback 동작 유지
  }
}

// ── 초기화
(async () => {
  try {
  await loadGameConfig();
  _manager = new StateManager();

  // ── 빠른 역사적 전투 복원 ──────────────────────────────────────────────────
  const _qbRaw = sessionStorage.getItem('quickBattle');
  if (_qbRaw) {
    sessionStorage.removeItem('quickBattle');
    const qb = JSON.parse(_qbRaw);
    _state = GameState.fromJSON(qb.stateJson);
    _state.troopsPerPoint = qb.troopsPerPoint;
    _state.eventContext   = {};
    _state.mapSvg         = '';
    _ui = window.getScenarioUI('ottoman-interregnum');
    tagStyle = { ...BASE_TAG_STYLE, ..._ui.tagExtras };
    _manager._state = _state;
    renderAll(_state);
    openCombatOverlay(qb.content, qb.resolution, qb.debug);
    document.getElementById('send-btn').disabled = false;
    return;
  }
  // ──────────────────────────────────────────────────────────────────────────

  const saveFile = NavState.getSaveFile();
  if (saveFile) {
    NavState.clearGame();
    try {
      const data = await GameAPI.loadSave(saveFile);
      const scenario = await ScenarioLoader.fetchOne(data.scenarioId);
      _ui = window.getScenarioUI(data.scenarioId);
      tagStyle = { ...BASE_TAG_STYLE, ..._ui.tagExtras };
      _state = GameState.fromJSON(data);
      _state.eventContext   = scenario.event_context ?? {};
      _state.mapSvg         = scenario.map_svg       ?? '';
      _state.troopsPerPoint = scenario.troops_per_strength_point ?? null;
      const mapContainer = document.getElementById('map-container');
      if (mapContainer) {
        const imgUrl = `${window.API_BASE}/api/scenarios/${data.scenarioId}/map-image`;
        mapContainer.innerHTML = `<div class="map-inner"><img id="map-img" src="${imgUrl}" alt="지도" onerror="this.style.display='none'"><div id="map-markers-layer"></div></div>`;
      }
      _manager._state = _state;
      _manager.save();
      renderAll(_state);
      const lastAssistant = [..._state.getHistory()].reverse().find(h => h.role === 'assistant');
      if (lastAssistant) {
        // 외교 UI 미완성 — diplomacyState가 active여도 일반 씬으로 복원
        // TODO: 외교 시스템 완성 후 openDiplomacyOverlay(lastAssistant.content, null) 로 교체
        if (_state.combatState?.active) {
          openCombatOverlay(lastAssistant.content, null);
        } else {
          renderSceneBody(markdownToHtml(extractNarrative(lastAssistant.content)));
          renderChoices(extractChoices(lastAssistant.content));
        }
      }
      document.getElementById('send-btn').disabled = false;
      return;
    } catch (e) {
      console.error('[saveFile 복원 실패]', e);
    }
  }

  _state = _manager.load();

  const scenarioId = _state ? _state.scenarioId : (NavState.getScenarioId() || null);

  if (!scenarioId) {
    renderSceneBody(`<p style="color:var(--text-secondary);font-size:13px;">
      <strong>시나리오가 선택되지 않았습니다.</strong><br><br>
      <a href="scenario_select.html" style="color:inherit;text-decoration:underline;">시나리오 선택 화면</a>으로 돌아가 다시 시작하세요.
    </p>`);
    console.warn('[game.html] sessionStorage에 scenarioId/scenario 키가 없음',
      { scenario: sessionStorage.getItem('scenario'), scenarioId: sessionStorage.getItem('scenarioId') });
    return;
  }

  _ui = window.getScenarioUI(scenarioId);
  tagStyle = { ...BASE_TAG_STYLE, ..._ui.tagExtras };

  const mapContainer = document.getElementById('map-container');
  let scenario;
  try {
    scenario = await ScenarioLoader.fetchOne(scenarioId);
  } catch (fetchErr) {
    const msg = fetchErr.message || String(fetchErr);
    renderSceneBody(`<p style="color:var(--text-secondary);font-size:13px;">
      <strong>백엔드 서버에 연결할 수 없습니다.</strong><br><br>
      <code style="font-size:11px;background:var(--bg-secondary);padding:2px 6px;border-radius:4px;">cd backend &amp;&amp; uvicorn main:app --reload --port 8000</code><br><br>
      서버를 시작한 뒤 페이지를 새로고침하세요.<br>
      <span style="font-size:11px;color:var(--text-tertiary);">${msg}</span>
    </p>`);
    return;
  }

  if (_state) {
    _state.eventContext   = scenario.event_context ?? {};
    _state.troopsPerPoint = scenario.troops_per_strength_point ?? null;
    _state.events         = scenario.events ?? [];
    // 세이브 생성 이후 시나리오에 추가된 세력·거점을 상태에 병합한다.
    for (const f of scenario.factions ?? []) {
      if (f.protagonist_only?.length && _state.protagonist &&
          !f.protagonist_only.includes(_state.protagonist)) continue;
      if (!_state.factions.has(f.id)) _state.factions.set(f.id, structuredClone(f));
    }
    for (const loc of scenario.locations ?? []) {
      if (!_state.locations.has(loc.id)) _state.locations.set(loc.id, structuredClone(loc));
    }
    // 히스토리가 없으면 아직 게임이 시작되지 않은 상태 — initial_diplomacy를 재적용해
    // 세션스토리지에 오래된 데이터가 남아있어도 올바른 초기값으로 복구된다.
    if (_state.history.length === 0) {
      GameState.applyInitialDiplomacy(_state, _state.protagonist);
      _ui.initDispositions(_state);
      _manager.save();
    }
  }

  if (mapContainer) {
    const imgUrl = `${window.API_BASE}/api/scenarios/${scenarioId}/map-image`;
    mapContainer.innerHTML = `<div class="map-inner"><img id="map-img" src="${imgUrl}" alt="지도" onerror="this.style.display='none'"><div id="map-markers-layer"></div></div>`;
  }

  if (!_state) {
    const protagonistId = NavState.getCharacterId() || scenario?.protagonist || null;

    if (scenario) {
      _state = _manager.init(scenario, protagonistId);
      _state.eventContext = scenario.event_context ?? {};
      _ui.initDispositions(_state);
      _ui.onInit?.(_state);
      _manager.save();
    }
  }

  if (_state) {
    renderAll(_state);

    const hist          = _state.getHistory();
    const lastAssistant = [...hist].reverse().find(h => h.role === 'assistant');

    if (lastAssistant) {
      // 외교 UI 미완성 — diplomacyState가 active여도 일반 씬으로 복원
      // TODO: 외교 시스템 완성 후 openDiplomacyOverlay(lastAssistant.content, null) 로 교체
      if (_state.combatState?.active) {
        openCombatOverlay(lastAssistant.content, null);
      } else {
        renderSceneBody(markdownToHtml(extractNarrative(lastAssistant.content)));
        renderChoices(extractChoices(lastAssistant.content));
      }
    } else {
      renderSceneBody('<div class="scene-loading">장면 생성 중…</div>');
      try {
        const { content, timestamp, state_updates: su } = await GameAPI.getOpening(_state.toJSON());

        if (Array.isArray(su?.new_characters)) {
          for (const c of su.new_characters) {
            if (c.id && !_state.characters.has(c.id)) _state.addCharacter(c);
          }
        }
        if (su?.event_state_changes && typeof su.event_state_changes === 'object') {
          _state.eventStates = { ..._state.eventStates, ...su.event_state_changes };
          renderEventList(_state);
        }

        _state.pushHistory('user',      '[게임 시작]');
        _state.pushHistory('assistant', content);
        _manager.save();

        if (timestamp) {
          const tsSpan = document.getElementById('timestamp-text');
          if (tsSpan) tsSpan.textContent = timestamp;
        }
        renderSceneBody(markdownToHtml(extractNarrative(content)));
        renderChoices(extractChoices(content));
      } catch (e) {
        renderSceneBody(`<p style="color:var(--text-secondary);font-size:13px;">오프닝 생성 실패: ${e.message}</p>`);
      }
    }
  }
  document.getElementById('send-btn').disabled = false;
  rebindTooltips();

  // ── 페이지 이탈 보호 ───────────────────────────────────────────────────────
  // history 가드 스테이트를 쌓아 뒤로가기를 popstate로 인터셉트한다.
  history.pushState({ gameGuard: true }, '');
  window.addEventListener('popstate', function onGamePopstate() {
    if (!window._serverUnsaved) return;       // 저장된 상태면 그냥 통과
    history.pushState({ gameGuard: true }, ''); // 한 번 더 쌓아 현 페이지 유지
    showUnsavedModal('__back__');
  });
  // 탭 닫기·새로고침·URL 직접 입력 등 beforeunload 계열 이탈 보호
  window.addEventListener('beforeunload', function(e) {
    if (window._serverUnsaved) {
      e.preventDefault();
      e.returnValue = '';
    }
  });
  // ──────────────────────────────────────────────────────────────────────────

  } catch (err) {
    console.error('[game.html init error]', err);
    renderSceneBody(`<p style="color:var(--text-secondary);font-size:13px;">
      <strong>초기화 중 오류가 발생했습니다.</strong><br><br>
      <span style="font-size:11px;color:var(--text-tertiary);">${err.message || err}</span><br><br>
      브라우저 콘솔(F12)에서 자세한 내용을 확인하세요.
    </p>`);
  }
})();
