"""Bounded, deterministic planning using ORS graph metrics and source POIs."""

from dataclasses import dataclass
from itertools import product
from math import asin, cos, isfinite, radians, sin, sqrt
from typing import Protocol

import httpx
from pydantic import ValidationError
from viberoute_geo import Anchor, AnchorCatalog

from app.core.config import ROOT, Settings
from app.integrations.geo_adapter import (
    DirectionsRequest,
    GeoError,
    GeoPoint,
    MatrixRequest,
    MatrixResult,
    RouteResult,
)
from app.retrieval.text import requests_pizza
from app.schemas.poi import Category, PublicPOI
from app.schemas.rag import Language, RetrievalMode, SearchRequest
from app.schemas.routes import (
    NoRouteReason,
    RoutePlanRequest,
    RoutePlanResponse,
    RoutePlanSuccess,
    RoutePlanUnavailable,
    RouteStop,
    RoutingProvenance,
)
from app.services.retrieval_service import RetrievalService
from app.services.route_intent import STOP_CATEGORIES, requested_stages

# Planning allowances, not observed visit durations or promises of admission.
VISIT_MINUTES: dict[Category, int] = {
    "cafe": 15,
    "restaurant": 20,
    "fast_food": 10,
    "food_court": 15,
    "library": 15,
    "cinema": 15,
    "theatre": 15,
    "arts_centre": 15,
    "community_centre": 10,
    "museum": 20,
    "gallery": 15,
    "attraction": 10,
    "artwork": 5,
    "viewpoint": 5,
    "park": 10,
    "garden": 10,
    "playground": 10,
    "mall": 15,
    "books": 10,
}


class WalkingAdapter(Protocol):
    def matrix(self, request: MatrixRequest) -> MatrixResult: ...

    def directions(self, request: DirectionsRequest) -> RouteResult: ...


@dataclass(frozen=True)
class Candidate:
    poi: PublicPOI
    rank: int
    nearby_fallback: bool = False
    stage: int | None = None

    @property
    def point(self) -> GeoPoint:
        return GeoPoint(longitude=self.poi.longitude, latitude=self.poi.latitude)

    @property
    def visit_seconds(self) -> int:
        return VISIT_MINUTES[self.poi.category] * 60


def haversine(a: GeoPoint, b: GeoPoint) -> float:
    """Straight-line meters for filtering/snap checks, never walking metrics."""
    latitude_delta = radians(b.latitude - a.latitude)
    longitude_delta = radians(b.longitude - a.longitude)
    term = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(a.latitude)) * cos(radians(b.latitude)) * sin(longitude_delta / 2) ** 2
    )
    return 6371000 * 2 * asin(sqrt(min(1.0, max(0.0, term))))


def stop_explanation(candidate: Candidate, language: Language) -> str:
    # Only enum categories and our planned allowances enter prose, never OSM text.
    category, minutes = candidate.poi.category, candidate.visit_seconds // 60
    if language == "kk":
        return (
            f"OSM санаты: {category}. Аялдамаға жоспарланған уақыт: {minutes} мин; "
            "бұл өлшенген уақыт емес. Қазір ашық екені мен кіру мүмкіндігі белгісіз."
        )
    if language == "ru":
        return (
            f"Категория OSM: {category}. На остановку запланировано {minutes} мин; "
            "это оценка, а не измерение. Открытие сейчас и возможность входа неизвестны."
        )
    return (
        f"OSM category: {category}. Planned visit: {minutes} min; "
        "this is an allowance, not a measurement. Current opening and admission are unknown."
    )


def no_route_explanation(reason: NoRouteReason, language: Language) -> str:
    messages = {
        "no_candidates": (
            "Рядом со стартом не найдено подходящих точек OSM.",
            "Бастапқы нүкте маңында жарамды OSM орындары табылмады.",
            "No eligible OSM places were found near the start.",
        ),
        "unreachable": (
            "ORS не подтвердил доступные переходы между выбранными точками.",
            "ORS таңдалған нүктелер арасындағы жаяу жолды растамады.",
            "ORS did not confirm reachable walking legs between the selected points.",
        ),
        "budget_exceeded": (
            "Не удалось подтвердить маршрут в пределах заданного времени.",
            "Берілген уақытқа сәйкес маршрут расталмады.",
            "A route within the requested time budget could not be confirmed.",
        ),
        "ors_unconfigured": (
            "Маршрутизация не настроена: на сервере отсутствует ORS_API_KEY.",
            "Маршруттау бапталмаған: серверде ORS_API_KEY жоқ.",
            "Routing is not configured: the server has no ORS_API_KEY.",
        ),
        "ors_timeout": (
            "Сервис ORS не ответил вовремя. Повторите попытку позже.",
            "ORS қызметі уақытында жауап бермеді. Кейінірек қайталаңыз.",
            "ORS timed out. Please try again later.",
        ),
        "ors_unavailable": (
            "Сервис ORS недоступен или отклонил запрос. Маршрут не подтверждён.",
            "ORS қызметі қолжетімсіз немесе сұрауды қабылдамады. Маршрут расталмады.",
            "ORS is unavailable or rejected the request. No route was confirmed.",
        ),
        "ors_invalid_response": (
            "ORS вернул некорректные данные; маршрут не подтверждён.",
            "ORS жарамсыз деректер қайтарды; маршрут расталмады.",
            "ORS returned invalid data; no route was confirmed.",
        ),
    }
    return messages[reason][{"ru": 0, "kk": 1, "en": 2}[language]]


class RoutePlanner:
    def __init__(
        self, retrieval: RetrievalService, adapter: WalkingAdapter, settings: Settings
    ) -> None:
        self.retrieval = retrieval
        self.adapter = adapter
        self.settings = settings
        # Public IDs are allowlisted by the request model; no user input becomes a path.
        catalog = AnchorCatalog.model_validate_json((ROOT / "shared/anchors.json").read_bytes())
        self.anchors = {anchor.id: anchor for anchor in catalog.anchors}

    def _eligible(self, poi: PublicPOI, anchor: Anchor) -> bool:
        if (
            not isfinite(poi.longitude)
            or not isfinite(poi.latitude)
            or not -180 <= poi.longitude <= 180
            or not -90 <= poi.latitude <= 90
        ):
            return False
        distance = haversine(
            anchor.location, GeoPoint(longitude=poi.longitude, latitude=poi.latitude)
        )
        # Do not recommend a visit to the same representative coordinate as the start.
        return 1 <= distance <= self.settings.route_nearby_radius_m

    def _candidates(
        self, request: RoutePlanRequest
    ) -> tuple[list[Candidate], list[str], RetrievalMode]:
        anchor = self.anchors[request.start_anchor_id]
        found = self.retrieval.search(
            SearchRequest(query=request.query, top_k=10, language=request.language)
        )
        repository = self.retrieval.repository
        stages = requested_stages(request.query)
        if stages:
            # Retrieve each required category within the geographic filter,
            # rather than letting global top-k exhaust one category or region.
            warnings = [w for w in found.warnings if w != "walking_access_not_checked"]
            if self.settings.route_max_candidates < len(stages):
                return (
                    [],
                    [*warnings, "required_stages_exceed_candidate_limit"],
                    found.retrieval_mode,
                )
            grouped: list[list[PublicPOI]] = []
            for kind in stages:
                eligible = [
                    poi
                    for poi in repository.items
                    if poi.category in STOP_CATEGORIES[kind] and self._eligible(poi, anchor)
                ]
                eligible.sort(
                    key=lambda poi: (
                        not bool(poi.name),
                        haversine(
                            anchor.location,
                            GeoPoint(longitude=poi.longitude, latitude=poi.latitude),
                        ),
                        poi.id,
                    )
                )
                if not eligible:
                    return [], [*warnings, f"required_stop_missing:{kind}"], found.retrieval_mode
                grouped.append(eligible)
            staged: list[Candidate] = []
            quota, remainder = divmod(self.settings.route_max_candidates, len(stages))
            for stage, eligible in enumerate(grouped):
                staged.extend(
                    Candidate(poi, rank, stage=stage)
                    for rank, poi in enumerate(
                        eligible[: quota + int(stage < remainder)],
                        start=1,
                    )
                )
            return staged, warnings, found.retrieval_mode
        candidates: list[Candidate] = []
        seen: set[str] = set()
        for hit in found.results:
            # Resolve IDs against the immutable dataset, not provider-supplied coordinates.
            poi = repository.by_id.get(hit.poi.id)
            if poi is not None and poi.id not in seen and self._eligible(poi, anchor):
                candidates.append(Candidate(poi, hit.rank))
                seen.add(poi.id)
        candidates.sort(key=lambda candidate: (candidate.rank, candidate.poi.id))
        target = min(3, self.settings.route_max_candidates)
        if len(candidates) < target and not requests_pizza(request.query):
            nearby = [
                poi
                for poi in repository.items
                if poi.id not in seen and self._eligible(poi, anchor)
            ]
            nearby.sort(
                key=lambda poi: (
                    haversine(
                        anchor.location, GeoPoint(longitude=poi.longitude, latitude=poi.latitude)
                    ),
                    poi.id,
                )
            )
            candidates.extend(
                Candidate(poi, 11 + index, nearby_fallback=True)
                for index, poi in enumerate(nearby[: target - len(candidates)])
            )
        warnings = [w for w in found.warnings if w != "walking_access_not_checked"]
        return candidates[: self.settings.route_max_candidates], warnings, found.retrieval_mode

    def _leg(self, matrix: MatrixResult, source: int, destination: int) -> float | None:
        data = matrix.data
        start, end = data.sources[source], data.destinations[destination]
        if (
            start is None
            or end is None
            or start.snapped_distance > self.settings.route_snap_radius_m
            or end.snapped_distance > self.settings.route_snap_radius_m
            or data.distances[source][destination] is None
        ):
            return None
        return data.durations[source][destination]

    def _select(
        self, candidates: list[Candidate], matrix: MatrixResult, request: RoutePlanRequest
    ) -> list[Candidate]:
        if requested_stages(request.query):
            return self._select_stages(candidates, matrix, request)
        selected: list[Candidate] = []
        indices: list[int] = []
        elapsed = 0.0
        current = 0
        while len(selected) < 3:
            feasible: list[tuple[int, float, str, int, float]] = []
            for index, candidate in enumerate(candidates, start=1):
                if index in indices or any(
                    haversine(candidate.point, previous.point) < 1 for previous in selected
                ):
                    continue
                outward = self._leg(matrix, current, index)
                returning = self._leg(matrix, index, 0) if request.round_trip else 0.0
                if outward is None or returning is None:
                    continue
                total = elapsed + outward + candidate.visit_seconds + returning
                if total > request.duration_minutes * 60:
                    continue
                utility = (1 / candidate.rank) / max(
                    1, outward + candidate.visit_seconds + returning
                )
                feasible.append(
                    (int(candidate.nearby_fallback), -utility, candidate.poi.id, index, outward)
                )
            if not feasible:
                break
            _, _, _, chosen, walking = min(feasible)
            candidate = candidates[chosen - 1]
            selected.append(candidate)
            indices.append(chosen)
            elapsed += walking + candidate.visit_seconds
            current = chosen
        return selected

    def _select_stages(
        self,
        candidates: list[Candidate],
        matrix: MatrixResult,
        request: RoutePlanRequest,
        *,
        ignore_budget: bool = False,
    ) -> list[Candidate]:
        stages = requested_stages(request.query)
        options = [
            [
                index
                for index, candidate in enumerate(candidates, start=1)
                if candidate.stage == stage
            ]
            for stage in range(len(stages))
        ]
        best: tuple[float, int, tuple[str, ...]] | None = None
        selected: list[Candidate] = []
        # At most 10 candidates and two required stages: bounded complete-path
        # search. Budget includes visits, every directed leg and the return leg.
        for indices in product(*options):
            stops = [candidates[index - 1] for index in indices]
            if any(
                haversine(first.point, second.point) < 1
                for i, first in enumerate(stops)
                for second in stops[i + 1 :]
            ):
                continue
            path = [0, *indices, *([0] if request.round_trip else [])]
            legs = [
                self._leg(matrix, start, end) for start, end in zip(path, path[1:], strict=False)
            ]
            if any(leg is None for leg in legs):
                continue
            total = sum(leg for leg in legs if leg is not None) + sum(
                stop.visit_seconds for stop in stops
            )
            if not ignore_budget and total > request.duration_minutes * 60:
                continue
            priority = (
                total,
                sum(stop.rank for stop in stops),
                tuple(stop.poi.id for stop in stops),
            )
            if best is None or priority < best:
                best, selected = priority, stops
        return selected

    def _directions(self, anchor: Anchor, stops: list[Candidate], round_trip: bool) -> RouteResult:
        points = [anchor.location, *[stop.point for stop in stops]]
        if round_trip:
            points.append(anchor.location)
        route = self.adapter.directions(
            DirectionsRequest(locations=points, snap_radius_m=self.settings.route_snap_radius_m)
        )
        feature = route.geojson.features[0]
        waypoints = feature.properties.way_points
        if (
            route.duration_seconds <= 0
            or route.distance_meters <= 0
            or len(waypoints) != len(points)
            or any(
                haversine(
                    point,
                    GeoPoint(
                        longitude=feature.geometry.coordinates[index][0],
                        latitude=feature.geometry.coordinates[index][1],
                    ),
                )
                > self.settings.route_snap_radius_m + 1
                for point, index in zip(points, waypoints, strict=True)
            )
        ):
            raise GeoError("invalid_response", "Route waypoints do not match the requested points")
        return route

    def plan(self, request: RoutePlanRequest) -> RoutePlanResponse:
        anchor = self.anchors[request.start_anchor_id]
        candidates, warnings, mode = self._candidates(request)
        warnings.extend(
            [
                "osm_source_only",
                "preferences_not_verified",
                "current_opening_status_unknown",
                "entrance_and_accessibility_not_verified",
                "visit_times_are_planned_estimates",
                "route_is_snapped_to_ors_walking_graph",
            ]
        )
        if anchor.coordinate_kind == "bounding_box_center":
            warnings.append(f"bounding_box_center_not_verified_entrance:{anchor.id}")
        provenance = RoutingProvenance()

        def unavailable(reason: NoRouteReason) -> RoutePlanUnavailable:
            explanation = no_route_explanation(reason, request.language)
            if reason == "no_candidates" and requests_pizza(request.query):
                radius = f"{self.settings.route_nearby_radius_m:g}"
                explanation = {
                    "ru": f"В данных OSM не найдено пиццерии в пределах {radius} м "
                    "от выбранного старта. Выберите другую точку старта.",
                    "kk": f"OSM деректерінде бастапқы нүктеден {radius} м ішінде "
                    "пиццерия табылмады. Басқа бастапқы нүктені таңдаңыз.",
                    "en": f"No pizzeria was found in the OSM dataset within {radius} m "
                    "of the selected start. Choose another starting point.",
                }[request.language]
            elif reason == "no_candidates" and requested_stages(request.query):
                explanation = {
                    "ru": "Не найдены все необходимые места для запрошенного маршрута "
                    "рядом с выбранным стартом. Выберите другую точку старта.",
                    "kk": "Таңдалған бастапқы нүкте маңында сұралған маршрутқа қажетті "
                    "орындардың бәрі табылмады. Басқа бастапқы нүктені таңдаңыз.",
                    "en": "Not all required stops were found near the selected start. "
                    "Choose another starting point.",
                }[request.language]
            return RoutePlanUnavailable(
                start_anchor_id=request.start_anchor_id,
                start_anchor=anchor,
                requested_duration_minutes=request.duration_minutes,
                round_trip=request.round_trip,
                language=request.language,
                retrieval_mode=mode,
                recommendation=explanation,
                reason=reason,
                warnings=sorted(set(warnings)),
                routing_provenance=provenance,
                dataset=self.retrieval.repository.metadata,
            )

        if not candidates:
            return unavailable("no_candidates")
        try:
            matrix = self.adapter.matrix(
                MatrixRequest(
                    locations=[anchor.location, *[candidate.point for candidate in candidates]]
                )
            )
            provenance.matrix = matrix.provenance
            selected = self._select(candidates, matrix, request)
            if not selected:
                # Distinguish disconnected graph from a connected but unaffordable visit.
                connected = (
                    bool(self._select_stages(candidates, matrix, request, ignore_budget=True))
                    if requested_stages(request.query)
                    else any(
                        self._leg(matrix, 0, i) is not None
                        and (not request.round_trip or self._leg(matrix, i, 0) is not None)
                        for i in range(1, len(candidates) + 1)
                    )
                )
                return unavailable("budget_exceeded" if connected else "unreachable")
            # One initial Directions request and at most one recalculation after dropping a stop.
            for attempt in range(2):
                route = self._directions(anchor, selected, request.round_trip)
                provenance.directions = route.provenance
                visiting_seconds = sum(candidate.visit_seconds for candidate in selected)
                if route.duration_seconds + visiting_seconds <= request.duration_minutes * 60:
                    return self._success(request, selected, route, provenance, warnings, mode)
                warnings.append("directions_exceeded_budget")
                if requested_stages(request.query):
                    # Dropping the park or cafe would violate the user's request.
                    return unavailable("budget_exceeded")
                if attempt == 0 and len(selected) > 1:
                    selected = selected[:-1]
                    warnings.append("stop_removed_after_directions_check")
                else:
                    return unavailable("budget_exceeded")
        except GeoError as error:
            # Never expose exception text, HTTP bodies, credentials or request headers.
            reason: NoRouteReason = "ors_unavailable"
            if error.code == "configuration_missing":
                reason = "ors_unconfigured"
            elif error.code == "invalid_response":
                reason = "ors_invalid_response"
            elif error.code == "transport_error":
                warnings.append("ors_transport_error")
            elif error.provider_code in {2010, 2099, 6010}:
                reason = "unreachable"
            return unavailable(reason)
        except httpx.TimeoutException:
            return unavailable("ors_timeout")
        except httpx.HTTPError:
            return unavailable("ors_unavailable")
        except (ValidationError, ValueError, IndexError, TypeError):
            return unavailable("ors_invalid_response")
        return unavailable("budget_exceeded")

    def _success(
        self,
        request: RoutePlanRequest,
        selected: list[Candidate],
        route: RouteResult,
        provenance: RoutingProvenance,
        warnings: list[str],
        mode: RetrievalMode,
    ) -> RoutePlanSuccess:
        stops = []
        for order, candidate in enumerate(selected, start=1):
            poi = candidate.poi
            if poi.coordinate_kind == "bounding_box_center":
                warnings.append(f"bounding_box_center_not_verified_entrance:{poi.id}")
            warnings.extend(poi.quality_warnings)
            if candidate.nearby_fallback:
                warnings.append("nearby_fallback_not_query_match")
            stops.append(
                RouteStop(
                    **poi.model_dump(),
                    order=order,
                    visiting_minutes=candidate.visit_seconds // 60,
                    selection_source="nearby_fallback"
                    if candidate.nearby_fallback
                    else "retrieval",
                    explanation=stop_explanation(candidate, request.language),
                )
            )
        if route.geojson.features[0].properties.warnings:
            warnings.append("ors_directions_warning")
        visiting = sum(stop.visiting_minutes for stop in stops)
        if request.language == "kk":
            recommendation = (
                f"OSM деректерінен {len(stops)} аялдама таңдалды. Жаяу уақыт пен қашықтық ORS-тен; "
                f"аялдамаларға жоспарланған уақыт: {visiting} мин. "
                "Қалауларға сәйкестік расталмаған."
            )
            fallback = " Кейбір орындар сұрау бойынша емес, жақын орналасуы бойынша таңдалды."
        elif request.language == "ru":
            recommendation = (
                f"Выбрано остановок по данным OSM: {len(stops)}. Пешее время и расстояние — ORS; "
                f"на посещения запланировано {visiting} мин. "
                "Соответствие пожеланиям не подтверждено."
            )
            fallback = " Часть мест выбрана по близости, без подтверждённого соответствия запросу."
        else:
            recommendation = (
                f"Selected {len(stops)} OSM stops. Walking time and distance are from ORS; "
                f"planned visits: {visiting} min. Preference matching is not verified."
            )
            fallback = " Some places were chosen by proximity without a confirmed query match."
        if any(candidate.nearby_fallback for candidate in selected):
            recommendation += fallback
        stages = requested_stages(request.query)
        if stages:
            labels = {
                "ru": {"coffee": "кофейня", "park": "прогулка в парке или саду"},
                "kk": {"coffee": "кофехана", "park": "саябақта немесе бақта серуендеу"},
                "en": {"coffee": "cafe", "park": "park or garden walk"},
            }[request.language]
            recommendation = " → ".join(labels[kind] for kind in stages) + ". " + recommendation
        return RoutePlanSuccess(
            start_anchor_id=request.start_anchor_id,
            start_anchor=self.anchors[request.start_anchor_id],
            requested_duration_minutes=request.duration_minutes,
            round_trip=request.round_trip,
            language=request.language,
            retrieval_mode=mode,
            stops=stops,
            walking_minutes=route.duration_seconds / 60,
            visiting_minutes=float(visiting),
            estimated_total_minutes=route.duration_seconds / 60 + visiting,
            total_distance_meters=route.distance_meters,
            route_geojson=route.geojson,
            recommendation=recommendation,
            warnings=sorted(set(warnings)),
            routing_provenance=provenance,
            dataset=self.retrieval.repository.metadata,
        )
