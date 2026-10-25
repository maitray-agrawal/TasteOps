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
    // Priority: Explicit option -> window.__TASTEOPS_ENV__ -> meta tag -> default
    const metaBase = typeof document !== 'undefined'
      ? document.querySelector('meta[name="api-base-url"]')?.getAttribute('content')
      : null;
    const envBase = (typeof window !== 'undefined' && window.__TASTEOPS_ENV__?.API_BASE_URL) || metaBase;

    this.baseUrl = (options.baseUrl || envBase || '/api/v1').replace(/\/+$/, '');
  }

  /**
   * Internal HTTP request dispatcher with centralized error handling.
   */
  async _fetch(endpoint, options = {}) {
    const isRootProbe = endpoint === ENDPOINTS.HEALTH || endpoint === ENDPOINTS.READY;
    const url = isRootProbe ? endpoint : `${this.baseUrl}${endpoint}`;

    const headers = {
      'Accept': 'application/json',
      ...options.headers,
    };

    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

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
      if (err instanceof APIError) {
        throw err;
      }
      throw new APIError(err.message || 'Network communication failure', {
        statusCode: 0,
        code: 'NETWORK_DISCONNECTED',
        detail: 'Unable to communicate with the TasteOps API server.',
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
    const intentParts = [
      `Venue concept: ${space.name}`,
      `Typology: ${space.business_type}`,
    ];
    if (space.brief?.desired_mood) intentParts.push(`Atmosphere: ${space.brief.desired_mood}`);
    if (space.brief?.target_audience) intentParts.push(`Target audience: ${space.brief.target_audience}`);
    if (space.brief?.anchor_entities?.length) intentParts.push(`Anchor affinities: ${space.brief.anchor_entities.join(', ')}`);
    const rawIntent = intentParts.join('. ') + '.';

    // 1. Create session
    const session = await this.createSession({
      raw_intent: rawIntent,
      space_id: spaceId,
      hints: {
        desired_mood: space.brief?.desired_mood,
        target_audience: space.brief?.target_audience,
        anchor_entities: space.brief?.anchor_entities,
        business_type: space.business_type,
        location: space.location,
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

    const provMap = {};
    if (twin.resolved_entities && Array.isArray(twin.resolved_entities)) {
      for (const ent of twin.resolved_entities) {
        const entKey = ent.entity_id || ent.id;
        if (!entKey) continue;
        provMap[entKey] = {
          entity_id: entKey,
          name: ent.name,
          category: ent.category || ent.type,
          source: ent.source || 'qloo_entity_resolver',
          confidence: typeof ent.confidence === 'number' ? ent.confidence : null,
          affinity_score: typeof ent.affinity === 'number' ? ent.affinity : (typeof ent.score === 'number' ? ent.score / 100 : null),
        };
      }
    }

    const readinessConfidence = typeof gov.readiness_score === 'number'
      ? gov.readiness_score
      : (typeof twin.confidence === 'number' ? twin.confidence : null);

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
      plan_hash: session.approval?.plan_hash || plan.plan_hash || null,
      execution_actions: plan.actions || [],
      recommendation_provenance_map: provMap,
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

    // 5. Agent Summaries (Derived strictly from real agent outputs):
    normalized.agent_summaries = {
      cultural_strategist: {
        name: 'Cultural Strategist',
        status: context.strategy_output ? 'COMPLETED' : (['INTENT_PARSED', 'CULTURAL_TWIN_CREATED'].includes(context.current_state) ? 'RUNNING' : 'PENDING'),
        output_summary: {
          decisions: context.strategy_output?.positioning_statement || 'Translates brief into Cultural Twin, resolves anchor terms in Qloo.',
        },
        evidence_count: context.strategy_output?.provenance_entity_ids?.length ?? (context.cultural_twin?.resolved_entities?.length || 0),
        duration: null,
      },
      experience_architect: {
        name: 'Experience Architect',
        status: context.experience_output ? 'COMPLETED' : (context.current_state === 'AGENTS_RUNNING' ? 'RUNNING' : 'PENDING'),
        output_summary: {
          decisions: context.experience_output?.sonic_identity ? 'Synthesizes spatial zones, acoustic identity, and sensory atmospheres.' : 'Awaiting upstream signals.',
        },
        evidence_count: context.experience_output?.provenance_entity_ids?.length ?? 0,
        duration: null,
      },
      partnership_agent: {
        name: 'Partnership Agent',
        status: context.partnership_output ? 'COMPLETED' : (context.current_state === 'AGENTS_RUNNING' ? 'RUNNING' : 'PENDING'),
        output_summary: {
          decisions: context.partnership_output?.partnerships ? `Curated ${context.partnership_output.partnerships.length} verified brand activations.` : 'Awaiting cultural matrix affinities.',
        },
        evidence_count: context.partnership_output?.provenance_entity_ids?.length ?? 0,
        duration: null,
      },
      governance_agent: {
        name: 'Governance / Execution Agent',
        status: gov ? (gov.is_valid ? 'COMPLETED' : 'FAILED') : (context.current_state === 'PLAN_GENERATED' ? 'RUNNING' : 'PENDING'),
        output_summary: {
          decisions: gov ? `Readiness score: ${typeof gov.readiness_score === 'number' ? (gov.readiness_score * 100).toFixed(0) + '%' : 'Unavailable'}. Provenance verified: ${gov.provenance_verified ? 'Yes' : 'No'}.` : 'Awaiting plan generation.',
        },
        evidence_count: gov ? (gov.unverified_entity_ids?.length === 0 ? '100% verified' : `${gov.unverified_entity_ids?.length} unverified`) : 'N/A',
        duration: null,
      },
    };

    return normalized;
  }
}

// Global singleton instance for application use
export const apiClient = new TasteOpsAPIClient();
