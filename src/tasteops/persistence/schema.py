"""TasteOps Relational Database Schema DDL.

Defines normalized relational tables, explicit primary keys, foreign keys,
and indexes for spaces, workflow sessions, cultural intelligence artifacts,
governance records, execution tasks, and audit logs.
"""

SCHEMA_DDL = """
-- 1. Physical Spaces
CREATE TABLE IF NOT EXISTS spaces (
    space_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    business_type TEXT NOT NULL,
    location_json TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spaces_created_at ON spaces(created_at DESC);

-- 2. Space Briefs
CREATE TABLE IF NOT EXISTS space_briefs (
    brief_id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL UNIQUE REFERENCES spaces(space_id) ON DELETE CASCADE,
    target_audience TEXT,
    positioning TEXT,
    desired_mood TEXT,
    budget TEXT,
    constraints_json TEXT NOT NULL DEFAULT '[]',
    anchor_entities_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_briefs_space_id ON space_briefs(space_id);

-- 3. Workflow Sessions
CREATE TABLE IF NOT EXISTS workflow_sessions (
    session_id TEXT PRIMARY KEY,
    space_id TEXT REFERENCES spaces(space_id) ON DELETE SET NULL,
    user_input TEXT NOT NULL,
    current_state TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
    parsed_intent_json TEXT NOT NULL DEFAULT '{}',
    validation_result_json TEXT NOT NULL DEFAULT '{}',
    validation_cycle_count INTEGER NOT NULL DEFAULT 0,
    qloo_retry_count INTEGER NOT NULL DEFAULT 0,
    agent_retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_space_id ON workflow_sessions(space_id);
CREATE INDEX IF NOT EXISTS idx_sessions_current_state ON workflow_sessions(current_state);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON workflow_sessions(created_at DESC);

-- 4. Session State Transitions History
CREATE TABLE IF NOT EXISTS session_state_transitions (
    transition_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transitions_session ON session_state_transitions(session_id, timestamp ASC);

-- 5. Cultural Twins
CREATE TABLE IF NOT EXISTS cultural_twins (
    twin_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    audience_profile TEXT NOT NULL,
    spatial_archetype TEXT NOT NULL,
    vibe_keywords_json TEXT NOT NULL DEFAULT '[]',
    core_values_json TEXT NOT NULL DEFAULT '[]',
    aesthetic_anchors_json TEXT NOT NULL DEFAULT '[]',
    subcultures_json TEXT NOT NULL DEFAULT '[]',
    cross_domain_correlations_json TEXT NOT NULL DEFAULT '[]',
    provenance_entities_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_twins_session_id ON cultural_twins(session_id);

-- 6. Cultural Matrices
CREATE TABLE IF NOT EXISTS cultural_matrices (
    matrix_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    total_entities INTEGER NOT NULL DEFAULT 0,
    domains_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_matrices_session_id ON cultural_matrices(session_id);

-- 7. Cultural Evidence & Provenance
CREATE TABLE IF NOT EXISTS cultural_evidence (
    evidence_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    matrix_id TEXT REFERENCES cultural_matrices(matrix_id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    affinity_score REAL NOT NULL DEFAULT 0.0,
    confidence REAL NOT NULL DEFAULT 1.0,
    sample_size INTEGER DEFAULT 0,
    query_params_json TEXT NOT NULL DEFAULT '{}',
    source_endpoint TEXT NOT NULL,
    verification_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_session_id ON cultural_evidence(session_id);
CREATE INDEX IF NOT EXISTS idx_evidence_entity_id ON cultural_evidence(entity_id);

-- 8. Agent Runs
CREATE TABLE IF NOT EXISTS agent_runs (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    input_hash TEXT,
    output_summary_json TEXT NOT NULL DEFAULT '{}',
    latency_ms REAL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'COMPLETED',
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_session ON agent_runs(session_id, created_at ASC);

-- 9. Experience Blueprints
CREATE TABLE IF NOT EXISTS experience_blueprints (
    blueprint_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    experience_narrative TEXT,
    spatial_zones_json TEXT NOT NULL DEFAULT '[]',
    sonic_identity_json TEXT NOT NULL DEFAULT '{}',
    lighting_design_json TEXT NOT NULL DEFAULT '{}',
    reading_library_json TEXT NOT NULL DEFAULT '{}',
    brand_ecosystem_json TEXT NOT NULL DEFAULT '{}',
    programming_calendar_json TEXT NOT NULL DEFAULT '[]',
    provenance_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blueprints_session_id ON experience_blueprints(session_id);

-- 10. Execution Plans (Versioning)
CREATE TABLE IF NOT EXISTS execution_plans (
    plan_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    plan_hash TEXT NOT NULL,
    estimated_cost TEXT,
    actions_count INTEGER NOT NULL DEFAULT 0,
    actions_json TEXT NOT NULL DEFAULT '[]',
    risks_json TEXT NOT NULL DEFAULT '[]',
    approvals_required_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exec_plans_session ON execution_plans(session_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_exec_plans_hash ON execution_plans(plan_hash);

-- 11. Execution Tasks
CREATE TABLE IF NOT EXISTS execution_tasks (
    task_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    plan_id TEXT REFERENCES execution_plans(plan_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    action TEXT NOT NULL,
    owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    idempotency_key TEXT NOT NULL,
    output_reference TEXT,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    executed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_tasks_session ON execution_tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_exec_tasks_idempotency ON execution_tasks(idempotency_key);

-- 12. Approvals
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES execution_plans(plan_id) ON DELETE CASCADE,
    plan_version INTEGER NOT NULL DEFAULT 1,
    plan_hash TEXT NOT NULL,
    approver TEXT NOT NULL,
    role TEXT,
    status TEXT NOT NULL DEFAULT 'APPROVED',
    notes TEXT,
    is_valid INTEGER NOT NULL DEFAULT 1,
    approved_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approvals_session ON approvals(session_id);
CREATE INDEX IF NOT EXISTS idx_approvals_plan_hash ON approvals(plan_hash);

-- 13. Audit Events Ledger
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES workflow_sessions(session_id) ON DELETE CASCADE,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_events_session ON audit_events(session_id, timestamp ASC);
"""
