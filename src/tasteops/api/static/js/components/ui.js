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
  } else if (s === 'EXECUTING') {
    badgeClass = 'badge-executing';
  } else if (s === 'COMPLETED') {
    badgeClass = 'badge-completed';
  } else if (s === 'FAILED') {
    badgeClass = 'badge-failed';
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

export function renderSubNav(sessionId, activeTab) {
  const tabs = [
    { key: 'overview', label: 'Overview & Twin', path: `/sessions/${sessionId}` },
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

export function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span style="font-size: 1.1rem;">
      ${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}
    </span>
    <span class="toast-message">${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 250);
  }, duration);
}
