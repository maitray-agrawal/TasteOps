/**
 * TasteOps Immutable Audit & Decision Ledger Screen (/sessions/[sessionId]/ledger).
 *
 * Visualizes the immutable chronological record of every state transition,
 * provenance audit, Qloo resolution step, curator sign-off, and external dispatch.
 * Automatically appends live SSE events as they occur in real-time.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  formatDate,
  renderBadge,
  renderEmptyState,
  renderError,
  renderLoading,
  renderSubNav,
} from '../components/ui.js';

export async function renderSessionLedger(rootElement, params, router) {
  const sessionId = params.sessionId;
  if (!sessionId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="ledger-screen-container">
      ${renderLoading('Retrieving immutable audit event ledger...')}
    </div>
  `;

  const container = document.getElementById('ledger-screen-container');
  let streamSubscription = null;

  const loadData = async () => {
    try {
      const eventsData = await apiClient.getSessionEvents(sessionId);
      const auditEvents = eventsData.events || [];

      container.innerHTML = `
        <div class="fade-in">
          <header class="page-header" style="margin-bottom: 1.5rem;">
            <div class="page-title-group">
              <div class="page-breadcrumbs">
                <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                <span class="breadcrumb-separator">/</span>
                <a href="/sessions/${escapeHtml(sessionId)}" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}');">Session</a>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-primary);">Audit Ledger</span>
              </div>
              <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem;">
                <span>Audit & Decision Ledger</span>
                <span class="hash-pill" style="font-size: 0.85rem;">${auditEvents.length} Immutable Records</span>
              </h1>
              <p class="page-subtitle">
                Cryptographically bound append-only ledger tracking all autonomous agent decisions, curator authorizations, and external dispatches.
              </p>
            </div>
          </header>

          <!-- Sub-navigation Tabs -->
          ${renderSubNav(sessionId, 'ledger')}

          <!-- Real-Time SSE Stream Monitor -->
          <div class="stream-monitor-bar">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span class="stream-status-pill">
                <span class="stream-dot" id="sse-ledger-dot"></span>
                <span id="sse-ledger-label">Live Event Stream Connected</span>
              </span>
              <span style="color: var(--text-muted);">|</span>
              <span style="font-size: 0.8rem; color: var(--text-secondary);">
                Incoming transitions will automatically append to the ledger below.
              </span>
            </div>
            <span class="hash-pill" id="sse-ledger-last-id">stream-synced</span>
          </div>

          <!-- Events Timeline -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">
                <span>📜</span> Chronological Event History
              </div>
            </div>

            ${auditEvents.length > 0 ? `
              <div id="ledger-events-list" style="display: flex; flex-direction: column; gap: 1rem;">
                ${auditEvents.map(ev => renderEventRow(ev)).join('')}
              </div>
            ` : `
              ${renderEmptyState({
                icon: '📜',
                title: 'No Audit Events Recorded',
                description: 'State transitions will be recorded as the workflow pipeline advances.',
              })}
            `}
          </div>
        </div>
      `;

      // Live SSE Stream: Dynamically append new incoming events
      streamSubscription = apiClient.subscribeSessionStream(sessionId, {
        onEvent(incomingEvent) {
          const list = document.getElementById('ledger-events-list');
          const lastIdPill = document.getElementById('sse-ledger-last-id');

          if (lastIdPill) {
            lastIdPill.textContent = incomingEvent.event_id;
          }

          if (list) {
            // Check if event already in list by event_id
            if (!list.querySelector(`[data-event-id="${incomingEvent.event_id}"]`)) {
              const auditPayload = {
                event_id: incomingEvent.event_id,
                from_state: incomingEvent.data?.from_state || 'ACTIVE',
                to_state: incomingEvent.data?.to_state || incomingEvent.event_type,
                reason: incomingEvent.data?.summary || incomingEvent.event_type,
                timestamp: incomingEvent.timestamp,
                metadata: incomingEvent.data,
                error: incomingEvent.data?.error || null,
              };

              const newRowHtml = renderEventRow(auditPayload, true);
              list.insertAdjacentHTML('afterbegin', newRowHtml);
            }
          }
        },
        onError(err) {
          const label = document.getElementById('sse-ledger-label');
          const dot = document.getElementById('sse-ledger-dot');
          if (label && dot) {
            label.textContent = 'Stream Idle / Terminal';
            dot.style.background = '#94a3b8';
            dot.style.boxShadow = 'none';
          }
        },
      });

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Failed to Load Decision Ledger',
        error: err,
        retryId: 'btn-retry-ledger',
      });
      document.getElementById('btn-retry-ledger')?.addEventListener('click', loadData);
    }
  };

  loadData();
}

function renderEventRow(ev, isNew = false) {
  const meta = ev.metadata || {};
  const hasMeta = Object.keys(meta).length > 0;

  return `
    <div 
      class="card ${isNew ? 'fade-in' : ''}" 
      data-event-id="${escapeHtml(ev.event_id)}" 
      style="padding: 1.25rem; background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); ${isNew ? 'border-color: var(--cyan);' : ''}"
    >
      <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.5rem;">
        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <span class="hash-pill" style="font-size: 0.75rem; color: var(--cyan);">${escapeHtml(ev.event_id)}</span>
          <span style="color: var(--text-muted); font-size: 0.85rem;">→</span>
          ${renderBadge(ev.to_state)}
          ${ev.from_state ? `
            <span style="font-size: 0.75rem; color: var(--text-muted);">(from ${escapeHtml(ev.from_state)})</span>
          ` : ''}
        </div>

        <span style="font-family: var(--font-mono); font-size: 0.775rem; color: var(--text-muted);">
          ${formatDate(ev.timestamp)}
        </span>
      </div>

      <div style="font-size: 0.95rem; color: var(--text-primary); margin-bottom: 0.5rem; line-height: 1.4;">
        ${escapeHtml(ev.reason || 'Workflow state transition recorded.')}
      </div>

      ${ev.error ? `
        <div style="background: rgba(244, 63, 94, 0.1); border-left: 3px solid var(--rose); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); color: #fda4af; font-size: 0.85rem; margin-bottom: 0.5rem;">
          ${escapeHtml(ev.error)}
        </div>
      ` : ''}

      ${hasMeta ? `
        <details style="margin-top: 0.5rem;">
          <summary style="font-size: 0.775rem; color: var(--text-muted); cursor: pointer; user-select: none;">
            View Structured Metadata (${Object.keys(meta).length} keys)
          </summary>
          <pre style="background: rgba(0, 0, 0, 0.4); padding: 0.75rem; border-radius: var(--radius-sm); font-size: 0.75rem; font-family: var(--font-mono); color: var(--cyan); margin-top: 0.5rem; overflow-x: auto;">
${escapeHtml(JSON.stringify(meta, null, 2))}
          </pre>
        </details>
      ` : ''}
    </div>
  `;
}
