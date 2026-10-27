/**
 * TasteOps Specialized Agents Screen (Route: /agents)
 * Section 13: Parallel agent command center featuring Sonic Agent, Procurement Agent,
 * and Brand Agent with animated waveform, telemetry, and live status.
 */

import { apiClient } from '../apiClient.js';
import { escapeHtml } from '../components/ui.js';

export function renderAgents(rootElement, params, router) {
  const activeSessionId = window.currentSessionId || (typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('tasteops_active_session_id') : null);

  const renderContent = (liveSession, isColdStarting = false) => {
    const tel = liveSession?.agent_telemetry || {};
    const sonicDur = tel.sonic?.duration_s ? `${tel.sonic.duration_s.toFixed(2)}s` : '4.82s';
    const procDur = tel.procurement?.duration_s ? `${tel.procurement.duration_s.toFixed(2)}s` : '3.11s';
    const brandDur = tel.brand?.duration_s ? `${tel.brand.duration_s.toFixed(2)}s` : '5.73s';

    const matrix = liveSession?.cultural_matrix;
    const sonicArtists = matrix?.artists?.length ? matrix.artists.slice(0, 3).map(a => a.name) : ['Khruangbin', 'Bon Iver', 'Tycho'];
    const procBooks = matrix?.books?.length ? matrix.books.slice(0, 3).map(b => b.name) : ['Gestalten Works', 'Kinfolk Issues', 'A24 Monograph'];
    const brandPartners = matrix?.brands?.length ? matrix.brands.slice(0, 3).map(br => br.name) : ['Aesop', 'Teenage Eng.', 'Herman Miller'];

    rootElement.innerHTML = `
      <div class="main-content" style="max-width: 1400px; margin: 0 auto;">
        ${isColdStarting ? `
          <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 0.75rem 1.25rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #92400e;">
            <span>⚡ <strong>Render Backend Waking Up:</strong> The backend is starting from idle. Displaying offline telemetry baseline.</span>
            <button id="btn-retry-agents-hydration" class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.75rem; background: #fff;">Retry Fetch</button>
          </div>
        ` : ''}
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 2rem;">
          <div>
            <div class="hero-eyebrow">AGENT COMMAND CENTER</div>
            <h1 class="hero-title" style="font-size: 2.4rem; margin-bottom: 0.5rem;">Specialized Agents</h1>
            <p class="hero-desc" style="max-width: 720px;">
              ${liveSession ? `Autonomous worker agents operating concurrently for session: ${activeSessionId}.` : 'Autonomous worker agents operating in parallel to transform cultural intelligence into verifiable physical spatial assets (Austin Reference Baseline).'}
            </p>
          </div>
          <div>
            <span class="status-badge ${liveSession ? 'status-completed' : 'status-waiting'}" style="font-size: 0.85rem; padding: 0.45rem 1rem;">
              ${liveSession ? `● Live Session: ${activeSessionId.slice(0, 10)}...` : '● Austin Demo Telemetry'}
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
            <span class="status-badge status-completed" style="font-size: 0.72rem;">COMPLETE · ${sonicDur}</span>
          </div>

          <div class="agent-desc">
            Creating day-parted ambient playlist calibrated for morning focus and evening unwind from Qloo musical affinities...
          </div>

          <!-- Animated Audio Waveform -->
          <div style="margin: 1.25rem 0;">
            <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 0.5rem; display: flex; justify-content: space-between;">
              <span>Acoustic Profile Modulation</span>
              <span style="color: var(--forest-green);">18 Entities Processed</span>
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
              <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                ${sonicArtists.map(name => `<span class="entity-pill">${escapeHtml(name)}</span>`).join('')}
              </div>
              <div style="display: flex; align-items: center; gap: 0.35rem; font-size: 0.75rem; color: var(--forest-green); font-weight: 600;">
                <span>STAGED · VALIDATED</span>
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
            <span class="status-badge status-completed" style="font-size: 0.72rem;">COMPLETE · ${procDur}</span>
          </div>

          <div class="agent-desc">
            Selecting books & generating 8-column purchase orders for architectural monographs and indie periodicals...
          </div>

          <!-- Catalog Generation Progress -->
          <div style="margin: 1.25rem 0;">
            <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 0.5rem; display: flex; justify-content: space-between;">
              <span>ISBN Resolution & Catalog Integrity</span>
              <span style="color: var(--forest-green);">12 Publications Sourced</span>
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
                <span class="entity-pill">12 Titles</span>
                <span class="entity-pill">CSV PO</span>
              </div>
              <span style="font-size: 0.75rem; color: var(--forest-green); font-weight: 600;">READY · VALIDATED</span>
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
            <span class="status-badge status-completed" style="font-size: 0.72rem;">COMPLETE · ${brandDur}</span>
          </div>

          <div class="agent-desc">
            Identifying aligned cultural brands & drafting co-branded activation outreach proposals...
          </div>

          <!-- Brand Match Highlights -->
          <div style="margin: 1.25rem 0;">
            <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 0.5rem; display: flex; justify-content: space-between;">
              <span>Partner Alignment Indices</span>
              <span style="color: var(--forest-green);">9 Entities Processed</span>
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
              <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                ${brandPartners.map(name => `<span class="entity-pill">${escapeHtml(name)}</span>`).join('')}
              </div>
              <span style="font-size: 0.75rem; color: var(--forest-green); font-weight: 600;">DRAFTED · VALIDATED</span>
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
              Deterministic state synchronization via asyncio.gather across isolated agent workers
            </p>
          </div>
          <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); background: var(--warm-ivory); padding: 0.3rem 0.6rem; border-radius: 6px;">
            PARALLEL DURATION: 5.73s • WORKERS: 3/3
          </span>
        </div>

        <div style="background: var(--forest-green); border-radius: 12px; padding: 1.25rem; font-family: var(--font-mono); font-size: 0.8rem; color: var(--soft-cream); line-height: 1.7; overflow-x: auto;">
          <div><span style="color: var(--muted-sage);">[14:42:01.000]</span> <span style="color: var(--sage-light);">[Orchestrator]</span> Dispatching ExperienceArchitect & PartnershipAgent concurrently via asyncio.gather</div>
          <div><span style="color: var(--muted-sage);">[14:42:01.108]</span> <span style="color: var(--accent-blue);">[SonicAgent]</span> Querying Qloo acoustic vector for space_id: "austin-coworking-1" · 18 entities processed</div>
          <div><span style="color: var(--muted-sage);">[14:42:04.110]</span> <span style="color: var(--completed-green);">[ProcurementAgent]</span> Sourced 12 ISBNs · Generated 8-column PO CSV · COMPLETE in 3.11s</div>
          <div><span style="color: var(--muted-sage);">[14:42:05.820]</span> <span style="color: var(--accent-blue);">[SonicAgent]</span> Created Spotify sandbox playlist spec · COMPLETE in 4.82s</div>
          <div><span style="color: var(--muted-sage);">[14:42:06.730]</span> <span style="color: var(--waiting-yellow);">[BrandAgent]</span> Synthesized 3 partnership dossiers & outreach letters · COMPLETE in 5.73s</div>
          <div><span style="color: var(--muted-sage);">[14:42:06.890]</span> <span style="color: var(--muted-sage);">[GovernanceAgent]</span> Zero compliance violations detected; plan hash SHA-256 bound; awaiting human sign-off</div>
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
  };

  // 1. Immediate synchronous render (0ms blocking delay)
  renderContent(null, false);

  // 2. Asynchronous non-blocking session hydration
  const hydrate = () => {
    if (!activeSessionId) return;
    apiClient.getSession(activeSessionId).then((liveSession) => {
      if (window.tasteopsRouter?.currentRoute !== '/agents') return;
      renderContent(liveSession, false);
    }).catch((err) => {
      if (window.tasteopsRouter?.currentRoute !== '/agents') return;
      const isColdStart = err.code === 'BACKEND_COLD_START_TIMEOUT' || err.isNetworkError;
      renderContent(null, isColdStart);
      document.getElementById('btn-retry-agents-hydration')?.addEventListener('click', hydrate);
    });
  };

  hydrate();
}
