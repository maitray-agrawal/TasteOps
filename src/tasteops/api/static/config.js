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

  // Check for explicit runtime override (e.g. for Zoho Catalyst AppSail deployments)
  const metaOverride = typeof document !== 'undefined'
    ? document.querySelector('meta[name="catalyst-api-base-url"]')?.getAttribute('content')
    : null;
  const catalystOverride = typeof window !== 'undefined'
    ? (window.__TASTEOPS_CATALYST_API_BASE__ || window.__TASTEOPS_OVERRIDE_API_URL__ || metaOverride)
    : null;

  const defaultRemote = 'https://tasteops-backend.onrender.com';
  const apiBase = catalystOverride || (isLocal ? '/api/v1' : defaultRemote);

  window.__TASTEOPS_CONFIG__ = Object.freeze({
    // In local development on localhost/127.0.0.1, route to local FastAPI (/api/v1)
    // On static CDN deployment (Vercel or Catalyst Web Client), route to the configured backend
    API_BASE_URL: apiBase,
    apiBaseUrl: apiBase,
    ENVIRONMENT: isLocal ? 'development' : 'production',
    VERSION: '0.1.0',
  });
})();

