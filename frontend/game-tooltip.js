// ── 툴팁 DOM 참조
const tooltip = document.getElementById('tooltip');
const ttName  = document.getElementById('tt-name');
const ttSub   = document.getElementById('tt-sub');
const ttBody  = document.getElementById('tt-body');
const ttDiv   = document.getElementById('tt-div');
const ttRows  = document.getElementById('tt-rows');
const ttTags  = document.getElementById('tt-tags');

// 기본 태그 스타일 (시나리오별 tagExtras로 보강됨)
const BASE_TAG_STYLE = {
  '확인됨': ['#e6f1fb','#185fa5'], '추정됨': ['#faeeda','#854f0b'],
  '불명':   ['#f0efea','#6b6a65'], '아군':   ['#eaf3de','#3b6d11'],
  '동맹':   ['#e6f1fb','#185fa5'], '적대':   ['#fcebeb','#a32d2d'],
  '함락':   ['#f0efea','#6b6a65'], '중립':   ['#f0efea','#6b6a65'],
};
let tagStyle = { ...BASE_TAG_STYLE };

function pos(e) {
  const tw=215, th=200, vw=window.innerWidth, vh=window.innerHeight;
  let x=e.clientX+14, y=e.clientY+14;
  if(x+tw>vw-8) x=e.clientX-tw-8;
  if(y+th>vh-8) y=e.clientY-th-8;
  tooltip.style.left=x+'px'; tooltip.style.top=y+'px';
}

function showGeneric(el, e) {
  const color = el.dataset.color;
  if (color) {
    ttName.innerHTML = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:6px;vertical-align:middle;flex-shrink:0;"></span>${el.dataset.name||''}`;
  } else {
    ttName.textContent=el.dataset.name||'';
  }
  ttSub.textContent=el.dataset.sub||'';
  ttBody.textContent=el.dataset.body||'';
  ttDiv.style.display='none'; ttRows.innerHTML='';
  const tag=el.dataset.tags||'';
  const [bg,fg]=tagStyle[tag]||['#f0efea','#6b6a65'];
  ttTags.innerHTML=tag?`<span class="tt-tag" style="background:${bg};color:${fg}">${tag}</span>`:'';
  tooltip.classList.add('active'); pos(e);
}

function showMap(el, e) {
  ttName.textContent=el.dataset.city||'';
  ttSub.textContent=''; ttBody.textContent='';
  const _c = el.dataset.color || '#888';
  const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${_c};margin-right:4px;flex-shrink:0;vertical-align:middle;"></span>`;
  ttDiv.style.display='block';
  ttRows.innerHTML=[['세력',el.dataset.faction,true],['지형',el.dataset.terrain],
    ['주둔군',el.dataset.garrison],['지휘관',el.dataset.commander],['상태',el.dataset.status,true]]
    .filter(([,v])=>v).map(([k,v,colored])=>`<div class="tt-row"><span class="tt-row-key">${k}</span><span class="tt-row-val">${colored?dot:''}${v}</span></div>`).join('');
  ttTags.innerHTML=el.dataset.note?`<div class="tt-note">${el.dataset.note}</div>`:'';
  tooltip.classList.add('active'); pos(e);
}

function showEvent(el, e) {
  ttName.textContent=el.dataset.name||'';
  ttSub.textContent=el.dataset.sub||'';
  ttBody.textContent=el.dataset.body||'';
  ttDiv.style.display='block';
  ttRows.innerHTML=(el.dataset.rows||'').split('|').filter(Boolean).map(r=>{
    const [k,...vs]=r.split(':');
    return `<div class="tt-row"><span class="tt-row-key">${k}</span><span class="tt-row-val">${vs.join(':')||''}</span></div>`;
  }).join('');
  ttTags.innerHTML='';
  tooltip.classList.add('active'); pos(e);
}

function rebindTooltips() {
  document.querySelectorAll('[data-name]').forEach(el => {
    el.addEventListener('mouseenter', e => showGeneric(el, e));
    el.addEventListener('mousemove',  e => pos(e));
    el.addEventListener('mouseleave', () => tooltip.classList.remove('active'));
  });
  document.querySelectorAll('.map-marker').forEach(el => {
    el.addEventListener('mouseenter', e => { showMap(el, e); });
    el.addEventListener('mousemove',  e => pos(e));
    el.addEventListener('mouseleave', () => { tooltip.classList.remove('active'); });
  });
  document.querySelectorAll('.event-item').forEach(el => {
    el.addEventListener('mouseenter', e => showEvent(el, e));
    el.addEventListener('mousemove',  e => pos(e));
    el.addEventListener('mouseleave', () => tooltip.classList.remove('active'));
  });
}
