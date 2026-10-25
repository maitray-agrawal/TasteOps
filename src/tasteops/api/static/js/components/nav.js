/**
 * TasteOps Navigation Command Bar Component.
 */

import { apiClient } from '../apiClient.js';

export function renderNavbar(container, router) {
  container.innerHTML = `
    <header class="navbar">
      <div class="nav-container">
        <a href="/dashboard" class="nav-brand" id="nav-brand-link">
          <span style="font-size: 1.5rem;">✦</span>
          <span>TasteOps</span>
          <span class="brand-badge">AI Operations</span>
        </a>

        <ul class="nav-links">
          <li>
            <a href="/dashboard" class="nav-link" id="nav-link-dashboard">
              <span>📊</span>
              <span>Dashboard</span>
            </a>
          </li>
          <li>
            <a href="/spaces/new" class="nav-link" id="nav-link-spaces-new">
              <span>🏛️</span>
              <span>Register Space</span>
            </a>
          </li>
        </ul>

        <div class="nav-actions">
          <div class="health-status-badge" id="backend-health-badge" title="API Gateway Live Status">
            <span class="health-dot" id="backend-health-dot"></span>
            <span id="backend-health-label">API Connected</span>
          </div>

          <button class="btn btn-primary btn-sm" id="btn-quick-new-space">
            <span>+</span>
            <span>New Space</span>
          </button>
        </div>
      </div>
    </header>
  `;

  // Attach event listeners for client-side navigation
  document.getElementById('nav-brand-link')?.addEventListener('click', (e) => {
    e.preventDefault();
    router.navigate('/dashboard');
  });

  document.getElementById('nav-link-dashboard')?.addEventListener('click', (e) => {
    e.preventDefault();
    router.navigate('/dashboard');
  });

  document.getElementById('nav-link-spaces-new')?.addEventListener('click', (e) => {
    e.preventDefault();
    router.navigate('/spaces/new');
  });

  document.getElementById('btn-quick-new-space')?.addEventListener('click', () => {
    router.navigate('/spaces/new');
  });

  // Highlight active link on route change
  window.addEventListener('tasteops:routechange', (e) => {
    const path = e.detail?.path || '';
    const dashLink = document.getElementById('nav-link-dashboard');
    const spaceLink = document.getElementById('nav-link-spaces-new');

    if (dashLink) dashLink.classList.toggle('active', path === '/dashboard' || path === '/');
    if (spaceLink) spaceLink.classList.toggle('active', path === '/spaces/new');
  });

  // Periodic non-intrusive backend health probe
  const checkHealth = async () => {
    const badge = document.getElementById('backend-health-badge');
    const label = document.getElementById('backend-health-label');
    const dot = document.getElementById('backend-health-dot');
    if (!badge || !label || !dot) return;

    try {
      const res = await apiClient.checkHealth();
      if (res.status === 'healthy') {
        badge.style.background = 'rgba(16, 185, 129, 0.1)';
        badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
        badge.style.color = '#34d399';
        label.textContent = 'API Live';
      }
    } catch (_) {
      badge.style.background = 'rgba(244, 63, 94, 0.1)';
      badge.style.borderColor = 'rgba(244, 63, 94, 0.3)';
      badge.style.color = '#fb7185';
      label.textContent = 'API Offline';
    }
  };

  checkHealth();
  setInterval(checkHealth, 30000);
}
