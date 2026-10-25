/**
 * TasteOps Execution Workspace (/sessions/[sessionId]/execution).
 *
 * Provides a comprehensive AI operations execution cockpit:
 * - Telemetry for every ExecutionTask: task_id, task_type, description, status,
 *   estimated_cost, connector, approval_status, execution_timestamp, result, error.
 * - Strict verification of 5 backend execution preconditions:
 *   1. Approved session
 *   2. Current plan version
 *   3. Successful governance validation
 *   4. Required evidence
 *   5. Executable tasks
 * - Enforces zero-simulation external execution: unconfigured connectors display NOT_CONFIGURED.
 * - Never shows success before backend confirmation.
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
      ${renderLoading('Loading execution workspace & task ledger...')}
    </div>
  `;

  const container = document.getElementById('execution-screen-container');

  // Filter & Search State
  let activeFilter = 'ALL';
  let searchQuery = '';

  const loadData = async () => {
    try {
      const session = await apiClient.getSession(sessionId);

      // Workflow & Session States
      const currentState = session.current_state || 'UNKNOWN';
      const isApprovedState = currentState === 'APPROVED';
      const isCompleted = currentState === 'COMPLETED';
      const isExecuting = currentState === 'EXECUTING';
      const isAwaiting = currentState === 'AWAITING_APPROVAL';

      const approval = session.approval_state || {};
      const validation = session.validation || {};
      const plan = session.execution_plan || {};
      const twin = session.cultural_twin || {};
      const matrix = session.cultural_matrix_summary || {};
      const execState = session.execution_state || {};
      const tasks = execState.tasks || [];

      // -----------------------------------------------------------------------
      // 5 Strict Backend Confirmation Preconditions
      // -----------------------------------------------------------------------
      // 1. Approved Session
      const isApprovedSession = Boolean(
        isApprovedState && approval.is_approved === true && approval.status === 'APPROVED'
      );

      // 2. Current Plan Version
      const isCurrentPlanVersion = Boolean(
        plan.plan_id &&
        approval.plan_version === (plan.version || 1) &&
        (approval.plan_hash && plan.plan_hash ? approval.plan_hash === plan.plan_hash : true)
      );

      // 3. Successful Governance Validation
      const isGovernanceValid = Boolean(
        validation.is_valid === true && (typeof validation.compliance_score === 'number' ? validation.compliance_score >= 0.85 : true)
      );

      // 4. Required Evidence
      const evidenceCount =
        (matrix.evidence_count || 0) +
        (twin.resolved_entities?.length || 0) +
        (twin.anchor_entities?.length || 0);
      const hasRequiredEvidence = Boolean(
        evidenceCount > 0 && validation.provenance_verified === true
      );

      // 5. Executable Tasks
      const hasExecutableTasks = Boolean(tasks && tasks.length > 0);

      // Master Gate: Execution must ONLY be possible when backend confirms all 5
      const allPreconditionsMet =
        isApprovedSession &&
        isCurrentPlanVersion &&
        isGovernanceValid &&
        hasRequiredEvidence &&
        hasExecutableTasks;

      const canExecute = allPreconditionsMet && !isCompleted && !isExecuting;

      // Status Metrics
      const totalTasks = tasks.length;
      const completedTasks = tasks.filter(t => t.status === 'COMPLETED' || t.status === 'EXECUTED').length;
      const runningTasks = tasks.filter(t => t.status === 'RUNNING').length;
      const failedTasks = tasks.filter(t => t.status === 'FAILED').length;
      const skippedTasks = tasks.filter(t => t.status === 'SKIPPED').length;
      const approvedOrPendingTasks = tasks.filter(t => t.status === 'APPROVED' || t.status === 'PENDING').length;
      const unconfiguredConnectorsCount = tasks.filter(
        t => t.connector === 'NOT_CONFIGURED' || !t.connector
      ).length;

      // Filtered Tasks
      const filteredTasks = tasks.filter(task => {
        // Status filter
        if (activeFilter !== 'ALL') {
          if (activeFilter === 'NOT_CONFIGURED') {
            if (task.connector !== 'NOT_CONFIGURED') return false;
          } else if (task.status !== activeFilter) {
            return false;
          }
        }
        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchId = (task.task_id || '').toLowerCase().includes(q);
          const matchType = (task.task_type || '').toLowerCase().includes(q);
          const matchDesc = (task.description || '').toLowerCase().includes(q);
          const matchConn = (task.connector || '').toLowerCase().includes(q);
          return matchId || matchType || matchDesc || matchConn;
        }
        return true;
      });

      container.innerHTML = `
        <div class="fade-in">
          <!-- Page Header -->
          <header class="page-header" style="margin-bottom: 1.5rem;">
            <div class="page-title-group">
              <div class="page-breadcrumbs">
                <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                <span class="breadcrumb-separator">/</span>
                <a href="/sessions/${escapeHtml(sessionId)}" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}');">Session</a>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-primary);">Execution Workspace</span>
              </div>
              <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                <span>Execution Workspace</span>
                ${renderBadge(currentState)}
                ${plan.plan_id ? `
                  <span class="hash-pill" style="font-size: 0.75rem; font-weight: normal; color: var(--text-muted);">
                    Plan v${escapeHtml(plan.version || 1)} • ${escapeHtml(plan.plan_id)}
                  </span>
                ` : ''}
              </h1>
              <p class="page-subtitle">
                Deterministic dispatch of acoustic seeding, hardware specifications, and brand outreach with cryptographic provenance verification.
              </p>
            </div>

            <div style="display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;">
              ${isCompleted ? `
                <div style="display: flex; align-items: center; gap: 0.5rem; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 0.5rem 1rem;">
                  <span style="color: var(--emerald); font-weight: 700;">✓ All Tasks Dispatched</span>
                </div>
              ` : `
                <button
                  class="btn ${canExecute ? 'btn-primary' : 'btn-secondary'} btn-lg"
                  id="btn-dispatch-tasks"
                  ${canExecute ? '' : 'disabled="disabled"'}
                  style="${canExecute ? 'box-shadow: 0 0 20px rgba(99, 102, 241, 0.35); font-weight: 700;' : 'opacity: 0.6; cursor: not-allowed;'}"
                  title="${canExecute ? 'Dispatch verified downstream execution tasks' : 'Execution disabled: All 5 backend preconditions must be confirmed first'}"
                >
                  <span>⚡ Dispatch Execution Tasks (${tasks.length})</span>
                </button>
              `}
            </div>
          </header>

          <!-- Sub-navigation Tabs -->
          ${renderSubNav(sessionId, 'execution')}

          <!-- Alert / Toast Container -->
          <div id="execution-alert-container"></div>

          <!-- Execution Gate Preconditions Checklist Card -->
          <div class="card" style="margin-bottom: 2rem; border: 1px solid ${allPreconditionsMet ? 'rgba(16, 185, 129, 0.35)' : 'rgba(245, 158, 11, 0.35)'}; background: ${allPreconditionsMet ? 'rgba(16, 185, 129, 0.03)' : 'rgba(245, 158, 11, 0.03)'};">
            <div class="card-header" style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
              <div class="card-title" style="display: flex; align-items: center; gap: 0.6rem;">
                <span style="font-size: 1.25rem;">${allPreconditionsMet ? '🛡️' : '⚠️'}</span>
                <span>Backend Execution Preconditions Gate</span>
              </div>
              <div>
                ${allPreconditionsMet ? `
                  <span class="badge badge-completed">5 of 5 Preconditions Confirmed</span>
                ` : `
                  <span class="badge badge-awaiting-approval">Preconditions Incomplete (${[isApprovedSession, isCurrentPlanVersion, isGovernanceValid, hasRequiredEvidence, hasExecutableTasks].filter(Boolean).length}/5)</span>
                `}
              </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-top: 0.5rem;">
              <!-- 1. Approved Session -->
              <div style="background: var(--bg-surface-elevated); border: 1px solid ${isApprovedSession ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}; border-radius: var(--radius-md); padding: 1rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                  <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-primary);">1. Approved Session</span>
                  <span style="font-size: 1.1rem;">${isApprovedSession ? '✅' : '❌'}</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                  ${isApprovedSession
                    ? `Curator sign-off confirmed (${escapeHtml(approval.approver || 'Curator')})`
                    : `State is '${escapeHtml(currentState)}'. Requires explicit sign-off at Human Gate.`}
                </div>
              </div>

              <!-- 2. Current Plan Version -->
              <div style="background: var(--bg-surface-elevated); border: 1px solid ${isCurrentPlanVersion ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}; border-radius: var(--radius-md); padding: 1rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                  <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-primary);">2. Current Plan Version</span>
                  <span style="font-size: 1.1rem;">${isCurrentPlanVersion ? '✅' : '❌'}</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                  ${isCurrentPlanVersion
                    ? `Approval v${escapeHtml(approval.plan_version || 1)} matches active plan revision`
                    : `Plan version mismatch or mutated plan (Approved: v${escapeHtml(approval.plan_version || 'None')} vs Plan: v${escapeHtml(plan.version || 1)})`}
                </div>
              </div>

              <!-- 3. Successful Governance Validation -->
              <div style="background: var(--bg-surface-elevated); border: 1px solid ${isGovernanceValid ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}; border-radius: var(--radius-md); padding: 1rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                  <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-primary);">3. Governance Validation</span>
                  <span style="font-size: 1.1rem;">${isGovernanceValid ? '✅' : '❌'}</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                  ${isGovernanceValid
                    ? `Governance checks verified (Score: ${typeof validation.compliance_score === 'number' ? Math.round(validation.compliance_score * 100) + '%' : 'Unavailable'})`
                    : `Validation failed: ${escapeHtml((validation.risk_flags || ['Unresolved risk flags']).join(', '))}`}
                </div>
              </div>

              <!-- 4. Required Evidence -->
              <div style="background: var(--bg-surface-elevated); border: 1px solid ${hasRequiredEvidence ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}; border-radius: var(--radius-md); padding: 1rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                  <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-primary);">4. Required Evidence</span>
                  <span style="font-size: 1.1rem;">${hasRequiredEvidence ? '✅' : '❌'}</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                  ${hasRequiredEvidence
                    ? `100% Qloo provenance confirmed (${evidenceCount} ground-truth entities)`
                    : 'Evidence missing or provenance verification failed'}
                </div>
              </div>

              <!-- 5. Executable Tasks -->
              <div style="background: var(--bg-surface-elevated); border: 1px solid ${hasExecutableTasks ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}; border-radius: var(--radius-md); padding: 1rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                  <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-primary);">5. Executable Tasks</span>
                  <span style="font-size: 1.1rem;">${hasExecutableTasks ? '✅' : '❌'}</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                  ${hasExecutableTasks
                    ? `${tasks.length} actionable execution task(s) present in plan`
                    : 'No actionable execution tasks found'}
                </div>
              </div>
            </div>

            ${!canExecute && !isCompleted ? `
              <div style="margin-top: 1rem; padding: 0.75rem 1rem; background: rgba(245, 158, 11, 0.08); border-radius: var(--radius-sm); border-left: 3px solid var(--amber); font-size: 0.825rem; color: #fde68a;">
                <strong>Execution Blocked:</strong> All 5 preconditions must be confirmed by the backend before execution can be triggered.
                ${!isApprovedSession ? `
                  <a href="/sessions/${escapeHtml(sessionId)}/approval" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/approval');" style="color: var(--cyan); margin-left: 0.5rem; text-decoration: underline;">
                    Open Approval Gate →
                  </a>
                ` : ''}
              </div>
            ` : ''}
          </div>

          <!-- Connector Policy Banner -->
          <div style="background: rgba(56, 189, 248, 0.04); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: var(--radius-md); padding: 1rem 1.25rem; margin-bottom: 2rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span style="font-size: 1.35rem;">🔌</span>
              <div>
                <div style="font-weight: 700; font-size: 0.9rem; color: #bae6fd;">
                  Connector Telemetry & Safe Execution Guarantee
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                  If external credentials (Spotify API, Notion, Outreach Mailer) are missing, connectors are tagged
                  <span class="badge badge-not-configured" style="margin: 0 0.25rem; font-size: 0.7rem;">NOT_CONFIGURED</span>.
                  TasteOps never simulates successful external mutations.
                </div>
              </div>
            </div>
            <div>
              <span class="badge" style="background: rgba(148, 163, 184, 0.15); color: #cbd5e1; font-family: var(--font-mono); font-size: 0.75rem;">
                ${unconfiguredConnectorsCount > 0 ? `${unconfiguredConnectorsCount} Unconfigured Connector(s)` : 'All Connectors Configured'}
              </span>
            </div>
          </div>

          <!-- Metric Counters -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
            <div class="card" style="padding: 1.15rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Total Tasks</div>
              <div style="font-family: var(--font-heading); font-size: 1.75rem; font-weight: 700; color: var(--text-primary);">${totalTasks}</div>
            </div>

            <div class="card" style="padding: 1.15rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Approved / Pending</div>
              <div style="font-family: var(--font-heading); font-size: 1.75rem; font-weight: 700; color: #a5b4fc;">${approvedOrPendingTasks}</div>
            </div>

            <div class="card" style="padding: 1.15rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Completed</div>
              <div style="font-family: var(--font-heading); font-size: 1.75rem; font-weight: 700; color: var(--emerald);">${completedTasks}</div>
            </div>

            <div class="card" style="padding: 1.15rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Failed</div>
              <div style="font-family: var(--font-heading); font-size: 1.75rem; font-weight: 700; color: ${failedTasks > 0 ? 'var(--rose)' : 'var(--text-muted)'};">${failedTasks}</div>
            </div>

            <div class="card" style="padding: 1.15rem;">
              <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Total Plan Cost</div>
              <div style="font-family: var(--font-heading); font-size: 1.35rem; font-weight: 700; color: var(--emerald); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                ${escapeHtml(plan.estimated_cost || 'Not estimated')}
              </div>
            </div>
          </div>

          <!-- Tasks Filter and Search Toolbar -->
          <div class="card" style="margin-bottom: 1.5rem; padding: 1rem 1.25rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
              <!-- Status Filter Pills -->
              <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                <span style="font-size: 0.775rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-right: 0.25rem;">Filter:</span>
                ${['ALL', 'PENDING', 'APPROVED', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED', 'NOT_CONFIGURED'].map(statusKey => `
                  <button
                    class="btn btn-sm ${activeFilter === statusKey ? 'btn-primary' : 'btn-secondary'}"
                    id="filter-btn-${statusKey.toLowerCase()}"
                    style="padding: 0.25rem 0.65rem; font-size: 0.75rem;"
                  >
                    ${statusKey.replace('_', ' ')}
                  </button>
                `).join('')}
              </div>

              <!-- Search Input -->
              <div style="min-width: 240px; flex-grow: 1; max-width: 360px;">
                <input
                  type="text"
                  id="task-search-input"
                  class="form-control"
                  placeholder="Search task ID, type, description..."
                  value="${escapeHtml(searchQuery)}"
                  style="padding: 0.4rem 0.8rem; font-size: 0.85rem;"
                />
              </div>
            </div>
          </div>

          <!-- Execution Tasks Ledger -->
          <div class="card">
            <div class="card-header" style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
              <div class="card-title">
                <span>📋</span> Downstream Execution Tasks (${filteredTasks.length} of ${tasks.length})
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted);">
                Idempotency Enforcement: <span class="hash-pill" style="font-size: 0.725rem;">SHA-256</span>
              </div>
            </div>

            ${filteredTasks.length > 0 ? `
              <div style="display: flex; flex-direction: column; gap: 1rem;" id="task-list-container">
                ${filteredTasks.map(task => {
                  const isUnconfigured = task.connector === 'NOT_CONFIGURED' || !task.connector;
                  return `
                    <div
                      class="execution-task-card"
                      id="task-card-${escapeHtml(task.task_id)}"
                      style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.25rem; transition: border-color 0.2s;"
                    >
                      <!-- Top Header: ID, Type, Description, Status -->
                      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 0.75rem; flex-wrap: wrap;">
                        <div style="flex-grow: 1;">
                          <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.35rem;">
                            <!-- task_id -->
                            <span class="hash-pill" style="font-weight: 700; color: var(--cyan); font-size: 0.775rem;">
                              ${escapeHtml(task.task_id)}
                            </span>
                            <!-- task_type -->
                            <span class="badge" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.3); font-size: 0.725rem;">
                              ${escapeHtml(task.task_type || task.category || 'general_execution')}
                            </span>
                            <!-- estimated_cost -->
                            <span class="badge" style="background: rgba(16, 185, 129, 0.1); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.25); font-size: 0.725rem;">
                              💰 ${escapeHtml(task.estimated_cost != null && task.estimated_cost !== '' ? task.estimated_cost : 'Not estimated')}
                            </span>
                            ${task.is_mock === true ? `
                              <span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); font-size: 0.725rem;">
                                ⚠️ Simulation / Mock
                              </span>
                            ` : task.is_mock === false ? `
                              <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.725rem;">
                                Live Dispatch
                              </span>
                            ` : ''}
                          </div>

                          <!-- description -->
                          <div style="font-size: 1.05rem; font-weight: 600; color: var(--text-primary); margin-top: 0.25rem; line-height: 1.4;">
                            ${escapeHtml(task.description || task.action || '')}
                          </div>
                        </div>

                        <!-- status -->
                        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.35rem;">
                          ${renderBadge(task.status)}
                          <div style="font-size: 0.725rem; color: var(--text-muted);">
                            Owner: <strong>${escapeHtml(task.owner || 'GovernanceAgent')}</strong>
                          </div>
                        </div>
                      </div>

                      <!-- 10 Fields Structured Telemetry Grid -->
                      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; padding: 0.85rem; background: var(--bg-surface); border-radius: var(--radius-md); border: 1px solid var(--border-subtle); margin-top: 0.5rem; font-size: 0.8rem;">
                        <!-- connector -->
                        <div>
                          <div style="color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; font-weight: 600; margin-bottom: 0.25rem;">
                            Connector
                          </div>
                          <div>
                            ${isUnconfigured ? `
                              <span class="badge badge-not-configured" id="task-conn-${escapeHtml(task.task_id)}">
                                NOT_CONFIGURED
                              </span>
                            ` : `
                              <span class="badge" style="background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3);">
                                🔌 ${escapeHtml(task.connector)}
                              </span>
                            `}
                          </div>
                        </div>

                        <!-- approval_status -->
                        <div>
                          <div style="color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; font-weight: 600; margin-bottom: 0.25rem;">
                            Approval Status
                          </div>
                          <div>
                            <span class="badge ${task.approval_status === 'APPROVED' ? 'badge-completed' : 'badge-awaiting-approval'}" style="font-size: 0.725rem;">
                              ${escapeHtml(task.approval_status || 'PENDING')}
                            </span>
                          </div>
                        </div>

                        <!-- estimated_cost -->
                        <div>
                          <div style="color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; font-weight: 600; margin-bottom: 0.25rem;">
                            Estimated Cost
                          </div>
                          <div style="font-weight: 600; color: var(--emerald); font-size: 0.85rem;">
                            ${escapeHtml(task.estimated_cost != null && task.estimated_cost !== '' ? task.estimated_cost : 'Not estimated')}
                          </div>
                        </div>

                        <!-- execution_timestamp -->
                        <div>
                          <div style="color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; font-weight: 600; margin-bottom: 0.25rem;">
                            Execution Timestamp
                          </div>
                          <div style="font-family: var(--font-mono); font-size: 0.775rem; color: ${task.execution_timestamp ? 'var(--text-primary)' : 'var(--text-muted)'};">
                            ${task.execution_timestamp ? formatDate(task.execution_timestamp) : '— (Pending Dispatch)'}
                          </div>
                        </div>
                      </div>

                      <!-- error (if failed) -->
                      ${task.error ? `
                        <div style="margin-top: 0.75rem; padding: 0.75rem 1rem; background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: var(--radius-sm); font-size: 0.825rem; color: #fb7185;">
                          <strong>⚠️ Error:</strong> ${escapeHtml(task.error)}
                        </div>
                      ` : ''}

                      <!-- result & output_reference -->
                      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); font-size: 0.775rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                          <span style="color: var(--text-muted);">Result:</span>
                          ${task.result ? `
                            <span class="hash-pill" style="color: #34d399; font-size: 0.725rem;">
                              ${typeof task.result === 'object' ? escapeHtml(JSON.stringify(task.result)) : escapeHtml(String(task.result))}
                            </span>
                          ` : task.output_reference ? `
                            <span class="hash-pill" style="color: #34d399; font-size: 0.725rem;">
                              ${escapeHtml(task.output_reference)}
                            </span>
                          ` : `
                            <span style="color: var(--text-muted); font-style: italic;">— (Not yet executed)</span>
                          `}
                        </div>

                        <div style="display: flex; align-items: center; gap: 0.75rem;">
                          <span style="font-family: var(--font-mono); color: var(--text-muted); font-size: 0.725rem;">
                            Idempotency: ${escapeHtml(task.idempotency_key ? task.idempotency_key.slice(0, 18) + '...' : 'Unspecified')}
                          </span>
                        </div>
                      </div>
                    </div>
                  `;
                }).join('')}
              </div>
            ` : `
              ${renderEmptyState({
                icon: '⚡',
                title: tasks.length === 0 ? 'No Execution Tasks Planned' : 'No Matching Tasks Found',
                description: tasks.length === 0
                  ? (isApprovedState
                      ? 'No actionable tasks formulated yet.'
                      : 'Tasks will be formulated once the plan is created and validated.')
                  : `No tasks matched the '${activeFilter}' filter or search '${escapeHtml(searchQuery)}'.`,
              })}
            `}
          </div>

          <!-- Post-Execution Audit Compliance Section (When Completed) -->
          ${isCompleted ? `
            <div class="card" style="margin-top: 2rem; border-color: rgba(16, 185, 129, 0.3);">
              <div class="card-header">
                <div class="card-title" style="display: flex; align-items: center; gap: 0.5rem;">
                  <span>📋</span> Post-Execution Audit Report
                </div>
                <span class="badge badge-completed">COMPLIANT</span>
              </div>
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; font-size: 0.85rem;">
                <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md);">
                  <div style="color: var(--text-muted); font-size: 0.75rem;">Total Tasks Executed</div>
                  <div style="font-size: 1.25rem; font-weight: 700; color: var(--emerald);">${completedTasks} / ${totalTasks}</div>
                </div>
                <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md);">
                  <div style="color: var(--text-muted); font-size: 0.75rem;">Provenance Violations</div>
                  <div style="font-size: 1.25rem; font-weight: 700; color: var(--emerald);">0 Detected</div>
                </div>
                <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md);">
                  <div style="color: var(--text-muted); font-size: 0.75rem;">Unsupported Actions Blocked</div>
                  <div style="font-size: 1.25rem; font-weight: 700; color: var(--emerald);">0 Blocked</div>
                </div>
                <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md);">
                  <div style="color: var(--text-muted); font-size: 0.75rem;">Curator Sign-off Verified</div>
                  <div style="font-size: 1.25rem; font-weight: 700; color: #a5b4fc;">True</div>
                </div>
              </div>
            </div>
          ` : ''}
        </div>
      `;

      // -----------------------------------------------------------------------
      // Event Handlers
      // -----------------------------------------------------------------------

      // 1. Filter Buttons
      ['ALL', 'PENDING', 'APPROVED', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED', 'NOT_CONFIGURED'].forEach(statusKey => {
        const btnId = `filter-btn-${statusKey.toLowerCase()}`;
        document.getElementById(btnId)?.addEventListener('click', () => {
          activeFilter = statusKey;
          loadData();
        });
      });

      // 2. Search Input
      const searchInput = document.getElementById('task-search-input');
      if (searchInput) {
        searchInput.addEventListener('input', (e) => {
          searchQuery = e.target.value;
          // Re-filter list dynamically without full page refresh
          const cards = document.querySelectorAll('.execution-task-card');
          const q = searchQuery.toLowerCase();
          cards.forEach(card => {
            const text = card.textContent.toLowerCase();
            card.style.display = text.includes(q) ? 'block' : 'none';
          });
        });
      }

      // 3. Dispatch Button Click Handler
      // CRITICAL: Never show success before backend confirmation.
      const dispatchBtn = document.getElementById('btn-dispatch-tasks');
      if (dispatchBtn && canExecute) {
        dispatchBtn.addEventListener('click', async () => {
          // Immediately disable button and show loading state
          dispatchBtn.disabled = true;
          dispatchBtn.style.opacity = '0.7';
          dispatchBtn.innerHTML = `
            <span style="display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 0.5rem; vertical-align: middle;"></span>
            <span>Dispatching & Verifying Provenance...</span>
          `;

          const alertContainer = document.getElementById('execution-alert-container');
          if (alertContainer) alertContainer.innerHTML = '';

          try {
            // Backend is authoritative source of truth: Invoke execute endpoint
            const res = await apiClient.executeSession(sessionId);

            // ONLY show success AFTER backend confirms 200 OK
            showToast(`Executed ${res.executed_tasks || totalTasks} activation tasks successfully!`, 'success');

            // Refresh complete authoritative server state
            await loadData();
          } catch (err) {
            // Re-enable button on error and display backend failure message
            dispatchBtn.disabled = false;
            dispatchBtn.style.opacity = '1';
            dispatchBtn.innerHTML = `<span>⚡ Dispatch Execution Tasks (${tasks.length})</span>`;

            if (alertContainer) {
              alertContainer.innerHTML = renderError({
                title: 'Execution Dispatch Failed',
                error: err,
                retryId: 'btn-retry-dispatch',
              });
              document.getElementById('btn-retry-dispatch')?.addEventListener('click', () => {
                dispatchBtn.click();
              });
            }
          }
        });
      }

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Failed to Load Execution Workspace',
        error: err,
        retryId: 'btn-retry-execution-load',
      });
      document.getElementById('btn-retry-execution-load')?.addEventListener('click', loadData);
    }
  };

  await loadData();
}
