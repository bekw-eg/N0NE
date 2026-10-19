from app.core.config import Settings
from app.integrations.ollama import EmbeddingProvider, ProviderError
from app.repositories.poi_repository import POIRepository
from app.retrieval.lexical import BM25Index
from app.retrieval.semantic import SemanticIndex
from app.retrieval.text import is_pizza_place, requests_pizza
from app.schemas.rag import RetrievalHit, RetrievalMode, RetrievalResponse, SearchRequest


def reciprocal_rank_fusion(*rankings: list[tuple[str, float]]) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, (poi_id, _) in enumerate(ranking, start=1):
            if poi_id not in seen:
                scores[poi_id] = scores.get(poi_id, 0.0) + 1.0 / (60 + rank)
                seen.add(poi_id)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


class RetrievalService:
    def __init__(
        self,
        repository: POIRepository,
        settings: Settings,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.lexical = BM25Index(repository)
        self.embedding_provider = embedding_provider
        self.semantic: SemanticIndex | None = None
        self.startup_warnings = []
        if not settings.semantic_enabled:
            self.startup_warnings.append("semantic_disabled")
        elif embedding_provider is None:
            self.startup_warnings.append("embedding_unavailable")
        else:
            try:
                self.semantic, cache_warnings = SemanticIndex.load_or_build(
                    self.lexical.documents,
                    repository.metadata.dataset_sha256,
                    embedding_provider,
                    settings,
                )
                self.startup_warnings.extend(cache_warnings)
            except ProviderError as error:
                self.startup_warnings.append(error.code)

    def search(self, request: SearchRequest) -> RetrievalResponse:
        lexical = self.lexical.search(request.query)
        semantic: list[tuple[str, float]] = []
        warnings = list(self.startup_warnings)
        mode: RetrievalMode = "lexical"
        if self.semantic is not None and self.embedding_provider is not None:
            try:
                vectors = self.embedding_provider.embed([request.query])
                if len(vectors) != 1:
                    raise ProviderError("embedding_invalid_response")
                semantic = self.semantic.search(vectors[0], self.settings.semantic_min_score)
                mode = "hybrid"
            except ProviderError as error:
                warnings.append(error.code)
        if mode == "hybrid":
            ranked = reciprocal_rank_fusion(lexical, semantic)
        else:
            ranked = lexical
        if requests_pizza(request.query):
            matching_ids = {poi.id for poi in self.repository.records if is_pizza_place(poi)}
            # Apply before top_k so generic lexical or semantic hits cannot crowd
            # out places with actual source evidence for the requested food.
            ranked = [(poi_id, score) for poi_id, score in ranked if poi_id in matching_ids]
        lexical_scores, semantic_scores = dict(lexical), dict(semantic)
        hits = []
        for rank, (poi_id, score) in enumerate(ranked[: request.top_k], start=1):
            poi = self.repository.by_id[poi_id]
            unknown = [
                f"{field}_unknown"
                for field in (
                    "opening_hours",
                    "indoor",
                    "covered",
                    "wheelchair",
                    "address",
                )
                if getattr(poi, field) is None
            ]
            hits.append(
                RetrievalHit(
                    poi=poi,
                    rank=rank,
                    score=score,
                    lexical_score=lexical_scores.get(poi_id),
                    semantic_score=semantic_scores.get(poi_id),
                    warnings=sorted(set(poi.quality_warnings + unknown)),
                )
            )
        warnings.extend(
            [
                "osm_source_only",
                "retrieval_scores_are_not_factual_confidence",
                "preferences_not_verified",
                "walking_access_not_checked",
                "current_opening_status_unknown",
            ]
        )
        return RetrievalResponse(
            query=request.query,
            retrieval_mode=mode,
            results=hits,
            dataset=self.repository.metadata,
            warnings=sorted(set(warnings)),
        )
