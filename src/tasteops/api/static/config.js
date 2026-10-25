/**
 * TasteOps Public Runtime Configuration for Independent Static Frontend Deployment.
 *
 * This file is loaded in the browser before the application scripts initialize.
 * It provides the production Render backend URL when hosted on static CDN (Vercel),
 * while cleanly defaulting to the local FastAPI backend during local development.
 *
 * SECURITY & INTEGRITY:
 * - This file contains ONLY public client-facing configuration.
 * - NEVER put API keys, Qloo credentials, Spotify secrets, or backend tokens here.
 */
(function () {
  const isBrowser = typeof window !== 'undefined' && typeof window.location !== 'undefined';
  const hostname = isBrowser ? window.location.hostname : 'localhost';
  const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';

  const apiBase = isLocal ? '/api/v1' : 'https://tasteops-backend.onrender.com';

  window.__TASTEOPS_CONFIG__ = Object.freeze({
    // In local development on localhost/127.0.0.1, route to local FastAPI (/api/v1)
    // On static CDN deployment (e.g. Vercel), route to the production Render backend
    API_BASE_URL: apiBase,
    apiBaseUrl: apiBase,
    ENVIRONMENT: isLocal ? 'development' : 'production',
    VERSION: '0.1.0',
  });
})();

