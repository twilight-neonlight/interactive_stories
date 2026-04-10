/**
 * scenario-ui.js — 시나리오별 UI 설정 레지스트리
 *
 * window.getScenarioUI(scenarioId) 로 접근합니다.
 * game.html이 이 파일을 로드해 시나리오에 맞는 렌더링 설정을 가져옵니다.
 */

(function () {

// ── 공통 strength 레이블 ─────────────────────────────────────────
const STRENGTH_LABEL = {
  extreme: '압도적', 'very high': '대규모', high: '강대',
  medium: '중규모', low: '소규모', 'very low': '소수', impotent: '무력',
};

// ════════════════════════════════════════════════════════════════
// 대군세 지도 SVG
// ════════════════════════════════════════════════════════════════
const GHA_MAP = `<svg viewBox="0 0 200 160" xmlns="http://www.w3.org/2000/svg">
  <rect width="200" height="160" fill="#e8edf2"/>
  <rect x="155" y="0" width="45" height="160" fill="#b5d4f4" opacity="0.25"/>
  <path d="M20,130 Q40,110 35,90 Q30,70 50,60 Q70,50 80,30 Q90,15 110,20 Q130,25 140,15 Q155,5 170,20 Q180,30 175,50 Q170,65 160,75 Q150,85 155,100 Q160,115 145,125 Q130,135 110,130 Q90,125 70,135 Q50,145 30,140 Z" fill="#c8dff5" stroke="#7ab3e0" stroke-width="0.6"/>
  <path d="M25,135 Q45,125 65,138 Q85,148 100,142 Q115,136 125,142 Q135,148 130,152 Q110,158 85,155 Q60,152 40,148 Z" fill="#c5dfa0" stroke="#7ab86b" stroke-width="0.5"/>
  <path d="M78,65 Q88,58 100,62 Q112,66 114,76 Q116,86 106,92 Q96,98 84,94 Q74,90 74,80 Z" fill="#f5b8b8" stroke="#e06060" stroke-width="0.6" stroke-dasharray="2,1.5"/>
  <line x1="56" y1="107" x2="86" y2="84" stroke="#5a9fd4" stroke-width="1" stroke-dasharray="3,2" opacity="0.7"/>
  <line x1="140" y1="91" x2="97" y2="83" stroke="#6aaa55" stroke-width="1" stroke-dasharray="3,2" opacity="0.7"/>
  <g class="map-marker" data-id="nottingham" data-city="노팅엄" data-faction="대군세 (점거)" data-terrain="트렌트강 북안 구릉, 방어 유리" data-garrison="추정 2,000~3,000명" data-commander="이바르 (추정)" data-status="적 점거 — 포위 중" data-note="아군 포위망 형성 중. 북문에서 전령 접근 중.">
    <circle class="map-pulse" cx="92" cy="80" r="8" fill="#E24B4A" opacity="0.18"/>
    <circle class="outer" cx="92" cy="80" r="5" fill="#E24B4A" opacity="0.28" stroke="#E24B4A" stroke-width="0.8"/>
    <circle cx="92" cy="80" r="3.5" fill="#E24B4A"/>
  </g>
  <g class="map-marker" data-id="leicester" data-city="레스터" data-faction="머시아" data-terrain="에이번강 유역 평지" data-garrison="~1,500명 (후방 수비)" data-commander="미확인" data-status="아군 거점" data-note="노팅엄 원정군의 주요 보급 기점.">
    <circle class="outer" cx="56" cy="110" r="4" fill="#378ADD" opacity="0.22" stroke="#378ADD" stroke-width="0.6"/>
    <circle cx="56" cy="110" r="2.8" fill="#378ADD"/>
  </g>
  <g class="map-marker" data-id="tamworth" data-city="탬워스" data-faction="머시아" data-terrain="태미강 합류 지점, 머시아 수도" data-garrison="~800명 (왕궁 수비)" data-commander="왕실 직속" data-status="아군 거점 — 수도" data-note="버그레드 왕의 본거지. 왕은 현재 전선에 있음.">
    <circle class="outer" cx="72" cy="90" r="4" fill="#378ADD" opacity="0.22" stroke="#378ADD" stroke-width="0.6"/>
    <circle cx="72" cy="90" r="3" fill="#378ADD" stroke="#185FA5" stroke-width="0.8"/>
    <rect x="70.2" y="88.2" width="3.6" height="3.6" fill="none" stroke="#185FA5" stroke-width="0.8"/>
  </g>
  <g class="map-marker" data-id="lincoln" data-city="링컨" data-faction="머시아 (불안정)" data-terrain="링컨셔 고지" data-garrison="불명" data-commander="불명" data-status="불안정 — 대군세 압박" data-note="대군세 이동 경로상. 수비 정보 없음.">
    <circle class="outer" cx="140" cy="93" r="4" fill="#EF9F27" opacity="0.22" stroke="#EF9F27" stroke-width="0.6"/>
    <circle cx="140" cy="93" r="2.8" fill="#EF9F27"/>
  </g>
  <g class="map-marker" data-id="york" data-city="요크" data-faction="대군세 (점령)" data-terrain="우즈강·포스강 합류점, 로마 요새 기반" data-garrison="대규모 주둔 (규모 불명)" data-commander="하프단 계열 (추정)" data-status="적 점령 — 866년 함락" data-note="대군세 북부 거점. 꼭두각시 왕 세워짐.">
    <circle class="outer" cx="115" cy="42" r="4" fill="#888780" opacity="0.22" stroke="#888780" stroke-width="0.6"/>
    <circle cx="115" cy="42" r="2.8" fill="#888780"/>
  </g>
  <text x="97" y="77"  font-size="6.5" fill="#8b2020" font-family="sans-serif" font-weight="bold">노팅엄</text>
  <text x="42" y="122" font-size="6"   fill="#0d4a87" font-family="sans-serif">레스터</text>
  <text x="58" y="100" font-size="6"   fill="#0d4a87" font-family="sans-serif">탬워스</text>
  <text x="144" y="90" font-size="6"   fill="#6b3a05" font-family="sans-serif">링컨</text>
  <text x="119" y="40" font-size="6"   fill="#555552" font-family="sans-serif">요크</text>
  <rect x="3" y="140" width="95" height="16" rx="3" fill="white" opacity="0.82"/>
  <circle cx="10" cy="148" r="3.5" fill="#E24B4A"/>
  <text x="16" y="151" font-size="5.5" fill="#8b2020" font-family="sans-serif">적 점거</text>
  <circle cx="42" cy="148" r="3" fill="#378ADD"/>
  <text x="48" y="151" font-size="5.5" fill="#0d4a87" font-family="sans-serif">아군</text>
  <circle cx="66" cy="148" r="3" fill="#EF9F27"/>
  <text x="72" y="151" font-size="5.5" fill="#6b3a05" font-family="sans-serif">불안정</text>
  <circle cx="88" cy="148" r="3" fill="#888780"/>
  <text x="93" y="151" font-size="5.5" fill="#555552" font-family="sans-serif">함락</text>
</svg>`;

// ════════════════════════════════════════════════════════════════
// 오스만 공위기 지도 SVG
// ════════════════════════════════════════════════════════════════
const OTTOMAN_MAP = `<svg viewBox="0 0 200 160" xmlns="http://www.w3.org/2000/svg">
  <rect width="200" height="160" fill="#d4e8f5"/>
  <path d="M62,2 Q95,0 128,2 Q158,4 178,10 Q192,16 196,26 Q188,34 174,30 Q154,26 136,28 Q112,30 90,28 Q74,30 65,36 Q58,30 58,22 Z" fill="#bdd2ec"/>
  <path d="M0,0 L0,160 L58,160 L64,138 L60,118 L52,100 L44,88 L50,76 L56,66 L55,50 L44,30 L28,14 L10,2 Z" fill="#d0c8a2" stroke="#b0a88c" stroke-width="0.5"/>
  <path d="M44,88 L46,95 L44,102 L42,100 L42,93 Z" fill="#d0c8a2" stroke="#b0a88c" stroke-width="0.4"/>
  <path d="M64,36 L70,22 L84,12 L108,6 L138,4 L168,6 L194,12 L200,18 L200,160 L76,160 L70,140 L66,118 L64,100 L66,86 L70,76 L66,64 L62,50 L62,38 Z" fill="#d0c8a2" stroke="#b0a88c" stroke-width="0.5"/>
  <ellipse cx="60" cy="92" rx="13" ry="7" fill="#d4e8f5"/>
  <line x1="156" y1="52" x2="156" y2="28" stroke="#C5932A" stroke-width="1.2" stroke-dasharray="3,2.5" opacity="0.7"/>
  <line x1="86" y1="95" x2="134" y2="82" stroke="#a8a088" stroke-width="0.8" stroke-dasharray="3,2" opacity="0.5"/>
  <line x1="134" y1="82" x2="157" y2="52" stroke="#a8a088" stroke-width="0.8" stroke-dasharray="3,2" opacity="0.5"/>
  <g class="map-marker" data-id="edirne" data-city="에디르네" data-faction="술레이만 첼레비파" data-terrain="강변 평지 — 마리차·통자·아르다 강 합류부" data-garrison="루멜리아 병력 다수 — 규모 불명" data-commander="술레이만 첼레비" data-status="술레이만 장악" data-note="루멜리아 행정 중심. 비잔틴·제노바 외교 거점.">
    <circle class="outer" cx="22" cy="54" r="4" fill="#3a7abf" opacity="0.22" stroke="#3a7abf" stroke-width="0.6"/>
    <circle cx="22" cy="54" r="2.8" fill="#3a7abf"/>
  </g>
  <g class="map-marker" data-id="gallipoli" data-city="갈리폴리" data-faction="술레이만 첼레비파" data-terrain="다르다넬스 해협 서안 — 반도 요새" data-garrison="해협 수비대 (규모 불명)" data-commander="술레이만 계열" data-status="술레이만 장악" data-note="유럽-아나톨리아 해협 도하 거점. 아나톨리아 개입의 병목.">
    <circle class="outer" cx="44" cy="98" r="4" fill="#3a7abf" opacity="0.22" stroke="#3a7abf" stroke-width="0.6"/>
    <circle cx="44" cy="98" r="2.8" fill="#3a7abf"/>
  </g>
  <g class="map-marker" data-id="constantinople" data-city="콘스탄티노폴리스" data-faction="비잔틴 제국" data-terrain="삼면이 바다 — 테오도시우스 성벽" data-garrison="도시 수비대 — 공략 불가" data-commander="마누엘 2세" data-status="비잔틴 지배 — 외교 중" data-note="어느 왕자도 직접 공략 불가. 외교 승인이 최대 변수.">
    <circle class="map-pulse" cx="63" cy="74" r="7" fill="#7F77DD" opacity="0.15"/>
    <circle class="outer" cx="63" cy="74" r="4" fill="#7F77DD" opacity="0.22" stroke="#7F77DD" stroke-width="0.7"/>
    <circle cx="63" cy="74" r="3" fill="#7F77DD" stroke="#5a52cc" stroke-width="0.8"/>
    <rect x="61.2" y="72.2" width="3.6" height="3.6" fill="none" stroke="#5a52cc" stroke-width="0.8"/>
  </g>
  <g class="map-marker" data-id="iznik" data-city="이즈니크" data-faction="분쟁 지역" data-terrain="이즈니크 호 동안 — 로마 성벽" data-garrison="불명" data-commander="불명" data-status="실효 지배 공백" data-note="부르사와 함께 아나톨리아 서부 패권의 핵심. 이사-술레이만 충돌 가능.">
    <circle class="outer" cx="88" cy="86" r="4" fill="#EF9F27" opacity="0.22" stroke="#EF9F27" stroke-width="0.6"/>
    <circle cx="88" cy="86" r="2.8" fill="#EF9F27"/>
  </g>
  <g class="map-marker" data-id="bursa" data-city="부르사" data-faction="이사 첼레비파" data-terrain="울루다으 산 북록 — 비옥한 평원" data-garrison="이사 병력 — 규모 불명" data-commander="이사 첼레비" data-status="이사 장악 — 불안정" data-note="오스만 최초 수도. 상징성 높으나 기반이 흔들림.">
    <circle class="outer" cx="82" cy="104" r="4" fill="#888780" opacity="0.22" stroke="#888780" stroke-width="0.6"/>
    <circle cx="82" cy="104" r="2.8" fill="#888780"/>
  </g>
  <g class="map-marker" data-id="ankara" data-city="앙카라" data-faction="분쟁 지역" data-terrain="아나톨리아 고원 — 성채 언덕" data-garrison="불명 — 베이릭들이 각자 영역 회복 중" data-commander="불명" data-status="실효 지배 공백" data-note="1402년 앙카라 전투 현장. 아나톨리아 교차로. 심리적 트라우마 지점.">
    <circle class="outer" cx="134" cy="80" r="4" fill="#EF9F27" opacity="0.22" stroke="#EF9F27" stroke-width="0.6"/>
    <circle cx="134" cy="80" r="2.8" fill="#EF9F27"/>
  </g>
  <g class="map-marker" data-id="amasya" data-city="아마스야" data-faction="마흐메트 첼레비파" data-terrain="예실으르막 강 협곡 — 절벽 위 요새 도시" data-garrison="아마스야 수비대 — 방어에 유리" data-commander="마흐메트 첼레비" data-status="마흐메트 거점" data-note="천연 요새. 흑해 교역로 관문. 4형제 중 방어가 가장 용이한 위치.">
    <circle class="map-pulse" cx="157" cy="52" r="7" fill="#C5932A" opacity="0.18"/>
    <circle class="outer" cx="157" cy="52" r="4" fill="#C5932A" opacity="0.22" stroke="#C5932A" stroke-width="0.7"/>
    <circle cx="157" cy="52" r="3" fill="#C5932A"/>
  </g>
  <text x="162" y="50"  font-size="6"   fill="#7a5c10" font-family="sans-serif" font-weight="bold">아마스야</text>
  <text x="139" y="78"  font-size="6"   fill="#6b3a05" font-family="sans-serif">앙카라</text>
  <text x="68"  y="72"  font-size="6"   fill="#45428a" font-family="sans-serif">콘스탄티노폴리스</text>
  <text x="27"  y="52"  font-size="6"   fill="#1a3a6a" font-family="sans-serif">에디르네</text>
  <text x="49"  y="96"  font-size="6"   fill="#1a3a6a" font-family="sans-serif">갈리폴리</text>
  <text x="87"  y="102" font-size="6"   fill="#555552" font-family="sans-serif">부르사</text>
  <rect x="3" y="140" width="126" height="16" rx="3" fill="white" opacity="0.82"/>
  <circle cx="10"  cy="148" r="3.5" fill="#C5932A"/>
  <text x="16"  y="151" font-size="5.5" fill="#7a5c10" font-family="sans-serif">아군</text>
  <circle cx="36"  cy="148" r="3"   fill="#3a7abf"/>
  <text x="42"  y="151" font-size="5.5" fill="#1a3a6a" font-family="sans-serif">경쟁 왕자</text>
  <circle cx="76"  cy="148" r="3"   fill="#EF9F27"/>
  <text x="82"  y="151" font-size="5.5" fill="#6b3a05" font-family="sans-serif">불안정</text>
  <circle cx="105" cy="148" r="3"   fill="#7F77DD"/>
  <text x="111" y="151" font-size="5.5" fill="#45428a" font-family="sans-serif">중립</text>
</svg>`;

// ════════════════════════════════════════════════════════════════
// 오스만 — 세계 사건 (고정)
// ════════════════════════════════════════════════════════════════
const OTTOMAN_WORLD_EVENTS = [
  {
    name: '오스만 공위 분쟁', sub: '1402년~ · 오스만 제국 전역',
    body: '앙카라 전투 패배와 바야지트 1세 사망으로 술탄위가 공석. 루멜리아와 아나톨리아 모두 명목상 지배자 없이 분열. 어느 왕자도 단독으로 전체를 통제하지 못하는 불안정한 균형.',
    rows: '성격:제국 전역 권력 공백|전선:루멜리아·아나톨리아 동시 분열',
    dot: '#C5932A', region: '제국 전역', badge: 'badge-active', badgeText: '진행 중',
  },
  {
    name: '아나톨리아 베이릭 복원', sub: '1402년~ · 아나톨리아 중·서부',
    body: '티무르가 오스만에 흡수됐던 소규모 공국(베이릭)들을 복원시키고 철수. 독립을 주장하며 영역을 회복 중. 오스만의 아나톨리아 장악력이 구조적으로 약화.',
    rows: '성격:과거 복속 세력 독립 복원|위험:오스만 재통합의 최대 장애물 중 하나',
    dot: '#EF9F27', region: '아나톨리아 중·서부', badge: 'badge-ongoing', badgeText: '진행 중',
  },
  {
    name: '갈리폴리 해협 통제 문제', sub: '1403년~ · 다르다넬스 해협',
    body: '유럽과 아나톨리아를 잇는 유일한 도하 거점. 아나톨리아 거점 왕자가 루멜리아 병력을 활용하려면 반드시 통과해야 하는 전략적 병목.',
    rows: '성격:유럽-아시아 연결 병목|현황:술레이만 장악 — 통행 통제 가능',
    dot: '#3a7abf', region: '다르다넬스 해협', badge: 'badge-unknown', badgeText: '소강 상태',
  },
  {
    name: '카라만의 아나톨리아 패권 시도', sub: '1402년~ · 아나톨리아 중남부',
    body: '오스만 공위 분쟁을 틈타 중앙 아나톨리아에서 영향력 확대 중. 내전이 길어질수록 이득. 어느 왕자가 통일하더라도 가장 먼저 맞닥뜨릴 외부 위협.',
    rows: '성격:외부 세력의 공백 활용|위협:오스만 재건 이후에도 충돌 불가피',
    dot: '#E24B4A', region: '아나톨리아 중남부', badge: 'badge-ongoing', badgeText: '진행 중',
  },
  {
    name: '비잔틴의 등거리 외교', sub: '1403년~ · 콘스탄티노폴리스',
    body: '마누엘 2세가 오스만 공위 분쟁을 분열 유지의 기회로 활용. 어느 한 왕자에게 배타적 지지를 주지 않고 모든 왕자와 동시 접촉하며 조기 통일을 억제.',
    rows: '성격:이웃 강국의 분열 유지 전략|변수:비잔틴 지지 획득 시 루멜리아 정당성 확보 유리',
    dot: '#7F77DD', region: '콘스탄티노폴리스', badge: 'badge-unknown', badgeText: '소강 상태',
  },
];

// ════════════════════════════════════════════════════════════════
// 오스만 — 왕자별 오프닝 콘텐츠
// ════════════════════════════════════════════════════════════════
const OTTOMAN_OPENING = {
  mehmed: {
    timestamp: '1403년 봄, 아마스야',
    html: `<p>1403년 봄, 아마스야 — 예실으르막 강 협곡 위 절벽에 세워진 요새. 아버지 바야지트 1세가 앙카라 전투에서 패하고 티무르의 포로로 사망했다는 소식이 닿은 지 한 달이 지났다. 제국은 후계자 없이 진공 상태로 돌입했다.</p>
<p>루멜리아의 장남 술레이만은 이미 에디르네에서 스스로를 술탄으로 선포했다. 티무르 진영에서 귀환한 무사는 아나톨리아 유목 세력을 규합하며 동쪽에서 세력을 키우고 있다. 이사는 부르사를 장악했으나 사방이 적이다. 그리고 지금, 아마스야의 이 집무실에는 넷 중 가장 어리고, 지금 당장은 가장 적은 것을 가진 왕자만이 있다.</p>
<p>아마스야는 수비에 유리하다. 흑해 교역로가 수입을 만들고, 지방 귀족들이 조금씩 지지를 보내오고 있다. 하지만 수비만으로는 왕좌가 오지 않는다. 어디서 시작할 것인가.</p>`,
    choices: [
      '비잔틴에 사절을 보낸다. 다른 왕자들보다 먼저 외교 접촉을 시도한다.',
      '이사 첼레비에게 연합을 제안한다. 열세인 왕자끼리 손을 잡는다.',
      '아마스야 방어를 강화하고 힘을 비축한다. 형제들이 서로 소진하길 기다린다.',
      '흑해 교역로 수입을 늘리고 지방 귀족 포섭을 확대한다. 기반부터 다진다.',
    ],
  },
  suleyman: {
    timestamp: '1403년 초여름, 에디르네',
    html: `<p>1403년 초여름, 에디르네 — 루멜리아의 심장. 아버지 바야지트 1세가 앙카라 전투에서 패하고 티무르의 포로로 사망했다는 소식이 닿은 지 두 달이 지났다. 장남으로서 행동은 빠를수록 유리했다. 술레이만은 이미 에디르네를 거점으로 스스로를 술탄으로 선포했다.</p>
<p>비잔틴 황제 마누엘 2세가 조심스러운 지지 신호를 보내왔고, 제노바 상인들과의 협상 통로도 열려 있다. 루멜리아 귀족들은 지금은 따르지만, 그들의 충성에는 언제나 조건이 붙는다. 한편 아나톨리아 건너편에서는 형제들이 저마다 기반을 다지고 있다.</p>
<p>가장 많은 것을 가진 자가 반드시 이기는 것은 아니다. 첫 번째 결정을 내려라.</p>`,
    choices: [
      '비잔틴과의 조약을 공식화한다. 외교 지위를 굳힌다.',
      '갈리폴리 수비를 강화하고 아나톨리아 개입을 준비한다.',
      '루멜리아 귀족들과 협의해 내부 결속을 다진다.',
      '이사 첼레비를 먼저 제거한다. 약한 고리부터 처리한다.',
    ],
  },
  isa: {
    timestamp: '1403년 봄, 부르사',
    html: `<p>1403년 봄, 부르사 — 오스만 제국 최초의 수도이자 상징의 도시. 아버지 바야지트 1세가 패하고 사망했다. 앙카라 전투 직후 빠르게 움직여 부르사를 손에 넣었다. 이것이 지금 가진 전부다.</p>
<p>서쪽에서는 술레이만이 에디르네를 거점으로 루멜리아 전역을 장악했다. 동쪽에서는 무사가 유목 세력을 이끌고 접근하고 있다는 소식이 들어온다. 북쪽 이즈니크는 아직 누구의 손에도 들어가지 않았다. 사방이 압박이다.</p>
<p>잃을 것이 없는 자가 가장 대담할 수 있다고들 한다. 지금이 그 때인지 모른다. 첫 번째 결정을 내려라.</p>`,
    choices: [
      '술레이만과 협상을 시도한다. 부르사를 인정받는 조건으로 복속한다.',
      '무사와 연합을 모색한다. 두 형에 대항하는 구도를 만든다.',
      '부르사 방어를 강화하고 버틴다. 형제들이 싸우는 동안 살아남는다.',
      '이즈니크를 선점해 방어 종심을 확보한다.',
    ],
  },
  musa: {
    timestamp: '1403년 봄, 아나톨리아 내륙',
    html: `<p>1403년, 아나톨리아 내륙 — 귀환의 길 위. 앙카라 전투에서 티무르에게 포로로 잡혔다가 풀려났다. 포로 생활이 끝났다. 아버지는 없고, 제국은 형제들이 쪼개 먹는 중이다.</p>
<p>가지 전사들과 유목 세력이 나를 따른다 — 외교가 아닌 칼로 말하는 자들이. 술레이만은 에디르네에서 왕위를 선포했지만, 루멜리아의 귀족들은 술레이만을 원하는 게 아니라 자신들의 이익을 원할 뿐이다. 이사는 곧 무너진다. 마흐메트는 아마스야 요새에 숨어 있다.</p>
<p>협상으로 술탄이 된 자는 없다. 첫 번째 결정을 내려라.</p>`,
    choices: [
      '베이릭 연합을 구성한다. 가지 세력과 유목 부족을 하나로 묶는다.',
      '이사 첼레비를 압박한다. 부르사를 빼앗아 아나톨리아를 통합한다.',
      '비잔틴에 사절을 보낸다. 외교 정당성을 확보한다.',
      '술레이만의 루멜리아로 직접 건너간다. 갈리폴리를 기습한다.',
    ],
  },
};

// ════════════════════════════════════════════════════════════════
// 시나리오별 UI 설정
// ════════════════════════════════════════════════════════════════

const CONFIGS = {

  // ── 대군세의 시대 ─────────────────────────────────────────────
  'great-heathen-army': {
    defaultScenarioId: 'great-heathen-army',
    defaultProtagonistId: null,  // scenario.protagonist 사용
    mapSvg: GHA_MAP,
    tagExtras: {},

    commanderInfo(state) {
      let name = '불명', sub = '—', title = '불명', troops = '불명', supply = '불명', ally = '없음';
      if (state.protagonist) {
        const char = state.characters.get(state.protagonist);
        if (char) {
          name   = char.name;
          title  = char.title || char.epithet || '불명';
          troops = char.troops || STRENGTH_LABEL[char.strength] || '불명';
          supply = char.supply || '불명';
          const fid = char.faction_id || char.faction;
          if (fid) { const f = state.factions.get(fid); if (f) sub = f.name; }
        }
      }
      const friendly = Array.from(state.factions.values()).filter(f => f.disposition === '우호');
      if (friendly.length > 0) {
        const pf = friendly[0];
        if (sub   === '—')    sub    = pf.name;
        if (name  === '불명') name   = pf.name;
        if (troops === '불명') troops = STRENGTH_LABEL[pf.strength] || '불명';
      }
      const allyNames = friendly.slice(1).map(f => f.name.split(' ')[0]).join(', ');
      if (ally === '없음') ally = allyNames || '없음';
      return { name, sub, fields: [
        { key: '직위', val: title },
        { key: '병력', val: troops },
        { key: '보급', val: supply },
        { key: '동맹', val: ally },
      ]};
    },

    charDotColor(char, state) {
      if (char.id === state.protagonist) return '#378ADD';
      return { 우호: '#378ADD', 적대: '#E24B4A', 중립: '#888780' }[char.disposition] || '#888780';
    },
    charRelInfo(char, state) {
      if (char.id === state.protagonist) return { cls: 'rel-player', label: '플레이어' };
      return (
        char.disposition === '우호' ? { cls: 'rel-coop', label: '협력' } :
        char.disposition === '적대' ? { cls: 'rel-host', label: '적대' } :
        char.disposition === '중립' ? { cls: 'rel-unk',  label: '중립' } :
                                      { cls: 'rel-dist',  label: '불명' }
      );
    },

    factionBarColor(faction) {
      return { 우호: '#378ADD', 적대: '#E24B4A', 중립: '#888780' }[faction.disposition] || '#888780';
    },
    factionBarTag(faction) {
      return { 우호: '아군', 적대: '적대', 중립: '중립' }[faction.disposition] || '불명';
    },

    mapMarkerStyle(loc, state) {
      if (loc.controller === 'contested') return { color: '#EF9F27', statusText: '불안정' };
      const faction = state.factions.get(loc.controller);
      const disp = faction?.disposition;
      if (disp === '우호') return { color: '#378ADD', statusText: '아군 거점' };
      if (disp === '적대') return { color: '#E24B4A', statusText: '적 점거' };
      return { color: '#888780', statusText: '함락' };
    },

    getEvents(state) {
      const events = [];
      state.factions.forEach(faction => {
        if (faction.disposition !== '적대') return;
        const locs = Array.from(state.locations.values())
          .filter(l => l.controller === faction.id)
          .map(l => l.name.split(' ')[0]).join(', ');
        events.push({
          name: faction.name, sub: `세력 동향 · ${state.scenarioTitle}`,
          body: faction.notes || '', dot: '#E24B4A', region: locs || '—',
          rows: `세력:${faction.name}|상태:적대 — 교전 중`,
          badge: 'badge-active', badgeText: '진행 중',
        });
      });
      return events;
    },

    getOpeningContent(_state) {
      return {
        timestamp: '868년 9월, 노팅엄 외곽',
        html: `<p>해가 기울기 시작한 오후, 머시아-웨섹스 연합군의 포위망은 노팅엄 성벽을 둘러싼 채 사흘째를 맞이하고 있었다. 성 안의 이바르 지대는 움직임이 없었다. 척후병들의 보고에 따르면 성내 수비대는 여전히 온전하며, 식량 비축도 상당한 것으로 추정된다.</p>
<p>애설레드의 막사에서 돌아온 전령이 보고를 올렸다. 웨섹스 측은 장기 포위에 부담을 느끼고 있으며, 자국 방어 준비를 이유로 2주 이상의 체류는 어렵다는 입장을 전해왔다. 이것은 공식 서한이 아닌, 비공식 경고에 가까운 언질이었다.</p>
<p>한편 성벽 북문에서 작은 움직임이 포착되었다. 바이킹 측 전령으로 보이는 인물이 흰 천을 들고 외곽 경계선 쪽으로 접근해오고 있었다. 협상 의사를 타진하는 것인지, 아니면 다른 목적인지 아직 불분명하다.</p>`,
        choices: [
          '바이킹 전령을 맞이한다. 협상 조건을 확인한다.',
          '전령을 무시하고 포위를 계속한다. 웨섹스에 기간 연장을 요청한다.',
          '야간 기습을 준비한다. 전령 접촉 전 선제 압박을 가한다.',
        ],
      };
    },
    initDispositions(_state) { /* 시나리오 데이터에 이미 설정됨 */ },

    onInit(state) {
      const MERCIA_NOBLES = [
        { name: '에셀문트',   epithet: '흐위체 수장',   desc: '머시아 서남부 흐위체 지역의 실력자. 장기전 지속에 공개적으로 회의적이며, 탬워스 귀족층 사이에 영향력이 크다.' },
        { name: '케올울프',   epithet: '머시아 유력 귀족', desc: '트렌트 강 유역 영지를 가진 중부 귀족. 조용하지만 결정적인 순간에 왕의 뜻을 꺾은 전례가 있다.' },
        { name: '울프레드',   epithet: '동부 귀족 대표',  desc: '레스터 방면 귀족 연합의 대표. 포위전 장기화로 영지 수비 공백을 우려하고 있다. 일부 바이킹과 접촉한다는 소문이 있다.' },
        { name: '베오르흐트', epithet: '왕실 고문',       desc: '선왕 대부터 왕실을 보좌해 온 고위 귀족. 겉으로는 버그레드를 지지하나 속내를 드러내지 않는다.' },
        { name: '무첼름',     epithet: '북부 국경 영주',  desc: '덴마크군과 가장 가까운 최전방 영지를 보유한 귀족. 현실론자로, 협상 타결을 가장 강하게 압박하고 있다.' },
      ];
      const pick = MERCIA_NOBLES[Math.floor(Math.random() * MERCIA_NOBLES.length)];
      state.addCharacter({
        id:          'mercia-noble',
        name:        pick.name,
        epithet:     pick.epithet,
        disposition: '중립',
        status_tag:  '불명',
        desc:        pick.desc,
      });
    },
  },

  // ── 뇌제의 후계자 ─────────────────────────────────────────────
  'ottoman-interregnum': {
    defaultScenarioId: 'ottoman-interregnum',
    defaultProtagonistId: 'mehmed',
    mapSvg: OTTOMAN_MAP,
    tagExtras: { '경쟁': ['#fcebeb', '#a32d2d'] },

    commanderInfo(state) {
      let name = '불명', sub = '—', epithet = '불명', base = '불명', strength = '불명', ally = '없음';
      if (state.protagonist) {
        const char = state.characters.get(state.protagonist);
        if (char) {
          name    = char.name;
          epithet = char.epithet || char.title || '불명';
          base    = char.base ? char.base.split(' — ')[0] : '불명';
        }
        const ownFaction = state.factions.get(state.protagonist);
        if (ownFaction) {
          sub      = ownFaction.name;
          strength = STRENGTH_LABEL[ownFaction.strength] || '불명';
        }
      }
      const allyFactions = Array.from(state.factions.values())
        .filter(f => f.disposition === '우호' && f.id !== state.protagonist);
      ally = allyFactions.map(f => f.name.split(' ')[0]).join(', ') || '없음';
      return { name, sub, fields: [
        { key: '칭호', val: epithet },
        { key: '세력', val: strength },
        { key: '거점', val: base },
        { key: '동맹', val: ally },
      ]};
    },

    charDotColor(char, _state) {
      const colors = { suleyman: '#3a7abf', isa: '#888780', musa: '#8b2020', mehmed: '#C5932A' };
      return colors[char.id] || '#888780';
    },
    charRelInfo(char, state) {
      if (char.id === state.protagonist) return { cls: 'rel-player', label: '플레이어' };
      return (
        char.disposition === '우호' ? { cls: 'rel-coop', label: '협력' } :
        char.disposition === '적대' ? { cls: 'rel-host', label: '경쟁' } :
        char.disposition === '중립' ? { cls: 'rel-unk',  label: '중립' } :
                                      { cls: 'rel-dist',  label: '불명' }
      );
    },

    factionBarColor(faction) {
      const colors = {
        suleyman: '#3a7abf', isa: '#888780', musa: '#8b2020', mehmed: '#C5932A',
        byzantine: '#7F77DD', karamanids: '#E24B4A', 'anatolian-beyliks': '#a09878',
      };
      return colors[faction.id] || '#888780';
    },
    factionBarTag(faction) {
      return { 우호: '아군', 적대: '경쟁', 중립: '중립' }[faction.disposition] || '불명';
    },

    mapMarkerStyle(loc, state) {
      const factionColors = {
        suleyman: '#3a7abf', isa: '#888780', musa: '#8b2020', mehmed: '#C5932A',
        byzantine: '#7F77DD', karamanids: '#E24B4A', 'anatolian-beyliks': '#a09878',
      };
      if (loc.controller === 'contested') return { color: '#EF9F27', statusText: '불안정' };
      const faction = state.factions.get(loc.controller);
      const color   = factionColors[loc.controller] || '#888780';
      const disp    = faction?.disposition;
      if (disp === '우호') return { color, statusText: '아군 거점' };
      if (disp === '적대') return { color, statusText: '경쟁 세력' };
      return { color, statusText: '중립' };
    },

    getEvents(_state) { return OTTOMAN_WORLD_EVENTS; },

    getOpeningContent(state) {
      if (!state.protagonist) return null;
      return OTTOMAN_OPENING[state.protagonist] || OTTOMAN_OPENING.mehmed;
    },

    initDispositions(state) {
      const PRINCES = ['suleyman', 'isa', 'musa', 'mehmed'];
      const pid = state.protagonist;
      PRINCES.forEach(id => {
        const f = state.factions.get(id);
        if (f) f.disposition = (id === pid) ? '우호' : '적대';
      });
      for (const [id, char] of state.characters) {
        if (id === pid) char.disposition = '우호';
        else if (PRINCES.includes(id)) char.disposition = '적대';
        else char.disposition = char.disposition ?? '중립';
      }
    },

    onInit(state) {
      const STAFF_POOL = {
        mehmed: [
          { name: '이브라힘 파샤',   epithet: '수석 고문',     desc: '아마스야 행정을 오래 보좌해온 실무형 관료. 흑해 교역로 수입 관리에 밝으며, 마흐메트의 신중한 노선을 지지한다.' },
          { name: '타히르 베이',     epithet: '지방 귀족 대표', desc: '아나톨리아 북부 지방 귀족 연합의 대변인. 독자적인 영지 이해관계를 갖고 있어 마흐메트의 결정에 조건부로 따른다.' },
          { name: '유수프 에펜디',   epithet: '율법학자',       desc: '아마스야 울레마(이슬람 법학자) 집단의 대표. 정통성 확보와 민심 관리를 조언하며, 신중한 외교를 일관되게 권고한다.' },
        ],
        suleyman: [
          { name: '알리 베이',       epithet: '루멜리아 총독',  desc: '에디르네를 실질적으로 운영하는 행정가. 귀족 네트워크에 두루 연결돼 있으나, 술레이만보다 귀족 전체의 이익을 우선한다.' },
          { name: '야코보 그릴로',   epithet: '제노바 상인 대표', desc: '제노바 무역 거점의 대리인. 술레이만의 외교 자산이지만, 상업적 이익이 보장되는 한에서만 협력한다.' },
          { name: '하산 아가',       epithet: '친위대 지휘관',  desc: '루멜리아 병력의 실질적 지휘를 맡은 군인. 전략보다 전술에 강하며, 아나톨리아 개입에 신중한 입장이다.' },
        ],
        isa: [
          { name: '케말 베이',       epithet: '부르사 수비대장', desc: '아나톨리아 서부 방어를 책임지는 장수. 충성스럽지만 병력 열세를 누구보다 잘 안다. 현실론적 조언을 아끼지 않는다.' },
          { name: '니코스 팔라이올로고스', epithet: '비잔틴 망명 귀족', desc: '비잔틴 황실 방계 출신으로 이사에게 망명해온 인물. 콘스탄티노폴리스 내부 사정에 밝으나 신뢰성은 미지수.' },
        ],
        musa: [
          { name: '도안 베이',       epithet: '가지 수장',      desc: '아나톨리아 유목 전사 집단의 지도자. 무사의 가장 믿을 만한 군사 자산이지만, 장기 행정보다 약탈과 전투를 선호한다.' },
          { name: '메흐메트 아가',   epithet: '참모장',         desc: '앙카라 전투 생존자. 포로 시절 무사를 수행한 측근. 전술적 감각이 뛰어나지만 외교엔 어둡다.' },
          { name: '압둘라 에펜디',   epithet: '부족 연합 중재자', desc: '여러 유목 부족 사이를 오가며 무사의 연대를 조율하는 인물. 부족 간 이해관계 충돌 시 유일한 조정 창구.' },
        ],
      };

      const pool = STAFF_POOL[state.protagonist];
      if (!pool) return;
      const pick = pool[Math.floor(Math.random() * pool.length)];
      state.addCharacter({
        id:          'protagonist-staff',
        name:        pick.name,
        epithet:     pick.epithet,
        disposition: '우호',
        status_tag:  '확인됨',
        desc:        pick.desc,
      });
    },
  },
};

// ── 공개 API ─────────────────────────────────────────────────────
window.getScenarioUI = function (scenarioId) {
  return CONFIGS[scenarioId] || CONFIGS['great-heathen-army'];
};

})();
