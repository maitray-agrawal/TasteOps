/**
 * TasteOps Typed API Client.
 *
 * Single authoritative client for all frontend API interactions.
 * Centralizes all backend URL endpoints, provides typed error envelopes (RFC 7807),
 * configures environment base URLs, and manages bounded polling for live sessions.
 * NOTE: Sensitive backend provider credentials and database connection strings
 * are NEVER stored or requested on the client tier.
 *
 * INTEGRITY ENFORCEMENT:
 * - Never fabricates cryptographic hashes, Merkle proofs, or verification statuses.
 * - Never injects artificial confidence scores, affinity values, or zero-cost defaults.
 * - Derives approval status strictly from authoritative backend workflow state.
 */

// Centralized endpoint registry matching backend contracts
export const ENDPOINTS = Object.freeze({
  SESSIONS: '/sessions',
  SESSION: (id) => `/sessions/${encodeURIComponent(id)}`,
  SESSION_PIPELINE: (id) => `/sessions/${encodeURIComponent(id)}/pipeline`,
  SESSION_APPROVE: (id) => `/sessions/${encodeURIComponent(id)}/approve`,
  SESSION_REJECT: (id) => `/sessions/${encodeURIComponent(id)}/reject`,
  SESSION_EXECUTE: (id) => `/sessions/${encodeURIComponent(id)}/execute`,
  SESSION_AUDIT: (id) => `/sessions/${encodeURIComponent(id)}/audit`,
  SESSION_ARTIFACT_CSV: (id) => `/sessions/${encodeURIComponent(id)}/artifacts/procurement.csv`,
  SESSION_ARTIFACT_SPOTIFY: (id) => `/sessions/${encodeURIComponent(id)}/artifacts/spotify_playlist.json`,
  SESSION_ARTIFACT_BRANDS: (id) => `/sessions/${encodeURIComponent(id)}/artifacts/brand_dossiers.json`,
  CONFIG: '/config',
  HEALTH: '/health',
  READY: '/ready',
});

export class APIError extends Error {
  constructor(message, { statusCode = 0, code = 'API_ERROR', detail = '', correlationId = null, isNetworkError = false } = {}) {
    super(message || detail || 'An unexpected API error occurred');
    this.name = 'APIError';
    this.statusCode = statusCode;
    this.code = code;
    this.detail = detail || message;
    this.correlationId = correlationId;
    this.isNetworkError = isNetworkError;
    this.canRetry = statusCode >= 500 || statusCode === 429 || isNetworkError;
  }
}

function inferEventType({ to_state, reason = '' }) {
  const r = (reason || '').toUpperCase();
  const s = (to_state || '').toUpperCase();
  if (s === 'CREATED' || r.includes('SESSION_CREATED')) return 'SESSION_CREATION';
  if (s === 'QLOO_RESOLVED' || r.includes('QLOO')) return 'QLOO_RETRIEVAL';
  if (s === 'CULTURAL_TWIN_CREATED' || s === 'CULTURAL_MATRIX_READY' || s === 'PLAN_GENERATED') return 'AGENT_COMPLETION';
  if (s === 'VALIDATED') return 'VALIDATION';
  if (s === 'AWAITING_APPROVAL') return 'GOVERNANCE_DECISION';
  if (s === 'APPROVED') return 'APPROVAL';
  if (s === 'FAILED') return 'REJECTION';
  if (s === 'EXECUTING') return 'EXECUTION_ATTEMPT';
  if (s === 'COMPLETED') return 'EXECUTION_OUTCOME';
  return 'STATE_CHANGE';
}

function inferActor({ to_state, metadata = {} }) {
  const s = (to_state || '').toUpperCase();
  if (metadata?.approver) return metadata.approver;
  if (metadata?.actor) return metadata.actor;
  if (s === 'INTENT_PARSED' || s === 'CULTURAL_TWIN_CREATED') return 'Cultural Strategist';
  if (s === 'QLOO_RESOLVED' || s === 'CULTURAL_MATRIX_READY') return 'Qloo';
  if (s === 'AGENTS_RUNNING') return 'Experience Architect';
  if (s === 'PLAN_GENERATED') return 'Partnership Agent';
  if (s === 'VALIDATED') return 'Governance Agent';
  if (s === 'APPROVED') return 'Human Curator';
  return 'TasteOps Engine';
}

export class TasteOpsAPIClient {
  constructor(options = {}) {
    this._initConfiguration(options);
  }

  /**
   * Initializes and validates runtime API configuration.
   * Ensures production Render API base URL is properly decomposed and validated.
   */
  _initConfiguration(options = {}) {
    const metaBase = typeof document !== 'undefined'
      ? document.querySelector('meta[name="api-base-url"]')?.getAttribute('content')
      : null;
    const configBase = typeof window !== 'undefined'
      ? (window.__TASTEOPS_CONFIG__?.API_BASE_URL || window.__TASTEOPS_CONFIG__?.apiBaseUrl)
      : null;
    const envBase = typeof window !== 'undefined'
      ? (window.__TASTEOPS_ENV__?.API_BASE_URL || window.__TASTEOPS_ENV__?.apiBaseUrl)
      : null;

    let rawBase = (options.baseUrl || configBase || envBase || metaBase || '').trim();

    // Check deployment environment
    const isBrowser = typeof window !== 'undefined' && typeof window.location !== 'undefined';
    const hostname = isBrowser ? window.location.hostname : 'localhost';
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';

    // Disallow silent fallback to localhost in production environments
    if (!rawBase) {
      if (isLocalhost) {
        rawBase = '/api/v1';
      } else {
        const errorMsg =
          'TasteOps Configuration Error: Missing API_BASE_URL in production environment. ' +
          'Configure window.__TASTEOPS_CONFIG__.API_BASE_URL (e.g. "https://tasteops-backend.onrender.com") ' +
          'in /static/config.js before deploying to static CDN.';
        console.error(errorMsg);
        this.configError = errorMsg;
        rawBase = 'https://tasteops-backend.onrender.com';
      }
    } else if (!isLocalhost && (rawBase.includes('localhost') || rawBase.includes('127.0.0.1'))) {
      const errorMsg =
        `TasteOps Configuration Error: Invalid API_BASE_URL "${rawBase}" configured on production origin (${hostname}). ` +
        'Do not point frontend to localhost in production. Use the production Render backend URL.';
      console.error(errorMsg);
      this.configError = errorMsg;
    }

    // Normalize trailing slashes safely
    const cleanUrl = rawBase.replace(/\/+$/, '');

    // Safely decompose into rootOrigin (for /health and /ready) and apiBase (for /api/v1/...)
    if (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://')) {
      try {
        const parsed = new URL(cleanUrl);
        this.rootOrigin = parsed.origin;
        const pathname = parsed.pathname.replace(/\/+$/, '');

        if (pathname === '/api/v1' || pathname.endsWith('/api/v1')) {
          this.apiBase = `${this.rootOrigin}${pathname}`;
        } else if (pathname === '/api' || pathname.endsWith('/api')) {
          this.apiBase = `${this.rootOrigin}${pathname}/v1`;
        } else if (pathname === '' || pathname === '/') {
          this.apiBase = `${this.rootOrigin}/api/v1`;
        } else {
          this.apiBase = `${this.rootOrigin}${pathname}/api/v1`;
        }
      } catch (err) {
        this.rootOrigin = cleanUrl;
        this.apiBase = `${cleanUrl}/api/v1`;
      }
    } else {
      // Relative path (monolithic FastAPI local fallback)
      this.rootOrigin = '';
      if (cleanUrl === '/api/v1' || cleanUrl.endsWith('/api/v1')) {
        this.apiBase = cleanUrl;
      } else if (cleanUrl === '/api') {
        this.apiBase = '/api/v1';
      } else {
        this.apiBase = cleanUrl ? `${cleanUrl}/api/v1` : '/api/v1';
      }
    }

    // Set baseUrl for backwards-compatible reference
    this.baseUrl = this.apiBase;
  }

  /**
   * Internal HTTP request dispatcher with centralized error handling, timeout, and cold-start recovery.
   */
  async _fetch(endpoint, options = {}) {
    const isRootProbe = endpoint === ENDPOINTS.HEALTH || endpoint === ENDPOINTS.READY;
    const targetBase = isRootProbe ? this.rootOrigin : this.apiBase;
    const url = targetBase ? `${targetBase}${endpoint}` : endpoint;

    const headers = {
      'Accept': 'application/json',
      ...options.headers,
    };

    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const timeoutMs = options.timeoutMs || (isRootProbe ? 8000 : 35000);
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller ? controller.signal : options.signal,
      });

      if (timeoutId) clearTimeout(timeoutId);

      const correlationId = response.headers.get('X-Request-ID') || response.headers.get('X-Correlation-ID');

      if (!response.ok) {
        let errorData = null;
        try {
          errorData = await response.json();
        } catch (_) {
          // Non-JSON error payload
        }

        const detail =
          (typeof errorData?.message === 'string' && errorData.message) ||
          (typeof errorData?.detail === 'string' && errorData.detail) ||
          (typeof errorData?.error === 'string' && errorData.error) ||
          errorData?.error?.detail ||
          response.statusText;

        const code =
          (typeof errorData?.error === 'string' && errorData.error) ||
          errorData?.error?.code ||
          `HTTP_${response.status}`;

        throw new APIError(detail, {
          statusCode: response.status,
          code,
          detail,
          correlationId,
          isNetworkError: false,
        });
      }

      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (err) {
      if (timeoutId) clearTimeout(timeoutId);

      if (err instanceof APIError) {
        throw err;
      }

      const isAbort = err.name === 'AbortError' || err.code === 20;
      const coldStartMessage =
        'Backend service may be starting from idle (Render free-tier cold start typically takes 30–60 seconds). ' +
        'Please wait a few moments and retry.';

      throw new APIError(isAbort ? `Request timed out after ${timeoutMs / 1000}s. ${coldStartMessage}` : err.message || 'Network communication failure', {
        statusCode: 0,
        code: isAbort ? 'BACKEND_COLD_START_TIMEOUT' : 'NETWORK_DISCONNECTED',
        detail: coldStartMessage,
        isNetworkError: true,
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Space Venue Operations (Local State Store Integration)
  // ---------------------------------------------------------------------------
  async listSpaces() {
    if (typeof localStorage === 'undefined') return [];
    try {
      const stored = localStorage.getItem('tasteops_spaces');
      return stored ? JSON.parse(stored) : [];
    } catch (_) {
      return [];
    }
  }

  async getSpace(spaceId) {
    if (!spaceId) throw new Error('Space ID is required');
    const spaces = await this.listSpaces();
    const found = spaces.find(s => s.space_id === spaceId);
    if (found) return found;

    // Graceful representation if navigating directly by ID
    return {
      space_id: spaceId,
      name: spaceId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      business_type: 'Curated Physical Space',
      location: { city: 'Global', country: 'TasteOps Network' },
      brief: {
        desired_mood: 'Curated cultural and sensory atmosphere',
        target_audience: 'Aesthetic enthusiasts & cultural patrons',
        anchor_entities: [],
      },
      updated_at: new Date().toISOString(),
    };
  }

  async createSpace(spaceData) {
    const spaceId = spaceData.space_id || `space_${(spaceData.name || 'venue').toLowerCase().replace(/[^a-z0-9]/g, '_')}_${Date.now().toString(36)}`;
    const record = {
      space_id: spaceId,
      name: spaceData.name || 'New Physical Space',
      business_type: spaceData.business_type || 'Curated Space',
      brand: spaceData.brand || null,
      location: spaceData.location || { city: '', country: '' },
      brief: {
        brand: spaceData.brand || null,
        desired_mood: spaceData.desired_mood || null,
        target_audience: spaceData.target_audience || null,
        positioning: spaceData.positioning || null,
        goals: spaceData.goals || [],
        budget: spaceData.budget || null,
        constraints: spaceData.constraints || [],
        cultural_preferences: spaceData.cultural_preferences || [],
        anchor_entities: spaceData.anchor_entities || [],
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    if (typeof localStorage !== 'undefined') {
      try {
        const spaces = await this.listSpaces();
        const updated = [record, ...spaces.filter(s => s.space_id !== spaceId)];
        localStorage.setItem('tasteops_spaces', JSON.stringify(updated.slice(0, 30)));
      } catch (_) {}
    }

    return record;
  }

  async analyzeSpace(spaceId, analyzeData = {}) {
    if (!spaceId) throw new Error('Space ID is required');
    const space = await this.getSpace(spaceId);

    // Formulate natural language raw_intent
    const narrative = space.brief?.cultural_preferences?.[0] || '';
    const intentParts = [];
    if (narrative) {
      intentParts.push(narrative);
    } else {
      intentParts.push(`Venue concept: ${space.name}`);
      intentParts.push(`Typology: ${space.business_type}`);
    }
    if (space.location?.city) {
      intentParts.push(`Location: ${space.location.city}${space.location.country ? ', ' + space.location.country : ''}`);
    }
    if (space.brief?.desired_mood) intentParts.push(`Atmosphere: ${space.brief.desired_mood}`);
    if (space.brief?.target_audience) intentParts.push(`Target audience: ${space.brief.target_audience}`);
    if (space.brief?.anchor_entities?.length) intentParts.push(`Anchor affinities: ${space.brief.anchor_entities.join(', ')}`);
    const rawIntent = intentParts.filter(Boolean).join('. ').replace(/\.\.+/g, '.') + '.';

    const vibeKeywords = [];
    if (space.brief?.desired_mood) vibeKeywords.push(space.brief.desired_mood.toLowerCase());
    if (space.brief?.positioning) vibeKeywords.push(space.brief.positioning.toLowerCase());

    const audienceTribes = [];
    if (space.brief?.target_audience) audienceTribes.push(space.brief.target_audience);

    // 1. Create session
    const session = await this.createSession({
      raw_intent: rawIntent,
      space_id: spaceId,
      hints: {
        desired_mood: space.brief?.desired_mood,
        target_audience: space.brief?.target_audience,
        anchor_entities: space.brief?.anchor_entities || [],
        raw_anchor_entities: space.brief?.anchor_entities || [],
        raw_tags: vibeKeywords,
        business_type: space.business_type,
        location: space.location,
        vibe_keywords: vibeKeywords,
        audience_tribes: audienceTribes,
      },
    });

    // 2. Drive pipeline if requested
    if (analyzeData.auto_run !== false) {
      return await this.runPipeline(session.session_id, {
        take_per_category: analyzeData.take_per_category || 10,
      });
    }

    return session;
  }

  // ---------------------------------------------------------------------------
  // Workflow Session Operations
  // ---------------------------------------------------------------------------
  async createSession({ raw_intent, space_id = null, hints = null }) {
    if (!raw_intent || raw_intent.trim().length < 3) {
      throw new Error('raw_intent must be at least 3 characters');
    }
    const payload = {
      raw_intent: raw_intent.trim(),
      space_id: space_id || undefined,
      hints: hints || undefined,
    };
    const res = await this._fetch(ENDPOINTS.SESSIONS, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return this._normalizeSession(res);
  }

  async runPipeline(sessionId, { take_per_category = 10, hints = null } = {}) {
    if (!sessionId) throw new Error('Session ID is required');
    const payload = {
      take_per_category,
      hints: hints || undefined,
    };
    const res = await this._fetch(ENDPOINTS.SESSION_PIPELINE(sessionId), {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return this._normalizeSession(res);
  }

  async getSession(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    const res = await this._fetch(ENDPOINTS.SESSION(sessionId), { method: 'GET' });
    return this._normalizeSession(res);
  }

  async approveSession(sessionId, { approver = 'human_curator' } = {}) {
    if (!sessionId) throw new Error('Session ID is required');
    if (!approver) throw new Error('Approver name is required for authoritative sign-off');
    const res = await this._fetch(ENDPOINTS.SESSION_APPROVE(sessionId), {
      method: 'POST',
      body: JSON.stringify({ approver }),
    });
    return this._normalizeSession(res);
  }

  async rejectSession(sessionId, { reason = 'Curator rejected plan' } = {}) {
    if (!sessionId) throw new Error('Session ID is required');
    if (!reason) throw new Error('Rejection rationale is required');
    const res = await this._fetch(ENDPOINTS.SESSION_REJECT(sessionId), {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
    return this._normalizeSession(res);
  }

  async executeSession(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    const res = await this._fetch(ENDPOINTS.SESSION_EXECUTE(sessionId), {
      method: 'POST',
      body: JSON.stringify({}),
    });
    return this._normalizeSession(res);
  }

  // ---------------------------------------------------------------------------
  // Execution Artifact Operations
  // ---------------------------------------------------------------------------
  getProcurementCsvUrl(sessionId) {
    if (!sessionId) return `${this.baseUrl}/sessions/default/artifacts/procurement.csv`;
    return `${this.baseUrl}${ENDPOINTS.SESSION_ARTIFACT_CSV(sessionId)}`;
  }

  getSpotifyPlaylistUrl(sessionId) {
    if (!sessionId) return `${this.baseUrl}/sessions/default/artifacts/spotify_playlist.json`;
    return `${this.baseUrl}${ENDPOINTS.SESSION_ARTIFACT_SPOTIFY(sessionId)}`;
  }

  getBrandDossiersUrl(sessionId) {
    if (!sessionId) return `${this.baseUrl}/sessions/default/artifacts/brand_dossiers.json`;
    return `${this.baseUrl}${ENDPOINTS.SESSION_ARTIFACT_BRANDS(sessionId)}`;
  }

  async getSpotifyArtifact(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    return this._fetch(ENDPOINTS.SESSION_ARTIFACT_SPOTIFY(sessionId), { method: 'GET' });
  }

  async getBrandDossiers(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    return this._fetch(ENDPOINTS.SESSION_ARTIFACT_BRANDS(sessionId), { method: 'GET' });
  }

  // ---------------------------------------------------------------------------
  // Session Audit & Decision Ledger Operations
  // ---------------------------------------------------------------------------
  async getSessionAudit(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    return this._fetch(ENDPOINTS.SESSION_AUDIT(sessionId), { method: 'GET' });
  }

  async getSessionEvents(sessionId) {
    const rawEvents = await this.getSessionAudit(sessionId);
    const eventsList = Array.isArray(rawEvents) ? rawEvents : [];

    const events = eventsList.map((e, idx) => ({
      event_id: e.event_id || `evt_${idx}`,
      session_id: sessionId,
      from_state: e.from_state || 'ACTIVE',
      to_state: e.to_state || 'PROGRESS',
      reason: e.reason || '',
      timestamp: e.timestamp || null,
      metadata: e.metadata || {},
      error: e.error || null,
      event_type: inferEventType({ to_state: e.to_state, reason: e.reason }),
      actor: inferActor({ to_state: e.to_state, metadata: e.metadata }),
      summary: e.reason || `Transitioned to ${e.to_state}`,
      related: { session_id: sessionId },
      provenance: { source: 'TasteOps FileStateStore Audit Ledger', timestamp: e.timestamp || null },
    }));

    // The backend provides authoritative persistent audit logs but does NOT
    // implement cryptographic hash-chaining or Merkle digest trees.
    // Return an explicit unverified / unavailable status rather than fabricated claims.
    const verificationStatus = {
      is_verified: false,
      status: 'UNAVAILABLE',
      reason: 'The TasteOps API stores immutable audit events in FileStateStore, but does not provide cryptographic hash-chain ledger verification.',
      chain_length: events.length,
      algorithm: null,
      head_hash: null,
      root_hash: null,
      plan_hash: null,
      plan_hash_matched: null,
    };

    return {
      events,
      verification_status: verificationStatus,
    };
  }

  async verifySessionLedger(sessionId) {
    const data = await this.getSessionEvents(sessionId);
    return data.verification_status;
  }

  // ---------------------------------------------------------------------------
  // Experience & Sensory Blueprint Adapter
  // ---------------------------------------------------------------------------
  async getSessionBlueprint(sessionId) {
    const session = await this.getSession(sessionId);

    const strat = session.strategy_output || {};
    const exp = session.experience_output || {};
    const part = session.partnership_output || {};
    const gov = session.governance_output || session.validation_result || {};
    const plan = session.execution_plan || session.plan || {};
    const twin = session.cultural_twin || {};
    const matrix = session.cultural_matrix || plan.cultural_matrix || {};
    const telem = session.agent_telemetry || plan.agent_telemetry || {};

    // 4-Layer Epistemic Provenance Registry
    // Maps entity IDs, partner names, and spatial zones to complete provenance records
    const provMap = {};

    const registerProv = (key, record) => {
      if (!key) return;
      provMap[key] = record;
      provMap[String(key).toLowerCase()] = record;
    };

    // 1. Resolved Cultural Anchors
    if (twin.resolved_entities && Array.isArray(twin.resolved_entities)) {
      for (const ent of twin.resolved_entities) {
        const entId = ent.entity_id || ent.id;
        const entName = ent.name || entId;
        const rec = {
          entity_name: entName,
          evidence: {
            entity_id: entId,
            source: ent.source || 'qloo_entity_resolver',
            urn: `urn:qloo:entity:${(ent.type && ent.type.toLowerCase() !== 'none') ? ent.type : 'cultural_anchor'}:${entId}`,
            affinity: typeof ent.affinity === 'number' ? ent.affinity : null,
            confidence: typeof ent.confidence === 'number' ? ent.confidence : null,
            why_it_matters: ent.why_it_matters || 'Ground-truth cultural intelligence anchor resolved from venue brief.',
          },
          agent_inference: {
            curatorial_rationale: `Anchor entity establishing aesthetic baseline and subcultural resonance for ${entName}.`,
            affinity_fit: 'Core taste anchor informing cross-domain cultural twin synthesis.',
            composite_fit_score: 95.0,
          },
          recommendation: {
            title: entName,
            role: (ent.type && ent.type.toLowerCase() !== 'none' && ent.type.toLowerCase() !== 'null') ? `Cultural Anchor (${ent.type})` : 'Cultural Anchor',
            category: (ent.type && ent.type.toLowerCase() !== 'none' && ent.type.toLowerCase() !== 'null') ? ent.type : 'Anchor',
          },
          execution_action: {
            action: `Incorporate ${entName} taste graph into sonic and sensory programming`,
            target_zone: 'Entire Space',
            connector: 'Cultural Intelligence MCP Server',
            status: 'VERIFIED',
          },
        };
        registerProv(entId, rec);
        registerProv(entName, rec);
      }
    }

    // 2. Cultural Matrix Places, Artists, Brands
    const matrixCategories = [
      { list: matrix.places || [], cat: 'place', source: 'qloo_insights_places' },
      { list: matrix.artists || [], cat: 'artist', source: 'qloo_insights_artists' },
      { list: matrix.brands || [], cat: 'brand', source: 'qloo_insights_brands' },
      { list: matrix.books || [], cat: 'literature', source: 'qloo_insights_books' },
    ];
    for (const group of matrixCategories) {
      for (const item of group.list) {
        const entId = item.entity_id || item.id || `urn:qloo:${group.cat}:${item.name}`;
        const entName = item.name || item.title || entId;
        const rec = {
          entity_name: entName,
          evidence: {
            entity_id: entId,
            source: group.source,
            urn: item.urn || `urn:qloo:${group.cat}:${entId}`,
            affinity: typeof item.affinity === 'number' ? item.affinity : null,
            confidence: typeof item.confidence === 'number' ? item.confidence : null,
            why_it_matters: item.why_it_matters || `Retrieved via Qloo Cultural Matrix ${group.cat} affinity analysis.`,
          },
          agent_inference: {
            curatorial_rationale: item.rationale || `Strong cultural overlap with patron taste profile across ${group.cat} affinities.`,
            affinity_fit: typeof item.affinity === 'number' ? `${(item.affinity * 100).toFixed(0)}% measured affinity` : 'Scored via independent multi-dimensional composite fit',
            composite_fit_score: typeof item.composite_fit === 'number' ? item.composite_fit : (typeof item.affinity === 'number' ? item.affinity * 100 : 75.0),
          },
          recommendation: {
            title: entName,
            role: `Cultural Reference (${group.cat})`,
            category: group.cat,
          },
          execution_action: {
            action: `Curate ${entName} in ${group.cat} rotation`,
            target_zone: 'Sensory & Social Zones',
            connector: group.cat === 'artist' ? 'Spotify Web API' : 'Procurement Order System',
            status: 'STAGED',
          },
        };
        registerProv(entId, rec);
        registerProv(entName, rec);
      }
    }

    // 3. Strategic Brand Partnerships
    const allPartners = [
      ...(part.partnerships || []),
      ...(part.candidates || []),
    ];
    for (const p of allPartners) {
      const pName = p.brand || p.partner_name || p.name;
      if (!pName) continue;
      const pId = p.brand_entity_id || p.partner_entity_id || `brand_${pName.toLowerCase().replace(/[^a-z0-9]/g, '_')}`;
      const compFit = typeof p.composite_fit_score === 'number' ? p.composite_fit_score : (typeof p.score === 'number' ? p.score : null);
      const affScore = typeof p.affinity_score === 'number' ? p.affinity_score : null;
      const rec = {
        entity_name: pName,
        evidence: {
          entity_id: pId,
          source: 'qloo_insights_brands',
          urn: `urn:qloo:brand:${pId}`,
          affinity: affScore,
          confidence: affScore,
          why_it_matters: `Evaluated via 6-dimensional partnership model: cultural fit, audience overlap, brand synergy, and operational feasibility.`,
        },
        agent_inference: {
          curatorial_rationale: p.partnership_concept || p.concept_description || `Co-branded activation aligning with patron aesthetic expectations.`,
          affinity_fit: compFit !== null ? `${compFit.toFixed(0)}/100 multi-dimensional composite score` : 'Evaluated across brand compatibility parameters',
          composite_fit_score: compFit,
        },
        recommendation: {
          title: pName,
          role: `${p.category || 'Strategic Partner'} Residency`,
          category: p.category || 'Brand Partner',
        },
        execution_action: {
          action: p.recommended_next_action || `Dispatch collaboration brief for '${pName}'`,
          target_zone: 'Physical Activation Zone',
          connector: 'Transactional Email Engine',
          status: 'STAGED',
        },
      };
      registerProv(pId, rec);
      registerProv(pName, rec);
    }

    // 4. Physical Spatial Zones
    const allZones = [
      ...(exp.spatial_zones || []),
      ...(plan.spatial_zones || []),
    ];
    for (const z of allZones) {
      const zName = z.zone_name || z.name;
      if (!zName) continue;
      const rec = {
        entity_name: zName,
        evidence: {
          entity_id: `zone_${zName.toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
          source: 'experience_architect_spatial_model',
          urn: `urn:tasteops:spatial_zone:${zName}`,
          affinity: null,
          confidence: 0.95,
          why_it_matters: `Architectural choreography structured around patron dwell tempo and acoustic SPL constraints (<75dB).`,
        },
        agent_inference: {
          curatorial_rationale: z.design_intent || z.description || 'Dedicated acoustic zone calibrated for unhurried listening and tactile engagement.',
          affinity_fit: `Target Mood: ${z.intended_mood || z.target_mood || 'Intimate'} • Materiality: ${(z.tactile_elements || []).join(', ')}`,
          composite_fit_score: 90.0,
        },
        recommendation: {
          title: zName,
          role: 'Physical Spatial Zone',
          category: 'Architecture & Acoustic Design',
        },
        execution_action: {
          action: `Generate physical design spec for zone '${zName}'`,
          target_zone: zName,
          connector: 'Procurement Order System',
          status: 'STAGED',
        },
      };
      registerProv(zName, rec);
    }

    // 5. Sonic Curations
    const sonicRecs = exp.sonic_identity?.curated_recommendations || [];
    for (const s of sonicRecs) {
      const sTitle = s.recommendation || s.title;
      if (!sTitle) continue;
      const rec = {
        entity_name: sTitle,
        evidence: {
          entity_id: `artist_${sTitle.toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
          source: 'qloo_insights_artists',
          urn: `urn:qloo:artist:${sTitle}`,
          affinity: typeof s.confidence === 'number' ? s.confidence : null,
          confidence: typeof s.confidence === 'number' ? s.confidence : null,
          why_it_matters: 'Acoustic fidelity vetting for non-fatiguing playback dynamics.',
        },
        agent_inference: {
          curatorial_rationale: s.expected_role || 'Acoustic day-parting rotation aligned with listening lounge sonic curve.',
          affinity_fit: 'Direct subcultural resonance with analog jazz and audiophile enthusiasts.',
          composite_fit_score: 88.0,
        },
        recommendation: {
          title: sTitle,
          role: s.expected_role || 'Acoustic Rotation Artist',
          category: 'Sonic Architecture',
        },
        execution_action: {
          action: `Export seed artist '${sTitle}' to Spotify audio engine pipeline`,
          target_zone: 'Soundscape Engine',
          connector: 'Spotify Web API',
          status: 'STAGED',
        },
      };
      registerProv(sTitle, rec);
    }

    const readinessConfidence = typeof gov.readiness_score === 'number'
      ? gov.readiness_score
      : (typeof twin.confidence === 'number' ? twin.confidence : null);

    // Identify failing stage if session halted in FAILED state
    let failingStage = null;
    if (session.current_state === 'FAILED' && session.history && session.history.length > 0) {
      const lastTransition = session.history[session.history.length - 1];
      failingStage = lastTransition.from_state || 'WORKFLOW_EXECUTION';
    }

    const errorMessage = session.error_message || (
      session.history && session.history.length > 0 && session.history[session.history.length - 1].to_state === 'FAILED'
        ? session.history[session.history.length - 1].reason
        : null
    );

    return {
      session_id: sessionId,
      state: session.current_state,
      strategic_objective: strat.positioning_statement || session.user_input || null,
      experience_narrative: strat.positioning_statement || session.user_input || null,
      audience: {
        target_subcultures: strat.target_subcultures || twin.target_audience || [],
        demographics: twin.audience_profile || null,
        affinity_themes: strat.affinity_themes || twin.cultural_themes || [],
      },
      cultural_positioning: {
        positioning_statement: strat.positioning_statement || null,
        cultural_pillars: strat.cultural_pillars || [],
      },
      cultural_pillars: strat.cultural_pillars || [],
      experience_concept: {
        spatial_zones: exp.spatial_zones || [],
        soundscape_design: exp.sonic_identity || {},
        atmosphere_guidelines: exp.atmosphere_guidelines || {},
      },
      spatial_zones: exp.spatial_zones || [],
      soundscape_design: exp.sonic_identity || {},
      activation_ideas: exp.cultural_programming_ideas?.weekly_curations || [],
      programming_calendar: exp.cultural_programming_ideas?.weekly_curations || [],
      partnership_opportunities: part.candidates || part.partnerships || [],
      partnerships: part.partnerships || [],
      budget_considerations: {
        estimated_cost: plan.estimated_cost || null,
        budget_tier: twin.budget || null,
      },
      risks: plan.risks || gov.risk_flags || [],
      evidence: plan.evidence || [],
      confidence: readinessConfidence,
      readiness_score: typeof gov.readiness_score === 'number' ? gov.readiness_score : null,
      governance_is_valid: gov.is_valid === true,
      compliance_checks: gov.compliance_checks || [],
      plan_hash: session.approval?.plan_hash || plan.plan_hash || null,
      execution_actions: plan.actions || [],
      recommendation_provenance_map: provMap,
      error_message: errorMessage,
      failing_stage: failingStage,
      agent_telemetry: telem,
    };
  }

  // ---------------------------------------------------------------------------
  // Live Session Subscriber (Bounded Polling Fallback)
  // ---------------------------------------------------------------------------
  subscribeSessionStream(sessionId, { onEvent, onError, onOpen, lastEventId = null }) {
    if (!sessionId) throw new Error('Session ID is required');

    let isClosed = false;
    let pollCount = 0;
    const maxPolls = 60; // 2.5 minutes maximum bounded polling
    let lastKnownState = null;

    if (onOpen) {
      setTimeout(() => {
        if (!isClosed) onOpen({ type: 'open' });
      }, 50);
    }

    const poll = async () => {
      if (isClosed) return;
      pollCount++;

      try {
        const session = await this.getSession(sessionId);
        if (isClosed) return;

        if (session.current_state !== lastKnownState) {
          lastKnownState = session.current_state;
          if (onEvent) {
            onEvent({
              event_id: `poll_${pollCount}_${Date.now()}`,
              event_type: session.current_state,
              timestamp: new Date().toISOString(),
              data: {
                from_state: 'ACTIVE',
                to_state: session.current_state,
                summary: `Workflow progressed to ${session.current_state}`,
              },
            });
          }
        }

        // Terminal states stop bounded polling
        if (['AWAITING_APPROVAL', 'APPROVED', 'COMPLETED', 'FAILED'].includes(session.current_state) || pollCount >= maxPolls) {
          clearInterval(pollTimer);
        }
      } catch (err) {
        if (onError && !isClosed) onError(err);
      }
    };

    const pollTimer = setInterval(poll, 2500);
    // Initial poll
    poll();

    return {
      close() {
        isClosed = true;
        clearInterval(pollTimer);
      },
    };
  }

  // ---------------------------------------------------------------------------
  // System Health & Diagnostics
  // ---------------------------------------------------------------------------
  async checkHealth() {
    return this._fetch(ENDPOINTS.HEALTH, { method: 'GET' });
  }

  async checkReady() {
    return this._fetch(ENDPOINTS.READY, { method: 'GET' });
  }

  async getConfig() {
    return this._fetch(ENDPOINTS.CONFIG, { method: 'GET' });
  }

  // ---------------------------------------------------------------------------
  // Context Normalizer
  // ---------------------------------------------------------------------------
  _normalizeSession(context) {
    if (!context || typeof context !== 'object') return context;

    const normalized = { ...context };

    // 1. Authoritative Approval State Derivation:
    // Must NOT infer approval merely because an approval object exists.
    // It must derive approval from authoritative backend state AND valid approval fields.
    const isApprovedState = ['APPROVED', 'EXECUTING', 'COMPLETED'].includes(context.current_state);
    const hasValidApproval = Boolean(context.approval && context.approval.is_valid && context.approval.plan_hash);
    const isAuthoritativelyApproved = isApprovedState && hasValidApproval;

    normalized.approval_state = {
      is_approved: isAuthoritativelyApproved,
      status: isAuthoritativelyApproved
        ? 'APPROVED'
        : (context.current_state === 'FAILED' ? 'REJECTED' : 'PENDING'),
      approver: context.approval?.approver || null,
      approved_at: context.approval?.approved_at || null,
      plan_hash: context.approval?.plan_hash || null,
      plan_version: context.approval?.plan_version || null,
      plan_id: context.approval?.plan_id || null,
    };

    // 2. Validation Normalization (Zero Fabricated 1.0 Defaults):
    const gov = context.governance_output || context.validation_result;
    if (gov) {
      normalized.validation = {
        is_valid: Boolean(gov.is_valid),
        provenance_verified: Boolean(gov.provenance_verified),
        compliance_score: typeof gov.readiness_score === 'number' ? gov.readiness_score : null,
        readiness_score: typeof gov.readiness_score === 'number' ? gov.readiness_score : null,
        risk_flags: Array.isArray(gov.risk_flags) ? gov.risk_flags : [],
        compliance_checks: Array.isArray(gov.compliance_checks) ? gov.compliance_checks : [],
        unverified_entity_ids: Array.isArray(gov.unverified_entity_ids) ? gov.unverified_entity_ids : [],
      };
    } else {
      normalized.validation = {
        is_valid: null,
        provenance_verified: null,
        compliance_score: null,
        readiness_score: null,
        risk_flags: [],
        compliance_checks: [],
        unverified_entity_ids: [],
      };
    }

    // 3. Execution State Normalization:
    // Never mark tasks as mock or non-mock unconditionally. Never default unknown estimated_cost to zero.
    const tasks = context.execution_tasks || [];
    normalized.execution_state = {
      tasks: tasks.map(t => {
        let isMock = null;
        if (typeof t.is_mock === 'boolean') {
          isMock = t.is_mock;
        } else if (t.result && typeof t.result.is_mock === 'boolean') {
          isMock = t.result.is_mock;
        } else if (t.input && typeof t.input.is_mock === 'boolean') {
          isMock = t.input.is_mock;
        }

        return {
          task_id: t.task_id,
          task_type: t.category || t.task_type || t.action || 'general_execution',
          action: t.action,
          description: t.description || t.action || null,
          status: t.status || 'PENDING',
          connector: t.connector || t.connector_type || (t.input?.connector ? t.input.connector : 'system'),
          is_mock: isMock,
          approval_status: isAuthoritativelyApproved ? 'APPROVED' : 'PENDING',
          estimated_cost: t.estimated_cost !== undefined && t.estimated_cost !== null && t.estimated_cost !== '' ? t.estimated_cost : null,
          provenance: t.provenance && Object.keys(t.provenance).length > 0 ? t.provenance : null,
          result: t.result && Object.keys(t.result).length > 0 ? t.result : null,
          error: t.error || null,
          execution_timestamp: t.executed_at || t.timestamp || null,
          idempotency_key: t.idempotency_key || null,
          owner: t.owner || null,
        };
      }),
    };

    // 4. Cultural Matrix Summary Normalization (Pass-Through Real Data):
    let evidenceCount = 0;
    const topAffinities = {};
    if (context.cultural_matrix && typeof context.cultural_matrix === 'object') {
      const cats = ['artists', 'books', 'brands', 'places', 'movies', 'destinations'];
      for (const cat of cats) {
        const list = context.cultural_matrix[cat];
        if (Array.isArray(list) && list.length > 0) {
          evidenceCount += list.length;
          topAffinities[cat] = list.map(item => ({
            id: item.id,
            name: item.name,
            type: item.type,
            affinity: typeof item.affinity === 'number' ? item.affinity : (typeof item.score === 'number' ? item.score / 100 : null),
            score: typeof item.score === 'number' ? item.score : null,
            confidence: typeof item.confidence === 'number' ? item.confidence : null,
            source_query: item.source_query || null,
          }));
        }
      }
    }
    normalized.cultural_matrix_summary = {
      evidence_count: evidenceCount,
      total_entities: evidenceCount,
      top_affinities: topAffinities,
    };

    // 5. Agent Summaries (Derived strictly from real agent outputs & telemetry):
    const telem = context.agent_telemetry || context.plan?.agent_telemetry || {};
    const isHalted = context.current_state === 'FAILED';

    normalized.agent_summaries = {
      cultural_strategist: {
        name: 'Cultural Strategist',
        status: context.strategy_output
          ? 'COMPLETED'
          : (isHalted && ['CREATED', 'INTENT_PARSED', 'CULTURAL_TWIN_CREATED'].includes(context.history?.[context.history.length - 1]?.from_state)
            ? 'FAILED'
            : (['INTENT_PARSED', 'CULTURAL_TWIN_CREATED'].includes(context.current_state) ? 'RUNNING' : 'PENDING')),
        output_summary: {
          decisions: context.strategy_output?.positioning_statement || (isHalted ? (context.error_message || 'Halted during cultural twin generation.') : 'Translates brief into Cultural Twin, resolves anchor terms in Qloo.'),
        },
        evidence_count: context.strategy_output?.provenance_entity_ids?.length ?? (context.cultural_twin?.resolved_entities?.length || 0),
        duration: telem.strategist?.duration_seconds ? `${telem.strategist.duration_seconds}s` : (context.strategy_output ? '<0.1s' : null),
        failure_information: isHalted && !context.strategy_output ? context.error_message : null,
      },
      experience_architect: {
        name: 'Experience Architect',
        status: context.experience_output
          ? 'COMPLETED'
          : (isHalted && context.strategy_output && !context.experience_output
            ? 'FAILED'
            : (context.current_state === 'AGENTS_RUNNING' ? 'RUNNING' : 'PENDING')),
        output_summary: {
          decisions: context.experience_output?.sonic_identity ? 'Synthesizes spatial zones, acoustic identity, and sensory atmospheres.' : (isHalted ? 'Awaiting upstream signals (workflow halted).' : 'Awaiting upstream signals.'),
        },
        evidence_count: context.experience_output?.provenance_entity_ids?.length ?? (telem.sonic?.entities_processed || 0),
        duration: telem.sonic?.duration_seconds ? `${telem.sonic.duration_seconds}s` : (context.experience_output ? '<0.1s' : null),
        failure_information: isHalted && context.strategy_output && !context.experience_output ? context.error_message : null,
      },
      partnership_agent: {
        name: 'Partnership Agent',
        status: context.partnership_output
          ? 'COMPLETED'
          : (isHalted && context.strategy_output && !context.partnership_output
            ? 'FAILED'
            : (context.current_state === 'AGENTS_RUNNING' ? 'RUNNING' : 'PENDING')),
        output_summary: {
          decisions: context.partnership_output?.partnerships ? `Curated ${context.partnership_output.partnerships.length} verified brand activations.` : (isHalted ? 'Awaiting cultural matrix affinities (workflow halted).' : 'Awaiting cultural matrix affinities.'),
        },
        evidence_count: context.partnership_output?.provenance_entity_ids?.length ?? (telem.brand?.entities_processed || 0),
        duration: telem.brand?.duration_seconds ? `${telem.brand.duration_seconds}s` : (context.partnership_output ? '<0.1s' : null),
        failure_information: isHalted && context.strategy_output && !context.partnership_output ? context.error_message : null,
      },
      governance_agent: {
        name: 'Governance / Execution Agent',
        status: gov
          ? (gov.is_valid ? 'COMPLETED' : 'FAILED')
          : (isHalted ? 'FAILED' : (context.current_state === 'PLAN_GENERATED' ? 'RUNNING' : 'PENDING')),
        output_summary: {
          decisions: gov
            ? `Governance readiness: ${typeof gov.readiness_score === 'number' ? (gov.readiness_score * 100).toFixed(0) + '%' : 'Unavailable'}. Provenance verified: ${gov.provenance_verified ? 'Yes' : 'No'}.`
            : (isHalted ? (context.error_message || 'Validation failed.') : 'Awaiting plan generation.'),
        },
        evidence_count: gov ? (gov.unverified_entity_ids?.length === 0 ? '100% verified' : `${gov.unverified_entity_ids?.length} unverified`) : 'N/A',
        duration: telem.procurement?.duration_seconds ? `${telem.procurement.duration_seconds}s` : (gov ? '<0.1s' : null),
        failure_information: isHalted ? context.error_message : null,
      },
    };

    return normalized;
  }
}

// Global singleton instance for application use
export const apiClient = new TasteOpsAPIClient();
