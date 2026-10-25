/**
 * TasteOps Opening / Splash Screen (Route: /)
 * Section 5: Minimal premium opening screen, centered arch logo, brand messaging, botanical arch vignette.
 */

export function renderSplash(rootElement, router) {
  rootElement.innerHTML = `
    <div class="splash-container">
      <!-- Minimalist Top Navigation Header -->
      <div class="splash-top-bar">
        <div style="font-size: 0.75rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted-sage);">
          Editorial Release • 2026
        </div>
        <div style="font-size: 0.8rem; font-weight: 500; color: var(--text-muted);">
          Culture × Intelligence × Action
        </div>
      </div>

      <!-- Centered Hero Brand Lockup -->
      <div class="splash-center">
        <!-- TasteOps Arch Motif Logo -->
        <div class="splash-logo-arch">
          <div class="splash-logo-inner"></div>
        </div>

        <h1 class="splash-title">TasteOps</h1>
        <div class="splash-subtitle">AUTONOMOUS SPATIAL CURATION</div>

        <div class="splash-philosophy">Spaces with a Soul.</div>

        <div class="splash-divider"></div>

        <div class="splash-workflow">Curate · Align · Execute</div>

        <!-- Primary CTA to enter main application -->
        <button class="splash-cta" id="btn-enter-tasteops">
          <span>Enter TasteOps</span>
          <span>→</span>
        </button>
      </div>

      <!-- Lower-Left Botanical Architectural Vignette -->
      <div class="splash-botanical-corner">
        <img src="/static/images/splash_arch.jpg" alt="TasteOps Architectural Vignette" />
      </div>

      <!-- Bottom Credits / Philosophy Tag -->
      <div style="display: flex; justify-content: flex-end; align-items: center; z-index: 2;">
        <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-sans);">
          Design spaces people belong to.
        </span>
      </div>
    </div>
  `;

  // Attach click listener for primary entrance
  document.getElementById('btn-enter-tasteops')?.addEventListener('click', (e) => {
    e.preventDefault();
    router.navigate('/home');
  });
}
