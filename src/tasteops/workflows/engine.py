"""TasteOps Workflow Engine.

Orchestrates deterministic state transitions for physical space cultural activations:
CREATED -> INTENT_PARSED -> CULTURAL_TWIN_CREATED -> QLOO_RESOLVED ->
CULTURAL_MATRIX_READY -> AGENTS_RUNNING -> PLAN_GENERATED -> VALIDATED ->
AWAITING_APPROVAL -> APPROVED -> EXECUTING -> COMPLETED (or FAILED).

Guarantees:
- Never makes direct Qloo REST API calls; all cultural data is requested via MCP tools.
- Strict state transition validation with zero unrestricted loops.
- Enforces human approval boundary at AWAITING_APPROVAL before execution.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from tasteops.models.cultural_matrix import (
    CulturalTwin,
    LocationInput,
    PhysicalSpaceBrief,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.schemas import (
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

    # -------------------------------------------------------------------------
    # Transition: Step 1 - Initialize and Parse Intent
    # -------------------------------------------------------------------------
    def initialize_session(
        self, raw_intent: str, parsed_hints: dict[str, Any] | None = None
    ) -> WorkflowContext:
        """Creates a fresh session in CREATED state."""
        ctx = WorkflowContext(raw_intent=raw_intent, parsed_intent=parsed_hints or {})
        ctx.record_transition(
            WorkflowState.CREATED, reason="Session initialized with raw intent"
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

        ctx.record_transition(
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

        ctx.record_transition(
            WorkflowState.CULTURAL_TWIN_CREATED,
            reason="Initial CulturalTwin instantiated; anchors and tags pending Qloo resolution",
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 3 - Resolve Cultural Anchors via MCP
    # -------------------------------------------------------------------------
    async def resolve_qloo_anchors(self, ctx: WorkflowContext) -> WorkflowContext:
        """Transitions CULTURAL_TWIN_CREATED -> QLOO_RESOLVED via MCP server."""
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

        ctx.cultural_twin = await self.strategist.transform_brief(brief)

        ctx.record_transition(
            WorkflowState.QLOO_RESOLVED,
            reason="Cultural anchors and aesthetic tags resolved through Cultural Intelligence MCP server",
            metadata={
                "resolved_entities_count": len(ctx.cultural_twin.resolved_entities),
                "resolved_tags_count": len(ctx.cultural_twin.resolved_tags),
                "entity_ids": ctx.cultural_twin.resolved_entity_ids,
                "tag_ids": ctx.cultural_twin.resolved_tags,
            },
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 4 - Fetch Cultural Matrix via MCP
    # -------------------------------------------------------------------------
    async def fetch_cultural_matrix(
        self, ctx: WorkflowContext, take_per_category: int = 10
    ) -> WorkflowContext:
        """Transitions QLOO_RESOLVED -> CULTURAL_MATRIX_READY via MCP server."""
        validate_transition(ctx.current_state, WorkflowState.CULTURAL_MATRIX_READY)

        if not ctx.cultural_twin:
            raise RuntimeError("Cannot fetch CulturalMatrix: CulturalTwin is missing.")

        matrix = await self.mcp.get_cultural_matrix(
            twin=ctx.cultural_twin,
            take_per_category=take_per_category,
        )
        ctx.cultural_matrix = matrix

        ctx.record_transition(
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
    # -------------------------------------------------------------------------
    async def run_agents_and_generate_plan(
        self, ctx: WorkflowContext
    ) -> WorkflowContext:
        """Transitions CULTURAL_MATRIX_READY -> AGENTS_RUNNING -> PLAN_GENERATED."""
        validate_transition(ctx.current_state, WorkflowState.AGENTS_RUNNING)
        ctx.record_transition(
            WorkflowState.AGENTS_RUNNING, reason="Launching specialized domain agents"
        )

        if not ctx.cultural_twin or not ctx.cultural_matrix:
            raise RuntimeError(
                "Cannot run agents: CulturalTwin or CulturalMatrix is missing."
            )

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
        ctx.partnership_output = await self.partnership.execute(partnership_input)

        # Transition to PLAN_GENERATED
        validate_transition(ctx.current_state, WorkflowState.PLAN_GENERATED)

        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        # Governance will populate governance output next
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

        ctx.record_transition(
            WorkflowState.PLAN_GENERATED,
            reason="Synthesized agent outputs into structured CulturalActivationPlan",
            metadata={"plan_id": plan_id},
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 6 - Validate & Enter Approval Gate
    # -------------------------------------------------------------------------
    async def validate_and_await_approval(
        self, ctx: WorkflowContext
    ) -> WorkflowContext:
        """Transitions PLAN_GENERATED -> VALIDATED -> AWAITING_APPROVAL."""
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
        gov_output = await self.governance.validate_plan(gov_input)
        ctx.governance_output = gov_output
        ctx.plan.governance = gov_output

        if not gov_output.is_valid:
            ctx.record_transition(
                WorkflowState.FAILED,
                reason=f"Plan validation failed: {gov_output.risk_flags}",
            )
            ctx.error_message = "; ".join(gov_output.risk_flags)
            return ctx

        ctx.record_transition(
            WorkflowState.VALIDATED,
            reason="Plan passed all provenance and constraint audits",
            metadata={"provenance_verified": gov_output.provenance_verified},
        )

        # Transition to AWAITING_APPROVAL (Deterministic human approval gate)
        validate_transition(ctx.current_state, WorkflowState.AWAITING_APPROVAL)
        ctx.record_transition(
            WorkflowState.AWAITING_APPROVAL,
            reason="Engine paused at approval gate. Waiting for human curator sign-off.",
        )
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 7 - Human Sign-off (Approve or Reject)
    # -------------------------------------------------------------------------
    async def approve_plan(
        self, ctx: WorkflowContext, approver: str = "human_curator"
    ) -> WorkflowContext:
        """Transitions AWAITING_APPROVAL -> APPROVED."""
        validate_transition(ctx.current_state, WorkflowState.APPROVED)

        ctx.record_transition(
            WorkflowState.APPROVED,
            reason=f"Plan approved by authorized curator: {approver}",
            metadata={"approver": approver},
        )
        return ctx

    async def reject_plan(
        self, ctx: WorkflowContext, reason: str = "Curator rejected plan"
    ) -> WorkflowContext:
        """Transitions AWAITING_APPROVAL -> FAILED."""
        validate_transition(ctx.current_state, WorkflowState.FAILED)

        ctx.record_transition(
            WorkflowState.FAILED,
            reason=f"Plan rejected by curator: {reason}",
            metadata={"rejection_reason": reason},
        )
        ctx.error_message = reason
        return ctx

    # -------------------------------------------------------------------------
    # Transition: Step 8 - Execute and Complete
    # -------------------------------------------------------------------------
    async def execute_plan(self, ctx: WorkflowContext) -> WorkflowContext:
        """Transitions APPROVED -> EXECUTING -> COMPLETED."""
        validate_transition(ctx.current_state, WorkflowState.EXECUTING)
        ctx.record_transition(
            WorkflowState.EXECUTING,
            reason="Governance agent dispatching execution tasks",
        )

        if not ctx.plan:
            raise RuntimeError("Cannot execute: Plan is missing.")

        # Identify approver from audit history
        last_approver = "curator"
        for record in reversed(ctx.history):
            if (
                record.to_state == WorkflowState.APPROVED
                and "approver" in record.metadata
            ):
                last_approver = record.metadata["approver"]
                break

        execution_summary = await self.governance.execute_plan(
            ctx.plan, is_approved=True, approved_by=last_approver
        )
        ctx.plan.execution_summary = execution_summary

        validate_transition(ctx.current_state, WorkflowState.COMPLETED)
        ctx.record_transition(
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
        take_per_category: int = 10,
    ) -> WorkflowContext:
        """Executes workflow deterministically from CREATED to AWAITING_APPROVAL."""
        ctx = self.initialize_session(raw_intent, parsed_hints)
        await self.parse_intent(ctx)
        await self.create_cultural_twin(ctx)
        await self.resolve_qloo_anchors(ctx)
        await self.fetch_cultural_matrix(ctx, take_per_category=take_per_category)
        await self.run_agents_and_generate_plan(ctx)
        await self.validate_and_await_approval(ctx)
        return ctx
