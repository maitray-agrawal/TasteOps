/**
 * TasteOps Agent Activity & Telemetry Screen (/sessions/[sessionId]/activity).
 *
 * Implements real-time observability into the 4 domain agents:
 * 1. Cultural Strategist
 * 2. Experience Architect
 * 3. Partnership Agent
 * 4. Governance / Execution Agent
 *
 * Displays for each agent:
 * - status (RUNNING, COMPLETED, FAILED, RETRYING, BLOCKED, AWAITING_APPROVAL)
 * - start timestamp
 * - completion timestamp
 * - duration
 * - output summary (concise reasoning, decisions, outputs - no raw chain-of-thought)
 * - validation status
 * - evidence count
 * - failure information (if failed)
 *
 * Real-time architecture:
 * - Consumes Server-Sent Events (SSE) when available.
 * - Automatically falls back to deterministic polling (3s) when SSE is unavailable.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  formatDate,
  renderAgentStatusBadge,
  renderBadge,
  renderError,
  renderLoading,
  renderStatePipeline,
  renderSubNav,
  showToast,
} from '../components/ui.js';

export async function renderSessionActivity(rootElement, params, router) {
  const sessionId = params.sessionId;
  if (!sessionId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="session-activity-container">
      ${renderLoading('Recovering domain agent execution telemetry...')}
    </div>
  `;

  const container = document.getElementById('session-activity-container');
  let streamSubscription = null;
  let fallbackPollTimer = null;
  let isSSEConnected = false;

  const stopPolling = () => {
    if (fallbackPollTimer) {
      clearInterval(fallbackPollTimer);
      fallbackPollTimer = null;
    }
  };

  const startPolling = () => {
    if (fallbackPollTimer) return;
    updateStreamStatus('polling');
    fallbackPollTimer = setInterval(() => {
      loadData(false);
    }, 3000);
  };

  function updateStreamStatus(mode, event = null) {
    const dot = document.getElementById('sse-agent-dot');
    const label = document.getElementById('sse-agent-label');
    const lastEventText = document.getElementById('sse-agent-last-event');
    const eventIdPill = document.getElementById('sse-agent-event-id');

    if (mode === 'sse') {
      if (dot) {
        dot.style.background = '#10b981';
        dot.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.6)';
      }
      if (label) label.textContent = 'SSE Stream Connected (Real-Time)';
      if (event && lastEventText) {
        lastEventText.textContent = `Event: ${event.event_type} (${event.data?.summary || ''})`;
      }
      if (event && eventIdPill) {
        eventIdPill.textContent = event.event_id || 'reconnect-safe';
      }
    } else if (mode === 'polling') {
      if (dot) {
        dot.style.background = '#f59e0b';
        dot.style.boxShadow = '0 0 10px rgba(245, 158, 11, 0.4)';
      }
      if (label) label.textContent = 'SSE Disconnected • Polling Fallback Active (3s)';
      if (lastEventText) {
        lastEventText.textContent = 'Synchronizing via /api/v1/sessions endpoint polling.';
      }
      if (eventIdPill) {
        eventIdPill.textContent = 'polling-fallback';
      }
    }
  }

  const loadData = async (initialRender = true) => {
    try {
      const session = await apiClient.getSession(sessionId);
      const summaries = session.agent_summaries || {};

      const agents = [
        summaries.cultural_strategist || {
          name: 'Cultural Strategist',
          status: 'RUNNING',
          start: session.timestamps?.created_at,
          completion: null,
          duration: null,
          validation_status: 'PENDING_REVIEW',
          evidence_count: 0,
          failure_information: null,
          output_summary: { decisions: 'Transforming brief into cultural anchors.' },
        },
        summaries.experience_architect || {
          name: 'Experience Architect',
          status: 'BLOCKED',
          start: null,
          completion: null,
          duration: null,
          validation_status: 'BLOCKED',
          evidence_count: 0,
          failure_information: null,
          output_summary: { decisions: 'Awaiting Cultural Matrix signals.' },
        },
        summaries.partnership_agent || {
          name: 'Partnership Agent',
          status: 'BLOCKED',
          start: null,
          completion: null,
          duration: null,
          validation_status: 'BLOCKED',
          evidence_count: 0,
          failure_information: null,
          output_summary: { decisions: 'Awaiting Cultural Matrix affinities.' },
        },
        summaries.governance_agent || {
          name: 'Governance / Execution Agent',
          status: 'BLOCKED',
          start: null,
          completion: null,
          duration: null,
          validation_status: 'BLOCKED',
          evidence_count: 0,
          failure_information: null,
          output_summary: { decisions: 'Awaiting Activation Plan generation.' },
        },
      ];

      // Render full template on initial load, or update DOM in-place on live stream
      if (initialRender) {
        container.innerHTML = `
          <div class="fade-in" style="padding-bottom: 4rem;">
            <!-- Header -->
            <header class="page-header" style="margin-bottom: 1.5rem;">
              <div class="page-title-group">
                <div class="page-breadcrumbs">
                  <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                  <span class="breadcrumb-separator">/</span>
                  <a href="/sessions/${escapeHtml(sessionId)}" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}');">Sessions</a>
                  <span class="breadcrumb-separator">/</span>
                  <span style="color: var(--text-primary);">Agent Activity</span>
                </div>
                <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                  <span>Agent Activity & Execution Telemetry</span>
                  ${renderBadge(session.current_state)}
                </h1>
                <p class="page-subtitle">
                  Deterministic orchestration across specialized agents with provenance auditing and verifiable evidence telemetry.
                </p>
              </div>

              <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                ${session.current_state === 'AWAITING_APPROVAL' ? `
                  <button class="btn btn-primary" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/approval')">
                    <span>⚖️ Human Approval Gate →</span>
                  </button>
                ` : session.current_state === 'APPROVED' ? `
                  <button class="btn btn-success" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/execution')">
                    <span>⚡ Dispatch Execution Tasks →</span>
                  </button>
                ` : ''}
              </div>
            </header>

            <!-- Sub-navigation -->
            ${renderSubNav(sessionId, 'activity')}

            <!-- Real-Time SSE Stream & Fallback Polling Bar -->
            <div class="stream-monitor-bar" style="margin-bottom: 1.5rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span class="stream-status-pill">
                  <span class="stream-dot" id="sse-agent-dot"></span>
                  <span id="sse-agent-label">SSE Stream Active</span>
                </span>
                <span style="color: var(--text-muted);">|</span>
                <span id="sse-agent-last-event" style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-secondary);">
                  Listening on /api/v1/sessions/${escapeHtml(sessionId)}/stream
                </span>
              </div>
              <span class="hash-pill" id="sse-agent-event-id" style="font-size: 0.7rem;">reconnect-safe</span>
            </div>

            <!-- Pipeline Stepper -->
            ${renderStatePipeline(session.current_state)}

            <!-- Agent Activity Cards Grid -->
            <div id="agent-cards-container" style="display: flex; flex-direction: column; gap: 1.75rem; margin-top: 2rem;">
              ${renderAgentCardsHtml(agents)}
            </div>
          </div>
        `;
      } else {
        // In-place live update
        const cardsContainer = document.getElementById('agent-cards-container');
        if (cardsContainer) {
          cardsContainer.innerHTML = renderAgentCardsHtml(agents);
        }
      }

    } catch (err) {
      if (initialRender) {
        container.innerHTML = renderError({
          title: 'Failed to Load Agent Telemetry',
          error: err,
          retryId: 'btn-retry-activity',
        });
        document.getElementById('btn-retry-activity')?.addEventListener('click', () => loadData(true));
      }
    }
  };

  // Initial render
  await loadData(true);

  // 1. Primary: Subscribe to SSE stream
  streamSubscription = apiClient.subscribeSessionStream(sessionId, {
    onEvent(ev) {
      isSSEConnected = true;
      stopPolling();
      updateStreamStatus('sse', ev);

      // Re-fetch agent states on lifecycle events
      if (
        ev.event_type.startsWith('agent.') ||
        ev.event_type.startsWith('workflow.') ||
        ev.event_type.startsWith('governance.') ||
        ev.event_type === 'approval.required' ||
        ev.event_type === 'execution.completed' ||
        ev.event_type === 'execution.started'
      ) {
        loadData(false);
      }
    },
    onError(err) {
      isSSEConnected = false;
      // 2. Secondary Fallback: Initiate interval polling
      startPolling();
    },
  });

  // Cleanup on route navigation away
  const cleanUp = () => {
    stopPolling();
    if (streamSubscription) {
      streamSubscription.close();
      streamSubscription = null;
    }
  };

  window.addEventListener('popstate', cleanUp, { once: true });
}

function renderAgentCardsHtml(agents) {
  return agents.map(agent => {
    const isFailed = agent.status === 'FAILED';
    const isRunning = agent.status === 'RUNNING';
    const isRetrying = agent.status === 'RETRYING';
    const isAwaiting = agent.status === 'AWAITING_APPROVAL';

    let cardBorder = 'var(--border-subtle)';
    if (isFailed) cardBorder = '#ef4444';
    else if (isRunning) cardBorder = '#06b6d4';
    else if (isRetrying) cardBorder = '#f59e0b';
    else if (isAwaiting) cardBorder = '#f59e0b';
    else if (agent.status === 'COMPLETED') cardBorder = '#10b981';

    return `
      <div class="card" style="border-left: 4px solid ${cardBorder}; background: var(--bg-surface);">
        <!-- Card Header: Agent Title + Status Badge -->
        <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span style="font-size: 1.5rem;">${getAgentIcon(agent.name)}</span>
            <div>
              <div style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700; color: var(--text-primary);">
                ${escapeHtml(agent.name)}
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted);">
                ${getAgentRoleDescription(agent.name)}
              </div>
            </div>
          </div>
          <div>
            ${renderAgentStatusBadge(agent.status)}
          </div>
        </div>

        <!-- Telemetry Metrics Bar (Start, Completion, Duration, Evidence Count) -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; padding: 1.25rem 0; border-bottom: 1px solid var(--border-subtle);">
          <!-- Start -->
          <div style="background: var(--bg-surface-elevated); padding: 0.75rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
            <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.25rem;">
              Execution Start
            </div>
            <div style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-primary);">
              ${agent.start ? formatDate(agent.start) : '<span style="color: var(--text-muted);">Pending</span>'}
            </div>
          </div>

          <!-- Completion -->
          <div style="background: var(--bg-surface-elevated); padding: 0.75rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
            <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.25rem;">
              Completion
            </div>
            <div style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-primary);">
              ${agent.completion ? formatDate(agent.completion) : (isRunning ? '<span style="color: var(--cyan);">In Progress...</span>' : '<span style="color: var(--text-muted);">—</span>')}
            </div>
          </div>

          <!-- Duration -->
          <div style="background: var(--bg-surface-elevated); padding: 0.75rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
            <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.25rem;">
              Latency / Duration
            </div>
            <div style="font-family: var(--font-mono); font-size: 0.95rem; font-weight: 700; color: ${agent.duration ? 'var(--cyan)' : 'var(--text-muted)'};">
              ${agent.duration ? escapeHtml(agent.duration) : (isRunning ? 'Calculating...' : '—')}
            </div>
          </div>

          <!-- Evidence Count -->
          <div style="background: var(--bg-surface-elevated); padding: 0.75rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
            <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.25rem;">
              Evidence Count
            </div>
            <div style="font-family: var(--font-mono); font-size: 0.95rem; font-weight: 700; color: #34d399;">
              ${agent.evidence_count} Signals / Records
            </div>
          </div>
        </div>

        <!-- Failure Information Alert (If Failed) -->
        ${(isFailed || agent.failure_information) ? `
          <div style="margin: 1.25rem 0 0.5rem; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); padding: 1rem 1.25rem; border-radius: var(--radius-md); display: flex; align-items: flex-start; gap: 0.75rem;">
            <span style="font-size: 1.25rem;">⚠️</span>
            <div>
              <div style="font-weight: 700; color: #f87171; font-size: 0.9rem; margin-bottom: 0.25rem;">
                Failure Information & Execution Error
              </div>
              <div style="color: var(--text-secondary); font-size: 0.85rem; line-height: 1.5;">
                ${escapeHtml(agent.failure_information || 'Execution halted due to unhandled constraint failure or provider timeout.')}
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Output Summary & Strategic Reasoning (No raw chain-of-thought) -->
        <div style="padding-top: 1.25rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
            <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">
              Output Summary & Concise Reasoning
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-size: 0.75rem; color: var(--text-muted);">Validation:</span>
              <span class="badge" style="${getValidationStatusStyle(agent.validation_status)}">
                ${escapeHtml(agent.validation_status || 'PENDING_REVIEW')}
              </span>
            </div>
          </div>

          <div style="background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem 1.25rem;">
            ${renderAgentSpecificOutputSummary(agent)}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function renderAgentSpecificOutputSummary(agent) {
  const out = agent.output_summary || {};

  if (agent.name === 'Cultural Strategist') {
    const pillars = out.pillars || [];
    return `
      <div style="display: flex; flex-direction: column; gap: 0.6rem; font-size: 0.85rem;">
        <div>
          <span style="color: var(--text-muted); font-weight: 600;">Positioning Statement:</span>
          <span style="color: var(--text-primary); margin-left: 0.4rem;">${escapeHtml(out.positioning || 'Synthesized physical space brief.')}</span>
        </div>
        ${out.target_audience ? `
          <div>
            <span style="color: var(--text-muted); font-weight: 600;">Target Audience:</span>
            <span style="color: var(--text-secondary); margin-left: 0.4rem;">${escapeHtml(out.target_audience)}</span>
          </div>
        ` : ''}
        ${pillars.length > 0 ? `
          <div>
            <span style="color: var(--text-muted); font-weight: 600;">Synthesized Cultural Pillars (${pillars.length}):</span>
            <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.35rem;">
              ${pillars.map(p => `<span class="hash-pill" style="color: var(--cyan); font-size: 0.75rem;">${escapeHtml(p)}</span>`).join('')}
            </div>
          </div>
        ` : ''}
        <div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.25rem;">
          <span style="color: #34d399;">✓</span> <em>${escapeHtml(out.decisions || 'Brief translated into Cultural Twin and resolved against Qloo.')}</em>
        </div>
      </div>
    `;
  }

  if (agent.name === 'Experience Architect') {
    const zones = out.spatial_zones || [];
    const materials = out.material_palette || [];
    return `
      <div style="display: flex; flex-direction: column; gap: 0.6rem; font-size: 0.85rem;">
        ${out.sonic_profile ? `
          <div>
            <span style="color: var(--text-muted); font-weight: 600;">Acoustic & Sonic Identity:</span>
            <span style="color: var(--text-primary); margin-left: 0.4rem;">${escapeHtml(out.sonic_profile)}</span>
          </div>
        ` : ''}
        ${zones.length > 0 ? `
          <div>
            <span style="color: var(--text-muted); font-weight: 600;">Spatial Experience Zones (${zones.length}):</span>
            <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.35rem;">
              ${zones.map(z => `<span class="hash-pill" style="color: #a5b4fc; font-size: 0.75rem;">✦ ${escapeHtml(z)}</span>`).join('')}
            </div>
          </div>
        ` : ''}
        ${materials.length > 0 ? `
          <div>
            <span style="color: var(--text-muted); font-weight: 600;">Material Palette:</span>
            <span style="color: var(--text-secondary); margin-left: 0.4rem;">${escapeHtml(materials.join(', '))}</span>
          </div>
        ` : ''}
        <div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.25rem;">
          <span style="color: #34d399;">✓</span> <em>${escapeHtml(out.decisions || 'Spatial zones and sensory design synthesized.')}</em>
        </div>
      </div>
    `;
  }

  if (agent.name === 'Partnership Agent') {
    const partners = out.partners || [];
    return `
      <div style="display: flex; flex-direction: column; gap: 0.6rem; font-size: 0.85rem;">
        <div>
          <span style="color: var(--text-muted); font-weight: 600;">Curated Partnerships:</span>
          <span style="color: var(--text-primary); margin-left: 0.4rem;">${out.partnerships_count || partners.length} Alignments Identified</span>
        </div>
        ${partners.length > 0 ? `
          <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.35rem;">
            ${partners.map(p => `
              <span class="hash-pill" style="color: #fbbf24; font-size: 0.75rem;">
                🤝 ${escapeHtml(p.name)} <span style="color: var(--text-muted);">(${escapeHtml(p.tier || p.type || 'Partner')})</span>
              </span>
            `).join('')}
          </div>
        ` : ''}
        <div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.25rem;">
          <span style="color: #34d399;">✓</span> <em>${escapeHtml(out.decisions || 'Curated brand and artist partnerships with commercial tiering.')}</em>
        </div>
      </div>
    `;
  }

  // Governance / Execution Agent
  return `
    <div style="display: flex; flex-direction: column; gap: 0.6rem; font-size: 0.85rem;">
      <div style="display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;">
        <div>
          <span style="color: var(--text-muted); font-weight: 600;">Provenance Verified:</span>
          <span style="color: ${out.provenance_verified === true ? '#34d399' : (out.provenance_verified === false ? '#f87171' : 'var(--text-muted)')}; font-weight: 700; margin-left: 0.4rem;">
            ${out.provenance_verified === true ? '✓ Traceable' : (out.provenance_verified === false ? 'Unverified' : 'Unavailable')}
          </span>
        </div>
        <div>
          <span style="color: var(--text-muted); font-weight: 600;">Compliance Score:</span>
          <span style="color: var(--cyan); font-weight: 700; font-family: var(--font-mono); margin-left: 0.4rem;">
            ${typeof out.compliance_score === 'number' ? `${(out.compliance_score * 100).toFixed(0)}%` : 'Unavailable'}
          </span>
        </div>
        <div>
          <span style="color: var(--text-muted); font-weight: 600;">Planned Execution Tasks:</span>
          <span style="color: var(--text-primary); font-family: var(--font-mono); margin-left: 0.4rem;">
            ${out.execution_tasks_count || 0} Tasks
          </span>
        </div>
      </div>
      <div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.25rem;">
        <span style="color: #34d399;">✓</span> <em>${escapeHtml(out.decisions || 'Audited provenance against Qloo signatures, verified spatial constraints, and enforced approval gate.')}</em>
      </div>
    </div>
  `;
}

function getAgentIcon(name) {
  if (name.includes('Strategist')) return '🧭';
  if (name.includes('Architect')) return '📐';
  if (name.includes('Partnership')) return '🤝';
  return '⚖️';
}

function getAgentRoleDescription(name) {
  if (name.includes('Strategist')) {
    return 'Translates brief into Cultural Twin, resolves anchor terms via Qloo, and computes aggregate signal confidence.';
  }
  if (name.includes('Architect')) {
    return 'Constructs multi-zone sensory architecture, circadian lighting curves, acoustic profile, and reading library.';
  }
  if (name.includes('Partnership')) {
    return 'Identifies brand and artist collaboration opportunities with tiered alignment based on matrix affinities.';
  }
  return 'Enforces constraint compliance, verifies entity provenance against Qloo signatures, and dispatches execution tasks.';
}

function getValidationStatusStyle(status) {
  const s = String(status || '').toUpperCase();
  if (s === 'PASSED') {
    return 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);';
  }
  if (s === 'FAILED') {
    return 'background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3);';
  }
  if (s === 'BLOCKED') {
    return 'background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3);';
  }
  return 'background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3);';
}
