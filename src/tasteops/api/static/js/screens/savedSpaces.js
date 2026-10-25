/**
 * TasteOps Saved Spaces Catalog Screen (Route: /saved-spaces)
 * Displays active and archived curated spaces with affinity scores and direct activation triggers.
 */

import { apiClient } from '../apiClient.js';

export async function renderSavedSpaces(rootElement, params, router) {
  rootElement.innerHTML = `
    <div class="main-content" style="max-width: 1400px; margin: 0 auto;">
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 2.25rem;">
        <div>
          <div class="hero-eyebrow">PORTFOLIO ARCHIVE</div>
          <h1 class="hero-title" style="font-size: 2.4rem; margin-bottom: 0.5rem;">Saved Spaces</h1>
          <p class="hero-desc" style="max-width: 780px;">
            Your curated physical environments across hospitality, retail, and commercial developments.
          </p>
        </div>
        <div>
          <a href="/create-space" class="btn btn-primary" style="text-decoration: none;">
            <span>+ Curate New Space</span>
          </a>
        </div>
      </div>

      <!-- Spaces Grid -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 1.75rem; margin-bottom: 2.5rem;">
        
        <!-- Space 1: Austin Co-working Hub -->
        <div class="card" style="padding: 2.25rem; display: flex; flex-direction: column;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
            <div>
              <span class="status-badge status-completed" style="font-size: 0.72rem; margin-bottom: 0.5rem;">Active Activation</span>
              <h3 style="font-family: var(--font-serif); font-size: 1.35rem; color: var(--forest-green); margin: 0.25rem 0 0 0;">
                Austin Co-working Hub
              </h3>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">Austin, USA • 100–500 occupants</div>
            </div>
            <div style="text-align: right;">
              <span style="font-family: var(--font-serif); font-size: 1.5rem; color: var(--forest-green); font-weight: 700;">87%</span>
              <div style="font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted);">Affinity</div>
            </div>
          </div>

          <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 1.5rem;">
            Tech & indie film demographic who value brutalist architecture, specialty coffee, and ambient day-parted soundscapes.
          </p>

          <div style="display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 1.5rem;">
            <span class="entity-pill">Khruangbin</span>
            <span class="entity-pill">Aesop</span>
            <span class="entity-pill">Gestalten</span>
            <span class="entity-pill">Kinfolk</span>
          </div>

          <div style="margin-top: auto; padding-top: 1.25rem; border-top: 1px solid var(--warm-stone-light); display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 0.75rem; color: var(--text-muted);">Last sync: Today, 14:42</span>
            <a href="/home" class="btn btn-secondary" style="padding: 0.4rem 0.85rem; font-size: 0.75rem; text-decoration: none;">
              Open Workspace
            </a>
          </div>
        </div>

        <!-- Space 2: Shibuya Vinyl Listening Room -->
        <div class="card" style="padding: 2.25rem; display: flex; flex-direction: column;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
            <div>
              <span class="status-badge status-completed" style="font-size: 0.72rem; margin-bottom: 0.5rem;">Active Activation</span>
              <h3 style="font-family: var(--font-serif); font-size: 1.35rem; color: var(--forest-green); margin: 0.25rem 0 0 0;">
                Shibuya Listening Lounge
              </h3>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">Tokyo, Japan • 50–100 occupants</div>
            </div>
            <div style="text-align: right;">
              <span style="font-family: var(--font-serif); font-size: 1.5rem; color: var(--forest-green); font-weight: 700;">94%</span>
              <div style="font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted);">Affinity</div>
            </div>
          </div>

          <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 1.5rem;">
            High-fidelity listening bar combining vintage McIntosh amplifiers, natural biodynamic wines, and contemporary Japanese ceramics.
          </p>

          <div style="display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 1.5rem;">
            <span class="entity-pill">Ryuichi Sakamoto</span>
            <span class="entity-pill">Teenage Engineering</span>
            <span class="entity-pill">Monocle</span>
          </div>

          <div style="margin-top: auto; padding-top: 1.25rem; border-top: 1px solid var(--warm-stone-light); display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 0.75rem; color: var(--text-muted);">Last sync: Yesterday</span>
            <a href="/home" class="btn btn-secondary" style="padding: 0.4rem 0.85rem; font-size: 0.75rem; text-decoration: none;">
              Open Workspace
            </a>
          </div>
        </div>

        <!-- Space 3: SoHo Concept Hotel & Gallery -->
        <div class="card" style="padding: 2.25rem; display: flex; flex-direction: column;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
            <div>
              <span class="status-badge status-waiting" style="font-size: 0.72rem; margin-bottom: 0.5rem;">In Governance Review</span>
              <h3 style="font-family: var(--font-serif); font-size: 1.35rem; color: var(--forest-green); margin: 0.25rem 0 0 0;">
                SoHo Concept Hotel & Lounge
              </h3>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">New York, USA • 200–500 occupants</div>
            </div>
            <div style="text-align: right;">
              <span style="font-family: var(--font-serif); font-size: 1.5rem; color: var(--forest-green); font-weight: 700;">89%</span>
              <div style="font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted);">Affinity</div>
            </div>
          </div>

          <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 1.5rem;">
            Boutique hospitality lobby featuring cast-iron architectural elements, independent fashion monographs, and artisanal tea service.
          </p>

          <div style="display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 1.5rem;">
            <span class="entity-pill">Kiasmos</span>
            <span class="entity-pill">Le Labo</span>
            <span class="entity-pill">Rizzoli Books</span>
          </div>

          <div style="margin-top: auto; padding-top: 1.25rem; border-top: 1px solid var(--warm-stone-light); display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 0.75rem; color: var(--text-muted);">Awaiting Approval</span>
            <a href="/execution-plan" class="btn btn-secondary" style="padding: 0.4rem 0.85rem; font-size: 0.75rem; text-decoration: none;">
              Review Plan
            </a>
          </div>
        </div>

      </div>
    </div>
  `;
}
