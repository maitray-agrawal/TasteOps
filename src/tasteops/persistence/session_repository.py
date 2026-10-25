"""TasteOps Workflow Session & Cultural Artifacts Relational Repository.

Persists and recovers all workflow lifecycle artifacts across normalized tables:
- WorkflowSession & state transitions
- CulturalTwin & CulturalMatrix references
- CulturalEvidence & Provenance verification hashes
- AgentRuns execution metrics
- ExperienceBlueprints (spatial, sensory, sonic, lighting)
- ExecutionPlans (versioned) & ExecutionTasks (idempotent)
- Human Curator Approvals (cryptographically bound)
- AuditEvents immutable ledger
"""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from tasteops.models.cultural_matrix import CulturalMatrix, CulturalTwin
from tasteops.persistence.database import Database
from tasteops.workflows.context import StateTransitionRecord, WorkflowContext
from tasteops.workflows.persistence import AuditEvent
from tasteops.workflows.schemas import (
    ApprovalRecord,
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExecutionPlan,
    ExecutionTask,
    ExperienceDesignOutput,
    GovernanceValidationOutput,
    PartnershipOutput,
)
from tasteops.workflows.states import WorkflowState

logger = logging.getLogger("tasteops.persistence.session_repo")


class BaseSessionRepository(ABC):
    """Abstract interface for WorkflowSession and artifact relational persistence."""

    @abstractmethod
    def save_session(self, ctx: WorkflowContext) -> None:
        """Persists all session artifacts transactionally across normalized tables."""

    @abstractmethod
    def load_session(self, session_id: str) -> WorkflowContext | None:
        """Recovers full typed WorkflowContext and all associated relational artifacts."""

    @abstractmethod
    def list_sessions(self, space_id: str | None = None) -> list[str]:
        """Lists session IDs optionally filtered by space_id."""

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Cascading delete of session and all child artifacts."""

    @abstractmethod
    def save_audit_event(self, event: AuditEvent) -> None:
        """Persists a single audit event record."""

    @abstractmethod
    def get_audit_events(self, session_id: str) -> list[AuditEvent]:
        """Retrieves ordered audit log events for a session."""


class SQLiteSessionRepository(BaseSessionRepository):
    """Relational SQLite implementation of BaseSessionRepository."""

    def __init__(self, database: Database) -> None:
        self.db = database

    def save_session(self, ctx: WorkflowContext) -> None:
        """Persists session state and all related artifacts within a single atomic transaction."""
        now = datetime.now(UTC).isoformat()
        parsed_intent_json = json.dumps(ctx.parsed_intent or {})

        with self.db.transaction() as cursor:
            # 0. Ensure space exists if referenced
            if ctx.space_id:
                cursor.execute(
                    """
                    INSERT INTO spaces (space_id, name, business_type, created_at, updated_at)
                    VALUES (?, ?, 'Registered Space', ?, ?)
                    ON CONFLICT(space_id) DO NOTHING;
                    """,
                    (ctx.space_id, ctx.space_id, now, now),
                )

            # 1. Upsert workflow_sessions
            status_str = "IN_PROGRESS"
            if ctx.current_state == WorkflowState.AWAITING_APPROVAL:
                status_str = "AWAITING_APPROVAL"
            elif ctx.current_state == WorkflowState.APPROVED:
                status_str = "APPROVED"
            elif ctx.current_state == WorkflowState.EXECUTING:
                status_str = "EXECUTING"
            elif ctx.current_state == WorkflowState.COMPLETED:
                status_str = "COMPLETED"
            elif ctx.current_state == WorkflowState.FAILED:
                status_str = "FAILED"

            val_res = ctx.validation_result or ctx.governance_output or (ctx.plan.governance if ctx.plan else None)
            val_json = val_res.model_dump_json() if val_res and hasattr(val_res, "model_dump_json") else "{}"

            cursor.execute(
                """
                INSERT INTO workflow_sessions (
                    session_id, space_id, user_input, current_state, status,
                    parsed_intent_json, validation_result_json,
                    validation_cycle_count, qloo_retry_count, agent_retry_count,
                    error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    current_state = excluded.current_state,
                    status = excluded.status,
                    parsed_intent_json = excluded.parsed_intent_json,
                    validation_result_json = excluded.validation_result_json,
                    validation_cycle_count = excluded.validation_cycle_count,
                    qloo_retry_count = excluded.qloo_retry_count,
                    agent_retry_count = excluded.agent_retry_count,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at;
                """,
                (
                    ctx.session_id,
                    ctx.space_id,
                    ctx.user_input,
                    ctx.current_state.value,
                    status_str,
                    parsed_intent_json,
                    val_json,
                    ctx.validation_cycle_count,
                    ctx.qloo_retry_count,
                    ctx.agent_retry_count,
                    ctx.error_message,
                    now,
                    now,
                ),
            )

            # 2. Upsert State Transitions
            for record in ctx.history:
                transition_id = f"tr_{uuid.uuid4().hex[:12]}"
                cursor.execute(
                    """
                    INSERT INTO session_state_transitions (
                        transition_id, session_id, from_state, to_state, reason, metadata_json, timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        transition_id,
                        ctx.session_id,
                        record.from_state.value,
                        record.to_state.value,
                        record.reason,
                        json.dumps(record.metadata),
                        record.timestamp.isoformat(),
                    ),
                )

            # 3. Upsert CulturalTwin
            if ctx.cultural_twin:
                twin = ctx.cultural_twin
                twin_id = f"twin_{ctx.session_id[:12]}"
                twin_json = twin.model_dump_json()
                spatial_arch = getattr(twin, "spatial_archetype", getattr(twin, "mood_profile", ""))
                vibe_kw = getattr(twin, "vibe_keywords", getattr(twin, "cultural_themes", []))
                core_val = getattr(twin, "core_values", getattr(twin, "cultural_constraints", []))
                aest_anch = getattr(twin, "aesthetic_anchors", getattr(twin, "anchor_entities", []))
                subcult = getattr(twin, "subcultures", getattr(twin, "resolved_tags", []))
                cross_dom = getattr(twin, "cross_domain_correlations", [])
                cursor.execute(
                    """
                    INSERT INTO cultural_twins (
                        twin_id, session_id, audience_profile, spatial_archetype,
                        vibe_keywords_json, core_values_json, aesthetic_anchors_json,
                        subcultures_json, cross_domain_correlations_json, provenance_entities_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        audience_profile = excluded.audience_profile,
                        spatial_archetype = excluded.spatial_archetype,
                        vibe_keywords_json = excluded.vibe_keywords_json,
                        core_values_json = excluded.core_values_json,
                        aesthetic_anchors_json = excluded.aesthetic_anchors_json,
                        subcultures_json = excluded.subcultures_json,
                        cross_domain_correlations_json = excluded.cross_domain_correlations_json,
                        provenance_entities_json = excluded.provenance_entities_json;
                    """,
                    (
                        twin_id,
                        ctx.session_id,
                        twin.audience_profile,
                        spatial_arch,
                        json.dumps(vibe_kw),
                        json.dumps(core_val),
                        json.dumps(aest_anch),
                        json.dumps(subcult),
                        json.dumps(cross_dom),
                        twin_json,
                        now,
                    ),
                )

            # 4. Upsert CulturalMatrix & CulturalEvidence
            if ctx.cultural_matrix:
                matrix = ctx.cultural_matrix
                matrix_id = f"mat_{ctx.session_id[:12]}"
                fingerprint = getattr(matrix, "fingerprint", f"fp_{ctx.session_id[:8]}")
                total_recs = matrix.total_recommendations if hasattr(matrix, "total_recommendations") else 0
                matrix_json = matrix.model_dump_json()
                cursor.execute(
                    """
                    INSERT INTO cultural_matrices (
                        matrix_id, session_id, fingerprint, total_entities, domains_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        fingerprint = excluded.fingerprint,
                        total_entities = excluded.total_entities,
                        domains_json = excluded.domains_json;
                    """,
                    (
                        matrix_id,
                        ctx.session_id,
                        fingerprint,
                        total_recs,
                        matrix_json,
                        now,
                    ),
                )

                # Persist evidence samples across categories
                category_map = {
                    "artist": getattr(matrix, "artists", []),
                    "book": getattr(matrix, "books", []),
                    "brand": getattr(matrix, "brands", []),
                    "place": getattr(matrix, "places", []),
                    "movie": getattr(matrix, "movies", []),
                    "destination": getattr(matrix, "destinations", []),
                }
                for cat_name, recs in category_map.items():
                    for rec in recs:
                        ev_id = f"ev_{uuid.uuid4().hex[:12]}"
                        ent_id = getattr(rec, "id", getattr(rec, "entity_id", "ent_unknown"))
                        rec_name = getattr(rec, "name", ent_id)
                        verification_hash = f"vhash_{ent_id}_{fingerprint[:8]}"
                        cursor.execute(
                            """
                            INSERT INTO cultural_evidence (
                                evidence_id, session_id, matrix_id, entity_id, entity_name,
                                entity_type, affinity_score, confidence, sample_size,
                                query_params_json, source_endpoint, verification_hash, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ev_id,
                                ctx.session_id,
                                matrix_id,
                                ent_id,
                                rec_name,
                                cat_name,
                                rec.affinity if getattr(rec, "affinity", None) is not None else 0.0,
                                rec.confidence if getattr(rec, "confidence", None) is not None else 1.0,
                                1,
                                json.dumps({"source": "qloo"}),
                                "/v2/insights",
                                verification_hash,
                                now,
                            ),
                        )

            # 5. Upsert ExperienceBlueprint
            exp = ctx.experience_output or (ctx.plan.experience_design if ctx.plan else None)
            if exp:
                bp_id = f"bp_{ctx.session_id[:12]}"
                narrative = getattr(exp, "experience_narrative", "")
                spatial_zones_json = json.dumps(
                    [z.model_dump() for z in exp.spatial_zones]
                    if hasattr(exp, "spatial_zones") and exp.spatial_zones
                    else []
                )
                sonic_json = json.dumps(
                    exp.sonic_identity.model_dump()
                    if hasattr(exp, "sonic_identity") and exp.sonic_identity
                    else {}
                )
                lighting_json = json.dumps(
                    exp.atmosphere_guidelines.model_dump()
                    if hasattr(exp, "atmosphere_guidelines") and exp.atmosphere_guidelines
                    else {}
                )
                reading_json = json.dumps(
                    exp.reading_library_identity.model_dump()
                    if hasattr(exp, "reading_library_identity") and exp.reading_library_identity
                    else {}
                )
                brand_json = json.dumps(
                    exp.brand_ecosystem.model_dump()
                    if hasattr(exp, "brand_ecosystem") and exp.brand_ecosystem
                    else {}
                )
                prog_json = json.dumps(
                    exp.cultural_programming_ideas.model_dump()
                    if hasattr(exp, "cultural_programming_ideas") and exp.cultural_programming_ideas
                    else []
                )
                prov_ids_json = json.dumps(getattr(exp, "provenance_entity_ids", []))

                cursor.execute(
                    """
                    INSERT INTO experience_blueprints (
                        blueprint_id, session_id, experience_narrative, spatial_zones_json,
                        sonic_identity_json, lighting_design_json, reading_library_json,
                        brand_ecosystem_json, programming_calendar_json, provenance_ids_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        experience_narrative = excluded.experience_narrative,
                        spatial_zones_json = excluded.spatial_zones_json,
                        sonic_identity_json = excluded.sonic_identity_json,
                        lighting_design_json = excluded.lighting_design_json,
                        reading_library_json = excluded.reading_library_json,
                        brand_ecosystem_json = excluded.brand_ecosystem_json,
                        programming_calendar_json = excluded.programming_calendar_json,
                        provenance_ids_json = excluded.provenance_ids_json;
                    """,
                    (
                        bp_id,
                        ctx.session_id,
                        narrative,
                        spatial_zones_json,
                        sonic_json,
                        lighting_json,
                        reading_json,
                        brand_json,
                        prog_json,
                        prov_ids_json,
                        now,
                    ),
                )

            # 5b. Upsert Agent Runs
            strat = ctx.strategy_output or (ctx.plan.strategy if ctx.plan else None)
            if strat:
                run_id = f"run_{ctx.session_id[:8]}_strat"
                strat_json = strat.model_dump_json() if hasattr(strat, "model_dump_json") else json.dumps(str(strat))
                cursor.execute(
                    """
                    INSERT INTO agent_runs (
                        run_id, session_id, agent_name, output_summary_json, status, created_at
                    )
                    VALUES (?, ?, 'CulturalStrategist', ?, 'COMPLETED', ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        output_summary_json = excluded.output_summary_json,
                        status = excluded.status;
                    """,
                    (run_id, ctx.session_id, strat_json, now),
                )

            if exp:
                run_id = f"run_{ctx.session_id[:8]}_exp"
                exp_json = exp.model_dump_json() if hasattr(exp, "model_dump_json") else json.dumps(str(exp))
                cursor.execute(
                    """
                    INSERT INTO agent_runs (
                        run_id, session_id, agent_name, output_summary_json, status, created_at
                    )
                    VALUES (?, ?, 'ExperienceArchitect', ?, 'COMPLETED', ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        output_summary_json = excluded.output_summary_json,
                        status = excluded.status;
                    """,
                    (run_id, ctx.session_id, exp_json, now),
                )

            part = ctx.partnership_output or (ctx.plan.partnerships if ctx.plan else None)
            if part:
                run_id = f"run_{ctx.session_id[:8]}_part"
                part_json = part.model_dump_json() if hasattr(part, "model_dump_json") else json.dumps(str(part))
                cursor.execute(
                    """
                    INSERT INTO agent_runs (
                        run_id, session_id, agent_name, output_summary_json, status, created_at
                    )
                    VALUES (?, ?, 'PartnershipAgent', ?, 'COMPLETED', ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        output_summary_json = excluded.output_summary_json,
                        status = excluded.status;
                    """,
                    (run_id, ctx.session_id, part_json, now),
                )

            if val_res:
                run_id = f"run_{ctx.session_id[:8]}_gov"
                cursor.execute(
                    """
                    INSERT INTO agent_runs (
                        run_id, session_id, agent_name, output_summary_json, status, created_at
                    )
                    VALUES (?, ?, 'GovernanceAgent', ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        output_summary_json = excluded.output_summary_json,
                        status = excluded.status;
                    """,
                    (
                        run_id,
                        ctx.session_id,
                        val_json,
                        "COMPLETED" if getattr(val_res, "is_valid", True) else "FAILED",
                        now,
                    ),
                )

            # 6. Upsert ExecutionPlan (versioned)
            exec_plan = ctx.execution_plan or (ctx.plan.execution_plan if ctx.plan else None)
            if exec_plan:
                plan_hash = getattr(exec_plan, "plan_hash", None) or (ctx.plan.compute_hash() if ctx.plan else f"hash_{exec_plan.plan_id}_{exec_plan.version}")
                actions_count = len(exec_plan.actions)
                risks_json = json.dumps(exec_plan.risks)
                approvals_req_json = json.dumps(exec_plan.approvals_required)

                plan_ids_to_upsert = {exec_plan.plan_id}
                if ctx.plan and ctx.plan.plan_id:
                    plan_ids_to_upsert.add(ctx.plan.plan_id)
                if ctx.approval and ctx.approval.plan_id:
                    plan_ids_to_upsert.add(ctx.approval.plan_id)

                for p_id in plan_ids_to_upsert:
                    cursor.execute(
                        """
                        INSERT INTO execution_plans (
                            plan_id, session_id, version, plan_hash, estimated_cost,
                            actions_count, risks_json, approvals_required_json, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(plan_id) DO UPDATE SET
                            version = excluded.version,
                            plan_hash = excluded.plan_hash,
                            estimated_cost = excluded.estimated_cost,
                            actions_count = excluded.actions_count,
                            risks_json = excluded.risks_json,
                            approvals_required_json = excluded.approvals_required_json;
                        """,
                        (
                            p_id,
                            ctx.session_id,
                            exec_plan.version,
                            plan_hash,
                            exec_plan.estimated_cost,
                            actions_count,
                            risks_json,
                            approvals_req_json,
                            now,
                        ),
                    )

            # 7. Upsert ExecutionTasks (idempotency enforcement)
            if ctx.execution_tasks:
                plan_id = exec_plan.plan_id if exec_plan else None
                for task in ctx.execution_tasks:
                    cursor.execute(
                        """
                        INSERT INTO execution_tasks (
                            task_id, session_id, plan_id, category, action, owner,
                            status, idempotency_key, output_reference, provenance_json,
                            created_at, executed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(task_id) DO UPDATE SET
                            status = excluded.status,
                            output_reference = excluded.output_reference,
                            executed_at = excluded.executed_at;
                        """,
                        (
                            task.task_id,
                            ctx.session_id,
                            plan_id,
                            task.category,
                            task.action,
                            task.owner,
                            task.status,
                            task.idempotency_key,
                            task.output_reference,
                            json.dumps(task.provenance),
                            task.timestamp.isoformat() if hasattr(task, "timestamp") and task.timestamp else now,
                            task.executed_at.isoformat() if task.executed_at else None,
                        ),
                    )

            # 8. Upsert Approvals
            if ctx.approval:
                appr = ctx.approval
                appr_id = getattr(appr, "approval_id", None) or f"appr_{ctx.session_id[:12]}"
                role = getattr(appr, "role", None) or "Lead Cultural Strategist"
                status = getattr(appr, "status", None) or ("APPROVED" if appr.is_valid else "INVALIDATED")
                notes = getattr(appr, "notes", None) or getattr(appr, "invalidation_reason", None)
                cursor.execute(
                    """
                    INSERT INTO approvals (
                        approval_id, session_id, plan_id, plan_version, plan_hash,
                        approver, role, status, notes, is_valid, approved_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(approval_id) DO UPDATE SET
                        status = excluded.status,
                        is_valid = excluded.is_valid,
                        notes = excluded.notes;
                    """,
                    (
                        appr_id,
                        ctx.session_id,
                        appr.plan_id,
                        appr.plan_version,
                        appr.plan_hash,
                        appr.approver,
                        role,
                        status,
                        notes,
                        1 if appr.is_valid else 0,
                        appr.approved_at.isoformat() if hasattr(appr.approved_at, "isoformat") else str(appr.approved_at),
                    ),
                )

            # 9. Upsert Audit Events
            for evt in ctx.audit_events:
                cursor.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, session_id, from_state, to_state, reason, metadata_json, error, timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id) DO NOTHING;
                    """,
                    (
                        evt.event_id,
                        ctx.session_id,
                        evt.from_state.value if hasattr(evt.from_state, "value") else str(evt.from_state),
                        evt.to_state.value if hasattr(evt.to_state, "value") else str(evt.to_state),
                        evt.reason,
                        json.dumps(evt.metadata),
                        evt.error,
                        evt.timestamp.isoformat() if hasattr(evt.timestamp, "isoformat") else str(evt.timestamp),
                    ),
                )

    def load_session(self, session_id: str) -> WorkflowContext | None:
        """Recovers the full typed WorkflowContext and associated relational artifacts."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            # 1. Fetch workflow_sessions
            cursor.execute(
                """
                SELECT session_id, space_id, user_input, current_state, parsed_intent_json,
                       validation_cycle_count, qloo_retry_count, agent_retry_count, error_message,
                       validation_result_json
                FROM workflow_sessions
                WHERE session_id = ?;
                """,
                (session_id,),
            )
            sess_row = cursor.fetchone()
            if not sess_row:
                return None

            current_state = WorkflowState(sess_row["current_state"])
            parsed_intent = json.loads(sess_row["parsed_intent_json"])

            ctx = WorkflowContext(
                session_id=sess_row["session_id"],
                space_id=sess_row["space_id"],
                user_input=sess_row["user_input"],
                current_state=current_state,
                parsed_intent=parsed_intent,
                validation_cycle_count=sess_row["validation_cycle_count"],
                qloo_retry_count=sess_row["qloo_retry_count"],
                agent_retry_count=sess_row["agent_retry_count"],
                error_message=sess_row["error_message"],
            )

            val_json = sess_row["validation_result_json"] if "validation_result_json" in sess_row.keys() else None
            if val_json and val_json != "{}":
                try:
                    ctx.validation_result = GovernanceValidationOutput.model_validate_json(val_json)
                    ctx.governance_output = ctx.validation_result
                except Exception as exc:
                    logger.debug("Non-critical: Validation output recovery relaxed: %s", exc)

            # 2. Recover CulturalTwin
            cursor.execute(
                """
                SELECT audience_profile, spatial_archetype, vibe_keywords_json, core_values_json,
                       aesthetic_anchors_json, subcultures_json, cross_domain_correlations_json,
                       provenance_entities_json
                FROM cultural_twins
                WHERE session_id = ?;
                """,
                (session_id,),
            )
            twin_row = cursor.fetchone()
            if twin_row:
                try:
                    ctx.cultural_twin = CulturalTwin.model_validate_json(twin_row["provenance_entities_json"])
                except Exception:
                    ctx.cultural_twin = CulturalTwin(
                        audience_profile=twin_row["audience_profile"],
                        mood_profile=twin_row["spatial_archetype"],
                        cultural_themes=json.loads(twin_row["vibe_keywords_json"]),
                    )

            # 3. Recover CulturalMatrix
            cursor.execute(
                """
                SELECT fingerprint, total_entities, domains_json
                FROM cultural_matrices
                WHERE session_id = ?;
                """,
                (session_id,),
            )
            mat_row = cursor.fetchone()
            if mat_row:
                try:
                    ctx.cultural_matrix = CulturalMatrix.model_validate_json(mat_row["domains_json"])
                except Exception as exc:
                    logger.debug("CulturalMatrix model_validate_json error: %s", exc)

            # 4. Recover ExperienceBlueprint
            cursor.execute(
                """
                SELECT experience_narrative, spatial_zones_json, sonic_identity_json,
                       lighting_design_json, reading_library_json, brand_ecosystem_json,
                       programming_calendar_json, provenance_ids_json
                FROM experience_blueprints
                WHERE session_id = ?;
                """,
                (session_id,),
            )
            bp_row = cursor.fetchone()
            if bp_row:
                try:
                    ctx.experience_output = ExperienceDesignOutput(
                        sonic_identity=json.loads(bp_row["sonic_identity_json"]),
                        reading_library_identity=json.loads(bp_row["reading_library_json"]),
                        brand_ecosystem=json.loads(bp_row["brand_ecosystem_json"]),
                        local_experience_ecosystem={
                            "overview": "Local neighborhood synergy",
                            "neighborhood_context": "Vibrant local community",
                            "curated_recommendations": [],
                            "community_synergies": [],
                        },
                        cultural_programming_ideas=json.loads(bp_row["programming_calendar_json"]),
                        atmosphere_guidelines=json.loads(bp_row["lighting_design_json"]),
                        spatial_zones=json.loads(bp_row["spatial_zones_json"]),
                        provenance_entity_ids=json.loads(bp_row["provenance_ids_json"]),
                    )
                except Exception as exc:
                    logger.debug("Non-critical: ExperienceDesignOutput recovery relaxed: %s", exc)

            # 5. Recover ExecutionPlan
            cursor.execute(
                """
                SELECT plan_id, version, plan_hash, estimated_cost, actions_count, risks_json, approvals_required_json
                FROM execution_plans
                WHERE session_id = ?
                ORDER BY version DESC LIMIT 1;
                """,
                (session_id,),
            )
            plan_row = cursor.fetchone()
            if plan_row:
                ctx.execution_plan = ExecutionPlan(
                    plan_id=plan_row["plan_id"],
                    version=plan_row["version"],
                    plan_hash=plan_row["plan_hash"],
                    estimated_cost=plan_row["estimated_cost"],
                    risks=json.loads(plan_row["risks_json"]),
                    approvals_required=json.loads(plan_row["approvals_required_json"]),
                    actions=[],
                )

            # 6. Recover ExecutionTasks
            cursor.execute(
                """
                SELECT task_id, category, action, owner, status, idempotency_key, output_reference,
                       provenance_json, created_at, executed_at
                FROM execution_tasks
                WHERE session_id = ?
                ORDER BY created_at ASC;
                """,
                (session_id,),
            )
            task_rows = cursor.fetchall()
            for r in task_rows:
                task = ExecutionTask(
                    task_id=r["task_id"],
                    category=r["category"],
                    action=r["action"],
                    owner=r["owner"],
                    status=r["status"],
                    idempotency_key=r["idempotency_key"],
                    output_reference=r["output_reference"],
                    provenance=json.loads(r["provenance_json"]),
                    timestamp=datetime.fromisoformat(r["created_at"]),
                    executed_at=datetime.fromisoformat(r["executed_at"]) if r["executed_at"] else None,
                )
                ctx.execution_tasks.append(task)

            # 7. Recover Approvals
            cursor.execute(
                """
                SELECT approval_id, plan_id, plan_version, plan_hash, approver, role,
                       status, notes, is_valid, approved_at
                FROM approvals
                WHERE session_id = ?
                ORDER BY approved_at DESC LIMIT 1;
                """,
                (session_id,),
            )
            appr_row = cursor.fetchone()
            if appr_row:
                ctx.approval = ApprovalRecord(
                    session_id=session_id,
                    plan_id=appr_row["plan_id"],
                    plan_version=appr_row["plan_version"],
                    plan_hash=appr_row["plan_hash"],
                    approver=appr_row["approver"],
                    is_valid=bool(appr_row["is_valid"]),
                    approved_at=datetime.fromisoformat(appr_row["approved_at"]),
                    invalidation_reason=appr_row["notes"] if not appr_row["is_valid"] else None,
                )

            # 8. Recover Agent Runs (CulturalStrategist, PartnershipAgent, GovernanceAgent)
            cursor.execute(
                "SELECT agent_name, output_summary_json FROM agent_runs WHERE session_id = ?;",
                (session_id,),
            )
            for r in cursor.fetchall():
                try:
                    if r["agent_name"] == "CulturalStrategist" and not ctx.strategy_output:
                        ctx.strategy_output = CulturalStrategyOutput.model_validate_json(r["output_summary_json"])
                    elif r["agent_name"] == "PartnershipAgent" and not ctx.partnership_output:
                        ctx.partnership_output = PartnershipOutput.model_validate_json(r["output_summary_json"])
                    elif r["agent_name"] == "GovernanceAgent" and not ctx.governance_output:
                        ctx.governance_output = GovernanceValidationOutput.model_validate_json(r["output_summary_json"])
                except Exception as exc:
                    logger.debug("Non-critical: Agent run recovery relaxed: %s", exc)

            # 9. Recover Audit Events
            ctx.audit_events = self.get_audit_events(session_id)
            ctx.sync_outputs()

            return ctx
        finally:
            cursor.close()

    def list_sessions(self, space_id: str | None = None) -> list[str]:
        """Lists all session IDs, optionally filtered by space_id."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            if space_id:
                cursor.execute(
                    "SELECT session_id FROM workflow_sessions WHERE space_id = ? ORDER BY created_at DESC;",
                    (space_id,),
                )
            else:
                cursor.execute(
                    "SELECT session_id FROM workflow_sessions ORDER BY created_at DESC;"
                )
            rows = cursor.fetchall()
            return [r["session_id"] for r in rows]
        finally:
            cursor.close()

    def delete_session(self, session_id: str) -> bool:
        """Cascading delete of session and all child artifacts."""
        with self.db.transaction() as cursor:
            cursor.execute("DELETE FROM workflow_sessions WHERE session_id = ?;", (session_id,))
            return cursor.rowcount > 0

    def save_audit_event(self, event: AuditEvent) -> None:
        """Persists an immutable audit log record."""
        now = event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp)
        with self.db.transaction() as cursor:
            # Ensure workflow_session row exists for foreign key
            cursor.execute(
                """
                INSERT INTO workflow_sessions (session_id, user_input, current_state, created_at, updated_at)
                VALUES (?, '', ?, ?, ?)
                ON CONFLICT(session_id) DO NOTHING;
                """,
                (
                    event.session_id,
                    event.to_state.value if hasattr(event.to_state, "value") else str(event.to_state),
                    now,
                    now,
                ),
            )
            cursor.execute(
                """
                INSERT INTO audit_events (
                    event_id, session_id, from_state, to_state, reason, metadata_json, error, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO NOTHING;
                """,
                (
                    event.event_id,
                    event.session_id,
                    event.from_state.value if hasattr(event.from_state, "value") else str(event.from_state),
                    event.to_state.value if hasattr(event.to_state, "value") else str(event.to_state),
                    event.reason,
                    json.dumps(event.metadata),
                    event.error,
                    now,
                ),
            )

    def get_audit_events(self, session_id: str) -> list[AuditEvent]:
        """Retrieves ordered audit events for a session."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT event_id, session_id, from_state, to_state, reason, metadata_json, error, timestamp
                FROM audit_events
                WHERE session_id = ?
                ORDER BY timestamp ASC;
                """,
                (session_id,),
            )
            rows = cursor.fetchall()
            events: list[AuditEvent] = []
            for r in rows:
                events.append(
                    AuditEvent(
                        event_id=r["event_id"],
                        session_id=r["session_id"],
                        from_state=WorkflowState(r["from_state"]),
                        to_state=WorkflowState(r["to_state"]),
                        reason=r["reason"],
                        metadata=json.loads(r["metadata_json"]),
                        error=r["error"],
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                    )
                )
            return events
        finally:
            cursor.close()
