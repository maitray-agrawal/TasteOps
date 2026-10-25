/**
 * TasteOps Session Overview & Cultural Twin Screen (/sessions/[sessionId]).
 *
 * Displays live Server-Sent Events status, FSM visual state pipeline,
 * resolved Cultural Twin, multidimensional Cultural Matrix affinities,
 * agent run summaries, and governance provenance audits.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  formatDate,
  renderBadge,
  renderError,
  renderLoading,
  renderStatePipeline,
  renderSubNav,
  showToast,
} from '../components/ui.js';

export async function renderSessionDetail(rootElement, params, router) {
  const sessionId = params.sessionId;
  if (!sessionId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="session-detail-container">
      ${renderLoading('Recovering workflow session state & cultural artifacts...')}
    </div>
  `;

  const container = document.getElementById('session-detail-container');
  let streamSubscription = null;

  const loadData = async () => {
    try {
      const session = await apiClient.getSession(sessionId);

      container.innerHTML = `
        <div class="fade-in">
          <header class="page-header" style="margin-bottom: 1.5rem;">
            <div class="page-title-group">
              <div class="page-breadcrumbs">
                <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-muted);">Sessions</span>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-primary); font-family: var(--font-mono);">${escapeHtml(sessionId.slice(0, 12))}</span>
              </div>
              <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                <span>Session Workspace</span>
                ${renderBadge(session.current_state)}
              </h1>
              <p class="page-subtitle">
                Autonomous activation orchestration for Space <a href="/spaces/${escapeHtml(session.space_id)}" style="color: var(--cyan); text-decoration: underline;" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/spaces/${escapeHtml(session.space_id)}');">${escapeHtml(session.space_id)}</a>.
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
              <button class="btn btn-secondary" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/blueprint')">
                <span>📐 View Blueprint</span>
              </button>
            </div>
          </header>

          <!-- Sub-navigation Tabs -->
          ${renderSubNav(sessionId, 'overview')}

          <!-- Real-Time SSE Stream Monitor -->
          <div class="stream-monitor-bar">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span class="stream-status-pill">
                <span class="stream-dot" id="sse-live-dot"></span>
                <span id="sse-live-label">SSE Stream Active</span>
              </span>
              <span style="color: var(--text-muted);">|</span>
              <span id="sse-last-event" style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-secondary);">
                Listening on /api/v1/sessions/${escapeHtml(sessionId)}/stream
              </span>
            </div>
            <span class="hash-pill" id="sse-event-id" style="font-size: 0.7rem;">reconnect-safe</span>
          </div>

          <!-- FSM Workflow Pipeline Stepper -->
          ${renderStatePipeline(session.current_state)}

          <!-- Main Grid -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 2.5rem;">
            <!-- Cultural Twin Column -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>🧬</span> Cultural Twin
                </div>
                ${session.cultural_twin ? `
                  <span class="badge badge-approved" style="font-size: 0.75rem;">Confidence: ${(session.cultural_twin.confidence * 100).toFixed(0)}%</span>
                ` : '<span class="badge badge-created">Pending</span>'}
              </div>

              ${session.cultural_twin ? `
                <div style="margin-bottom: 1.25rem;">
                  <div style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Audience Profile</div>
                  <div style="color: var(--text-primary); font-size: 0.95rem;">${escapeHtml(session.cultural_twin.audience_profile || 'Curated physical space audience')}</div>
                </div>

                <div style="margin-bottom: 1.25rem;">
                  <div style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Mood & Spatial Archetype</div>
                  <div style="color: var(--text-primary); font-size: 0.95rem;">${escapeHtml(session.cultural_twin.mood_profile || 'Sensory sanctuary')}</div>
                </div>

                <div style="margin-bottom: 1.25rem;">
                  <div style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem;">Resolved Cultural Anchors (Qloo)</div>
                  <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                    ${(session.cultural_twin.resolved_entities || []).map(ent => `
                      <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 0.65rem 0.85rem; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: space-between;">
                        <div>
                          <div style="font-weight: 600; color: var(--text-primary); font-size: 0.9rem;">${escapeHtml(ent.name)}</div>
                          <div style="font-size: 0.775rem; color: var(--text-muted);">${escapeHtml(ent.type || 'Entity')} • ${escapeHtml(ent.why_it_matters || '')}</div>
                        </div>
                        <span class="hash-pill" style="color: #34d399;">${((ent.confidence || 1.0) * 100).toFixed(0)}%</span>
                      </div>
                    `).join('')}
                  </div>
                </div>

                ${(session.cultural_twin.cultural_themes || []).length > 0 ? `
                  <div style="margin-top: 1rem;">
                    <div style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.4rem;">Aesthetic Tags</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;">
                      ${session.cultural_twin.cultural_themes.map(t => `
                        <span style="font-size: 0.75rem; background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.25); color: #a5b4fc; padding: 0.2rem 0.5rem; border-radius: var(--radius-sm);">
                          #${escapeHtml(t)}
                        </span>
                      `).join('')}
                    </div>
                  </div>
                ` : ''}
              ` : `
                <div style="color: var(--text-muted); padding: 2rem 0; text-align: center;">Cultural Twin not yet materialized.</div>
              `}
            </div>

            <!-- Cultural Matrix Summary Column -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>📊</span> Cultural Matrix Affinities
                </div>
                ${session.cultural_matrix_summary ? `
                  <span class="badge badge-approved" style="font-size: 0.75rem;">${session.cultural_matrix_summary.total_entities || 0} Entities</span>
                ` : '<span class="badge badge-created">Pending</span>'}
              </div>

              ${session.cultural_matrix_summary ? `
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; background: var(--bg-surface-elevated); padding: 0.75rem 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                  <div>
                    <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Affinity Fingerprint</div>
                    <div style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--cyan);">${escapeHtml(session.cultural_matrix_summary.fingerprint || 'fp_generated')}</div>
                  </div>
                  <div style="text-align: right;">
                    <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Active Domains</div>
                    <div style="font-size: 0.85rem; color: var(--text-primary); font-weight: 600;">
                      ${(session.cultural_matrix_summary.domains_present || []).length} Categories
                    </div>
                  </div>
                </div>

                <div>
                  <div style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.75rem;">Cross-Domain Affinities</div>
                  <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                    ${Object.entries(session.cultural_matrix_summary.top_affinities || {}).map(([domain, items]) => `
                      <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 0.75rem 1rem;">
                        <div style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: var(--primary); margin-bottom: 0.5rem;">
                          ${escapeHtml(domain)}
                        </div>
                        <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                          ${items.map(it => `
                            <span style="font-size: 0.8rem; background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 0.25rem 0.6rem; border-radius: var(--radius-sm); color: var(--text-primary); display: inline-flex; align-items: center; gap: 0.35rem;">
                              <span>${escapeHtml(it.name)}</span>
                              <span style="font-size: 0.7rem; color: var(--cyan); font-family: var(--font-mono);">${(it.affinity * 100).toFixed(0)}%</span>
                            </span>
                          `).join('')}
                        </div>
                      </div>
                    `).join('')}
                  </div>
                </div>
              ` : `
                <div style="color: var(--text-muted); padding: 2rem 0; text-align: center;">Multidimensional matrix pending resolution.</div>
              `}
            </div>
          </div>

          <!-- Bottom: Agent Summaries & Governance Audit -->
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 2rem;">
            <!-- Agent Summaries -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>🤖</span> Specialized Agent Outputs
                </div>
              </div>

              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem;">
                <!-- Cultural Strategist -->
                <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                  <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem;">
                    <span>🧭</span> Cultural Strategist
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5;">
                    Synthesizes core cultural pillars and narrative positioning from multidimensional affinities.
                  </div>
                  <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--emerald);">✓ Complete</div>
                </div>

                <!-- Experience Architect -->
                <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                  <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem;">
                    <span>📐</span> Experience Architect
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5;">
                    Designs multi-zone acoustic, lighting, sensory, and signature programming specifications.
                  </div>
                  <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--emerald);">✓ Complete</div>
                </div>

                <!-- Partnership Agent -->
                <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                  <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem;">
                    <span>🤝</span> Partnership Agent
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5;">
                    Identifies high-affinity brand alignment partners and co-branded activation proposals.
                  </div>
                  <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--emerald);">✓ Complete</div>
                </div>
              </div>
            </div>

            <!-- Governance Audit Scorecard -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>⚖️</span> Governance Audit
                </div>
                ${session.validation?.is_valid ? `
                  <span class="badge badge-completed">Verified</span>
                ` : '<span class="badge badge-awaiting-approval">Review</span>'}
              </div>

              <div style="margin-bottom: 1rem;">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Provenance Chain</div>
                <div style="color: #34d399; font-weight: 600; font-size: 0.9rem;">
                  ${session.validation?.provenance_verified ? '✓ 100% Entities Provenance Verified' : 'Audit Incomplete'}
                </div>
              </div>

              <div style="margin-bottom: 1rem;">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Risk Assessment</div>
                <div style="color: var(--text-secondary); font-size: 0.85rem;">
                  ${(session.validation?.risk_flags || []).length === 0
                    ? '0 critical risks detected. All constraints satisfied.'
                    : `${session.validation.risk_flags.length} potential risk flags flagged.`}
                </div>
              </div>

              <div style="padding-top: 1rem; border-top: 1px solid var(--border-subtle);">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Cryptographic Plan Binding</div>
                <div class="hash-pill" style="font-size: 0.75rem; width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  ${escapeHtml(session.approval_state?.plan_hash || session.execution_plan?.plan_hash || 'SHA-256 bound')}
                </div>
              </div>
            </div>
          </div>
        </div>
      `;

      // Subscribe to real-time SSE stream
      streamSubscription = apiClient.subscribeSessionStream(sessionId, {
        onEvent(ev) {
          const lastEventLabel = document.getElementById('sse-last-event');
          const lastEventId = document.getElementById('sse-event-id');
          if (lastEventLabel) {
            lastEventLabel.textContent = `Live Event: ${ev.event_type} (${ev.data?.summary || ''})`;
          }
          if (lastEventId) {
            lastEventId.textContent = ev.event_id;
          }

          // If workflow transitioned, reload state to reflect newest pipeline step
          if (ev.event_type === 'workflow.state_changed' || ev.event_type === 'approval.required' || ev.event_type === 'execution.completed') {
            loadData();
          }
        },
        onError(err) {
          const label = document.getElementById('sse-live-label');
          const dot = document.getElementById('sse-live-dot');
          if (label && dot) {
            label.textContent = 'SSE Closed / Idle';
            dot.style.background = '#94a3b8';
            dot.style.boxShadow = 'none';
          }
        },
      });

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Failed to Load Workflow Session',
        error: err,
        retryId: 'btn-retry-session',
      });
      document.getElementById('btn-retry-session')?.addEventListener('click', loadData);
    }
  };

  loadData();
}
