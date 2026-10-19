"""Environment configuration; .env files are loaded only when explicitly requested."""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    poi_dataset_path: Path = ROOT / "data/astana/pois.json"
    cors_origins: list[str] = []
    semantic_enabled: bool = False
    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:11434")
    llm_provider: Literal["ollama", "disabled"] = "ollama"
    llm_model: str = Field(default="qwen3:4b-instruct", min_length=1, max_length=120)
    embedding_model: str = Field(default="qwen3-embedding:0.6b", min_length=1, max_length=120)
    embedding_batch_size: int = Field(default=32, ge=1, le=128)
    embedding_timeout_seconds: float = Field(default=60, gt=0, le=120)
    index_build_timeout_seconds: float = Field(default=300, gt=0, le=600)
    llm_timeout_seconds: float = Field(default=60, gt=0, le=120)
    llm_max_tokens: int = Field(default=1200, ge=100, le=4096)
    semantic_min_score: float = Field(default=0.35, ge=-1, le=1)
    embedding_index_dir: Path = ROOT / "data/tmp/embeddings"
    context_max_bytes: int = Field(default=24000, ge=1024, le=64000)

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins(cls, values: list[str]) -> list[str]:
        from urllib.parse import urlsplit

        for value in values:
            parts = urlsplit(value)
            if (
                "*" in value
                or parts.scheme not in {"http", "https"}
                or not parts.netloc
                or parts.username
                or parts.password
                or parts.path
                or parts.query
                or parts.fragment
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths")
        return values
