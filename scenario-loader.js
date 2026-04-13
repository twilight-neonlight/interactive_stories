/**
 * scenario-loader.js — 시나리오 데이터 단일 소스 및 file:// 호환 로더
 *
 * type="module" 없이 일반 <script>로 로드합니다.
 * ScenarioLoader와 SECTIONS을 window에 전역으로 노출합니다.
 *
 * 데이터 편집: 이 파일의 LOCAL_SCENARIOS 배열을 직접 수정하세요.
 * 백엔드 연동: [LOCAL-ONLY] 블록 삭제 → [BACKEND] 블록 주석 해제
 */

// ─────────────────────────────────────────────
// 섹션 정의
// ─────────────────────────────────────────────
window.SECTIONS = [
  { id: 'history', label: '역사 기반' },
  { id: 'fantasy', label: '판타지 · 창작 세계' },
];

// ━━━ [LOCAL-ONLY] ━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 백엔드 연동 시 이 블록 전체(LOCAL_SCENARIOS 선언 포함)를 삭제하세요.
// 시나리오 추가: 아래 배열에 객체를 추가하고 scenario-ui.js에 UI 설정을 등록하세요.
const LOCAL_SCENARIOS = [

  // ── great-heathen-army ─────────────────────
  {
    id: 'great-heathen-army',
    title: '대군세의 시대',
    section: 'history',
    eyebrow: '868년 여름 · 머시아 왕국',
    meta: '버그레드 왕 — 노팅엄 포위전',
    desc: '바이킹 대군세가 노팅엄을 점거하고 농성에 들어갔다. 동맹인 웨섹스 지원군은 2주 안에 철수해야 한다. 전투, 협상, 아니면 다른 길을 찾아봐야 한다.',
    tags: ['군사', '외교', '바이킹', '앵글로색슨'],
    icon: '⚔',
    color: '#E24B4A',
    colorSoft: 'rgba(226,75,74,0.06)',
    iconBg: 'rgba(226,75,74,0.08)',
    status: 'ready',
    href: 'game.html',
    protagonistMode: 'fixed',
    protagonist: 'burgred',
    locations: [
      { id: 'nottingham',  x: 92,  y: 80,  name: '노팅엄 (Snotengaham)',        controller: 'great-heathen-army', terrain: '강변 평지 — 트렌트 강 북안, 목책 요새',          strategic_value: '트렌트 강 도하 거점. 점령한 채 농성 중이므로 직접 공략 없이는 남진 불가.',  notes: '덴마크군이 겨울을 나기 위해 점거. 성벽보다 강과 늪이 천연 방어선.' },
      { id: 'york',        x: 115, y: 42,  name: '요크 (Jorvik)',                controller: 'great-heathen-army', terrain: '평원 — 우즈 강·포스 강 합류 지점',               strategic_value: '865년 함락 후 덴마크 북잉글랜드 수도. 병참·병력 보충의 핵심 기지.',            notes: '괴뢰왕 에그버트가 통치 중. 공략 시 전선 확대 불가피.' },
      { id: 'tamworth',    x: 72,  y: 90,  name: '탬워스 (Tamworth)',            controller: 'mercia',             terrain: '내륙 평지 — 앤커 강 합류부',                    strategic_value: '머시아 왕궁 소재지. 왕국의 행정·상징적 중심.',                                notes: '노팅엄이 함락되면 다음 침공 목표가 될 가능성 높음.' },
      { id: 'repton',      x: 80,  y: 98,  name: '레프턴 (Repton)',              controller: 'mercia',             terrain: '트렌트 강 남안 — 수도원 언덕',                  strategic_value: '머시아 왕실 묘지이자 수도원. 정신적·종교적 거점.',                              notes: '역사적으로 873년 덴마크군이 동계 야영지로 삼음. 현재는 아직 머시아 영토.' },
      { id: 'leicester',   x: 56,  y: 110, name: '레스터 (Ligera ceaster)',      controller: 'mercia',             terrain: '내륙 평지 — 소어 강변 로마 도로망 교차점',       strategic_value: '노팅엄-탬워스 사이 보급로 결절점. 덴마크군 남하 시 전초기지 역할.' },
      { id: 'winchester',  x: 58,  y: 138, name: '윈체스터 (Venta Belgarum)',    controller: 'wessex',             terrain: '남부 구릉 — 이첸 강변',                         strategic_value: '고대 로마의 유산 위에 세워진, 웨섹스 왕국의 수도이자 심장 ',                           notes: '고대 로마시대에 세워진 도시로, 7세기 경 건립된 올드 민스터(Old Minster) 성당은 웨섹스 왕실의 권위를 상징한다.' },
      { id: 'norfolk',     x: 158, y: 112, name: '노포크 (Norfolc)',              controller: 'east-anglia',        terrain: '동해안 저지대 — 습지·하구 밀집 지형',            strategic_value: '동앵글리아의 북부 관문. 북해 연안 상륙 경로와 직결되며 덴마크군 증원 시 최초 상륙 후보지.' },
    ],
    factions: [
      { id: 'great-heathen-army', name: '대군세 (Micel Hæþen Here)', type: 'tribe',   strength: 'very high', disposition: '적대', notes: '이바르·할프단 형제 공동 지휘. 요크를 병참 기지로 노팅엄에 농성 중. 보급선이 길어 장기전보다 단기 결착 선호. 협상 창구가 열려 있으나 조건이 가혹함.' },
      { id: 'mercia',             name: '머시아 왕국',               type: 'kingdom', strength: 'medium',    disposition: '우호', notes: '버그레드 왕이 플레이어. 귀족 간 파벌이 있어 강경파·온건파 모두 존재. 웨섹스 지원에 의존하는 구조가 내부 자율성을 제약.' },
      { id: 'wessex',             name: '웨섹스 왕국',               type: 'kingdom', strength: 'high',      disposition: '우호', notes: '에셀레드 1세와 동생 알프레드가 지원군 이끌고 참전 중. 2주 후 철수 예정. 동맹 유지를 위해 외교적 성과가 필요.' },
      { id: 'northumbria-puppet', name: '노섬브리아 (덴마크 괴뢰)',   type: 'kingdom', strength: 'very low',   disposition: '중립', notes: '866년 함락 후 에그버트를 앞세운 괴뢰 정권. 독자적 군사 행동 불가. 덴마크군의 후방 보급 통로 역할.' },
      { id: 'east-anglia',        name: '동앵글리아 왕국',           type: 'kingdom', strength: 'low',       disposition: '중립', notes: '아직 침공받지 않았으나 방어력이 약함. 덴마크군 철수 협상 시 완충지대로 활용 가능. 868년 현재 에드문드 왕 통치 중.' },
    ],
    characters: [
      { id: 'burgred',       name: '버그레드',     epithet: '머시아 왕',           disposition: '플레이어', status_tag: '확인됨', title: '왕', troops: '~12,000', supply: '약 8일치', desc: '머시아 왕. 웨섹스와의 동맹을 기반으로 노팅엄 포위전을 지휘 중.' },
      { id: 'aethelred',     name: '애설레드',     epithet: '웨섹스 왕',           disposition: '우호', status_tag: '확인됨', desc: '머시아와 동맹 유지 중. 장기 파견에 부담, 2주 이상 체류 어렵다는 입장.' },
      { id: 'alfred',        name: '알프레드',     epithet: '웨섹스 왕자',         disposition: '우호', status_tag: '추정됨', desc: '애설레드의 동생. 신중한 전술가로 알려짐. 성향 추정 단계.' },
      { id: 'ivar',          name: '이바르',       epithet: '대군세 지휘관',       disposition: '적대', status_tag: '불명',   desc: '노팅엄 점거 후 농성. 협상 전령을 보냈으나 의도 불명.' },
      { id: 'halfdan',       name: '하프단',       epithet: '대군세 공동 지휘관',  disposition: '적대', status_tag: '추정됨', desc: '이바르의 형제. 공격적 성향. 노팅엄 내부 추정.' },
      { id: 'ubba',          name: '우바',         epithet: '대군세 지휘관',       disposition: '적대', status_tag: '불명',   desc: '이바르·하프단의 형제. 현재 위치 불명.' },
    ],
  },

  // ── ottoman-interregnum ────────────────────
  {
    id: 'ottoman-interregnum',
    title: '뇌제의 후계자',
    section: 'history',
    eyebrow: '1403년 · 오스만 제국',
    meta: '4인의 왕자 중 선택 — 오스만 공위기',
    desc: '앙카라 전투 이후 티무르의 포로로 잡힌 바야지트 1세가 사망했다. 술레이만, 무사, 이사, 마흐메트 — 네 왕자가 저마다의 방식으로 제국을 손에 넣으려 한다. 누구의 길을 걷겠는가.',
    tags: ['정치', '내전', '외교', '오스만'],
    icon: '🌙',
    color: '#C5932A',
    colorSoft: 'rgba(197,147,42,0.07)',
    iconBg: 'rgba(197,147,42,0.09)',
    status: 'wip',
    protagonistMode: 'select',
    characterSelectPage: 'prince_select.html',
    locations: [
      { id: 'edirne',         x: 22,  y: 54,  name: '에디르네 (Edirne / Adrianople)',      controller: 'suleyman',  terrain: '강변 평지 — 마리차·통자·아르다 강 합류부',     strategic_value: '루멜리아(유럽 영토) 행정·군사 수도. 비잔틴·제노바 교역로 결절점.',         notes: '술레이만이 형제 중 가장 탄탄한 행정 기반을 가진 이유. 내부 귀족 영향력도 집중.' },
      { id: 'bursa',          x: 82,  y: 104, name: '부르사 (Bursa / Prusa)',               controller: 'isa',       terrain: '울루다으 산 북록 — 비옥한 평원',               strategic_value: '오스만 최초 수도이자 상업 중심지. 비단 교역로의 요충. 상징성 강함.',       notes: '이사가 장악 중이나 기반이 불안정. 무사·술레이만 양측의 압박을 동시에 받는 위치.' },
      { id: 'amasya',         x: 157, y: 52,  name: '아마스야 (Amasya)',                    controller: 'mehmed',    terrain: '예실으르막 강 협곡 — 절벽 위 요새 도시',       strategic_value: '아나톨리아 북부 흑해 교역로 관문. 천연 요새 지형으로 방어에 유리.',       notes: '마흐메트의 근거지. 티무르가 각 왕자에게 분봉한 영역 중 방어가 가장 용이.' },
      { id: 'constantinople', x: 63,  y: 74,  name: '콘스탄티노폴리스 (Konstantinoupolis)', controller: 'byzantine', terrain: '삼면이 바다 — 테오도시우스 성벽',               strategic_value: '비잔틴 제국 수도. 어느 왕자도 직접 공략 불가. 외교 승인의 핵심 변수.', notes: '마누엘 2세가 모든 왕자와 동시 협상 중. 비잔틴 지지 확보는 루멜리아 통제권과 직결.' },
      { id: 'ankara',         x: 134, y: 80,  name: '앙카라 (Ankara / Ancyra)',             controller: 'contested', terrain: '아나톨리아 고원 — 성채 언덕',                  strategic_value: '1402년 전투 현장. 중앙 아나톨리아 교차로. 현재 실효 지배 공백.',       notes: '티무르 철수 후 아나톨리아 베이릭들이 각자 영역 회복 중. 심리적 트라우마 지점.' },
      { id: 'gallipoli',      x: 44,  y: 98,  name: '갈리폴리 (Gelibolu)',                  controller: 'suleyman',  terrain: '다르다넬스 해협 서안 — 반도 요새',             strategic_value: '유럽-아나톨리아 해협 도하 거점. 루멜리아 병력의 아나톨리아 투입 관문.', notes: '술레이만이 장악 중. 아나톨리아 전선 참여 시 반드시 통과해야 하는 병목.' },
      { id: 'iznik',          x: 88,  y: 86,  name: '이즈니크 (İznik / Nicaea)',            controller: 'contested', terrain: '이즈니크 호 동안 — 로마 성벽',                 strategic_value: '아나톨리아 서북부 요충. 부르사-콘스탄티노폴리스 사이 방어선.',         notes: '부르사와 함께 아나톨리아 서부 패권의 핵심. 이사-술레이만 충돌 가능 지점.' },
    ],
    factions: [
      { id: 'suleyman',          name: '술레이만 첼레비파',         type: 'faction',  strength: 'very high', disposition: '중립', notes: '루멜리아 전역과 비잔틴·제노바 외교망 보유. 귀족·봉신 의존 구조라 중앙집권이 약함. 협상 가능하나 양보 시 내부 반발 위험.' },
      { id: 'isa',               name: '이사 첼레비파',             type: 'faction',  strength: 'very low',  disposition: '중립', notes: '부르사를 거점으로 하나 사방이 압박. 생존 압박이 커서 외교 제안에 반응적. 조기 탈락 가능성이 있어 단기 동맹 상대로 적합.' },
      { id: 'musa',              name: '무사 첼레비파',             type: 'faction',  strength: 'medium',    disposition: '중립', notes: '아나톨리아 가지·유목 세력 기반. 외교보다 전쟁을 선호해 협상 비용이 높음. 전투력 강하나 장기 행정 능력 부재.' },
      { id: 'mehmed',            name: '마흐메트 첼레비파',         type: 'faction',  strength: 'low',       disposition: '중립', notes: '아마스야 요새와 흑해 교역 수입 보유. 신중하고 장기적 시각. 단독으론 열세지만 연합 구성 시 가장 지속적인 파트너.' },
      { id: 'byzantine',         name: '비잔틴 제국',               type: 'empire',   strength: 'very low',  disposition: '중립', notes: '마누엘 2세가 모든 왕자와 동시 접촉해 분열을 유지. 지지 선언은 외교 자산이나 군사 지원은 제한적. 내정 간섭 의도 있음.' },
      { id: 'karamanids',        name: '카라만 왕조',               type: 'emirate',  strength: 'medium',    disposition: '적대', notes: '티무르 이후 아나톨리아 패권을 노리는 가장 강력한 베이릭. 오스만 내전을 기회로 영역 확장 시도. 어느 왕자가 강해져도 결국 충돌 불가피.' },
      { id: 'anatolian-beyliks', name: '아나톨리아 베이릭들',       type: 'tribe',    strength: 'very low',  disposition: '중립', notes: '티무르가 복원한 소규모 공국들. 개별 포섭 가능하나 집단 행동은 어려움. 가지 전사 충원의 공급처.' },
    ],
    characters: [
      { id: 'suleyman', name: '술레이만 첼레비', epithet: '유럽의 왕자',       icon: '🏛', location: '루멜리아\n에디르네',         desc: '바야지트의 장남. 루멜리아(유럽 영토)를 장악하고 있어 자원과 외교 기반이 가장 탄탄하다. 비잔틴과 제노바의 지지를 확보했으나, 유럽 귀족의 입김에서 자유롭지 못하다.', traits: ['외교 중심', '풍부한 자원', '귀족 의존'],    base: '에디르네 — 루멜리아 전역',         color: '#3a7abf', colorSoft: 'rgba(58,122,191,0.06)' },
      { id: 'isa',      name: '이사 첼레비',     epithet: '잊혀진 왕자',       icon: '⚔', location: '아나톨리아 서부\n부르사',     desc: '앙카라 전투 직후 아나톨리아 서부를 장악했으나 기반이 불안하다. 형 술레이만과 동생 무사 양쪽에서 압박을 받는 처지. 지지 세력이 가장 약하지만, 역설적으로 가장 많은 것을 잃을 것이 없다.', traits: ['불안정한 기반', '기동전', '고위험 고수익'], base: '부르사 — 아나톨리아 서부',         color: '#888780', colorSoft: 'rgba(136,135,128,0.06)' },
      { id: 'musa',     name: '무사 첼레비',     epithet: '포로에서 돌아온 자', icon: '🗡', location: '아나톨리아\n티무르 진영 귀환', desc: '앙카라에서 티무르에게 포로로 잡혔다가 귀환했다. 아나톨리아 유목 세력과 가지(전사) 집단의 지지를 받는다. 타협 없는 전사의 이미지가 강점이자 약점 — 외교보다 전쟁이 익숙한 왕자다.',   traits: ['전투 중심', '가지 세력', '외교 취약'],    base: '아나톨리아 내륙 — 유목 세력권',    color: '#8b2020', colorSoft: 'rgba(139,32,32,0.06)' },
      { id: 'mehmed',   name: '마흐메트 첼레비', epithet: '아마스야의 군주',    icon: '🌙', location: '아나톨리아 북부\n아마스야',   desc: '가장 어리지만 가장 신중하다. 아마스야를 거점으로 흑해 교역로를 장악하고 있으며, 아나톨리아 지방 귀족들의 지지를 조금씩 모으고 있다. 역사는 그를 제1대 술탄이라 부르게 될 것이다 — 하지만 그것은 아직 오지 않은 미래다.', traits: ['균형 외교', '장기 전략', '초반 열세'],    base: '아마스야 — 흑해 연안',             color: '#C5932A', colorSoft: 'rgba(197,147,42,0.07)' },
    ],
  },

  // ── voice-of-god ───────────────────────────
  {
    id: 'voice-of-god',
    title: '신의 목소리',
    section: 'history',
    eyebrow: '1429년 봄 · 프랑스 왕국',
    meta: '잔 다르크 — 오를레앙 포위전 돌파',
    desc: '영국군이 오를레앙을 포위한 지 반년이 지났다. 한 농민 소녀가 신의 계시를 들었다고 주장하며 군대 앞에 섰다. 전장을 돌파하는 것만이 문제가 아니다 — 프랑스 내부의 견제를 버텨내야 한다.',
    tags: ['군사', '정치', '백년전쟁', '프랑스'],
    icon: '⚜',
    color: '#3a7abf',
    colorSoft: 'rgba(58,122,191,0.06)',
    iconBg: 'rgba(58,122,191,0.08)',
    status: 'wip',
    protagonistMode: 'fixed',
  },

  // ── empty-throne ───────────────────────────
  {
    id: 'empty-throne',
    title: '공허의 왕좌',
    section: 'fantasy',
    eyebrow: '판타지 · 창작 세계',
    meta: '마법 붕괴 시대 — 다섯 제후의 전쟁',
    desc: '신의 죽음과 함께 마법의 원천이 말라붙기 시작했다. 마법에 의존하던 제국은 균열을 보이고, 다섯 제후는 각자의 방식으로 공백을 채우려 한다. 새로운 질서의 설계자가 될 것인가.',
    tags: ['판타지', '정치', '마법', '세계 붕괴'],
    icon: '👁',
    color: '#5B4FBB',
    colorSoft: 'rgba(91,79,187,0.07)',
    iconBg: 'rgba(91,79,187,0.09)',
    status: 'wip',
    protagonistMode: 'fixed',
  },

];
// ━━━ [/LOCAL-ONLY] ━━━━━━━━━━━━━━━━━━━━━━━━━━━

// ─────────────────────────────────────────────
// ScenarioLoader
// ─────────────────────────────────────────────
window.ScenarioLoader = {

  async fetchAll() {
    // ── [LOCAL-ONLY] 백엔드 연동 시 아래 줄 삭제 ──
    return structuredClone(LOCAL_SCENARIOS);
    // ── [/LOCAL-ONLY] ─────────────────────────────

    // ── [BACKEND] 백엔드 연동 시 아래 주석 해제 ───
    // const res = await fetch('/api/scenarios');
    // if (!res.ok) throw new Error('시나리오 목록을 불러오지 못했습니다.');
    // return res.json();
    // ── [/BACKEND] ────────────────────────────────
  },

  async fetchCharacters(scenarioId) {
    const all = await this.fetchAll();
    const scenario = all.find(s => s.id === scenarioId);
    if (!scenario) throw new Error(`시나리오 '${scenarioId}'를 찾을 수 없습니다.`);
    // ── [LOCAL-ONLY] 백엔드 연동 시 아래 줄 삭제 ──
    return scenario.characters ?? [];
    // ── [/LOCAL-ONLY] ─────────────────────────────

    // ── [BACKEND] 백엔드 연동 시 아래 주석 해제 ───
    // const res = await fetch(`/api/scenarios/${scenarioId}/characters`);
    // if (!res.ok) throw new Error('캐릭터 목록을 불러오지 못했습니다.');
    // return res.json();
    // ── [/BACKEND] ────────────────────────────────
  },

  async fetchGrouped() {
    const all = await this.fetchAll();
    return window.SECTIONS
      .map(section => ({
        section,
        scenarios: all.filter(s => s.section === section.id),
      }))
      .filter(group => group.scenarios.length > 0);
  },
};
