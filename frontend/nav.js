// 네비게이션 상태 — sessionStorage 키를 한 곳에서 관리
const NavState = {
  setScenario(id) {
    sessionStorage.removeItem('is_gameState');
    sessionStorage.setItem('scenarioId', id);
  },

  setCharacter(id, name, scenarioId) {
    sessionStorage.setItem('selectedCharacterId', id);
    sessionStorage.setItem('selectedCharacterName', name);
    sessionStorage.setItem('scenario', scenarioId);
    sessionStorage.removeItem('is_gameState');
  },

  setSaveFile(filename) {
    sessionStorage.removeItem('is_gameState');
    sessionStorage.setItem('saveFile', filename);
  },

  setCustomScenario(text) {
    sessionStorage.setItem('customScenario', text);
  },

  clearGame() {
    sessionStorage.removeItem('saveFile');
    sessionStorage.removeItem('is_gameState');
  },

  getSaveFile()    { return sessionStorage.getItem('saveFile'); },
  getScenarioId()  { return sessionStorage.getItem('scenario') || sessionStorage.getItem('scenarioId'); },
  getCharacterId() { return sessionStorage.getItem('selectedCharacterId') || sessionStorage.getItem('selectedCharacter'); },
};
window.NavState = NavState;
