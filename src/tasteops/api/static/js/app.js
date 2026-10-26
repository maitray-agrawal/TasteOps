/**
 * TasteOps AI Operations Workspace Main Application Entrypoint.
 * Section 24: Information Architecture routes + deterministic execution pipeline.
 */

import { apiClient } from './apiClient.js';
import { renderNavbar } from './components/nav.js';
import { Router } from './router.js';
import { renderAgents } from './screens/agents.js';
import { renderCulturalTwin } from './screens/culturalTwin.js';
import { renderDashboard } from './screens/dashboard.js';
import { renderExecutionPlan } from './screens/executionPlan.js';
import { renderResults } from './screens/results.js';
import { renderSavedSpaces } from './screens/savedSpaces.js';
import { renderSessionActivity } from './screens/sessionActivity.js';
import { renderSessionApproval } from './screens/sessionApproval.js';
import { renderSessionBlueprint } from './screens/sessionBlueprint.js';
import { renderSessionDetail } from './screens/sessionDetail.js';
import { renderSessionExecution } from './screens/sessionExecution.js';
import { renderSessionLedger } from './screens/sessionLedger.js';
import { renderSpaceDetail } from './screens/spaceDetail.js';
import { renderSpaceNew } from './screens/spaceNew.js';
import { renderSplash } from './screens/splash.js';

document.addEventListener('DOMContentLoaded', () => {
  const rootElement = document.getElementById('app-main');
  const navElement = document.getElementById('app-nav');

  // Surface visible configuration error banner if invalid or missing in production
  if (apiClient.configError) {
    const banner = document.createElement('div');
    banner.className = 'config-error-banner';
    banner.style.cssText =
      'background: #fef2f2; border-bottom: 2px solid #ef4444; color: #991b1b; padding: 0.75rem 1.5rem; ' +
      'font-size: 0.85rem; font-family: var(--font-sans); position: sticky; top: 0; z-index: 9999; ' +
      'display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06);';
    banner.innerHTML = `
      <span>⚠️ <strong>Configuration Notice:</strong> ${apiClient.configError}</span>
      <button style="background: none; border: 1px solid #b91c1c; color: #b91c1c; padding: 0.2rem 0.5rem; border-radius: 4px; cursor: pointer; font-size: 0.75rem;" onclick="this.parentElement.remove()">Dismiss</button>
    `;
    document.body.prepend(banner);
  }

  const router = new Router({}, { rootElement });
  window.tasteopsRouter = router;

  // Master Information Architecture (Section 24)
  router.addRoute('/', renderSplash);
  router.addRoute('/home', renderDashboard);
  router.addRoute('/dashboard', renderDashboard);
  router.addRoute('/create-space', renderSpaceNew);
  router.addRoute('/cultural-twin', renderCulturalTwin);
  router.addRoute('/agents', renderAgents);
  router.addRoute('/execution-plan', renderExecutionPlan);
  router.addRoute('/results', renderResults);
  router.addRoute('/saved-spaces', renderSavedSpaces);

  // Canonical workspace and execution routes
  router.addRoute('/spaces/new', renderSpaceNew);
  router.addRoute('/spaces/:spaceId', renderSpaceDetail);
  router.addRoute('/sessions/:sessionId', renderSessionDetail);
  router.addRoute('/sessions/:sessionId/activity', renderSessionActivity);
  router.addRoute('/sessions/:sessionId/blueprint', renderSessionBlueprint);
  router.addRoute('/sessions/:sessionId/approval', renderSessionApproval);
  router.addRoute('/sessions/:sessionId/execution', renderSessionExecution);
  router.addRoute('/sessions/:sessionId/ledger', renderSessionLedger);

  // Mount navigation command bar
  if (navElement) {
    renderNavbar(navElement, router);
  }

  // Intercept relative link clicks to enable seamless single-page-app navigation
  document.addEventListener('click', (e) => {
    const targetLink = e.target.closest('a');
    if (!targetLink) return;

    const href = targetLink.getAttribute('href');
    if (href && href.startsWith('/') && !href.startsWith('//') && !targetLink.hasAttribute('target')) {
      e.preventDefault();
      router.navigate(href);
    }
  });

  // Resolve current route immediately
  router.resolve();

  // Non-blocking background health probe (does not delay initial UI render)
  const probeBackendHealth = async () => {
    try {
      const res = await apiClient.checkHealth();
      window.__TASTEOPS_BACKEND_STATUS__ = { status: 'healthy', version: res?.version };
      window.dispatchEvent(new CustomEvent('tasteops:backend_status', { detail: { status: 'healthy' } }));
    } catch (err) {
      window.__TASTEOPS_BACKEND_STATUS__ = { status: 'waking', error: err.message };
      window.dispatchEvent(new CustomEvent('tasteops:backend_status', { detail: { status: 'waking', isColdStart: true } }));
    }
  };

  // Run in next animation frame / tick after mount
  setTimeout(probeBackendHealth, 250);
});
