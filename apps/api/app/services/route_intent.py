"""Small source-category walking intents; no claims about ambience or admission."""

from typing import Literal

from app.retrieval.text import requests_pizza, tokens
from app.schemas.poi import Category

StopKind = Literal["coffee", "park"]
STOP_CATEGORIES: dict[StopKind, frozenset[Category]] = {
    "coffee": frozenset({"cafe"}),
    "park": frozenset({"park", "garden"}),
}
STOP_WORDS: dict[StopKind, frozenset[str]] = {
    "coffee": frozenset(
        {
            "кофе",
            "кофейня",
            "кофейню",
            "кофейне",
            "кофейни",
            "кофейней",
            "кафе",
            "coffee",
            "cafe",
            "café",
            "кофеге",
            "кофені",
        }
    ),
    "park": frozenset(
        {
            "парк",
            "парка",
            "парке",
            "парку",
            "парком",
            "парки",
            "парков",
            "сад",
            "сада",
            "саду",
            "садом",
            "park",
            "parks",
            "garden",
            "gardens",
            "саябақ",
            "саябақта",
            "саябаққа",
            "бақ",
            "бақта",
        }
    ),
}


def requested_stages(query: str) -> tuple[StopKind, ...]:
    # Keep the separate source-evidence pizza contract; arbitrary dishes and
    # complex food combinations are outside this bounded category parser.
    if requests_pizza(query):
        return ()
    words = tokens(query)
    positions: dict[StopKind, int] = {}
    for kind, aliases in STOP_WORDS.items():
        for index, word in enumerate(words):
            if word in aliases and not {"без", "without"}.intersection(
                words[max(0, index - 1) : index]
            ):
                positions.setdefault(kind, index)
    if len(positions) < 2:
        return tuple(positions)
    # An unspecified coffee-and-walk scenario starts with coffee. Explicit
    # "first park, then coffee" / "coffee after park" overrides that default.
    if {
        "сначала",
        "потом",
        "затем",
        "после",
        "до",
        "first",
        "then",
        "after",
        "before",
        "алдымен",
        "кейін",
    }.intersection(words):
        ordered = sorted(positions, key=lambda kind: positions[kind])
        first, last = positions[ordered[0]], positions[ordered[-1]]
        if {"после", "after"}.intersection(words[first + 1 : last]):
            ordered.reverse()
        return tuple(ordered)
    return ("coffee", "park")
