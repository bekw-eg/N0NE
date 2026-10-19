from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.ollama import LLMProvider, ProviderError
from app.schemas.rag import GenerationDraft, RAGResponse, SearchRequest
from app.services.evidence import build_context, detect_language, summary
from app.services.retrieval_service import RetrievalService


class RAGService:
    def __init__(
        self,
        retrieval: RetrievalService,
        settings: Settings,
        llm: LLMProvider | None = None,
    ) -> None:
        self.retrieval = retrieval
        self.settings = settings
        self.llm = llm

    def query(self, request: SearchRequest) -> RAGResponse:
        retrieval = self.retrieval.search(request)
        language = request.language or detect_language(request.query)
        context, truncated = build_context(retrieval, language, self.settings.context_max_bytes)
        warnings = list(retrieval.warnings)
        if truncated:
            warnings.append("evidence_context_truncated")
        recommendations = context.allowed_explanations
        generated = False
        used_model: str | None = None
        if not context.pois:
            warnings.append("no_evidence_for_generation")
        elif self.llm is None:
            warnings.append("llm_disabled")
        else:
            used_model = self.llm.model_id
            try:
                # Revalidate even a custom provider; Pydantic schema is only the first gate.
                draft = GenerationDraft.model_validate(
                    self.llm.generate(
                        request.query,
                        context,
                        language,
                    ).model_dump()
                )
                allowed = {item.poi_id: item.explanation for item in context.allowed_explanations}
                ids = [item.poi_id for item in draft.recommendations]
                if draft.language != language or len(ids) != len(set(ids)):
                    raise ProviderError("llm_ungrounded_response")
                if any(
                    allowed.get(item.poi_id) != item.explanation for item in draft.recommendations
                ):
                    raise ProviderError("llm_ungrounded_response")
                recommendations = draft.recommendations
                generated = True
            except (ProviderError, ValidationError) as error:
                warnings.append(
                    error.code if isinstance(error, ProviderError) else "llm_invalid_response"
                )
        mentioned = [item.poi_id for item in recommendations]
        evidence_by_id = {poi.poi_id: poi for poi in context.pois}
        return RAGResponse(
            query=request.query,
            language=language,
            explanation=summary(language, bool(retrieval.results)),
            mentioned_poi_ids=mentioned,
            recommendations=recommendations,
            sources=[evidence_by_id[poi_id] for poi_id in mentioned],
            generation_status="generated" if generated else "retrieval_only",
            generation_method="constrained_extractive" if generated else "deterministic",
            llm_model=used_model,
            warnings=sorted(set(warnings)),
            retrieval=retrieval,
        )
