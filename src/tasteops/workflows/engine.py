"""TasteOps Workflow Engine.

Orchestrates deterministic state transitions for physical space cultural activations:
CREATED -> INTENT_PARSED -> CULTURAL_TWIN_CREATED -> QLOO_RESOLVED ->
CULTURAL_MATRIX_READY -> AGENTS_RUNNING -> PLAN_GENERATED -> VALIDATED ->
AWAITING_APPROVAL -> APPROVED -> EXECUTING -> COMPLETED (or FAILED).

Guarantees:
- Bounded Qloo retries and fallback before FAILED (no infinite network loops).
- Bounded Agent retries before FAILED (no infinite agent loops).
- Validation failure transitions back to PLAN_GENERATED for bounded corrective cycles.
- Persists state transitions and emits an immutable AuditEvent on every transition.
- Never makes direct Qloo REST API calls; all cultural data is requested via MCP tools.
- Enforces strict human approval gate at AWAITING_APPROVAL before execution.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tasteops.agents.governance import UnapprovedExecutionError
from tasteops.models.cultural_matrix import (
    CulturalTwin,
    LocationInput,
    PhysicalSpaceBrief,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.persistence import (
    AuditEvent,
    BaseStateStore,
    InMemoryStateStore,
)
from tasteops.workflows.schemas import (
    ApprovalRecord,
    CulturalActivationPlan,
    CulturalStrategyInput,
    ExperienceDesignInput,
    GovernanceValidationInput,
    PartnershipInput,
)
from tasteops.workflows.states import WorkflowState, validate_transition

if TYPE_CHECKING:
    from tasteops.agents.architect import ExperienceArchitect
    from tasteops.agents.governance import GovernanceAgent
    from tasteops.agents.mcp_adapter import CulturalIntelligenceMCPAdapter
    from tasteops.agents.partnership import PartnershipAgent
    from tasteops.agents.strategist import CulturalStrategist

logger = logging.getLogger("tasteops.workflows.engine")


class WorkflowEngine:
    """Deterministic orchestrator executing finite state machine transitions."""

    def __init__(
        self,
        mcp_adapter: CulturalIntelligenceMCPAdapter | None = None,
        strategist: CulturalStrategist | None = None,
        architect: ExperienceArchitect | None = None,
        partnership: PartnershipAgent | None = None,
        governance: GovernanceAgent | None = None,
        store: BaseStateStore | None = None,
        max_qloo_retries: int = 2,
        max_agent_retries: int = 2,
        max_validation_cycles: int = 2,
    ) -> None:
        from tasteops.agents.architect import ExperienceArchitect
        from tasteops.agents.governance import GovernanceAgent
        from tasteops.agents.mcp_adapter import CulturalIntelligenceMCPAdapter
        from tasteops.agents.partnership import PartnershipAgent
        from tasteops.agents.strategist import CulturalStrategist

        self.mcp = mcp_adapter or CulturalIntelligenceMCPAdapter()
        self.strategist = strategist or CulturalStrategist(mcp_adapter=self.mcp)
        self.architect = architect or ExperienceArchitect()
        self.partnership = partnership or PartnershipAgent()
        self.governance = governance or GovernanceAgent()
        self.store = store or InMemoryStateStore()

        # Guardrail bounds against infinite loops
        self.max_qloo_retries = max_qloo_retries
        self.max_agent_retries = max_agent_retries
        self.max_validation_cycles = max_validation_cycles

    def _record_and_persist(
        self,
        ctx: WorkflowContext,
        to_state: WorkflowState,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AuditEvent:
        """Records transition in context history and persists audit event to store."""
        event = ctx.record_transition(
            to_state=to_state,
            reason=reason,
            metadata=metadata or {},
            error=error,
        )
        if self.store:
            try:
                self.store.save_transition(event, ctx)
            except Exception as exc:
                logger.warning(
                    "StateStore persistence failed for session %s: %s",
                    ctx.session_id,
                    exc,
                )
        return event

    # -------------------------------------------------------------------------
    # Transition: Step 1 - Initialize and Parse Intent
    # -------------------------------------------------------------------------
    def initialize_session(
        self,
        raw_intent: str,
        parsed_hints: dict[str, Any] | None = None,
        space_id: str | None = None,
    ) -> WorkflowContext:
        """Creates a fresh session in CREATED state."""
        ctx = WorkflowContext(
            user_input=raw_intent,
            space_id=space_id,
            parsed_intent=parsed_hints or {},
        )
        self._record_and_persist(
            ctx,
            WorkflowState.CREATED,
            reason="Session initialized with raw intent",
            metadata={"space_id": space_id} if space_id else {},
        )
        return ctx

    async def parse_intent(
        self, ctx: WorkflowContext, parsed_data: dict[str, Any] | None = None
    ) -> WorkflowContext:
        """Transitions CREATED -> INTENT_PARSED."""
        validate_transition(ctx.current_state, WorkflowState.INTENT_PARSED)

        if parsed_data:
            ctx.parsed_intent.update(parsed_data)

        # Ensure minimal required intent fields exist or provide defaults
        if not ctx.parsed_intent.get("business_type"):
            ctx.parsed_intent["business_type"] = "Curated Physical Space"

        self._record_and_persist(
            ctx,
            WorkflowState.INTENT_PARSED,
            reason="User intent parsed into structured domain attributes",
            metadata={"parsed_keys": list(ctx.parsed_intent.keys())},
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 2 - Create Cultural Twin
    # -------------------------------------------------------------------------
    async def create_cultural_twin(self, ctx: WorkflowContext) -> WorkflowContext:
        """Transitions INTENT_PARSED -> CULTURAL_TWIN_CREATED."""
        validate_transition(ctx.current_state, WorkflowState.CULTURAL_TWIN_CREATED)

        intent = ctx.parsed_intent
        loc_data = intent.get("location")
        loc_model = None
        if isinstance(loc_data, dict):
            loc_model = LocationInput(**loc_data)

        ctx.cultural_twin = CulturalTwin(
            target_audience=intent.get("target_audience"),
            location=loc_model,
            business_type=intent.get("business_type"),
            mood=intent.get("mood"),
            positioning=intent.get("positioning"),
            anchor_entities=[],  # Will be resolved in QLOO_RESOLVED
            resolved_tags=[],  # Will be resolved in QLOO_RESOLVED
            constraints=intent.get("constraints", {}),
        )

        self._record_and_persist(
            ctx,
            WorkflowState.CULTURAL_TWIN_CREATED,
            reason="Initial CulturalTwin instantiated; anchors and tags pending Qloo resolution",
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 3 - Resolve Cultural Anchors via MCP
    # Flow: RETRY -> FALLBACK -> FAILED
    # -------------------------------------------------------------------------
    async def resolve_qloo_anchors(self, ctx: WorkflowContext) -> WorkflowContext:
        """Transitions CULTURAL_TWIN_CREATED -> QLOO_RESOLVED via MCP server with retry/fallback/fail flow."""
        validate_transition(ctx.current_state, WorkflowState.QLOO_RESOLVED)

        if not ctx.cultural_twin:
            raise RuntimeError(
                "Cannot resolve Qloo anchors: CulturalTwin has not been created."
            )

        intent = ctx.parsed_intent
        loc_data = intent.get("location")
        loc_model: LocationInput | None = None
        if isinstance(loc_data, dict):
            loc_model = LocationInput(**loc_data)
        elif isinstance(loc_data, LocationInput):
            loc_model = loc_data

        raw_entities = intent.get("raw_anchor_entities", [])
        raw_tags = intent.get("raw_tags", [])

        brief = PhysicalSpaceBrief(
            business_type=intent.get("business_type", "Curated Physical Space"),
            location=loc_model,
            target_audience=intent.get("target_audience"),
            positioning=intent.get("positioning"),
            desired_mood=intent.get("mood"),
            budget=intent.get("budget"),
            constraints=intent.get("constraints"),
            anchor_entities=raw_entities + raw_tags,
        )

        twin: CulturalTwin | None = None
        qloo_succeeded = False
        last_error = None

        # Bounded Retry Loop: RETRY
        for attempt in range(self.max_qloo_retries + 1):
            try:
                twin = await self.strategist.transform_brief(brief)
                qloo_succeeded = True
                break
            except Exception as exc:
                ctx.qloo_retry_count += 1
                last_error = str(exc)
                logger.warning(
                    "Qloo anchor resolution attempt %d failed: %s",
                    attempt + 1,
                    exc,
                )
                if attempt >= self.max_qloo_retries:
                    # Bounded Retries Exhausted -> FALLBACK
                    logger.info(
                        "Qloo resolution retries exhausted. Activating FALLBACK."
                    )
                    try:
                        fallback_brief = brief.model_copy(deep=True)
                        fallback_brief.anchor_entities = [
                            e for e in brief.anchor_entities if len(str(e).strip()) > 1
                        ]
                        twin = await self.strategist.transform_brief(fallback_brief)
                        qloo_succeeded = True
                    except Exception as fb_exc:
                        logger.error(
                            "Qloo fallback anchor resolution failed: %s", fb_exc
                        )
                        qloo_succeeded = False

        if not qloo_succeeded or twin is None:
            # Fallback exhausted -> FAILED
            validate_transition(ctx.current_state, WorkflowState.FAILED)
            self._record_and_persist(
                ctx,
                WorkflowState.FAILED,
                reason="QLOO_FAILURE_TERMINAL: Anchor resolution failed after bounded retries and fallback",
                error=last_error,
            )
            ctx.error_message = f"QLOO_FAILURE: Anchor resolution failed: {last_error}"
            return ctx

        ctx.cultural_twin = twin
        self._record_and_persist(
            ctx,
            WorkflowState.QLOO_RESOLVED,
            reason="Cultural anchors and aesthetic tags resolved through Cultural Intelligence MCP server",
            metadata={
                "resolved_entities_count": len(ctx.cultural_twin.resolved_entities),
                "resolved_tags_count": len(ctx.cultural_twin.resolved_tags),
                "entity_ids": ctx.cultural_twin.resolved_entity_ids,
                "tag_ids": ctx.cultural_twin.resolved_tags,
                "qloo_retries_used": ctx.qloo_retry_count,
            },
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 4 - Fetch Cultural Matrix via MCP
    # Flow: RETRY -> FALLBACK -> FAILED
    # -------------------------------------------------------------------------
    async def fetch_cultural_matrix(
        self, ctx: WorkflowContext, take_per_category: int = 10
    ) -> WorkflowContext:
        """Transitions QLOO_RESOLVED -> CULTURAL_MATRIX_READY via MCP server with retry/fallback/fail flow."""
        validate_transition(ctx.current_state, WorkflowState.CULTURAL_MATRIX_READY)

        if not ctx.cultural_twin:
            raise RuntimeError("Cannot fetch CulturalMatrix: CulturalTwin is missing.")

        matrix = None
        last_error = None

        # Bounded Retry Loop: RETRY
        for attempt in range(self.max_qloo_retries + 1):
            try:
                matrix = await self.mcp.get_cultural_matrix(
                    twin=ctx.cultural_twin,
                    take_per_category=take_per_category,
                )
                break
            except Exception as exc:
                ctx.qloo_retry_count += 1
                last_error = str(exc)
                logger.warning(
                    "CulturalMatrix fetch attempt %d failed: %s",
                    attempt + 1,
                    exc,
                )
                if attempt >= self.max_qloo_retries:
                    # Bounded Retries Exhausted -> FALLBACK
                    logger.info(
                        "CulturalMatrix retries exhausted. Activating FALLBACK."
                    )
                    try:
                        matrix = await self.mcp.get_cultural_matrix(
                            twin=ctx.cultural_twin,
                            take_per_category=3,
                        )
                    except Exception as fb_exc:
                        logger.error("CulturalMatrix fallback query failed: %s", fb_exc)

        if matrix is None:
            # Fallback exhausted -> FAILED
            validate_transition(ctx.current_state, WorkflowState.FAILED)
            self._record_and_persist(
                ctx,
                WorkflowState.FAILED,
                reason="QLOO_FAILURE_TERMINAL: CulturalMatrix generation failed after bounded retries and fallback",
                error=last_error,
            )
            ctx.error_message = (
                f"QLOO_FAILURE: CulturalMatrix generation failed: {last_error}"
            )
            return ctx

        ctx.cultural_matrix = matrix
        self._record_and_persist(
            ctx,
            WorkflowState.CULTURAL_MATRIX_READY,
            reason="Multidimensional CulturalMatrix generated across 6 domains via MCP server",
            metadata={
                "total_recommendations": matrix.total_recommendations,
                "artists": len(matrix.artists),
                "brands": len(matrix.brands),
                "places": len(matrix.places),
            },
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 5 - Run Deterministic Agents & Generate Plan
    # Flow: Bounded Retries -> FAILED
    # -------------------------------------------------------------------------
    async def run_agents_and_generate_plan(
        self, ctx: WorkflowContext
    ) -> WorkflowContext:
        """Transitions CULTURAL_MATRIX_READY -> AGENTS_RUNNING -> PLAN_GENERATED with bounded retries."""
        validate_transition(ctx.current_state, WorkflowState.AGENTS_RUNNING)
        self._record_and_persist(
            ctx,
            WorkflowState.AGENTS_RUNNING,
            reason="Launching specialized domain agents",
        )

        if not ctx.cultural_twin or not ctx.cultural_matrix:
            raise RuntimeError(
                "Cannot run agents: CulturalTwin or CulturalMatrix is missing."
            )

        agents_succeeded = False
        last_error = None

        # Bounded Agent Retry Loop
        for attempt in range(self.max_agent_retries + 1):
            try:
                # 1. Cultural Strategist
                strategy_input = CulturalStrategyInput(
                    cultural_twin=ctx.cultural_twin,
                    cultural_matrix=ctx.cultural_matrix,
                )
                ctx.strategy_output = await self.strategist.execute(strategy_input)

                # 2. Experience Architect
                experience_input = ExperienceDesignInput(
                    cultural_twin=ctx.cultural_twin,
                    cultural_matrix=ctx.cultural_matrix,
                    strategy=ctx.strategy_output,
                )
                ctx.experience_output = await self.architect.execute(experience_input)

                # 3. Partnership Agent
                partnership_input = PartnershipInput(
                    cultural_twin=ctx.cultural_twin,
                    strategy=ctx.strategy_output,
                    experience_design=ctx.experience_output,
                    cultural_matrix=ctx.cultural_matrix,
                )
                ctx.partnership_output = await self.partnership.execute(
                    partnership_input
                )

                agents_succeeded = True
                break
            except Exception as exc:
                ctx.agent_retry_count += 1
                last_error = str(exc)
                logger.warning(
                    "Domain agent execution attempt %d failed: %s",
                    attempt + 1,
                    exc,
                )
                if attempt >= self.max_agent_retries:
                    break

        if not agents_succeeded:
            # Retries exhausted -> FAILED
            validate_transition(ctx.current_state, WorkflowState.FAILED)
            self._record_and_persist(
                ctx,
                WorkflowState.FAILED,
                reason=f"AGENT_FAILURE: Domain agents failed after {self.max_agent_retries} bounded retries",
                error=last_error,
            )
            ctx.error_message = (
                f"AGENT_FAILURE: Domain agents failed after {self.max_agent_retries} retries:"
                f" {last_error}"
            )
            return ctx

        # Transition to PLAN_GENERATED
        validate_transition(ctx.current_state, WorkflowState.PLAN_GENERATED)
        assert ctx.strategy_output is not None
        assert ctx.experience_output is not None
        assert ctx.partnership_output is not None

        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        empty_governance = GovernanceValidationInput(
            cultural_twin=ctx.cultural_twin,
            cultural_matrix=ctx.cultural_matrix,
            strategy=ctx.strategy_output,
            experience_design=ctx.experience_output,
            partnerships=ctx.partnership_output,
        )
        # 1. PLAN Phase: Generate structured ExecutionPlan
        execution_plan = self.governance.plan(empty_governance)

        # 2. Preliminary validation to construct plan
        gov_output = await self.governance.validate_plan(
            empty_governance, execution_plan=execution_plan
        )
        ctx.governance_output = gov_output

        ctx.plan = CulturalActivationPlan(
            plan_id=plan_id,
            cultural_twin=ctx.cultural_twin,
            cultural_matrix=ctx.cultural_matrix,
            strategy=ctx.strategy_output,
            experience_design=ctx.experience_output,
            partnerships=ctx.partnership_output,
            governance=ctx.governance_output,
            execution_plan=execution_plan,
        )
        ctx.sync_outputs()

        self._record_and_persist(
            ctx,
            WorkflowState.PLAN_GENERATED,
            reason="Synthesized agent outputs into structured CulturalActivationPlan",
            metadata={"plan_id": plan_id},
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 6 - Validate & Enter Approval Gate
    # Flow: Validation Failure -> PLAN_GENERATED (bounded cycles -> FAILED)
    # -------------------------------------------------------------------------
    async def validate_and_await_approval(
        self, ctx: WorkflowContext
    ) -> WorkflowContext:
        """Transitions PLAN_GENERATED -> VALIDATED -> AWAITING_APPROVAL.

        On validation failure:
        - If cycle count <= max_validation_cycles: transitions back to PLAN_GENERATED for refinement.
        - If cycle count > max_validation_cycles: transitions to FAILED.
        """
        validate_transition(ctx.current_state, WorkflowState.VALIDATED)

        if not ctx.plan or not ctx.cultural_twin or not ctx.cultural_matrix:
            raise RuntimeError("Cannot validate: Plan is missing.")
        if (
            not ctx.strategy_output
            or not ctx.experience_output
            or not ctx.partnership_output
        ):
            raise RuntimeError(
                "Cannot validate: One or more agent outputs are missing."
            )

        gov_input = GovernanceValidationInput(
            cultural_twin=ctx.cultural_twin,
            cultural_matrix=ctx.cultural_matrix,
            strategy=ctx.strategy_output,
            experience_design=ctx.experience_output,
            partnerships=ctx.partnership_output,
        )
        gov_output = await self.governance.validate_plan(
            gov_input, execution_plan=ctx.plan.execution_plan
        )
        ctx.governance_output = gov_output
        ctx.plan.governance = gov_output

        # Handle Validation Failure
        if not gov_output.is_valid:
            ctx.validation_cycle_count += 1
            if ctx.validation_cycle_count <= self.max_validation_cycles:
                # Validation failure -> loop back to PLAN_GENERATED with bounded limit!
                self._record_and_persist(
                    ctx,
                    WorkflowState.VALIDATED,
                    reason=(
                        f"Plan validation failed (cycle {ctx.validation_cycle_count}/{self.max_validation_cycles}): "
                        f"{'; '.join(gov_output.risk_flags)}"
                    ),
                    error="; ".join(gov_output.risk_flags),
                )
                logger.info(
                    "Validation failed. Looping back to PLAN_GENERATED for curatorial refinement (cycle %d/%d).",
                    ctx.validation_cycle_count,
                    self.max_validation_cycles,
                )
                validate_transition(ctx.current_state, WorkflowState.PLAN_GENERATED)
                self._record_and_persist(
                    ctx,
                    WorkflowState.PLAN_GENERATED,
                    reason=f"Regenerating plan after validation feedback: {'; '.join(gov_output.risk_flags)}",
                )
                ctx.plan.execution_plan = self.governance.plan(gov_input)
                return ctx
            else:
                # Bounded validation cycles exhausted -> FAILED
                self._record_and_persist(
                    ctx,
                    WorkflowState.VALIDATED,
                    reason=f"Validation cycles exhausted ({self.max_validation_cycles} cycles): {'; '.join(gov_output.risk_flags)}",
                    error="; ".join(gov_output.risk_flags),
                )
                validate_transition(ctx.current_state, WorkflowState.FAILED)
                self._record_and_persist(
                    ctx,
                    WorkflowState.FAILED,
                    reason=f"Plan failed validation after {self.max_validation_cycles} corrective cycles: {'; '.join(gov_output.risk_flags)}",
                    error="; ".join(gov_output.risk_flags),
                )
                ctx.error_message = f"VALIDATION_FAILURE: Validation cycles exhausted ({self.max_validation_cycles} cycles): {'; '.join(gov_output.risk_flags)}"
                return ctx

        # Validation Passed -> VALIDATED
        self._record_and_persist(
            ctx,
            WorkflowState.VALIDATED,
            reason="Plan passed all provenance and constraint audits",
            metadata={"provenance_verified": gov_output.provenance_verified},
        )

        # Transition to AWAITING_APPROVAL (Deterministic human approval gate)
        validate_transition(ctx.current_state, WorkflowState.AWAITING_APPROVAL)
        self._record_and_persist(
            ctx,
            WorkflowState.AWAITING_APPROVAL,
            reason="Engine paused at approval gate. Waiting for human curator sign-off.",
        )
        ctx.sync_outputs()
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 7 - Human Sign-off (Approve or Reject)
    # -------------------------------------------------------------------------
    async def approve_plan(
        self, ctx: WorkflowContext, approver: str = "human_curator"
    ) -> WorkflowContext:
        """Transitions AWAITING_APPROVAL -> APPROVED with cryptographic plan binding."""
        validate_transition(ctx.current_state, WorkflowState.APPROVED)

        if not ctx.plan:
            raise RuntimeError("Cannot approve: Plan is missing.")

        plan_hash = ctx.plan.compute_hash()
        approval_rec = ApprovalRecord(
            session_id=ctx.session_id,
            plan_id=ctx.plan.plan_id,
            plan_version=ctx.plan.version,
            plan_hash=plan_hash,
            approver=approver,
            approved_at=datetime.now(UTC),
            is_valid=True,
        )
        ctx.approval = approval_rec

        self._record_and_persist(
            ctx,
            WorkflowState.APPROVED,
            reason=f"Plan approved by authorized curator: {approver}",
            metadata={
                "approver": approver,
                "plan_id": ctx.plan.plan_id,
                "plan_version": ctx.plan.version,
                "plan_hash": plan_hash,
            },
        )
        ctx.sync_outputs()
        return ctx

    async def reject_plan(
        self, ctx: WorkflowContext, reason: str = "Curator rejected plan"
    ) -> WorkflowContext:
        """Transitions AWAITING_APPROVAL -> FAILED."""
        validate_transition(ctx.current_state, WorkflowState.FAILED)

        if ctx.approval:
            ctx.approval.is_valid = False
            ctx.approval.invalidation_reason = f"Rejected: {reason}"

        self._record_and_persist(
            ctx,
            WorkflowState.FAILED,
            reason=f"Plan rejected by curator: {reason}",
            metadata={"rejection_reason": reason},
            error=reason,
        )
        ctx.error_message = reason
        ctx.sync_outputs()
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 8 - Execute and Complete
    # -------------------------------------------------------------------------
    async def execute_plan(self, ctx: WorkflowContext) -> WorkflowContext:
        """Transitions APPROVED -> EXECUTING -> COMPLETED."""
        validate_transition(ctx.current_state, WorkflowState.EXECUTING)
        self._record_and_persist(
            ctx,
            WorkflowState.EXECUTING,
            reason="Governance agent dispatching execution tasks",
        )

        if not ctx.plan:
            raise RuntimeError("Cannot execute: Plan is missing.")

        # Verify explicit approval record is present
        if not ctx.approval and not any(
            record.to_state == WorkflowState.APPROVED for record in ctx.history
        ):
            raise UnapprovedExecutionError(
                "Execution blocked: Plan has not been approved (approval record is absent)."
            )

        # Identify approver from approval record or audit history
        last_approver = ctx.approval.approver if ctx.approval else "curator"
        if not ctx.approval:
            for record in reversed(ctx.history):
                if (
                    record.to_state == WorkflowState.APPROVED
                    and "approver" in record.metadata
                ):
                    last_approver = record.metadata["approver"]
                    break

        execution_summary = await self.governance.execute_plan(
            ctx.plan,
            is_approved=True,
            approved_by=last_approver,
            approval=ctx.approval,
            session_id=ctx.session_id,
        )
        ctx.plan.execution_summary = execution_summary
        ctx.execution_tasks = execution_summary.tasks
        ctx.sync_outputs()

        validate_transition(ctx.current_state, WorkflowState.COMPLETED)
        self._record_and_persist(
            ctx,
            WorkflowState.COMPLETED,
            reason="All downstream activation tasks confirmed with provenance",
            metadata={
                "total_tasks": execution_summary.total_tasks,
                "executed_tasks": execution_summary.executed_tasks,
            },
        )
        return ctx

    # -------------------------------------------------------------------------
    # Full Pipeline Helper: Up to Human Gate
    # -------------------------------------------------------------------------
    async def run_pipeline_to_approval_gate(
        self,
        raw_intent: str,
        parsed_hints: dict[str, Any] | None = None,
        space_id: str | None = None,
        take_per_category: int = 10,
    ) -> WorkflowContext:
        """Executes workflow deterministically from CREATED to AWAITING_APPROVAL."""
        ctx = self.initialize_session(raw_intent, parsed_hints, space_id=space_id)
        await self.parse_intent(ctx)
        if ctx.current_state == WorkflowState.FAILED:
            return ctx

        await self.create_cultural_twin(ctx)
        if ctx.current_state == WorkflowState.FAILED:
            return ctx

        await self.resolve_qloo_anchors(ctx)
        if ctx.current_state == WorkflowState.FAILED:
            return ctx

        await self.fetch_cultural_matrix(ctx, take_per_category=take_per_category)
        if ctx.current_state == WorkflowState.FAILED:
            return ctx

        await self.run_agents_and_generate_plan(ctx)
        if ctx.current_state == WorkflowState.FAILED:
            return ctx

        # Bounded validation loop: if validation fails, loops to PLAN_GENERATED
        while (
            ctx.current_state == WorkflowState.PLAN_GENERATED
            and ctx.validation_cycle_count <= self.max_validation_cycles
        ):
            await self.validate_and_await_approval(ctx)
            if ctx.current_state in {
                WorkflowState.AWAITING_APPROVAL,
                WorkflowState.FAILED,
            }:
                break

        return ctx
