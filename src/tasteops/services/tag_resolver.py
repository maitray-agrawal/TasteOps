"""TasteOps Tag Resolver.

Converts cultural vibes, aesthetic movements, and genre keywords into verified Qloo taxonomy tags.
Strictly rejects unknown tags and prevents tag ID fabrication.
"""

import difflib
import logging
import re

from tasteops.client import QlooClient
from tasteops.models.params import TagParams
from tasteops.models.resolution import (
    ResolutionEvidence,
    TagCandidate,
    TagResolutionResult,
)
from tasteops.models.tag import QlooTag

logger = logging.getLogger("tasteops.tag_resolver")


class TagResolver:
    """Resolves natural language cultural tags into validated Qloo taxonomy tags."""

    def __init__(self, client: QlooClient) -> None:
        self.client = client

    @staticmethod
    def normalize_term(term: str) -> str:
        """Cleans and standardizes raw input terms (strips quotes, excess whitespace)."""
        if not term:
            return ""
        cleaned = term.strip().strip("'\"`").strip()
        return re.sub(r"\s+", " ", cleaned)

    def compute_tag_match_score(
        self,
        query: str,
        tag: QlooTag,
        expected_category: str | None = None,
    ) -> tuple[float, str]:
        """Calculates similarity score [0.0 - 1.0] and match justification."""
        norm_q = query.lower()
        norm_tag = tag.name.strip().lower()

        # 1. Exact match (case-insensitive)
        if norm_q == norm_tag:
            return 1.0, "exact_match"

        # 2. Token set exact match (e.g. "minimalism japanese" -> "Japanese minimalism")
        tokens_q = set(norm_q.split())
        tokens_tag = set(norm_tag.split())
        if tokens_q == tokens_tag:
            return 0.98, "token_exact_match"

        # 3. Token subset match (e.g. "indie" in "indie cinema")
        if tokens_q.issubset(tokens_tag) and len(tokens_tag) > 0:
            coverage = len(tokens_q) / len(tokens_tag)
            score = round(0.85 + (0.10 * coverage), 4)
            return score, "token_subset_match"

        # 4. Prefix or Substring match
        if norm_tag.startswith(norm_q) or norm_q.startswith(norm_tag):
            ratio = min(len(norm_q), len(norm_tag)) / max(len(norm_q), len(norm_tag))
            score = round(0.80 + (0.14 * ratio), 4)
            return score, "prefix_match"

        # 5. Fuzzy string similarity via SequenceMatcher
        seq_ratio = difflib.SequenceMatcher(None, norm_q, norm_tag).ratio()
        fuzzy_score = round(seq_ratio, 4)

        # Small boost if expected category matches
        if expected_category and tag.category and expected_category.lower() in tag.category.lower():
            fuzzy_score = min(1.0, round(fuzzy_score + 0.05, 4))

        return fuzzy_score, "fuzzy_similarity"

    async def resolve(
        self,
        query: str,
        *,
        expected_category: str | None = None,
        min_confidence: float = 0.5,
        take: int = 20,
    ) -> TagResolutionResult:
        """Resolves a natural language vibe/genre/tag into a verified Qloo taxonomy tag.

        Rejects unknown tags that cannot be verified in the Qloo taxonomy.

        Args:
            query: Natural language tag term (e.g. "Japanese minimalism", "indie cinema").
            expected_category: Optional domain category (e.g. "music", "dining", "style").
            min_confidence: Minimum score [0.0 - 1.0] required to accept top match.
            take: Candidate pool size retrieved from Qloo.

        Returns:
            TagResolutionResult containing verified tag ID or None, confidence,
            ranked alternatives, and full provenance evidence.
        """
        norm_query = self.normalize_term(query)

        if not norm_query:
            logger.warning("Empty or blank query provided to TagResolver.")
            return TagResolutionResult(
                input=query,
                resolved_tag_id=None,
                tag_name=None,
                category=None,
                confidence=0.0,
                source="qloo_tags",
                tag=None,
                alternatives=[],
                evidence=ResolutionEvidence(
                    source="qloo_tags",
                    raw_query=query,
                    normalized_query=norm_query,
                    match_method="empty_input",
                    score=0.0,
                    metadata={"error": "Blank tag query"},
                ),
            )

        logger.debug("Searching Qloo tag taxonomy for: '%s' (category=%s)", norm_query, expected_category)

        # 1. Search Qloo tags endpoint
        tag_params = TagParams(
            query=norm_query,
            type=expected_category,
            take=take,
        )
        candidates_raw = await self.client.get_tags(tag_params)

        # If no direct query match, optionally fall back to category query
        if not candidates_raw and expected_category:
            logger.debug("No direct tag results for '%s'; attempting category search for '%s'", norm_query, expected_category)
            candidates_raw = await self.client.get_tags(TagParams(type=expected_category, take=take))

        if not candidates_raw:
            logger.info("Unknown tag rejected: '%s' not found in Qloo taxonomy.", norm_query)
            return TagResolutionResult(
                input=query,
                resolved_tag_id=None,
                tag_name=None,
                category=None,
                confidence=0.0,
                source="qloo_tags",
                tag=None,
                alternatives=[],
                evidence=ResolutionEvidence(
                    source="qloo_tags",
                    raw_query=query,
                    normalized_query=norm_query,
                    match_method="rejected_unknown_tag",
                    score=0.0,
                    metadata={"candidates_found": 0},
                ),
            )

        # 2. Score and rank candidates
        ranked_candidates: list[TagCandidate] = []
        for cand in candidates_raw:
            score, reason = self.compute_tag_match_score(norm_query, cand, expected_category)
            ranked_candidates.append(
                TagCandidate(tag=cand, confidence=score, match_reason=reason)
            )

        ranked_candidates.sort(key=lambda c: c.confidence, reverse=True)

        best = ranked_candidates[0]
        alternatives = ranked_candidates[1:]

        # 3. Acceptance threshold check
        if best.confidence >= min_confidence:
            logger.info(
                "Resolved tag '%s' -> '%s' (ID: %s, Category: %s, Confidence: %0.2f)",
                norm_query,
                best.tag.name,
                best.tag.id,
                best.tag.category,
                best.confidence,
            )
            return TagResolutionResult(
                input=query,
                resolved_tag_id=best.tag.id,
                tag_name=best.tag.name,
                category=best.tag.category,
                confidence=best.confidence,
                source="qloo_tags",
                tag=best.tag,
                alternatives=alternatives,
                evidence=ResolutionEvidence(
                    source="qloo_tags",
                    raw_query=query,
                    normalized_query=norm_query,
                    match_method=best.match_reason,
                    score=best.confidence,
                    metadata={
                        "candidate_count": len(ranked_candidates),
                        "top_tag_name": best.tag.name,
                    },
                ),
            )
        else:
            logger.warning(
                "Unknown tag rejected: Top match '%s' (score %0.2f) for query '%s' was below min_confidence %0.2f.",
                best.tag.name,
                best.confidence,
                norm_query,
                min_confidence,
            )
            return TagResolutionResult(
                input=query,
                resolved_tag_id=None,
                tag_name=None,
                category=None,
                confidence=0.0,
                source="qloo_tags",
                tag=None,
                alternatives=ranked_candidates,
                evidence=ResolutionEvidence(
                    source="qloo_tags",
                    raw_query=query,
                    normalized_query=norm_query,
                    match_method="rejected_below_confidence",
                    score=best.confidence,
                    metadata={
                        "candidate_count": len(ranked_candidates),
                        "highest_rejected_score": best.confidence,
                        "highest_rejected_tag": best.tag.name,
                    },
                ),
            )

    async def resolve_batch(
        self,
        queries: list[str],
        *,
        expected_category: str | None = None,
        min_confidence: float = 0.5,
    ) -> list[TagResolutionResult]:
        """Resolves multiple tag terms."""
        results: list[TagResolutionResult] = []
        for q in queries:
            res = await self.resolve(q, expected_category=expected_category, min_confidence=min_confidence)
            results.append(res)
        return results
