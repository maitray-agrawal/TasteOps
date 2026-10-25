"""TasteOps Space and SpaceBrief Repository.

Provides relational persistence for physical venue spaces and their associated briefs.
"""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from tasteops.api.schemas.spaces import SpaceCreateRequest, SpaceResponse
from tasteops.persistence.database import Database

logger = logging.getLogger("tasteops.persistence.space_repo")


class BaseSpaceRepository(ABC):
    """Abstract interface for Space and SpaceBrief persistence."""

    @abstractmethod
    def save_space(
        self,
        request: SpaceCreateRequest,
        space_id: str | None = None,
    ) -> SpaceResponse:
        """Persists a space and its brief atomically."""

    @abstractmethod
    def get_space(self, space_id: str) -> SpaceResponse | None:
        """Retrieves a space and its brief by ID."""

    @abstractmethod
    def list_spaces(self) -> list[SpaceResponse]:
        """Lists all registered physical spaces."""

    @abstractmethod
    def delete_space(self, space_id: str) -> bool:
        """Deletes a space and cascades to its brief and sessions."""


class SQLiteSpaceRepository(BaseSpaceRepository):
    """Relational SQLite implementation of BaseSpaceRepository."""

    def __init__(self, database: Database) -> None:
        self.db = database

    def save_space(
        self,
        request: SpaceCreateRequest,
        space_id: str | None = None,
    ) -> SpaceResponse:
        """Persists a space and its brief in a single atomic transaction."""
        s_id = space_id or f"space_{uuid.uuid4().hex[:12]}"
        brief_id = f"brief_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()

        location_json = json.dumps(request.location) if request.location is not None else None
        metadata_json = json.dumps(request.metadata)
        constraints_json = json.dumps(request.constraints or [])
        anchors_json = json.dumps(request.anchor_entities or [])

        with self.db.transaction() as cursor:
            # 1. Insert or update Space
            cursor.execute(
                """
                INSERT INTO spaces (space_id, name, business_type, location_json, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(space_id) DO UPDATE SET
                    name = excluded.name,
                    business_type = excluded.business_type,
                    location_json = excluded.location_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at;
                """,
                (s_id, request.name, request.business_type, location_json, metadata_json, now, now),
            )

            # 2. Insert or update SpaceBrief
            cursor.execute(
                """
                INSERT INTO space_briefs (
                    brief_id, space_id, target_audience, positioning, desired_mood,
                    budget, constraints_json, anchor_entities_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(space_id) DO UPDATE SET
                    target_audience = excluded.target_audience,
                    positioning = excluded.positioning,
                    desired_mood = excluded.desired_mood,
                    budget = excluded.budget,
                    constraints_json = excluded.constraints_json,
                    anchor_entities_json = excluded.anchor_entities_json,
                    updated_at = excluded.updated_at;
                """,
                (
                    brief_id,
                    s_id,
                    request.target_audience,
                    request.positioning,
                    request.desired_mood,
                    request.budget,
                    constraints_json,
                    anchors_json,
                    now,
                    now,
                ),
            )

        brief_dict: dict[str, Any] = {
            "business_type": request.business_type,
            "location": request.location,
            "target_audience": request.target_audience,
            "positioning": request.positioning,
            "desired_mood": request.desired_mood,
            "budget": request.budget,
            "constraints": request.constraints or [],
            "anchor_entities": request.anchor_entities or [],
        }

        return SpaceResponse(
            space_id=s_id,
            name=request.name,
            business_type=request.business_type,
            location=request.location,
            brief=brief_dict,
            metadata=request.metadata,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def get_space(self, space_id: str) -> SpaceResponse | None:
        """Retrieves a space joining with its brief."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    s.space_id, s.name, s.business_type, s.location_json, s.metadata_json,
                    s.created_at, s.updated_at,
                    b.target_audience, b.positioning, b.desired_mood, b.budget,
                    b.constraints_json, b.anchor_entities_json
                FROM spaces s
                LEFT JOIN space_briefs b ON s.space_id = b.space_id
                WHERE s.space_id = ?;
                """,
                (space_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            location = json.loads(row["location_json"]) if row["location_json"] else None
            metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            constraints = json.loads(row["constraints_json"]) if row["constraints_json"] else []
            anchors = json.loads(row["anchor_entities_json"]) if row["anchor_entities_json"] else []

            brief_dict: dict[str, Any] = {
                "business_type": row["business_type"],
                "location": location,
                "target_audience": row["target_audience"],
                "positioning": row["positioning"],
                "desired_mood": row["desired_mood"],
                "budget": row["budget"],
                "constraints": constraints,
                "anchor_entities": anchors,
            }

            return SpaceResponse(
                space_id=row["space_id"],
                name=row["name"],
                business_type=row["business_type"],
                location=location,
                brief=brief_dict,
                metadata=metadata,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        finally:
            cursor.close()

    def list_spaces(self) -> list[SpaceResponse]:
        """Lists all spaces ordered by creation date descending."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    s.space_id, s.name, s.business_type, s.location_json, s.metadata_json,
                    s.created_at, s.updated_at,
                    b.target_audience, b.positioning, b.desired_mood, b.budget,
                    b.constraints_json, b.anchor_entities_json
                FROM spaces s
                LEFT JOIN space_briefs b ON s.space_id = b.space_id
                ORDER BY s.created_at DESC;
                """
            )
            rows = cursor.fetchall()
            spaces: list[SpaceResponse] = []
            for row in rows:
                loc = json.loads(row["location_json"]) if row["location_json"] else None
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                constraints = json.loads(row["constraints_json"]) if row["constraints_json"] else []
                anchors = json.loads(row["anchor_entities_json"]) if row["anchor_entities_json"] else []

                brief_dict: dict[str, Any] = {
                    "business_type": row["business_type"],
                    "location": loc,
                    "target_audience": row["target_audience"],
                    "positioning": row["positioning"],
                    "desired_mood": row["desired_mood"],
                    "budget": row["budget"],
                    "constraints": constraints,
                    "anchor_entities": anchors,
                }

                spaces.append(
                    SpaceResponse(
                        space_id=row["space_id"],
                        name=row["name"],
                        business_type=row["business_type"],
                        location=loc,
                        brief=brief_dict,
                        metadata=meta,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                )
            return spaces
        finally:
            cursor.close()

    def delete_space(self, space_id: str) -> bool:
        """Deletes a space by ID. Cascades to briefs and associated child records."""
        with self.db.transaction() as cursor:
            cursor.execute("DELETE FROM spaces WHERE space_id = ?;", (space_id,))
            return cursor.rowcount > 0
