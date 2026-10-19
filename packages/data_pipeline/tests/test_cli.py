import json
from pathlib import Path

from viberoute_data.cli import collect_main, validate_main
from viberoute_data.models import Capture, Dataset
from viberoute_data.normalize import capture_bytes


def test_offline_cli_roundtrip_and_geojson_validation(tmp_path: Path, capture: Capture) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(capture_bytes(capture))
    output = tmp_path / "dataset"
    assert collect_main(["--from-raw", str(source), "--output-dir", str(output)]) == 0
    args = [
        str(output / "pois.json"),
        "--raw",
        str(output / "overpass.capture.json"),
        "--geojson",
        str(output / "pois.geojson"),
    ]
    assert validate_main(args) == 0
    dataset = Dataset.model_validate_json((output / "pois.json").read_bytes())
    assert len(dataset.pois) == 1
    document = json.loads((output / "pois.geojson").read_bytes())
    document["features"][0]["geometry"]["coordinates"].reverse()
    (output / "pois.geojson").write_text(json.dumps(document), encoding="utf-8")
    assert validate_main(args) == 1


def test_failed_empty_collection_preserves_existing_output(
    tmp_path: Path, capture: Capture
) -> None:
    capture.response["elements"] = []
    source = tmp_path / "source.json"
    source.write_bytes(capture_bytes(capture))
    output = tmp_path / "dataset"
    output.mkdir()
    existing = output / "pois.json"
    existing.write_bytes(b"PREVIOUS DATASET")
    assert collect_main(["--from-raw", str(source), "--output-dir", str(output)]) == 1
    assert existing.read_bytes() == b"PREVIOUS DATASET"


def test_missing_source_is_a_controlled_error(tmp_path: Path) -> None:
    assert collect_main(["--from-raw", str(tmp_path / "missing.json")]) == 1
    assert validate_main([str(tmp_path / "missing.json"), "--raw", str(tmp_path / "raw.json")]) == 1
