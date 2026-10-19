from urllib.parse import parse_qs

import httpx
import pytest

from viberoute_data.models import Capture
from viberoute_data.overpass import CollectionError, build_query, collect


def test_query_is_bounded_and_requests_metadata(capture: Capture) -> None:
    query = build_query(capture.bbox)
    assert "nwr" in query
    assert query.count(f"({capture.bbox.ql()})") == 4
    assert '"^(cafe|restaurant|' in query
    assert query.endswith("out meta center;\n")


def test_live_client_request_and_removal_of_mapper_identity(capture: Capture) -> None:
    payload = capture.response.copy()
    payload["elements"] = [
        {
            "type": "node",
            "id": 100,
            "user": "SYNTHETIC MAPPER",
            "uid": 42,
            "version": 1,
            "timestamp": "2025-01-01T00:00:00Z",
        }
    ]

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert parse_qs(request.content.decode())["data"] == [build_query(capture.bbox)]
        assert request.headers["User-Agent"].startswith("VibeRoute/")
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = collect(capture.bbox, client=client)
    element = result.response["elements"][0]
    assert "uid" not in element and "user" not in element
    assert element["timestamp"] == "2025-01-01T00:00:00Z"


def test_rate_limit_retry_is_bounded(capture: Capture) -> None:
    requests = []
    sleeps: list[float] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": "120"})
        return httpx.Response(200, json=capture.response)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        collect(capture.bbox, client=client, sleep=sleeps.append)
    assert len(requests) == 2
    assert sleeps == [30.0]


def test_repeated_upstream_failure_is_not_fake_empty_success(capture: Capture) -> None:
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(CollectionError):
            collect(capture.bbox, client=client, sleep=lambda _: None)
    assert len(requests) == 3


@pytest.mark.parametrize(
    "payload",
    [
        {"elements": [], "remark": "runtime error: Query timed out"},
        {"error": "upstream unavailable"},
        {"elements": ["bad element"]},
        [],
    ],
)
def test_partial_or_malformed_results_rejected(capture: Capture, payload: object) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(CollectionError):
            collect(capture.bbox, client=client)


def test_invalid_json_is_controlled(capture: Capture) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html/>"))
    ) as client:
        with pytest.raises(CollectionError):
            collect(capture.bbox, client=client)


def test_transport_failure_is_retried(capture: Capture) -> None:
    sleeps: list[float] = []

    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("SYNTHETIC timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(CollectionError, match="transport failed"):
            collect(capture.bbox, client=client, sleep=sleeps.append)
    assert sleeps == [2.0, 4.0]
