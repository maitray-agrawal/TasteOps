/**
 * TasteOps AI Operations Workspace Main Application Entrypoint.
 */

import { renderNavbar } from './components/nav.js';
import { Router } from './router.js';
import { renderDashboard } from './screens/dashboard.js';
import { renderSessionActivity } from './screens/sessionActivity.js';
import { renderSessionApproval } from './screens/sessionApproval.js';
import { renderSessionBlueprint } from './screens/sessionBlueprint.js';
import { renderSessionDetail } from './screens/sessionDetail.js';
import { renderSessionExecution } from './screens/sessionExecution.js';
import { renderSessionLedger } from './screens/sessionLedger.js';
import { renderSpaceDetail } from './screens/spaceDetail.js';
import { renderSpaceNew } from './screens/spaceNew.js';

document.addEventListener('DOMContentLoaded', () => {
  const rootElement = document.getElementById('app-main');
  const navElement = document.getElementById('app-nav');

  const router = new Router({}, { rootElement });
  window.tasteopsRouter = router;

  // Register all required screens (and aliases)
  router.addRoute('/', renderDashboard);
  router.addRoute('/dashboard', renderDashboard);
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

  // Resolve current route
  router.resolve();
});
