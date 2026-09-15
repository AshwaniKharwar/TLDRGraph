'use strict';

const canvas = document.getElementById('workflow-canvas');
const ctx = canvas.getContext('2d');
const phaseColors = {user_action:'#67a8ff',frontend:'#8a9cff',request:'#c68aff',backend:'#56dfcc',persistence:'#7bd879',external:'#ffca6a',response:'#ff9b73',ui_update:'#ff88ba'};
let selected = null;
let shapes = [];
let view = {x:80,y:210,scale:1};
let dragging = false;
let pointer = null;
let dragStart = null;

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
    step.evidence.forEach(item => values.push(item.file, item.symbol));
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
  shapes = [];
  if (!selected || !selected.steps.length) return;
  selected.steps.forEach((step,index) => shapes.push({step,x:index*260,y:0,w:210,h:112}));
}

function drawArrow(a,b) {
  const x1=a.x+a.w, y1=a.y+a.h/2, x2=b.x, y2=b.y+b.h/2;
  ctx.strokeStyle='#436181';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
  ctx.fillStyle='#436181';ctx.beginPath();ctx.moveTo(x2,y2);ctx.lineTo(x2-10,y2-6);ctx.lineTo(x2-10,y2+6);ctx.fill();
}

function draw() {
  const box=canvas.getBoundingClientRect();ctx.clearRect(0,0,box.width,box.height);buildShapes();
  if (!selected) return;
  if (!selected.steps.length) {
    ctx.fillStyle='#91a0b8';ctx.font='15px sans-serif';ctx.fillText(selected.missing_coverage || 'Workflow pending source investigation.',80,260);return;
  }
  ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.scale,view.scale);
  for(let i=0;i<shapes.length-1;i++) drawArrow(shapes[i],shapes[i+1]);
  shapes.forEach(shape => {
    const {step,x,y,w,h}=shape;ctx.fillStyle='#141d2b';ctx.strokeStyle=phaseColors[step.phase]||'#67a8ff';ctx.lineWidth=2;roundedRect(x,y,w,h,12);
    ctx.fillStyle=phaseColors[step.phase]||'#67a8ff';ctx.font='600 10px sans-serif';ctx.fillText(`${step.number}. ${step.phase.replace('_',' ').toUpperCase()}`,x+14,y+21);
    ctx.fillStyle='#edf3ff';ctx.font='600 14px sans-serif';wrap(step.title,180).forEach((line,index)=>ctx.fillText(line,x+14,y+48+index*18));
    ctx.fillStyle='#91a0b8';ctx.font='11px sans-serif';ctx.fillText(`${step.evidence.length} source ${step.evidence.length===1?'reference':'references'}`,x+14,y+h-14);
  });ctx.restore();
}

function fitWorkflow() {
  const width = Math.max(1,(selected && selected.steps.length || 1)*260-50);
  const box=canvas.getBoundingClientRect();view.scale=Math.min(1.15,Math.max(.35,(box.width-120)/width));
  view.x=70;view.y=Math.max(180,box.height/2-56*view.scale);
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
document.getElementById('close-detail').onclick=()=>{document.getElementById('detail').hidden=true};
document.getElementById('search').addEventListener('input',renderCatalog);
window.addEventListener('resize',resize);

const state=DATA.workflow_state||{};
if(state.state==='stale_features'){const banner=document.getElementById('state-banner');banner.hidden=false;banner.textContent='This catalog was generated from older source. Run tldrgraph init to refresh it.'}
if(state.state&&state.state!=='ready'&&state.state!=='stale_features'){const banner=document.getElementById('state-banner');banner.hidden=false;banner.textContent=state.error||'No valid v3 workflow catalog is available. Run tldrgraph init.'}
renderCatalog();if(DATA.workflows.length)selectWorkflow(DATA.workflows[0].id);resize();
