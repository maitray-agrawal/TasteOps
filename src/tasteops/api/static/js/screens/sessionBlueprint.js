/**
 * TasteOps Architectural & Sensory Blueprint Screen (/sessions/[sessionId]/blueprint).
 *
 * Inspects spatial zone layouts, day-parting sonic identities, circadian lighting,
 * brand partnership recommendations, signature programming, and cryptographic plan hashes.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  renderError,
  renderLoading,
  renderSubNav,
} from '../components/ui.js';

export async function renderSessionBlueprint(rootElement, params, router) {
  const sessionId = params.sessionId;
  if (!sessionId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="blueprint-container">
      ${renderLoading('Extracting architectural blueprint & sensory parameters...')}
    </div>
  `;

  const container = document.getElementById('blueprint-container');

  const loadData = async () => {
    try {
      const blueprint = await apiClient.getSessionBlueprint(sessionId);
      const zones = blueprint.spatial_zones || [];
      const soundscape = blueprint.soundscape_design || {};
      const lighting = blueprint.lighting_design || {};
      const partnerships = blueprint.partnerships || [];
      const programming = blueprint.programming_calendar || [];
      const pillars = blueprint.cultural_pillars || [];

      container.innerHTML = `
        <div class="fade-in">
          <header class="page-header" style="margin-bottom: 1.5rem;">
            <div class="page-title-group">
              <div class="page-breadcrumbs">
                <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                <span class="breadcrumb-separator">/</span>
                <a href="/sessions/${escapeHtml(sessionId)}" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}');">Session</a>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-primary);">Architectural Blueprint</span>
              </div>
              <h1 class="page-title">Experience & Sensory Blueprint</h1>
              <p class="page-subtitle">
                Synthesized multi-zone physical layout, sonic curation, circadian lighting, and brand partnership specifications.
              </p>
            </div>

            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span class="hash-pill" title="Cryptographic Plan Hash">
                🔒 ${escapeHtml((blueprint.plan_hash || '').slice(0, 16))}...
              </span>
            </div>
          </header>

          <!-- Sub-navigation Tabs -->
          ${renderSubNav(sessionId, 'blueprint')}

          <!-- Cultural Pillars & Narrative -->
          ${pillars.length > 0 || blueprint.experience_narrative ? `
            <div class="card" style="margin-bottom: 2rem;">
              <div class="card-header">
                <div class="card-title">
                  <span>🏛️</span> Cultural Narrative & Strategic Pillars
                </div>
              </div>
              ${blueprint.experience_narrative ? `
                <p style="font-size: 1.05rem; color: var(--text-primary); line-height: 1.6; margin-bottom: 1.5rem;">
                  "${escapeHtml(blueprint.experience_narrative)}"
                </p>
              ` : ''}
              ${pillars.length > 0 ? `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
                  ${pillars.map(p => `
                    <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                      <div style="font-weight: 600; color: var(--cyan); margin-bottom: 0.25rem;">${escapeHtml(p.pillar_name || p.name || 'Pillar')}</div>
                      <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;">${escapeHtml(p.manifestation || p.description || '')}</div>
                    </div>
                  `).join('')}
                </div>
              ` : ''}
            </div>
          ` : ''}

          <!-- Spatial Zones Layout Grid -->
          <section style="margin-bottom: 2.5rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem;">
              <h2 style="font-family: var(--font-heading); font-size: 1.35rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
                <span>📐</span> Physical Spatial Zones (${zones.length})
              </h2>
            </div>

            ${zones.length > 0 ? `
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 1.5rem;">
                ${zones.map((zone, idx) => `
                  <div class="card">
                    <div class="card-header">
                      <div class="card-title">
                        <span>Zone ${idx + 1}:</span> ${escapeHtml(zone.zone_name || zone.name || 'Spatial Area')}
                      </div>
                      <span class="hash-pill">${escapeHtml(zone.target_mood || 'Intimate')}</span>
                    </div>

                    <div style="margin-bottom: 1rem;">
                      <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Design Intent</div>
                      <p style="font-size: 0.9rem; color: var(--text-secondary); line-height: 1.5;">${escapeHtml(zone.design_intent || zone.description || 'Sensory zone specification')}</p>
                    </div>

                    ${zone.acoustic_treatment || zone.sound_profile ? `
                      <div style="margin-bottom: 0.75rem; background: var(--bg-surface-elevated); padding: 0.65rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--cyan); font-weight: 600; margin-bottom: 0.2rem;">🔊 Acoustics</div>
                        <div style="font-size: 0.85rem; color: var(--text-primary);">${escapeHtml(zone.acoustic_treatment || zone.sound_profile || '')}</div>
                      </div>
                    ` : ''}

                    ${zone.lighting_guidelines || zone.lighting ? `
                      <div style="margin-bottom: 0.75rem; background: var(--bg-surface-elevated); padding: 0.65rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--amber); font-weight: 600; margin-bottom: 0.2rem;">💡 Lighting</div>
                        <div style="font-size: 0.85rem; color: var(--text-primary);">${escapeHtml(typeof zone.lighting_guidelines === 'object' ? JSON.stringify(zone.lighting_guidelines) : (zone.lighting_guidelines || zone.lighting || ''))}</div>
                      </div>
                    ` : ''}

                    ${zone.materiality || zone.materials ? `
                      <div style="margin-top: 0.75rem;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Materiality & Textures</div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(zone.materiality || zone.materials || '')}</div>
                      </div>
                    ` : ''}
                  </div>
                `).join('')}
              </div>
            ` : `
              <div class="empty-state">
                <div class="empty-state-icon">📐</div>
                <h3>No Spatial Zones Formatted</h3>
                <p>Zones will populate once the Experience Architect completes synthesis.</p>
              </div>
            `}
          </section>

          <!-- Soundscape & Lighting Split -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 2.5rem;">
            <!-- Sonic Identity -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>🎧</span> Sonic Identity & Day-parting
                </div>
              </div>

              <div style="margin-bottom: 1rem;">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Acoustic Philosophy</div>
                <div style="font-size: 0.95rem; color: var(--text-primary); line-height: 1.5;">
                  ${escapeHtml(soundscape.acoustic_philosophy || soundscape.genre_palette || 'Analog warm listening acoustics with custom horn-loaded monitors.')}
                </div>
              </div>

              ${soundscape.day_parting ? `
                <div style="display: flex; flex-direction: column; gap: 0.6rem; margin-top: 1rem;">
                  ${Object.entries(soundscape.day_parting).map(([part, desc]) => `
                    <div style="background: var(--bg-surface-elevated); padding: 0.65rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
                      <span style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: var(--cyan);">${escapeHtml(part)}</span>
                      <span style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(typeof desc === 'object' ? JSON.stringify(desc) : desc)}</span>
                    </div>
                  `).join('')}
                </div>
              ` : ''}
            </div>

            <!-- Brand Partnerships -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>🤝</span> Strategic Brand Partnerships (${partnerships.length})
                </div>
              </div>

              ${partnerships.length > 0 ? `
                <div style="display: flex; flex-direction: column; gap: 0.85rem;">
                  ${partnerships.map(p => `
                    <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 0.85rem;">
                      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.25rem;">
                        <span style="font-weight: 600; color: var(--text-primary);">${escapeHtml(p.brand_name || p.name || 'Partner')}</span>
                        <span class="hash-pill" style="color: var(--amber);">${escapeHtml(p.category || 'Lifestyle')}</span>
                      </div>
                      <div style="font-size: 0.825rem; color: var(--text-secondary); line-height: 1.4;">
                        ${escapeHtml(p.activation_concept || p.rationale || 'High-affinity co-branded sensory activation')}
                      </div>
                    </div>
                  `).join('')}
                </div>
              ` : `
                <div style="color: var(--text-muted); padding: 1.5rem 0; text-align: center;">Partnerships pending alignment review.</div>
              `}
            </div>
          </div>
        </div>
      `;

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Blueprint Not Ready or Available',
        error: err,
        retryId: 'btn-retry-blueprint',
      });
      document.getElementById('btn-retry-blueprint')?.addEventListener('click', loadData);
    }
  };

  loadData();
}
