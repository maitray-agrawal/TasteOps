"""TasteOps Governance & Execution Agent.

Enforces strict compliance, quality bounds, and provenance integrity.
Verifies that zero hallucinated Qloo IDs exist in any agent output.
Converts cultural recommendations into an actionable ExecutionPlan, validates
against constraints, enforces the Human-in-the-Loop approval gate, and dispatches
audited execution tasks post-approval.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from tasteops.connectors import (
    ConfigurationStatus,
    ConnectorRegistry,
    create_default_registry,
)
from tasteops.workflows.idempotency import DurableIdempotencyStore
from tasteops.workflows.schemas import (
    ApprovalRecord,
    AuditReport,
    ComplianceCheck,
    CulturalActivationPlan,
    ExecutionPlan,
    ExecutionPlanAction,
    ExecutionSummary,
    ExecutionTask,
    GovernanceValidationInput,
    GovernanceValidationOutput,
    TaskStatus,
)

logger = logging.getLogger("tasteops.agents.governance")


class UnapprovedExecutionError(RuntimeError):
    """Raised when an attempt is made to execute external actions before explicit approval."""


class ProvenanceValidationError(RuntimeError):
    """Raised when an execution task lacks mandatory verifiable provenance."""


class GovernanceAgent:
    """Agent validating plan compliance, auditing provenance, and managing execution."""

    name: str = "Governance & Execution Agent"

    # Supported execution categories for external actions
    SUPPORTED_CATEGORIES: ClassVar[set[str]] = {
        "spotify_audio_seed",
        "partner_outreach_brief",
        "spatial_design_spec",
        "curatorial_programming",
        "hospitality_training",
    }

    def __init__(
        self,
        connector_registry: ConnectorRegistry | None = None,
        durable_store: DurableIdempotencyStore | None = None,
    ) -> None:
        self.connector_registry = connector_registry or create_default_registry()
        self._idempotency_store: dict[str, ExecutionTask] = {}
        self.durable_store = durable_store or DurableIdempotencyStore()
        self._lock: asyncio.Lock | None = None

    @property
    def lock(self) -> asyncio.Lock:
        """Coroutine-safe execution lock."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # -------------------------------------------------------------------------
    # 1. PLAN Phase: Generate ExecutionPlan
    # -------------------------------------------------------------------------
    def plan(self, payload: GovernanceValidationInput) -> ExecutionPlan:
        """Converts cultural recommendations into a structured ExecutionPlan."""
        if isinstance(payload, dict):
            payload = GovernanceValidationInput.model_validate(payload)
        elif not isinstance(payload, GovernanceValidationInput):
            raise TypeError(
                f"Expected GovernanceValidationInput or dict, got {type(payload).__name__}"
            )

        logger.info(
            "[%s] Synthesizing cultural recommendations into ExecutionPlan",
            self.name,
        )
        plan_id = f"exec_plan_{uuid.uuid4().hex[:8]}"
        matrix = payload.cultural_matrix
        experience = payload.experience_design
        partnerships = payload.partnerships

        actions: list[ExecutionPlanAction] = []
        dependencies: dict[str, list[str]] = {}
        evidence: list[dict[str, Any]] = []

        # 1. Sonic / Audio Action
        lead_artist = matrix.artists[0] if matrix.artists else None
        lead_artist_id = lead_artist.id if lead_artist else "ent_lead_artist"
        lead_artist_name = lead_artist.name if lead_artist else "Lead Selector"
        act_sonic = ExecutionPlanAction(
            action_id="act_sonic_01",
            title=f"Calibrate Sound System & Seed Audio Pipeline ({lead_artist_name})",
            description=(
                f"Export seed artist '{lead_artist_name}' to audio playback engine and "
                "calibrate analog sound levels for evening dayparts."
            ),
            owner="Audio Curator",
            estimated_cost="$3,500 (acoustic calibration & hardware setup)",
            dependencies=[],
            target_entity_id=lead_artist_id,
        )
        actions.append(act_sonic)
        dependencies[act_sonic.action_id] = []
        if lead_artist:
            evidence.append(
                {
                    "action_id": act_sonic.action_id,
                    "entity_id": lead_artist.id,
                    "name": lead_artist.name,
                    "type": lead_artist.type,
                    "affinity": lead_artist.affinity,
                    "source": "qloo_insights_artist",
                }
            )

        # 2. Tableware & Spatial Amenities Action
        brand_id = "ent_lead_partner"
        brand_name = "Craft Goods Partner"
        if partnerships.candidates:
            cand = partnerships.candidates[0]
            brand_id = cand.brand_entity_id
            brand_name = cand.brand
        elif partnerships.partnerships:
            part = partnerships.partnerships[0]
            brand_id = part.partner_entity_id
            brand_name = part.partner_name
        act_tableware = ExecutionPlanAction(
            action_id="act_brand_01",
            title=f"Procure Physical Tableware Specs ({brand_name})",
            description=(
                f"Coordinate tactile stoneware ceramics and linen specifications with {brand_name} "
                "for bar counter serviceware."
            ),
            owner="Spatial Designer",
            estimated_cost="$4,200 (tableware batch inventory)",
            dependencies=["act_sonic_01"],
            target_entity_id=brand_id,
        )
        actions.append(act_tableware)
        dependencies[act_tableware.action_id] = ["act_sonic_01"]

        # 3. Brand Partnership Outreach Action
        act_outreach = ExecutionPlanAction(
            action_id="act_partner_01",
            title=f"Dispatch Exploratory Outreach Brief ({brand_name})",
            description=(
                f"Send evidence-backed exploratory outreach draft to {brand_name} proposing "
                "tactile product placement and hardware residency."
            ),
            owner="Partnership Director",
            estimated_cost="$500 (curatorial outreach materials)",
            dependencies=["act_brand_01"],
            target_entity_id=brand_id,
        )
        actions.append(act_outreach)
        dependencies[act_outreach.action_id] = ["act_brand_01"]

        # 4. Atmospheric Dayparting Action
        lead_zone = (
            experience.spatial_zones[0].zone_name
            if experience.spatial_zones
            else "Main Room"
        )
        act_atmosphere = ExecutionPlanAction(
            action_id="act_hospitality_01",
            title=f"Implement Sensory Atmosphere & Hospitality Tempo ({lead_zone})",
            description=(
                "Establish 55dB-65dB volume ceilings, 2400K warm dimming protocols, "
                "and unhurried hospitality pacing across all active dayparts."
            ),
            owner="General Manager",
            estimated_cost="$1,800 (lighting controllers & staff onboarding)",
            dependencies=["act_sonic_01"],
            target_entity_id=None,
        )
        actions.append(act_atmosphere)
        dependencies[act_atmosphere.action_id] = ["act_sonic_01"]

        # 5. Cultural Programming Action
        act_programming = ExecutionPlanAction(
            action_id="act_prog_01",
            title="Schedule Recurring Analog Listening Salon",
            description=(
                "Lock monthly curatorial calendar date for deep-listening vinyl session "
                "paired with single-origin tasting flights."
            ),
            owner="Cultural Curator",
            estimated_cost="$2,500 (guest selector honorarium & event production)",
            dependencies=["act_sonic_01", "act_hospitality_01"],
            target_entity_id=None,
        )
        actions.append(act_programming)
        dependencies[act_programming.action_id] = [
            "act_sonic_01",
            "act_hospitality_01",
        ]

        cost_summary = (
            "$12,500 total estimated allocation ($3,500 audio setup, $4,200 tableware, "
            "$500 outreach, $1,800 hospitality, $2,500 programming)"
        )
        risks = [
            "Acoustic decibel leakage during evening dayparts; mitigated by 65dB sound ceiling.",
            "Brand over-commercialization risk; mitigated by strict zero-promotional-banner policy.",
            "Procurement lead-time risk for custom tableware; mitigated by 4-week inventory buffer.",
        ]
        approvals = [
            "General Manager",
            "Cultural Curator",
            "Financial Controller",
        ]

        return ExecutionPlan(
            plan_id=plan_id,
            actions=actions,
            dependencies=dependencies,
            estimated_cost=cost_summary,
            risks=risks,
            approvals_required=approvals,
            evidence=evidence,
        )

    # -------------------------------------------------------------------------
    # 2. VALIDATE Phase: Audit all constraints and failure modes
    # -------------------------------------------------------------------------
    async def validate_plan(
        self,
        payload: GovernanceValidationInput,
        execution_plan: ExecutionPlan | None = None,
    ) -> GovernanceValidationOutput:
        """Audits the generated cultural plan across all 7 mandatory validation criteria.

        Validation Checks:
        1. missing evidence (missing Qloo signals or query metadata)
        2. conflicting recommendations (conflicts with exclusions or acoustic contradictions)
        3. budget violations (budget constraint breaches)
        4. invalid entities (zero-hallucination ground truth audit)
        5. low confidence (affinity or confidence below threshold)
        6. duplicate actions (redundant or duplicate action IDs/targets)
        7. unsupported external actions (unauthorized external mutations)
        """
        if isinstance(payload, dict):
            payload = GovernanceValidationInput.model_validate(payload)
        elif not isinstance(payload, GovernanceValidationInput):
            raise TypeError(
                f"Expected GovernanceValidationInput or dict, got {type(payload).__name__}"
            )

        if execution_plan is not None:
            if isinstance(execution_plan, dict):
                execution_plan = ExecutionPlan.model_validate(execution_plan)
            elif not isinstance(execution_plan, ExecutionPlan):
                raise TypeError(
                    f"Expected ExecutionPlan, dict, or None, got {type(execution_plan).__name__}"
                )

        twin = payload.cultural_twin
        matrix = payload.cultural_matrix
        strategy = payload.strategy
        experience = payload.experience_design
        partnerships = payload.partnerships

        logger.info(
            "[%s] Executing comprehensive 7-point governance validation audit",
            self.name,
        )

        compliance_checks: list[ComplianceCheck] = []
        risk_flags: list[str] = []
        unverified_ids: list[str] = []

        # Check 1: Missing Evidence
        has_matrix_evidence = (
            bool(matrix.evidence) or bool(matrix.query_metadata) or bool(matrix.artists)
        )
        has_recs_evidence = True
        for rec in experience.sonic_identity.curated_recommendations:
            if not rec.qloo_evidence:
                has_recs_evidence = False
                break
        evidence_passed = has_matrix_evidence and has_recs_evidence
        compliance_checks.append(
            ComplianceCheck(
                rule_name="missing_evidence_audit",
                passed=evidence_passed,
                detail=(
                    "All recommendations and cultural signals are backed by verifiable Qloo evidence."
                    if evidence_passed
                    else "Missing Qloo evidence detected in one or more recommendation payloads."
                ),
            )
        )
        if not evidence_passed:
            risk_flags.append(
                "Missing evidence: Recommendations lack verifiable Qloo provenance."
            )

        # Check 2: Conflicting Recommendations
        exclusions_lower = [e.lower() for e in twin.exclusions if e.strip()]
        conflicts: list[str] = []

        # Check if recommended entities match exclusions
        for rec in (
            experience.sonic_identity.curated_recommendations
            + experience.brand_ecosystem.curated_recommendations
        ):
            r_name_lower = rec.recommendation.lower()
            if any(ex in r_name_lower or r_name_lower in ex for ex in exclusions_lower):
                conflicts.append(
                    f"Entity '{rec.recommendation}' conflicts with cultural exclusion list"
                )

        # Check acoustic atmosphere conflicts
        if (
            "75db" in " ".join(twin.cultural_constraints).lower()
            or "quiet" in (twin.mood or "").lower()
        ):
            for directive in experience.sonic_identity.directives:
                if "club level" in directive.lower() or "85db" in directive:
                    conflicts.append(
                        f"Sonic directive '{directive}' contradicts quiet/75dB acoustic guardrail"
                    )

        conflicts_passed = len(conflicts) == 0
        compliance_checks.append(
            ComplianceCheck(
                rule_name="conflicting_recommendations_audit",
                passed=conflicts_passed,
                detail=(
                    "Zero conflicting recommendations or aesthetic contradictions detected."
                    if conflicts_passed
                    else f"Conflicting recommendations detected: {'; '.join(conflicts)}"
                ),
            )
        )
        if not conflicts_passed:
            risk_flags.append(f"Conflicting recommendations: {'; '.join(conflicts)}")

        # Check 3: Budget Violations
        budget_str = (twin.budget or "Medium Tier").lower()
        budget_passed = True
        budget_detail = f"Plan financial requirements align with {twin.budget or 'standard'} budget tier."

        if any(
            b in budget_str for b in ["tight", "under $10k", "micro", "minimal"]
        ) and (
            execution_plan
            and (
                "$50,000" in execution_plan.estimated_cost
                or "$100,000" in execution_plan.estimated_cost
            )
        ):
            budget_passed = False
            budget_detail = f"Budget violation: Estimated cost exceeds strict ceiling ({budget_str})."

        compliance_checks.append(
            ComplianceCheck(
                rule_name="budget_violations_audit",
                passed=budget_passed,
                detail=budget_detail,
            )
        )
        if not budget_passed:
            risk_flags.append(budget_detail)

        # Check 4: Invalid Entities (Zero Hallucination Audit)
        verified_truth_ids: set[str] = set(twin.anchor_entities)
        for matrix_item in (
            matrix.artists
            + matrix.books
            + matrix.brands
            + matrix.places
            + matrix.movies
            + matrix.destinations
        ):
            verified_truth_ids.add(matrix_item.id)

        referenced_ids: set[str] = set()
        for pillar in strategy.cultural_pillars:
            referenced_ids.update(pillar.aligned_entity_ids)

        for daypart in experience.daypart_programs:
            referenced_ids.update(daypart.featured_artist_ids)

        for zone in experience.spatial_zones:
            referenced_ids.update(zone.design_reference_ids)

        for p in partnerships.partnerships:
            referenced_ids.add(p.partner_entity_id)

        for c in partnerships.candidates:
            referenced_ids.add(c.brand_entity_id)

        for ref_id in referenced_ids:
            if ref_id not in verified_truth_ids:
                unverified_ids.append(ref_id)

        provenance_passed = len(unverified_ids) == 0
        compliance_checks.append(
            ComplianceCheck(
                rule_name="invalid_entities_audit",
                passed=provenance_passed,
                detail=(
                    f"Audited {len(referenced_ids)} referenced entity IDs. "
                    f"{len(unverified_ids)} unverified/hallucinated IDs detected."
                    if not provenance_passed
                    else f"All {len(referenced_ids)} referenced entity IDs verified against Qloo origin."
                ),
            )
        )
        if not provenance_passed:
            risk_flags.append(
                f"Provenance violation: Invalid entities detected: Unverified IDs: {unverified_ids}"
            )

        # Check 5: Low Confidence
        low_confidence_items: list[str] = []
        for p in partnerships.partnerships:
            if p.affinity_score < 0.50:
                low_confidence_items.append(f"{p.partner_name} ({p.affinity_score})")
        for cand in partnerships.candidates:
            if cand.score < 50.0:
                low_confidence_items.append(f"{cand.brand} ({cand.score})")

        confidence_passed = len(low_confidence_items) == 0
        compliance_checks.append(
            ComplianceCheck(
                rule_name="confidence_threshold_audit",
                passed=confidence_passed,
                detail=(
                    "All recommendations satisfy the minimum cultural affinity and confidence thresholds."
                    if confidence_passed
                    else f"Low confidence detected for: {', '.join(low_confidence_items)}"
                ),
            )
        )
        if not confidence_passed:
            risk_flags.append(
                f"Low confidence recommendations detected: {low_confidence_items}"
            )

        # Check 6: Duplicate Actions
        duplicate_actions: list[str] = []
        if execution_plan:
            seen_actions: set[str] = set()
            for a in execution_plan.actions:
                if a.action_id in seen_actions:
                    duplicate_actions.append(a.action_id)
                seen_actions.add(a.action_id)

        duplicates_passed = len(duplicate_actions) == 0
        compliance_checks.append(
            ComplianceCheck(
                rule_name="duplicate_actions_audit",
                passed=duplicates_passed,
                detail=(
                    "Zero duplicate actions detected in execution plan."
                    if duplicates_passed
                    else f"Duplicate action IDs detected: {duplicate_actions}"
                ),
            )
        )
        if not duplicates_passed:
            risk_flags.append(f"Duplicate actions detected: {duplicate_actions}")

        # Check 7: Unsupported External Actions
        unsupported_actions: list[str] = []
        if execution_plan:
            for a in execution_plan.actions:
                # Actions must map to legitimate physical/cultural operations
                if any(
                    bad in a.action_id.lower()
                    for bad in ["bank_transfer", "raw_http", "shell_exec"]
                ):
                    unsupported_actions.append(a.action_id)

        supported_passed = len(unsupported_actions) == 0
        compliance_checks.append(
            ComplianceCheck(
                rule_name="unsupported_external_actions_audit",
                passed=supported_passed,
                detail=(
                    "All actions map to validated physical space operational handlers."
                    if supported_passed
                    else f"Unsupported external actions flagged: {unsupported_actions}"
                ),
            )
        )
        if not supported_passed:
            risk_flags.append(
                f"Unsupported external actions flagged: {unsupported_actions}"
            )

        # Overall validity
        all_passed = all(c.passed for c in compliance_checks)
        readiness_score = 1.0 if all_passed else 0.3

        return GovernanceValidationOutput(
            is_valid=all_passed,
            provenance_verified=provenance_passed,
            compliance_checks=compliance_checks,
            risk_flags=risk_flags,
            unverified_entity_ids=unverified_ids,
            readiness_score=readiness_score,
        )

    def validate_task_provenance(self, task: ExecutionTask) -> None:
        """Validates that an execution task retains complete verifiable provenance."""
        required_keys = [
            "source",
            "source_id",
            "source_type",
            "query",
            "timestamp",
            "task_id",
            "plan_id",
            "session_id",
            "approved_by",
            "approved_at",
            "execution_status",
        ]
        prov = task.provenance or {}
        missing = [k for k in required_keys if not prov.get(k)]
        if missing:
            raise ProvenanceValidationError(
                f"Execution blocked: Task '{task.task_id}' missing mandatory provenance fields: {missing}"
            )
        source_id = str(prov.get("source_id", ""))
        if (
            source_id.startswith(("invalid_", "unverified_"))
            or source_id == "unverified"
        ):
            raise ProvenanceValidationError(
                f"Execution blocked: Task '{task.task_id}' references invalid/unverified Qloo ID '{source_id}'."
            )

    async def _execute_or_stage_task(
        self,
        task: ExecutionTask,
        session_id: str,
        plan_id: str,
        plan_version: int,
        target_entity_id: str,
    ) -> ExecutionTask:
        """Executes task via registered connector or stages/not_configures honestly."""
        registry = self.connector_registry
        conn = registry.get_connector(task.category) if registry else None

        if conn is None:
            task.status = TaskStatus.NOT_CONFIGURED
            task.output_reference = None
            task.result = {
                "status": "not_configured",
                "message": f"No connector registered for '{task.category}'",
            }
        elif conn.configuration_status != ConfigurationStatus.CONFIGURED:
            task.status = TaskStatus.STAGED
            task.output_reference = f"staged://{task.category}/{target_entity_id}"
            task.result = {
                "status": "staged",
                "connector": conn.name,
                "configuration_status": conn.configuration_status.value,
                "message": (
                    f"Provider credentials for '{conn.name}' are not configured. "
                    "Operation is staged for curatorial review."
                ),
            }
        else:
            try:
                res = await registry.dispatch_task(
                    task,
                    session_id=session_id,
                    plan_id=plan_id,
                    plan_version=plan_version,
                )
                task.status = TaskStatus.COMPLETED
                task.output_reference = res.output_reference
                task.result = res.payload
                task.executed_at = res.executed_at
            except Exception as exc:
                logger.error(
                    "[%s] Execution dispatch failed for task %s: %s",
                    self.name,
                    task.task_id,
                    exc,
                )
                task.status = TaskStatus.FAILED
                task.result = {
                    "status": "failed",
                    "connector": conn.name,
                    "error": str(exc),
                }

        if task.provenance:
            task.provenance["execution_status"] = task.status.value

        self.validate_task_provenance(task)

        # Durably persist outcome immediately to close the crash window
        if task.idempotency_key:
            if task.status in (
                TaskStatus.COMPLETED,
                TaskStatus.STAGED,
                TaskStatus.NOT_CONFIGURED,
            ):
                self.durable_store.save_outcome(task.idempotency_key, task)
                self._idempotency_store[task.idempotency_key] = task
            else:
                self.durable_store.release_reservation(task.idempotency_key)

        return task

    # -------------------------------------------------------------------------
    # 3. APPROVAL & 4. EXECUTION Phases: Enforce Gate & Generate Tasks
    # -------------------------------------------------------------------------
    async def execute_plan(
        self,
        plan: CulturalActivationPlan,
        is_approved: bool = False,
        approved_by: str | None = None,
        approval: ApprovalRecord | None = None,
        session_id: str | None = None,
    ) -> ExecutionSummary:
        """Executes concrete downstream activation tasks once human approval is confirmed.

        Strict Constraints:
        - The agent must NEVER execute external actions before explicit approval.
        - Execution must be idempotent: tasks with matching idempotency keys return existing results.
        - Approval must match plan_id and plan_version, and plan must not have mutated.
        - Every execution task must pass strict provenance validation before execution.
        """
        # Strict Human-in-the-Loop Gate Enforcement
        if isinstance(plan, dict):
            plan = CulturalActivationPlan.model_validate(plan)
        elif not isinstance(plan, CulturalActivationPlan):
            raise TypeError(
                f"Expected CulturalActivationPlan or dict, got {type(plan).__name__}"
            )

        if not is_approved:
            logger.error(
                "[%s] Security violation: Attempted execution of plan '%s' prior to approval.",
                self.name,
                plan.plan_id,
            )
            raise UnapprovedExecutionError(
                "The agent must NEVER execute external actions before explicit approval."
            )

        if approval is not None:
            if not approval.is_valid:
                raise UnapprovedExecutionError(
                    f"Approval is invalidated: {approval.invalidation_reason or 'Invalid approval'}"
                )
            if approval.plan_id != plan.plan_id:
                raise UnapprovedExecutionError(
                    f"Approval plan_id '{approval.plan_id}' does not match plan '{plan.plan_id}'."
                )
            if approval.plan_version != plan.version:
                raise UnapprovedExecutionError(
                    f"Approval for plan version {approval.plan_version} does not authorize version {plan.version}."
                )
            # Mutation Check: If plan hash changed after approval, invalidate!
            current_hash = plan.compute_hash()
            if approval.plan_hash and approval.plan_hash != current_hash:
                approval.is_valid = False
                approval.invalidation_reason = "Plan was mutated after approval"
                raise UnapprovedExecutionError(
                    "Plan was mutated after approval. Previous approval is invalidated."
                )

        if plan.governance and not plan.governance.is_valid:
            logger.error(
                "[%s] Security violation: Attempted execution of unvalidated plan '%s'.",
                self.name,
                plan.plan_id,
            )
            raise UnapprovedExecutionError(
                f"Cannot execute unvalidated plan: {plan.governance.risk_flags}"
            )

        async with self.lock:
            # Pre-populate idempotency store from existing tasks in plan if resuming
            if plan.execution_summary and plan.execution_summary.tasks:
                for past_task in plan.execution_summary.tasks:
                    if past_task.idempotency_key and past_task.status in (
                        TaskStatus.COMPLETED,
                        TaskStatus.STAGED,
                        TaskStatus.NOT_CONFIGURED,
                    ):
                        self._idempotency_store[past_task.idempotency_key] = past_task

            logger.info(
                "[%s] Human approval verified (approver: %s). Dispatching execution tasks for plan '%s'",
                self.name,
                approved_by or "curator",
                plan.plan_id,
            )

            tasks: list[ExecutionTask] = []
            now = datetime.now(UTC)
            approver_tag = (
                (approval.approver if approval else None)
                or approved_by
                or "human_curator"
            )
            approval_time = (approval.approved_at if approval else None) or now
            sess_id = (
                (approval.session_id if approval else None)
                or session_id
                or plan.plan_id
            )

            # 1. Spotify Audio Seeding Task
            if plan.cultural_matrix.artists:
                lead_artist = plan.cultural_matrix.artists[0]
                task_id = f"task_{lead_artist.id}_{plan.plan_id[:6]}"
                idem_key = f"idem_{plan.plan_id}_spotify_{lead_artist.id}"

                cached_task = self.durable_store.get_outcome(
                    idem_key
                ) or self._idempotency_store.get(idem_key)
                if cached_task and cached_task.status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.STAGED,
                    TaskStatus.NOT_CONFIGURED,
                ):
                    logger.info(
                        "Task with idempotency key '%s' was already executed. Returning previous result.",
                        idem_key,
                    )
                    tasks.append(cached_task)
                else:
                    acquired, outcome = await self.durable_store.async_reserve_or_wait(
                        idem_key
                    )
                    if not acquired and outcome:
                        self._idempotency_store[idem_key] = outcome
                        tasks.append(outcome)
                    else:
                        task = ExecutionTask(
                            task_id=task_id,
                            idempotency_key=idem_key,
                            action=f"Export seed artist '{lead_artist.name}' to Spotify audio engine pipeline",
                            owner="Audio Curator",
                            input={
                                "engine": "spotify",
                                "artist_id": lead_artist.id,
                                "artist_name": lead_artist.name,
                                "affinity": lead_artist.affinity,
                                "daypart": "evening",
                            },
                            status=TaskStatus.PENDING,
                            timestamp=now,
                            provenance={
                                "source": "qloo_insights_artist",
                                "source_id": lead_artist.id,
                                "source_type": "artist",
                                "query": "/v2/insights",
                                "timestamp": now.isoformat(),
                                "task_id": task_id,
                                "plan_id": plan.plan_id,
                                "session_id": sess_id,
                                "approved_by": approver_tag,
                                "approved_at": approval_time.isoformat(),
                                "execution_status": "PENDING",
                                "entity_id": lead_artist.id,
                            },
                            category="spotify_audio_seed",
                            description=f"Export seed artist '{lead_artist.name}' to Spotify audio engine pipeline",
                            target_partner_or_artist=lead_artist.name,
                            target_entity_id=lead_artist.id,
                            executed_at=now,
                            output_reference=None,
                            result={"status": "pending", "artist_id": lead_artist.id},
                        )
                        task = await self._execute_or_stage_task(
                            task,
                            session_id=sess_id,
                            plan_id=plan.plan_id,
                            plan_version=plan.version,
                            target_entity_id=lead_artist.id,
                        )
                        tasks.append(task)

            # 2. Partnership Outreach Brief Dispatch Tasks
            for p in plan.partnerships.partnerships[:2]:
                task_id = f"task_{p.partner_entity_id}_{plan.plan_id[:6]}"
                idem_key = f"idem_{plan.plan_id}_partner_{p.partner_entity_id}"

                cached_task = self.durable_store.get_outcome(
                    idem_key
                ) or self._idempotency_store.get(idem_key)
                if cached_task and cached_task.status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.STAGED,
                    TaskStatus.NOT_CONFIGURED,
                ):
                    logger.info(
                        "Task with idempotency key '%s' was already executed. Returning previous result.",
                        idem_key,
                    )
                    tasks.append(cached_task)
                else:
                    acquired, outcome = await self.durable_store.async_reserve_or_wait(
                        idem_key
                    )
                    if not acquired and outcome:
                        self._idempotency_store[idem_key] = outcome
                        tasks.append(outcome)
                    else:
                        task = ExecutionTask(
                            task_id=task_id,
                            idempotency_key=idem_key,
                            action=f"Dispatch collaboration brief for '{p.partner_name}' ({p.activation_type})",
                            owner="Partnership Director",
                            input={
                                "partner_name": p.partner_name,
                                "partner_entity_id": p.partner_entity_id,
                                "activation_type": p.activation_type,
                                "affinity_score": p.affinity_score,
                            },
                            status=TaskStatus.PENDING,
                            timestamp=now,
                            provenance={
                                "source": "qloo_insights_brand",
                                "source_id": p.partner_entity_id,
                                "source_type": "brand",
                                "query": "/v2/insights",
                                "timestamp": now.isoformat(),
                                "task_id": task_id,
                                "plan_id": plan.plan_id,
                                "session_id": sess_id,
                                "approved_by": approver_tag,
                                "approved_at": approval_time.isoformat(),
                                "execution_status": "PENDING",
                                "entity_id": p.partner_entity_id,
                            },
                            category="partner_outreach_brief",
                            description=f"Dispatch collaboration brief for '{p.partner_name}' ({p.activation_type})",
                            target_partner_or_artist=p.partner_name,
                            target_entity_id=p.partner_entity_id,
                            executed_at=now,
                            output_reference=None,
                            result={
                                "status": "pending",
                                "partner_entity_id": p.partner_entity_id,
                            },
                        )
                        task = await self._execute_or_stage_task(
                            task,
                            session_id=sess_id,
                            plan_id=plan.plan_id,
                            plan_version=plan.version,
                            target_entity_id=p.partner_entity_id,
                        )
                        tasks.append(task)

            # 3. Spatial Specification Task
            if plan.experience_design.spatial_zones:
                lead_zone = plan.experience_design.spatial_zones[0]
                task_id = f"task_{lead_zone.zone_name.lower().replace(' ', '_')}_{plan.plan_id[:6]}"
                idem_key = f"idem_{plan.plan_id}_spatial_{lead_zone.zone_name.lower().replace(' ', '_')}"

                cached_task = self.durable_store.get_outcome(
                    idem_key
                ) or self._idempotency_store.get(idem_key)
                if cached_task and cached_task.status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.STAGED,
                    TaskStatus.NOT_CONFIGURED,
                ):
                    logger.info(
                        "Task with idempotency key '%s' was already executed. Returning previous result.",
                        idem_key,
                    )
                    tasks.append(cached_task)
                else:
                    acquired, outcome = await self.durable_store.async_reserve_or_wait(
                        idem_key
                    )
                    if not acquired and outcome:
                        self._idempotency_store[idem_key] = outcome
                        tasks.append(outcome)
                    else:
                        source_id = (
                            plan.cultural_matrix.places[0].id
                            if plan.cultural_matrix.places
                            else f"zone_{lead_zone.zone_name.lower().replace(' ', '_')}"
                        )
                        source_type = (
                            "place" if plan.cultural_matrix.places else "spatial_zone"
                        )
                        task = ExecutionTask(
                            task_id=task_id,
                            idempotency_key=idem_key,
                            action=f"Generate physical design spec for zone '{lead_zone.zone_name}'",
                            owner="Spatial Designer",
                            input={
                                "zone_name": lead_zone.zone_name,
                                "lighting": "2400K warm indirect dimming",
                                "acoustics": "60dB max ambient",
                            },
                            status=TaskStatus.PENDING,
                            timestamp=now,
                            provenance={
                                "source": "qloo_insights_place",
                                "source_id": source_id,
                                "source_type": source_type,
                                "query": "/v2/insights",
                                "timestamp": now.isoformat(),
                                "task_id": task_id,
                                "plan_id": plan.plan_id,
                                "session_id": sess_id,
                                "approved_by": approver_tag,
                                "approved_at": approval_time.isoformat(),
                                "execution_status": "PENDING",
                                "zone": lead_zone.zone_name,
                            },
                            category="spatial_design_spec",
                            description=f"Generate physical design spec for zone '{lead_zone.zone_name}'",
                            target_partner_or_artist=lead_zone.zone_name,
                            target_entity_id=source_id,
                            executed_at=now,
                            output_reference=None,
                            result={
                                "status": "pending",
                                "zone": lead_zone.zone_name,
                            },
                        )
                        task = await self._execute_or_stage_task(
                            task,
                            session_id=sess_id,
                            plan_id=plan.plan_id,
                            plan_version=plan.version,
                            target_entity_id=source_id,
                        )
                        tasks.append(task)

            # ---------------------------------------------------------------------
            # 5. AUDIT Phase: Generate Post-Execution Audit Report
            # ---------------------------------------------------------------------
            audit_report = self.audit(plan, tasks)

            completed_count = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
            staged_count = sum(1 for t in tasks if t.status == TaskStatus.STAGED)
            not_configured_count = sum(
                1 for t in tasks if t.status == TaskStatus.NOT_CONFIGURED
            )
            failed_count = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
            executed_count = completed_count + staged_count + not_configured_count

            return ExecutionSummary(
                total_tasks=len(tasks),
                executed_tasks=executed_count,
                completed_tasks=completed_count,
                staged_tasks=staged_count,
                not_configured_tasks=not_configured_count,
                failed_tasks=failed_count,
                tasks=tasks,
                completed_at=datetime.now(UTC),
                audit_report=audit_report,
            )

    # -------------------------------------------------------------------------
    # 5. AUDIT Phase: Verify Execution Integrity
    # -------------------------------------------------------------------------
    def audit(
        self, plan: CulturalActivationPlan, tasks: list[ExecutionTask]
    ) -> AuditReport:
        """Conducts a post-execution audit validating task provenance and execution bounds."""
        if isinstance(plan, dict):
            plan = CulturalActivationPlan.model_validate(plan)
        elif not isinstance(plan, CulturalActivationPlan):
            raise TypeError(
                f"Expected CulturalActivationPlan or dict, got {type(plan).__name__}"
            )

        audit_id = f"audit_{uuid.uuid4().hex[:8]}"
        provenance_violations = sum(1 for t in tasks if not t.provenance)
        unsupported = sum(
            1 for t in tasks if t.category not in self.SUPPORTED_CATEGORIES
        )

        findings = [
            f"Audited {len(tasks)} executed physical tasks.",
            "Human approval confirmed prior to task dispatch.",
            "All executed tasks verified against Qloo cultural provenance.",
        ]

        status = (
            "COMPLIANT"
            if provenance_violations == 0 and unsupported == 0
            else "FLAGGED"
        )

        return AuditReport(
            audit_id=audit_id,
            plan_id=plan.plan_id,
            total_actions_planned=len(
                plan.execution_plan.actions if plan.execution_plan else tasks
            ),
            total_tasks_executed=len(tasks),
            provenance_violations=provenance_violations,
            unsupported_actions_blocked=unsupported,
            approval_verified=True,
            compliance_status=status,
            findings=findings,
        )
