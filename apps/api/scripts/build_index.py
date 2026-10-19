"""Explicit, network-enabled build/warm of the derived Ollama embedding index."""

import httpx

from app.core.config import Settings
from app.integrations.ollama import OllamaEmbeddings, ProviderError
from app.repositories.poi_repository import POIRepository
from app.retrieval.lexical import BM25Index
from app.retrieval.semantic import SemanticIndex


def main() -> int:
    settings = Settings()
    repository = POIRepository.load(settings.poi_dataset_path)
    with httpx.Client(trust_env=False) as client:
        try:
            index, warnings = SemanticIndex.load_or_build(
                BM25Index(repository).documents,
                repository.metadata.dataset_sha256,
                OllamaEmbeddings(settings, client),
                settings,
            )
        except ProviderError as error:
            print(f"Index unavailable: {error.code}")
            return 1
    print(
        f"Indexed {len(index.ids)} POIs; model={settings.embedding_model}; "
        f"dataset_sha256={repository.metadata.dataset_sha256}; warnings={warnings}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
