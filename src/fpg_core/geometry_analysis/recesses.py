from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from heapq import heappop, heappush

from shapely.affinity import affine_transform
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


@dataclass(slots=True)
class Section:
    polygon: BaseGeometry
    width: float
    depth: float
    level: int
    parents: tuple[int, ...]
    direction: tuple[int, int]
    entrance: BaseGeometry | None


@dataclass(slots=True)
class Recess:
    polygon: BaseGeometry
    entrance: LineString
    direction: tuple[int, int]
    depth: float
    sections: tuple[Section, ...]
    branch_count: int


def polygons(geometry: BaseGeometry) -> tuple[Polygon, ...]:
    if geometry.is_empty:
        return ()
    if isinstance(geometry, Polygon):
        return (geometry,)
    return tuple(
        part for item in getattr(geometry, "geoms", ()) for part in polygons(item)
    )


def lines(geometry: BaseGeometry) -> tuple[LineString, ...]:
    if geometry.is_empty:
        return ()
    if isinstance(geometry, LineString):
        return (geometry,)
    return tuple(
        part for item in getattr(geometry, "geoms", ()) for part in lines(item)
    )


def detect_recesses(footprint: BaseGeometry, tolerance: float, *, include_section_entrances: bool = False) -> tuple[Recess, ...]:
    # Interior rings belong to the enclosed-void evaluator.
    solid = unary_union(
        [Polygon(poly.exterior) for poly in polygons(footprint)]
    ).simplify(0)
    if solid.is_empty:
        return ()
    candidates = [
        *_sweep(solid, False, tolerance, include_section_entrances),
        *_sweep(_swap_axes(solid), True, tolerance, include_section_entrances),
    ]
    regions: list[Recess] = []
    for recess in sorted(candidates, key=lambda item: -item.polygon.area):
        container = next(
            (
                region
                for region in regions
                if region.polygon.area > recess.polygon.area
                and region.polygon.covers(recess.polygon)
            ),
            None,
        )
        if container is None:
            regions.append(recess)
        else:
            _add_cross_sections(container, recess, tolerance)
    return tuple(regions)


def _add_cross_sections(region: Recess, arm: Recess, tolerance: float) -> None:
    # Perpendicular blind arms can have a narrow width along the original sweep axis.
    # Keep their measurements without counting the same space as another recess.
    parents = tuple(
        index
        for index, section in enumerate(region.sections)
        if bool(section.direction[0]) == bool(region.direction[0])
        if section.polygon.intersection(arm.entrance).length > tolerance
    )
    level = max((region.sections[index].level for index in parents), default=1)
    overall = Section(arm.polygon, arm.entrance.length, arm.depth, 1, (), arm.direction, arm.entrance)
    indices: dict[int, int] = {}
    for index, section in enumerate((overall, *arm.sections), start=-1):
        inherited = (
            parents
            if index == -1
            else tuple(
                sorted({indices[previous] for previous in section.parents or (-1,)})
            )
        )
        section_level = level + section.level - 1
        duplicate = next(
            (
                existing
                for existing, other in enumerate(region.sections)
                if abs(section.width - other.width) <= tolerance
                and abs(section.depth - other.depth) <= tolerance
                and other.level >= section_level
                and other.polygon.equals(section.polygon)
            ),
            None,
        )
        if duplicate is not None:
            indices[index] = duplicate
            continue
        indices[index] = len(region.sections)
        region.sections += (
            Section(
                section.polygon,
                section.width,
                section.depth,
                section_level,
                inherited,
                section.direction,
                section.entrance,
            ),
        )
    region.branch_count = max(region.branch_count, arm.branch_count)


def _swap_axes(geometry: BaseGeometry) -> BaseGeometry:
    return affine_transform(geometry, (0, 1, 1, 0, 0, 0))


def _sweep(solid: BaseGeometry, swap: bool, tolerance: float, debug: bool) -> list[Recess]:
    left, bottom, right, top = solid.bounds
    empty = box(left, bottom, right, top).difference(solid)
    coordinates = sorted(
        {y for poly in polygons(solid) for _, y in poly.exterior.coords}
    )
    side_edges = (
        LineString(((left, bottom), (left, top))),
        LineString(((right, bottom), (right, top))),
    )
    cells: list[Polygon] = []
    layers: list[list[int]] = []
    bounded: set[int] = set()
    mouths: dict[int, list[tuple[int, BaseGeometry]]] = defaultdict(list)
    links: dict[int, list[int]] = defaultdict(list)
    centers: list[float] = []
    for low, high in zip(coordinates, coordinates[1:], strict=False):
        current: list[int] = []
        for cell in sorted(
            polygons(empty.intersection(box(left, low, right, high))),
            key=lambda polygon: polygon.bounds,
        ):
            index = len(cells)
            cells.append(cell)
            centers.append(low + (high - low) / 2)
            current.append(index)
            if all(cell.intersection(edge).length == 0 for edge in side_edges):
                bounded.add(index)
                for sign, edge in ((1, bottom), (-1, top)):
                    if edge in (low, high):
                        opening = cell.intersection(
                            LineString(((left, edge), (right, edge)))
                        )
                        if opening.length > tolerance:
                            mouths[index].append((sign, opening))

        for first in layers[-1] if layers else ():
            for second in current:
                shared = cells[first].intersection(cells[second])
                if shared.length <= tolerance:
                    continue
                if first in bounded and second in bounded:
                    links[first].append(second)
                    links[second].append(first)
                elif first in bounded:
                    mouths[first].append((-1, shared))
                elif second in bounded:
                    mouths[second].append((1, shared))
        layers.append(current)

    results: list[Recess] = []
    unseen = bounded.copy()
    for seed in sorted(bounded):
        if seed not in unseen:
            continue
        component = [seed]
        unseen.remove(seed)
        for cell_index in component:
            for neighbor in links[cell_index]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.append(neighbor)
        openings = [
            (index, sign, geom) for index in component for sign, geom in mouths[index]
        ]
        if len(openings) != 1:
            continue
        root, sign, opening = openings[0]
        entrances = lines(opening)
        if len(entrances) != 1:
            continue
        entrance = entrances[0]
        # Root the links at the mouth. A blind arm can turn back toward the entrance.
        distance = {root: 0.0}
        queue = [(0.0, root)]
        while queue:
            cost, index = heappop(queue)
            if cost != distance[index]:
                continue
            for neighbor in links[index]:
                reached = cost + abs(centers[index] - centers[neighbor])
                if reached < distance.get(neighbor, float("inf")):
                    distance[neighbor] = reached
                    heappush(queue, (reached, neighbor))
        ordered = sorted(component, key=distance.__getitem__)
        rank = {index: position for position, index in enumerate(ordered)}
        children = {
            index: [
                neighbor for neighbor in links[index] if rank[index] < rank[neighbor]
            ]
            for index in ordered
        }
        by_cell: dict[int, int] = {}
        pieces: list[list[Polygon]] = []
        widths: list[float] = []
        directions: list[int] = []
        levels: list[int] = []
        parents: list[tuple[int, ...]] = []
        section_entrances: list[BaseGeometry | None] = []
        branch_count = 1 + sum(
            max(0, len(outgoing) - 1) for outgoing in children.values()
        )
        for index in ordered:
            previous = [
                neighbor for neighbor in links[index] if rank[neighbor] < rank[index]
            ]
            cell = cells[index]
            start, end = (cell.bounds[1], cell.bounds[3])[::sign]
            entry = cell.intersection(
                LineString(((left, start), (right, start)))
            ).length
            exit_width = cell.intersection(
                LineString(((left, end), (right, end)))
            ).length
            width = (
                min(entry, exit_width)
                if min(entry, exit_width) > tolerance
                else max(entry, exit_width)
            )
            prior = tuple(sorted({by_cell[i] for i in previous}))
            split = any(len(children[i]) > 1 for i in previous)
            direction = (
                -sign
                if previous
                and all(sign * (centers[index] - centers[i]) < 0 for i in previous)
                else sign
            )
            if (
                len(previous) == 1
                and not split
                and direction == directions[prior[0]]
                and abs(width - widths[prior[0]]) <= tolerance
            ):
                section = prior[0]
            else:
                section = len(pieces)
                pieces.append([])
                widths.append(width)
                directions.append(direction)
                parents.append(prior)
                section_entrance = None
                if debug:
                    section_entrance = (unary_union([cell.intersection(cells[i]) for i in previous])
                                        if previous else entrance)
                section_entrances.append(section_entrance)
                levels.append(
                    max(
                        (
                            levels[i] + int(split or width < widths[i] - tolerance)
                            for i in prior
                        ),
                        default=1,
                    )
                )
            pieces[section].append(cell)
            by_cell[index] = section
        if any(width <= tolerance for width in widths):
            continue
        geometry = unary_union([cells[i] for i in component])
        depth = sign * (geometry.bounds[3 if sign == 1 else 1] - entrance.bounds[1])
        sections = []
        for parts, width, level, parent, direction, section_entrance in zip(
            pieces,
            widths,
            levels,
            parents,
            directions,
            section_entrances,
            strict=True,
        ):
            shape = unary_union(parts)
            sections.append(
                Section(
                    _swap_axes(shape) if swap else shape,
                    width,
                    shape.bounds[3] - shape.bounds[1],
                    level,
                    parent,
                    (direction, 0) if swap else (0, direction),
                    _swap_axes(section_entrance) if swap and section_entrance is not None else section_entrance,
                )
            )
        if swap:
            geometry = _swap_axes(geometry)
            entrance = LineString(_swap_axes(entrance).coords)
        results.append(
            Recess(
                geometry,
                entrance,
                (sign, 0) if swap else (0, sign),
                depth,
                tuple(sections),
                branch_count,
            )
        )
    return results
