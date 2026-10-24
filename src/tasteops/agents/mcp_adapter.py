"""TasteOps MCP Client Adapter.

Ensures Developer 2 agents NEVER make direct Qloo REST API calls.
All cultural intelligence is strictly retrieved by invoking the TasteOps
Cultural Intelligence MCP server via standard MCP tool calls.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from tasteops.mcp.server import create_cultural_intelligence_mcp
from tasteops.models.cultural_matrix import CulturalMatrix, CulturalTwin


class CulturalIntelligenceMCPAdapter:
    """Async adapter wrapping tool invocations on the TasteOps Cultural Intelligence MCPServer."""

    def __init__(self, server: MCPServer | None = None) -> None:
        self._server = server

    @property
    def server(self) -> MCPServer:
        if self._server is None:
            self._server = create_cultural_intelligence_mcp()
        return self._server

    async def call_mcp_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatches an MCP tool call through the MCP protocol layer."""
        result = await self.server.call_tool(tool_name, arguments)
        if not isinstance(result, CallToolResult):
            raise TypeError(
                f"Unexpected MCP response type for '{tool_name}': {type(result)}"
            )
        if result.is_error:
            raise RuntimeError(
                f"MCP tool '{tool_name}' failed with error: {result.content}"
            )
        if result.structured_content is not None and isinstance(
            result.structured_content, dict
        ):
            return result.structured_content
        # Fallback to text content if structured content is missing
        if result.content and hasattr(result.content[0], "text"):
            import json

            try:
                return json.loads(result.content[0].text)  # type: ignore[no-any-return]
            except Exception:
                return {"text": result.content[0].text}
        return {}

    async def resolve_entity(
        self, query: str, expected_type: str | None = None, min_confidence: float = 0.5
    ) -> dict[str, Any]:
        """Resolves natural language anchor via MCP tool 'resolve_entity'."""
        return await self.call_mcp_tool(
            "resolve_entity",
            {
                "query": query,
                "expected_type": expected_type,
                "min_confidence": min_confidence,
            },
        )

    async def resolve_tag(
        self,
        query: str,
        expected_category: str | None = None,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Resolves natural language tag via MCP tool 'resolve_tag'."""
        return await self.call_mcp_tool(
            "resolve_tag",
            {
                "query": query,
                "expected_category": expected_category,
                "min_confidence": min_confidence,
            },
        )

    async def get_cultural_profile(
        self,
        entity_id: str | None = None,
        entity_name: str | None = None,
        take: int = 5,
    ) -> dict[str, Any]:
        """Profiles an anchor entity via MCP tool 'get_cultural_profile'."""
        return await self.call_mcp_tool(
            "get_cultural_profile",
            {"entity_id": entity_id, "entity_name": entity_name, "take": take},
        )

    async def get_cultural_matrix(
        self, twin: CulturalTwin, take_per_category: int = 10
    ) -> CulturalMatrix:
        """Retrieves CulturalMatrix via MCP tool 'get_cultural_matrix'."""
        payload = await self.call_mcp_tool(
            "get_cultural_matrix",
            {
                "cultural_twin": twin.model_dump(),
                "take_per_category": take_per_category,
            },
        )
        if payload.get("status") == "error" or not payload.get("cultural_matrix"):
            raise RuntimeError(f"MCP get_cultural_matrix error: {payload.get('error')}")
        return CulturalMatrix.model_validate(payload["cultural_matrix"])

    async def get_related_artists(
        self, anchor_entities: list[str], resolved_tags: list[str], take: int = 10
    ) -> dict[str, Any]:
        """Fetches related music artists via MCP tool 'get_related_artists'."""
        return await self.call_mcp_tool(
            "get_related_artists",
            {
                "anchor_entities": anchor_entities,
                "resolved_tags": resolved_tags,
                "take": take,
            },
        )

    async def get_related_brands(
        self, anchor_entities: list[str], resolved_tags: list[str], take: int = 10
    ) -> dict[str, Any]:
        """Fetches related brands via MCP tool 'get_related_brands'."""
        return await self.call_mcp_tool(
            "get_related_brands",
            {
                "anchor_entities": anchor_entities,
                "resolved_tags": resolved_tags,
                "take": take,
            },
        )
