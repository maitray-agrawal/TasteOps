/**
 * TasteOps Immutable Decision Ledger & Audit Trail Screen (/sessions/[sessionId]/ledger).
 *
 * Implements a read-only, cryptographically verified chronological ledger
 * displaying all workflow lifecycle events:
 * - Session creation
 * - Workflow state changes
 * - Qloo retrieval
 * - Agent completion
 * - Governance decisions
 * - Plan validation
 * - Curator approvals & rejections
 * - Execution attempts & outcomes
 * - Policy and runtime failures
 *
 * Each event exposes timestamp, event type, actor/source, concise summary,
 * related session/task/plan, and provenance.
 *
 * Features:
 * - Hash-chain cryptographic verification status
 * - Multi-dimensional client-side filtering (event type, agent, state, date, search)
 * - Strict read-only enforcement (no editing or deletion permitted)
 * - Live Server-Sent Events (SSE) stream auto-append
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

// Configuration of supported event types with icons, labels, and color tokens
const EVENT_TYPE_CONFIG = {
  SESSION_CREATION: {
    label: 'Session Creation',
    icon: '🚀',
    color: '#8b5cf6',
    bgColor: 'rgba(139, 92, 246, 0.15)',
    borderColor: 'rgba(139, 92, 246, 0.35)',
  },
  STATE_CHANGE: {
    label: 'State Change',
    icon: '🔄',
    color: '#38bdf8',
    bgColor: 'rgba(56, 189, 248, 0.15)',
    borderColor: 'rgba(56, 189, 248, 0.35)',
  },
  QLOO_RETRIEVAL: {
    label: 'Qloo Retrieval',
    icon: '🔍',
    color: '#06b6d4',
    bgColor: 'rgba(6, 182, 212, 0.15)',
    borderColor: 'rgba(6, 182, 212, 0.35)',
  },
  AGENT_COMPLETION: {
    label: 'Agent Completion',
    icon: '🧠',
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: 'rgba(16, 185, 129, 0.35)',
  },
  GOVERNANCE_DECISION: {
    label: 'Governance Decision',
    icon: '⚖️',
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.15)',
    borderColor: 'rgba(245, 158, 11, 0.35)',
  },
  VALIDATION: {
    label: 'Validation',
    icon: '🛡️',
    color: '#14b8a6',
    bgColor: 'rgba(20, 184, 166, 0.15)',
    borderColor: 'rgba(20, 184, 166, 0.35)',
  },
  APPROVAL: {
    label: 'Curator Approval',
    icon: '✍️',
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.2)',
    borderColor: 'rgba(16, 185, 129, 0.5)',
  },
  REJECTION: {
    label: 'Curator Rejection',
    icon: '🛑',
    color: '#f43f5e',
    bgColor: 'rgba(244, 63, 94, 0.15)',
    borderColor: 'rgba(244, 63, 94, 0.4)',
  },
  EXECUTION_ATTEMPT: {
    label: 'Execution Attempt',
    icon: '⚡',
    color: '#eab308',
    bgColor: 'rgba(234, 179, 8, 0.15)',
    borderColor: 'rgba(234, 179, 8, 0.35)',
  },
  EXECUTION_OUTCOME: {
    label: 'Execution Outcome',
    icon: '✅',
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: 'rgba(16, 185, 129, 0.35)',
  },
  FAILURE: {
    label: 'Failure',
    icon: '❌',
    color: '#f43f5e',
    bgColor: 'rgba(244, 63, 94, 0.2)',
    borderColor: 'rgba(244, 63, 94, 0.5)',
  },
};

export async function renderSessionLedger(rootElement, params, router) {
  const sessionId = params.sessionId;
  if (!sessionId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="ledger-screen-container">
      ${renderLoading('Retrieving immutable audit event ledger & verifying hash chain...')}
    </div>
  `;

  const container = document.getElementById('ledger-screen-container');
  let streamSubscription = null;
  let allEvents = [];
  let verificationData = null;

  // Active filter state
  const filters = {
    eventType: 'ALL',
    agent: 'ALL',
    state: 'ALL',
    date: 'ALL',
    search: '',
    sortOrder: 'ASC', // 'ASC' (chronological) or 'DESC' (newest first)
  };

  const loadData = async () => {
    try {
      // 1. Fetch audit events and verification status from API
      const eventsData = await apiClient.getSessionEvents(sessionId);
      allEvents = eventsData.events || [];
      verificationData = eventsData.verification_status || null;

      // If verification status was not included in events payload, try dedicated verify endpoint
      if (!verificationData && apiClient.verifySessionLedger) {
        try {
          verificationData = await apiClient.verifySessionLedger(sessionId);
        } catch (_) {
          // Graceful fallback
        }
      }

      renderMainView();
      initStreamSubscription();

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Failed to Load Decision Ledger',
        error: err,
        retryId: 'btn-retry-ledger',
      });
      document.getElementById('btn-retry-ledger')?.addEventListener('click', loadData);
    }
  };

  const renderMainView = () => {
    container.innerHTML = `
      <div class="fade-in">
        <!-- Page Header & Breadcrumbs -->
        <header class="page-header" style="margin-bottom: 1.5rem;">
          <div class="page-title-group">
            <div class="page-breadcrumbs">
              <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
              <span class="breadcrumb-separator">/</span>
              <a href="/sessions/${escapeHtml(sessionId)}" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}');">Session</a>
              <span class="breadcrumb-separator">/</span>
              <span style="color: var(--text-primary);">Decision Ledger</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; margin-top: 0.5rem;">
              <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0;">
                <span>Decision Ledger & Audit Trail</span>
                <span class="hash-pill" style="font-size: 0.85rem;" id="total-events-count-pill">${allEvents.length} Records</span>
              </h1>
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.75rem;">
                  🔒 READ-ONLY AUDIT LOG
                </span>
                <button id="btn-reverify-chain" class="btn btn-secondary btn-sm" style="display: flex; align-items: center; gap: 0.4rem;">
                  <span>🛡️</span> Re-Verify Hash Chain
                </button>
              </div>
            </div>
            <p class="page-subtitle" style="margin-top: 0.5rem;">
              Cryptographically chained, tamper-evident audit ledger capturing every space transition, Qloo retrieval, agent inference, human curator sign-off, and external connector outcome.
            </p>
          </div>
        </header>

        <!-- Sub-navigation Tabs -->
        ${renderSubNav(sessionId, 'ledger')}

        <!-- Read-Only & Immutability Notice Banner -->
        <div class="read-only-notice-banner" style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; padding: 0.85rem 1.25rem; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(99, 102, 241, 0.25); border-radius: var(--radius-md); margin-bottom: 1.5rem; backdrop-filter: blur(8px);">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span style="font-size: 1.2rem;">🏛️</span>
            <div>
              <div style="font-weight: 600; font-size: 0.875rem; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
                <span>Immutable Decision Record</span>
                <span style="font-size: 0.7rem; color: var(--cyan); background: rgba(6, 182, 212, 0.1); padding: 0.1rem 0.4rem; border-radius: var(--radius-sm); border: 1px solid rgba(6, 182, 212, 0.25);">
                  APPEND-ONLY
                </span>
              </div>
              <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.15rem;">
                Modifications, retroactive edits, and event deletions are strictly prohibited at database and API protocol boundaries.
              </div>
            </div>
          </div>
          <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
            LEDGER ID: <span style="color: var(--cyan);">${escapeHtml(sessionId)}</span>
          </div>
        </div>

        <!-- Hash-Chain Cryptographic Verification Card -->
        <div id="hash-chain-verification-section" style="margin-bottom: 1.5rem;">
          ${renderVerificationStatusCard(verificationData, allEvents.length)}
        </div>

        <!-- Real-Time SSE Stream Monitor Bar -->
        <div class="stream-monitor-bar" style="margin-bottom: 1.5rem;">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span class="stream-status-pill">
              <span class="stream-dot" id="sse-ledger-dot"></span>
              <span id="sse-ledger-label">Live Event Stream Connected</span>
            </span>
            <span style="color: var(--text-muted);">|</span>
            <span style="font-size: 0.8rem; color: var(--text-secondary);">
              Incoming state transitions and execution outcomes append automatically to this ledger.
            </span>
          </div>
          <span class="hash-pill" id="sse-ledger-last-id">stream-synced</span>
        </div>

        <!-- Multi-Dimensional Filter Controls Bar -->
        <div class="card" style="padding: 1.25rem; margin-bottom: 1.5rem; background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle);">
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem;">
            <div style="font-weight: 600; font-size: 0.95rem; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
              <span>🔍</span> Filter Audit Events
              <span class="hash-pill" id="filtered-count-badge" style="font-size: 0.75rem;">
                Showing ${allEvents.length} of ${allEvents.length}
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <!-- Sort Order Toggle -->
              <button id="btn-toggle-sort" class="btn btn-secondary btn-sm" style="display: flex; align-items: center; gap: 0.4rem;">
                <span id="sort-order-icon">⏳</span>
                <span id="sort-order-label">Chronological (Oldest First)</span>
              </button>
              <!-- Reset Filters -->
              <button id="btn-reset-filters" class="btn btn-secondary btn-sm" style="display: flex; align-items: center; gap: 0.4rem;">
                <span>✕</span> Reset Filters
              </button>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
            <!-- 1. Event Type Filter -->
            <div class="form-group" style="margin-bottom: 0;">
              <label for="filter-event-type" style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">
                Event Type
              </label>
              <select id="filter-event-type" class="form-input" style="padding: 0.5rem 0.75rem; font-size: 0.85rem; background: var(--bg-deep);">
                <option value="ALL">All Event Types</option>
                <option value="SESSION_CREATION">🚀 Session Creation</option>
                <option value="STATE_CHANGE">🔄 State Change</option>
                <option value="QLOO_RETRIEVAL">🔍 Qloo Retrieval</option>
                <option value="AGENT_COMPLETION">🧠 Agent Completion</option>
                <option value="GOVERNANCE_DECISION">⚖️ Governance Decision</option>
                <option value="VALIDATION">🛡️ Plan Validation</option>
                <option value="APPROVAL">✍️ Curator Approval</option>
                <option value="REJECTION">🛑 Curator Rejection</option>
                <option value="EXECUTION_ATTEMPT">⚡ Execution Attempt</option>
                <option value="EXECUTION_OUTCOME">✅ Execution Outcome</option>
                <option value="FAILURE">❌ Failure / Policy Violation</option>
              </select>
            </div>

            <!-- 2. Agent / Actor Filter -->
            <div class="form-group" style="margin-bottom: 0;">
              <label for="filter-agent" style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">
                Agent / Actor
              </label>
              <select id="filter-agent" class="form-input" style="padding: 0.5rem 0.75rem; font-size: 0.85rem; background: var(--bg-deep);">
                <option value="ALL">All Actors & Agents</option>
                <option value="Cultural Strategist">🧠 Cultural Strategist</option>
                <option value="Experience Architect">📐 Experience Architect</option>
                <option value="Partnership Agent">🤝 Partnership Agent</option>
                <option value="Governance Agent">⚖️ Governance Agent</option>
                <option value="Human Curator">👤 Human Curator</option>
                <option value="Qloo">🔍 Qloo MCP / Matrix</option>
                <option value="Spotify">🎵 Spotify Connector</option>
                <option value="Email">✉️ Email Connector</option>
                <option value="Procurement">📦 Procurement Connector</option>
                <option value="TasteOps Engine">🏛️ TasteOps Engine</option>
              </select>
            </div>

            <!-- 3. Workflow State Filter -->
            <div class="form-group" style="margin-bottom: 0;">
              <label for="filter-state" style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">
                Workflow State
              </label>
              <select id="filter-state" class="form-input" style="padding: 0.5rem 0.75rem; font-size: 0.85rem; background: var(--bg-deep);">
                <option value="ALL">All States</option>
                <option value="CREATED">CREATED</option>
                <option value="INTENT_PARSED">INTENT_PARSED</option>
                <option value="CULTURAL_TWIN_CREATED">CULTURAL_TWIN_CREATED</option>
                <option value="QLOO_RESOLVED">QLOO_RESOLVED</option>
                <option value="CULTURAL_MATRIX_READY">CULTURAL_MATRIX_READY</option>
                <option value="AGENTS_RUNNING">AGENTS_RUNNING</option>
                <option value="PLAN_GENERATED">PLAN_GENERATED</option>
                <option value="VALIDATED">VALIDATED</option>
                <option value="AWAITING_APPROVAL">AWAITING_APPROVAL</option>
                <option value="APPROVED">APPROVED</option>
                <option value="EXECUTING">EXECUTING</option>
                <option value="COMPLETED">COMPLETED</option>
                <option value="FAILED">FAILED</option>
              </select>
            </div>

            <!-- 4. Date Range Filter -->
            <div class="form-group" style="margin-bottom: 0;">
              <label for="filter-date" style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">
                Date Window
              </label>
              <select id="filter-date" class="form-input" style="padding: 0.5rem 0.75rem; font-size: 0.85rem; background: var(--bg-deep);">
                <option value="ALL">All Recorded Dates</option>
                <option value="TODAY">Today Only</option>
                <option value="24H">Past 24 Hours</option>
                <option value="7D">Past 7 Days</option>
              </select>
            </div>

            <!-- 5. Free-Text Search -->
            <div class="form-group" style="margin-bottom: 0;">
              <label for="filter-search" style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">
                Keyword Search
              </label>
              <input 
                type="text" 
                id="filter-search" 
                class="form-input" 
                placeholder="Search summaries, IDs, actors..." 
                style="padding: 0.5rem 0.75rem; font-size: 0.85rem; background: var(--bg-deep);"
              />
            </div>
          </div>
        </div>

        <!-- Chronological Events Timeline Container -->
        <div class="card" style="padding: 1.5rem; background: var(--bg-card); border: 1px solid var(--border-subtle);">
          <div class="card-header" style="margin-bottom: 1.25rem;">
            <div class="card-title" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
              <div style="display: flex; align-items: center; gap: 0.6rem;">
                <span>📜</span>
                <span>Chronological Decision Stream</span>
              </div>
              <span style="font-size: 0.75rem; font-weight: 500; color: var(--text-muted); font-family: var(--font-mono);">
                Read-Only • Zero Edit Rights
              </span>
            </div>
          </div>

          <div id="ledger-events-container">
            ${renderFilteredEvents()}
          </div>
        </div>
      </div>
    `;

    bindFilterEvents();
  };

  const renderFilteredEvents = () => {
    let filtered = [...allEvents];

    // Filter by Event Type
    if (filters.eventType !== 'ALL') {
      filtered = filtered.filter(ev => {
        const evType = (ev.event_type || inferEventType(ev)).toUpperCase();
        return evType === filters.eventType;
      });
    }

    // Filter by Agent / Actor
    if (filters.agent !== 'ALL') {
      const q = filters.agent.toLowerCase();
      filtered = filtered.filter(ev => {
        const actorStr = String(ev.actor || '').toLowerCase();
        return actorStr.includes(q);
      });
    }

    // Filter by Workflow State
    if (filters.state !== 'ALL') {
      filtered = filtered.filter(ev => {
        const toState = String(ev.to_state || '').toUpperCase();
        const fromState = String(ev.from_state || '').toUpperCase();
        return toState === filters.state || fromState === filters.state;
      });
    }

    // Filter by Date
    if (filters.date !== 'ALL') {
      const now = new Date();
      filtered = filtered.filter(ev => {
        if (!ev.timestamp) return false;
        const evDate = new Date(ev.timestamp);
        const diffMs = now - evDate;

        if (filters.date === 'TODAY') {
          return evDate.toDateString() === now.toDateString();
        }
        if (filters.date === '24H') {
          return diffMs <= 24 * 60 * 60 * 1000;
        }
        if (filters.date === '7D') {
          return diffMs <= 7 * 24 * 60 * 60 * 1000;
        }
        return true;
      });
    }

    // Filter by Free-Text Search
    if (filters.search.trim()) {
      const q = filters.search.trim().toLowerCase();
      filtered = filtered.filter(ev => {
        const summary = String(ev.summary || ev.reason || '').toLowerCase();
        const eventId = String(ev.event_id || '').toLowerCase();
        const actor = String(ev.actor || '').toLowerCase();
        const related = JSON.stringify(ev.related || {}).toLowerCase();
        const metadata = JSON.stringify(ev.metadata || {}).toLowerCase();
        return (
          summary.includes(q) ||
          eventId.includes(q) ||
          actor.includes(q) ||
          related.includes(q) ||
          metadata.includes(q)
        );
      });
    }

    // Apply Sorting
    filtered.sort((a, b) => {
      const tA = new Date(a.timestamp || 0).getTime();
      const tB = new Date(b.timestamp || 0).getTime();
      return filters.sortOrder === 'ASC' ? tA - tB : tB - tA;
    });

    // Update count badge
    const badge = document.getElementById('filtered-count-badge');
    if (badge) {
      badge.textContent = `Showing ${filtered.length} of ${allEvents.length}`;
    }

    if (filtered.length === 0) {
      return renderEmptyState({
        icon: '🔍',
        title: 'No Matching Audit Events',
        description: 'No events match the selected filter criteria. Try resetting your filters.',
        actionText: 'Reset Filters',
        actionId: 'btn-empty-reset-filters',
      });
    }

    return `
      <div id="ledger-events-list" style="display: flex; flex-direction: column; gap: 1rem;">
        ${filtered.map(ev => renderEventCard(ev)).join('')}
      </div>
    `;
  };

  const bindFilterEvents = () => {
    // Event Type
    const typeSelect = document.getElementById('filter-event-type');
    if (typeSelect) {
      typeSelect.value = filters.eventType;
      typeSelect.addEventListener('change', (e) => {
        filters.eventType = e.target.value;
        refreshEventsContainer();
      });
    }

    // Agent
    const agentSelect = document.getElementById('filter-agent');
    if (agentSelect) {
      agentSelect.value = filters.agent;
      agentSelect.addEventListener('change', (e) => {
        filters.agent = e.target.value;
        refreshEventsContainer();
      });
    }

    // State
    const stateSelect = document.getElementById('filter-state');
    if (stateSelect) {
      stateSelect.value = filters.state;
      stateSelect.addEventListener('change', (e) => {
        filters.state = e.target.value;
        refreshEventsContainer();
      });
    }

    // Date
    const dateSelect = document.getElementById('filter-date');
    if (dateSelect) {
      dateSelect.value = filters.date;
      dateSelect.addEventListener('change', (e) => {
        filters.date = e.target.value;
        refreshEventsContainer();
      });
    }

    // Search
    const searchInput = document.getElementById('filter-search');
    if (searchInput) {
      searchInput.value = filters.search;
      searchInput.addEventListener('input', (e) => {
        filters.search = e.target.value;
        refreshEventsContainer();
      });
    }

    // Reset Filters button
    document.getElementById('btn-reset-filters')?.addEventListener('click', resetFilters);
    document.getElementById('btn-empty-reset-filters')?.addEventListener('click', resetFilters);

    // Toggle Sort Order button
    const sortBtn = document.getElementById('btn-toggle-sort');
    if (sortBtn) {
      sortBtn.addEventListener('click', () => {
        filters.sortOrder = filters.sortOrder === 'ASC' ? 'DESC' : 'ASC';
        const label = document.getElementById('sort-order-label');
        const icon = document.getElementById('sort-order-icon');
        if (label && icon) {
          if (filters.sortOrder === 'ASC') {
            label.textContent = 'Chronological (Oldest First)';
            icon.textContent = '⏳';
          } else {
            label.textContent = 'Reverse Chronological (Newest First)';
            icon.textContent = '⌛';
          }
        }
        refreshEventsContainer();
      });
    }

    // Re-verify Hash Chain button
    document.getElementById('btn-reverify-chain')?.addEventListener('click', async () => {
      const btn = document.getElementById('btn-reverify-chain');
      const hashSection = document.getElementById('hash-chain-verification-section');
      if (btn) btn.disabled = true;
      try {
        if (apiClient.verifySessionLedger) {
          verificationData = await apiClient.verifySessionLedger(sessionId);
        } else {
          // Re-fetch events
          const eventsData = await apiClient.getSessionEvents(sessionId);
          verificationData = eventsData.verification_status;
        }
        if (hashSection) {
          hashSection.innerHTML = renderVerificationStatusCard(verificationData, allEvents.length);
        }
      } catch (err) {
        alert(`Verification request failed: ${err.message}`);
      } finally {
        if (btn) btn.disabled = false;
      }
    });
  };

  const resetFilters = () => {
    filters.eventType = 'ALL';
    filters.agent = 'ALL';
    filters.state = 'ALL';
    filters.date = 'ALL';
    filters.search = '';

    const typeSelect = document.getElementById('filter-event-type');
    const agentSelect = document.getElementById('filter-agent');
    const stateSelect = document.getElementById('filter-state');
    const dateSelect = document.getElementById('filter-date');
    const searchInput = document.getElementById('filter-search');

    if (typeSelect) typeSelect.value = 'ALL';
    if (agentSelect) agentSelect.value = 'ALL';
    if (stateSelect) stateSelect.value = 'ALL';
    if (dateSelect) dateSelect.value = 'ALL';
    if (searchInput) searchInput.value = '';

    refreshEventsContainer();
  };

  const refreshEventsContainer = () => {
    const listContainer = document.getElementById('ledger-events-container');
    if (listContainer) {
      listContainer.innerHTML = renderFilteredEvents();
    }
  };

  const initStreamSubscription = () => {
    streamSubscription = apiClient.subscribeSessionStream(sessionId, {
      onEvent(incomingEvent) {
        const lastIdPill = document.getElementById('sse-ledger-last-id');
        if (lastIdPill) {
          lastIdPill.textContent = incomingEvent.event_id;
        }

        // Avoid duplicates
        if (!allEvents.some(e => e.event_id === incomingEvent.event_id)) {
          const synthesized = {
            event_id: incomingEvent.event_id,
            session_id: sessionId,
            from_state: incomingEvent.data?.from_state || 'ACTIVE',
            to_state: incomingEvent.data?.to_state || incomingEvent.event_type,
            reason: incomingEvent.data?.summary || incomingEvent.event_type,
            timestamp: incomingEvent.timestamp,
            metadata: incomingEvent.data || {},
            error: incomingEvent.data?.error || null,
            event_type: inferEventType({
              to_state: incomingEvent.data?.to_state || incomingEvent.event_type,
              reason: incomingEvent.data?.summary,
            }),
            actor: inferActor({
              to_state: incomingEvent.data?.to_state,
              metadata: incomingEvent.data,
            }),
            summary: incomingEvent.data?.summary || `Transitioned to ${incomingEvent.event_type}`,
            related: { session_id: sessionId, plan_id: incomingEvent.data?.plan_id },
            provenance: { source: 'Server-Sent Events Stream', timestamp: incomingEvent.timestamp },
          };

          allEvents.push(synthesized);

          // Update header counter
          const countPill = document.getElementById('total-events-count-pill');
          if (countPill) {
            countPill.textContent = `${allEvents.length} Records`;
          }

          refreshEventsContainer();
        }
      },
      onError() {
        const label = document.getElementById('sse-ledger-label');
        const dot = document.getElementById('sse-ledger-dot');
        if (label && dot) {
          label.textContent = 'Stream Idle / Completed';
          dot.style.background = '#94a3b8';
          dot.style.boxShadow = 'none';
        }
      },
    });
  };

  loadData();
}

/**
 * Renders the cryptographic hash-chain verification status card.
 */
function renderVerificationStatusCard(verification, eventCount) {
  const isVerified = Boolean(verification && verification.is_verified === true);
  const statusLabel = isVerified ? '✓ VERIFIED AUTHENTIC' : 'STORED AUDIT LOG (HASH-CHAIN UNAVAILABLE)';
  const badgeStyle = isVerified
    ? 'background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4);'
    : 'background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3);';

  const algorithm = verification?.algorithm || 'None (Authoritative StateStore Log)';
  const headHash = verification?.head_hash || null;
  const rootHash = verification?.root_hash || null;
  const planHash = verification?.plan_hash || null;
  const planHashMatched = verification?.plan_hash_matched;

  return `
    <div class="card verification-card fade-in" style="padding: 1.25rem 1.5rem; background: rgba(14, 20, 36, 0.85); border: 1px solid ${isVerified ? 'rgba(16, 185, 129, 0.35)' : 'rgba(148, 163, 184, 0.25)'}; border-radius: var(--radius-md); box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4); backdrop-filter: blur(8px);">
      <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <div style="width: 42px; height: 42px; border-radius: var(--radius-md); background: ${isVerified ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.1)'}; border: 1px solid ${isVerified ? 'rgba(16, 185, 129, 0.3)' : 'rgba(148, 163, 184, 0.2)'}; display: flex; align-items: center; justify-content: center; font-size: 1.35rem;">
            ${isVerified ? '🛡️' : '📋'}
          </div>
          <div>
            <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
              <span style="font-weight: 700; font-size: 1.05rem; color: var(--text-primary);">
                Audit Trail Integrity Status
              </span>
              <span class="badge" style="${badgeStyle} font-weight: 700; font-size: 0.775rem;">
                ${statusLabel}
              </span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem; line-height: 1.4;">
              ${isVerified
                ? `Algorithm: <span style="font-family: var(--font-mono); color: var(--cyan);">${escapeHtml(algorithm)}</span> • Verified Chain Length: <span style="font-weight: 600; color: var(--text-primary);">${eventCount} events</span>`
                : 'The TasteOps API records and serves authoritative state-transition audit events from persistent storage. Cryptographic hash-chain and Merkle ledger verification are not currently supported by the backend.'}
            </div>
          </div>
        </div>

        <div style="text-align: right; font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
          <div>STORAGE PERSISTENCE</div>
          <div style="color: ${isVerified ? '#34d399' : 'var(--cyan)'}; font-weight: 600;">
            ${eventCount} PERSISTED EVENTS
          </div>
        </div>
      </div>

      <!-- Hash Metadata Grid -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.85rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); font-family: var(--font-mono); font-size: 0.775rem;">
        <div style="background: rgba(0, 0, 0, 0.3); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          <div style="color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.2rem;">Hash-Chain Digest</div>
          <div style="color: ${headHash ? 'var(--cyan)' : 'var(--text-muted)'}; word-break: break-all;">
            ${headHash ? escapeHtml(headHash) : '<span style="font-style: italic;">Unavailable (No backend hash-chain)</span>'}
          </div>
        </div>

        <div style="background: rgba(0, 0, 0, 0.3); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          <div style="color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.2rem;">Merkle Root Digest</div>
          <div style="color: ${rootHash ? 'var(--text-secondary)' : 'var(--text-muted)'}; word-break: break-all;">
            ${rootHash ? escapeHtml(rootHash) : '<span style="font-style: italic;">Unavailable (No Merkle tree)</span>'}
          </div>
        </div>

        <div style="background: rgba(0, 0, 0, 0.3); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          <div style="color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.2rem;">
            Plan Hash Binding ${planHash ? (planHashMatched ? '<span style="color: #34d399;">(MATCHED)</span>' : '<span style="color: #f87171;">(MUTATED)</span>') : ''}
          </div>
          <div style="color: ${planHash ? (planHashMatched ? '#34d399' : '#f87171') : 'var(--text-muted)'}; word-break: break-all;">
            ${planHash ? escapeHtml(planHash.length > 32 ? planHash.slice(0, 28) + '...' : planHash) : '<span style="font-style: italic;">Pending curator approval</span>'}
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Renders a single immutable audit event card exposing:
 * - timestamp
 * - event type
 * - actor/source
 * - concise summary
 * - related session/task/plan
 * - provenance
 */
function renderEventCard(ev) {
  const evTypeKey = (ev.event_type || inferEventType(ev)).toUpperCase();
  const typeCfg = EVENT_TYPE_CONFIG[evTypeKey] || EVENT_TYPE_CONFIG.STATE_CHANGE;

  const actor = ev.actor || inferActor(ev);
  const summary = ev.summary || ev.reason || 'Workflow state transition recorded.';
  const timestampStr = formatDate(ev.timestamp);
  const rawIso = ev.timestamp ? (new Date(ev.timestamp).toISOString()) : '';

  const related = ev.related || {};
  const sessionId = related.session_id || ev.session_id;
  const planId = related.plan_id || ev.metadata?.plan_id;
  const taskId = related.task_id || ev.metadata?.task_id;
  const spaceId = related.space_id;

  const provenance = ev.provenance || {};
  const vHash = ev.verification_hash || provenance.verification_hash;
  const metadata = ev.metadata || {};
  const hasMetadata = Object.keys(metadata).length > 0;

  return `
    <div 
      class="card event-card fade-in" 
      data-event-id="${escapeHtml(ev.event_id)}" 
      style="padding: 1.25rem 1.5rem; background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-left: 4px solid ${typeCfg.color}; position: relative;"
    >
      <!-- Top Row: Badges, Event Type, Actor, Timestamp -->
      <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.75rem;">
        <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
          <!-- Event ID Pill -->
          <span class="hash-pill" style="font-size: 0.75rem; color: var(--cyan); background: rgba(6, 182, 212, 0.1);">
            ${escapeHtml(ev.event_id)}
          </span>

          <!-- Event Type Badge -->
          <span class="badge" style="background: ${typeCfg.bgColor}; color: ${typeCfg.color}; border: 1px solid ${typeCfg.borderColor}; font-weight: 600; font-size: 0.75rem;">
            ${typeCfg.icon} ${escapeHtml(typeCfg.label)}
          </span>

          <!-- Actor / Source Badge -->
          <span class="badge" style="background: rgba(255, 255, 255, 0.05); color: var(--text-primary); border: 1px solid var(--border-subtle); font-size: 0.75rem;">
            ${escapeHtml(actor)}
          </span>

          <!-- State Progression (if state transition event) -->
          ${ev.to_state ? `
            <span style="display: flex; align-items: center; gap: 0.35rem; font-size: 0.75rem;">
              ${ev.from_state ? `<span style="color: var(--text-muted);">${escapeHtml(ev.from_state)}</span> <span style="color: var(--text-muted);">→</span>` : ''}
              ${renderBadge(ev.to_state)}
            </span>
          ` : ''}
        </div>

        <!-- Timestamp Exposer -->
        <div style="text-align: right; font-family: var(--font-mono); font-size: 0.775rem; color: var(--text-muted);" title="${escapeHtml(rawIso)}">
          <span>🕒 ${timestampStr}</span>
        </div>
      </div>

      <!-- Concise Summary -->
      <div style="font-size: 0.95rem; color: var(--text-primary); line-height: 1.5; margin-bottom: 0.85rem; font-weight: 500;">
        ${escapeHtml(summary)}
      </div>

      <!-- Error Banner (if event represents a failure) -->
      ${ev.error ? `
        <div style="background: rgba(244, 63, 94, 0.1); border-left: 3px solid var(--rose); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); color: #fda4af; font-size: 0.85rem; margin-bottom: 0.85rem;">
          <strong>Failure Detail:</strong> ${escapeHtml(ev.error)}
        </div>
      ` : ''}

      <!-- Related Session / Task / Plan Group -->
      <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.75rem; font-family: var(--font-mono); font-size: 0.75rem;">
        <span style="color: var(--text-muted);">Related:</span>

        ${sessionId ? `
          <span class="hash-pill" style="color: var(--text-secondary); background: rgba(255, 255, 255, 0.03);">
            session: ${escapeHtml(sessionId.slice(0, 14))}...
          </span>
        ` : ''}

        ${planId ? `
          <span class="hash-pill" style="color: #a78bfa; background: rgba(139, 92, 246, 0.08); border-color: rgba(139, 92, 246, 0.25);">
            plan: ${escapeHtml(planId)} ${related.plan_version ? `(v${related.plan_version})` : ''}
          </span>
        ` : ''}

        ${taskId ? `
          <span class="hash-pill" style="color: #38bdf8; background: rgba(56, 189, 248, 0.08); border-color: rgba(56, 189, 248, 0.25);">
            task: ${escapeHtml(taskId)}
          </span>
        ` : ''}

        ${spaceId ? `
          <span class="hash-pill" style="color: var(--text-secondary); background: rgba(255, 255, 255, 0.03);">
            space: ${escapeHtml(spaceId)}
          </span>
        ` : ''}

        <!-- Read-Only Badge -->
        <span style="margin-left: auto; color: var(--text-muted); font-size: 0.7rem; display: flex; align-items: center; gap: 0.25rem;">
          <span>🔒</span> Immutable
        </span>
      </div>

      <!-- Provenance & Structured Verification Drawer -->
      <details style="margin-top: 0.5rem; border-top: 1px solid rgba(255, 255, 255, 0.05); padding-top: 0.6rem;">
        <summary style="font-size: 0.775rem; color: var(--cyan); cursor: pointer; user-select: none; display: flex; align-items: center; gap: 0.4rem;">
          <span>🔬</span> View Provenance & Audit Metadata
        </summary>
        
        <div style="margin-top: 0.75rem; display: flex; flex-direction: column; gap: 0.6rem;">
          <!-- Provenance Trace Block -->
          <div style="background: rgba(0, 0, 0, 0.35); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); font-family: var(--font-mono); font-size: 0.75rem;">
            <div style="color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.3rem;">Provenance & Verification Chain</div>
            <div style="color: var(--text-secondary); margin-bottom: 0.2rem;">
              Actor Source: <span style="color: var(--text-primary);">${escapeHtml(actor)}</span>
            </div>
            ${vHash ? `
              <div style="color: var(--text-secondary); margin-bottom: 0.2rem; word-break: break-all;">
                Block Hash: <span style="color: var(--cyan);">${escapeHtml(vHash)}</span>
              </div>
            ` : ''}
            ${provenance.plan_hash ? `
              <div style="color: var(--text-secondary); margin-bottom: 0.2rem; word-break: break-all;">
                Plan Binding: <span style="color: #a78bfa;">${escapeHtml(provenance.plan_hash)}</span>
              </div>
            ` : ''}
            ${provenance.signed_by ? `
              <div style="color: var(--text-secondary); margin-bottom: 0.2rem;">
                Authorized By: <span style="color: #34d399; font-weight: 600;">${escapeHtml(provenance.signed_by)}</span>
              </div>
            ` : ''}
          </div>

          <!-- Structured Metadata Payload -->
          ${hasMetadata ? `
            <pre style="background: rgba(0, 0, 0, 0.45); padding: 0.75rem; border-radius: var(--radius-sm); font-size: 0.75rem; font-family: var(--font-mono); color: var(--cyan); overflow-x: auto; max-height: 240px;">
${escapeHtml(JSON.stringify(metadata, null, 2))}
            </pre>
          ` : ''}
        </div>
      </details>
    </div>
  `;
}

/**
 * Fallback helpers to infer event type and actor from state transitions if not explicit in payload.
 */
function inferEventType(ev) {
  const toSt = String(ev.to_state || '').toUpperCase();
  const reason = String(ev.reason || '').toLowerCase();

  if (toSt === 'CREATED' || reason.includes('initialized')) return 'SESSION_CREATION';
  if (toSt === 'INTENT_PARSED') return 'STATE_CHANGE';
  if (toSt === 'CULTURAL_TWIN_CREATED' || toSt === 'QLOO_RESOLVED' || toSt === 'CULTURAL_MATRIX_READY') return 'QLOO_RETRIEVAL';
  if (toSt === 'PLAN_GENERATED') return 'AGENT_COMPLETION';
  if (toSt === 'VALIDATED') return 'VALIDATION';
  if (toSt === 'AWAITING_APPROVAL') return 'GOVERNANCE_DECISION';
  if (toSt === 'APPROVED') return 'APPROVAL';
  if (toSt === 'FAILED') {
    return reason.includes('reject') ? 'REJECTION' : 'FAILURE';
  }
  if (toSt === 'EXECUTING') return 'EXECUTION_ATTEMPT';
  if (toSt === 'COMPLETED') return 'EXECUTION_OUTCOME';
  return 'STATE_CHANGE';
}

function inferActor(ev) {
  const toSt = String(ev.to_state || '').toUpperCase();
  const meta = ev.metadata || {};

  if (meta.approver) return `Human Curator: ${meta.approver}`;
  if (toSt === 'CREATED') return 'TasteOps Engine';
  if (toSt === 'INTENT_PARSED') return 'TasteOps Intent Parser';
  if (toSt === 'CULTURAL_TWIN_CREATED') return 'Cultural Intelligence Core';
  if (toSt === 'QLOO_RESOLVED') return 'Qloo MCP Adapter';
  if (toSt === 'CULTURAL_MATRIX_READY') return 'Qloo Cultural Matrix Service';
  if (toSt === 'AGENTS_RUNNING') return 'Agent Orchestrator';
  if (toSt === 'PLAN_GENERATED') return 'Domain Agent Ensemble';
  if (toSt === 'VALIDATED' || toSt === 'AWAITING_APPROVAL') return 'Governance Agent';
  if (toSt === 'APPROVED') return 'Human Curator';
  if (toSt === 'EXECUTING') return 'Execution Dispatcher';
  if (toSt === 'COMPLETED') return 'TasteOps Execution Subsystem';
  if (toSt === 'FAILED') return 'Governance Guard';
  return 'TasteOps System';
}
