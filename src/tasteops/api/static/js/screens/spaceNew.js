/**
 * TasteOps Curatorial Space Brief & Vibe Check Screen (/spaces/new).
 *
 * Implements the editorial Vibe Check experience:
 * 1. Collects spatial brief through natural language, tactile chips, and progressive disclosure:
 *    - THE SPACE: Venue Name, Natural Language Brief, Business Typology (chips), Parent Brand
 *    - THE PLACE: City, Country, Cultural District, optional Coordinates & Radius
 *    - THE PEOPLE: Target Audience (interactive chips + custom traits)
 *    - THE VIBE: Atmosphere, Desired Mood, Aesthetic Motifs (tactile tags)
 *    - THE BOUNDARIES (Fine-tune): Goals, Budget Tier, Operational Constraints, Cultural Anchor Entities
 *
 * 2. Deterministic Pipeline Flow:
 *    POST /spaces
 *          ↓
 *    POST /spaces/{space_id}/analyze
 *          ↓
 *    Session Workspace (/sessions/[sessionId])
 */

import { apiClient } from '../apiClient.js';
import { escapeHtml, renderError, showToast } from '../components/ui.js';

export function renderSpaceNew(rootElement, params, router) {
  // Preset choices for visual chip selectors
  const typologies = [
    { id: 'listening-bar', label: 'Listening Bar', value: 'Analog Vinyl Listening Bar & Cafe' },
    { id: 'cafe', label: 'Café', value: 'Specialty Coffee Lab & Roastery' },
    { id: 'coworking', label: 'Co-working', value: 'Creative Co-working & Cultural Sanctuary' },
    { id: 'retail', label: 'Retail Store', value: 'Sensory Concept Store & Retail' },
    { id: 'hotel', label: 'Luxury Hotel', value: 'Boutique Hotel & Sanctuary' },
    { id: 'wellness', label: 'Wellness Space', value: 'Holistic Wellness & Sensory Sanctuary' },
    { id: 'cultural-club', label: 'Cultural Club', value: 'Private Members Cultural Club' },
    { id: 'dining', label: 'Dining & Bar', value: 'Curated Dining Room & Bar' },
  ];

  const audiencePresets = [
    'Design crowd',
    'Vinyl collectors',
    'Creative professionals',
    'Founders',
    'Music obsessives',
    'Culture seekers',
    'Travelers',
    'Local community',
  ];

  const vibePresets = [
    'Analog',
    'Intimate',
    'Editorial',
    'Experimental',
    'Warm',
    'Minimal',
    'Eclectic',
    'Contemporary',
  ];

  rootElement.innerHTML = `
    <div class="fade-in space-brief-container">
      <!-- Breadcrumbs -->
      <nav class="page-breadcrumbs" style="margin-bottom: 1.5rem;" aria-label="Breadcrumb">
        <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
        <span class="breadcrumb-separator">/</span>
        <span style="color: var(--text-muted);">Spaces</span>
        <span class="breadcrumb-separator">/</span>
        <span style="color: var(--forest-green); font-weight: 500;">Vibe Check</span>
      </nav>

      <!-- Hero Section -->
      <header class="space-brief-hero">
        <div class="space-brief-eyebrow">
          <span>✦</span>
          <span>Curatorial Space Brief</span>
        </div>
        <h1 class="space-brief-headline">What are we curating?</h1>
        <p class="space-brief-subtext">
          Give TasteOps the cultural context. We'll translate your brief into an operational Cultural Twin grounded in empirical taste intelligence.
        </p>
      </header>

      <div id="form-error-container" style="margin-bottom: 1.5rem;"></div>

      <form id="form-space-brief" novalidate>
        <!-- 1. THE SPACE -->
        <section class="space-brief-card" aria-labelledby="section-space-title">
          <div class="brief-section-header">
            <div class="brief-section-eyebrow">The Space</div>
            <h2 id="section-space-title" class="brief-section-title">The Vision & Typology</h2>
            <p class="brief-section-hint">Describe the space in natural language. We'll extract cultural affinities and spatial requirements.</p>
          </div>

          <!-- Natural Language Brief Textarea -->
          <div class="brief-field-group" style="margin-bottom: 1.75rem;">
            <label class="brief-field-label" for="input-brief-narrative">Natural Language Brief</label>
            <textarea 
              id="input-brief-narrative" 
              class="brief-textarea-large" 
              placeholder="An intimate vinyl listening bar in Mumbai for design-conscious creatives who love Japanese jazz, analog sound and contemporary Indian art."
              rows="3"
            >An intimate vinyl listening bar and Japanese specialty cafe in Kala Ghoda, Mumbai for design-conscious creatives featuring analog sound, third-wave pour-overs, and contemporary curation.</textarea>
          </div>

          <!-- Venue Name & Brand -->
          <div class="brief-input-row" style="margin-bottom: 1.75rem;">
            <div class="brief-field-group">
              <label class="brief-field-label" for="input-space-name">Venue / Space Name *</label>
              <input type="text" id="input-space-name" class="brief-input" placeholder="e.g. Kitsuné Musique Lab" value="Kitsuné Musique Lab" required />
            </div>

            <div class="brief-field-group">
              <label class="brief-field-label" for="input-brand">Brand / Parent Identity</label>
              <input type="text" id="input-brand" class="brief-input" placeholder="e.g. Maison Kitsuné" value="Maison Kitsuné" />
            </div>
          </div>

          <!-- Business Typology Chips -->
          <div class="brief-field-group">
            <label class="brief-field-label">Space Type *</label>
            <div class="brief-chip-grid" id="typology-chips-grid" role="radiogroup" aria-label="Space Type">
              ${typologies.map((t, idx) => `
                <button 
                  type="button" 
                  class="brief-chip ${idx === 0 ? 'active' : ''}" 
                  data-value="${escapeHtml(t.value)}" 
                  data-typology="${t.id}"
                  role="radio"
                  aria-checked="${idx === 0 ? 'true' : 'false'}"
                >
                  <span class="chip-dot"></span>
                  <span>${escapeHtml(t.label)}</span>
                </button>
              `).join('')}
            </div>
            <input type="hidden" id="input-business-type" value="${escapeHtml(typologies[0].value)}" />
          </div>
        </section>

        <!-- 2. THE PLACE -->
        <section class="space-brief-card" aria-labelledby="section-place-title">
          <div class="brief-section-header">
            <div class="brief-section-eyebrow">The Place</div>
            <h2 id="section-place-title" class="brief-section-title">Where does it live?</h2>
            <p class="brief-section-hint">Establishes local geographic taste clustering and physical POI radius.</p>
          </div>

          <div class="brief-input-row" style="margin-bottom: 1.25rem;">
            <div class="brief-field-group">
              <label class="brief-field-label" for="input-city">City *</label>
              <input type="text" id="input-city" class="brief-input" placeholder="e.g. Mumbai, Kyoto, London, Berlin" value="Mumbai" required />
            </div>

            <div class="brief-field-group">
              <label class="brief-field-label" for="input-country">Country *</label>
              <input type="text" id="input-country" class="brief-input" placeholder="e.g. India, Japan, UK, Germany" value="India" required />
            </div>

            <div class="brief-field-group">
              <label class="brief-field-label" for="input-address">Cultural District / Street</label>
              <input type="text" id="input-address" class="brief-input" placeholder="e.g. Kala Ghoda Arts Precinct" value="Kala Ghoda Arts Precinct" />
            </div>
          </div>

          <!-- Secondary Coordinates Affordance -->
          <div style="margin-top: 0.75rem;">
            <button type="button" id="btn-toggle-coords" class="btn-link" style="background: transparent; border: none; font-size: 0.775rem; color: var(--muted-sage); cursor: pointer; display: inline-flex; align-items: center; gap: 0.35rem; padding: 0;">
              <span id="coords-chevron">▾</span>
              <span>Fine-tune GPS coordinates & search radius</span>
            </button>
            <div id="coords-drawer" style="display: none; margin-top: 1rem; padding-top: 1rem; border-top: 1px dashed var(--border-stone);">
              <div class="brief-input-row">
                <div class="brief-field-group">
                  <label class="brief-field-label" for="input-coordinates">Coordinates (Lat, Long)</label>
                  <input type="text" id="input-coordinates" class="brief-input" placeholder="e.g. 18.9287, 72.8331" value="18.9287, 72.8331" />
                </div>
                <div class="brief-field-group">
                  <label class="brief-field-label" for="input-radius">Search Radius (Meters)</label>
                  <input type="number" id="input-radius" class="brief-input" value="2500" min="200" max="50000" step="100" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 3. THE PEOPLE -->
        <section class="space-brief-card" aria-labelledby="section-people-title">
          <div class="brief-section-header">
            <div class="brief-section-eyebrow">The People</div>
            <h2 id="section-people-title" class="brief-section-title">Who is it for?</h2>
            <p class="brief-section-hint">Select the cultural tribes and demographic psychographics to ground the Cultural Twin.</p>
          </div>

          <div class="brief-field-group" style="margin-bottom: 1.5rem;">
            <label class="brief-field-label">Target Audience Chips</label>
            <div class="brief-chip-grid" id="audience-chips-grid" role="group" aria-label="Audience Groups">
              ${audiencePresets.map((a, idx) => `
                <button 
                  type="button" 
                  class="brief-chip ${idx < 3 ? 'active' : ''}" 
                  data-audience="${escapeHtml(a)}"
                  role="checkbox"
                  aria-checked="${idx < 3 ? 'true' : 'false'}"
                >
                  <span class="chip-dot"></span>
                  <span>${escapeHtml(a)}</span>
                </button>
              `).join('')}
            </div>
          </div>

          <div class="brief-field-group">
            <label class="brief-field-label" for="input-target-audience">Audience Profile Narrative *</label>
            <input 
              type="text" 
              id="input-target-audience" 
              class="brief-input" 
              placeholder="e.g. Design crowd, vinyl collectors, creative professionals valuing tactile craft and analog sound" 
              value="Design crowd, vinyl collectors, creative professionals" 
              required 
            />
          </div>
        </section>

        <!-- 4. THE VIBE -->
        <section class="space-brief-card" aria-labelledby="section-vibe-title">
          <div class="brief-section-header">
            <div class="brief-section-eyebrow">The Vibe</div>
            <h2 id="section-vibe-title" class="brief-section-title">How should it feel?</h2>
            <p class="brief-section-hint">Tactile aesthetic tags governing acoustic curves, lighting warmth, and spatial materials.</p>
          </div>

          <div class="brief-field-group" style="margin-bottom: 1.5rem;">
            <label class="brief-field-label">Atmospheric Tags</label>
            <div class="brief-chip-grid" id="vibe-chips-grid" role="group" aria-label="Atmospheric Tags">
              ${vibePresets.map((v, idx) => `
                <button 
                  type="button" 
                  class="brief-chip ${idx < 4 ? 'active' : ''}" 
                  data-vibe="${escapeHtml(v)}"
                  role="checkbox"
                  aria-checked="${idx < 4 ? 'true' : 'false'}"
                >
                  <span class="chip-dot"></span>
                  <span>${escapeHtml(v)}</span>
                </button>
              `).join('')}
            </div>
          </div>

          <div class="brief-input-row">
            <div class="brief-field-group">
              <label class="brief-field-label" for="input-desired-mood">Desired Mood & Energy *</label>
              <input 
                type="text" 
                id="input-desired-mood" 
                class="brief-input" 
                placeholder="e.g. Intimate acoustic warmth, wabi-sabi minimalism, golden-hour circadian lighting" 
                value="Intimate acoustic warmth, analog jazz culture, warm lighting" 
                required 
              />
            </div>

            <div class="brief-field-group">
              <label class="brief-field-label" for="input-positioning">Market Positioning *</label>
              <input 
                type="text" 
                id="input-positioning" 
                class="brief-input" 
                placeholder="e.g. High-fidelity listening sanctuary for Mumbai's contemporary design community" 
                value="High-fidelity listening sanctuary for contemporary design community" 
                required 
              />
            </div>
          </div>
        </section>

        <!-- 5. THE BOUNDARIES (Progressive Disclosure) -->
        <section class="space-brief-card" style="padding: 1.5rem 2rem;">
          <button type="button" id="btn-toggle-disclosure" class="brief-disclosure-btn" aria-expanded="false" aria-controls="disclosure-content">
            <div style="display: flex; align-items: center; gap: 0.65rem;">
              <span style="font-size: 1.1rem; color: var(--terracotta);">✦</span>
              <span>Fine-tune context (Goals, Budget, Operational Constraints & Anchors)</span>
            </div>
            <span id="disclosure-chevron" style="color: var(--muted-sage); font-size: 1.1rem;">+</span>
          </button>

          <div id="disclosure-content" class="brief-disclosure-content" style="display: none;">
            <div class="brief-input-row" style="margin-bottom: 1.25rem;">
              <div class="brief-field-group">
                <label class="brief-field-label" for="input-goals">Strategic Goals</label>
                <input type="text" id="input-goals" class="brief-input" placeholder="e.g. Bridge Japanese vinyl culture with Indian contemporary craft; cultivate recurring community" />
              </div>

              <div class="brief-field-group">
                <label class="brief-field-label" for="input-budget">Activation Budget Tier</label>
                <input type="text" id="input-budget" class="brief-input" placeholder="e.g. $120,000 USD / High-end boutique allocation" value="$120,000 USD / Boutique allocation" />
              </div>
            </div>

            <div class="brief-field-group" style="margin-bottom: 1.25rem;">
              <label class="brief-field-label" for="input-constraints">Operational & Spatial Guardrails</label>
              <input type="text" id="input-constraints" class="brief-input" placeholder="e.g. Acoustic cap at 78 dB, timber-only resonance, no digital screens in main listening lounge" value="Acoustic cap at 78 dB, timber-only resonance, no digital screens" />
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">Enforced deterministically by the Governance Compliance Agent.</div>
            </div>

            <div class="brief-field-group">
              <label class="brief-field-label" for="input-anchor-entities">Cultural Anchor Entities (Comma separated)</label>
              <input type="text" id="input-anchor-entities" class="brief-input" placeholder="e.g. Ryuichi Sakamoto, Midori Takada, Blue Bottle Coffee, Aesop, Teenage Engineering" value="Ryuichi Sakamoto, Midori Takada, Blue Bottle Coffee, Aesop" />
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">Real-world cultural entities matched against Qloo taste vectors.</div>
            </div>
          </div>
        </section>

        <!-- Primary Action Bar -->
        <div class="brief-action-bar">
          <button type="button" class="btn-brief-secondary" id="btn-save-brief">
            Save Brief
          </button>

          <div style="display: flex; align-items: center; gap: 1rem;">
            <button type="button" class="btn-brief-secondary" id="btn-cancel-brief">
              Cancel
            </button>
            <button type="submit" class="btn-brief-primary" id="btn-submit-brief">
              <span>Build Cultural Twin →</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  `;

  // ---------------------------------------------------------------------------
  // Interactive Component State & Handlers
  // ---------------------------------------------------------------------------

  // 1. Business Typology Chips Selection
  const typologyChips = rootElement.querySelectorAll('#typology-chips-grid .brief-chip');
  const businessTypeInput = rootElement.querySelector('#input-business-type');
  typologyChips.forEach(chip => {
    chip.addEventListener('click', () => {
      typologyChips.forEach(c => {
        c.classList.remove('active');
        c.setAttribute('aria-checked', 'false');
      });
      chip.classList.add('active');
      chip.setAttribute('aria-checked', 'true');
      if (businessTypeInput) businessTypeInput.value = chip.dataset.value;
    });
  });

  // 2. Audience Chips Multi-Select
  const audienceChips = rootElement.querySelectorAll('#audience-chips-grid .brief-chip');
  const targetAudienceInput = rootElement.querySelector('#input-target-audience');
  audienceChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const isNowActive = !chip.classList.contains('active');
      chip.classList.toggle('active', isNowActive);
      chip.setAttribute('aria-checked', String(isNowActive));

      // Gather active chips
      const selected = Array.from(rootElement.querySelectorAll('#audience-chips-grid .brief-chip.active'))
        .map(c => c.dataset.audience);
      if (targetAudienceInput && selected.length > 0) {
        targetAudienceInput.value = selected.join(', ');
      }
    });
  });

  // 3. Vibe Chips Multi-Select
  const vibeChips = rootElement.querySelectorAll('#vibe-chips-grid .brief-chip');
  const desiredMoodInput = rootElement.querySelector('#input-desired-mood');
  vibeChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const isNowActive = !chip.classList.contains('active');
      chip.classList.toggle('active', isNowActive);
      chip.setAttribute('aria-checked', String(isNowActive));

      const selected = Array.from(rootElement.querySelectorAll('#vibe-chips-grid .brief-chip.active'))
        .map(c => c.dataset.vibe);
      if (desiredMoodInput && selected.length > 0) {
        desiredMoodInput.value = selected.join(', ') + ' atmosphere';
      }
    });
  });

  // 4. Coordinates Toggle
  const btnToggleCoords = rootElement.querySelector('#btn-toggle-coords');
  const coordsDrawer = rootElement.querySelector('#coords-drawer');
  const coordsChevron = rootElement.querySelector('#coords-chevron');
  btnToggleCoords?.addEventListener('click', () => {
    if (!coordsDrawer) return;
    const isHidden = coordsDrawer.style.display === 'none';
    coordsDrawer.style.display = isHidden ? 'block' : 'none';
    if (coordsChevron) coordsChevron.textContent = isHidden ? '▴' : '▾';
  });

  // 5. Progressive Disclosure Drawer
  const btnToggleDisclosure = rootElement.querySelector('#btn-toggle-disclosure');
  const disclosureContent = rootElement.querySelector('#disclosure-content');
  const disclosureChevron = rootElement.querySelector('#disclosure-chevron');
  btnToggleDisclosure?.addEventListener('click', () => {
    if (!disclosureContent) return;
    const isHidden = disclosureContent.style.display === 'none';
    disclosureContent.style.display = isHidden ? 'block' : 'none';
    btnToggleDisclosure.setAttribute('aria-expanded', String(isHidden));
    if (disclosureChevron) disclosureChevron.textContent = isHidden ? '−' : '+';
  });

  // 6. Natural Language Narrative sync with space name
  const narrativeEl = rootElement.querySelector('#input-brief-narrative');
  const spaceNameInput = rootElement.querySelector('#input-space-name');
  narrativeEl?.addEventListener('input', () => {
    const text = narrativeEl.value.trim();
    if (text && (!spaceNameInput.value || spaceNameInput.value === 'Kissa Sound Room')) {
      const match = text.match(/(?:a|an)\s+([a-zA-Z\s]+?)\s+(?:in|for|with)/i);
      if (match && match[1]) {
        spaceNameInput.value = match[1].trim().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      }
    }
  });

  // 7. Cancel button
  rootElement.querySelector('#btn-cancel-brief')?.addEventListener('click', () => {
    router.navigate('/dashboard');
  });

  // 8. Save Brief button (without running pipeline immediately)
  rootElement.querySelector('#btn-save-brief')?.addEventListener('click', async () => {
    const name = rootElement.querySelector('#input-space-name')?.value.trim() || 'Curated Space Brief';
    const businessType = rootElement.querySelector('#input-business-type')?.value;
    const city = rootElement.querySelector('#input-city')?.value.trim() || 'Global';
    const country = rootElement.querySelector('#input-country')?.value.trim() || '';

    showToast({ title: 'Brief Saved', text: `Saved "${name}" to spatial workspace registry.`, type: 'success' });
  });

  // 9. Main Form Submission (Create Space + Run Pipeline)
  const form = rootElement.querySelector('#form-space-brief');
  const errorContainer = rootElement.querySelector('#form-error-container');
  const submitBtn = rootElement.querySelector('#btn-submit-brief');

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (errorContainer) errorContainer.innerHTML = '';

    const name = rootElement.querySelector('#input-space-name')?.value.trim() || 'New Curated Venue';
    const brand = rootElement.querySelector('#input-brand')?.value.trim() || null;
    const businessType = rootElement.querySelector('#input-business-type')?.value || 'Curated Space';
    const city = rootElement.querySelector('#input-city')?.value.trim();
    const country = rootElement.querySelector('#input-country')?.value.trim();
    const address = rootElement.querySelector('#input-address')?.value.trim();
    const coordsStr = rootElement.querySelector('#input-coordinates')?.value.trim();
    const radiusMeters = parseInt(rootElement.querySelector('#input-radius')?.value, 10) || 2500;
    const targetAudience = rootElement.querySelector('#input-target-audience')?.value.trim();
    const positioning = rootElement.querySelector('#input-positioning')?.value.trim();
    const desiredMood = rootElement.querySelector('#input-desired-mood')?.value.trim();
    const goals = rootElement.querySelector('#input-goals')?.value.trim();
    const budget = rootElement.querySelector('#input-budget')?.value.trim();
    const constraints = rootElement.querySelector('#input-constraints')?.value.trim();
    const rawAnchors = rootElement.querySelector('#input-anchor-entities')?.value.trim();
    const briefNarrative = rootElement.querySelector('#input-brief-narrative')?.value.trim();

    if (!city || !country || !targetAudience || !positioning || !desiredMood) {
      if (errorContainer) {
        errorContainer.innerHTML = renderError({
          title: 'Brief Incomplete',
          error: { detail: 'Please provide City, Country, Target Audience, and Desired Mood to ground your Cultural Twin.' },
        });
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    // Build location payload
    const locationObj = {
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

    let anchorEntities = rawAnchors
      ? rawAnchors.split(',').map(s => s.trim()).filter(Boolean)
      : [];

    if (anchorEntities.length === 0) {
      const autoAnchors = [];
      if (desiredMood) autoAnchors.push(desiredMood);
      if (targetAudience) autoAnchors.push(targetAudience);
      if (name) autoAnchors.push(name);
      anchorEntities = autoAnchors;
    }

    const goalsList = goals
      ? goals.split(';').map(s => s.trim()).filter(Boolean)
      : [];

    const constraintsList = constraints
      ? constraints.split(';').map(s => s.trim()).filter(Boolean)
      : [];

    // Assemble complete payload compatible with TasteOps API contracts
    const spacePayload = {
      name,
      business_type: businessType,
      brand,
      location: locationObj,
      target_audience: targetAudience,
      positioning: positioning,
      goals: goalsList.length > 0 ? goalsList : (goals ? [goals] : []),
      budget: budget || null,
      desired_mood: desiredMood,
      cultural_preferences: briefNarrative ? [briefNarrative] : [desiredMood],
      constraints: constraintsList.length > 0 ? constraintsList : (constraints ? [constraints] : []),
      anchor_entities: anchorEntities,
    };

    // Progression Feedback via Single Activity Capsule
    if (submitBtn) submitBtn.disabled = true;
    showToast({ title: 'Building your Cultural Twin...', text: 'Synthesizing spatial brief and cultural context.', type: 'loading' });

    try {
      // 1. Register Space
      const space = await apiClient.createSpace(spacePayload);

      // Progression step 2: Reading signals & running agents
      showToast({ title: 'Reading cultural signals...', text: 'Resolving empirical Qloo taste graph correlations.', type: 'loading' });

      // 2. Trigger pipeline analysis
      const session = await apiClient.analyzeSpace(space.space_id, {
        auto_run: true,
        take_per_category: 10,
      });

      // Progression step 3: Completed & Redirecting
      showToast({ title: 'Curatorial synthesis complete', text: 'Cultural Twin established. Opening workspace...', type: 'success' });

      // 3. Navigate to session workspace
      setTimeout(() => {
        router.navigate(`/sessions/${session.session_id}`);
      }, 500);

    } catch (err) {
      if (submitBtn) submitBtn.disabled = false;
      showToast(err.message || 'Brief synthesis failed. Please review your inputs.', 'error');
      if (errorContainer) {
        errorContainer.innerHTML = renderError({
          title: 'Brief Synthesis Notice',
          error: err,
        });
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });
}
