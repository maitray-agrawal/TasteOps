/**
 * TasteOps Execution Plan & Governance Screen (Route: /execution-plan)
 * Sections 15 & 16: 4 Artifact cards, Human-in-the-loop Governance checklist,
 * SHA-256 plan hash, and the primary "Approve & Execute →" CTA.
 */

import { apiClient } from '../apiClient.js';

export async function renderExecutionPlan(rootElement, params, router) {
  rootElement.innerHTML = `
    <div class="main-content" style="max-width: 1400px; margin: 0 auto;">
      <!-- Header -->
      <div style="margin-bottom: 2.25rem;">
        <div class="hero-eyebrow">GOVERNANCE & VALIDATION</div>
        <h1 class="hero-title" style="font-size: 2.4rem; margin-bottom: 0.5rem;">Execution Plan</h1>
        <p class="hero-desc" style="max-width: 780px;">
          Review and audit all synthesized spatial artifacts before committing physical execution.
          Deterministic SHA-256 plan fingerprinting ensures complete provenance.
        </p>
      </div>

      <!-- 4 Artifact Cards -->
      <div style="margin-bottom: 2.5rem;">
        <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted-sage); margin-bottom: 1rem;">
          Synthesized Spatial Artifacts (4)
        </div>
        <div class="artifacts-grid">
          
          <!-- Moodboard Artifact -->
          <div class="artifact-card">
            <div class="artifact-badge">Visual Direction</div>
            <h3 class="artifact-title">Architectural Moodboard</h3>
            <p class="artifact-meta">
              Material palette: Warm lime plaster, dark stained oak, raw brass, monolithic arch motifs, and organic botanical accents.
            </p>
            <div style="display: flex; gap: 0.5rem; margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--warm-stone-light);">
              <span class="entity-pill">High-Res PDF</span>
              <span class="entity-pill">Hex Specs</span>
            </div>
          </div>

          <!-- Playlist Artifact -->
          <div class="artifact-card">
            <div class="artifact-badge">Day-Parted Music</div>
            <h3 class="artifact-title">Austin Mornings Tracklist</h3>
            <p class="artifact-meta">
              25 tracks, 2h 14m runtime. Calibrated acoustic flow featuring Khruangbin, Bon Iver, Tycho, Men I Trust, Alabaster DePlume.
            </p>
            <div style="display: flex; gap: 0.5rem; margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--warm-stone-light);">
              <span class="entity-pill">Spotify Sync</span>
              <span class="entity-pill">BPM Balanced</span>
            </div>
          </div>

          <!-- Library List Artifact -->
          <div class="artifact-card">
            <div class="artifact-badge">Books & Media</div>
            <h3 class="artifact-title">Library Purchase Order</h3>
            <p class="artifact-meta">
              18 curated publications: Gestalten architectural editions, Kinfolk spatial volumes, and A24 screenplay book monographs.
            </p>
            <div style="display: flex; gap: 0.5rem; margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--warm-stone-light);">
              <span class="entity-pill">PO #TO-8402</span>
              <span class="entity-pill">ISBN Matched</span>
            </div>
          </div>

          <!-- Brand Deck Artifact -->
          <div class="artifact-card">
            <div class="artifact-badge">Partnership Draft</div>
            <h3 class="artifact-title">Brand Alignment Deck</h3>
            <p class="artifact-meta">
              Formal partnership pitch letters for Aesop (sensory amenities), Teenage Engineering (sound installation), and Herman Miller.
            </p>
            <div style="display: flex; gap: 0.5rem; margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--warm-stone-light);">
              <span class="entity-pill">Pitch Memos</span>
              <span class="entity-pill">Outreach Ready</span>
            </div>
          </div>

        </div>
      </div>

      <!-- Human-in-the-Loop Governance Gate -->
      <div class="card" style="padding: 2.5rem; border: 1.5px solid var(--deep-botanical); background: var(--white); margin-bottom: 2.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span class="status-badge status-completed" style="font-size: 0.8rem;">● Execution Ready</span>
              <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
                SHA-256: 7f8a9e2d...410b
              </span>
            </div>
            <h2 style="font-family: var(--font-serif); font-size: 1.6rem; color: var(--forest-green); margin: 0.5rem 0 0 0;">
              Awaiting Human Approval
            </h2>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0.25rem 0 0 0;">
              Autonomous curation requires human-in-the-loop executive validation before physical API dispatch.
            </p>
          </div>

          <div style="text-align: right;">
            <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted-sage); font-weight: 600;">
              Auditor
            </div>
            <div style="font-size: 0.9rem; font-weight: 600; color: var(--forest-green);">
              Maitray Agrawal (Venue Manager)
            </div>
          </div>
        </div>

        <!-- Governance Checklist -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin: 1.75rem 0; padding: 1.25rem; background: var(--warm-ivory); border-radius: 12px;">
          <div style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.85rem; color: var(--forest-green); font-weight: 500;">
            <span style="color: var(--completed-green); font-weight: 700;">✓</span>
            <span>Cultural entities verified</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.85rem; color: var(--forest-green); font-weight: 500;">
            <span style="color: var(--completed-green); font-weight: 700;">✓</span>
            <span>Agent outputs validated</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.85rem; color: var(--forest-green); font-weight: 500;">
            <span style="color: var(--completed-green); font-weight: 700;">✓</span>
            <span>Qloo entities resolved</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.85rem; color: var(--forest-green); font-weight: 500;">
            <span style="color: var(--completed-green); font-weight: 700;">✓</span>
            <span>No governance violations</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.85rem; color: var(--forest-green); font-weight: 500;">
            <span style="color: var(--completed-green); font-weight: 700;">✓</span>
            <span>Execution artifacts ready</span>
          </div>
        </div>

        <!-- Strong Primary CTA Button -->
        <div style="display: flex; justify-content: flex-end; align-items: center; gap: 1.25rem; margin-top: 2rem;">
          <a href="/home" class="btn btn-secondary" style="text-decoration: none;">
            Return to Dashboard
          </a>
          <button class="btn btn-primary" id="btn-approve-execute" style="background: #102A22; color: #FFFFFF; font-size: 1rem; padding: 0.85rem 2rem; box-shadow: 0 4px 14px rgba(16, 42, 34, 0.25);">
            <span>Approve & Execute</span>
            <span>→</span>
          </button>
        </div>
      </div>

    </div>
  `;

  // Attach execution trigger
  document.getElementById('btn-approve-execute')?.addEventListener('click', () => {
    router.navigate('/results');
  });
}
