"""Start a real Uvicorn process and verify HTTP; no external services required."""

import socket
import subprocess
import sys
import time

import httpx

from app.core.config import Settings


def main() -> None:
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client:
            settings = Settings()
            startup_budget = 20.0
            if settings.semantic_enabled:
                startup_budget += (
                    settings.index_build_timeout_seconds + settings.embedding_timeout_seconds
                )
            deadline = time.monotonic() + startup_budget
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Uvicorn exited before readiness")
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Uvicorn readiness timed out")
            assert client.get("/docs").status_code == 200
            assert client.get("/openapi.json").status_code == 200
            page = client.get("/api/v1/pois", params={"q": "Rafe"}).json()
            assert any(poi["id"] == "osm:node:1843876259" for poi in page["items"])
            assert client.get("/api/v1/pois").json()["total"] == 497
            print("PASS: real Uvicorn, health, docs, OpenAPI, 497 POIs, Rafe lookup")
            retrieval = client.post("/api/v1/retrieval/search", json={"query": "Rafe"}).json()
            assert any(hit["poi"]["id"] == "osm:node:1843876259" for hit in retrieval["results"])
            rag = client.post(
                "/api/v1/rag/query", json={"query": "Ботаникалық бақ"}, timeout=120
            ).json()
            assert rag["mentioned_poi_ids"] and rag["language"] == "kk"
            assert rag["retrieval"]["dataset"]["license"] == "ODbL-1.0"
            print(
                f"PASS: retrieval mode={retrieval['retrieval_mode']}; "
                f"RAG status={rag['generation_status']}; warnings={','.join(rag['warnings'])}"
            )
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
