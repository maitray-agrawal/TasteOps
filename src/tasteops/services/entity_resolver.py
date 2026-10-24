"""TasteOps Entity Resolver.

Converts natural-language cultural anchors into verified Qloo entity identifiers.
Guarantees verified IDs, ranks candidates with confidence scoring, preserves
alternatives, and records algorithmic provenance.
"""

import difflib
import logging
import re

from tasteops.client import QlooClient
from tasteops.models.entity import QlooEntity
from tasteops.models.params import SearchParams
from tasteops.models.resolution import (
    EntityCandidate,
    EntityResolutionResult,
    ResolutionEvidence,
)

logger = logging.getLogger("tasteops.entity_resolver")


class EntityResolver:
    """Resolves natural language cultural anchors into verified Qloo entities."""

    def __init__(self, client: QlooClient) -> None:
        self.client = client

    @staticmethod
    def normalize_term(term: str) -> str:
        """Cleans and standardizes raw input terms (strips quotes, excess whitespace)."""
        if not term:
            return ""
        # Remove outer quotes and whitespace
        cleaned = term.strip().strip("'\"`").strip()
        # Collapse multiple spaces into single space
        return re.sub(r"\s+", " ", cleaned)

    def compute_match_score(
        self,
        query: str,
        entity: QlooEntity,
        expected_type: str | None = None,
    ) -> tuple[float, str]:
        """Calculates similarity score [0.0 - 1.0] and match justification."""
        norm_q = query.lower()
        norm_cand = entity.name.strip().lower()

        # 1. Exact match (case-insensitive)
        if norm_q == norm_cand:
            return 1.0, "exact_match"

        # 2. Token set exact match (e.g. "Monkeys Arctic" -> "Arctic Monkeys")
        tokens_q = set(norm_q.split())
        tokens_cand = set(norm_cand.split())
        if tokens_q == tokens_cand:
            return 0.98, "token_exact_match"

        # 3. Token subset match (e.g. "Blue Bottle" in "Blue Bottle Coffee")
        if tokens_q.issubset(tokens_cand) and len(tokens_cand) > 0:
            coverage = len(tokens_q) / len(tokens_cand)
            score = round(0.85 + (0.10 * coverage), 4)
            return score, "token_subset_match"

        # 4. Prefix or Substring match
        if norm_cand.startswith(norm_q) or norm_q.startswith(norm_cand):
            ratio = min(len(norm_q), len(norm_cand)) / max(len(norm_q), len(norm_cand))
            score = round(0.80 + (0.14 * ratio), 4)
            return score, "prefix_match"

        # 5. Fuzzy string similarity via SequenceMatcher
        seq_ratio = difflib.SequenceMatcher(None, norm_q, norm_cand).ratio()
        fuzzy_score = round(seq_ratio, 4)

        # Small boost if expected entity type matches
        if (
            expected_type
            and entity.type
            and expected_type.lower() in entity.type.lower()
        ):
            fuzzy_score = min(1.0, round(fuzzy_score + 0.05, 4))

        return fuzzy_score, "fuzzy_similarity"

    async def resolve(
        self,
        query: str,
        *,
        expected_type: str | None = None,
        min_confidence: float = 0.5,
        take: int = 10,
    ) -> EntityResolutionResult:
        """Resolves a natural language term to the best verified Qloo entity.

        Args:
            query: Natural language anchor (e.g. " A24 ", "Arctic Monkeys").
            expected_type: Optional entity type filter (e.g. "brand", "artist", "place").
            min_confidence: Minimum score [0.0 - 1.0] required to accept top match.
            take: Candidate pool size retrieved from Qloo.

        Returns:
            EntityResolutionResult containing verified ID or None, confidence,
            ranked alternatives, and full provenance evidence.
        """
        norm_query = self.normalize_term(query)

        if not norm_query:
            logger.warning("Empty or blank query provided to EntityResolver.")
            return EntityResolutionResult(
                input=query,
                resolved_entity_id=None,
                entity_type=None,
                confidence=0.0,
                source="qloo_search",
                entity=None,
                alternatives=[],
                evidence=ResolutionEvidence(
                    source="qloo_search",
                    raw_query=query,
                    normalized_query=norm_query,
                    match_method="empty_input",
                    score=0.0,
                    metadata={"error": "Blank query"},
                ),
            )

        logger.debug(
            "Searching Qloo for cultural anchor: '%s' (type=%s)",
            norm_query,
            expected_type,
        )

        # 1. Search Qloo using validated SearchParams
        search_params = SearchParams(
            query=norm_query,
            type=expected_type,
            take=take,
        )
        candidates_raw = await self.client.search(search_params)

        if not candidates_raw:
            logger.info("No candidates found in Qloo for '%s'", norm_query)
            return EntityResolutionResult(
                input=query,
                resolved_entity_id=None,
                entity_type=None,
                confidence=0.0,
                source="qloo_search",
                entity=None,
                alternatives=[],
                evidence=ResolutionEvidence(
                    source="qloo_search",
                    raw_query=query,
                    normalized_query=norm_query,
                    match_method="unresolved_no_results",
                    score=0.0,
                    metadata={"candidates_found": 0},
                ),
            )

        # 2. Score and rank all candidate matches
        ranked_candidates: list[EntityCandidate] = []
        for cand in candidates_raw:
            score, reason = self.compute_match_score(norm_query, cand, expected_type)
            ranked_candidates.append(
                EntityCandidate(entity=cand, confidence=score, match_reason=reason)
            )

        # Sort descending by confidence score
        ranked_candidates.sort(key=lambda c: c.confidence, reverse=True)

        best = ranked_candidates[0]
        alternatives = ranked_candidates[1:]

        # 3. Acceptance threshold check - NEVER invent or accept sub-threshold IDs
        if best.confidence >= min_confidence:
            logger.info(
                "Resolved '%s' -> %s ('%s', ID: %s, Confidence: %0.2f)",
                norm_query,
                best.entity.type or "entity",
                best.entity.name,
                best.entity.id,
                best.confidence,
            )
            return EntityResolutionResult(
                input=query,
                resolved_entity_id=best.entity.id,
                entity_type=best.entity.type,
                confidence=best.confidence,
                source="qloo_search",
                entity=best.entity,
                alternatives=alternatives,
                evidence=ResolutionEvidence(
                    source="qloo_search",
                    raw_query=query,
                    normalized_query=norm_query,
                    match_method=best.match_reason,
                    score=best.confidence,
                    metadata={
                        "candidate_count": len(ranked_candidates),
                        "top_candidate_name": best.entity.name,
                    },
                ),
            )
        else:
            logger.warning(
                "Top candidate '%s' (score %0.2f) for query '%s' was below min_confidence %0.2f. Rejected.",
                best.entity.name,
                best.confidence,
                norm_query,
                min_confidence,
            )
            return EntityResolutionResult(
                input=query,
                resolved_entity_id=None,
                entity_type=None,
                confidence=0.0,
                source="qloo_search",
                entity=None,
                alternatives=ranked_candidates,
                evidence=ResolutionEvidence(
                    source="qloo_search",
                    raw_query=query,
                    normalized_query=norm_query,
                    match_method="rejected_below_confidence",
                    score=best.confidence,
                    metadata={
                        "candidate_count": len(ranked_candidates),
                        "highest_rejected_score": best.confidence,
                        "highest_rejected_candidate": best.entity.name,
                    },
                ),
            )

    async def resolve_batch(
        self,
        queries: list[str],
        *,
        expected_type: str | None = None,
        min_confidence: float = 0.5,
    ) -> list[EntityResolutionResult]:
        """Resolves multiple natural language terms sequentially or concurrently."""
        results: list[EntityResolutionResult] = []
        for q in queries:
            res = await self.resolve(
                q, expected_type=expected_type, min_confidence=min_confidence
            )
            results.append(res)
        return results
