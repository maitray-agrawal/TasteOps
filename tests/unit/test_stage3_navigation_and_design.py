"""Stage 3 Unit & Contract Verification: Navigation Integrity, Design System Tokens, and Human Approval UX."""

from __future__ import annotations

import pathlib

import pytest
from httpx import ASGITransport, AsyncClient

from tasteops.api.main import app
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.states import WorkflowState


def test_index_css_contains_design_tokens_and_navigation_classes() -> None:
    """Verifies that index.css defines all required design system tokens and navigation classes."""
    css_path = (
        pathlib.Path(__file__).parents[2]
        / "src"
        / "tasteops"
        / "api"
        / "static"
        / "css"
        / "index.css"
    )
    assert css_path.exists(), "index.css must exist"
    content = css_path.read_text(encoding="utf-8")

    # Required Surface & Design Tokens
    required_tokens = [
        "--bg-surface",
        "--bg-surface-elevated",
        "--bg-deep",
        "--bg-card",
        "--primary",
        "--cyan",
        "--amber",
        "--emerald",
        "--rose",
        "--font-heading",
        "--focus-ring",
    ]
    for token in required_tokens:
        assert token in content, f"CSS variable '{token}' must be declared in :root"

    # Required Navigation & Component Classes
    required_classes = [
        ".session-nav-bar",
        ".session-tabs-container",
        ".session-tab-item",
        ".session-tab-item.active",
        ".curatorial-certificate",
        ".governance-checklist",
        ".checklist-row",
        ".crypto-hash-box",
        ".copy-hash-btn",
        ".card",
        ".card-header",
        ".card-title",
        ".btn",
        ".btn-primary",
        ".btn-success",
        ".btn-danger",
    ]
    for cls in required_classes:
        assert cls in content, f"CSS class '{cls}' must be defined in index.css"


def test_ui_js_defines_authoritative_sub_navigation() -> None:
    """Verifies that renderSubNav provides all 6 destinations with semantic role=tab."""
    ui_path = (
        pathlib.Path(__file__).parents[2]
        / "src"
        / "tasteops"
        / "api"
        / "static"
        / "js"
        / "components"
        / "ui.js"
    )
    assert ui_path.exists(), "ui.js must exist"
    content = ui_path.read_text(encoding="utf-8")

    # 6 required workspace destinations
    destinations = [
        "overview",
        "activity",
        "blueprint",
        "approval",
        "execution",
        "ledger",
    ]
    for dest in destinations:
        assert f"key: '{dest}'" in content, (
            f"Destination '{dest}' must be registered in renderSubNav"
        )

    # Semantic accessibility attributes
    assert 'role="tab"' in content, "Tabs must declare role='tab'"
    assert 'role="tablist"' in content, "Tab bar container must declare role='tablist'"
    assert "session-tab-item" in content, "Tabs must use session-tab-item class"


def test_session_approval_screen_integrity() -> None:
    """Verifies that sessionApproval.js provides review summary, governance checklist, and certificate."""
    approval_path = (
        pathlib.Path(__file__).parents[2]
        / "src"
        / "tasteops"
        / "api"
        / "static"
        / "js"
        / "screens"
        / "sessionApproval.js"
    )
    assert approval_path.exists(), "sessionApproval.js must exist"
    content = approval_path.read_text(encoding="utf-8")

    # Header & Review summary
    assert "Review & Approve Experience Plan" in content
    assert "Curatorial Review Summary" in content

    # 6 structured governance checks
    assert "Cultural Intelligence Provenance Verification" in content
    assert "Physical Space Constraints" in content
    assert "Budget Envelope & Financial Allocation" in content
    assert "Sensory Acoustic Coherence" in content
    assert "Commercial Partnership" in content
    assert "Cryptographic Plan Digest & Tamper Verification" in content

    # Certificate & Copy button
    assert "Curatorial Certificate of Authorization" in content
    assert "crypto-hash-box" in content
    assert "btn-copy-hash" in content


@pytest.mark.asyncio
async def test_backend_approval_enforces_governance_gate() -> None:
    """Verifies that execution remains blocked before approval, and approval transitions to APPROVED."""
    orch = TasteOpsOrchestrator()
    app.state.orchestrator = orch

    ctx = orch.create_session("Tokyo vinyl listening lounge")
    orch._active_sessions[ctx.session_id] = ctx
    orch.store.save_context(ctx)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Direct execution attempt before approval must be rejected by backend
        exec_res = await client.post(f"/api/v1/sessions/{ctx.session_id}/execute")
        assert exec_res.status_code == 400
        err_body = exec_res.json()
        err_msg = (err_body.get("message") or err_body.get("detail") or "").lower()
        assert (
            "cannot transition" in err_msg
            or "invalid" in err_msg
            or "unapproved" in err_msg
        )

        # 2. Advance workflow to AWAITING_APPROVAL without plan -> Must be blocked
        ctx.current_state = WorkflowState.AWAITING_APPROVAL
        orch.store.save_context(ctx)

        approve_fail_res = await client.post(
            f"/api/v1/sessions/{ctx.session_id}/approve",
            json={"approver": "Lead Curator", "notes": "Premature attempt"},
        )
        assert approve_fail_res.status_code == 400
        fail_msg = (approve_fail_res.json().get("message") or "").lower()
        assert "plan is missing" in fail_msg

        # 3. Attach valid plan and approve
        from tests.unit.test_approval_gate import _create_valid_plan

        ctx.plan = await _create_valid_plan()
        orch.store.save_context(ctx)

        # 4. Authoritative sign-off
        approve_res = await client.post(
            f"/api/v1/sessions/{ctx.session_id}/approve",
            json={
                "approver": "Lead Curator",
                "notes": "Verified Qloo provenance and sensory acoustics",
            },
        )
        assert approve_res.status_code == 200
        data = approve_res.json()
        assert data["current_state"] == "APPROVED"
        assert data["approval"]["is_valid"] is True
        assert data["approval"]["approver"] == "Lead Curator"
        assert len(data["approval"]["plan_hash"]) == 64
