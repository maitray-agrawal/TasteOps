/**
 * TasteOps Execution Engine & Connector Screen (/sessions/[sessionId]/execution).
 *
 * Dispatches verified external integration tasks (Spotify audio seeding, smart lighting,
 * partner outreach) with idempotency guarantees, provenance binding, and execution tracking.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  formatDate,
  renderBadge,
  renderEmptyState,
  renderError,
  renderLoading,
  renderSubNav,
  showToast,
} from '../components/ui.js';

export async function renderSessionExecution(rootElement, params, router) {
  const sessionId = params.sessionId;
  if (!sessionId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="execution-screen-container">
      ${renderLoading('Loading execution engine state & task ledger...')}
    </div>
  `;

  const container = document.getElementById('execution-screen-container');

  const loadData = async () => {
    try {
      const session = await apiClient.getSession(sessionId);
      const isApproved = session.current_state === 'APPROVED';
      const isCompleted = session.current_state === 'COMPLETED';
      const isExecuting = session.current_state === 'EXECUTING';
      const isAwaiting = session.current_state === 'AWAITING_APPROVAL';

      const execState = session.execution_state || {};
      const tasks = execState.tasks || [];
      const totalTasks = execState.total_tasks || tasks.length;
      const executedTasks = execState.executed_tasks || tasks.filter(t => t.status === 'EXECUTED').length;
      const failedTasks = execState.failed_tasks || tasks.filter(t => t.status === 'FAILED').length;

      container.innerHTML = `
        <div class="fade-in">
          <header class="page-header" style="margin-bottom: 1.5rem;">
            <div class="page-title-group">
              <div class="page-breadcrumbs">
                <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                <span class="breadcrumb-separator">/</span>
                <a href="/sessions/${escapeHtml(sessionId)}" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}');">Session</a>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-primary);">Execution Engine</span>
              </div>
              <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem;">
                <span>External Execution Engine</span>
                ${renderBadge(session.current_state)}
              </h1>
              <p class="page-subtitle">
                Deterministic dispatch of acoustic seeding, hardware specifications, and brand outreach with provenance validation.
              </p>
            </div>

            <div>
              ${isApproved ? `
                <button class="btn btn-success btn-lg" id="btn-dispatch-tasks">
                  <span>⚡ Dispatch Verified Tasks</span>
                </button>
              ` : ''}
            </div>
          </header>

          <!-- Sub-navigation Tabs -->
          ${renderSubNav(sessionId, 'execution')}

          <div id="execution-alert-container"></div>

          <!-- Execution Status Banner -->
          ${isAwaiting ? `
            <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: var(--radius-lg); padding: 1.5rem; margin-bottom: 2rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.5rem; color: var(--amber);">⚠️</span>
                <div>
                  <div style="font-weight: 700; color: #fde68a;">Execution Gate Blocked</div>
                  <div style="font-size: 0.875rem; color: var(--text-secondary);">Tasks cannot be dispatched automatically. Explicit curator sign-off is required first.</div>
                </div>
              </div>
              <button class="btn btn-primary btn-sm" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/approval')">
                Open Approval Gate →
              </button>
            </div>
          ` : isApproved ? `
            <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: var(--radius-lg); padding: 1.5rem; margin-bottom: 2rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.5rem; color: var(--cyan);">⚡</span>
                <div>
                  <div style="font-weight: 700; color: #c7d2fe;">Plan Approved & Ready for Dispatch</div>
                  <div style="font-size: 0.875rem; color: var(--text-secondary);">Human curator sign-off verified. Click "Dispatch Verified Tasks" to execute downstream integrations with idempotency.</div>
                </div>
              </div>
            </div>
          ` : isCompleted ? `
            <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-lg); padding: 1.5rem; margin-bottom: 2rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.5rem; color: var(--emerald);">✓</span>
                <div>
                  <div style="font-weight: 700; color: #a7f3d0;">All Activation Tasks Confirmed Executed</div>
                  <div style="font-size: 0.875rem; color: var(--text-secondary);">Downstream hardware configurations, acoustic seeds, and partner briefs dispatched with cryptographic provenance.</div>
                </div>
              </div>
            </div>
          ` : ''}

          <!-- Task Counters -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem;">
            <div class="card" style="padding: 1.25rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Total Tasks</div>
              <div style="font-family: var(--font-heading); font-size: 1.75rem; font-weight: 700; color: var(--text-primary);">${totalTasks}</div>
            </div>

            <div class="card" style="padding: 1.25rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Executed</div>
              <div style="font-family: var(--font-heading); font-size: 1.75rem; font-weight: 700; color: var(--emerald);">${executedTasks}</div>
            </div>

            <div class="card" style="padding: 1.25rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Failed</div>
              <div style="font-family: var(--font-heading); font-size: 1.75rem; font-weight: 700; color: ${failedTasks > 0 ? 'var(--rose)' : 'var(--text-muted)'};">${failedTasks}</div>
            </div>

            <div class="card" style="padding: 1.25rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Idempotency Guard</div>
              <div style="font-size: 0.95rem; font-weight: 600; color: var(--cyan); margin-top: 0.4rem;">Enforced (SHA-256)</div>
            </div>
          </div>

          <!-- Tasks Ledger -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">
                <span>📋</span> Downstream Activation Tasks (${tasks.length})
              </div>
            </div>

            ${tasks.length > 0 ? `
              <div style="display: flex; flex-direction: column; gap: 1rem;">
                ${tasks.map(task => `
                  <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.25rem;">
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 0.5rem;">
                      <div>
                        <div style="font-weight: 600; font-size: 1rem; color: var(--text-primary); margin-bottom: 0.25rem;">
                          ${escapeHtml(task.action)}
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-muted);">
                          Category: <span style="color: var(--cyan); text-transform: uppercase; font-weight: 600;">${escapeHtml(task.category)}</span>
                          • Owner: <span>${escapeHtml(task.owner || 'GovernanceAgent')}</span>
                        </div>
                      </div>
                      ${renderBadge(task.status)}
                    </div>

                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); font-size: 0.775rem;">
                      <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="color: var(--text-muted);">Output URI:</span>
                        <span class="hash-pill" style="color: #34d399;">${escapeHtml(task.output_reference || 'pending://dispatch')}</span>
                      </div>
                      <div style="font-family: var(--font-mono); color: var(--text-muted);">
                        Idempotency: ${escapeHtml((task.idempotency_key || '').slice(0, 16))}...
                      </div>
                    </div>
                  </div>
                `).join('')}
              </div>
            ` : `
              ${renderEmptyState({
                icon: '⚡',
                title: 'No Tasks Dispatched Yet',
                description: isApproved
                  ? 'Click "Dispatch Verified Tasks" above to execute integration actions.'
                  : 'Tasks will be formulated by the Governance Agent once the plan is approved.',
              })}
            `}
          </div>
        </div>
      `;

      // Handle Dispatch Button Click
      document.getElementById('btn-dispatch-tasks')?.addEventListener('click', async () => {
        const btn = document.getElementById('btn-dispatch-tasks');
        btn.disabled = true;
        btn.textContent = 'Dispatching Integrations...';

        try {
          const res = await apiClient.executeSession(sessionId);
          showToast(`Executed ${res.executed_tasks} activation tasks successfully!`, 'success');
          loadData();
        } catch (err) {
          btn.disabled = false;
          btn.textContent = '⚡ Dispatch Verified Tasks';
          document.getElementById('execution-alert-container').innerHTML = renderError({
            title: 'Task Dispatch Failed',
            error: err,
          });
        }
      });

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Failed to Load Execution Engine',
        error: err,
        retryId: 'btn-retry-execution',
      });
      document.getElementById('btn-retry-execution')?.addEventListener('click', loadData);
    }
  };

  loadData();
}
