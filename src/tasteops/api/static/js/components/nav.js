/**
 * TasteOps Left Sidebar Navigation Component.
 * Implements Section 7: Warm ivory, arch logo, 7 menu items, active sage tint, user profile card.
 */

import { apiClient } from '../apiClient.js';

export function renderNavbar(container, router) {
  const currentPath = window.location.pathname;

  // On opening screen '/', hide the left sidebar completely
  if (currentPath === '/') {
    container.classList.add('hidden-nav');
    document.getElementById('app-main')?.classList.add('full-width');
  } else {
    container.classList.remove('hidden-nav');
    document.getElementById('app-main')?.classList.remove('full-width');
  }

  container.innerHTML = `
    <aside class="sidebar">
      <div>
        <!-- Brand & Arch Logo -->
        <a href="/home" class="sidebar-brand" id="brand-home-link">
          <div class="brand-logo-lockup">
            <div class="brand-arch-icon">
              <div class="brand-arch-inner"></div>
            </div>
            <span class="brand-name">TasteOps</span>
          </div>
          <span class="brand-tagline">AUTONOMOUS SPATIAL CURATION</span>
        </a>

        <!-- 7 Primary Navigation Items -->
        <ul class="sidebar-nav">
          <li class="sidebar-nav-item">
            <a href="/home" id="nav-item-home" class="${currentPath === '/home' || currentPath === '/dashboard' ? 'active' : ''}">
              <span class="nav-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                  <polyline points="9 22 9 12 15 12 15 22"></polyline>
                </svg>
              </span>
              <span>Home</span>
            </a>
          </li>

          <li class="sidebar-nav-item">
            <a href="/create-space" id="nav-item-create" class="${currentPath === '/create-space' || currentPath === '/spaces/new' ? 'active' : ''}">
              <span class="nav-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="16"></line>
                  <line x1="8" y1="12" x2="16" y2="12"></line>
                </svg>
              </span>
              <span>Create Space</span>
            </a>
          </li>

          <li class="sidebar-nav-item">
            <a href="/cultural-twin" id="nav-item-twin" class="${currentPath === '/cultural-twin' ? 'active' : ''}">
              <span class="nav-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"></path>
                  <circle cx="12" cy="12" r="3"></circle>
                </svg>
              </span>
              <span>Cultural Twin</span>
            </a>
          </li>

          <li class="sidebar-nav-item">
            <a href="/agents" id="nav-item-agents" class="${currentPath === '/agents' ? 'active' : ''}">
              <span class="nav-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                  <line x1="8" y1="21" x2="16" y2="21"></line>
                  <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
              </span>
              <span>Agents</span>
            </a>
          </li>

          <li class="sidebar-nav-item">
            <a href="/execution-plan" id="nav-item-plan" class="${currentPath === '/execution-plan' ? 'active' : ''}">
              <span class="nav-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                  <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
              </span>
              <span>Execution Plan</span>
            </a>
          </li>

          <li class="sidebar-nav-item">
            <a href="/results" id="nav-item-results" class="${currentPath === '/results' ? 'active' : ''}">
              <span class="nav-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </span>
              <span>Results</span>
            </a>
          </li>

          <li class="sidebar-nav-item">
            <a href="/saved-spaces" id="nav-item-saved" class="${currentPath === '/saved-spaces' ? 'active' : ''}">
              <span class="nav-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
                </svg>
              </span>
              <span>Saved Spaces</span>
            </a>
          </li>
        </ul>
      </div>

      <!-- User Profile Card -->
      <div class="sidebar-user">
        <div class="user-avatar">M</div>
        <div class="user-meta">
          <span class="user-name">Maitray Agrawal</span>
          <span class="user-role">Venue Manager</span>
        </div>
      </div>
    </aside>
  `;

  // Listen to router navigation to update active tab and toggle sidebar visibility
  window.addEventListener('tasteops:routechange', (e) => {
    const path = e.detail?.path || window.location.pathname;
    if (path === '/') {
      container.classList.add('hidden-nav');
      document.getElementById('app-main')?.classList.add('full-width');
    } else {
      container.classList.remove('hidden-nav');
      document.getElementById('app-main')?.classList.remove('full-width');
    }

    // Update active pills
    container.querySelectorAll('.sidebar-nav-item a').forEach(el => el.classList.remove('active'));
    if (path === '/' || path === '/home' || path === '/dashboard') {
      document.getElementById('nav-item-home')?.classList.add('active');
    } else if (path === '/create-space' || path === '/spaces/new') {
      document.getElementById('nav-item-create')?.classList.add('active');
    } else if (path === '/cultural-twin') {
      document.getElementById('nav-item-twin')?.classList.add('active');
    } else if (path === '/agents') {
      document.getElementById('nav-item-agents')?.classList.add('active');
    } else if (path === '/execution-plan') {
      document.getElementById('nav-item-plan')?.classList.add('active');
    } else if (path === '/results') {
      document.getElementById('nav-item-results')?.classList.add('active');
    } else if (path === '/saved-spaces') {
      document.getElementById('nav-item-saved')?.classList.add('active');
    }
  });
}
