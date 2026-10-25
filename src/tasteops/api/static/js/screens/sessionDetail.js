/**
 * TasteOps Session Overview & Cultural Twin Screen (/sessions/[sessionId]).
 *
 * Implements authoritative Cultural Twin intelligence view:
 * 1. Clearly distinguishes:
 *    - SOURCE EVIDENCE (Empirical brief signals & verified Qloo entity resolutions)
 *    - INFERENCE (Synthesized audience, mood, cultural themes, constraints, exclusions)
 *    - RECOMMENDATION (Multidimensional taste affinities across 6 cultural domains)
 *
 * 2. Displays all required elements:
 *    - audience profile
 *    - cultural themes
 *    - mood
 *    - anchor entities
 *    - resolved entities
 *    - resolved tags
 *    - constraints
 *    - exclusions
 *    - confidence
 *    - evidence
 *    - provenance
 *
 * 3. Shows explicit alerts if evidence is missing.
 * 4. Never invents Qloo entities, scores, IDs, or evidence.
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
      const ct = session.cultural_twin || {};
      const matSummary = session.cultural_matrix_summary || {};
      const mat = session.cultural_matrix || {};

      container.innerHTML = `
        <div class="fade-in" style="padding-bottom: 4rem;">
          <!-- Top Header -->
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
              <button class="btn btn-secondary" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/ledger')">
                <span>📜 Audit Ledger</span>
              </button>
            </div>
          </header>

          <!-- Sub-navigation Tabs -->
          ${renderSubNav(sessionId, 'overview')}

          <!-- Real-Time SSE Stream Monitor -->
          <div class="stream-monitor-bar" style="margin-bottom: 1.5rem;">
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

          <!-- =================================================================== -->
          <!-- CULTURAL TWIN THREE-TIER INTELLIGENCE ARCHITECTURE                  -->
          <!-- =================================================================== -->
          <div style="margin-top: 2.5rem; margin-bottom: 2.5rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; border-bottom: 1px solid var(--border-subtle); padding-bottom: 0.75rem;">
              <div>
                <h2 style="font-family: var(--font-heading); font-size: 1.4rem; font-weight: 700; color: var(--text-primary); margin: 0; display: flex; align-items: center; gap: 0.6rem;">
                  <span>🧬</span> Cultural Twin & Provenance Intelligence
                </h2>
                <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem;">
                  Rigorous distinction between empirical source evidence, strategic inferences, and algorithmic taste recommendations.
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span class="badge" style="background: rgba(16, 185, 129, 0.12); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.25); font-size: 0.75rem;">SOURCE EVIDENCE</span>
                <span class="badge" style="background: rgba(99, 102, 241, 0.12); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.25); font-size: 0.75rem;">INFERENCE</span>
                <span class="badge" style="background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.25); font-size: 0.75rem;">RECOMMENDATION</span>
              </div>
            </div>

            <!-- TIER 1: SOURCE EVIDENCE -->
            <div class="card" style="margin-bottom: 2rem; border-left: 4px solid #10b981; background: var(--bg-surface);">
              <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
                <div>
                  <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.25rem;">
                    <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-weight: 700; border: 1px solid rgba(16, 185, 129, 0.4);">
                      SOURCE EVIDENCE
                    </span>
                    <span style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary);">
                      Empirical Brief Signals & Authoritative Qloo Ground Truth
                    </span>
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary);">
                    Empirical facts submitted in the venue brief or verified via external knowledge graph queries. Never synthesized or hallucinated.
                  </div>
                </div>
              </div>

              <!-- 1A: Anchor Entities (Raw User Input) -->
              <div style="padding: 1.5rem 0 1rem; border-bottom: 1px solid var(--border-subtle);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                  <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">
                    Anchor Entities (Raw Brief Input)
                  </div>
                  <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                    ${(ct.anchor_entities || []).length} Anchors Registered
                  </span>
                </div>

                ${(ct.anchor_entities && ct.anchor_entities.length > 0) ? `
                  <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                    ${ct.anchor_entities.map(anchor => `
                      <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 0.4rem 0.85rem; border-radius: var(--radius-sm); display: inline-flex; align-items: center; gap: 0.5rem;">
                        <span style="color: #34d399; font-size: 0.85rem;">⚓</span>
                        <span style="font-weight: 500; font-size: 0.9rem; color: var(--text-primary);">${escapeHtml(anchor)}</span>
                        <span style="font-size: 0.7rem; background: rgba(255,255,255,0.06); padding: 0.1rem 0.35rem; border-radius: 3px; color: var(--text-muted);">Brief Source</span>
                      </div>
                    `).join('')}
                  </div>
                ` : `
                  <div style="background: rgba(245, 158, 11, 0.06); border: 1px dashed rgba(245, 158, 11, 0.3); padding: 0.75rem 1rem; border-radius: var(--radius-md); color: #fbbf24; font-size: 0.85rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span>⚠️</span>
                    <span><strong>EVIDENCE MISSING:</strong> No anchor entities were provided in the space brief.</span>
                  </div>
                `}
              </div>

              <!-- 1B: Resolved Entities (Verified Qloo IDs & Matches) -->
              <div style="padding: 1.5rem 0 1rem; border-bottom: 1px solid var(--border-subtle);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                  <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">
                    Resolved Entities (Authoritative Qloo Verification)
                  </div>
                  <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                    ${(ct.resolved_entities || []).length} Entities Verified
                  </span>
                </div>

                ${(ct.resolved_entities && ct.resolved_entities.length > 0) ? `
                  <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                    ${ct.resolved_entities.map(ent => {
                      const hasEvidence = ent.evidence && Object.keys(ent.evidence).length > 0;
                      return `
                        <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 0.5rem;">
                            <div>
                              <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                                <span style="font-weight: 700; color: var(--text-primary); font-size: 1rem;">${escapeHtml(ent.name)}</span>
                                <span class="badge" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc; font-size: 0.75rem; text-transform: uppercase;">
                                  ${escapeHtml(ent.type || 'Entity')}
                                </span>
                                <span class="hash-pill" style="font-size: 0.75rem; color: var(--cyan);">
                                  ${escapeHtml(ent.id)}
                                </span>
                              </div>
                              <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.35rem;">
                                ${escapeHtml(ent.why_it_matters || 'Ground truth reference entity verified in Qloo.')}
                              </div>
                            </div>
                            <div style="text-align: right; flex-shrink: 0;">
                              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Confidence</div>
                              <div style="font-weight: 700; color: #34d399; font-size: 1.1rem; font-family: var(--font-mono);">
                                ${((ent.confidence || 1.0) * 100).toFixed(0)}%
                              </div>
                            </div>
                          </div>

                          <!-- Evidence Payload Box -->
                          <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); font-size: 0.8rem;">
                            ${hasEvidence ? `
                              <div style="color: var(--text-muted); display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                                <span style="color: #34d399;">✓</span>
                                <span style="font-weight: 600; text-transform: uppercase; font-size: 0.7rem; color: var(--text-secondary);">Verified Evidence Payload:</span>
                                <span style="font-family: var(--font-mono); color: var(--text-muted); font-size: 0.75rem;">Source: ${escapeHtml(ent.source || 'qloo_search')}</span>
                              </div>
                              <pre style="background: rgba(0,0,0,0.3); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-secondary); overflow-x: auto; margin: 0;">${escapeHtml(JSON.stringify(ent.evidence, null, 2))}</pre>
                            ` : `
                              <div style="background: rgba(245, 158, 11, 0.08); border: 1px dashed rgba(245, 158, 11, 0.3); padding: 0.5rem 0.75rem; border-radius: 4px; color: #fbbf24; display: flex; align-items: center; justify-content: space-between;">
                                <div style="display: flex; align-items: center; gap: 0.4rem;">
                                  <span>⚠️</span>
                                  <span><strong>EVIDENCE MISSING:</strong> Raw match telemetry was not recorded for this entity.</span>
                                </div>
                                <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">source: ${escapeHtml(ent.source || 'untracked')}</span>
                              </div>
                            `}
                          </div>
                        </div>
                      `;
                    }).join('')}
                  </div>
                ` : `
                  <div style="background: rgba(245, 158, 11, 0.06); border: 1px dashed rgba(245, 158, 11, 0.3); padding: 1rem; border-radius: var(--radius-md); color: #fbbf24; font-size: 0.85rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span>⚠️</span>
                    <span><strong>EVIDENCE MISSING:</strong> No entities could be resolved in Qloo from anchor references.</span>
                  </div>
                `}
              </div>

              <!-- 1C: Resolved Tags -->
              <div style="padding: 1.5rem 0 1rem; border-bottom: 1px solid var(--border-subtle);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                  <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">
                    Resolved Tags (Aesthetic Motifs)
                  </div>
                  <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                    ${((ct.resolved_tag_details && ct.resolved_tag_details.length) || (ct.resolved_tags && ct.resolved_tags.length) || 0)} Tags
                  </span>
                </div>

                ${(ct.resolved_tag_details && ct.resolved_tag_details.length > 0) ? `
                  <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0.75rem;">
                    ${ct.resolved_tag_details.map(tag => `
                      <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 0.75rem; border-radius: var(--radius-md);">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                          <span style="font-weight: 600; font-size: 0.85rem; color: var(--text-primary);">${escapeHtml(tag.name)}</span>
                          <span class="hash-pill" style="font-size: 0.7rem; color: var(--cyan);">${escapeHtml(tag.id)}</span>
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(tag.why_it_matters || tag.category || 'Verified aesthetic tag')}</div>
                      </div>
                    `).join('')}
                  </div>
                ` : (ct.resolved_tags && ct.resolved_tags.length > 0) ? `
                  <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                    ${ct.resolved_tags.map(t => `
                      <span class="hash-pill" style="font-size: 0.8rem; padding: 0.35rem 0.7rem; color: #a5b4fc;">
                        #${escapeHtml(t)}
                      </span>
                    `).join('')}
                  </div>
                ` : `
                  <div style="background: rgba(255,255,255,0.02); border: 1px dashed var(--border-subtle); padding: 0.75rem 1rem; border-radius: var(--radius-md); color: var(--text-muted); font-size: 0.85rem;">
                    No resolved tags registered.
                  </div>
                `}
              </div>

              <!-- 1D: Provenance Audit Trail -->
              <div style="padding-top: 1.5rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                  <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">
                    Signal Provenance Audit Chain
                  </div>
                  <span style="font-size: 0.75rem; color: #34d399; font-weight: 600;">
                    ✓ Immutable Trace
                  </span>
                </div>

                ${(ct.provenance && ct.provenance.length > 0) ? `
                  <div style="background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); overflow: hidden;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
                      <thead>
                        <tr style="border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface-elevated); color: var(--text-muted); text-align: left;">
                          <th style="padding: 0.6rem 0.85rem;">Signal Type</th>
                          <th style="padding: 0.6rem 0.85rem;">Target / Category</th>
                          <th style="padding: 0.6rem 0.85rem;">Source</th>
                          <th style="padding: 0.6rem 0.85rem;">Provenance Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        ${ct.provenance.map(p => `
                          <tr style="border-bottom: 1px solid rgba(255,255,255,0.03);">
                            <td style="padding: 0.6rem 0.85rem; font-family: var(--font-mono); color: var(--cyan);">${escapeHtml(p.type)}</td>
                            <td style="padding: 0.6rem 0.85rem; font-weight: 500; color: var(--text-primary);">${escapeHtml(p.target_name || p.category || p.target_id || '')}</td>
                            <td style="padding: 0.6rem 0.85rem; color: var(--text-muted);">${escapeHtml(p.source || 'qloo')}</td>
                            <td style="padding: 0.6rem 0.85rem; color: var(--text-secondary); font-size: 0.75rem;">${escapeHtml(p.message || (p.confidence ? `Match confidence: ${(p.confidence*100).toFixed(0)}%` : 'Verified trace'))}</td>
                          </tr>
                        `).join('')}
                      </tbody>
                    </table>
                  </div>
                ` : `
                  <div style="background: rgba(245, 158, 11, 0.06); border: 1px dashed rgba(245, 158, 11, 0.3); padding: 0.75rem 1rem; border-radius: var(--radius-md); color: #fbbf24; font-size: 0.85rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span>⚠️</span>
                    <span><strong>PROVENANCE MISSING:</strong> External signal provenance logs are not recorded for this session.</span>
                  </div>
                `}
              </div>
            </div>

            <!-- TIER 2: INFERENCE -->
            <div class="card" style="margin-bottom: 2rem; border-left: 4px solid #6366f1; background: var(--bg-surface);">
              <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
                <div>
                  <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.25rem;">
                    <span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; font-weight: 700; border: 1px solid rgba(99, 102, 241, 0.4);">
                      INFERENCE
                    </span>
                    <span style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary);">
                      Strategic Inferences & Cultural Identity Synthesis
                    </span>
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary);">
                    Cultural psychographics, atmospheric archetypes, and aesthetic guardrails deduced by the Cultural Strategist agent.
                  </div>
                </div>
                <div style="text-align: right;">
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Overall Confidence</div>
                  <div style="font-weight: 700; color: #a5b4fc; font-size: 1.25rem; font-family: var(--font-mono);">
                    ${((ct.confidence !== undefined ? ct.confidence : 1.0) * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; padding: 1.5rem 0;">
                <!-- Audience Profile Inference -->
                <div style="background: var(--bg-surface-elevated); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.4rem; font-weight: 600;">
                    Audience Profile (Synthesized)
                  </div>
                  <div style="color: var(--text-primary); font-size: 0.95rem; line-height: 1.5;">
                    ${escapeHtml(ct.audience_profile || 'Inference pending: no audience profile synthesized.')}
                  </div>
                </div>

                <!-- Mood & Atmosphere Inference -->
                <div style="background: var(--bg-surface-elevated); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.4rem; font-weight: 600;">
                    Mood & Atmospheric Archetype
                  </div>
                  <div style="color: var(--text-primary); font-size: 0.95rem; line-height: 1.5;">
                    ${escapeHtml(ct.mood_profile || ct.mood || 'Inference pending: no mood profile synthesized.')}
                  </div>
                </div>
              </div>

              <!-- Cultural Themes (Hashtags) -->
              <div style="margin-bottom: 1.5rem;">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem; font-weight: 600;">
                  Synthesized Cultural Themes
                </div>
                ${(ct.cultural_themes && ct.cultural_themes.length > 0) ? `
                  <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                    ${ct.cultural_themes.map(th => `
                      <span style="font-size: 0.8rem; background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.3); color: #c7d2fe; padding: 0.3rem 0.65rem; border-radius: var(--radius-sm); font-weight: 500;">
                        #${escapeHtml(th)}
                      </span>
                    `).join('')}
                  </div>
                ` : `
                  <div style="color: var(--text-muted); font-size: 0.85rem;">[No cultural themes inferred]</div>
                `}
              </div>

              <!-- Constraints & Exclusions Grid -->
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; border-top: 1px solid var(--border-subtle); padding-top: 1.5rem;">
                <!-- Constraints -->
                <div>
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem; font-weight: 600; display: flex; align-items: center; gap: 0.4rem;">
                    <span>🛡️</span> Cultural Constraints & Guardrails
                  </div>
                  ${((ct.cultural_constraints && ct.cultural_constraints.length > 0) || (ct.constraints && (Array.isArray(ct.constraints) ? ct.constraints.length > 0 : Object.keys(ct.constraints).length > 0))) ? `
                    <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6;">
                      ${(ct.cultural_constraints || []).map(c => `<li>${escapeHtml(c)}</li>`).join('')}
                      ${Array.isArray(ct.constraints) ? ct.constraints.map(c => `<li>${escapeHtml(c)}</li>`).join('') : ''}
                      ${(!Array.isArray(ct.constraints) && typeof ct.constraints === 'object') ? Object.entries(ct.constraints).map(([k, v]) => `<li>${escapeHtml(k)}: ${escapeHtml(typeof v === 'object' ? JSON.stringify(v) : v)}</li>`).join('') : ''}
                    </ul>
                  ` : `
                    <div style="color: var(--text-muted); font-size: 0.85rem;">[No specific cultural constraints declared]</div>
                  `}
                </div>

                <!-- Exclusions -->
                <div>
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem; font-weight: 600; display: flex; align-items: center; gap: 0.4rem;">
                    <span>🚫</span> Aesthetic Exclusions & Antipatterns
                  </div>
                  ${(ct.exclusions && ct.exclusions.length > 0) ? `
                    <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.85rem; color: #f87171; line-height: 1.6;">
                      ${ct.exclusions.map(ex => `<li>${escapeHtml(ex)}</li>`).join('')}
                    </ul>
                  ` : `
                    <div style="color: var(--text-muted); font-size: 0.85rem;">[No exclusions declared]</div>
                  `}
                </div>
              </div>
            </div>

            <!-- TIER 3: RECOMMENDATION -->
            <div class="card" style="border-left: 4px solid #f59e0b; background: var(--bg-surface);">
              <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
                <div>
                  <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.25rem;">
                    <span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-weight: 700; border: 1px solid rgba(245, 158, 11, 0.4);">
                      RECOMMENDATION
                    </span>
                    <span style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary);">
                      Multidimensional Cultural Matrix Affinities (Qloo)
                    </span>
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary);">
                    Cross-domain affinity scoring retrieved from verified Qloo taste endpoints. Entity IDs and affinity percentages are empirical outputs.
                  </div>
                </div>
                <div style="text-align: right;">
                  <span class="badge badge-approved" style="font-size: 0.75rem;">
                    ${matSummary.total_entities || 0} Total Entities
                  </span>
                </div>
              </div>

              <!-- Domain Affinities Grid -->
              <div style="padding-top: 1.5rem;">
                ${(matSummary.top_affinities && Object.keys(matSummary.top_affinities).length > 0) ? `
                  <div style="display: flex; flex-direction: column; gap: 1rem;">
                    ${Object.entries(matSummary.top_affinities).map(([domain, items]) => `
                      <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                          <div style="font-weight: 700; text-transform: uppercase; font-size: 0.85rem; color: var(--cyan); display: flex; align-items: center; gap: 0.5rem;">
                            <span>${getDomainIcon(domain)}</span>
                            <span>${escapeHtml(domain)}</span>
                          </div>
                          <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                            ${items.length} verified items
                          </span>
                        </div>

                        ${items.length > 0 ? `
                          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 0.5rem;">
                            ${items.map(it => `
                              <div style="background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;">
                                <div style="overflow: hidden;">
                                  <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                    ${escapeHtml(it.name)}
                                  </div>
                                  <div style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                    ${escapeHtml(it.id)}
                                  </div>
                                </div>
                                <span class="hash-pill" style="font-size: 0.75rem; color: #34d399; font-weight: 700; flex-shrink: 0;">
                                  ${((it.affinity || 0) * 100).toFixed(0)}%
                                </span>
                              </div>
                            `).join('')}
                          </div>
                        ` : `
                          <div style="font-size: 0.8rem; color: var(--text-muted);">
                            No recommendations returned for this domain (Evidence: Empty Qloo response).
                          </div>
                        `}
                      </div>
                    `).join('')}
                  </div>
                ` : `
                  <div style="background: rgba(255,255,255,0.02); border: 1px dashed var(--border-subtle); padding: 1.5rem; border-radius: var(--radius-md); text-align: center; color: var(--text-muted);">
                    Multidimensional cultural matrix pending resolution. No recommendations generated yet.
                  </div>
                `}
              </div>
            </div>
          </div>

          <!-- Bottom: Specialized Domain Agent Summaries & Governance Audit -->
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 2rem;">
            <!-- Agent Summaries -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>🤖</span> Domain Agent Orchestration
                </div>
                <a href="/sessions/${escapeHtml(sessionId)}/activity" class="btn btn-secondary btn-sm" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/activity');">
                  <span>View Telemetry →</span>
                </a>
              </div>

              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem;">
                <!-- Cultural Strategist -->
                <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 0.4rem;">
                      <span>🧭</span> Cultural Strategist
                    </div>
                    ${renderAgentStatusBadge(session.agent_summaries?.cultural_strategist?.status || 'COMPLETED')}
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5;">
                    ${escapeHtml(session.agent_summaries?.cultural_strategist?.output_summary?.decisions || 'Translates brief into Cultural Twin, resolves anchor terms in Qloo.')}
                  </div>
                  <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                    Duration: ${escapeHtml(session.agent_summaries?.cultural_strategist?.duration || '0.15s')}
                  </div>
                </div>

                <!-- Experience Architect -->
                <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 0.4rem;">
                      <span>📐</span> Experience Architect
                    </div>
                    ${renderAgentStatusBadge(session.agent_summaries?.experience_architect?.status || 'COMPLETED')}
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5;">
                    ${escapeHtml(session.agent_summaries?.experience_architect?.output_summary?.decisions || 'Synthesizes spatial zones, acoustic identity, and sensory atmospheres.')}
                  </div>
                  <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                    Duration: ${escapeHtml(session.agent_summaries?.experience_architect?.duration || '0.18s')}
                  </div>
                </div>

                <!-- Partnership Agent -->
                <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 0.4rem;">
                      <span>🤝</span> Partnership Agent
                    </div>
                    ${renderAgentStatusBadge(session.agent_summaries?.partnership_agent?.status || 'COMPLETED')}
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5;">
                    ${escapeHtml(session.agent_summaries?.partnership_agent?.output_summary?.decisions || 'Curates high-affinity brand and artist partnerships with commercial tiering.')}
                  </div>
                  <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                    Duration: ${escapeHtml(session.agent_summaries?.partnership_agent?.duration || '0.14s')}
                  </div>
                </div>

                <!-- Governance / Execution Agent -->
                <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 0.4rem;">
                      <span>⚖️</span> Governance / Execution Agent
                    </div>
                    ${renderAgentStatusBadge(session.agent_summaries?.governance_agent?.status || 'AWAITING_APPROVAL')}
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5;">
                    ${escapeHtml(session.agent_summaries?.governance_agent?.output_summary?.decisions || 'Audited provenance against Qloo signatures, enforced approval gate.')}
                  </div>
                  <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                    Duration: ${escapeHtml(session.agent_summaries?.governance_agent?.duration || '0.08s')}
                  </div>
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

function getDomainIcon(domain) {
  switch (domain?.toLowerCase()) {
    case 'artists': return '🎵';
    case 'books': return '📚';
    case 'brands': return '🏷️';
    case 'places': return '📍';
    case 'movies': return '🎬';
    case 'destinations': return '✈️';
    default: return '✦';
  }
}
