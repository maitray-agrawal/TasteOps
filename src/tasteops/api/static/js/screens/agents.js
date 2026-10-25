/**
 * TasteOps Specialized Agents Screen (Route: /agents)
 * Section 13: Parallel agent command center featuring Sonic Agent, Procurement Agent,
 * and Brand Agent with animated waveform, telemetry, and live status.
 */

export async function renderAgents(rootElement, params, router) {
  rootElement.innerHTML = `
    <div class="main-content" style="max-width: 1400px; margin: 0 auto;">
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 2rem;">
        <div>
          <div class="hero-eyebrow">AGENT COMMAND CENTER</div>
          <h1 class="hero-title" style="font-size: 2.4rem; margin-bottom: 0.5rem;">Specialized Agents</h1>
          <p class="hero-desc" style="max-width: 720px;">
            Autonomous worker agents operating in parallel to transform cultural intelligence
            into verifiable, tangible physical spatial assets.
          </p>
        </div>
        <div>
          <span class="status-badge status-running" style="font-size: 0.85rem; padding: 0.45rem 1rem;">
            ● 3 Agents Running in Parallel
          </span>
        </div>
      </div>

      <!-- 3 Primary Parallel Agent Cards -->
      <div class="agents-grid" style="margin-bottom: 2.5rem;">
        
        <!-- Sonic Agent Card -->
        <div class="agent-card">
          <div class="agent-header">
            <div class="agent-avatar">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 18V5l12-2v13"></path>
                <circle cx="6" cy="18" r="3"></circle>
                <circle cx="18" cy="16" r="3"></circle>
              </svg>
            </div>
            <div style="flex: 1;">
              <div class="agent-name">Sonic Agent</div>
              <div style="font-size: 0.72rem; color: var(--text-muted);">Spotify & Ambient Audio Curation</div>
            </div>
            <span class="status-badge status-running" style="font-size: 0.72rem;">Running</span>
          </div>

          <div class="agent-desc">
            Creating day-parted ambient playlist calibrated for morning focus and evening unwind...
          </div>

          <!-- Animated Audio Waveform -->
          <div style="margin: 1.25rem 0;">
            <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 0.5rem;">
              Acoustic Profile Modulation
            </div>
            <div class="waveform-anim">
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
              <div class="wave-bar"></div>
            </div>
          </div>

          <!-- Thumbnails & Spotify Indicator -->
          <div style="margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--warm-stone-light);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div style="display: flex; gap: 0.4rem;">
                <span class="entity-pill">Khruangbin</span>
                <span class="entity-pill">Bon Iver</span>
                <span class="entity-pill">Tycho</span>
              </div>
              <div style="display: flex; align-items: center; gap: 0.35rem; font-size: 0.75rem; color: #1DB954; font-weight: 600;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                </svg>
                <span>Spotify Sync</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Procurement Agent Card -->
        <div class="agent-card">
          <div class="agent-header">
            <div class="agent-avatar">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
              </svg>
            </div>
            <div style="flex: 1;">
              <div class="agent-name">Procurement Agent</div>
              <div style="font-size: 0.72rem; color: var(--text-muted);">Library, Books & Art Media POs</div>
            </div>
            <span class="status-badge status-running" style="font-size: 0.72rem;">Running</span>
          </div>

          <div class="agent-desc">
            Selecting books & generating purchase orders for architectural monographs and indie periodicals...
          </div>

          <!-- Catalog Generation Progress -->
          <div style="margin: 1.25rem 0;">
            <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 0.5rem;">
              ISBN Resolution & Supplier Verification
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.45rem;">
              <div style="font-size: 0.78rem; display: flex; justify-content: space-between; color: var(--text-ink);">
                <span>Gestalten Architectural Works</span>
                <span style="font-weight: 600; color: var(--forest-green);">Verified</span>
              </div>
              <div style="font-size: 0.78rem; display: flex; justify-content: space-between; color: var(--text-ink);">
                <span>Kinfolk Volume 42 (Spatial Issues)</span>
                <span style="font-weight: 600; color: var(--forest-green);">In Stock</span>
              </div>
              <div style="font-size: 0.78rem; display: flex; justify-content: space-between; color: var(--text-ink);">
                <span>A24 Screenplay: The Lighthouse</span>
                <span style="font-weight: 600; color: var(--forest-green);">Sourced</span>
              </div>
            </div>
          </div>

          <!-- Thumbnails & Status -->
          <div style="margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--warm-stone-light);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div style="display: flex; gap: 0.4rem;">
                <span class="entity-pill">18 Titles</span>
                <span class="entity-pill">ISBN Matched</span>
              </div>
              <span style="font-size: 0.75rem; color: var(--forest-green); font-weight: 600;">PO Ready</span>
            </div>
          </div>
        </div>

        <!-- Brand Agent Card -->
        <div class="agent-card">
          <div class="agent-header">
            <div class="agent-avatar">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>
                <line x1="7" y1="7" x2="7.01" y2="7"></line>
              </svg>
            </div>
            <div style="flex: 1;">
              <div class="agent-name">Brand Agent</div>
              <div style="font-size: 0.72rem; color: var(--text-muted);">Partnership Outreaches & Amenities</div>
            </div>
            <span class="status-badge status-running" style="font-size: 0.72rem;">Running</span>
          </div>

          <div class="agent-desc">
            Identifying aligned cultural brands & drafting co-branded activation outreach proposals...
          </div>

          <!-- Brand Match Highlights -->
          <div style="margin: 1.25rem 0;">
            <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 0.5rem;">
              Partner Alignment Indices
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.45rem;">
              <div style="font-size: 0.78rem; display: flex; justify-content: space-between; color: var(--text-ink);">
                <span>Aesop (Aromatics & Hand Care)</span>
                <span style="font-weight: 600; color: var(--forest-green);">94% Fit</span>
              </div>
              <div style="font-size: 0.78rem; display: flex; justify-content: space-between; color: var(--text-ink);">
                <span>Teenage Engineering (Audio Hardware)</span>
                <span style="font-weight: 600; color: var(--forest-green);">89% Fit</span>
              </div>
              <div style="font-size: 0.78rem; display: flex; justify-content: space-between; color: var(--text-ink);">
                <span>Herman Miller (Ergonomic Seating)</span>
                <span style="font-weight: 600; color: var(--forest-green);">87% Fit</span>
              </div>
            </div>
          </div>

          <!-- Thumbnails & Pitch Status -->
          <div style="margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--warm-stone-light);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div style="display: flex; gap: 0.4rem;">
                <span class="entity-pill">Aesop</span>
                <span class="entity-pill">TE</span>
                <span class="entity-pill">Herman Miller</span>
              </div>
              <span style="font-size: 0.75rem; color: var(--terracotta); font-weight: 600;">Drafting Pitch</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Agent Telemetry & Deterministic Pipeline Log Stream -->
      <div class="card" style="padding: 2rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
          <div>
            <h3 style="font-family: var(--font-serif); font-size: 1.25rem; color: var(--forest-green); margin: 0;">Parallel Execution Telemetry</h3>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin: 0.2rem 0 0 0;">
              Deterministic state synchronization across isolated agent workers
            </p>
          </div>
          <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); background: var(--warm-ivory); padding: 0.3rem 0.6rem; border-radius: 6px;">
            LATENCY: 42ms • WORKERS: 3/3
          </span>
        </div>

        <div style="background: var(--forest-green); border-radius: 12px; padding: 1.25rem; font-family: var(--font-mono); font-size: 0.8rem; color: var(--soft-cream); line-height: 1.7; overflow-x: auto;">
          <div><span style="color: var(--muted-sage);">[14:42:01.108]</span> <span style="color: var(--accent-blue);">[SonicAgent]</span> Querying Qloo acoustic vector for space_id: "austin-coworking-1"</div>
          <div><span style="color: var(--muted-sage);">[14:42:01.320]</span> <span style="color: var(--completed-green);">[ProcurementAgent]</span> Sourced 18 ISBNs; generating purchase order with local Austin bookstore distributor</div>
          <div><span style="color: var(--muted-sage);">[14:42:01.550]</span> <span style="color: var(--waiting-yellow);">[BrandAgent]</span> Synthesized partnership memo for Aesop spatial scenting residency</div>
          <div><span style="color: var(--muted-sage);">[14:42:01.890]</span> <span style="color: var(--muted-sage);">[GovernanceAgent]</span> Zero compliance violations detected; ready for human sign-off</div>
        </div>
      </div>

      <!-- Footer CTA to proceed to Execution Plan -->
      <div style="margin-top: 2rem; display: flex; justify-content: flex-end;">
        <a href="/execution-plan" class="btn btn-primary" style="text-decoration: none;">
          <span>Review Execution Plan & Governance</span>
          <span>→</span>
        </a>
      </div>
    </div>
  `;
}
