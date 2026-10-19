"""Start a real Uvicorn process and verify HTTP; no external services required."""

import socket
import subprocess
import sys
import time

import httpx


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
            for _ in range(100):
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
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
