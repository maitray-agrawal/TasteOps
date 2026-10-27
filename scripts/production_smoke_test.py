"""TasteOps Production End-to-End API Smoke Test and Execution Truthfulness Verification."""

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.getenv("TASTEOPS_BASE_URL", "https://tasteops-backend.onrender.com")


def http_post(path: str, payload: dict | None = None) -> tuple[int, dict, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else b""
    headers = {
        "Accept": "application/json",
        "Connection": "close",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            headers = dict(resp.headers)
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body), headers
    except urllib.error.HTTPError as exc:
        headers = dict(exc.headers)
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed, headers


def http_get(path: str) -> tuple[int, dict, dict]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Connection": "close"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            headers = dict(resp.headers)
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body), headers
    except urllib.error.HTTPError as exc:
        headers = dict(exc.headers)
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed, headers


def run_smoke_test():
    results = {}
    print("=== TASTEOPS LIVE PRODUCTION SMOKE TEST ===")
    print(f"Target: {BASE_URL}")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")

    # 1. Health Probe
    status, health_data, headers = http_get("/health")
    print(f"[1] GET /health: HTTP {status}")
    print(f"    Body: {json.dumps(health_data)}")
    assert status == 200, f"Health check failed: {status}"
    results["health"] = {
        "status_code": status,
        "body": health_data,
        "request_id": headers.get("x-request-id"),
    }

    # 2. Ready Probe
    status, ready_data, headers = http_get("/ready")
    print(f"[2] GET /ready: HTTP {status}")
    print(f"    Body: {json.dumps(ready_data)}")
    assert status == 200, f"Ready check failed: {status}"
    assert ready_data["status"] == "ready", "Status not ready"
    assert ready_data["qloo_configured"] is True, "qloo_configured is not True"
    assert ready_data["storage_ready"] is True, "storage_ready is not True"
    results["ready"] = {
        "status_code": status,
        "body": ready_data,
        "request_id": headers.get("x-request-id"),
    }

    # 3. Create Session
    intent_payload = {
        "raw_intent": "Launch a Tokyo listening bar with vinyl jazz and seasonal highballs in Shibuya."
    }
    status, session_data, headers = http_post("/api/v1/sessions", intent_payload)
    print(f"\n[3] POST /api/v1/sessions: HTTP {status}")
    assert status == 201, f"Session creation failed: {status}"
    session_id = session_data["session_id"]
    assert session_data["current_state"] == "CREATED"
    print(f"    Session ID: {session_id}")
    print(f"    Initial State: {session_data['current_state']}")
    results["create_session"] = {
        "session_id": session_id,
        "status_code": status,
        "state": session_data["current_state"],
        "request_id": headers.get("x-request-id"),
    }

    # 4. Run Cultural Intelligence Pipeline (Qloo + Agents)
    print(
        f"\n[4] POST /api/v1/sessions/{session_id}/pipeline (driving Qloo + Agent mesh)..."
    )
    t0 = time.time()
    status, pipe_data, headers = http_post(
        f"/api/v1/sessions/{session_id}/pipeline",
        {"enrichment_depth": "comprehensive"},
    )
    t_pipe = time.time() - t0
    print(f"    HTTP {status} in {t_pipe:.2f}s")
    assert status == 200, f"Pipeline execution failed: {status} - {pipe_data}"
    print(f"    Post-Pipeline State: {pipe_data['current_state']}")
    assert pipe_data["current_state"] == "AWAITING_APPROVAL", (
        f"Expected AWAITING_APPROVAL, got {pipe_data['current_state']}"
    )
    plan = pipe_data.get("plan")
    assert plan is not None, "Missing plan"
    plan_id = plan.get("plan_id")
    plan_version = plan.get("version")
    cultural_twin = plan.get("cultural_twin") or {}
    print(f"    Plan ID: {plan_id} (v{plan_version})")
    print(f"    Audience: {cultural_twin.get('audience_profile', '')[:80]}...")
    results["pipeline"] = {
        "status_code": status,
        "duration_s": round(t_pipe, 2),
        "state": pipe_data["current_state"],
        "plan_id": plan_id,
        "plan_version": plan_version,
        "request_id": headers.get("x-request-id"),
    }

    # 5. CRITICAL TEST: CASE A — Execute without approval (MUST BE REJECTED)
    print("\n[5] CRITICAL TEST: CASE A — Execute without approval")
    status, unapproved_data, headers = http_post(
        f"/api/v1/sessions/{session_id}/execute",
        None,
    )
    print(f"    HTTP {status}")
    print(f"    Body: {json.dumps(unapproved_data)}")
    assert status in (400, 403, 409), f"Unapproved execution should fail: {status}"
    # Verify session state is still AWAITING_APPROVAL
    _status_chk, chk_data, _ = http_get(f"/api/v1/sessions/{session_id}")
    assert chk_data["current_state"] == "AWAITING_APPROVAL", (
        "State mutated during unapproved execution!"
    )
    print(
        f"    Verified session state remains: {chk_data['current_state']} (truthful gate maintained)"
    )
    results["case_a_unapproved_rejection"] = {
        "status_code": status,
        "error_response": unapproved_data,
        "state_preserved": chk_data["current_state"],
        "request_id": headers.get("x-request-id"),
    }

    # 6. Approve Plan (Governance Gate)
    print(
        f"\n[6] POST /api/v1/sessions/{session_id}/approve (Curator Approval Gate)..."
    )
    status, approve_data, headers = http_post(
        f"/api/v1/sessions/{session_id}/approve",
        {
            "curator_id": "curator_live_prod_test",
            "notes": "Approved for live production verification test.",
        },
    )
    print(f"    HTTP {status}")
    assert status == 200, f"Approval failed: {status} - {approve_data}"
    print(f"    Post-Approval State: {approve_data['current_state']}")
    assert approve_data["current_state"] == "APPROVED"
    approval = approve_data.get("approval") or {}
    plan_hash = approval.get("plan_hash")
    print(f"    Cryptographic Plan Hash (SHA-256): {plan_hash}")
    assert plan_hash is not None and len(plan_hash) == 64, (
        "Plan hash missing or invalid SHA-256"
    )
    results["approval"] = {
        "status_code": status,
        "state": approve_data["current_state"],
        "plan_hash": plan_hash,
        "approver": approval.get("approver"),
        "request_id": headers.get("x-request-id"),
    }

    # 7. CRITICAL TEST: CASE B — Approved Execution with Truthful Connector Reporting
    print("\n[7] CRITICAL TEST: CASE B — Approved Execution")
    t0 = time.time()
    status, exec_data, headers = http_post(
        f"/api/v1/sessions/{session_id}/execute",
        None,
    )
    t_exec = time.time() - t0
    print(f"    HTTP {status} in {t_exec:.2f}s")
    assert status == 200, f"Execution failed: {status} - {exec_data}"
    print(f"    Execution Final State: {exec_data['current_state']}")
    tasks = exec_data.get("execution_tasks") or []
    print(f"    Dispatched Tasks ({len(tasks)}):")
    for task in tasks:
        print(
            f"      - [{task.get('category')}] Action: {task.get('action')}, Status: {task.get('status')}"
        )
        result_obj = task.get("result") or {}
        print(
            f"        Connector: {result_obj.get('connector')}, Config Status: {result_obj.get('configuration_status')}"
        )
        # Invariant: Connectors without live third-party credentials (e.g. Spotify, SendGrid, POS, Procurement)
        # MUST report STAGED, NOT_CONFIGURED, or MOCK, NEVER fake COMPLETED!
        assert task.get("status") in (
            "STAGED",
            "NOT_CONFIGURED",
            "MOCK",
            "SIMULATED",
            "SKIPPED",
            "COMPLETED",
        ), f"Unexpected status: {task.get('status')}"
        if result_obj.get("configuration_status") == "NOT_CONFIGURED":
            assert task.get("status") == "STAGED", (
                f"Truthfulness violation: unconfigured connector has status {task.get('status')}"
            )
    results["case_b_execution"] = {
        "status_code": status,
        "duration_s": round(t_exec, 2),
        "state": exec_data["current_state"],
        "tasks": tasks,
        "request_id": headers.get("x-request-id"),
    }

    # 8. CRITICAL TEST: CASE C — Duplicate Execution (Idempotency Invariant)
    print("\n[8] CRITICAL TEST: CASE C — Duplicate Execution Idempotency")
    time.sleep(2.0)
    status, exec_dup_data, headers = http_post(
        f"/api/v1/sessions/{session_id}/execute",
        None,
    )
    print(f"    HTTP {status}")
    assert status == 200, f"Duplicate execution failed: {status}"
    assert exec_dup_data["current_state"] == exec_data["current_state"], (
        "Duplicate execution altered state!"
    )
    dup_tasks = exec_dup_data.get("execution_tasks") or []
    assert len(dup_tasks) == len(tasks), (
        f"Duplicate execution created extra tasks: {len(dup_tasks)} vs {len(tasks)}"
    )
    print(
        f"    Verified: Idempotent return, state preserved ({exec_dup_data['current_state']}), no duplicate tasks created."
    )
    results["case_c_idempotency"] = {
        "status_code": status,
        "state": exec_dup_data["current_state"],
        "task_count": len(dup_tasks),
        "idempotent": True,
        "request_id": headers.get("x-request-id"),
    }

    # 9. Audit Ledger Verification
    print(f"\n[9] GET /api/v1/sessions/{session_id}/audit (Audit Ledger Inspection)...")
    status, audit_events, headers = http_get(f"/api/v1/sessions/{session_id}/audit")
    print(f"    HTTP {status}")
    assert status == 200, f"Audit retrieval failed: {status}"
    print(f"    Audit Event Count: {len(audit_events)}")
    transitions = [
        f"{e.get('from_state')} -> {e.get('to_state')}" for e in audit_events
    ]
    print(f"    Transitions: {' | '.join(transitions)}")
    assert len(audit_events) >= 3, "Audit ledger missing required transition events"
    results["audit"] = {
        "status_code": status,
        "event_count": len(audit_events),
        "transitions": transitions,
        "request_id": headers.get("x-request-id"),
    }

    # 10. Secrets Leak Check
    print("\n[10] CRITICAL TEST: Verifying Zero Secrets in Responses...")
    all_text = json.dumps([results, exec_data, audit_events])
    for forbidden in [
        "raw_api_key",
        "sk-live-",
        "sk-proj-",
        "qloo_secret",
        "BEGIN RSA PRIVATE KEY",
    ]:
        assert forbidden not in all_text, f"Potential secret leak detected: {forbidden}"
    print("    PASS: Zero secrets detected in responses.")

    print("\n=== ALL PRODUCTION VERIFICATION TESTS PASSED SUCCESSFULLY ===")
    with open("production_smoke_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote results to production_smoke_test_results.json")
    return results


if __name__ == "__main__":
    try:
        run_smoke_test()
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
