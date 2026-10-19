"""Optional real-model smoke. Exit 2 means skipped, never a passing model test."""

import httpx

from app.core.config import Settings
from app.integrations.ollama import OllamaEmbeddings, OllamaLLM, ProviderError
from app.repositories.poi_repository import POIRepository
from app.schemas.rag import SearchRequest
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService


def main() -> int:
    settings = Settings(semantic_enabled=True)
    with httpx.Client(trust_env=False, timeout=3) as client:
        try:
            response = client.get(f"{str(settings.ollama_base_url).rstrip('/')}/api/tags")
            response.raise_for_status()
            installed = {item["name"] for item in response.json()["models"]}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            print("SKIP: Ollama unavailable; real models were not tested")
            return 2
        missing = {settings.llm_model, settings.embedding_model} - installed
        if missing:
            print(f"SKIP: required models not installed: {', '.join(sorted(missing))}")
            return 2
        repository = POIRepository.load(settings.poi_dataset_path)
        search = RetrievalService(repository, settings, OllamaEmbeddings(settings, client))
        rag = RAGService(search, settings, OllamaLLM(settings, client))
        requests = [
            SearchRequest(query="Ботаникалық бақ", language="kk", top_k=2),
            SearchRequest(query="Хочу кафе", language="ru", top_k=2),
        ]
        for request in requests:
            result = rag.query(request)
            if (
                result.retrieval.retrieval_mode != "hybrid"
                or result.generation_status != "generated"
            ):
                print(f"FAIL: real model smoke fell back ({request.language}): {result.warnings}")
                return 1
            print(
                f"PASS: real embeddings, hybrid retrieval and grounded Qwen generation "
                f"({request.language})"
            )
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProviderError as error:
        print(f"FAIL: {error.code}")
        raise SystemExit(1) from error
