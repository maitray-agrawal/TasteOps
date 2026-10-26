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
  const steps = [
    { key: 'CREATED', label: 'Created' },
    { key: 'INTENT_PARSED', label: 'Intent' },
    { key: 'CULTURAL_TWIN_CREATED', label: 'Twin' },
    { key: 'QLOO_RESOLVED', label: 'Qloo' },
    { key: 'CULTURAL_MATRIX_READY', label: 'Matrix' },
    { key: 'AGENTS_RUNNING', label: 'Agents' },
    { key: 'PLAN_GENERATED', label: 'Plan' },
    { key: 'VALIDATED', label: 'Governance' },
    { key: 'AWAITING_APPROVAL', label: 'Gate' },
    { key: 'APPROVED', label: 'Approved' },
    { key: 'EXECUTING', label: 'Execution' },
    { key: 'COMPLETED', label: 'Complete' },
  ];

  const stepKeys = steps.map(st => st.key);
  const currentIndex = stepKeys.indexOf(s);
  const isFailed = s === 'FAILED';

  return `
    <div class="workflow-stepper">
      ${steps.map((st, idx) => {
        let nodeClass = '';
        if (isFailed) {
          nodeClass = idx === 0 ? 'completed' : '';
        } else if (idx < currentIndex) {
          nodeClass = 'completed';
        } else if (idx === currentIndex) {
          nodeClass = 'active';
        }

        const isConnectorCompleted = !isFailed && idx < currentIndex;

        return `
          <div class="stepper-node ${nodeClass}">
            <div class="stepper-circle">
              ${idx < currentIndex ? '✓' : idx + 1}
            </div>
            <div class="stepper-label">${st.label}</div>
          </div>
          ${idx < steps.length - 1 ? `
            <div class="stepper-connector ${isConnectorCompleted ? 'completed' : ''}"></div>
          ` : ''}
        `;
      }).join('')}
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
  const tabs = [
    { key: 'overview', label: 'Overview & Twin', path: `/sessions/${sessionId}` },
    { key: 'activity', label: 'Agent Activity', path: `/sessions/${sessionId}/activity` },
    { key: 'blueprint', label: 'Architectural Blueprint', path: `/sessions/${sessionId}/blueprint` },
    { key: 'approval', label: 'Approval Gate', path: `/sessions/${sessionId}/approval` },
    { key: 'execution', label: 'Execution Engine', path: `/sessions/${sessionId}/execution` },
    { key: 'ledger', label: 'Audit Ledger', path: `/sessions/${sessionId}/ledger` },
  ];

  return `
    <nav class="tabs-nav">
      ${tabs.map(t => `
        <button 
          class="tab-btn ${activeTab === t.key ? 'active' : ''}" 
          onclick="window.tasteopsRouter.navigate('${t.path}')"
        >
          ${t.label}
        </button>
      `).join('')}
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

