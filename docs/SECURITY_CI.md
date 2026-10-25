# TasteOps Security CI & Pipeline Policy

## 1. Overview
The TasteOps Security CI pipeline continuously audits code, dependencies, secrets, and container artifacts to prevent security regressions, unauthorized side-effects, credential leaks, and vulnerabilities.

This document describes the automated checks, severity classifications, gating rules, and vulnerability remediation procedures.

---

## 2. Automated Security Workflows

| Check | Tool | Scope | Trigger | Gating Policy |
| :--- | :--- | :--- | :--- | :--- |
| **Dependency Vulnerability** | `pip-audit` | Python packages in `uv.lock` | Push, PR, Nightly | High / Critical: `BLOCKING` |
| **Static Security Analysis** | `bandit` | Source code in `src/` | Push, PR, Nightly | High / Medium: `BLOCKING` |
| **Secret Scan Guard** | Custom regex / grep | Entire repository | Push, PR | Any detected secret: `BLOCKING` |
| **Container Hardening** | Custom Docker audit | `Dockerfile` | Push, PR | Non-root & Healthcheck: `BLOCKING` |
| **Path Traversal / SSRF** | Pytest Security Suite | API routers & connectors | Push, PR | Any failure: `BLOCKING` |

---

## 3. Severity Classification & Gating Matrix

### CRITICAL (Blocking)
- Remote Code Execution (RCE) or SQL Injection.
- Unauthenticated bypass of the Human-in-the-Loop Approval Gate.
- Direct object reference allowing cross-tenant or cross-session task execution (IDOR).
- Committed live API keys, tokens, or private secrets in version control.
- **Action**: Deployment and PR merging are strictly blocked until a hotfix is verified.

### HIGH (Blocking)
- SSRF in external connector endpoints (e.g., reaching cloud metadata `169.254.169.254` or private RFC-1918 subnets).
- Secret leakage in error responses or logs.
- Execution of unapproved or stale plan versions.
- Container running as root (`UID 0`).
- **Action**: Must be remediated prior to milestone release.

### MEDIUM (Non-Blocking for PR, Blocking for Release)
- Overly permissive CORS wildcard headers in production mode.
- Incomplete input validation on optional fields.
- Missing rate limits on public endpoints.
- **Action**: Remediated within release sprint cycle.

### LOW / INFO (Informational)
- Minor configuration discrepancies.
- Deprecated dependency warnings without known CVEs.
- **Action**: Tracked in backlog for routine dependency maintenance.

---

## 4. Remediation Process
1. **Identify Finding**: Review the Security CI workflow run logs in GitHub Actions.
2. **Reproduce Locally**:
   ```bash
   bandit -r src/ -ll -x tests/
   pip-audit
   uv run pytest tests/integration/test_security_deep_coverage.py -v
   ```
3. **Patch Vulnerability**: Follow least-privilege principles, input validation, and parameter binding.
4. **Verify Tests**: Ensure both positive tests and negative failure-injection tests pass.
5. **Commit & Push**: Use Conventional Commits (`fix(security): ...`) and confirm pipeline passes.
