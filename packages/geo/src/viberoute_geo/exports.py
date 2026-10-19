"""Atomic JSON exports shared by the smoke CLI and public-anchor scenario."""

import json
import os
from pathlib import Path


def atomic_json(path: Path, value: object) -> None:
    contents = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(contents)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
