// ── 마크다운 → HTML 변환 (씬 본문용 경량 변환기)
function inline(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function markdownToHtml(md) {
  if (!md) return '';
  const lines = md.split('\n');
  const out   = [];
  let inList  = false;
  let inTable = false;

  const flushList  = () => { if (inList)  { out.push('</ul>');            inList  = false; } };
  const flushTable = () => { if (inTable) { out.push('</tbody></table>'); inTable = false; } };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flushList(); flushTable(); continue; }
    if (/^---+$/.test(line)) { flushList(); flushTable(); out.push('<hr class="divider">'); continue; }
    if (line.startsWith('|')) {
      flushList();
      if (/^\|[\s:|-]+\|/.test(line)) continue;
      const cells = line.split('|').slice(1, -1).map(c => c.trim());
      if (!inTable) {
        inTable = true;
        out.push('<table class="summary-table"><thead><tr>');
        cells.forEach(c => out.push(`<th>${inline(c)}</th>`));
        out.push('</tr></thead><tbody>');
      } else {
        out.push('<tr>');
        cells.forEach(c => out.push(`<td>${inline(c)}</td>`));
        out.push('</tr>');
      }
      continue;
    }
    flushTable();
    if (/^- ./.test(line)) {
      if (!inList) { out.push('<ul style="padding-left:16px;margin:6px 0;">'); inList = true; }
      out.push(`<li style="margin:3px 0;">${inline(line.slice(2))}</li>`);
      continue;
    }
    flushList();
    out.push(`<p>${inline(line)}</p>`);
  }
  flushList(); flushTable();
  return out.join('');
}

// ── 응답 텍스트 파싱 헬퍼
function extractNarrative(text) {
  let body = text.replace(/^##[^\n]*\n/, '').trim();
  body = body.replace(/^\*\*시각:\*\*[^\n]*\n?/m, '').trim();
  const cutIdx = body.search(/\*{0,2}결정 시점\*{0,2}/);
  if (cutIdx !== -1) body = body.slice(0, cutIdx).trim();
  return body;
}

function extractChoices(text) {
  const cutIdx = text.search(/\*{0,2}결정\s*(시점|기로)\*{0,2}/);
  const section = cutIdx !== -1 ? text.slice(cutIdx) : text;
  return section
    .split('\n')
    .filter(l => /^(-|\d+[.)]) .{4,}/.test(l.trim()))
    .map(l => l.trim().replace(/^(-|\d+[.)]) /, '').trim());
}
