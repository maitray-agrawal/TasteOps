"""TasteOps API Space Management Routes.

Provides endpoints to register physical spaces, retrieve space profiles,
and trigger cultural intelligence analyses.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Path, Response, status

from tasteops.api.dependencies import AuthDep, ServiceDep
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
    _actor: AuthDep = "dev-curator",
) -> SpaceResponse:
    space = service.create_space(request)
    response.headers["Location"] = f"/api/v1/spaces/{space.space_id}"
    return space


@router.get(
    "",
    response_model=list[SpaceResponse],
    status_code=status.HTTP_200_OK,
    summary="List Physical Spaces",
    description="Lists all registered physical venue spaces ordered by creation date descending.",
)
async def list_spaces(service: ServiceDep) -> list[SpaceResponse]:
    return service.list_spaces()


@router.get(
    "/{space_id}",
    response_model=SpaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Space Profile",
    description="Retrieves a registered physical space profile by its unique identifier.",
    responses={404: {"description": "Space not found"}},
)
async def get_space(
    space_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
) -> SpaceResponse:
    return service.get_space(space_id)


@router.delete(
    "/{space_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Space Profile",
    description="Deletes a registered physical space profile and its associated briefs.",
    responses={404: {"description": "Space not found"}},
)
async def delete_space(
    space_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
    _actor: AuthDep = "dev-curator",
) -> dict[str, Any]:

    # Verify space exists
    service.get_space(space_id)
    if service.space_repo:
        service.space_repo.delete_space(space_id)
    elif space_id in getattr(service, "_spaces", {}):
        del service._spaces[space_id]
    return {"deleted": True, "space_id": space_id}


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
    space_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    request: AnalyzeSpaceRequest | None = None,
    service: ServiceDep = None,  # type: ignore[assignment]
    _actor: AuthDep = "dev-curator",
) -> SessionDetailResponse:
    req = request or AnalyzeSpaceRequest()
    ctx = await service.analyze_space(space_id=space_id, request=req)
    return format_session_detail(ctx)
