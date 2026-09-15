'use strict';

const canvas = document.getElementById('workflow-canvas');
const ctx = canvas.getContext('2d');
const phaseColors = {user_action:'#67a8ff',frontend:'#8a9cff',request:'#c68aff',backend:'#56dfcc',persistence:'#7bd879',external:'#ffca6a',response:'#ff9b73',ui_update:'#ff88ba'};
let selected = null;
let shapes = [];
let edges = [];
let view = {x:80,y:210,scale:1};
let dragging = false;
let pointer = null;
let dragStart = null;
let direction = 'horizontal';

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
  fitWorkflow(); renderCatalog(); draw();
}

function resize() {
  const ratio = window.devicePixelRatio || 1;
  const box = canvas.getBoundingClientRect();
  canvas.width = Math.round(box.width * ratio); canvas.height = Math.round(box.height * ratio);
  ctx.setTransform(ratio,0,0,ratio,0,0); draw();
}

function roundedRect(x,y,w,h,r) {
  ctx.beginPath(); ctx.roundRect(x,y,w,h,r); ctx.fill(); ctx.stroke();
}

function wrap(text, width) {
  const words = String(text || '').split(/\s+/); const lines = []; let line = '';
  words.forEach(word => {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > width && line) { lines.push(line); line = word; } else line = next;
  });
  if (line) lines.push(line); return lines.slice(0,3);
}

function buildShapes() {
  shapes = []; edges = [];
  if (!selected || !selected.steps.length) return;
  const groups = selected.steps.map((step,index) => {
    const items = step.options && step.options.length ? step.options.map((option,optionIndex) => ({
      step: {...option, number: step.number, displayNumber: `${step.number}.${String.fromCharCode(97+optionIndex)}`},
      x:index*280,y:0,w:230,h:112,
    })) : [{step,x:index*280,y:0,w:230,h:112}];
    const gap = 28;
    if (direction === 'horizontal') {
      const height = items.length*112 + (items.length-1)*gap;
      items.forEach((shape,shapeIndex) => {
        shape.x = index * 280;
        shape.y = shapeIndex * (112 + gap) - height / 2 + 56;
      });
    } else {
      const width = items.length * 230 + (items.length - 1) * gap;
      items.forEach((shape,shapeIndex) => {
        shape.x = shapeIndex * (230 + gap) - width / 2 + 115;
        shape.y = index * 160;
      });
    }
    shapes.push(...items);
    return items;
  });
  for(let i=0;i<groups.length-1;i++) {
    groups[i].forEach(from => groups[i+1].forEach(to => edges.push({from,to})));
  }
}

function drawArrow(a,b) {
  const horizontal = direction === 'horizontal';
  const x1 = horizontal ? a.x + a.w : a.x + a.w / 2;
  const y1 = horizontal ? a.y + a.h / 2 : a.y + a.h;
  const x2 = horizontal ? b.x : b.x + b.w / 2;
  const y2 = horizontal ? b.y + b.h / 2 : b.y;
  ctx.strokeStyle='#436181';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
  ctx.fillStyle='#436181';ctx.beginPath();
  if (horizontal) { ctx.moveTo(x2,y2);ctx.lineTo(x2-10,y2-6);ctx.lineTo(x2-10,y2+6); }
  else { ctx.moveTo(x2,y2);ctx.lineTo(x2-6,y2-10);ctx.lineTo(x2+6,y2-10); }
  ctx.fill();
}

function draw() {
  const box=canvas.getBoundingClientRect();ctx.clearRect(0,0,box.width,box.height);buildShapes();
  if (!selected) return;
  if (!selected.steps.length) {
    ctx.fillStyle='#91a0b8';ctx.font='15px sans-serif';ctx.fillText(selected.missing_coverage || 'Workflow pending source investigation.',80,260);return;
  }
  ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.scale,view.scale);
  edges.forEach(edge => drawArrow(edge.from,edge.to));
  shapes.forEach(shape => {
    const {step,x,y,w,h}=shape;ctx.fillStyle='#141d2b';ctx.strokeStyle=phaseColors[step.phase]||'#67a8ff';ctx.lineWidth=2;roundedRect(x,y,w,h,12);
    ctx.fillStyle=phaseColors[step.phase]||'#67a8ff';ctx.font='600 10px sans-serif';ctx.fillText(`${step.displayNumber || step.number}. ${step.phase.replace('_',' ').toUpperCase()}`,x+14,y+21);
    ctx.fillStyle='#edf3ff';ctx.font='600 14px sans-serif';wrap(step.title,200).forEach((line,index)=>ctx.fillText(line,x+14,y+48+index*18));
    ctx.fillStyle='#91a0b8';ctx.font='11px sans-serif';ctx.fillText(`${step.evidence.length} source ${step.evidence.length===1?'reference':'references'}`,x+14,y+h-14);
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

function canvasPoint(event) {
  const box=canvas.getBoundingClientRect();return {x:(event.clientX-box.left-view.x)/view.scale,y:(event.clientY-box.top-view.y)/view.scale};
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
canvas.addEventListener('pointerup',event=>{const moved=Math.hypot(event.clientX-dragStart.x,event.clientY-dragStart.y);dragging=false;if(moved<4){const p=canvasPoint(event);const hit=shapes.find(s=>p.x>=s.x&&p.x<=s.x+s.w&&p.y>=s.y&&p.y<=s.y+s.h);if(hit)showDetail(hit.step)}});
canvas.addEventListener('wheel',event=>{event.preventDefault();view.scale=Math.max(.3,Math.min(2,view.scale*(event.deltaY<0?1.1:.9)));document.getElementById('zoom-label').textContent=`${Math.round(view.scale*100)}%`;draw()},{passive:false});
document.getElementById('zoom-in').onclick=()=>{view.scale=Math.min(2,view.scale*1.15);draw()};
document.getElementById('zoom-out').onclick=()=>{view.scale=Math.max(.3,view.scale/1.15);draw()};
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
