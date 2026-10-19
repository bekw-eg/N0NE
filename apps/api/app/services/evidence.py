"""Bounded evidence and trusted, localized explanations for extractive generation."""

import re

from app.schemas.poi import PublicPOI
from app.schemas.rag import (
    EvidenceContext,
    EvidencePOI,
    Language,
    Recommendation,
    RetrievalResponse,
)
from app.services.poi_service import normalize


def detect_language(query: str) -> Language:
    normalized = normalize(query)
    if re.search("[әғқңөұүһі]", normalized):
        return "kk"
    if re.search("[а-яё]", normalized):
        return "ru"
    return "en"


def source_evidence(poi: PublicPOI) -> EvidencePOI:
    return EvidencePOI(
        poi_id=poi.id,
        name=poi.name,
        category=poi.category,
        address=poi.address,
        opening_hours=poi.opening_hours,
        indoor=poi.indoor,
        covered=poi.covered,
        wheelchair=poi.wheelchair,
        source_url=str(poi.source_url),
        retrieved_at=poi.retrieved_at.isoformat(),
        quality_warnings=list(poi.quality_warnings),
    )


def trusted_explanation(poi: PublicPOI, language: Language) -> str:
    # Raw OSM text is never interpolated into prose. The category is an upstream enum.
    if language == "kk":
        base = f"OSM жазбасы табылды. Дереккөз санаты: {poi.category}. "
        hours = (
            "Жұмыс уақыты белгісіз. "
            if poi.opening_hours is None
            else "Дереккөзде жұмыс уақыты бар, оның өзектілігі тексерілмеген. "
        )
        return base + hours + "Жаяу жету мүмкіндігі мен қазір ашық екені тексерілмеген."
    if language == "ru":
        base = f"Найдена запись OSM. Категория по источнику: {poi.category}. "
        hours = (
            "Часы работы неизвестны. "
            if poi.opening_hours is None
            else "В источнике есть часы работы; их актуальность не проверена. "
        )
        return base + hours + "Пешая доступность и открытие сейчас не проверены."
    base = f"An OSM record was found. Source category: {poi.category}. "
    hours = (
        "Opening hours are unknown. "
        if poi.opening_hours is None
        else "Source hours exist; their current validity has not been checked. "
    )
    return base + hours + "Walking access and current opening status have not been checked."


def summary(language: Language, has_results: bool) -> str:
    if language == "kk":
        return (
            "OSM дереккөзіндегі іздеу нәтижелері. Қалауларға сәйкестігі тексерілмеген."
            if has_results
            else "Сұрауға сәйкес расталған жазбалар табылмады."
        )
    if language == "ru":
        return (
            "Результаты поиска по данным OSM. Соответствие предпочтениям не проверено."
            if has_results
            else "Подтверждённых записей по запросу не найдено."
        )
    return (
        "Search results from OSM. Preference matching has not been verified."
        if has_results
        else "No source-backed records matched the query."
    )


def build_context(
    retrieval: RetrievalResponse,
    language: Language,
    maximum_bytes: int,
) -> tuple[EvidenceContext, bool]:
    context = EvidenceContext(pois=[], allowed_explanations=[])
    truncated = False
    for hit in retrieval.results:
        evidence = source_evidence(hit.poi)
        explanation = Recommendation(
            poi_id=hit.poi.id,
            explanation=trusted_explanation(hit.poi, language),
        )
        candidate = EvidenceContext(
            pois=[*context.pois, evidence],
            allowed_explanations=[*context.allowed_explanations, explanation],
        )
        if len(candidate.model_dump_json().encode("utf-8")) > maximum_bytes:
            truncated = True
            continue  # Never truncate a source field into a different asserted fact.
        context = candidate
    return context, truncated
