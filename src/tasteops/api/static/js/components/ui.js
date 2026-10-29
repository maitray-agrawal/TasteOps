/**
 * TasteOps Reusable UI Primitives.
 *
 * Implements loading skeletons, empty states, error cards with retry actions,
 * status badges, workflow stepper pipelines, and toast notifications.
 */

export function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function formatDate(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch (_) {
    return isoString;
  }
}

export function renderLoading(message = 'Loading workspace data...') {
  return `
    <div class="fade-in" style="padding: 3rem 0; text-align: center;">
      <div style="display: inline-block; width: 44px; height: 44px; border: 3px solid rgba(99, 102, 241, 0.2); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 1.25rem;"></div>
      <p style="color: var(--text-secondary); font-size: 0.95rem;">${escapeHtml(message)}</p>
      <style>@keyframes spin { to { transform: rotate(360deg); } }</style>
    </div>
  `;
}

export function renderSkeletonGrid(count = 3) {
  return `
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem;">
      ${Array.from({ length: count }).map(() => `
        <div class="card skeleton-card">
          <div class="skeleton-box skeleton-title"></div>
          <div class="skeleton-box skeleton-text"></div>
          <div class="skeleton-box skeleton-text" style="width: 80%;"></div>
        </div>
      `).join('')}
    </div>
  `;
}

export function renderEmptyState({ icon = '📂', title = 'No Data Available', description = 'Nothing to display here yet.', actionText = null, actionId = null }) {
  return `
    <div class="empty-state fade-in">
      <div class="empty-state-icon">${icon}</div>
      <h3 class="empty-state-title">${escapeHtml(title)}</h3>
      <p class="empty-state-description">${escapeHtml(description)}</p>
      ${actionText ? `
        <button id="${actionId || 'empty-action-btn'}" class="btn btn-primary">
          ${escapeHtml(actionText)}
        </button>
      ` : ''}
    </div>
  `;
}

export function renderError({ title = 'Failed to Load', error = null, retryId = 'retry-btn' }) {
  const detail = error?.detail || error?.message || 'An unexpected server error occurred.';
  const code = error?.code || 'UNKNOWN_ERROR';
  const correlationId = error?.correlationId;

  return `
    <div class="error-banner fade-in">
      <div class="error-banner-icon">⚠️</div>
      <div class="error-banner-content">
        <div class="error-banner-title">${escapeHtml(title)}</div>
        <div class="error-banner-detail">${escapeHtml(detail)}</div>
        <div style="display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;">
          <span style="font-family: var(--font-mono); font-size: 0.775rem; color: var(--text-muted);">
            CODE: ${escapeHtml(code)}${correlationId ? ` | REQ: ${escapeHtml(correlationId)}` : ''}
          </span>
          <button id="${retryId}" class="btn btn-secondary btn-sm" style="margin-left: auto;">
            🔄 Retry
          </button>
        </div>
      </div>
    </div>
  `;
}

export function renderBadge(state) {
  const s = String(state || '').toUpperCase();
  let badgeClass = 'badge-created';

  if (s === 'AWAITING_APPROVAL') {
    badgeClass = 'badge-awaiting-approval';
  } else if (s === 'APPROVED') {
    badgeClass = 'badge-approved';
  } else if (s === 'EXECUTING' || s === 'RUNNING') {
    badgeClass = 'badge-executing';
  } else if (s === 'COMPLETED' || s === 'EXECUTED') {
    badgeClass = 'badge-completed';
  } else if (s === 'FAILED') {
    badgeClass = 'badge-failed';
  } else if (s === 'SKIPPED') {
    badgeClass = 'badge-skipped';
  } else if (s === 'PENDING') {
    badgeClass = 'badge-pending';
  } else if (s === 'NOT_CONFIGURED') {
    badgeClass = 'badge-not-configured';
  } else if (s.includes('RUNNING') || s.includes('PARSED') || s.includes('READY')) {
    badgeClass = 'badge-in-progress';
  }

  return `<span class="badge ${badgeClass}">${escapeHtml(s)}</span>`;
}

export function renderStatePipeline(currentState) {
  const s = String(currentState || '').toUpperCase();
  const isFailed = s === 'FAILED';

  // 5 Canonical Human-Centric Milestones
  const milestones = [
    {
      id: 1,
      name: 'Concept Ingestion',
      desc: 'Venue Brief & Parameters',
      states: ['CREATED', 'INTENT_PARSED'],
    },
    {
      id: 2,
      name: 'Cultural Intelligence',
      desc: 'Qloo Taste Graph Signals',
      states: ['CULTURAL_TWIN_CREATED', 'QLOO_RESOLVED', 'CULTURAL_MATRIX_READY'],
    },
    {
      id: 3,
      name: 'Agent Synthesis',
      desc: 'Multi-Agent Blueprint',
      states: ['AGENTS_RUNNING', 'PLAN_GENERATED'],
    },
    {
      id: 4,
      name: 'Governance Gate',
      desc: 'Mandatory Human Approval',
      states: ['VALIDATED', 'AWAITING_APPROVAL'],
    },
    {
      id: 5,
      name: 'Governed Activation',
      desc: 'Dispatch & Procurement',
      states: ['APPROVED', 'EXECUTING', 'COMPLETED'],
    },
  ];

  // Determine current active milestone index (0 to 4)
  let activeIndex = 0;
  if (milestones[1].states.includes(s)) activeIndex = 1;
  else if (milestones[2].states.includes(s)) activeIndex = 2;
  else if (milestones[3].states.includes(s)) activeIndex = 3;
  else if (milestones[4].states.includes(s)) activeIndex = 4;
  else if (isFailed) activeIndex = 3; // Typically halts at governance/validation

  const isCompleted = s === 'COMPLETED';

  // Human-friendly stage name and next action
  let stageTitle = `Milestone ${activeIndex + 1} of 5: ${milestones[activeIndex].name}`;
  let stageBadgeText = s.replace(/_/g, ' ');
  let stageBadgeClass = 'badge-in-progress';
  let nextActionHtml = '';

  if (isFailed) {
    stageTitle = 'Workflow Halted — Validation or Policy Check Failed';
    stageBadgeText = 'Validation Failed';
    stageBadgeClass = 'badge-failed';
    nextActionHtml = '<strong>Next Action:</strong> Inspect governance violations in the failure diagnostics below, adjust brief constraints or brand partner thresholds, and rerun synthesis.';
  } else if (s === 'AWAITING_APPROVAL') {
    stageTitle = 'Milestone 4 of 5: Governance Checks Passed — Awaiting Human Approval';
    stageBadgeText = 'Awaiting Approval';
    stageBadgeClass = 'badge-awaiting-approval';
    nextActionHtml = '<strong>Next Action:</strong> Human curator review required. Navigate to the <em>Approval Gate</em> tab to review policy compliance and sign off on execution.';
  } else if (s === 'APPROVED') {
    stageTitle = 'Milestone 5 of 5: Human Approval Granted — Ready for Execution';
    stageBadgeText = 'Approved';
    stageBadgeClass = 'badge-approved';
    nextActionHtml = '<strong>Next Action:</strong> Plan approved by curator. Click <em>Dispatch Execution Tasks</em> to stage real-world procurement and playlist specifications.';
  } else if (s === 'EXECUTING' || s === 'RUNNING') {
    stageTitle = 'Milestone 5 of 5: Governed Task Execution In Progress';
    stageBadgeText = 'Executing Tasks';
    stageBadgeClass = 'badge-executing';
    nextActionHtml = '<strong>Next Action:</strong> Connectors are generating Spotify playlist specs, procurement purchase orders, and partner outreach packets.';
  } else if (isCompleted) {
    stageTitle = 'Milestone 5 of 5: Execution Completed & Cryptographically Verified';
    stageBadgeText = 'Execution Complete';
    stageBadgeClass = 'badge-completed';
    nextActionHtml = '<strong>Next Action:</strong> Review final deliverables in the <em>Results</em> screen or inspect the immutable audit record in the <em>Audit Ledger</em>.';
  } else {
    nextActionHtml = '<strong>Next Action:</strong> Autonomous cultural agents are analyzing cross-domain taste vectors. Real-time updates streaming below.';
  }

  return `
    <div class="tasteops-workflow-progress">
      <!-- Top Status Banner -->
      <div class="workflow-progress-header">
        <div class="workflow-progress-title-block">
          <div class="workflow-progress-stage">${escapeHtml(stageTitle)}</div>
          <div class="workflow-progress-action">${nextActionHtml}</div>
        </div>
        <div class="workflow-progress-badge-wrap">
          <span class="badge ${stageBadgeClass}" style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.04em;">
            ${escapeHtml(stageBadgeText)}
          </span>
        </div>
      </div>

      <!-- Responsive 5-Milestone Track -->
      <div class="workflow-stepper">
        ${milestones.map((m, idx) => {
          let nodeClass = 'upcoming';
          let icon = String(idx + 1);

          if (isFailed && idx === activeIndex) {
            nodeClass = 'failed';
            icon = '✕';
          } else if (idx < activeIndex || (idx === activeIndex && isCompleted)) {
            nodeClass = 'completed';
            icon = '✓';
          } else if (idx === activeIndex) {
            nodeClass = 'active';
            icon = String(idx + 1);
          }

          const isConnectorCompleted = !isFailed && (idx < activeIndex || (idx === activeIndex && isCompleted));

          return `
            <div class="stepper-step ${nodeClass}">
              <div class="stepper-circle">
                ${icon}
              </div>
              <div class="stepper-meta">
                <span class="stepper-num">Phase 0${idx + 1}</span>
                <span class="stepper-label">${escapeHtml(m.name)}</span>
                <span class="stepper-sublabel">${escapeHtml(m.desc)}</span>
              </div>
            </div>
            ${idx < milestones.length - 1 ? `
              <div class="stepper-connector ${isConnectorCompleted ? 'completed' : ''}"></div>
            ` : ''}
          `;
        }).join('')}
      </div>

      <!-- Collapsible Technical Telemetry & Diagnostics -->
      <details class="pipeline-diagnostics-drawer">
        <summary class="diagnostics-summary">
          <span>🛠️ Technical FSM State Machine &amp; Telemetry Details</span>
          <span class="diagnostics-summary-hint">Authoritative State: <code>${escapeHtml(s)}</code></span>
        </summary>
        <div class="diagnostics-body">
          <div class="diagnostics-grid">
            <div class="diagnostics-item">
              <span class="diagnostics-label">Authoritative State:</span>
              <strong class="diagnostics-val" style="color: var(--cyan);">${escapeHtml(s)}</strong>
            </div>
            <div class="diagnostics-item">
              <span class="diagnostics-label">State Machine Invariant:</span>
              <span class="diagnostics-val">Deterministic 13-state sequential transition model</span>
            </div>
            <div class="diagnostics-item">
              <span class="diagnostics-label">Human Gate Enforcement:</span>
              <span class="diagnostics-val" style="color: #34d399;">Mandatory curator sign-off before task execution</span>
            </div>
            <div class="diagnostics-item">
              <span class="diagnostics-label">Event Transport:</span>
              <span class="diagnostics-val">Server-Sent Events (SSE) with reconnect resilience</span>
            </div>
          </div>
        </div>
      </details>
    </div>
  `;
}

export function renderAgentStatusBadge(status) {
  const s = String(status || '').toUpperCase();
  let badgeStyle = '';
  let icon = '✦';

  switch (s) {
    case 'RUNNING':
      badgeStyle = 'background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.35);';
      icon = '⚡';
      break;
    case 'COMPLETED':
      badgeStyle = 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35);';
      icon = '✓';
      break;
    case 'FAILED':
      badgeStyle = 'background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.35);';
      icon = '✕';
      break;
    case 'RETRYING':
      badgeStyle = 'background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35);';
      icon = '🔄';
      break;
    case 'BLOCKED':
      badgeStyle = 'background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.35);';
      icon = '⏸';
      break;
    case 'AWAITING_APPROVAL':
      badgeStyle = 'background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4);';
      icon = '⚖️';
      break;
    default:
      badgeStyle = 'background: rgba(255, 255, 255, 0.08); color: #e2e8f0; border: 1px solid rgba(255, 255, 255, 0.15);';
      icon = '✦';
  }

  return `<span class="badge" style="${badgeStyle} display: inline-flex; align-items: center; gap: 0.35rem; font-weight: 700; letter-spacing: 0.04em;"><span>${icon}</span><span>${escapeHtml(s)}</span></span>`;
}

export function renderSubNav(sessionId, activeTab) {
  const sid = sessionId || (typeof window !== 'undefined' && window.currentSessionId) || '';
  const tabs = [
    { key: 'overview', label: 'Overview & Twin', icon: '🧬', path: `/sessions/${sid}` },
    { key: 'activity', label: 'Agent Activity', icon: '🤖', path: `/sessions/${sid}/activity` },
    { key: 'blueprint', label: 'Architectural Blueprint', icon: '📐', path: `/sessions/${sid}/blueprint` },
    { key: 'approval', label: 'Approval Gate', icon: '⚖️', path: `/sessions/${sid}/approval` },
    { key: 'execution', label: 'Execution Engine', icon: '⚡', path: `/sessions/${sid}/execution` },
    { key: 'ledger', label: 'Audit Ledger', icon: '📜', path: `/sessions/${sid}/ledger` },
  ];

  return `
    <nav class="session-nav-bar tabs-nav" aria-label="Session Navigation">
      <div class="session-tabs-container" role="tablist">
        ${tabs.map(t => {
          const isActive = activeTab === t.key;
          return `
            <a 
              href="${t.path}" 
              role="tab"
              aria-selected="${isActive ? 'true' : 'false'}"
              class="session-tab-item tab-btn ${isActive ? 'active' : ''}" 
              id="session-tab-${t.key}"
              data-tab="${t.key}"
              onclick="if (window.tasteopsRouter) { event.preventDefault(); window.tasteopsRouter.navigate('${t.path}'); }"
            >
              <span class="session-tab-icon" aria-hidden="true">${t.icon}</span>
              <span class="session-tab-label">${escapeHtml(t.label)}</span>
            </a>
          `;
        }).join('')}
      </div>
    </nav>
  `;
}

// ---------------------------------------------------------------------------
// Centralized Activity Capsule / Telemetry Notification System
// Rule: Exactly ONE visible capsule. In-place smooth progression. Never stacks.
// ---------------------------------------------------------------------------

let activeCapsuleEl = null;
let activeCapsuleTimer = null;

/**
 * Intelligent error and message translator.
 * Maps raw backend technical strings into calm, editorial product telemetry.
 */
function translateToastMessage(input, defaultType = 'info') {
  if (typeof input === 'object' && input !== null) {
    return {
      title: input.title || 'Telemetry',
      text: input.text || input.message || '',
      type: input.type || defaultType,
      actionText: input.actionText || null,
      onAction: input.onAction || null,
    };
  }

  const raw = String(input || '').trim();
  let title = '';
  let text = '';
  let type = defaultType;
  let actionText = null;
  let onAction = null;

  // Pattern 1: Session not found / expired in cache/state store
  if (/not found in active cache|not found in.*state store|session.*not found/i.test(raw)) {
    title = 'Session Expired';
    text = 'This workspace is no longer active. Reopen the space to continue.';
    type = 'error';
    actionText = 'Reopen workspace →';
    onAction = () => {
      if (window.tasteopsRouter) window.tasteopsRouter.navigate('/spaces/new');
    };
  }
  // Pattern 2: Approval gate enforcement / invalid workflow transition
  else if (/cannot transition from.*to|Invalid workflow transition/i.test(raw)) {
    title = 'Approval Gate Required';
    text = 'Curatorial sign-off must be recorded before physical execution can begin.';
    type = 'warning';
  }
  // Pattern 3: Initializing pipeline
  else if (/initializing autonomous spatial curation|building your cultural twin/i.test(raw)) {
    title = 'Building Cultural Twin';
    text = 'Synthesizing spatial brief and cultural context.';
    type = 'loading';
  }
  // Pattern 4: Reading signals / running Qloo & agents
  else if (/running qloo cultural matrix|reading cultural signals/i.test(raw)) {
    title = 'Reading Cultural Signals';
    text = 'Querying Qloo cross-domain taste graph & activating agents.';
    type = 'loading';
  }
  // Pattern 5: 3 agents completed
  else if (/all 3 specialized agents completed|3 agents synthesizing/i.test(raw)) {
    title = 'Curatorial Synthesis Complete';
    text = 'Spatial, sonic, and brand agents ready for human approval.';
    type = 'success';
  }
  // Pattern 6: Recording curator sign-off / binding SHA-256
  else if (/binding sha-256|recording curator sign-off/i.test(raw)) {
    title = 'Recording Sign-Off';
    text = 'Securing cryptographic approval gate with human signature.';
    type = 'loading';
  }
  // Pattern 7: Execution staged
  else if (/plan approved & physical execution|workflow execution completed/i.test(raw)) {
    title = 'Execution Staged';
    text = 'Artifacts and operational orders are ready for review.';
    type = 'success';
  }
  // Pattern 8: Space registered and analyzed
  else if (/space registered and pipeline analyzed/i.test(raw)) {
    title = 'Cultural Twin Established';
    text = 'Opening curatorial workspace...';
    type = 'success';
  }
  // Pattern 9: Generic error with UUID or HTTP jargon
  else if (type === 'error' || /failed|exception|error:/i.test(raw)) {
    type = 'error';
    const cleaned = raw
      .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, 'workspace')
      .replace(/HTTP \d+[:\s]*/gi, '')
      .replace(/^error:\s*/i, '')
      .replace(/Approval\/Execution error:\s*/i, '');
    title = 'Operation Notice';
    text = cleaned.length > 90 ? cleaned.slice(0, 88) + '...' : cleaned;
  }
  // Normal messages
  else {
    if (raw.length <= 48 && !raw.includes('.')) {
      title = raw;
      text = '';
    } else {
      const parts = raw.split(/(?<=[.!?])\s+/);
      title = parts[0] || 'Notice';
      text = parts.slice(1).join(' ') || '';
    }
  }

  // Strip any lingering raw UUIDs from title & text
  title = title.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '').trim();
  text = text.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '').trim();

  return { title, text, type, actionText, onAction };
}

export function showToast(input, type = 'info', duration = null) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const { title, text, type: resolvedType, actionText, onAction } = translateToastMessage(input, type);

  // Determine auto-dismiss timeout
  let autoDismissMs = duration;
  if (!autoDismissMs) {
    if (resolvedType === 'loading') {
      autoDismissMs = 12000; // loading safety timeout
    } else if (resolvedType === 'error') {
      autoDismissMs = actionText ? 9000 : 7000;
    } else if (resolvedType === 'warning') {
      autoDismissMs = 5500;
    } else {
      autoDismissMs = 3800; // compact info/success
    }
  }

  // Clear any existing dismissal timer
  if (activeCapsuleTimer) {
    clearTimeout(activeCapsuleTimer);
    activeCapsuleTimer = null;
  }

  // Icon markup based on resolved type
  let iconHtml = '';
  if (resolvedType === 'loading') {
    iconHtml = '<div class="telemetry-spinner" aria-hidden="true"></div>';
  } else if (resolvedType === 'success') {
    iconHtml = '<span class="telemetry-dot dot-success" aria-hidden="true"></span>';
  } else if (resolvedType === 'error') {
    iconHtml = '<span class="telemetry-dot dot-error" aria-hidden="true"></span>';
  } else if (resolvedType === 'warning') {
    iconHtml = '<span class="telemetry-dot dot-warning" aria-hidden="true"></span>';
  } else {
    iconHtml = '<span class="telemetry-dot dot-info" aria-hidden="true"></span>';
  }

  // If capsule already exists, update in-place smoothly
  if (activeCapsuleEl && activeCapsuleEl.parentNode) {
    activeCapsuleEl.classList.remove('exiting');
    const iconContainer = activeCapsuleEl.querySelector('.toast-capsule-icon');
    const titleEl = activeCapsuleEl.querySelector('.toast-capsule-title');
    const textEl = activeCapsuleEl.querySelector('.toast-capsule-text');
    const actionSlot = activeCapsuleEl.querySelector('.toast-capsule-action-slot');

    if (iconContainer) iconContainer.innerHTML = iconHtml;
    if (titleEl) titleEl.textContent = title;
    if (textEl) {
      textEl.textContent = text;
      textEl.style.display = text ? 'block' : 'none';
    }
    if (actionSlot) {
      if (actionText && typeof onAction === 'function') {
        actionSlot.innerHTML = `<a class="toast-capsule-action" href="#">${escapeHtml(actionText)}</a>`;
        actionSlot.querySelector('a')?.addEventListener('click', (e) => {
          e.preventDefault();
          dismissActiveToast();
          onAction();
        });
      } else {
        actionSlot.innerHTML = '';
      }
    }

    // Set auto-dismiss timer
    activeCapsuleTimer = setTimeout(dismissActiveToast, autoDismissMs);
    return;
  }

  // Otherwise, create the single capsule element
  const capsule = document.createElement('div');
  capsule.className = 'toast-capsule entering';
  capsule.setAttribute('role', resolvedType === 'error' ? 'alert' : 'status');
  capsule.setAttribute('aria-live', 'polite');

  capsule.innerHTML = `
    <div class="toast-capsule-icon">${iconHtml}</div>
    <div class="toast-capsule-body">
      <div class="toast-capsule-title">${escapeHtml(title)}</div>
      <div class="toast-capsule-text" style="${text ? '' : 'display: none;'}">${escapeHtml(text)}</div>
      <div class="toast-capsule-action-slot">
        ${actionText && typeof onAction === 'function' ? `<a class="toast-capsule-action" href="#">${escapeHtml(actionText)}</a>` : ''}
      </div>
    </div>
    <button class="toast-capsule-close" type="button" aria-label="Dismiss notification">×</button>
  `;

  // Attach event handlers
  capsule.querySelector('.toast-capsule-close')?.addEventListener('click', dismissActiveToast);
  if (actionText && typeof onAction === 'function') {
    capsule.querySelector('.toast-capsule-action')?.addEventListener('click', (e) => {
      e.preventDefault();
      dismissActiveToast();
      onAction();
    });
  }

  container.appendChild(capsule);
  activeCapsuleEl = capsule;

  // Trigger enter transition
  requestAnimationFrame(() => {
    capsule.classList.remove('entering');
  });

  // Schedule auto-dismiss
  activeCapsuleTimer = setTimeout(dismissActiveToast, autoDismissMs);
}

function dismissActiveToast() {
  if (activeCapsuleTimer) {
    clearTimeout(activeCapsuleTimer);
    activeCapsuleTimer = null;
  }
  if (!activeCapsuleEl) return;

  const el = activeCapsuleEl;
  activeCapsuleEl = null;

  el.classList.add('exiting');
  setTimeout(() => {
    if (el.parentNode) el.parentNode.removeChild(el);
  }, 280);
}

