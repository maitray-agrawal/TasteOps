/**
 * TasteOps Client-Side Router.
 *
 * Provides declarative URL routing with dynamic path parameter extraction,
 * HTML5 History API integration, and route change lifecycle events.
 */

export class Router {
  constructor(routes = {}, options = {}) {
    this.routes = routes; // Pattern -> handler: { path, handler }
    this.rootElement = options.rootElement || document.getElementById('app-main');
    this.currentRoute = null;
    this.params = {};

    window.addEventListener('popstate', () => this.resolve());
    window.addEventListener('hashchange', () => this.resolve());
  }

  addRoute(pattern, handler) {
    this.routes[pattern] = handler;
    return this;
  }

  navigate(path) {
    const cleanPath = path.startsWith('/') ? path : '/' + path;
    const isCatalyst = typeof window !== 'undefined' && window.location.pathname.startsWith('/app');
    const isHashMode = typeof window !== 'undefined' && window.location.hash && window.location.hash.startsWith('#/');

    if (isCatalyst || isHashMode) {
      const targetHash = '#' + cleanPath;
      if (window.location.hash === targetHash) {
        this.resolve();
      } else {
        window.location.hash = targetHash;
      }
      return;
    }
    if (window.location.pathname === path) return;
    window.history.pushState({}, '', path);
    this.resolve();
  }

  replace(path) {
    const cleanPath = path.startsWith('/') ? path : '/' + path;
    const isCatalyst = typeof window !== 'undefined' && window.location.pathname.startsWith('/app');
    const isHashMode = typeof window !== 'undefined' && window.location.hash && window.location.hash.startsWith('#/');

    if (isCatalyst || isHashMode) {
      const targetHash = '#' + cleanPath;
      if (window.location.hash === targetHash) {
        this.resolve();
      } else {
        window.location.hash = targetHash;
      }
      return;
    }
    window.history.replaceState({}, '', path);
    this.resolve();
  }

  getParam(key) {
    return this.params[key];
  }

  /**
   * Matches current window.location.pathname (or hash) against registered route patterns.
   */
  resolve() {
    let pathname = window.location.pathname;

    // Support Catalyst Web Client Hosting hash-based fallback navigation
    if (window.location.hash && window.location.hash.startsWith('#/')) {
      pathname = window.location.hash.slice(1);
    } else if (pathname.startsWith('/app')) {
      // Strip Catalyst /app base path if present
      pathname = pathname.slice(4);
      if (pathname.startsWith('/index.html')) {
        pathname = pathname.slice(11);
      }
    } else if (pathname === '/index.html') {
      pathname = '/';
    }

    // Normalize empty path to root
    if (pathname === '' || pathname === '/') {
      pathname = '/';
    }

    // Strip trailing slash if present (except root)
    if (pathname.length > 1 && pathname.endsWith('/')) {
      pathname = pathname.slice(0, -1);
    }

    let matchedHandler = null;
    let matchedParams = {};

    for (const [pattern, handler] of Object.entries(this.routes)) {
      const match = this._matchPattern(pattern, pathname);
      if (match) {
        matchedHandler = handler;
        matchedParams = match.params;
        this.currentRoute = pattern;
        break;
      }
    }

    this.params = matchedParams;

    if (matchedHandler) {
      // Trigger navigation event for active tab updates
      window.dispatchEvent(new CustomEvent('tasteops:routechange', {
        detail: { path: pathname, route: this.currentRoute, params: this.params }
      }));

      // Render screen
      if (this.rootElement) {
        this.rootElement.innerHTML = '';
        matchedHandler(this.rootElement, this.params, this);
      }
    } else {
      this._renderNotFound(pathname);
    }
  }

  _matchPattern(pattern, pathname) {
    const patternParts = pattern.split('/').filter(Boolean);
    const pathParts = pathname.split('/').filter(Boolean);

    if (patternParts.length !== pathParts.length) {
      return null;
    }

    const params = {};
    for (let i = 0; i < patternParts.length; i++) {
      const pPart = patternParts[i];
      const actualPart = pathParts[i];

      if (pPart.startsWith(':')) {
        const paramName = pPart.slice(1);
        params[paramName] = decodeURIComponent(actualPart);
      } else if (pPart !== actualPart) {
        return null;
      }
    }

    return { params };
  }

  _renderNotFound(pathname) {
    if (!this.rootElement) return;
    this.rootElement.innerHTML = `
      <div class="empty-state fade-in" style="margin-top: 3rem;">
        <div class="empty-state-icon">🔍</div>
        <h2 class="empty-state-title">Screen Not Found</h2>
        <p class="empty-state-description">The requested workspace route <code>${escapeHtml(pathname)}</code> does not exist.</p>
        <button class="btn btn-primary" onclick="window.tasteopsRouter.navigate('/dashboard')">
          Return to Dashboard
        </button>
      </div>
    `;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
