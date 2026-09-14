/* Grouped, searchable feature catalog for Workflow Explorer. */

const collapsedWorkflowAreas = new Set();

function workflowMatches(w, area, query) {
  if (!query) return true;
  const values = [
    w.title, w.root_node, w.file, w.summary, w.audience,
    area.title, area.summary, area.perspective,
  ];
  (w.steps || []).forEach(step => values.push(
    step.display_label, step.intent, step.symbol, step.file, step.phase
  ));
  return values.some(value => String(value || '').toLowerCase().includes(query));
}

function workflowAreas() {
  const configured = DATA.workflow_areas || [];
  if (configured.length) return configured;
  const seen = new Map();
  (DATA.workflows || []).forEach(w => {
    const id = w.area_id || 'legacy_features';
    if (!seen.has(id)) seen.set(id, {
      id: id,
      title: w.area_title || 'Legacy features',
      summary: w.area_summary || '',
      perspective: w.perspective || 'technical',
      order: w.area_order || 0,
    });
  });
  return Array.from(seen.values());
}

function statusLabel(workflow) {
  const status = workflow.status || 'generated';
  if (status === 'generated') return `${workflow.step_count} steps`;
  if (status === 'partial') return `${workflow.step_count} known`;
  return 'pending';
}

function featureCardHtml(w) {
  const status = w.status || 'generated';
  const isActive = w.id === activeWorkflowId;
  return `
    <button class="flow-card ${isActive ? 'active' : ''}" data-flow-id="${escapeHtml(w.id)}" type="button">
      <div class="flow-card-top">
        <span class="flow-card-title">${escapeHtml(w.title)}</span>
        <span class="flow-status-badge ${escapeHtml(status)}">${escapeHtml(statusLabel(w))}</span>
      </div>
      <div class="flow-card-summary">${escapeHtml(w.summary || '')}</div>
      <div class="flow-card-layers">
        <span class="flow-audience-badge">${escapeHtml(w.audience || 'developer')}</span>
        ${status === 'partial' ? '<span class="flow-coverage-note">Partial coverage</span>' : ''}
      </div>
    </button>`;
}

function areaHtml(area, workflows, searching) {
  const collapsed = !searching && collapsedWorkflowAreas.has(area.id);
  const generated = workflows.filter(w => (w.status || 'generated') === 'generated').length;
  return `
    <section class="flow-area ${collapsed ? 'collapsed' : ''}" data-area-id="${escapeHtml(area.id)}">
      <button class="flow-area-header" data-toggle-area="${escapeHtml(area.id)}" type="button" aria-expanded="${!collapsed}">
        <span class="flow-area-chevron">⌄</span>
        <span class="flow-area-copy">
          <span class="flow-area-title">${escapeHtml(area.title)}</span>
          <span class="flow-area-summary">${escapeHtml(area.summary || '')}</span>
        </span>
        <span class="flow-area-count">${generated}/${workflows.length}</span>
      </button>
      <div class="flow-area-features">${workflows.map(featureCardHtml).join('')}</div>
    </section>`;
}

function perspectiveHtml(perspective, areas, workflows, searching) {
  const label = perspective === 'product' ? 'Product capabilities' : 'Technical capabilities';
  const body = areas.map(area => {
    const members = workflows.filter(w => w.area_id === area.id);
    return members.length ? areaHtml(area, members, searching) : '';
  }).join('');
  return body ? `<div class="flow-perspective"><div class="flow-perspective-title">${label}</div>${body}</div>` : '';
}

function renderWorkflowsList() {
  const listEl = document.getElementById('flows-list');
  if (!listEl) return;

  const allWorkflows = DATA.workflows || [];
  const areas = workflowAreas();
  const areaById = new Map(areas.map(area => [area.id, area]));
  const workflows = allWorkflows.filter(w => workflowMatches(
    w, areaById.get(w.area_id) || {}, flowSearchQuery
  ));
  const countEl = document.getElementById('flows-list-count');
  const complete = workflows.filter(w => (w.status || 'generated') === 'generated').length;
  if (countEl) {
    const completedFeatures = allWorkflows.filter(
      w => (w.status || 'generated') === 'generated'
    ).length;
    // Search results must not make the summary disappear; only the absence of
    // completed features does.
    countEl.hidden = completedFeatures === 0;
    countEl.textContent = `Features (${complete}/${workflows.length} complete)`;
  }

  if (!workflows.length) {
    const state = (DATA.workflow_state || {}).state || 'missing_features';
    const messages = {
      missing_features: 'No feature catalog found. Run tldrgraph init to create it.',
      invalid_features: 'The saved feature catalog is invalid. Run tldrgraph init to refresh it.',
      stale_features: 'The saved catalog is stale. Complete the feature-workflow handoff.',
      empty_features: 'No source-backed capabilities were saved for this project.',
      ready: allWorkflows.length ? 'No matching capabilities found.' : 'No saved capabilities found.',
    };
    listEl.innerHTML = `<div class="flows-list-message">${escapeHtml(messages[state] || messages.ready)}</div>`;
    selectWorkflow(null);
    return;
  }

  const orderedAreas = [...areas].sort((a, b) => (a.order || 0) - (b.order || 0));
  listEl.innerHTML = ['product', 'technical'].map(perspective => perspectiveHtml(
    perspective,
    orderedAreas.filter(area => (area.perspective || 'technical') === perspective),
    workflows,
    Boolean(flowSearchQuery)
  )).join('');

  listEl.onclick = event => {
    const toggle = event.target.closest('[data-toggle-area]');
    if (toggle) {
      const id = toggle.getAttribute('data-toggle-area');
      if (collapsedWorkflowAreas.has(id)) collapsedWorkflowAreas.delete(id);
      else collapsedWorkflowAreas.add(id);
      renderWorkflowsList();
      return;
    }
    const card = event.target.closest('[data-flow-id]');
    if (card) selectWorkflow(card.getAttribute('data-flow-id'));
  };
}
