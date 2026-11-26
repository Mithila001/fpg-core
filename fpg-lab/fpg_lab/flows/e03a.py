"""Exact discrete room sizing. This module does not depend on the Lab UI."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict, deque
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations, product
from math import ceil, floor
from time import monotonic

from fpg_core.domain import RoomSizeSpec, RoomType, RoomWidthAxis

from fpg_lab.e03a_config import ROOM_TYPES, Aspect, Configuration, room_label

Dimensions = dict[int, tuple[tuple[int, int], ...]]
RuleKey = tuple[RoomType, RoomType]


class AnalysisLimit(Exception):
    pass


@dataclass(frozen=True)
class AreaRange:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if (
            type(self.minimum) is not int
            or type(self.maximum) is not int
            or not 0 < self.minimum <= self.maximum
        ):
            raise ValueError("Enter positive whole areas with minimum at most maximum.")


@dataclass(frozen=True)
class Variation:
    difference: int
    spread: Fraction
    restricted_by_other_rules: bool


@dataclass(frozen=True)
class Edge:
    source: int
    target: int
    multiplier: Fraction
    rule: RuleKey
    minimum: bool = False

    def required(self, area: int) -> int:
        n = area * self.multiplier.numerator
        return -(-n // self.multiplier.denominator)


@dataclass(frozen=True)
class Promotion:
    edge: Edge
    source_area: int
    required_area: int
    cause: Promotion | None


@dataclass
class Analysis:
    status: str = "incomplete"
    room_ids: tuple[str, ...] = ()
    dimensions: dict[str, Dimensions] = field(default_factory=dict)
    supported: dict[str, tuple[int, ...]] = field(default_factory=dict)
    area_ranges: dict[str, tuple[tuple[int, int], ...]] = field(default_factory=dict)
    variation: dict[RoomType, Variation] = field(default_factory=dict)
    witness: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    inactive: tuple[RuleKey, ...] = ()
    diagnostics: list[str] = field(default_factory=list)
    category: str | None = None

    def flexibility(self, room: str) -> float | None:
        original = len(self.dimensions.get(room, {}))
        remaining = self.supported.get(room)
        return 100 * len(remaining) / original if original and remaining is not None else None

    def ranges(self, room: str) -> tuple[tuple[int, int], ...]:
        return self.area_ranges.get(room, ())


def enumerate_dimensions(
    spec: RoomSizeSpec, aspect: Aspect | None, precision: int, deadline: float
) -> Dimensions:
    minimum, maximum = ceil(spec.min_width), floor(spec.max_width)
    min_area, max_area = ceil(spec.min_area), floor(spec.max_area)
    if minimum > maximum or min_area > max_area:
        return {}
    low = round(float(aspect.min_ratio) * precision) if aspect else 0
    high = round(float(aspect.max_ratio) * precision) if aspect else None
    if high == 0:
        return {}
    by_area: dict[int, list[tuple[int, int]]] = defaultdict(list)
    pair_count = 0
    # For ANY, enumerate two disjoint regions where either span meets maximum width.
    regions = [(minimum, maximum, max_area)] if spec.width_axis is RoomWidthAxis.X else []
    if spec.width_axis is RoomWidthAxis.Y:
        regions = [(minimum, max_area // minimum, maximum)]
    elif spec.width_axis is RoomWidthAxis.ANY:
        regions = [(minimum, maximum, max_area), (maximum + 1, max_area // minimum, maximum)]
    for x_min, x_max, y_max in regions:
        for x in range(x_min, min(x_max, max_area // minimum) + 1):
            if monotonic() >= deadline:
                raise AnalysisLimit("Dimension enumeration reached the analysis time limit")
            y_min = max(minimum, -(-min_area // x))
            if high is not None:
                y_min = max(y_min, -(-(x * precision) // high))
            y_limit = min(y_max, max_area // x)
            if low:
                y_limit = min(y_limit, x * precision // low)
            pair_count += max(0, y_limit - y_min + 1)
            if pair_count > 100_000:
                raise AnalysisLimit("A room specification exceeds 100,000 dimension pairs")
            for y in range(y_min, y_limit + 1):
                by_area[x * y].append((x, y))
    return {area: tuple(by_area[area]) for area in sorted(by_area)}


def propagate(
    domains: tuple[tuple[int, ...], ...],
    outgoing: tuple[tuple[Edge, ...], ...],
    deadline: float,
    fixed: tuple[int, int] | None = None,
    *,
    trace: bool = False,
) -> tuple[list[int] | None, Promotion | None]:
    values = [domain[0] for domain in domains]
    if fixed is not None:
        values[fixed[0]] = fixed[1]
    queue = deque(i for i, edges in enumerate(outgoing) if edges)
    pending = set(queue)
    causes: dict[int, Promotion] = {}
    while queue:
        if monotonic() >= deadline:
            raise AnalysisLimit("Area propagation reached the analysis time limit")
        source = queue.popleft()
        pending.remove(source)
        for edge in outgoing[source]:
            target = edge.target
            required = edge.required(values[source])
            if required <= values[target]:
                continue
            domain = domains[target]
            index = bisect_left(domain, required)
            promotion = (
                Promotion(edge, values[source], required, causes.get(source)) if trace else None
            )
            if index == len(domain) or (fixed is not None and target == fixed[0]):
                return None, promotion
            values[target] = domain[index]
            if promotion is not None:
                causes[target] = promotion
            if outgoing[target] and target not in pending:
                queue.append(target)
                pending.add(target)
    return values, None


def _outgoing(count: int, edges: tuple[Edge, ...]) -> tuple[tuple[Edge, ...], ...]:
    by_source: list[list[Edge]] = [[] for _ in range(count)]
    for edge in edges:
        by_source[edge.source].append(edge)
    return tuple(tuple(row) for row in by_source)


def _relationships(
    config: Configuration, indexes: dict[RoomType, list[int]]
) -> tuple[tuple[Edge, ...], tuple[RuleKey, ...]]:
    edges = []
    inactive = []
    for rule in config.cross_type_rules:
        key = (rule.compared_type, rule.reference_type)
        if not all(indexes[room] for room in key):
            inactive.append(key)
        for compared, reference in product(*(indexes[room] for room in key)):
            if rule.min_ratio is not None:
                edges.append(Edge(reference, compared, Fraction(rule.min_ratio), key, minimum=True))
            if rule.max_ratio is not None:
                edges.append(Edge(compared, reference, 1 / Fraction(rule.max_ratio), key))
    for rule in config.same_type_rules:
        key = (rule.room_type, rule.room_type)
        if len(indexes[rule.room_type]) < 2:
            inactive.append(key)
        multiplier = 1 / (1 + Fraction(rule.maximum_spread_ratio))
        for first, second in combinations(indexes[rule.room_type], 2):
            edges.extend(
                (Edge(first, second, multiplier, key), Edge(second, first, multiplier, key))
            )
    return tuple(edges), tuple(inactive)


def _describe(rule: RuleKey) -> str:
    a, b = (room_label(room.value) for room in rule)
    return f"{a} spread" if a == b else f"{a} to {b} area ratio"


def _relaxation(edges: tuple[Edge, ...], witness: list[int], key: RuleKey) -> list[str]:
    """Find decimal bounds that admit this witness under every other rule."""
    changes = []
    scale = 10_000
    for edge in edges:
        if edge.rule != key or edge.required(witness[edge.source]) <= witness[edge.target]:
            continue
        limit = Fraction(witness[edge.target], witness[edge.source])
        if key[0] == key[1]:
            changes.append(("maximum spread", ceil((1 / limit - 1) * scale)))
        elif edge.minimum:
            changes.append(("minimum ratio", floor(limit * scale)))
        else:
            changes.append(("maximum ratio", ceil(scale / limit)))
    recommendations = []
    for label in dict.fromkeys(label for label, _ in changes):
        values = [value for name, value in changes if name == label]
        value = min(values) if label == "minimum ratio" else max(values)
        whole, fraction = divmod(value, scale)
        decimal = f"{whole}.{fraction:04}".rstrip("0").rstrip(".")
        recommendations.append(f"{label} {decimal}" if value else f"clear the {label}")
    return recommendations


def _diagnose(
    result: Analysis,
    domains: tuple[tuple[int, ...], ...],
    edges: tuple[Edge, ...],
    lock_induced: bool,
    deadline: float,
) -> None:
    count = len(domains)
    _, failure = propagate(domains, _outgoing(count, edges), deadline, trace=True)
    keys = tuple(dict.fromkeys(edge.rule for edge in edges))
    result.category = "Area-range lock" if lock_induced else "Combined"
    for key in keys:
        value, _ = propagate(
            domains, _outgoing(count, tuple(e for e in edges if e.rule == key)), deadline
        )
        if value is None:
            kind = "Same-type" if key[0] == key[1] else "Cross-type"
            if result.category == "Combined":
                result.category = kind
            result.diagnostics.append(f"{kind} rule fails on its own — {_describe(key)}")
    chain = []
    while failure is not None:
        edge = failure.edge
        source, target = (result.room_ids[i] for i in (edge.source, edge.target))
        original = result.dimensions[target]
        chain.append(
            f"{_describe(edge.rule)} · {room_label(source)} at {failure.source_area} units² "
            f"requires {room_label(target)} ≥ {failure.required_area} units² "
            f"(original achievable range {min(original)}–{max(original)}, current maximum {domains[edge.target][-1]})."
        )
        failure = failure.cause
    result.diagnostics.extend(reversed(tuple(dict.fromkeys(reversed(chain)))))
    if lock_induced:
        result.diagnostics.append("Clearing the current locks restores a compatible configuration.")
    for removed in keys:
        witness, _ = propagate(
            domains, _outgoing(count, tuple(e for e in edges if e.rule != removed)), deadline
        )
        if witness is not None:
            adjustments = _relaxation(edges, witness, removed)
            if adjustments == ["clear the minimum ratio"] and not any(
                edge.rule == removed and not edge.minimum for edge in edges
            ):
                result.diagnostics.append(
                    f"Removing {_describe(removed)} would make this scenario compatible."
                )
            elif adjustments:
                result.diagnostics.append(
                    f"Compatible adjustment for {_describe(removed)} · {', '.join(adjustments)}."
                )
    result.diagnostics.append(
        "Try widening an affected room’s size bounds or relaxing a contributing ratio."
    )


def analyze(
    config: Configuration,
    locks: dict[RoomType, AreaRange] | None = None,
    baseline: Analysis | None = None,
    *,
    seconds: float = 5,
) -> Analysis:
    """Use a matching unlocked baseline when provided for the same configuration."""
    locks = locks or {}
    deadline = monotonic() + seconds
    result = Analysis()
    try:
        if sum(room.count for room in config.rooms.values()) > 64:
            raise AnalysisLimit("The analysis supports at most 64 active room instances")
        indexes: dict[RoomType, list[int]] = {room: [] for room in ROOM_TYPES}
        ids: list[str] = []
        by_spec: dict[tuple[RoomSizeSpec, Aspect | None], Dimensions] = {}
        for room_type in ROOM_TYPES:
            spec = config.rooms[room_type]
            for number in range(1, spec.count + 1):
                room_id = f"{room_type.value}_{number}"
                indexes[room_type].append(len(ids))
                ids.append(room_id)
                if baseline and room_id in baseline.dimensions:
                    dims = baseline.dimensions[room_id]
                else:
                    key = spec.size_spec(room_type), config.aspect_for(room_type)
                    if key not in by_spec:
                        by_spec[key] = enumerate_dimensions(*key, config.aspect_precision, deadline)
                    dims = by_spec[key]
                result.dimensions[room_id] = dims
        result.room_ids = tuple(ids)
        edges, result.inactive = _relationships(config, indexes)
        empty = [room for room in ids if not result.dimensions[room]]
        restricted: list[tuple[int, ...]] = [()] * len(ids)
        unavailable = []
        for kind, group in indexes.items():
            if not group:
                continue
            original = tuple(result.dimensions[ids[group[0]]])
            lock = locks.get(kind)
            allowed = original
            if lock is not None:
                allowed = original[
                    bisect_left(original, lock.minimum) : bisect_right(original, lock.maximum)
                ]
                if original and not allowed:
                    unavailable.append((kind, lock))
            for i in group:
                restricted[i] = allowed
        if empty or unavailable:
            result.status = "incompatible"
            result.category = "Dimension" if empty else "Area-range lock"
            for room in empty:
                kind = RoomType(room.rsplit("_", 1)[0])
                settings = config.rooms[kind]
                aspect = config.aspect_for(kind)
                aspect_range = (
                    f"{aspect.min_ratio}–{aspect.max_ratio}"
                    if aspect is not None
                    else "unrestricted"
                )
                result.diagnostics.append(
                    f"{room_label(room)} has no integer dimensions with width "
                    f"{settings.min_width}–{settings.max_width}, area "
                    f"{settings.min_area}–{settings.max_area}, and X/Y ratio {aspect_range}. "
                    "Try widening one of those bounds."
                )
            for kind, lock in unavailable:
                result.diagnostics.append(
                    f"{room_label(kind.value)} has no achievable area within the requested "
                    f"{lock.minimum}–{lock.maximum} units² range."
                )
            result.supported = dict.fromkeys(ids, ())
            return result
        domains = tuple(restricted)
        outgoing = _outgoing(len(ids), edges)
        least, _ = propagate(domains, outgoing, deadline)
        if least is None:
            result.status = "incompatible"
            result.supported = dict.fromkeys(ids, ())
            lock_induced = bool(locks) and (
                baseline.status == "compatible"
                if baseline is not None
                else propagate(
                    tuple(tuple(result.dimensions[room]) for room in ids), outgoing, deadline
                )[0]
                is not None
            )
            _diagnose(result, domains, edges, lock_induced, deadline)
            return result
        result.witness = {
            room: (*result.dimensions[room][area][0], area)
            for room, area in zip(ids, least, strict=True)
        }
        connected = {edge.source for edge in edges} | {edge.target for edge in edges}
        for group in indexes.values():
            if not group:
                continue
            i = group[0]
            supported = domains[i]
            if i in connected:
                if locks and baseline and baseline.status == "compatible":
                    prior = set(baseline.supported[ids[i]])
                    supported = tuple(area for area in supported if area in prior)
                supported = tuple(
                    area
                    for area in supported
                    if area >= least[i]
                    and (
                        area == least[i]
                        or propagate(domains, outgoing, deadline, (i, area))[0] is not None
                    )
                )
            for member in group:
                result.supported[ids[member]] = supported
        cached_ranges = {}
        for room, areas in result.supported.items():
            dimensions = result.dimensions[room]
            key_ids = (id(dimensions), id(areas))
            if key_ids not in cached_ranges:
                width, length = zip(
                    *(pair for area in areas for pair in dimensions[area]), strict=True
                )
                cached_ranges[key_ids] = (
                    (areas[0], areas[-1]),
                    (min(width), max(width)),
                    (min(length), max(length)),
                )
            result.area_ranges[room] = cached_ranges[key_ids]
        result.variation = _variation(config, indexes, edges, domains, result, deadline)
        result.status = "compatible"
    except (AnalysisLimit, OverflowError) as exc:
        result.diagnostics.append(str(exc))
    return result


def _variation(
    config: Configuration,
    indexes: dict[RoomType, list[int]],
    edges: tuple[Edge, ...],
    domains: tuple[tuple[int, ...], ...],
    result: Analysis,
    deadline: float,
) -> dict[RoomType, Variation]:
    # Negate areas and reverse each bound to reuse propagation for greatest assignments.
    negative_by_domain = {
        id(domains[group[0]]): tuple(-area for area in reversed(domains[group[0]]))
        for group in indexes.values()
        if group
    }
    negative = tuple(negative_by_domain[id(domain)] for domain in domains)
    reversed_edges = tuple(
        Edge(edge.target, edge.source, 1 / edge.multiplier, edge.rule) for edge in edges
    )
    outgoing = _outgoing(len(domains), reversed_edges)
    tolerance = {
        rule.room_type: Fraction(rule.maximum_spread_ratio) for rule in config.same_type_rules
    }
    variations = {}
    for kind, group in indexes.items():
        if len(group) < 2:
            continue
        first, second = group[:2]
        domain = domains[first]
        limit = tolerance.get(kind)
        difference = own_difference = 0
        spread = own_spread = Fraction(0)
        for smaller in domain:
            if monotonic() >= deadline:
                raise AnalysisLimit("Same-type variation reached the analysis time limit")
            if limit is None:
                same_only = domain[-1]
            else:
                same_only = domain[bisect_right(domain, floor(smaller * (1 + limit))) - 1]
            own_difference = max(own_difference, same_only - smaller)
            own_spread = max(own_spread, Fraction(same_only - smaller, smaller))
        for smaller in result.supported[result.room_ids[first]]:
            greatest, _ = propagate(negative, outgoing, deadline, (first, -smaller))
            assert greatest is not None  # The fixed area already has global support.
            delta = -greatest[second] - smaller
            difference = max(difference, delta)
            spread = max(spread, Fraction(delta, smaller))
        variations[kind] = Variation(
            difference, spread, difference < own_difference or spread < own_spread
        )
    return variations
