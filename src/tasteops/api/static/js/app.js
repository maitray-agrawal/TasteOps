/**
 * TasteOps AI Operations Workspace Main Application Entrypoint.
 * Section 24: Information Architecture routes + deterministic execution pipeline.
 */

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

  // Resolve current route
  router.resolve();
});
