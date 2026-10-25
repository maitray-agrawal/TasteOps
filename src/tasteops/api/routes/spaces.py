"""TasteOps API Space Management Routes.

Provides endpoints to register physical spaces, retrieve space profiles,
and trigger cultural intelligence analyses.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from tasteops.api.dependencies import ServiceDep
from tasteops.api.routes.sessions import format_session_detail
from tasteops.api.schemas.sessions import SessionDetailResponse
from tasteops.api.schemas.spaces import (
    AnalyzeSpaceRequest,
    SpaceCreateRequest,
    SpaceResponse,
)

router = APIRouter(prefix="/spaces", tags=["Spaces"])


@router.post(
    "",
    response_model=SpaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Physical Space",
    description="Registers a new physical venue space with initial architectural and audience brief parameters.",
)
async def create_space(
    request: SpaceCreateRequest,
    service: ServiceDep,
    response: Response,
) -> SpaceResponse:
    space = service.create_space(request)
    response.headers["Location"] = f"/api/v1/spaces/{space.space_id}"
    return space


@router.get(
    "/{space_id}",
    response_model=SpaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Space Profile",
    description="Retrieves a registered physical space profile by its unique identifier.",
    responses={404: {"description": "Space not found"}},
)
async def get_space(space_id: str, service: ServiceDep) -> SpaceResponse:
    return service.get_space(space_id)


@router.post(
    "/{space_id}/analyze",
    response_model=SessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Physical Space",
    description=(
        "Triggers end-to-end cultural intelligence analysis for the space. "
        "Initializes a deterministic workflow session, translates the space brief into "
        "cultural anchors, fetches Qloo cultural affinities, generates sensory blueprint, "
        "and validates compliance up to the Human Approval Gate."
    ),
    responses={
        404: {"description": "Space not found"},
        409: {"description": "Workflow state conflict or invalid transition"},
    },
)
async def analyze_space(
    space_id: str,
    request: AnalyzeSpaceRequest | None = None,
    service: ServiceDep = None,  # type: ignore[assignment]
) -> SessionDetailResponse:
    req = request or AnalyzeSpaceRequest()
    ctx = await service.analyze_space(space_id=space_id, request=req)
    return format_session_detail(ctx)
