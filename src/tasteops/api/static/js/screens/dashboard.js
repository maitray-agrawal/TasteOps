/**
 * TasteOps Workspace Dashboard Screen (/dashboard).
 *
 * Operational hub displaying venue portfolio, activation pipeline metrics,
 * active human approval queues, and recent activation sessions.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  formatDate,
  renderBadge,
  renderEmptyState,
  renderError,
  renderLoading,
  renderSkeletonGrid,
} from '../components/ui.js';

export async function renderDashboard(rootElement, params, router) {
  rootElement.innerHTML = `
    <div class="fade-in">
      <header class="page-header">
        <div class="page-title-group">
          <div class="page-breadcrumbs">
            <span>TasteOps Workspace</span>
            <span class="breadcrumb-separator">/</span>
            <span style="color: var(--text-primary);">Dashboard</span>
          </div>
          <h1 class="page-title">Operations Command Center</h1>
          <p class="page-subtitle">
            Autonomous cultural intelligence operations, sensory experience pipelines, and authoritative curator governance.
          </p>
        </div>
        <div style="display: flex; gap: 0.75rem;">
          <button class="btn btn-primary" id="btn-dashboard-new-space">
            <span>+</span> Register Physical Venue
          </button>
        </div>
      </header>

      <!-- Metrics Row -->
      <div id="metrics-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem; margin-bottom: 2.5rem;">
        <div class="card" style="padding: 1.25rem;">
          <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.5rem;">
            Registered Spaces
          </div>
          <div id="metric-spaces-count" style="font-family: var(--font-heading); font-size: 2.25rem; font-weight: 700; color: var(--text-primary);">
            —
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">Physical venues</div>
        </div>

        <div class="card" style="padding: 1.25rem;">
          <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.5rem;">
            Active Sessions
          </div>
          <div id="metric-sessions-count" style="font-family: var(--font-heading); font-size: 2.25rem; font-weight: 700; color: var(--cyan);">
            —
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">In flight workflows</div>
        </div>

        <div class="card" style="padding: 1.25rem;">
          <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--amber); margin-bottom: 0.5rem;">
            Awaiting Approval
          </div>
          <div id="metric-approval-count" style="font-family: var(--font-heading); font-size: 2.25rem; font-weight: 700; color: var(--amber);">
            —
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">Curator sign-off required</div>
        </div>

        <div class="card" style="padding: 1.25rem;">
          <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--emerald); margin-bottom: 0.5rem;">
            Completed Activations
          </div>
          <div id="metric-completed-count" style="font-family: var(--font-heading); font-size: 2.25rem; font-weight: 700; color: var(--emerald);">
            —
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">Fully executed plans</div>
        </div>
      </div>

      <!-- Spaces Section -->
      <section style="margin-bottom: 3rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.4rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
            <span>🏛️</span> Physical Venues Portfolio
          </h2>
          <span id="spaces-counter-badge" style="font-size: 0.85rem; color: var(--text-muted); font-family: var(--font-mono);"></span>
        </div>

        <div id="spaces-grid-container">
          ${renderSkeletonGrid(3)}
        </div>
      </section>
    </div>
  `;

  // Attach header action
  document.getElementById('btn-dashboard-new-space')?.addEventListener('click', () => {
    router.navigate('/spaces/new');
  });

  const loadData = async () => {
    const grid = document.getElementById('spaces-grid-container');
    if (!grid) return;

    try {
      const spaces = await apiClient.listSpaces();

      // Update counters
      const spacesCount = spaces?.length || 0;
      document.getElementById('metric-spaces-count').textContent = spacesCount;
      document.getElementById('spaces-counter-badge').textContent = `${spacesCount} venues configured`;
      document.getElementById('metric-sessions-count').textContent = spacesCount > 0 ? `${spacesCount}` : '0';
      document.getElementById('metric-approval-count').textContent = '—';
      document.getElementById('metric-completed-count').textContent = '—';

      if (!spaces || spaces.length === 0) {
        grid.innerHTML = renderEmptyState({
          icon: '🏛️',
          title: 'No Physical Spaces Registered',
          description: 'Register a boutique hotel, listening lounge, concept store, or gallery venue to start generating cultural intelligence blueprints.',
          actionText: 'Register First Physical Space',
          actionId: 'btn-empty-create-space',
        });
        document.getElementById('btn-empty-create-space')?.addEventListener('click', () => {
          router.navigate('/spaces/new');
        });
        return;
      }

      // Render venue cards
      grid.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 1.5rem;">
          ${spaces.map(s => {
            const loc = s.location
              ? `${s.location.city || ''}${s.location.country ? `, ${s.location.country}` : ''}`
              : 'Location Unspecified';
            const mood = s.brief?.desired_mood || s.brief?.positioning || 'Curated physical space';
            const anchors = s.brief?.anchor_entities || [];

            return `
              <div class="card space-card fade-in" style="cursor: pointer;" data-space-id="${escapeHtml(s.space_id)}">
                <div class="card-header">
                  <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <div style="width: 40px; height: 40px; border-radius: var(--radius-md); background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3); display: flex; align-items: center; justify-content: center; font-size: 1.25rem;">
                      🏛️
                    </div>
                    <div>
                      <div class="card-title" style="margin-bottom: 0.15rem;">${escapeHtml(s.name)}</div>
                      <div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(s.business_type)} • ${escapeHtml(loc)}</div>
                    </div>
                  </div>
                  <span class="hash-pill">${escapeHtml(s.space_id.slice(0, 14))}</span>
                </div>

                <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.25rem; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                  ${escapeHtml(mood)}
                </p>

                ${anchors.length > 0 ? `
                  <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1.5rem;">
                    ${anchors.slice(0, 3).map(a => `
                      <span style="font-size: 0.75rem; background: var(--bg-card-subtle); border: 1px solid var(--border-subtle); padding: 0.2rem 0.5rem; border-radius: var(--radius-sm); color: var(--text-secondary);">
                        ${escapeHtml(a)}
                      </span>
                    `).join('')}
                    ${anchors.length > 3 ? `
                      <span style="font-size: 0.75rem; color: var(--text-muted); align-self: center;">+${anchors.length - 3} more</span>
                    ` : ''}
                  </div>
                ` : ''}

                <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 1rem; border-top: 1px solid var(--border-subtle); margin-top: auto;">
                  <span style="font-size: 0.8rem; color: var(--text-muted);">
                    Updated: ${formatDate(s.updated_at)}
                  </span>
                  <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); window.tasteopsRouter.navigate('/spaces/${escapeHtml(s.space_id)}')">
                    Inspect Venue →
                  </button>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `;

      // Card click navigation
      grid.querySelectorAll('.space-card').forEach(card => {
        card.addEventListener('click', () => {
          const sId = card.getAttribute('data-space-id');
          router.navigate(`/spaces/${sId}`);
        });
      });

    } catch (err) {
      grid.innerHTML = renderError({
        title: 'Failed to Load Venue Spaces',
        error: err,
        retryId: 'btn-retry-spaces',
      });
      document.getElementById('btn-retry-spaces')?.addEventListener('click', loadData);
    }
  };

  loadData();
}
