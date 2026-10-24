"""Unit tests for EntityResolver and TagResolver."""

import httpx
import pytest
import respx

from tasteops.client import QlooClient
from tasteops.services.entity_resolver import EntityResolver
from tasteops.services.tag_resolver import TagResolver


@pytest.mark.asyncio
async def test_resolve_entity_with_whitespace_and_exact_match(mock_settings):
    """Test ' A24 ' normalizes whitespace and resolves with exact match and provenance."""
    mock_payload = {
        "results": [
            {
                "id": "ent_a24_film",
                "name": "A24",
                "type": "brand",
                "urn": "urn:entity:brand:a24",
                "tags": ["indie-film", "production", "entertainment"],
            },
            {
                "id": "ent_a24_other",
                "name": "A24 Music",
                "type": "brand",
            },
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_payload)

        async with QlooClient(settings=mock_settings) as client:
            resolver = EntityResolver(client)
            result = await resolver.resolve(" A24 ")

            assert result.is_resolved is True
            assert result.input == " A24 "
            assert result.resolved_entity_id == "ent_a24_film"
            assert result.entity_type == "brand"
            assert result.confidence == 1.0
            assert result.source == "qloo_search"

            # Check provenance and evidence
            assert result.evidence.raw_query == " A24 "
            assert result.evidence.normalized_query == "A24"
            assert result.evidence.match_method == "exact_match"
            assert result.evidence.score == 1.0

            # Check preserved alternatives
            assert len(result.alternatives) == 1
            assert result.alternatives[0].entity.id == "ent_a24_other"
            assert result.alternatives[0].confidence < 1.0


@pytest.mark.asyncio
async def test_resolve_entity_arctic_monkeys_token_match(mock_settings):
    """Test 'Arctic Monkeys' resolves with high confidence and alternative preservation."""
    mock_payload = {
        "results": [
            {
                "id": "ent_arctic_monkeys",
                "name": "Arctic Monkeys",
                "type": "artist",
                "urn": "urn:entity:artist:arctic_monkeys",
                "tags": ["indie-rock", "post-punk-revival", "british"],
            },
            {
                "id": "ent_the_monkeys",
                "name": "The Monkees",
                "type": "artist",
            },
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_payload)

        async with QlooClient(settings=mock_settings) as client:
            resolver = EntityResolver(client)
            result = await resolver.resolve("Arctic Monkeys", expected_type="artist")

            assert result.is_resolved is True
            assert result.resolved_entity_id == "ent_arctic_monkeys"
            assert result.entity_type == "artist"
            assert result.confidence >= 0.95
            assert len(result.alternatives) == 1
            assert result.alternatives[0].entity.name == "The Monkees"


@pytest.mark.asyncio
async def test_resolve_entity_never_invents_id_on_empty(mock_settings):
    """Safety check: When Qloo returns 0 results, the resolver NEVER fabricates an ID."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json={"results": []})

        async with QlooClient(settings=mock_settings) as client:
            resolver = EntityResolver(client)
            result = await resolver.resolve("completely_unknown_fictional_place_98765")

            assert result.is_resolved is False
            assert result.resolved_entity_id is None
            assert result.confidence == 0.0
            assert result.entity is None
            assert result.alternatives == []
            assert result.evidence.match_method == "unresolved_no_results"


@pytest.mark.asyncio
async def test_resolve_entity_rejects_sub_threshold_fuzzy(mock_settings):
    """Safety check: Sub-threshold candidate matches are rejected and ID is not assigned."""
    mock_payload = {
        "results": [
            {
                "id": "ent_unrelated_pizza",
                "name": "Luigi's Pizza",
                "type": "place",
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_payload)

        async with QlooClient(settings=mock_settings) as client:
            resolver = EntityResolver(client)
            # High threshold of 0.8; "Starbucks" vs "Luigi's Pizza" is well below 0.8
            result = await resolver.resolve("Starbucks", min_confidence=0.8)

            assert result.is_resolved is False
            assert result.resolved_entity_id is None
            assert result.confidence == 0.0
            # Candidate is preserved in alternatives for manual review, but not accepted
            assert len(result.alternatives) == 1
            assert result.evidence.match_method == "rejected_below_confidence"


@pytest.mark.asyncio
async def test_resolve_tag_japanese_minimalism(mock_settings):
    """Test resolving 'Japanese minimalism' to valid tag ID and metadata."""
    mock_payload = {
        "results": [
            {
                "id": "tag_jp_minimalism",
                "name": "Japanese Minimalism",
                "category": "style",
                "urn": "urn:tag:style:japanese_minimalism",
                "metadata": {"origin": "Japan", "aesthetic": "wabi-sabi"},
            },
            {
                "id": "tag_scandi_minimalism",
                "name": "Scandinavian Minimalism",
                "category": "style",
            },
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_payload)

        async with QlooClient(settings=mock_settings) as client:
            resolver = TagResolver(client)
            result = await resolver.resolve("Japanese minimalism")

            assert result.is_resolved is True
            assert result.resolved_tag_id == "tag_jp_minimalism"
            assert result.tag_name == "Japanese Minimalism"
            assert result.category == "style"
            assert result.confidence == 1.0
            assert result.source == "qloo_tags"
            assert result.tag.metadata["aesthetic"] == "wabi-sabi"
            assert len(result.alternatives) == 1


@pytest.mark.asyncio
async def test_resolve_tag_indie_cinema_and_indian_design(mock_settings):
    """Test resolving 'indie cinema' and 'contemporary Indian design'."""
    tag_responses = {
        "indie cinema": {
            "results": [
                {
                    "id": "tag_indie_cinema",
                    "name": "Indie Cinema",
                    "category": "entertainment",
                    "urn": "urn:tag:entertainment:indie_cinema",
                }
            ]
        },
        "contemporary Indian design": {
            "results": [
                {
                    "id": "tag_contemp_indian_design",
                    "name": "Contemporary Indian Design",
                    "category": "design",
                    "urn": "urn:tag:design:contemporary_indian",
                }
            ]
        },
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        def tag_side_effect(request):
            query = request.url.params.get("query", "")
            if "indie" in query:
                return httpx.Response(200, json=tag_responses["indie cinema"])
            return httpx.Response(200, json=tag_responses["contemporary Indian design"])

        mock_router.get("/v2/tags").mock(side_effect=tag_side_effect)

        async with QlooClient(settings=mock_settings) as client:
            resolver = TagResolver(client)

            res1 = await resolver.resolve("indie cinema")
            assert res1.is_resolved is True
            assert res1.resolved_tag_id == "tag_indie_cinema"
            assert res1.category == "entertainment"

            res2 = await resolver.resolve("contemporary Indian design")
            assert res2.is_resolved is True
            assert res2.resolved_tag_id == "tag_contemp_indian_design"
            assert res2.category == "design"


@pytest.mark.asyncio
async def test_reject_unknown_tags_never_invents_id(mock_settings):
    """Safety check: Unknown tags are rejected and never fabricated."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/tags").respond(status_code=200, json={"results": []})

        async with QlooClient(settings=mock_settings) as client:
            resolver = TagResolver(client)
            result = await resolver.resolve("completely_unknown_fictional_tag_xyz")

            assert result.is_resolved is False
            assert result.resolved_tag_id is None
            assert result.tag_name is None
            assert result.confidence == 0.0
            assert result.tag is None
            assert result.evidence.match_method == "rejected_unknown_tag"


@pytest.mark.asyncio
async def test_resolve_batch(mock_settings):
    """Test resolving a batch of cultural anchors."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(
            status_code=200,
            json={
                "results": [
                    {"id": "ent_1", "name": "A24", "type": "brand"},
                ]
            },
        )

        async with QlooClient(settings=mock_settings) as client:
            resolver = EntityResolver(client)
            batch_results = await resolver.resolve_batch(["A24", "A24"])
            assert len(batch_results) == 2
            assert batch_results[0].resolved_entity_id == "ent_1"
            assert batch_results[1].resolved_entity_id == "ent_1"
