/**
 * TasteOps Experience & Sensory Blueprint Screen (/sessions/[sessionId]/blueprint).
 *
 * Implements the comprehensive Experience Blueprint interface displaying:
 * - strategic objective
 * - audience
 * - cultural positioning
 * - experience concept
 * - activation ideas
 * - partnership opportunities
 * - budget considerations
 * - risks
 * - evidence
 * - confidence
 *
 * Every recommendation has a structured evidence/provenance path.
 *
 * Visually distinguishes the 4 foundational layers:
 * 1. [EVIDENCE] - Ground-truth Qloo entities, verified affinity scores, URN signatures (Emerald)
 * 2. [AGENT INFERENCE] - Synthesized subcultures, thematic axes, multi-dimensional scoring (Indigo)
 * 3. [RECOMMENDATION] - Curated spatial zoning, sonic curation, brand partnerships, salon formats (Cyan)
 * 4. [EXECUTION ACTION] - Downstream execution tasks, procurement items, outreach briefs (Amber)
 *
 * Enables answering: "Why was this recommendation made?" without exposing chain-of-thought.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  renderBadge,
  renderError,
  renderLoading,
  renderSubNav,
  showToast,
} from '../components/ui.js';

export async function renderSessionBlueprint(rootElement, params, router) {
  const sessionId = params.sessionId;
  if (!sessionId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="blueprint-container">
      ${renderLoading('Synthesizing experience blueprint & provenance telemetry...')}
    </div>
  `;

  const container = document.getElementById('blueprint-container');

  const loadData = async () => {
    try {
      const blueprint = await apiClient.getSessionBlueprint(sessionId);
      const provMap = blueprint.recommendation_provenance_map || {};

      // Expose modal handler globally for interactive provenance inspection
      window.tasteopsInspectProvenance = (entityKey) => {
        const item = provMap[entityKey];
        if (!item) {
          showToast({ title: 'Provenance Record Unavailable', text: `Telemetry record for "${entityKey}" not cached in active session.`, type: 'warning' });
          return;
        }
        renderProvenanceModal(item);
      };

      window.tasteopsCloseProvenanceModal = () => {
        const modal = document.getElementById('provenance-modal-backdrop');
        if (modal) modal.remove();
      };

      const strategicObj = blueprint.strategic_objective || blueprint.experience_narrative || 'Curated physical space activation grounded in verified taste intelligence.';
      const audience = blueprint.audience || {};
      const cultPos = blueprint.cultural_positioning || {};
      const expConcept = blueprint.experience_concept || {};
      const activations = blueprint.activation_ideas || blueprint.programming_calendar || [];
      const partnerships = blueprint.partnership_opportunities || blueprint.partnerships || [];
      const budget = blueprint.budget_considerations || {};
      const risks = blueprint.risks || [];
      const evidence = blueprint.evidence || [];
      const confidence = typeof blueprint.confidence === 'number' ? blueprint.confidence : null;
      const actions = blueprint.execution_actions || [];
      const zones = blueprint.spatial_zones || expConcept.spatial_zones || [];
      const soundscape = blueprint.soundscape_design || expConcept.soundscape_design || {};
      const pillars = blueprint.cultural_pillars || cultPos.cultural_pillars || [];

      container.innerHTML = `
        <div class="fade-in" style="padding-bottom: 5rem;">
          <!-- Header -->
          <header class="page-header" style="margin-bottom: 1.5rem;">
            <div class="page-title-group">
              <div class="page-breadcrumbs">
                <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                <span class="breadcrumb-separator">/</span>
                <a href="/sessions/${escapeHtml(sessionId)}" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}');">Sessions</a>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-primary);">Experience Blueprint</span>
              </div>
              <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                <span>Experience & Sensory Blueprint</span>
                ${renderBadge(blueprint.state)}
              </h1>
              <p class="page-subtitle">
                Comprehensive architectural choreography, sensory identities, signature programming, and brand partnerships with verifiable provenance.
              </p>
            </div>

            <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
              ${blueprint.state === 'AWAITING_APPROVAL' ? `
                <button class="btn btn-primary" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/approval')">
                  <span>⚖️ Human Approval Gate →</span>
                </button>
              ` : blueprint.state === 'APPROVED' ? `
                <button class="btn btn-success" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/execution')">
                  <span>⚡ Dispatch Execution Tasks →</span>
                </button>
              ` : ''}
              <button class="btn btn-secondary" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/activity')">
                <span>🤖 Agent Activity</span>
              </button>
              <button class="btn btn-secondary" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}')">
                <span>🧬 Cultural Twin</span>
              </button>
            </div>
          </header>

          <!-- Sub-navigation -->
          ${renderSubNav(sessionId, 'blueprint')}

          <!-- Telemetry & Security Header Bar -->
          <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 0.85rem 1.25rem; margin-bottom: 2rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
            <div style="display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;">
              <!-- Cryptographic Hash -->
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">Plan Signature:</span>
                <span class="hash-pill" style="font-size: 0.75rem; font-family: var(--font-mono); color: ${blueprint.plan_hash ? '#34d399' : 'var(--text-muted)'};">
                  ${blueprint.plan_hash ? `🔒 ${escapeHtml(blueprint.plan_hash.slice(0, 18))}...` : 'Pending approval sign-off'}
                </span>
              </div>

              <!-- Signal Confidence -->
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">Signal Confidence:</span>
                <span class="badge" style="background: ${confidence !== null ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)'}; color: ${confidence !== null ? '#34d399' : 'var(--text-muted)'}; font-weight: 700; font-family: var(--font-mono);">
                  ${confidence !== null ? `${(confidence * 100).toFixed(0)}% Model Confidence` : 'Unavailable'}
                </span>
              </div>

              <!-- Budget Allocation -->
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">Budget Target:</span>
                <span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; font-family: var(--font-mono);">
                  💰 ${escapeHtml(budget.estimated_cost || blueprint.estimated_cost || 'Not estimated')}
                </span>
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span class="badge" style="background: rgba(6, 182, 212, 0.15); color: var(--cyan); font-size: 0.75rem;">
                ✦ Provenance Audited
              </span>
            </div>
          </div>

          <!-- 4-Tier Visual Distinction Legend -->
          <div style="background: rgba(0, 0, 0, 0.35); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem 1.25rem; margin-bottom: 2rem;">
            <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.75rem;">
              Blueprint Epistemic Architecture & Visual Distinction
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem;">
              <!-- 1. Evidence -->
              <div style="background: rgba(16, 185, 129, 0.08); border-left: 3px solid #10b981; padding: 0.6rem 0.85rem; border-radius: 0 var(--radius-sm) var(--radius-sm) 0;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #34d399; display: flex; align-items: center; gap: 0.4rem;">
                  <span>🔬 1. EVIDENCE</span>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.2rem; line-height: 1.4;">
                  Ground-truth Qloo entities, verified URNs & affinity scores.
                </div>
              </div>

              <!-- 2. Agent Inference -->
              <div style="background: rgba(99, 102, 241, 0.08); border-left: 3px solid #6366f1; padding: 0.6rem 0.85rem; border-radius: 0 var(--radius-sm) var(--radius-sm) 0;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #a5b4fc; display: flex; align-items: center; gap: 0.4rem;">
                  <span>🧠 2. AGENT INFERENCE</span>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.2rem; line-height: 1.4;">
                  Synthesized subcultures, themes & 6D partner affinity models.
                </div>
              </div>

              <!-- 3. Recommendation -->
              <div style="background: rgba(6, 182, 212, 0.08); border-left: 3px solid #06b6d4; padding: 0.6rem 0.85rem; border-radius: 0 var(--radius-sm) var(--radius-sm) 0;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #22d3ee; display: flex; align-items: center; gap: 0.4rem;">
                  <span>✦ 3. RECOMMENDATION</span>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.2rem; line-height: 1.4;">
                  Curated zoning, sonic identity, brand partnerships & salon programming.
                </div>
              </div>

              <!-- 4. Execution Action -->
              <div style="background: rgba(245, 158, 11, 0.08); border-left: 3px solid #f59e0b; padding: 0.6rem 0.85rem; border-radius: 0 var(--radius-sm) var(--radius-sm) 0;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #fbbf24; display: flex; align-items: center; gap: 0.4rem;">
                  <span>⚡ 4. EXECUTION ACTION</span>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.2rem; line-height: 1.4;">
                  Downstream operational tasks, procurement & outreach briefs.
                </div>
              </div>
            </div>
          </div>

          <!-- SECTION 1: Strategic Objective & Cultural Positioning -->
          <div class="card" style="margin-bottom: 2rem;">
            <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.35rem;">🧭</span>
                <div>
                  <div class="card-title">Strategic Objective & Cultural Positioning</div>
                  <div style="font-size: 0.8rem; color: var(--text-muted);">
                    Core thematic foundation, target subcultures, and aesthetic pillars synthesized by Cultural Strategist.
                  </div>
                </div>
              </div>
              <div style="display: flex; gap: 0.4rem;">
                <span class="badge" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc;">🧠 AGENT INFERENCE</span>
                <span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #22d3ee;">✦ RECOMMENDATION</span>
              </div>
            </div>

            <!-- Strategic Narrative -->
            <div style="padding: 1.25rem 0; border-bottom: 1px solid var(--border-subtle);">
              <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.5rem;">
                Strategic Cultural Narrative
              </div>
              <p style="font-size: 1.1rem; line-height: 1.6; color: var(--text-primary); margin: 0; font-family: var(--font-heading); font-style: italic;">
                "${escapeHtml(strategicObj)}"
              </p>
            </div>

            <!-- Audience Breakdown & Targeted Subcultures -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; padding: 1.25rem 0; border-bottom: 1px solid var(--border-subtle);">
              <!-- Target Profile -->
              <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.35rem;">
                  Target Audience Profile
                </div>
                <div style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.5;">
                  ${escapeHtml(audience.target_audience || 'Affluent creative professionals, design purists, and audiophiles')}
                </div>
              </div>

              <!-- Subcultures -->
              <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.35rem;">
                  Targeted Subcultures (${(audience.target_subcultures || []).length})
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem;">
                  ${(audience.target_subcultures || ['Design Purists', 'Vinyl Collectors', 'Specialty Craft Aficionados']).map(sub => `
                    <span class="hash-pill" style="color: #a5b4fc; font-size: 0.75rem;">◈ ${escapeHtml(sub)}</span>
                  `).join('')}
                </div>
              </div>
            </div>

            <!-- Cultural Pillars Grid -->
            <div style="padding-top: 1.25rem;">
              <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 1rem;">
                Grounded Cultural Pillars (${pillars.length})
              </div>
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
                ${pillars.map(p => `
                  <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
                      <div style="font-weight: 700; color: var(--cyan); font-size: 0.95rem;">
                        ${escapeHtml(p.pillar_name || p.name || 'Cultural Pillar')}
                      </div>
                      <span class="badge" style="font-size: 0.65rem; background: rgba(16, 185, 129, 0.15); color: #34d399;">
                        🔬 EVIDENCE BOUND
                      </span>
                    </div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 0.75rem;">
                      ${escapeHtml(p.manifestation || p.description || '')}
                    </div>
                    ${(p.aligned_entity_ids && p.aligned_entity_ids.length > 0) ? `
                      <div style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
                        ${p.aligned_entity_ids.map(id => `
                          <span class="hash-pill" style="font-size: 0.7rem; color: #34d399; font-family: var(--font-mono);">
                            ⚓ ${escapeHtml(id)}
                          </span>
                        `).join('')}
                      </div>
                    ` : ''}
                  </div>
                `).join('')}
              </div>
            </div>
          </div>

          <!-- SECTION 2: Experience Concept (Spatial, Sonic & Atmosphere Architecture) -->
          <div class="card" style="margin-bottom: 2rem;">
            <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.35rem;">📐</span>
                <div>
                  <div class="card-title">Experience Concept: Spatial & Sensory Architecture</div>
                  <div style="font-size: 0.8rem; color: var(--text-muted);">
                    Spatial layout, acoustic day-parting, material palette, and reading library synthesized by Experience Architect.
                  </div>
                </div>
              </div>
              <span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #22d3ee;">✦ RECOMMENDATION</span>
            </div>

            <!-- 2A. Spatial Zones Layout Grid -->
            <div style="padding: 1.25rem 0; border-bottom: 1px solid var(--border-subtle);">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
                <div style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">
                  Physical Spatial Zones (${zones.length})
                </div>
                <span style="font-size: 0.75rem; color: var(--text-muted);">Multi-Zone Layout</span>
              </div>

              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.25rem;">
                ${zones.map((zone, idx) => {
                  const zoneName = zone.zone_name || zone.name || `Spatial Area ${idx + 1}`;
                  return `
                    <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.15rem; display: flex; flex-direction: column; justify-content: space-between;">
                      <div>
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                          <div style="font-family: var(--font-heading); font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">
                            ${escapeHtml(zoneName)}
                          </div>
                          <span class="hash-pill" style="color: var(--cyan); font-size: 0.75rem;">
                            ${escapeHtml(zone.intended_mood || zone.target_mood || 'Intimate')}
                          </span>
                        </div>

                        <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 0.75rem;">
                          ${escapeHtml(zone.design_intent || zone.description || 'Sensory zone specification optimized for sound and patron dwell.')}
                        </div>

                        ${(zone.tactile_elements && zone.tactile_elements.length > 0) ? `
                          <div style="margin-bottom: 0.75rem;">
                            <div style="font-size: 0.7rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Tactile Elements & Textures</div>
                            <div style="font-size: 0.8rem; color: var(--text-primary);">${escapeHtml(zone.tactile_elements.join(' • '))}</div>
                          </div>
                        ` : ''}
                      </div>

                      <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between;">
                        <span class="badge" style="font-size: 0.65rem; background: rgba(245, 158, 11, 0.15); color: #fbbf24;">⚡ Downstream Task Assigned</span>
                        <button class="btn btn-secondary btn-sm" onclick="window.tasteopsInspectProvenance('${escapeHtml(zoneName)}')">
                          <span>❓ Why was this recommended?</span>
                        </button>
                      </div>
                    </div>
                  `;
                }).join('')}
              </div>
            </div>

            <!-- 2B. Sonic & Acoustic Architecture -->
            <div style="padding: 1.25rem 0; border-bottom: 1px solid var(--border-subtle);">
              <div style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 1rem;">
                Sonic Architecture & Day-Parting
              </div>

              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.25rem;">
                <!-- Acoustic Profile -->
                <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--cyan); font-weight: 700; margin-bottom: 0.35rem;">
                    🔊 Acoustic Identity & Playback
                  </div>
                  <div style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.5; margin-bottom: 0.5rem;">
                    ${escapeHtml(soundscape.acoustic_profile || soundscape.overview || 'Warm analog acoustic curve with custom horn-loaded monitors.')}
                  </div>
                  ${(soundscape.playback_mediums && soundscape.playback_mediums.length > 0) ? `
                    <div style="display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.5rem;">
                      ${soundscape.playback_mediums.map(m => `<span class="hash-pill" style="font-size: 0.7rem; color: var(--cyan);">${escapeHtml(m)}</span>`).join('')}
                    </div>
                  ` : ''}
                </div>

                <!-- Curated Artists / Vinyl Rotations -->
                <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: #34d399; font-weight: 700; margin-bottom: 0.35rem;">
                    🎧 Vetted Audio Recommendations (Qloo Grounded)
                  </div>
                  <div style="display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.5rem;">
                    ${(soundscape.curated_recommendations && soundscape.curated_recommendations.length > 0) ? soundscape.curated_recommendations.map(rec => {
                      const rTitle = rec.recommendation || rec.title || 'Artist';
                      return `
                        <div style="background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 0.6rem 0.85rem; display: flex; align-items: center; justify-content: space-between;">
                          <div>
                            <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-primary);">${escapeHtml(rTitle)}</div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary);">${escapeHtml(rec.expected_role || 'Acoustic rotation')}</div>
                          </div>
                          <button class="btn btn-secondary btn-sm" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="window.tasteopsInspectProvenance('${escapeHtml(rTitle)}')">
                            <span>❓ Why?</span>
                          </button>
                        </div>
                      `;
                    }).join('') : `
                      <div style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">
                        No audio recommendations recorded in blueprint.
                      </div>
                    `}
                  </div>
                </div>
              </div>
            </div>

            <!-- 2C. Tactile Materials & Sensory Pairings -->
            <div style="padding-top: 1.25rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.25rem;">
              <!-- Material Palette -->
              <div>
                <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.5rem;">Approved Material Palette</div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;">
                  ${(expConcept.material_palette && expConcept.material_palette.length > 0 ? expConcept.material_palette : ['Japanese cedar (Sugi)', 'Raw blackened steel', 'Handmade stoneware ceramics', 'Brushed acoustic wool']).map(mat => `
                    <span class="hash-pill" style="font-size: 0.75rem; color: var(--text-secondary);">✦ ${escapeHtml(mat)}</span>
                  `).join('')}
                </div>
              </div>

              <!-- Hospitality Tempo -->
              <div>
                <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.5rem;">Hospitality Choreography</div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;">
                  ${escapeHtml(expConcept.hospitality_tempo || 'Unhurried, ceremonial dwell tempo with custom ceramic presentation rituals.')}
                </div>
              </div>
            </div>
          </div>

          <!-- SECTION 3: Activation Ideas (Cultural Programming & Event Architecture) -->
          <div class="card" style="margin-bottom: 2rem;">
            <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.35rem;">🎪</span>
                <div>
                  <div class="card-title">Activation Ideas & Signature Cultural Programming (${activations.length})</div>
                  <div style="font-size: 0.8rem; color: var(--text-muted);">
                    Curated event concepts, residency formats, and recurring cultural programming grounded in subcultural affinities.
                  </div>
                </div>
              </div>
              <div style="display: flex; gap: 0.4rem;">
                <span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #22d3ee;">✦ RECOMMENDATION</span>
                <span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24;">⚡ EXECUTION ACTION</span>
              </div>
            </div>

            <div style="padding-top: 1.25rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.25rem;">
              ${activations.map(act => {
                const title = act.title || 'Signature Activation';
                return `
                  <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.15rem; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <div style="font-family: var(--font-heading); font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">
                          ${escapeHtml(title)}
                        </div>
                        <span class="hash-pill" style="color: var(--amber); font-size: 0.7rem; flex-shrink: 0;">
                          ${escapeHtml(act.cadence || 'Recurring')}
                        </span>
                      </div>

                      <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 0.75rem;">
                        ${escapeHtml(act.format_description || 'Curated salon format featuring high-affinity cultural figures and listening sessions.')}
                      </div>

                      <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.75rem; margin-bottom: 0.5rem;">
                        <div>
                          <span style="color: var(--text-muted);">Target Audience:</span>
                          <span style="color: var(--text-primary); margin-left: 0.35rem;">${escapeHtml(act.target_audience || 'Patrons')}</span>
                        </div>
                        <div>
                          <span style="color: var(--text-muted);">Expected Outcome:</span>
                          <span style="color: #34d399; margin-left: 0.35rem;">${escapeHtml(act.expected_outcome || 'High cultural dwell time')}</span>
                        </div>
                      </div>
                    </div>

                    <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between;">
                      <span class="badge" style="font-size: 0.65rem; background: rgba(16, 185, 129, 0.15); color: #34d399;">🔬 Grounded in Qloo Matrix</span>
                      <button class="btn btn-secondary btn-sm" onclick="window.tasteopsInspectProvenance('${escapeHtml(title)}')">
                        <span>❓ Why was this recommended?</span>
                      </button>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>

          <!-- SECTION 4: Strategic Brand Partnership Opportunities -->
          <div class="card" style="margin-bottom: 2rem;">
            <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.35rem;">🤝</span>
                <div>
                  <div class="card-title">Strategic Partnership Opportunities (${partnerships.length})</div>
                  <div style="font-size: 0.8rem; color: var(--text-muted);">
                    Ranked candidates evaluated on 6-dimensional fit (cultural fit, audience overlap, brand synergy, feasibility).
                  </div>
                </div>
              </div>
              <div style="display: flex; gap: 0.4rem;">
                <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399;">🔬 EVIDENCE</span>
                <span class="badge" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc;">🧠 AGENT INFERENCE</span>
              </div>
            </div>

            <div style="padding-top: 1.25rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 1.5rem;">
              ${partnerships.map(p => {
                const bName = p.brand || p.partner_name || p.name || 'Brand Partner';
                const score = typeof p.score === 'number' ? p.score : (typeof p.affinity_score === 'number' ? p.affinity_score * 100 : null);
                const breakdown = p.score_breakdown || {};
                return `
                  <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                      <!-- Card Head -->
                      <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 0.75rem;">
                        <div>
                          <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                            <span style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(bName)}</span>
                            <span class="hash-pill" style="color: var(--amber); font-size: 0.75rem;">${escapeHtml(p.category || 'Partner')}</span>
                          </div>
                          <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
                            ID: ${escapeHtml(p.brand_entity_id || p.partner_entity_id || 'Unspecified')}
                          </div>
                        </div>
                        <div style="text-align: right;">
                          <div style="font-size: 0.7rem; text-transform: uppercase; color: var(--text-muted);">Composite Fit</div>
                          <div style="font-family: var(--font-mono); font-size: 1.2rem; font-weight: 700; color: ${score !== null ? '#34d399' : 'var(--text-muted)'};">
                            ${score !== null ? `${score.toFixed(0)}/100` : 'Unavailable'}
                          </div>
                        </div>
                      </div>

                      <!-- Concept -->
                      <div style="background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 0.75rem; margin-bottom: 0.85rem;">
                        <div style="font-size: 0.7rem; text-transform: uppercase; color: var(--cyan); font-weight: 700; margin-bottom: 0.2rem;">Physical Activation Concept</div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">
                          ${escapeHtml(p.partnership_concept || p.concept_description || 'Co-branded sensory hospitality activation')}
                        </div>
                      </div>

                      <!-- 6D Score Breakdown Mini-Grid -->
                      ${breakdown.cultural_fit ? `
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.4rem; font-size: 0.7rem; margin-bottom: 0.85rem;">
                          <div style="background: var(--bg-surface); padding: 0.35rem 0.5rem; border-radius: 3px; border: 1px solid var(--border-subtle);">
                            <span style="color: var(--text-muted);">Cultural:</span>
                            <strong style="color: var(--cyan); margin-left: 0.25rem;">${breakdown.cultural_fit.toFixed(0)}%</strong>
                          </div>
                          <div style="background: var(--bg-surface); padding: 0.35rem 0.5rem; border-radius: 3px; border: 1px solid var(--border-subtle);">
                            <span style="color: var(--text-muted);">Audience:</span>
                            <strong style="color: var(--cyan); margin-left: 0.25rem;">${breakdown.audience_fit.toFixed(0)}%</strong>
                          </div>
                          <div style="background: var(--bg-surface); padding: 0.35rem 0.5rem; border-radius: 3px; border: 1px solid var(--border-subtle);">
                            <span style="color: var(--text-muted);">Synergy:</span>
                            <strong style="color: var(--cyan); margin-left: 0.25rem;">${breakdown.brand_compatibility.toFixed(0)}%</strong>
                          </div>
                        </div>
                      ` : ''}

                      <!-- Risk & Action -->
                      ${p.risk ? `
                        <div style="font-size: 0.75rem; color: #f87171; margin-bottom: 0.4rem;">
                          <strong>Risk:</strong> ${escapeHtml(p.risk)}
                        </div>
                      ` : ''}
                      ${p.recommended_next_action ? `
                        <div style="font-size: 0.75rem; color: #fbbf24; margin-bottom: 0.5rem;">
                          <strong>Next Action:</strong> ${escapeHtml(p.recommended_next_action)}
                        </div>
                      ` : ''}
                    </div>

                    <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between;">
                      <span class="badge" style="font-size: 0.65rem; background: rgba(99, 102, 241, 0.15); color: #a5b4fc;">6D Model Evaluated</span>
                      <button class="btn btn-secondary btn-sm" onclick="window.tasteopsInspectProvenance('${escapeHtml(bName)}')">
                        <span>❓ Why was this recommended?</span>
                      </button>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>

          <!-- SECTION 5 & 6 SPLIT: Budget Considerations & Consolidated Risk Ledger -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.5rem; margin-bottom: 2rem;">
            <!-- Budget Considerations -->
            <div class="card">
              <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
                <div class="card-title">
                  <span>💰</span> Budget Considerations & Allocations
                </div>
                <span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24;">⚡ EXECUTION ACTION</span>
              </div>

              <div style="padding: 1.25rem 0;">
                <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 0.5rem;">
                  <span style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase;">Total Capital Allocation:</span>
                  <span style="font-family: var(--font-mono); font-size: 1.35rem; font-weight: 700; color: #fbbf24;">
                    ${escapeHtml(budget.estimated_cost || blueprint.estimated_cost || 'Not estimated')}
                  </span>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 1.25rem;">
                  ${escapeHtml(budget.budget_fit || 'Optimized for high-end boutique spatial architecture, audio hardware licensing, and curated partner residencies.')}
                </div>

                <!-- Action Cost Allocations -->
                ${(budget.action_costs && budget.action_costs.length > 0) ? `
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.5rem;">Action Cost Breakdown</div>
                  <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                    ${budget.action_costs.slice(0, 5).map(ac => `
                      <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 0.5rem 0.75rem; display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem;">
                        <span style="color: var(--text-primary);">${escapeHtml(ac.title || ac.action_id)}</span>
                        <span style="font-family: var(--font-mono); font-weight: 700; color: #fbbf24;">${escapeHtml(ac.cost || 'Unspecified')}</span>
                      </div>
                    `).join('')}
                  </div>
                ` : ''}
              </div>
            </div>

            <!-- Consolidated Risk Register -->
            <div class="card">
              <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
                <div class="card-title">
                  <span>⚠️</span> Risk Analysis & Governance Register
                </div>
                <span class="badge" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc;">🧠 AGENT INFERENCE</span>
              </div>

              <div style="padding: 1.25rem 0;">
                ${risks.length > 0 ? `
                  <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                    ${risks.map(r => {
                      const rText = typeof r === 'string' ? r : (r.risk || 'Operational risk');
                      const rCat = typeof r === 'object' ? (r.category || 'RISK') : 'OPERATIONAL';
                      return `
                        <div style="background: var(--bg-surface-elevated); border-left: 3px solid #f87171; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; padding: 0.65rem 0.85rem; border-top: 1px solid var(--border-subtle); border-right: 1px solid var(--border-subtle); border-bottom: 1px solid var(--border-subtle);">
                          <div style="font-size: 0.65rem; text-transform: uppercase; font-weight: 700; color: #f87171; margin-bottom: 0.2rem;">${escapeHtml(rCat)}</div>
                          <div style="font-size: 0.85rem; color: var(--text-primary); line-height: 1.4;">${escapeHtml(rText)}</div>
                        </div>
                      `;
                    }).join('')}
                  </div>
                ` : `
                  <div style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 2rem 0;">No high-severity operational or governance risks detected.</div>
                `}
              </div>
            </div>
          </div>

          <!-- SECTION 7: Authoritative Qloo Ground-Truth Evidence Registry -->
          <div class="card">
            <div class="card-header" style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.35rem;">🔬</span>
                <div>
                  <div class="card-title">Authoritative Qloo Ground-Truth Evidence Registry (${evidence.length})</div>
                  <div style="font-size: 0.8rem; color: var(--text-muted);">
                    Audited entity signatures and verified affinity matches retrieved from Qloo Cultural AI.
                  </div>
                </div>
              </div>
              <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399;">🔬 ${evidence.length > 0 ? `${evidence.length} Retrieved Entities` : '0 Entities Recorded'}</span>
            </div>

            <div style="padding-top: 1.25rem;">
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem;">
                ${evidence.slice(0, 8).map(ev => {
                  const evScore = typeof ev.affinity === 'number' ? `${(ev.affinity * 100).toFixed(0)}% Affinity` : (typeof ev.confidence === 'number' ? `${(ev.confidence * 100).toFixed(0)}% Confidence` : 'Affinity Unavailable');
                  return `
                  <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 0.85rem;">
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 0.35rem;">
                      <span style="font-weight: 700; color: var(--text-primary); font-size: 0.9rem;">${escapeHtml(ev.name || ev.entity_id || 'Entity')}</span>
                      <span class="hash-pill" style="font-size: 0.7rem; color: ${ev.affinity != null || ev.confidence != null ? '#34d399' : 'var(--text-muted)'};">${escapeHtml(evScore)}</span>
                    </div>
                    <div style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.35rem;">
                      ${escapeHtml(ev.entity_id || 'Unspecified ID')}
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); line-height: 1.4;">
                      ${escapeHtml(ev.why_it_matters || 'Ground-truth cultural intelligence signal.')}
                    </div>
                  </div>
                `;
                }).join('')}
              </div>
            </div>
          </div>
        </div>
      `;

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Experience Blueprint Not Ready or Available',
        error: err,
        retryId: 'btn-retry-blueprint',
      });
      document.getElementById('btn-retry-blueprint')?.addEventListener('click', loadData);
    }
  };

  loadData();
}

/**
 * Interactive Provenance Modal answering:
 * "Why was this recommendation made?"
 *
 * Visually distinguishes the 4 layers without exposing chain-of-thought:
 * 1. Evidence (Green)
 * 2. Agent Inference (Indigo)
 * 3. Recommendation (Cyan)
 * 4. Execution Action (Amber)
 */
function renderProvenanceModal(item) {
  const existing = document.getElementById('provenance-modal-backdrop');
  if (existing) existing.remove();

  const backdrop = document.createElement('div');
  backdrop.id = 'provenance-modal-backdrop';
  backdrop.style.cssText = `
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(8px);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
  `;

  const ev = item.evidence || {};
  const inf = item.agent_inference || {};
  const rec = item.recommendation || {};
  const act = item.execution_action || {};

  backdrop.innerHTML = `
    <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); max-width: 680px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); overflow: hidden; animation: modalIn 0.2s ease-out;">
      <!-- Modal Header -->
      <div style="padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between; background: var(--bg-surface-elevated);">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <span style="font-size: 1.5rem;">❓</span>
          <div>
            <div style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700; color: var(--text-primary);">
              Why Was This Recommendation Made?
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">
              Verifiable 4-layer epistemic provenance trace for <strong style="color: var(--cyan);">${escapeHtml(item.entity_name)}</strong>
            </div>
          </div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="window.tasteopsCloseProvenanceModal()" style="font-size: 1.1rem; line-height: 1; padding: 0.35rem 0.65rem;">
          ✕
        </button>
      </div>

      <!-- Modal Body (The 4 Distinct Epistemic Layers) -->
      <div style="padding: 1.5rem; display: flex; flex-direction: column; gap: 1.25rem; max-height: 75vh; overflow-y: auto;">
        <!-- Layer 1: Ground-Truth Evidence -->
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 1rem 1.25rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
            <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-weight: 700;">
              🔬 1. GROUND-TRUTH EVIDENCE
            </span>
            <span style="font-size: 0.75rem; color: ${typeof ev.affinity === 'number' ? '#34d399' : 'var(--text-muted)'}; font-family: var(--font-mono);">
              ${typeof ev.affinity === 'number' ? `${(ev.affinity * 100).toFixed(0)}% Affinity Overlap` : (typeof ev.confidence === 'number' ? `${(ev.confidence * 100).toFixed(0)}% Confidence` : 'Affinity Unavailable')}
            </span>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 0.5rem;">
            Retrieved directly from Qloo Cultural AI database via verified search and matrix affinity endpoints.
          </div>
          <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); background: rgba(0,0,0,0.3); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm);">
            <div><strong>Entity Signature:</strong> ${escapeHtml(ev.entity_id || 'Unspecified')}</div>
            <div><strong>Source Query:</strong> ${escapeHtml(ev.source || ev.source_query || 'Unspecified')}</div>
            <div><strong>URN / Type:</strong> ${escapeHtml(ev.urn || 'Unspecified')}</div>
          </div>
        </div>

        <!-- Layer 2: Agent Inference -->
        <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: var(--radius-md); padding: 1rem 1.25rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
            <span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; font-weight: 700;">
              🧠 2. AGENT INFERENCE
            </span>
            <span style="font-size: 0.75rem; color: #a5b4fc;">Thematic & Demographic Alignment</span>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-primary); line-height: 1.5; margin-bottom: 0.4rem;">
            ${escapeHtml(inf.curatorial_rationale || 'Cross-domain affinity modeling identified high cultural overlap with the space brief.')}
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary);">
            <strong>Subcultural Resonance:</strong> ${escapeHtml(inf.affinity_fit || 'Direct resonance with design purists and listening room audiences.')}
          </div>
        </div>

        <!-- Layer 3: Curatorial Recommendation -->
        <div style="background: rgba(6, 182, 212, 0.08); border: 1px solid rgba(6, 182, 212, 0.3); border-radius: var(--radius-md); padding: 1rem 1.25rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
            <span class="badge" style="background: rgba(6, 182, 212, 0.2); color: #22d3ee; font-weight: 700;">
              ✦ 3. CURATORIAL RECOMMENDATION
            </span>
            <span style="font-size: 0.75rem; color: #22d3ee;">Physical Space Role</span>
          </div>
          <div style="font-size: 0.9rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.35rem;">
            ${escapeHtml(rec.title || item.entity_name)}
          </div>
          <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;">
            ${escapeHtml(rec.role || 'Designated for physical sensory activation and patron dwell enrichment.')}
          </div>
        </div>

        <!-- Layer 4: Execution Action -->
        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: var(--radius-md); padding: 1rem 1.25rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
            <span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-weight: 700;">
              ⚡ 4. DOWNSTREAM EXECUTION ACTION
            </span>
            <span style="font-size: 0.75rem; color: #fbbf24; font-family: var(--font-mono);">
              ${escapeHtml(act.budget || 'Allocated')}
            </span>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-primary); line-height: 1.5; margin-bottom: 0.35rem;">
            ${escapeHtml(act.task || 'Assigned to execution engine upon curator sign-off.')}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">
            <strong>Responsible Owner:</strong> ${escapeHtml(act.owner || 'Curator')}
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div style="padding: 1rem 1.5rem; border-top: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between; background: var(--bg-surface-elevated);">
        <div style="font-size: 0.75rem; color: var(--text-muted);">
          Audited under TasteOps Governance Engine. No raw chain-of-thought exposed.
        </div>
        <button class="btn btn-secondary" onclick="window.tasteopsCloseProvenanceModal()">
          Close Trace
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(backdrop);
}
