from typing import Literal

from pydantic import Field, field_validator

from app.schemas.poi import DatasetMetadata, Model, PublicPOI

Language = Literal["ru", "kk", "en"]
RetrievalMode = Literal["lexical", "hybrid"]


class SearchRequest(Model):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    language: Language | None = None

    @field_validator("query")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must contain non-whitespace text")
        return value


class RetrievalHit(Model):
    poi: PublicPOI
    rank: int
    score: float
    lexical_score: float | None = None
    semantic_score: float | None = None
    warnings: list[str]


class RetrievalResponse(Model):
    query: str
    retrieval_mode: RetrievalMode
    results: list[RetrievalHit]
    dataset: DatasetMetadata
    warnings: list[str]


class Recommendation(Model):
    poi_id: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=1500)


class GenerationDraft(Model):
    language: Language
    recommendations: list[Recommendation] = Field(min_length=1, max_length=10)


class EvidencePOI(Model):
    poi_id: str
    name: str | None
    category: str
    address: dict[str, str] | None
    opening_hours: str | None
    indoor: bool | None
    covered: bool | None
    wheelchair: str | None
    source_url: str
    retrieved_at: str
    quality_warnings: list[str]
    verification_status: Literal["osm_source_only"] = "osm_source_only"


class EvidenceContext(Model):
    pois: list[EvidencePOI]
    allowed_explanations: list[Recommendation]


class RAGResponse(Model):
    query: str
    language: Language
    explanation: str
    mentioned_poi_ids: list[str]
    recommendations: list[Recommendation]
    sources: list[EvidencePOI]
    generation_status: Literal["generated", "retrieval_only"]
    generation_method: Literal["constrained_extractive", "deterministic"]
    llm_model: str | None
    warnings: list[str]
    retrieval: RetrievalResponse
