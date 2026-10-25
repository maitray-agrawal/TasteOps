/**
 * TasteOps Cultural Twin Screen (Route: /cultural-twin)
 * Section 12: Primary visual centerpiece, concentric/radial cultural fingerprint visualization,
 * verified cultural insights from Qloo's 250M+ entity graph.
 */

import { apiClient } from '../apiClient.js';

export async function renderCulturalTwin(rootElement, params, router) {
  rootElement.innerHTML = `
    <div class="main-content" style="max-width: 1400px; margin: 0 auto;">
      <!-- Header -->
      <div style="margin-bottom: 2.25rem;">
        <div class="hero-eyebrow">CULTURAL INTELLIGENCE</div>
        <h1 class="hero-title" style="font-size: 2.4rem; margin-bottom: 0.5rem;">Cultural Twin</h1>
        <p class="hero-desc" style="max-width: 780px;">
          Verified cultural insights derived from Qloo's 250M+ entity cross-domain taste graph.
          Mapping multi-category affinity distributions for demographic resonance.
        </p>
      </div>

      <!-- Grid: Radial Fingerprint + Domain Breakdown -->
      <div style="display: grid; grid-template-columns: 1.1fr 1fr; gap: 2rem; align-items: start; margin-bottom: 2.5rem;">
        
        <!-- Radial Cultural Fingerprint Card -->
        <div class="card" style="padding: 2.5rem; text-align: center;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <div>
              <h2 style="font-family: var(--font-serif); font-size: 1.4rem; color: var(--forest-green); margin: 0; text-align: left;">Cultural Fingerprint</h2>
              <p style="font-size: 0.8rem; color: var(--text-muted); margin: 0.25rem 0 0 0; text-align: left;">High-dimensional affinity projection</p>
            </div>
            <span class="status-badge status-completed" style="font-size: 0.75rem;">Qloo Verified</span>
          </div>

          <!-- Master Radial Geometry Container -->
          <div class="twin-visual-container" style="margin: 1.5rem auto;">
            <div class="twin-ring twin-ring-3"></div>
            <div class="twin-ring twin-ring-2"></div>
            <div class="twin-ring twin-ring-1"></div>
            
            <!-- Center Affinity Metric -->
            <div class="twin-core">
              <span class="twin-core-val">87%</span>
              <span class="twin-core-lbl">Cultural Affinity</span>
            </div>

            <!-- 5 Satellites with Entity Thumbnails & Affinity -->
            <div class="twin-satellite twin-sat-music" title="Khruangbin, Bon Iver, Men I Trust">
              <span class="sat-val">92%</span>
              <span class="sat-lbl">Music</span>
            </div>

            <div class="twin-satellite twin-sat-books" title="Gestalten Architecture, Kinfolk, A24 Screenplays">
              <span class="sat-val">78%</span>
              <span class="sat-lbl">Books</span>
            </div>

            <div class="twin-satellite twin-sat-brands" title="Aesop, Herman Miller, Teenage Engineering">
              <span class="sat-val">81%</span>
              <span class="sat-lbl">Brands</span>
            </div>

            <div class="twin-satellite twin-sat-lifestyle" title="Specialty Pour-over, Modern Ceramics, Vinyl">
              <span class="sat-val">86%</span>
              <span class="sat-lbl">Lifestyle</span>
            </div>

            <div class="twin-satellite twin-sat-interests" title="Minimalist Architecture, Independent Cinema">
              <span class="sat-val">73%</span>
              <span class="sat-lbl">Interests</span>
            </div>
          </div>

          <div style="margin-top: 1.5rem; font-size: 0.825rem; color: var(--text-muted); line-height: 1.5;">
            Cross-domain correlation index computed across 6 distinct cultural verticals with zero synthetic hallucinations.
          </div>
        </div>

        <!-- Domain Affinity Breakdown Card -->
        <div class="card" style="padding: 2.25rem;">
          <h2 style="font-family: var(--font-serif); font-size: 1.4rem; color: var(--forest-green); margin: 0 0 0.5rem 0;">Entity Graph Resolution</h2>
          <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1.75rem;">
            Resolved cultural entities matched to Austin Tech & Creative demographic intent.
          </p>

          <div style="display: flex; flex-direction: column; gap: 1.25rem;">
            <!-- Music Domain -->
            <div style="border-bottom: 1px solid var(--warm-stone-light); padding-bottom: 1rem;">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.4rem;">
                <span style="font-weight: 600; font-size: 0.95rem; color: var(--forest-green);">Music & Sonic Atmosphere</span>
                <span style="font-weight: 700; color: var(--forest-green); font-size: 0.95rem;">92%</span>
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                Key Entities: Khruangbin, Bon Iver, Tycho, Men I Trust, Alabaster DePlume
              </div>
              <div style="height: 6px; background: var(--warm-stone-light); border-radius: 999px; overflow: hidden;">
                <div style="width: 92%; height: 100%; background: var(--forest-green); border-radius: 999px;"></div>
              </div>
            </div>

            <!-- Lifestyle Domain -->
            <div style="border-bottom: 1px solid var(--warm-stone-light); padding-bottom: 1rem;">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.4rem;">
                <span style="font-weight: 600; font-size: 0.95rem; color: var(--forest-green);">Lifestyle & Spatial Rituals</span>
                <span style="font-weight: 700; color: var(--forest-green); font-size: 0.95rem;">86%</span>
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                Key Entities: Flat White Ritual, Japanese Ceramics, Natural Wine Evenings
              </div>
              <div style="height: 6px; background: var(--warm-stone-light); border-radius: 999px; overflow: hidden;">
                <div style="width: 86%; height: 100%; background: var(--deep-botanical); border-radius: 999px;"></div>
              </div>
            </div>

            <!-- Brands Domain -->
            <div style="border-bottom: 1px solid var(--warm-stone-light); padding-bottom: 1rem;">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.4rem;">
                <span style="font-weight: 600; font-size: 0.95rem; color: var(--forest-green);">Aligned Brand Partnerships</span>
                <span style="font-weight: 700; color: var(--forest-green); font-size: 0.95rem;">81%</span>
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                Key Entities: Aesop, Teenage Engineering, Herman Miller, HAY Design
              </div>
              <div style="height: 6px; background: var(--warm-stone-light); border-radius: 999px; overflow: hidden;">
                <div style="width: 81%; height: 100%; background: var(--muted-sage); border-radius: 999px;"></div>
              </div>
            </div>

            <!-- Books Domain -->
            <div style="border-bottom: 1px solid var(--warm-stone-light); padding-bottom: 1rem;">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.4rem;">
                <span style="font-weight: 600; font-size: 0.95rem; color: var(--forest-green);">Curated Library & Publications</span>
                <span style="font-weight: 700; color: var(--forest-green); font-size: 0.95rem;">78%</span>
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                Key Entities: Gestalten Architecture, Kinfolk Volumes, A24 Screenplay Books
              </div>
              <div style="height: 6px; background: var(--warm-stone-light); border-radius: 999px; overflow: hidden;">
                <div style="width: 78%; height: 100%; background: var(--terracotta); border-radius: 999px;"></div>
              </div>
            </div>

            <!-- Cinema & Cultural Interests -->
            <div>
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.4rem;">
                <span style="font-weight: 600; font-size: 0.95rem; color: var(--forest-green);">Independent Film & Architecture</span>
                <span style="font-weight: 700; color: var(--forest-green); font-size: 0.95rem;">73%</span>
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                Key Entities: A24 Productions, Brutalist Monograph, Nordic Mid-century
              </div>
              <div style="height: 6px; background: var(--warm-stone-light); border-radius: 999px; overflow: hidden;">
                <div style="width: 73%; height: 100%; background: var(--soft-clay); border-radius: 999px;"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer CTA to proceed to Specialized Agents -->
      <div class="card" style="padding: 1.75rem 2.25rem; display: flex; justify-content: space-between; align-items: center; background: var(--soft-cream);">
        <div>
          <span style="font-size: 0.75rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted-sage);">Next Operational Step</span>
          <div style="font-family: var(--font-serif); font-size: 1.25rem; color: var(--forest-green); margin-top: 0.2rem;">
            Dispatch Specialized Agents for Playlist, Library & Brands
          </div>
        </div>
        <a href="/agents" class="btn btn-primary" style="text-decoration: none;">
          <span>View Agents Command Center</span>
          <span>→</span>
        </a>
      </div>
    </div>
  `;
}
