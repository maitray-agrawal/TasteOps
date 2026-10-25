/**
 * TasteOps New Physical Space Venue Registration Screen (/spaces/new).
 *
 * Implements the complete New Space workflow:
 * 1. Collects:
 *    - business/brand
 *    - location (city, country, address, coordinates, radius)
 *    - audience
 *    - positioning
 *    - goals
 *    - budget
 *    - constraints
 *    - cultural preferences (mood, aesthetic motifs)
 *    - optional references (anchor entities)
 *
 * 2. Executes deterministic pipeline flow:
 *    POST /spaces
 *          ↓
 *    POST /spaces/{space_id}/analyze
 *          ↓
 *    session page (/sessions/[sessionId])
 */

import { apiClient } from '../apiClient.js';
import { escapeHtml, renderError, showToast } from '../components/ui.js';

export function renderSpaceNew(rootElement, params, router) {
  rootElement.innerHTML = `
    <div class="fade-in" style="max-width: 900px; margin: 0 auto; padding-bottom: 4rem;">
      <header class="page-header" style="margin-bottom: 2rem;">
        <div class="page-title-group">
          <div class="page-breadcrumbs">
            <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
            <span class="breadcrumb-separator">/</span>
            <span>Spaces</span>
            <span class="breadcrumb-separator">/</span>
            <span style="color: var(--text-primary);">New Space</span>
          </div>
          <h1 class="page-title">Register Physical Space</h1>
          <p class="page-subtitle">
            Configure architectural typology, sensory preferences, and cultural anchor affinities to establish an operational workspace.
          </p>
        </div>
      </header>

      <!-- Flow Stepper Indicator -->
      <div class="card" style="margin-bottom: 2rem; padding: 1.25rem 2rem; background: var(--bg-surface-elevated);">
        <div style="display: flex; align-items: center; justify-content: space-between; position: relative;">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <div style="width: 28px; height: 28px; border-radius: 50%; background: var(--cyan); color: #000; font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 0.85rem;">1</div>
            <div>
              <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-primary);">Create Activation Brief</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">POST /api/v1/sessions</div>
            </div>
          </div>
          <div style="flex: 1; height: 2px; background: var(--border-subtle); margin: 0 1.5rem;"></div>
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <div style="width: 28px; height: 28px; border-radius: 50%; background: var(--bg-surface); border: 1px solid var(--border-strong); color: var(--text-muted); font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 0.85rem;">2</div>
            <div>
              <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-muted);">Run Cultural Pipeline</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">POST /api/v1/sessions/{id}/pipeline</div>
            </div>
          </div>
          <div style="flex: 1; height: 2px; background: var(--border-subtle); margin: 0 1.5rem;"></div>
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <div style="width: 28px; height: 28px; border-radius: 50%; background: var(--bg-surface); border: 1px solid var(--border-strong); color: var(--text-muted); font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 0.85rem;">3</div>
            <div>
              <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-muted);">Session Workspace</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">/sessions/{sessionId}</div>
            </div>
          </div>
        </div>
      </div>

      <div id="form-error-container"></div>
      <div id="form-progress-container" style="display: none; margin-bottom: 2rem;"></div>

      <form id="form-create-space" class="card" style="padding: 2.5rem;">
        <!-- 1. Business & Brand -->
        <div style="margin-bottom: 2.25rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span style="color: var(--cyan);">1.</span> Business & Brand Identity
          </h2>

          <div class="form-grid-2">
            <div class="form-group">
              <label class="form-label" for="input-space-name">Venue / Space Name *</label>
              <input type="text" id="input-space-name" class="form-input" placeholder="e.g. Kitsuné Musique Lab" required />
              <div class="form-hint">Unique activation or venue identity.</div>
            </div>

            <div class="form-group">
              <label class="form-label" for="input-brand">Brand / Parent Identity</label>
              <input type="text" id="input-brand" class="form-input" placeholder="e.g. Maison Kitsuné" />
              <div class="form-hint">Parent brand or corporate cultural sponsor.</div>
            </div>
          </div>

          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label" for="input-business-type">Business Typology *</label>
            <select id="input-business-type" class="form-select" required>
              <option value="Analog Vinyl Listening Bar & Cafe">Analog Vinyl Listening Bar & Cafe</option>
              <option value="Boutique Hotel & Sanctuary">Boutique Hotel & Sanctuary</option>
              <option value="Contemporary Art Gallery & Cafe">Contemporary Art Gallery & Cafe</option>
              <option value="Sensory Concept Store & Retail">Sensory Concept Store & Retail</option>
              <option value="Private Members Cultural Club">Private Members Cultural Club</option>
              <option value="Curated Dining Room & Bar">Curated Dining Room & Bar</option>
              <option value="Specialty Coffee Lab">Specialty Coffee Lab</option>
            </select>
          </div>
        </div>

        <!-- 2. Location -->
        <div style="margin-bottom: 2.25rem; border-top: 1px solid var(--border-subtle); padding-top: 1.75rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span style="color: var(--cyan);">2.</span> Location & Spatial Context
          </h2>

          <div class="form-grid-2">
            <div class="form-group">
              <label class="form-label" for="input-city">City *</label>
              <input type="text" id="input-city" class="form-input" placeholder="e.g. Kyoto, Mumbai, Berlin, London" required />
            </div>

            <div class="form-group">
              <label class="form-label" for="input-country">Country *</label>
              <input type="text" id="input-country" class="form-input" placeholder="e.g. Japan, India, Germany, UK" required />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label" for="input-address">Street Address / Cultural District</label>
            <input type="text" id="input-address" class="form-input" placeholder="e.g. Gion Historic District, Higashiyama" />
          </div>

          <div class="form-grid-2" style="margin-bottom: 0;">
            <div class="form-group" style="margin-bottom: 0;">
              <label class="form-label" for="input-coordinates">Coordinates (Optional: Lat, Long)</label>
              <input type="text" id="input-coordinates" class="form-input" placeholder="e.g. 35.0037, 135.7772" />
              <div class="form-hint">Used for exact Qloo spatial POI radius filtering.</div>
            </div>

            <div class="form-group" style="margin-bottom: 0;">
              <label class="form-label" for="input-radius">Search Radius (Meters)</label>
              <input type="number" id="input-radius" class="form-input" value="2000" min="100" max="50000" step="100" />
            </div>
          </div>
        </div>

        <!-- 3. Audience & Positioning -->
        <div style="margin-bottom: 2.25rem; border-top: 1px solid var(--border-subtle); padding-top: 1.75rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span style="color: var(--cyan);">3.</span> Audience & Market Positioning
          </h2>

          <div class="form-grid-2">
            <div class="form-group">
              <label class="form-label" for="input-target-audience">Target Audience Profile *</label>
              <input type="text" id="input-target-audience" class="form-input" placeholder="e.g. Design purists, vinyl collectors, ambient music lovers aged 25-45" required />
              <div class="form-hint">Demographic and psychographic traits grounding the Cultural Twin.</div>
            </div>

            <div class="form-group">
              <label class="form-label" for="input-positioning">Market Positioning *</label>
              <input type="text" id="input-positioning" class="form-input" placeholder="e.g. Underground Franco-Japanese sound and coffee sanctuary" required />
              <div class="form-hint">Aesthetic differentiation against conventional venues.</div>
            </div>
          </div>
        </div>

        <!-- 4. Goals & Budget -->
        <div style="margin-bottom: 2.25rem; border-top: 1px solid var(--border-subtle); padding-top: 1.75rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span style="color: var(--cyan);">4.</span> Strategic Goals & Budget
          </h2>

          <div class="form-grid-2">
            <div class="form-group">
              <label class="form-label" for="input-goals">Strategic Goals</label>
              <input type="text" id="input-goals" class="form-input" placeholder="e.g. Bridge Parisian indie music with Kyoto craftsmanship; foster intimate analog community" />
              <div class="form-hint">Key qualitative activation milestones.</div>
            </div>

            <div class="form-group">
              <label class="form-label" for="input-budget">Activation Budget Tier</label>
              <input type="text" id="input-budget" class="form-input" placeholder="e.g. $150,000 USD / High-end boutique allocation" />
              <div class="form-hint">Budget boundary guiding material and partnership curations.</div>
            </div>
          </div>
        </div>

        <!-- 5. Cultural Preferences & Mood -->
        <div style="margin-bottom: 2.25rem; border-top: 1px solid var(--border-subtle); padding-top: 1.75rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span style="color: var(--cyan);">5.</span> Cultural Preferences & Atmosphere
          </h2>

          <div class="form-group">
            <label class="form-label" for="input-desired-mood">Desired Mood & Atmospheric Energy *</label>
            <input type="text" id="input-desired-mood" class="form-input" placeholder="e.g. Warm intimate acoustic focus, wabi-sabi minimalism, golden-hour circadian lighting" required />
            <div class="form-hint">Governs sensory design, lighting Kelvin/lux profiles, and acoustic soundscape.</div>
          </div>

          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label" for="input-cultural-preferences">Cultural & Aesthetic Preferences</label>
            <textarea id="input-cultural-preferences" class="form-textarea" style="min-height: 70px;" placeholder="e.g. Japanese jazz kissa culture, Japanese ambient electronic music, artisanal fermented teas, brutalist woodwork"></textarea>
            <div class="form-hint">Artistic subcultures, sonic textures, and design traditions to synthesize.</div>
          </div>
        </div>

        <!-- 6. Constraints & Exclusions -->
        <div style="margin-bottom: 2.25rem; border-top: 1px solid var(--border-subtle); padding-top: 1.75rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span style="color: var(--cyan);">6.</span> Constraints & Guardrails
          </h2>

          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label" for="input-constraints">Operational & Spatial Constraints</label>
            <input type="text" id="input-constraints" class="form-input" placeholder="e.g. Acoustic cap at 78 dB, timber-only resonance, no digital screens in main listening lounge" />
            <div class="form-hint">Strict boundaries enforced by the Governance compliance agent.</div>
          </div>
        </div>

        <!-- 7. Optional References (Anchor Entities) -->
        <div style="margin-bottom: 2.25rem; border-top: 1px solid var(--border-subtle); padding-top: 1.75rem;">
          <h2 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
            <span style="color: var(--cyan);">7.</span> Optional Reference Anchors (Ground Truth Signals)
          </h2>

          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label" for="input-anchor-entities">Cultural Anchor Entities (Comma separated)</label>
            <textarea id="input-anchor-entities" class="form-textarea" style="min-height: 80px;" placeholder="e.g. Ryuichi Sakamoto, Midori Takada, Blue Bottle Coffee, Aesop, Kissa Bossa"></textarea>
            <div class="form-hint">Authoritative real-world artists, brands, venues, or aesthetics resolved via Qloo for empirical taste correlations. Never invented.</div>
          </div>
        </div>

        <!-- Submit & Actions -->
        <div style="display: flex; align-items: center; justify-content: flex-end; gap: 1rem; border-top: 1px solid var(--border-subtle); padding-top: 1.5rem;">
          <button type="button" class="btn btn-secondary" id="btn-cancel-new-space">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary" id="btn-submit-space">
            <span>Register & Analyze Space →</span>
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
  const progressContainer = document.getElementById('form-progress-container');
  const submitBtn = document.getElementById('btn-submit-space');

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorContainer.innerHTML = '';

    const name = document.getElementById('input-space-name').value.trim();
    const brand = document.getElementById('input-brand').value.trim();
    const businessType = document.getElementById('input-business-type').value;
    const city = document.getElementById('input-city').value.trim();
    const country = document.getElementById('input-country').value.trim();
    const address = document.getElementById('input-address').value.trim();
    const coordsStr = document.getElementById('input-coordinates').value.trim();
    const radiusMeters = parseInt(document.getElementById('input-radius').value, 10) || 2000;
    const targetAudience = document.getElementById('input-target-audience').value.trim();
    const positioning = document.getElementById('input-positioning').value.trim();
    const goals = document.getElementById('input-goals').value.trim();
    const budget = document.getElementById('input-budget').value.trim();
    const desiredMood = document.getElementById('input-desired-mood').value.trim();
    const culturalPrefs = document.getElementById('input-cultural-preferences').value.trim();
    const constraints = document.getElementById('input-constraints').value.trim();
    const rawAnchors = document.getElementById('input-anchor-entities').value.trim();

    if (!name || !businessType || !city || !country || !desiredMood || !targetAudience || !positioning) {
      errorContainer.innerHTML = renderError({
        title: 'Validation Error',
        error: { detail: 'Please fill in all mandatory fields indicated with *' },
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    // Parse coordinates if provided
    let locationObj = {
      city,
      country,
      address: address || null,
      radius_meters: radiusMeters,
    };

    if (coordsStr) {
      const parts = coordsStr.split(',').map(s => parseFloat(s.trim()));
      if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        locationObj.latitude = parts[0];
        locationObj.longitude = parts[1];
      }
    }

    const anchorEntities = rawAnchors
      ? rawAnchors.split(',').map(s => s.trim()).filter(Boolean)
      : [];

    const goalsList = goals
      ? goals.split(';').map(s => s.trim()).filter(Boolean)
      : [];

    const constraintsList = constraints
      ? constraints.split(';').map(s => s.trim()).filter(Boolean)
      : [];

    const culturalPrefsList = culturalPrefs
      ? culturalPrefs.split(',').map(s => s.trim()).filter(Boolean)
      : [];

    const spacePayload = {
      name,
      business_type: businessType,
      brand: brand || null,
      location: locationObj,
      target_audience: targetAudience,
      positioning: positioning,
      goals: goalsList.length > 0 ? goalsList : (goals || null),
      budget: budget || null,
      desired_mood: desiredMood,
      cultural_preferences: culturalPrefsList.length > 0 ? culturalPrefsList : (culturalPrefs || null),
      constraints: constraintsList.length > 0 ? constraintsList : (constraints ? [constraints] : []),
      anchor_entities: anchorEntities,
    };

    submitBtn.disabled = true;
    submitBtn.innerHTML = `
      <span class="spinner" style="width: 14px; height: 14px; margin-right: 0.5rem; display: inline-block;"></span>
      <span>Orchestrating Workflow...</span>
    `;

    progressContainer.style.display = 'block';
    progressContainer.innerHTML = `
      <div class="card" style="padding: 1.5rem; border: 1px solid var(--cyan-subtle); background: rgba(6, 182, 212, 0.04);">
        <div style="display: flex; align-items: center; gap: 1rem;">
          <div class="spinner"></div>
          <div>
            <div style="font-weight: 600; color: var(--text-primary); font-size: 0.95rem;" id="progress-step-title">
              Step 1 of 2: Creating Activation Session Brief (POST /api/v1/sessions)...
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted);" id="progress-step-desc">
              Establishing spatial coordinates, cultural brief, and anchor parameters.
            </div>
          </div>
        </div>
      </div>
    `;

    try {
      // 1. Create space & session
      const space = await apiClient.createSpace(spacePayload);

      // Update progress for Step 2
      const stepTitle = document.getElementById('progress-step-title');
      const stepDesc = document.getElementById('progress-step-desc');
      if (stepTitle) {
        stepTitle.textContent = `Step 2 of 2: Orchestrating Cultural Pipeline (POST /api/v1/sessions/{id}/pipeline)...`;
      }
      if (stepDesc) {
        stepDesc.textContent = `Resolving empirical Qloo signals, creating Cultural Twin, and driving pipeline to Approval Gate...`;
      }

      // 2. POST /spaces/{space_id}/analyze
      const session = await apiClient.analyzeSpace(space.space_id, {
        auto_run: true,
        take_per_category: 10,
      });

      showToast(`Space registered and pipeline analyzed! Redirecting to Session Workspace...`, 'success');

      // 3. session page
      router.navigate(`/sessions/${session.session_id}`);
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Register & Analyze Space →</span>';
      progressContainer.style.display = 'none';

      errorContainer.innerHTML = renderError({
        title: 'New Space Workflow Execution Failed',
        error: err,
        retryId: 'btn-retry-form-submit',
      });

      window.scrollTo({ top: 0, behavior: 'smooth' });

      document.getElementById('btn-retry-form-submit')?.addEventListener('click', () => {
        form.dispatchEvent(new Event('submit'));
      });
    }
  });
}
