"""Deterministic Demo Fixture: Mumbai Contemporary Indian Luxury Boutique Hotel.

Represents a sanitized physical space brief and corresponding verified Qloo responses
explicitly tagged as `test_fixture_*` for deterministic orchestration tests.
"""

from typing import Any

from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
    LocationInput,
    ResolvedEntity,
    ResolvedTag,
)

# ---------------------------------------------------------------------------
# 1. Physical Space Brief & Hints
# ---------------------------------------------------------------------------

MUMBAI_DEMO_RAW_INTENT = (
    "Launch an intimate boutique hotel in Mumbai for affluent design-conscious "
    "professionals embodying contemporary Indian luxury with independent cinema, "
    "alternative music, and contemporary Indian design."
)

MUMBAI_DEMO_HINTS: dict[str, Any] = {
    "venue_name": "The Haveli Contemporary Mumbai",
    "business_type": "Boutique Hotel",
    "location": {
        "latitude": 18.9220,
        "longitude": 72.8347,
        "radius_meters": 5000,
    },
    "target_audience": "Affluent design-conscious professionals",
    "positioning": "Contemporary Indian luxury",
    "mood": "Sophisticated / intimate / creative",
    "raw_anchor_entities": [
        "Independent cinema",
        "Alternative music",
        "Contemporary Indian design",
    ],
    "raw_tags": [
        "Contemporary Indian design",
        "Independent cinema",
        "Alternative music",
    ],
    "budget": "$150,000 opening phase allocation",
    "constraints": {
        "acoustic_ceiling_db": 68,
        "zero_overt_commercial_branding": True,
        "materiality": "Local natural basalt stone, teak wood, handwoven textiles",
    },
}

# ---------------------------------------------------------------------------
# 2. Sanitized Mock API Responses (Explicitly marked as test fixtures)
# ---------------------------------------------------------------------------

MUMBAI_SEARCH_MOCK_RESPONSE: dict[str, Any] = {
    "results": [
        {
            "id": "test_fixture_ent_raw_mango",
            "name": "Raw Mango",
            "type": "brand",
            "popularity": 0.88,
        },
        {
            "id": "test_fixture_ent_prateek_kuhad",
            "name": "Prateek Kuhad",
            "type": "artist",
            "popularity": 0.92,
        },
        {
            "id": "test_fixture_ent_anand_gandhi",
            "name": "Anand Gandhi",
            "type": "artist",
            "popularity": 0.84,
        },
        {
            "id": "test_fixture_ent_subko_coffee",
            "name": "Subko Coffee Roasters",
            "type": "place",
            "popularity": 0.91,
        },
    ]
}

MUMBAI_TAGS_MOCK_RESPONSE: dict[str, Any] = {
    "results": [
        {
            "id": "test_fixture_tag_contemporary_indian_design",
            "name": "Contemporary Indian design",
            "category": "design",
        },
        {
            "id": "test_fixture_tag_indie_cinema",
            "name": "Independent cinema",
            "category": "film",
        },
        {
            "id": "test_fixture_tag_alternative_music",
            "name": "Alternative music",
            "category": "music",
        },
    ]
}

MUMBAI_INSIGHTS_MOCK_RESPONSE: dict[str, Any] = {
    "results": [
        {
            "id": "test_fixture_ent_prateek_kuhad",
            "name": "Prateek Kuhad",
            "type": "artist",
            "affinity": 0.94,
        },
        {
            "id": "test_fixture_ent_peter_cat_recording_co",
            "name": "Peter Cat Recording Co.",
            "type": "artist",
            "affinity": 0.91,
        },
        {
            "id": "test_fixture_ent_raw_mango",
            "name": "Raw Mango",
            "type": "brand",
            "affinity": 0.93,
        },
        {
            "id": "test_fixture_ent_kashmir_loom",
            "name": "Kashmir Loom",
            "type": "brand",
            "affinity": 0.89,
        },
        {
            "id": "test_fixture_ent_subko_coffee",
            "name": "Subko Specialty Coffee & Craft Bakehouse",
            "type": "place",
            "affinity": 0.95,
        },
        {
            "id": "test_fixture_ent_soho_house_mumbai",
            "name": "Soho House Mumbai",
            "type": "place",
            "affinity": 0.92,
        },
        {
            "id": "test_fixture_ent_the_god_of_small_things",
            "name": "The God of Small Things",
            "type": "book",
            "affinity": 0.88,
        },
        {
            "id": "test_fixture_ent_the_lunchbox",
            "name": "The Lunchbox",
            "type": "movie",
            "affinity": 0.90,
        },
    ]
}

# ---------------------------------------------------------------------------
# 3. Structured Model Fixtures
# ---------------------------------------------------------------------------


def get_mumbai_demo_twin() -> CulturalTwin:
    """Returns a deterministic CulturalTwin model for the Mumbai Boutique Hotel."""
    return CulturalTwin(
        business_type="Boutique Hotel",
        location=LocationInput(latitude=18.9220, longitude=72.8347, radius_meters=5000),
        target_audience="Affluent design-conscious professionals",
        positioning="Contemporary Indian luxury",
        mood="Sophisticated / intimate / creative",
        audience_profile=(
            "Cultured global and domestic travelers, architects, creators, and professionals "
            "seeking understated Indian materiality, literary depth, and bespoke acoustic calm."
        ),
        cultural_themes=[
            "Contemporary Indian Material Craft",
            "Independent New-Wave South Asian Cinema",
            "Intimate Analog & Acoustic Music Curation",
            "Specialty Third-Wave Regional Coffee & Culinary Heritage",
        ],
        mood_profile=(
            "Sophisticated, tactile, and quiet. Low indirect 2400K illumination with warm teak millwork, "
            "subtle scent of sandalwood and wet vetiver, and analog vinyl playback."
        ),
        anchor_entities=[
            "Independent cinema",
            "Alternative music",
            "Contemporary Indian design",
        ],
        resolved_entities=[
            ResolvedEntity(
                id="test_fixture_ent_raw_mango",
                name="Raw Mango",
                type="brand",
                confidence=0.96,
                why_it_matters="Pioneering contemporary Indian textile design and craft revivalism.",
            ),
            ResolvedEntity(
                id="test_fixture_ent_prateek_kuhad",
                name="Prateek Kuhad",
                type="artist",
                confidence=0.94,
                why_it_matters="Intimate acoustic songcraft resonating with cultured urban professionals.",
            ),
        ],
        resolved_tags=[
            "test_fixture_tag_contemporary_indian_design",
            "test_fixture_tag_indie_cinema",
            "test_fixture_tag_alternative_music",
        ],
        resolved_tag_details=[
            ResolvedTag(
                id="test_fixture_tag_contemporary_indian_design",
                name="Contemporary Indian design",
                why_it_matters="Grounds physical furniture and architectural detailing.",
            ),
            ResolvedTag(
                id="test_fixture_tag_indie_cinema",
                name="Independent cinema",
                why_it_matters="Informs cultural screening programming and narrative atmosphere.",
            ),
            ResolvedTag(
                id="test_fixture_tag_alternative_music",
                name="Alternative music",
                why_it_matters="Shapes morning and evening auditory landscape.",
            ),
        ],
        cultural_constraints=[
            "Acoustic decibel ceiling of 68dB in library and courtyard zones",
            "Zero overt corporate promotional banners or commercial signage",
            "100% locally sourced or regional artisanal tableware and amenities",
        ],
        exclusions=[
            "Mass-market commercial Bollywood club music",
            "Generic chain hospitality amenities",
            "Loud aggressive neon visual signage",
        ],
        confidence=0.95,
    )


def get_mumbai_demo_matrix() -> CulturalMatrix:
    """Returns a deterministic CulturalMatrix model for the Mumbai Boutique Hotel."""
    return CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="test_fixture_ent_prateek_kuhad",
                name="Prateek Kuhad",
                type="artist",
                affinity=0.94,
                source_query="/v2/insights",
                source_signal="Alternative music",
            ),
            CulturalRecommendation(
                id="test_fixture_ent_peter_cat_recording_co",
                name="Peter Cat Recording Co.",
                type="artist",
                affinity=0.91,
                source_query="/v2/insights",
                source_signal="Alternative music",
            ),
        ],
        brands=[
            CulturalRecommendation(
                id="test_fixture_ent_raw_mango",
                name="Raw Mango",
                type="brand",
                affinity=0.93,
                source_query="/v2/insights",
                source_signal="Contemporary Indian design",
            ),
            CulturalRecommendation(
                id="test_fixture_ent_kashmir_loom",
                name="Kashmir Loom",
                type="brand",
                affinity=0.89,
                source_query="/v2/insights",
                source_signal="Contemporary Indian design",
            ),
        ],
        places=[
            CulturalRecommendation(
                id="test_fixture_ent_subko_coffee",
                name="Subko Specialty Coffee & Craft Bakehouse",
                type="place",
                affinity=0.95,
                source_query="/v2/insights",
                source_signal="Neighborhood third place",
            ),
            CulturalRecommendation(
                id="test_fixture_ent_soho_house_mumbai",
                name="Soho House Mumbai",
                type="place",
                affinity=0.92,
                source_query="/v2/insights",
                source_signal="Curated creative club benchmark",
            ),
        ],
        books=[
            CulturalRecommendation(
                id="test_fixture_ent_the_god_of_small_things",
                name="The God of Small Things",
                type="book",
                affinity=0.88,
                source_query="/v2/insights",
                source_signal="Contemporary Indian literature",
            )
        ],
        movies=[
            CulturalRecommendation(
                id="test_fixture_ent_the_lunchbox",
                name="The Lunchbox",
                type="movie",
                affinity=0.90,
                source_query="/v2/insights",
                source_signal="Independent Indian cinema",
            )
        ],
    )
