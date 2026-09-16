'use strict';

const canvas = document.getElementById('workflow-canvas');
const ctx = canvas.getContext('2d');
const phaseColors = {user_action:'#67a8ff',frontend:'#8a9cff',request:'#c68aff',backend:'#56dfcc',persistence:'#7bd879',external:'#ffca6a',response:'#ff9b73',ui_update:'#ff88ba'};
let selected = null;
let shapes = [];
let edges = [];
const DEFAULT_ZOOM = 0.5;
let view = {x:80,y:210,scale:DEFAULT_ZOOM};
let dragging = false;
let pointer = null;
let dragStart = null;
let direction = 'vertical';

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function areasInOrder() {
  const rank = {product:0, technical:1};
  return [...(DATA.workflow_areas || [])].sort((a,b) => (rank[a.perspective]-rank[b.perspective]) || a.order-b.order);
}

function searchable(workflow, query) {
  if (!query) return true;
  const values = [workflow.title, workflow.summary, workflow.audience, workflow.area_title];
  workflow.steps.forEach(step => {
    values.push(step.title, step.text, step.phase, step.file, step.symbol);
    (step.evidence || []).forEach(item => values.push(item.file, item.symbol));
    (step.options || []).forEach(option => {
      values.push(option.title, option.text, option.phase, option.file, option.symbol);
      (option.evidence || []).forEach(item => values.push(item.file, item.symbol));
    });
  });
  (workflow.evidence || []).forEach(item => values.push(item.file, item.symbol));
  return values.some(value => String(value || '').toLowerCase().includes(query));
}

function renderCatalog() {
  const query = document.getElementById('search').value.trim().toLowerCase();
  const visible = (DATA.workflows || []).filter(item => searchable(item, query));
  const complete = (DATA.workflows || []).filter(item => item.status === 'generated').length;
  document.getElementById('summary').textContent = `${complete}/${DATA.workflows.length} complete · ${visible.length} shown`;
  const groups = [];
  for (const perspective of ['product','technical']) {
    const sections = areasInOrder().filter(area => area.perspective === perspective).map(area => {
      const cards = visible.filter(item => item.area_id === area.id).map(item => `
        <button class="workflow-card ${selected && selected.id === item.id ? 'active' : ''}" data-id="${escapeHtml(item.id)}">
          <strong>${escapeHtml(item.title)}</strong>
          <small><span class="badge ${item.status}">${escapeHtml(item.status)}</span> ${escapeHtml(item.summary)}</small>
        </button>`).join('');
      return cards ? `<section class="area"><h3>${escapeHtml(area.title)}</h3>${cards}</section>` : '';
    }).join('');
    if (sections) groups.push(`<div class="perspective">${perspective} capabilities</div>${sections}`);
  }
  document.getElementById('catalog').innerHTML = groups.join('') || '<div class="empty">No matching workflows.</div>';
  document.querySelectorAll('.workflow-card').forEach(card => card.addEventListener('click', () => selectWorkflow(card.dataset.id)));
}

function selectWorkflow(id) {
  selected = (DATA.workflows || []).find(item => item.id === id) || null;
  document.getElementById('workflow-title').textContent = selected ? selected.title : 'Select a workflow';
  document.getElementById('workflow-summary').textContent = selected ? selected.summary : 'Choose a source-backed capability from the catalog.';
  document.getElementById('status-badge').className = selected ? `badge ${selected.status}` : '';
  document.getElementById('status-badge').textContent = selected ? selected.status : '';
  document.getElementById('audience').textContent = selected ? selected.audience : '';
  const refs = document.getElementById('workflow-evidence');
  refs.innerHTML = selected ? (selected.evidence || []).map((item,index)=>`<button data-header-evidence="${index}">${escapeHtml(item.symbol)}</button>`).join('') : '';
  refs.querySelectorAll('[data-header-evidence]').forEach(button=>button.addEventListener('click',()=>openEvidence(selected.evidence[Number(button.dataset.headerEvidence)])));
  document.getElementById('detail').hidden = true;
  resetWorkflowView(); renderCatalog(); draw();
}

function resize() {
  const ratio = window.devicePixelRatio || 1;
  const box = canvas.getBoundingClientRect();
  canvas.width = Math.round(box.width * ratio); canvas.height = Math.round(box.height * ratio);
  ctx.setTransform(ratio,0,0,ratio,0,0); draw();
}

function wrap(text, width) {
  const words = String(text || '').split(/\s+/); const lines = []; let line = '';
  words.forEach(word => {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > width && line) { lines.push(line); line = word; } else line = next;
  });
  if (line) lines.push(line); return lines.slice(0,3);
}

function roundedRect(x,y,w,h,r) {
  ctx.beginPath(); ctx.roundRect(x,y,w,h,r); ctx.fill(); ctx.stroke();
}

function makeNode(step, kind, x, y, w, h) {
  return {step, kind, x, y, w, h};
}

function buildShapes() {
  shapes = []; edges = [];
  if (!selected || !selected.steps.length) return;
  const groups = direction === 'vertical' ? buildVerticalGroups() : buildHorizontalGroups();
  groups.forEach(group => shapes.push(group.main, ...(group.options || [])));
  groups.forEach((group, index) => {
    if (!group.options) return;
    group.options.forEach(option => edges.push({from: group.main, to: option, label: option.step.title, branch: true}));
    const next = groups[index + 1];
    if (next) group.options.forEach(option => edges.push({from: option, to: next.main, merge: true}));
  });
  for (let index = 0; index < groups.length - 1; index += 1) {
    if (!groups[index].options) edges.push({from: groups[index].main, to: groups[index + 1].main});
  }
}

function buildVerticalGroups() {
  const groups = []; const processWidth = 230; const processHeight = 112;
  const decisionWidth = 210; const decisionHeight = 126; const optionGap = 42;
  let cursor = 0;
  selected.steps.forEach(step => {
    if (!(step.options && step.options.length)) {
      const main = makeNode(step, 'process', -processWidth / 2, cursor, processWidth, processHeight);
      groups.push({main}); cursor += processHeight + 92; return;
    }
    const main = makeNode(step, 'decision', -decisionWidth / 2, cursor, decisionWidth, decisionHeight);
    const branchWidth = step.options.length * processWidth + (step.options.length - 1) * optionGap;
    const optionY = cursor + decisionHeight + 94;
    const options = step.options.map((option, index) => makeNode(
      {...option, number: step.number, displayNumber: `${step.number}.${String.fromCharCode(97 + index)}`},
      'process', -branchWidth / 2 + index * (processWidth + optionGap), optionY, processWidth, processHeight,
    ));
    groups.push({main, options}); cursor = optionY + processHeight + 120;
  });
  return groups;
}

function buildHorizontalGroups() {
  const groups = []; const processWidth = 230; const processHeight = 112;
  const decisionWidth = 190; const decisionHeight = 126; const optionGap = 34;
  let cursor = 0;
  selected.steps.forEach(step => {
    if (!(step.options && step.options.length)) {
      const main = makeNode(step, 'process', cursor, -processHeight / 2, processWidth, processHeight);
      groups.push({main}); cursor += processWidth + 110; return;
    }
    const main = makeNode(step, 'decision', cursor, -decisionHeight / 2, decisionWidth, decisionHeight);
    const branchHeight = step.options.length * processHeight + (step.options.length - 1) * optionGap;
    const optionX = cursor + decisionWidth + 106;
    const options = step.options.map((option, index) => makeNode(
      {...option, number: step.number, displayNumber: `${step.number}.${String.fromCharCode(97 + index)}`},
      'process', optionX, -branchHeight / 2 + index * (processHeight + optionGap), processWidth, processHeight,
    ));
    groups.push({main, options}); cursor = optionX + processWidth + 125;
  });
  return groups;
}

function anchor(node, side) {
  if (side === 'top') return {x: node.x + node.w / 2, y: node.y};
  if (side === 'bottom') return {x: node.x + node.w / 2, y: node.y + node.h};
  if (side === 'left') return {x: node.x, y: node.y + node.h / 2};
  return {x: node.x + node.w, y: node.y + node.h / 2};
}

function connectorPoints(edge) {
  const vertical = direction === 'vertical';
  const from = anchor(edge.from, vertical ? 'bottom' : 'right');
  const to = anchor(edge.to, vertical ? 'top' : 'left');
  const bend = vertical ? (from.y + to.y) / 2 : (from.x + to.x) / 2;
  return vertical ? [from, {x: from.x, y: bend}, {x: to.x, y: bend}, to]
    : [from, {x: bend, y: from.y}, {x: bend, y: to.y}, to];
}

function drawArrowHead(points) {
  const end = points[points.length - 1]; const previous = points[points.length - 2];
  const angle = Math.atan2(end.y - previous.y, end.x - previous.x); const size = 8;
  ctx.fillStyle = '#53657c'; ctx.beginPath(); ctx.moveTo(end.x, end.y);
  ctx.lineTo(end.x - size * Math.cos(angle - Math.PI / 6), end.y - size * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(end.x - size * Math.cos(angle + Math.PI / 6), end.y - size * Math.sin(angle + Math.PI / 6)); ctx.fill();
}

function drawEdge(edge) {
  const points = connectorPoints(edge);
  ctx.strokeStyle = edge.branch ? '#70839c' : '#53657c'; ctx.lineWidth = edge.branch ? 1.8 : 1.5;
  ctx.beginPath(); ctx.moveTo(points[0].x, points[0].y);
  points.slice(1).forEach(point => ctx.lineTo(point.x, point.y)); ctx.stroke(); drawArrowHead(points);
  if (!edge.label) return;
  const middle = points[1]; ctx.font = '600 10px sans-serif'; const text = edge.label;
  const width = Math.min(150, ctx.measureText(text).width + 12); const x = middle.x - width / 2; const y = middle.y - 19;
  ctx.fillStyle = '#101722'; ctx.strokeStyle = '#344257'; ctx.lineWidth = 1; roundedRect(x, y, width, 18, 5);
  ctx.fillStyle = '#cbd7e8'; ctx.textAlign = 'center'; ctx.fillText(text, middle.x, y + 12); ctx.textAlign = 'left';
}

function drawDecision(node, color) {
  const {x, y, w, h, step} = node; const cx = x + w / 2; const cy = y + h / 2;
  ctx.fillStyle = '#20242c'; ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
  ctx.moveTo(cx, y); ctx.lineTo(x + w, cy); ctx.lineTo(cx, y + h); ctx.lineTo(x, cy); ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.fillStyle = color; ctx.font = '600 9px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText(`${step.displayNumber || step.number}. DECISION`, cx, cy - 24);
  ctx.fillStyle = '#edf3ff'; ctx.font = '600 13px sans-serif';
  wrap(step.title, w - 54).slice(0, 2).forEach((line, index) => ctx.fillText(line, cx, cy + index * 17));
  ctx.fillStyle = '#aab8ca'; ctx.font = '10px sans-serif'; ctx.fillText(`${step.evidence.length} source ${step.evidence.length === 1 ? 'reference' : 'references'}`, cx, cy + 35);
  ctx.textAlign = 'left';
}

function drawProcess(node, color) {
  const {x, y, w, h, step} = node; ctx.fillStyle = '#202124'; ctx.strokeStyle = color; ctx.lineWidth = 1.5; roundedRect(x, y, w, h, 8);
  ctx.fillStyle = color; ctx.font = '600 10px sans-serif'; ctx.fillText(`${step.displayNumber || step.number}. ${step.phase.replace('_', ' ').toUpperCase()}`, x + 13, y + 20);
  ctx.fillStyle = '#edf3ff'; ctx.font = '600 14px sans-serif'; wrap(step.title, w - 28).forEach((line, index) => ctx.fillText(line, x + 13, y + 47 + index * 18));
  ctx.fillStyle = '#aab8ca'; ctx.font = '10px sans-serif'; ctx.fillText(`${step.evidence.length} source ${step.evidence.length === 1 ? 'reference' : 'references'}`, x + 13, y + h - 14);
}

function draw() {
  const box=canvas.getBoundingClientRect();ctx.clearRect(0,0,box.width,box.height);buildShapes();
  if (!selected) return;
  if (!selected.steps.length) {
    ctx.fillStyle='#91a0b8';ctx.font='15px sans-serif';ctx.fillText(selected.missing_coverage || 'Workflow pending source investigation.',80,260);return;
  }
  ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.scale,view.scale);
  edges.forEach(drawEdge);
  shapes.forEach(shape => {
    const color = phaseColors[shape.step.phase] || '#67a8ff';
    if (shape.kind === 'decision') drawDecision(shape, color); else drawProcess(shape, color);
  });ctx.restore();
}

function fitWorkflow() {
  buildShapes();
  const minX = shapes.length ? Math.min(...shapes.map(shape => shape.x)) : 0;
  const maxX = shapes.length ? Math.max(...shapes.map(shape => shape.x + shape.w)) : 230;
  const minY = shapes.length ? Math.min(...shapes.map(shape => shape.y)) : 0;
  const maxY = shapes.length ? Math.max(...shapes.map(shape => shape.y + shape.h)) : 112;
  const width = Math.max(230, maxX - minX);
  const height = Math.max(112, maxY - minY);
  const box=canvas.getBoundingClientRect();
  const availableWidth = Math.max(1, box.width - 100);
  const top = 170;
  const availableHeight = Math.max(1, box.height - top - 70);
  view.scale = Math.min(1.15, Math.max(.3, Math.min(availableWidth / width, availableHeight / height)));
  view.x = (box.width - width * view.scale) / 2 - minX * view.scale;
  view.y = top + (availableHeight - height * view.scale) / 2 - minY * view.scale;
  document.getElementById('zoom-label').textContent=`${Math.round(view.scale*100)}%`;
}

function resetWorkflowView() {
  buildShapes();
  if (!shapes.length) return;
  const first = shapes[0];
  const box = canvas.getBoundingClientRect();
  const headerBox = document.getElementById('workflow-header').getBoundingClientRect();
  const protectedTop = Math.max(170, headerBox.bottom - box.top + 32);
  view.scale = DEFAULT_ZOOM;
  view.x = box.width / 2 - (first.x + first.w / 2) * view.scale;
  view.y = protectedTop - first.y * view.scale;
  document.getElementById('zoom-label').textContent=`${Math.round(view.scale*100)}%`;
}

function canvasPoint(event) {
  const box=canvas.getBoundingClientRect();return {x:(event.clientX-box.left-view.x)/view.scale,y:(event.clientY-box.top-view.y)/view.scale};
}

function contains(shape, point) {
  if (shape.kind !== 'decision') return point.x >= shape.x && point.x <= shape.x + shape.w && point.y >= shape.y && point.y <= shape.y + shape.h;
  const cx = shape.x + shape.w / 2; const cy = shape.y + shape.h / 2;
  return Math.abs(point.x - cx) / (shape.w / 2) + Math.abs(point.y - cy) / (shape.h / 2) <= 1;
}

function showDetail(step) {
  const panel=document.getElementById('detail');panel.hidden=false;
  document.getElementById('detail-phase').textContent=step.phase.replace('_',' ');
  document.getElementById('detail-title').textContent=step.title;
  document.getElementById('detail-text').textContent=step.text;
  document.getElementById('detail-evidence').innerHTML=step.evidence.map((item,index)=>`
    <div class="evidence"><button data-evidence="${index}">${escapeHtml(item.symbol)}</button>
    <small>${escapeHtml(item.file)}:${item.code_start}${item.code_end!==item.code_start?`–${item.code_end}`:''}</small></div>`).join('');
  panel.querySelectorAll('[data-evidence]').forEach(button=>button.addEventListener('click',()=>openEvidence(step.evidence[Number(button.dataset.evidence)])));
}

canvas.addEventListener('pointerdown',event=>{dragging=true;pointer={x:event.clientX,y:event.clientY};dragStart={...pointer};canvas.setPointerCapture(event.pointerId)});
canvas.addEventListener('pointermove',event=>{if(!dragging)return;view.x+=event.clientX-pointer.x;view.y+=event.clientY-pointer.y;pointer={x:event.clientX,y:event.clientY};draw()});
canvas.addEventListener('pointerup',event=>{const moved=Math.hypot(event.clientX-dragStart.x,event.clientY-dragStart.y);dragging=false;if(moved<4){const p=canvasPoint(event);const hit=shapes.find(shape=>contains(shape,p));if(hit)showDetail(hit.step)}});
canvas.addEventListener('wheel',event=>{event.preventDefault();view.scale=Math.max(.3,Math.min(2,view.scale*(event.deltaY<0?1.1:.9)));document.getElementById('zoom-label').textContent=`${Math.round(view.scale*100)}%`;draw()},{passive:false});
document.getElementById('zoom-in').onclick=()=>{view.scale=Math.min(2,view.scale*1.15);document.getElementById('zoom-label').textContent=`${Math.round(view.scale*100)}%`;draw()};
document.getElementById('zoom-out').onclick=()=>{view.scale=Math.max(.3,view.scale/1.15);document.getElementById('zoom-label').textContent=`${Math.round(view.scale*100)}%`;draw()};
document.getElementById('fit').onclick=()=>{fitWorkflow();draw()};
function setDirection(nextDirection) {
  direction = nextDirection;
  ['horizontal', 'vertical'].forEach(value => {
    const button = document.getElementById(`direction-${value}`);
    const active = value === direction;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  fitWorkflow(); draw();
}
document.getElementById('direction-horizontal').onclick=()=>setDirection('horizontal');
document.getElementById('direction-vertical').onclick=()=>setDirection('vertical');
document.getElementById('close-detail').onclick=()=>{document.getElementById('detail').hidden=true};
document.getElementById('search').addEventListener('input',renderCatalog);
window.addEventListener('resize',resize);

const state=DATA.workflow_state||{};
if(state.state==='stale_features'){const banner=document.getElementById('state-banner');banner.hidden=false;banner.textContent='This catalog was generated from older source. Run tldrgraph init to refresh it.'}
if(state.state&&state.state!=='ready'&&state.state!=='stale_features'){const banner=document.getElementById('state-banner');banner.hidden=false;banner.textContent=state.error||'No valid v3 workflow catalog is available. Run tldrgraph init.'}
renderCatalog();if(DATA.workflows.length)selectWorkflow(DATA.workflows[0].id);resize();
