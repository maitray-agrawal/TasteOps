/**
 * TasteOps New Physical Space Venue Registration Screen (/spaces/new).
 *
 * Captures spatial dimensions, business type, sensory atmosphere intent,
 * target audience, cultural anchors, and operational constraints.
 */

import { apiClient } from '../apiClient.js';
import { escapeHtml, renderError, showToast } from '../components/ui.js';

export function renderSpaceNew(rootElement, params, router) {
  rootElement.innerHTML = `
    <div class="fade-in" style="max-width: 860px; margin: 0 auto;">
      <header class="page-header" style="margin-bottom: 2.5rem;">
        <div class="page-title-group">
          <div class="page-breadcrumbs">
            <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
            <span class="breadcrumb-separator">/</span>
            <span>Spaces</span>
            <span class="breadcrumb-separator">/</span>
            <span style="color: var(--text-primary);">New Venue</span>
          </div>
          <h1 class="page-title">Register Physical Space</h1>
          <p class="page-subtitle">
            Configure venue boundaries, audience profiles, and cultural anchor affinities to establish an operational workspace.
          </p>
        </div>
      </header>

      <div id="form-error-container"></div>

      <form id="form-create-space" class="card" style="padding: 2.5rem;">
        <!-- 1. Core Identity -->
        <div style="margin-bottom: 2rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>1.</span> Venue Identity & Typology
          </h2>

          <div class="form-grid-2">
            <div class="form-group">
              <label class="form-label" for="input-space-name">Venue Name *</label>
              <input type="text" id="input-space-name" class="form-input" placeholder="e.g. The Haveli Contemporary" required />
              <div class="form-hint">Physical hospitality venue or cultural space identity.</div>
            </div>

            <div class="form-group">
              <label class="form-label" for="input-business-type">Business Typology *</label>
              <select id="input-business-type" class="form-select" required>
                <option value="Boutique Hotel">Boutique Hotel & Sanctuary</option>
                <option value="Vinyl Listening Bar">Vinyl Listening Bar & Lounge</option>
                <option value="Contemporary Art Gallery & Cafe">Contemporary Art Gallery & Cafe</option>
                <option value="Sensory Concept Store">Sensory Concept Store & Retail</option>
                <option value="Private Members Cultural Club">Private Members Cultural Club</option>
                <option value="Curated Dining Room">Curated Dining Room & Bar</option>
              </select>
            </div>
          </div>
        </div>

        <!-- 2. Geographic Location -->
        <div style="margin-bottom: 2rem; border-top: 1px solid var(--border-subtle); padding-top: 1.75rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>2.</span> Location & Spatial Context
          </h2>

          <div class="form-grid-2">
            <div class="form-group">
              <label class="form-label" for="input-city">City *</label>
              <input type="text" id="input-city" class="form-input" placeholder="e.g. Mumbai, Tokyo, London" required />
            </div>

            <div class="form-group">
              <label class="form-label" for="input-country">Country *</label>
              <input type="text" id="input-country" class="form-input" placeholder="e.g. India, Japan, UK" required />
            </div>
          </div>

          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label" for="input-address">Street Address / Neighborhood</label>
            <input type="text" id="input-address" class="form-input" placeholder="e.g. Kala Ghoda Art District, Fort" />
          </div>
        </div>

        <!-- 3. Cultural & Sensory Brief -->
        <div style="margin-bottom: 2rem; border-top: 1px solid var(--border-subtle); padding-top: 1.75rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>3.</span> Cultural Activation Brief
          </h2>

          <div class="form-group">
            <label class="form-label" for="input-desired-mood">Desired Mood & Atmosphere *</label>
            <input type="text" id="input-desired-mood" class="form-input" placeholder="e.g. Sophisticated, intimate, vinyl-centric, creative sanctuary" required />
            <div class="form-hint">Drives lighting lux parameters, circadian curves, and acoustic identity.</div>
          </div>

          <div class="form-grid-2">
            <div class="form-group">
              <label class="form-label" for="input-target-audience">Target Audience</label>
              <input type="text" id="input-target-audience" class="form-input" placeholder="e.g. Affluent design purists, alternative music lovers" />
            </div>

            <div class="form-group">
              <label class="form-label" for="input-positioning">Brand Positioning</label>
              <input type="text" id="input-positioning" class="form-input" placeholder="e.g. Contemporary Indian cultural sanctuary" />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label" for="input-anchor-entities">Cultural Anchor Entities (Comma separated)</label>
            <textarea id="input-anchor-entities" class="form-textarea" style="min-height: 80px;" placeholder="e.g. Independent cinema, Alternative music, Contemporary Indian design, Ryuichi Sakamoto, Aesop"></textarea>
            <div class="form-hint">Specific entities, artists, brands, or movements used by Qloo to compute cross-domain correlations.</div>
          </div>

          <div class="form-grid-2">
            <div class="form-group">
              <label class="form-label" for="input-budget">Activation Budget</label>
              <input type="text" id="input-budget" class="form-input" placeholder="e.g. $120,000 USD" />
            </div>

            <div class="form-group">
              <label class="form-label" for="input-constraints">Operational Constraints</label>
              <input type="text" id="input-constraints" class="form-input" placeholder="e.g. Noise limit past 11 PM, heritage building facade" />
            </div>
          </div>
        </div>

        <div style="display: flex; align-items: center; justify-content: flex-end; gap: 1rem; border-top: 1px solid var(--border-subtle); padding-top: 1.5rem;">
          <button type="button" class="btn btn-secondary" id="btn-cancel-new-space">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary" id="btn-submit-space">
            <span>Register & Open Space</span>
          </button>
        </div>
      </form>
    </div>
  `;

  document.getElementById('btn-cancel-new-space')?.addEventListener('click', () => {
    router.navigate('/dashboard');
  });

  const form = document.getElementById('form-create-space');
  const errorContainer = document.getElementById('form-error-container');
  const submitBtn = document.getElementById('btn-submit-space');

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorContainer.innerHTML = '';

    const name = document.getElementById('input-space-name').value.trim();
    const businessType = document.getElementById('input-business-type').value;
    const city = document.getElementById('input-city').value.trim();
    const country = document.getElementById('input-country').value.trim();
    const address = document.getElementById('input-address').value.trim();
    const desiredMood = document.getElementById('input-desired-mood').value.trim();
    const targetAudience = document.getElementById('input-target-audience').value.trim();
    const positioning = document.getElementById('input-positioning').value.trim();
    const rawAnchors = document.getElementById('input-anchor-entities').value.trim();
    const budget = document.getElementById('input-budget').value.trim();
    const constraints = document.getElementById('input-constraints').value.trim();

    if (!name || !businessType || !city || !country || !desiredMood) {
      errorContainer.innerHTML = renderError({
        title: 'Validation Error',
        error: { detail: 'Please fill in all required fields indicated with *' },
      });
      return;
    }

    const anchorEntities = rawAnchors
      ? rawAnchors.split(',').map(s => s.trim()).filter(Boolean)
      : [];

    const payload = {
      name,
      business_type: businessType,
      location: {
        city,
        country,
        address: address || null,
      },
      desired_mood: desiredMood,
      target_audience: targetAudience || null,
      positioning: positioning || null,
      anchor_entities: anchorEntities,
      budget: budget || null,
      constraints: constraints ? { general: constraints } : {},
    };

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Creating space...</span>';

    try {
      const space = await apiClient.createSpace(payload);
      showToast(`Physical space '${space.name}' registered successfully!`, 'success');
      router.navigate(`/spaces/${space.space_id}`);
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Register & Open Space</span>';
      errorContainer.innerHTML = renderError({
        title: 'Failed to Register Space',
        error: err,
        retryId: 'btn-retry-form-submit',
      });
    }
  });
}
