"""Pytest fixtures and configuration for TasteOps unit tests."""

import pytest

from tasteops.config import QlooSettings


@pytest.fixture
def mock_settings():
    """Provides test settings with mock API key and rapid retries."""
    return QlooSettings(
        QLOO_API_KEY="test_mock_qloo_api_key_12345",
        QLOO_BASE_URL="https://hackathon.api.qloo.com",
        QLOO_TIMEOUT_SECONDS=2.0,
        QLOO_MAX_RETRIES=2,
        QLOO_RETRY_BACKOFF_FACTOR=0.01,
        QLOO_CACHE_ENABLED=False,
    )


@pytest.fixture
def sample_search_payload():
    return {
        "results": [
            {
                "id": "ent_blue_bottle_123",
                "name": "Blue Bottle Coffee",
                "type": "place",
                "subtype": "cafe",
                "urn": "urn:entity:place:cafe",
                "tags": ["specialty-coffee", "minimalist", "craft"],
                "metadata": {"city": "New York", "neighborhood": "Chelsea"},
            },
            {
                "id": "ent_stumptown_456",
                "name": "Stumptown Coffee Roasters",
                "type": "place",
                "subtype": "cafe",
                "tags": [{"name": "cold-brew"}, {"name": "portland"}],
                "metadata": {"city": "New York"},
            },
        ]
    }


@pytest.fixture
def sample_tags_payload():
    return {
        "results": [
            {
                "id": "tag_lofi_beats",
                "name": "Lo-Fi Beats",
                "category": "music",
                "urn": "urn:tag:music:genre:lofi",
            },
            {
                "id": "tag_artisan_pastry",
                "name": "Artisan Pastry",
                "category": "dining",
                "urn": "urn:tag:dining:artisan",
            },
        ]
    }


@pytest.fixture
def sample_insights_payload():
    return {
        "results": [
            {
                "id": "ent_four_tet",
                "name": "Four Tet",
                "type": "urn:entity:artist",
                "affinity": 0.94,
                "score": 94.0,
                "explainability": ["Audience overlap with Blue Bottle Coffee patrons"],
            },
            {
                "id": "ent_aesop",
                "name": "Aesop",
                "type": "urn:entity:brand",
                "affinity": 0.88,
                "score": 88.0,
                "explainability": ["Shared aesthetic and demographic affinity"],
            },
        ]
    }
