// ── 전역 상태 참조
let _manager = null;
let _state   = null;
let _ui      = null;

// ── 초기화
(async () => {
  try {
  _manager = new StateManager();

  const saveFile = sessionStorage.getItem('saveFile');
  if (saveFile) {
    sessionStorage.removeItem('saveFile');
    sessionStorage.removeItem('is_gameState');
    try {
      const data = await fetch(`${window.API_BASE}/api/saves/${encodeURIComponent(saveFile)}`).then(r => r.json());
      const scenario = await ScenarioLoader.fetchOne(data.scenarioId);
      _ui = window.getScenarioUI(data.scenarioId);
      tagStyle = { ...BASE_TAG_STYLE, ..._ui.tagExtras };
      _state = GameState.fromJSON(data);
      _state.opening        = scenario.opening  ?? {};
      _state.npcPool        = scenario.npc_pool ?? {};
      _state.mapSvg         = scenario.map_svg  ?? '';
      _state.troopsPerPoint = scenario.troops_per_strength_point ?? null;
      const mapContainer = document.getElementById('map-container');
      if (mapContainer) {
        const imgUrl = `${window.API_BASE}/api/scenarios/${data.scenarioId}/map-image`;
        mapContainer.innerHTML = `<div class="map-inner"><img id="map-img" src="${imgUrl}" alt="지도"><div id="map-markers-layer"></div></div>`;
      }
      _manager._state = _state;
      _manager.save();
      renderAll(_state);
      const lastAssistant = [..._state.getHistory()].reverse().find(h => h.role === 'assistant');
      if (lastAssistant) {
        if (_state.progress.isChapterEnd) renderChapterClose(lastAssistant.content);
        else { renderSceneBody(markdownToHtml(extractNarrative(lastAssistant.content))); renderChoices(extractChoices(lastAssistant.content)); }
      }
      document.getElementById('send-btn').disabled = false;
      return;
    } catch (e) {
      console.error('[saveFile 복원 실패]', e);
    }
  }

  _state = _manager.load();

  const scenarioId = _state
    ? _state.scenarioId
    : (sessionStorage.getItem('scenario') || sessionStorage.getItem('scenarioId') || null);

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
    _state.opening        = scenario.opening  ?? {};
    _state.npcPool        = scenario.npc_pool ?? {};
    _state.troopsPerPoint = scenario.troops_per_strength_point ?? null;
  }

  if (mapContainer) {
    const imgUrl = `${window.API_BASE}/api/scenarios/${scenarioId}/map-image`;
    mapContainer.innerHTML = `<div class="map-inner"><img id="map-img" src="${imgUrl}" alt="지도"><div id="map-markers-layer"></div></div>`;
  }

  if (!_state) {
    const protagonistId = sessionStorage.getItem('selectedCharacterId')
      || sessionStorage.getItem('selectedCharacter')
      || scenario?.protagonist
      || null;

    if (scenario) {
      _state = _manager.init(scenario, protagonistId);
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
      if (_state.progress.isChapterEnd) {
        renderChapterClose(lastAssistant.content);
      } else {
        renderSceneBody(markdownToHtml(extractNarrative(lastAssistant.content)));
        renderChoices(extractChoices(lastAssistant.content));
      }
    } else {
      renderSceneBody('<div class="scene-loading">장면 생성 중…</div>');
      try {
        const res = await fetch(`${window.API_BASE}/api/opening`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ state: _state.toJSON() }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const { content, timestamp, state_updates: su } = await res.json();

        if (Array.isArray(su?.new_characters)) {
          for (const c of su.new_characters) {
            if (c.id && !_state.characters.has(c.id)) _state.addCharacter(c);
          }
        }

        _state.pushHistory('user',      '[게임 시작]');
        _state.pushHistory('assistant', content);
        _manager.save();

        renderSceneHeader(_state.progress, _state.scenarioTitle);
        if (timestamp) {
          const tsSpan = document.getElementById('timestamp-text');
          if (tsSpan) tsSpan.textContent = timestamp;
        }
        renderSceneBody(markdownToHtml(extractNarrative(content)));
        renderChoices(extractChoices(content));
      } catch (e) {
        const opening = _ui.getOpeningContent(_state);
        if (opening) {
          renderSceneBody(opening.html);
          renderChoices(opening.choices);
          const tsSpan = document.getElementById('timestamp-text');
          if (tsSpan && opening.timestamp) tsSpan.textContent = opening.timestamp;
        } else {
          renderSceneBody(`<p style="color:var(--text-secondary);font-size:13px;">오프닝 생성 실패: ${e.message}</p>`);
        }
      }
    }
  }
  document.getElementById('send-btn').disabled = false;
  rebindTooltips();
  } catch (err) {
    console.error('[game.html init error]', err);
    renderSceneBody(`<p style="color:var(--text-secondary);font-size:13px;">
      <strong>초기화 중 오류가 발생했습니다.</strong><br><br>
      <span style="font-size:11px;color:var(--text-tertiary);">${err.message || err}</span><br><br>
      브라우저 콘솔(F12)에서 자세한 내용을 확인하세요.
    </p>`);
  }
})();
