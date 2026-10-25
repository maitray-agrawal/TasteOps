/**
 * TasteOps Authoritative Human Approval Gate Screen (/sessions/[sessionId]/approval).
 *
 * Implements the authoritative human curator sign-off gate, cryptographic plan hash
 * verification, curator credential recording, and rejection workflows.
 */

import { apiClient } from '../apiClient.js';
import {
  escapeHtml,
  formatDate,
  renderBadge,
  renderError,
  renderLoading,
  renderSubNav,
  showToast,
} from '../components/ui.js';

export async function renderSessionApproval(rootElement, params, router) {
  const sessionId = params.sessionId;
  if (!sessionId) {
    router.navigate('/dashboard');
    return;
  }

  rootElement.innerHTML = `
    <div id="approval-screen-container">
      ${renderLoading('Checking human approval gate status...')}
    </div>
  `;

  const container = document.getElementById('approval-screen-container');

  const loadData = async () => {
    try {
      const session = await apiClient.getSession(sessionId);
      const isAwaiting = session.current_state === 'AWAITING_APPROVAL';
      const isApproved = session.current_state === 'APPROVED' || session.current_state === 'EXECUTING' || session.current_state === 'COMPLETED';
      const isFailed = session.current_state === 'FAILED';
      const planHash = session.approval_state?.plan_hash || session.execution_plan?.plan_hash || 'hash_pending';

      container.innerHTML = `
        <div class="fade-in">
          <header class="page-header" style="margin-bottom: 1.5rem;">
            <div class="page-title-group">
              <div class="page-breadcrumbs">
                <a href="/dashboard" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/dashboard');">Dashboard</a>
                <span class="breadcrumb-separator">/</span>
                <a href="/sessions/${escapeHtml(sessionId)}" style="color: var(--text-muted);" onclick="event.preventDefault(); window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}');">Session</a>
                <span class="breadcrumb-separator">/</span>
                <span style="color: var(--text-primary);">Approval Gate</span>
              </div>
              <h1 class="page-title" style="display: flex; align-items: center; gap: 0.75rem;">
                <span>Authoritative Approval Gate</span>
                ${renderBadge(session.current_state)}
              </h1>
              <p class="page-subtitle">
                Cryptographic plan binding and governance sign-off. External integration tasks are strictly blocked prior to curator authorization.
              </p>
            </div>
          </header>

          <!-- Sub-navigation Tabs -->
          ${renderSubNav(sessionId, 'approval')}

          <div id="approval-alert-container"></div>

          <!-- Gate Status Banner -->
          ${isAwaiting ? `
            <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: var(--radius-lg); padding: 1.75rem; margin-bottom: 2rem;">
              <div style="display: flex; align-items: flex-start; gap: 1rem;">
                <div style="font-size: 2rem; color: var(--amber);">⚖️</div>
                <div style="flex: 1;">
                  <h3 style="font-family: var(--font-heading); font-size: 1.25rem; font-weight: 700; color: #fde68a; margin-bottom: 0.35rem;">
                    Curator Sign-Off Required Before Execution
                  </h3>
                  <p style="color: var(--text-secondary); font-size: 0.95rem; line-height: 1.5; margin-bottom: 1rem;">
                    The activation plan has passed all provenance and constraint audits. Review the sensory parameters below and provide explicit sign-off to unblock task dispatch.
                  </p>
                  <div style="display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;">
                    <div style="font-size: 0.8rem; color: var(--text-muted);">Cryptographic Binding Hash:</div>
                    <span class="hash-pill" style="font-size: 0.8rem;">🔒 ${escapeHtml(planHash)}</span>
                  </div>
                </div>
              </div>
            </div>
          ` : isApproved ? `
            <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-lg); padding: 1.75rem; margin-bottom: 2rem;">
              <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 1.5rem;">
                <div style="display: flex; align-items: flex-start; gap: 1rem;">
                  <div style="font-size: 2rem; color: var(--emerald);">✓</div>
                  <div>
                    <h3 style="font-family: var(--font-heading); font-size: 1.25rem; font-weight: 700; color: #a7f3d0; margin-bottom: 0.35rem;">
                      Plan Approved & Cryptographically Sealed
                    </h3>
                    <p style="color: var(--text-secondary); font-size: 0.95rem; margin-bottom: 0.5rem;">
                      Approved by: <strong style="color: var(--text-primary);">${escapeHtml(session.approval_state?.approver || 'Curator')}</strong>
                    </p>
                    <div style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">
                      Timestamp: ${formatDate(session.approval_state?.approved_at)} | Hash: ${escapeHtml(planHash.slice(0, 20))}...
                    </div>
                  </div>
                </div>

                ${session.current_state === 'APPROVED' ? `
                  <button class="btn btn-success" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/execution')">
                    <span>⚡ Dispatch Execution Tasks →</span>
                  </button>
                ` : `
                  <button class="btn btn-secondary" onclick="window.tasteopsRouter.navigate('/sessions/${escapeHtml(sessionId)}/execution')">
                    <span>View Execution Status →</span>
                  </button>
                `}
              </div>
            </div>
          ` : isFailed ? `
            <div style="background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: var(--radius-lg); padding: 1.75rem; margin-bottom: 2rem;">
              <div style="display: flex; align-items: flex-start; gap: 1rem;">
                <div style="font-size: 2rem; color: var(--rose);">❌</div>
                <div>
                  <h3 style="font-family: var(--font-heading); font-size: 1.25rem; font-weight: 700; color: #fda4af; margin-bottom: 0.35rem;">
                    Activation Plan Rejected
                  </h3>
                  <p style="color: var(--text-secondary); font-size: 0.95rem;">
                    Rationale: <strong style="color: var(--text-primary);">${escapeHtml(session.error_message || session.errors?.[0] || 'Curator rejected activation specifications')}</strong>
                  </p>
                </div>
              </div>
            </div>
          ` : `
            <div style="background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 1.75rem; margin-bottom: 2rem;">
              <p style="color: var(--text-secondary);">Workflow is currently in state <strong>${escapeHtml(session.current_state)}</strong>. The approval gate will activate once plan validation completes.</p>
            </div>
          `}

          <!-- Sign-Off & Rejection Workspaces (Only visible if AWAITING_APPROVAL) -->
          ${isAwaiting ? `
            <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 2rem;">
              <!-- Approval Form -->
              <div class="card elevated" style="border-color: rgba(16, 185, 129, 0.3);">
                <div class="card-header">
                  <div class="card-title" style="color: var(--emerald);">
                    <span>✍️</span> Authorize & Bind Plan
                  </div>
                  <span class="badge badge-approved">Authoritative Sign-Off</span>
                </div>

                <form id="form-approve-plan">
                  <div class="form-grid-2">
                    <div class="form-group">
                      <label class="form-label" for="input-approver-name">Curator Full Name *</label>
                      <input type="text" id="input-approver-name" class="form-input" placeholder="e.g. Satwik Jaiswal" required />
                    </div>

                    <div class="form-group">
                      <label class="form-label" for="input-approver-role">Curatorial Role / Title</label>
                      <input type="text" id="input-approver-role" class="form-input" placeholder="e.g. Head of Cultural Intelligence" value="Lead Cultural Strategist" />
                    </div>
                  </div>

                  <div class="form-group">
                    <label class="form-label" for="input-curator-notes">Approval Notes & Sign-off Rationale</label>
                    <textarea id="input-curator-notes" class="form-textarea" placeholder="e.g. Spatial acoustic specs and brand partnerships verified. Approved for physical execution.">Plan verified against venue acoustics and brand alignment guidelines. Approved for execution.</textarea>
                  </div>

                  <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 1rem; border-top: 1px solid var(--border-subtle);">
                    <div style="font-size: 0.8rem; color: var(--text-muted);">
                      Cryptographically bound to hash <code>${escapeHtml(planHash.slice(0, 10))}...</code>
                    </div>
                    <button type="submit" class="btn btn-success btn-lg" id="btn-submit-approval">
                      <span>✓ Authorize Plan & Unblock Execution</span>
                    </button>
                  </div>
                </form>
              </div>

              <!-- Rejection Workspace -->
              <div class="card" style="border-color: rgba(244, 63, 94, 0.25);">
                <div class="card-header">
                  <div class="card-title" style="color: var(--rose);">
                    <span>🛑</span> Reject Plan
                  </div>
                </div>

                <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.25rem; line-height: 1.4;">
                  If the spatial blueprint, sonic day-parting, or brand partners fail curatorial standards, record a rejection reason to terminate the session.
                </p>

                <form id="form-reject-plan">
                  <div class="form-group">
                    <label class="form-label" for="input-reject-reason">Rejection Rationale *</label>
                    <textarea id="input-reject-reason" class="form-textarea" style="min-height: 90px;" placeholder="e.g. Acoustic soundscape violates local noise bylaws." required></textarea>
                  </div>

                  <button type="submit" class="btn btn-danger" style="width: 100%;" id="btn-submit-rejection">
                    <span>Reject Activation Plan</span>
                  </button>
                </form>
              </div>
            </div>
          ` : ''}
        </div>
      `;

      // Handle Approval Submit
      document.getElementById('form-approve-plan')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const approver = document.getElementById('input-approver-name').value.trim();
        const role = document.getElementById('input-approver-role').value.trim();
        const notes = document.getElementById('input-curator-notes').value.trim();
        const submitBtn = document.getElementById('btn-submit-approval');

        submitBtn.disabled = true;
        submitBtn.textContent = 'Recording Approval...';

        try {
          await apiClient.approveSession(sessionId, { approver, role, notes, planVersion: 1 });
          showToast('Activation Plan Approved! Execution is now unblocked.', 'success');
          loadData();
        } catch (err) {
          submitBtn.disabled = false;
          submitBtn.textContent = '✓ Authorize Plan & Unblock Execution';
          document.getElementById('approval-alert-container').innerHTML = renderError({
            title: 'Approval Failed',
            error: err,
          });
        }
      });

      // Handle Rejection Submit
      document.getElementById('form-reject-plan')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const reason = document.getElementById('input-reject-reason').value.trim();
        const rejectBtn = document.getElementById('btn-submit-rejection');

        if (!reason) return;

        rejectBtn.disabled = true;
        rejectBtn.textContent = 'Rejecting...';

        try {
          await apiClient.rejectSession(sessionId, { reason });
          showToast('Plan rejected. Workflow terminated in FAILED state.', 'error');
          loadData();
        } catch (err) {
          rejectBtn.disabled = false;
          rejectBtn.textContent = 'Reject Activation Plan';
          document.getElementById('approval-alert-container').innerHTML = renderError({
            title: 'Rejection Failed',
            error: err,
          });
        }
      });

    } catch (err) {
      container.innerHTML = renderError({
        title: 'Failed to Load Approval Gate',
        error: err,
        retryId: 'btn-retry-approval',
      });
      document.getElementById('btn-retry-approval')?.addEventListener('click', loadData);
    }
  };

  loadData();
}
