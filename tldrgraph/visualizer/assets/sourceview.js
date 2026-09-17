'use strict';

const SOURCE_CACHE = new Map();
let sourceMode = 'none';
let sourceBase = null;

function escapeSource(value) {
  return String(value || '').replace(/[&<>]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[char]));
}

function sourceStatus() {
  const label = document.getElementById('source-status');
  const names = {served:'Source connected', folder:'Project folder connected', upload:'Uploaded source connected', none:'Source not connected'};
  label.textContent = names[sourceMode];
}

async function probeSourceServer() {
  const first = (DATA.source_files || [])[0];
  if (!first || !location.protocol.startsWith('http')) return false;
  for (const base of ['../', './', '/']) {
    try {
      const response = await fetch(base + first.path);
      if (response.ok) { sourceBase = base; return true; }
    } catch (_) {}
  }
  return false;
}

async function initSourceAccess() {
  if (await probeSourceServer()) sourceMode = 'served';
  sourceStatus();
}

async function loadSource(path) {
  if (SOURCE_CACHE.has(path)) return SOURCE_CACHE.get(path);
  let text;
  if (sourceMode === 'served') {
    const response = await fetch(sourceBase + path);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    text = await response.text();
  } else {
    throw new Error('Run tldrgraph ui --serve to view source');
  }
  SOURCE_CACHE.set(path, text);
  return text;
}

async function openEvidence(evidence) {
  const viewer = document.getElementById('source-viewer');
  const code = document.getElementById('source-code');
  viewer.hidden = false;
  document.getElementById('source-path').textContent = evidence.file;
  document.getElementById('source-meta').textContent = evidence.symbol;
  document.getElementById('open-editor').href = `vscode://file${DATA.root}/${evidence.file}:${evidence.code_start || evidence.line || 1}`;
  code.textContent = 'Loading source…';
  try {
    const text = await loadSource(evidence.file);
    const lines = text.split('\n');
    const located = locateEvidence(lines, evidence);
    const start = located.start;
    const end = located.end;
    document.getElementById('source-meta').textContent = evidence.symbol + (located.relocated ? ' · relocated in current source' : '');
    code.innerHTML = lines.map((line, index) => {
      const number = index + 1;
      return `<span class="code-line${number >= start && number <= end ? ' active' : ''}">${escapeSource(line) || ' '}</span>`;
    }).join('');
    const active = code.querySelector('.active');
    if (active) active.scrollIntoView({block:'center'});
  } catch (error) {
    code.textContent = error.message;
  }
}

function locateEvidence(lines, evidence) {
  const start = evidence.code_start || evidence.line || 1;
  const end = evidence.code_end || start;
  const stored = lines.slice(start - 1, end).join('\n');
  if (!evidence.symbol || stored.includes(evidence.symbol)) return {start, end, relocated:false};
  const found = lines.findIndex(line => line.includes(evidence.symbol));
  return found < 0 ? {start, end, relocated:false} : {start:found + 1, end:found + 1, relocated:true};
}

document.getElementById('close-source').addEventListener('click', () => { document.getElementById('source-viewer').hidden = true; });
initSourceAccess();
