/**
 * TasteOps Typed API Client.
 *
 * Single authoritative client for all frontend API interactions.
 * Centralizes all backend URL endpoints, provides typed error envelopes (RFC 7807),
 * configures environment base URLs, and manages Server-Sent Events subscriptions.
 * NOTE: Sensitive backend provider credentials and database connection strings
 * are NEVER stored or requested on the client tier.
 */

// Centralized endpoint registry - URLs are NEVER duplicated across UI screens
export const ENDPOINTS = Object.freeze({
  SPACES: '/spaces',
  SPACE: (id) => `/spaces/${encodeURIComponent(id)}`,
  SPACE_ANALYZE: (id) => `/spaces/${encodeURIComponent(id)}/analyze`,
  SESSION: (id) => `/sessions/${encodeURIComponent(id)}`,
  SESSION_EVENTS: (id) => `/sessions/${encodeURIComponent(id)}/events`,
  SESSION_BLUEPRINT: (id) => `/sessions/${encodeURIComponent(id)}/blueprint`,
  SESSION_STREAM: (id) => `/sessions/${encodeURIComponent(id)}/stream`,
  SESSION_APPROVE: (id) => `/sessions/${encodeURIComponent(id)}/approve`,
  SESSION_REJECT: (id) => `/sessions/${encodeURIComponent(id)}/reject`,
  SESSION_EXECUTE: (id) => `/sessions/${encodeURIComponent(id)}/execute`,
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

      const correlationId = response.headers.get('X-Correlation-ID');

      if (!response.ok) {
        let errorData = null;
        try {
          errorData = await response.json();
        } catch (_) {
          // Non-JSON error payload
        }

        const errObj = errorData?.error || {};
        const code = errObj.code || `HTTP_${response.status}`;
        const detail = errObj.detail || response.statusText;

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
  // Space Venue Operations
  // ---------------------------------------------------------------------------
  async listSpaces() {
    return this._fetch(ENDPOINTS.SPACES, { method: 'GET' });
  }

  async getSpace(spaceId) {
    if (!spaceId) throw new Error('Space ID is required');
    return this._fetch(ENDPOINTS.SPACE(spaceId), { method: 'GET' });
  }

  async createSpace(spaceData) {
    return this._fetch(ENDPOINTS.SPACES, {
      method: 'POST',
      body: JSON.stringify(spaceData),
    });
  }

  async analyzeSpace(spaceId, analyzeData = {}) {
    if (!spaceId) throw new Error('Space ID is required');
    return this._fetch(ENDPOINTS.SPACE_ANALYZE(spaceId), {
      method: 'POST',
      body: JSON.stringify(analyzeData),
    });
  }

  // ---------------------------------------------------------------------------
  // Workflow Session Operations
  // ---------------------------------------------------------------------------
  async getSession(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    return this._fetch(ENDPOINTS.SESSION(sessionId), { method: 'GET' });
  }

  async getSessionEvents(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    return this._fetch(ENDPOINTS.SESSION_EVENTS(sessionId), { method: 'GET' });
  }

  async getSessionBlueprint(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    return this._fetch(ENDPOINTS.SESSION_BLUEPRINT(sessionId), { method: 'GET' });
  }

  async approveSession(sessionId, { approver, role, notes, planVersion = 1 }) {
    if (!sessionId) throw new Error('Session ID is required');
    if (!approver) throw new Error('Approver name is required for authoritative sign-off');
    return this._fetch(ENDPOINTS.SESSION_APPROVE(sessionId), {
      method: 'POST',
      body: JSON.stringify({ approver, role, notes, plan_version: planVersion }),
    });
  }

  async rejectSession(sessionId, { reason }) {
    if (!sessionId) throw new Error('Session ID is required');
    if (!reason) throw new Error('Rejection rationale is required');
    return this._fetch(ENDPOINTS.SESSION_REJECT(sessionId), {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  async executeSession(sessionId) {
    if (!sessionId) throw new Error('Session ID is required');
    return this._fetch(ENDPOINTS.SESSION_EXECUTE(sessionId), {
      method: 'POST',
    });
  }

  // ---------------------------------------------------------------------------
  // Server-Sent Events (SSE) Live Stream Subscriber
  // ---------------------------------------------------------------------------
  subscribeSessionStream(sessionId, { onEvent, onError, onOpen, lastEventId = null }) {
    if (!sessionId) throw new Error('Session ID is required');

    let streamUrl = `${this.baseUrl}${ENDPOINTS.SESSION_STREAM(sessionId)}`;
    if (lastEventId) {
      streamUrl += `?last_event_id=${encodeURIComponent(lastEventId)}`;
    }

    const eventSource = new EventSource(streamUrl);

    if (onOpen) {
      eventSource.onopen = (e) => onOpen(e);
    }

    eventSource.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (onEvent) onEvent(payload);
      } catch (parseErr) {
        console.error('Error parsing SSE event payload:', parseErr);
      }
    };

    eventSource.onerror = (err) => {
      if (onError) onError(err);
    };

    return {
      close() {
        eventSource.close();
      },
      raw: eventSource,
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
}

// Global singleton instance for application use
export const apiClient = new TasteOpsAPIClient();
