"""Small deterministic BM25 index (k1=1.5, b=0.75), with stable-ID ties."""

import math
from collections import Counter

from app.repositories.poi_repository import POIRepository
from app.retrieval.text import document, tokens


class BM25Index:
    def __init__(self, repository: POIRepository) -> None:
        self.documents = {poi.id: document(poi) for poi in repository.records}
        self.frequencies = {key: Counter(tokens(value)) for key, value in self.documents.items()}
        self.lengths = {key: sum(value.values()) for key, value in self.frequencies.items()}
        self.average_length = sum(self.lengths.values()) / max(1, len(self.lengths)) or 1.0
        self.document_frequency = Counter(
            term for counts in self.frequencies.values() for term in counts
        )

    def search(self, query: str) -> list[tuple[str, float]]:
        terms = sorted(set(tokens(query)))
        results = []
        count = len(self.frequencies)
        for poi_id, frequencies in self.frequencies.items():
            score = 0.0
            for term in terms:
                frequency = frequencies[term]
                if not frequency:
                    continue
                df = self.document_frequency[term]
                idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
                denominator = frequency + 1.5 * (
                    0.25 + 0.75 * self.lengths[poi_id] / self.average_length
                )
                score += idf * frequency * 2.5 / denominator
            if score > 0:
                results.append((poi_id, score))
        return sorted(results, key=lambda item: (-item[1], item[0]))
