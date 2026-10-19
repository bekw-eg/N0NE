"""CLI for live collection, offline replay, and source-backed validation."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .models import BoundingBox, Capture, Dataset
from .normalize import capture_bytes, geojson, json_bytes, normalize, validate_source
from .overpass import DEFAULT_ENDPOINT, CollectionError, collect

LOGGER = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = {"level": record.levelname, "event": record.getMessage()}
        for key in ("error", "status", "attempt"):
            if hasattr(record, key):
                fields[key] = getattr(record, key)
        return json.dumps(fields, ensure_ascii=False)


def atomic_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(contents)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def collect_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect actual OSM POIs; no synthetic fallback")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--bbox", nargs=4, type=float, metavar=("SOUTH", "WEST", "NORTH", "EAST"))
    scope.add_argument("--from-raw", type=Path, help="Replay a previously recorded capture offline")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--output-dir", type=Path, default=Path("data/astana"))
    args = parser.parse_args(argv)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    try:
        if args.from_raw:
            raw = args.from_raw.read_bytes()
            capture = Capture.model_validate_json(raw)
        else:
            south, west, north, east = args.bbox
            bbox = BoundingBox(south=south, west=west, north=north, east=east)
            capture = collect(bbox, endpoint=args.endpoint)
            raw = capture_bytes(capture)
        dataset = normalize(capture, raw_bytes=raw)
        if not dataset.pois:
            raise CollectionError("No eligible POIs returned; existing output left untouched")
        validate_source(dataset, raw)
        atomic_write(args.output_dir / "overpass.capture.json", raw)
        atomic_write(args.output_dir / "pois.json", json_bytes(dataset.model_dump(mode="json")))
        atomic_write(args.output_dir / "pois.geojson", json_bytes(geojson(dataset)))
        print(json.dumps({"event": "collection_complete", **dataset.stats.model_dump()}))
        return 0
    except (CollectionError, ValidationError, ValueError, OSError) as exc:
        LOGGER.error("collection_failed", extra={"error": str(exc)})
        return 1


def validate_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate dataset and independently replay its source"
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--geojson", type=Path)
    args = parser.parse_args(argv)
    try:
        dataset = Dataset.model_validate_json(args.dataset.read_bytes())
        if not dataset.pois:
            raise ValueError("Dataset is empty")
        validate_source(dataset, args.raw.read_bytes())
        if args.geojson and json.loads(args.geojson.read_bytes()) != geojson(dataset):
            raise ValueError("GeoJSON does not match dataset")
        print(json.dumps({"valid": True, "pois": len(dataset.pois), "source_replayed": True}))
        return 0
    except (CollectionError, ValidationError, ValueError, OSError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}), file=sys.stderr)
        return 1
