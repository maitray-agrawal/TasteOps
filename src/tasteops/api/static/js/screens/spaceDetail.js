/**
 * TasteOps Space Detail & Analysis Trigger Screen (/spaces/[spaceId]).
 *
 * Inspects venue brief specifications, anchor entities, and provides the
 * operational trigger to launch autonomous cultural activation pipelines.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  formatDate,
  renderBadge,
  renderError,
  renderLoading,
  showToast,
} from '../components/ui.js';

export async function renderSpaceDetail(rootElement, params, router) {
  const spaceId = params.spaceId;
  if (!spaceId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="space-detail-container">
      ${renderLoading('Loading space configuration...')}
    </div>
  `;

  const container = document.getElementById('space-detail-container');

  const loadData = async () => {
    try {
      const space = await apiClient.getSpace(spaceId);
      const brief = space.brief || {};
      const loc = space.location
        ? `${space.location.city || ''}${space.location.country ? `, ${space.location.country}` : ''}`
        : 'Location Unspecified';
      const anchors = brief.anchor_entities || [];

      // Synthesize natural intent from brief
      const defaultIntentParts = [
        `Venue concept: ${space.name}`,
        `Type: ${space.business_type}`,
      ];
      if (brief.desired_mood) defaultIntentParts.push(`Atmosphere: ${brief.desired_mood}`);
      if (brief.target_audience) defaultIntentParts.push(`Target audience: ${brief.target_audience}`);
      if (brief.positioning) defaultIntentParts.push(`Positioning: ${brief.positioning}`);
      if (anchors.length > 0) defaultIntentParts.push(`Anchors: ${anchors.join(', ')}`);
      const defaultUserIntent = defaultIntentParts.join('. ') + '.';

      container.innerHTML = `
        <div class="fade-in">
          <header class="page-header">
            <div class="page-title-group">
              <div class="page-breadcrumbs">
                <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-muted);">Spaces</span>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-primary);">${escapeHtml(space.name)}</span>
              </div>
              <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                <span>${escapeHtml(space.name)}</span>
                <span class="badge badge-approved" style="font-size: 0.85rem;">Active Venue</span>
              </h1>
              <p class="page-subtitle">
                ${escapeHtml(space.business_type)} • ${escapeHtml(loc)}
              </p>
            </div>

            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span class="hash-pill" title="Physical Space Identifier">${escapeHtml(space.space_id)}</span>
            </div>
          </header>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 3rem;">
            <!-- Left Column: Venue Brief Specifications -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>📋</span> Spatial & Cultural Brief
                </div>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.25rem;">
                  Desired Atmosphere & Mood
                </div>
                <div style="font-size: 1rem; color: var(--text-primary); line-height: 1.5;">
                  ${escapeHtml(brief.desired_mood || 'Not specified')}
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.25rem;">
                <div>
                  <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.25rem;">
                    Target Audience
                  </div>
                  <div style="color: var(--text-primary); font-size: 0.95rem;">
                    ${escapeHtml(brief.target_audience || 'General cultural audience')}
                  </div>
                </div>

                <div>
                  <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.25rem;">
                    Positioning Statement
                  </div>
                  <div style="color: var(--text-primary); font-size: 0.95rem;">
                    ${escapeHtml(brief.positioning || 'Curated physical hospitality')}
                  </div>
                </div>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.5rem;">
                  Cultural Anchor Entities (${anchors.length})
                </div>
                ${anchors.length > 0 ? `
                  <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;">
                    ${anchors.map(a => `
                      <span style="font-size: 0.8rem; background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 0.25rem 0.6rem; border-radius: var(--radius-sm); color: var(--cyan);">
                        ✦ ${escapeHtml(a)}
                      </span>
                    `).join('')}
                  </div>
                ` : `
                  <div style="font-size: 0.85rem; color: var(--text-muted);">No anchor entities specified.</div>
                `}
              </div>

              ${brief.budget || (brief.constraints && Object.keys(brief.constraints).length > 0) ? `
                <div style="padding-top: 1rem; border-top: 1px solid var(--border-subtle); display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                  ${brief.budget ? `
                    <div>
                      <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Budget</div>
                      <div style="color: var(--amber); font-weight: 600;">${escapeHtml(brief.budget)}</div>
                    </div>
                  ` : ''}
                  ${brief.constraints ? `
                    <div>
                      <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Constraints</div>
                      <div style="color: var(--text-secondary); font-size: 0.85rem;">
                        ${escapeHtml(typeof brief.constraints === 'object' ? JSON.stringify(brief.constraints) : brief.constraints)}
                      </div>
                    </div>
                  ` : ''}
                </div>
              ` : ''}
            </div>

            <!-- Right Column: Launch Cultural Intelligence Analysis -->
            <div class="card elevated" style="border-color: rgba(99, 102, 241, 0.3);">
              <div class="card-header">
                <div class="card-title" style="color: var(--cyan);">
                  <span>⚡</span> Launch Activation Pipeline
                </div>
                <span class="badge badge-in-progress">Autonomous FSM</span>
              </div>

              <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.5rem; line-height: 1.5;">
                Initiates cultural intelligence extraction via MCP, resolves high-affinity multidimensional matrices, runs specialized domain agents, constructs sensory zones, and pauses deterministically at the human curator approval gate.
              </p>

              <div id="analyze-error-container"></div>

              <form id="form-trigger-analysis">
                <div class="form-group">
                  <label class="form-label" for="input-custom-intent">
                    Operational Activation Concept & Input
                  </label>
                  <textarea id="input-custom-intent" class="form-textarea" style="min-height: 120px;" required>${escapeHtml(defaultUserIntent)}</textarea>
                  <div class="form-hint">Natural language concept driving cultural twin synthesis.</div>
                </div>

                <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 1rem; border-top: 1px solid var(--border-subtle);">
                  <div style="font-size: 0.8rem; color: var(--text-muted);">
                    Stops deterministically at <strong style="color: var(--amber);">Approval Gate</strong>
                  </div>
                  <button type="submit" class="btn btn-primary btn-lg" id="btn-start-analysis">
                    <span>⚡ Run Cultural Analysis</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      `;

      // Handle Analysis form trigger
      const form = document.getElementById('form-trigger-analysis');
      const analyzeBtn = document.getElementById('btn-start-analysis');
      const errBox = document.getElementById('analyze-error-container');

      form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        errBox.innerHTML = '';
        const userIntent = document.getElementById('input-custom-intent').value.trim();

        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = `
          <div style="display: inline-block; width: 16px; height: 16px; border: 2px solid white; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 0.5rem;"></div>
          <span>Driving Workflow Engine...</span>
        `;

        try {
          const session = await apiClient.analyzeSpace(spaceId, {
            user_input: userIntent,
            auto_run: true,
          });
          showToast(`Workflow Session '${session.session_id.slice(0, 8)}' reached Approval Gate!`, 'success');
          router.navigate(`/sessions/${session.session_id}`);
        } catch (err) {
          analyzeBtn.disabled = false;
          analyzeBtn.innerHTML = '<span>⚡ Run Cultural Analysis</span>';
          errBox.innerHTML = renderError({
            title: 'Analysis Pipeline Failed',
            error: err,
            retryId: 'btn-retry-analysis',
          });
        }
      });

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Failed to Load Space',
        error: err,
        retryId: 'btn-retry-space-detail',
      });
      document.getElementById('btn-retry-space-detail')?.addEventListener('click', loadData);
    }
  };

  loadData();
}
