import pytest

from app.services.route_intent import requested_stages


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Хочу спокойную прогулку возле парка с кофе", ("coffee", "park")),
        ("парк и кофейня", ("coffee", "park")),
        ("сначала парк потом кофе", ("park", "coffee")),
        ("coffee after park", ("park", "coffee")),
        ("кофе после парка", ("park", "coffee")),
        ("сначала кофе затем парк", ("coffee", "park")),
        ("first cafe then garden", ("coffee", "park")),
        ("парк без кофе", ("park",)),
        ("coffee", ("coffee",)),
        ("Хочу пиццу", ()),
        ("Архитектура EXPO", ()),
    ],
)
def test_required_walking_stages(query: str, expected: tuple[str, ...]) -> None:
    assert requested_stages(query) == expected
