"""Session-local floor traffic: clearance-aware routes and footprint coverage."""
from __future__ import annotations

import heapq
import math
from collections.abc import Mapping, Sequence
from typing import Any

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

RADIUS = 4.0
GRID = 2.0


def _coords(polygon: Mapping[str, Any]) -> list[tuple[float, float]]:
    return [(p["x"], p["y"]) for p in polygon["points"]]


def _line(opening: Mapping[str, Any]) -> LineString:
    return LineString([(opening[k]["x"], opening[k]["y"]) for k in ("start", "end")])


def geometry(plan: Mapping[str, Any]) -> tuple[dict[str, Polygon], Any, Any]:
    """Validate a plan and return rooms, walkable floor, and solid wall segments."""
    boundary = Polygon(_coords(plan["boundary"]))
    if not boundary.is_valid or boundary.area <= 0:
        raise ValueError("Invalid floor boundary")
    rooms: dict[str, Polygon] = {}
    for room in plan["rooms"]:
        room_id = room["id"]
        polygon = Polygon(_coords(room["boundary"]))
        if room_id in rooms or not polygon.is_valid or polygon.area <= 0 or not boundary.covers(polygon):
            raise ValueError(f"Invalid room geometry or duplicate ID: {room_id}")
        if any(polygon.intersection(other).area > 1e-8 for other in rooms.values()):
            raise ValueError(f"Overlapping room: {room_id}")
        rooms[room_id] = polygon
    if not rooms:
        raise ValueError("The floor plan has no rooms")
    wall_lines = unary_union([p.boundary for p in rooms.values()])
    doors = []
    seen = set()
    for opening in plan["openings"]:
        if opening["id"] in seen:
            raise ValueError(f"Duplicate opening: {opening['id']}")
        seen.add(opening["id"])
        line = _line(opening)
        ids = opening["connected_room_ids"]
        if line.length <= 0 or not ids or len(ids) != len(set(ids)) or any(i not in rooms for i in ids):
            raise ValueError(f"Invalid opening: {opening['id']}")
        if any(not rooms[i].boundary.buffer(1e-7).covers(line) for i in ids):
            raise ValueError(f"Opening is not on its room walls: {opening['id']}")
        if opening["opening_type"] == "door" and len(ids) == 2:
            doors.append(line)
    walls = wall_lines.difference(unary_union(doors)) if doors else wall_lines
    return rooms, unary_union(list(rooms.values())), walls


def _vertices(area: Any) -> list[tuple[float, float]]:
    polygons = list(area.geoms) if area.geom_type == "MultiPolygon" else [area]
    vertices: list[tuple[float, float]] = []
    for polygon in polygons:
        if polygon.geom_type != "Polygon":
            continue
        for ring in [polygon.exterior, *polygon.interiors]:
            vertices.extend((float(x), float(y)) for x, y in list(ring.coords)[:-1])
    return list(dict.fromkeys(vertices))


def _graph(area: Any, centers: dict[str, tuple[float, float]]) -> tuple[list, list]:
    vertices = list(dict.fromkeys([*centers.values(), *_vertices(area)]))
    graph: list[list[tuple[int, float]]] = [[] for _ in vertices]
    # ponytail: visibility edges scale quadratically with wall vertices; use a spatial index for larger plans.
    for i, a in enumerate(vertices):
        if not area.covers(Point(a)):
            continue
        for j in range(i):
            b = vertices[j]
            if area.covers(LineString([a, b])):
                distance = math.dist(a, b)
                graph[i].append((j, distance))
                graph[j].append((i, distance))
    return vertices, graph


def _shortest(vertices: list, graph: list, start: tuple, end: tuple) -> list[tuple] | None:
    source, target = vertices.index(start), vertices.index(end)
    queue = [(0.0, source)]
    distances = {source: 0.0}
    previous: dict[int, int] = {}
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == target:
            path = [node]
            while path[-1] != source:
                path.append(previous[path[-1]])
            return [vertices[i] for i in reversed(path)]
        for neighbor, weight in graph[node]:
            candidate = distance + weight
            if candidate < distances.get(neighbor, math.inf):
                distances[neighbor] = candidate
                previous[neighbor] = node
                heapq.heappush(queue, (candidate, neighbor))
    return None


def _smooth(path: list[tuple], safe_area: Any) -> list[tuple]:
    result = [path[0]]
    for i in range(1, len(path) - 1):
        a, b, c = path[i - 1:i + 2]
        trim = min(4.0, math.dist(a, b) / 3, math.dist(b, c) / 3)
        curve = None
        for _ in range(12):
            if trim < 1e-5:
                break
            p = tuple(b[k] + (a[k] - b[k]) * trim / math.dist(a, b) for k in (0, 1))
            q = tuple(b[k] + (c[k] - b[k]) * trim / math.dist(b, c) for k in (0, 1))
            points = [tuple((1-t)**2*p[k] + 2*(1-t)*t*b[k] + t*t*q[k] for k in (0, 1))
                      for t in (j / 10 for j in range(11))]
            if safe_area.covers(LineString(points)):
                curve = points
                break
            trim /= 2
        result.extend(curve if curve else [b])
    result.append(path[-1])
    return result


def preset_trips(plan: Mapping[str, Any]) -> list[tuple[str, str]]:
    by_type: dict[str, list[str]] = {}
    for room in plan["rooms"]:
        by_type.setdefault(room["room_type"], []).append(room["id"])
    pairs: list[tuple[str, str]] = []
    for source_type, destination_type in (("veranda", "living_room"), ("veranda", "kitchen"),
                                          ("kitchen", "dining_room"), ("living_room", "dining_room")):
        pairs.extend((source, dest) for source in by_type.get(source_type, [])
                     for dest in by_type.get(destination_type, []))
    for bedroom in by_type.get("bedroom", []):
        pairs.append((bedroom, "@closest_bathroom"))
        pairs.extend((bedroom, kitchen) for kitchen in by_type.get("kitchen", []))
    return pairs


def simulate(plan: Mapping[str, Any], trips: Sequence[tuple[str, str]] | None = None) -> dict:
    rooms, floor, walls = geometry(plan)
    safe = floor.difference(walls.buffer(RADIUS + 0.001, cap_style="square", join_style="mitre"))
    planning = floor.difference(walls.buffer(RADIUS + 0.6, cap_style="square", join_style="mitre"))
    centers = {key: (polygon.centroid.x, polygon.centroid.y) for key, polygon in rooms.items()}
    vertices, graph = _graph(planning, centers)
    bathroom_ids = sorted(r["id"] for r in plan["rooms"]
                          if r["room_type"] in ("bathroom", "attached_bathroom"))
    routes, failures = [], []
    for source, requested in trips if trips is not None else preset_trips(plan):
        destinations = bathroom_ids if requested == "@closest_bathroom" else [requested]
        candidates = []
        for dest in destinations:
            if source not in centers or dest not in centers or source == dest:
                continue
            if not planning.covers(Point(centers[source])) or not planning.covers(Point(centers[dest])):
                continue
            path = _shortest(vertices, graph, centers[source], centers[dest])
            if path:
                points = _smooth(path, safe)
                line = LineString(points)
                if safe.covers(line):
                    candidates.append((line.length, dest, points))
        if not candidates:
            failures.append({"source": source, "destination": requested, "reason": "No route with 8-unit clearance"})
            continue
        length, dest, points = min(candidates, key=lambda item: (item[0], item[1]))
        routes.append({"source": source, "destination": dest, "length": length,
                       "points": points, "footprint": LineString(points).buffer(RADIUS)})
    heatmap, summaries = _heatmap(rooms, floor, routes)
    present = {room["room_type"] for room in plan["rooms"]}
    missing = [kind for kind in ("veranda", "living_room", "kitchen", "dining_room", "bedroom")
               if kind not in present]
    if not present.intersection({"bathroom", "attached_bathroom"}):
        missing.append("bathroom")
    return {"routes": routes, "failures": failures, "heatmap": heatmap, "rooms": summaries,
            "missing_room_types": missing if trips is None else []}


def _heatmap(rooms: dict[str, Polygon], floor: Any, routes: list[dict]) -> tuple[dict, list]:
    minx, miny, maxx, maxy = floor.bounds
    xs = [minx + GRID * (i + 0.5) for i in range(math.ceil((maxx - minx) / GRID))]
    ys = [miny + GRID * (i + 0.5) for i in range(math.ceil((maxy - miny) / GRID))]
    z = []
    totals = {key: [0.0, 0.0, 0.0, 0.0] for key in rooms}
    footprints = [r["footprint"] for r in routes]
    for y in ys:
        row: list[float | None] = []
        for x in xs:
            cell = box(x - GRID / 2, y - GRID / 2, x + GRID / 2, y + GRID / 2)
            inside = cell.intersection(floor)
            if inside.area < 1e-9:
                row.append(None)
                continue
            value = sum(inside.intersection(p).area / inside.area for p in footprints if inside.intersects(p))
            row.append(value)
            for key, room in rooms.items():
                part = cell.intersection(room)
                if part.area:
                    traffic = sum(part.intersection(p).area / part.area for p in footprints if part.intersects(p))
                    total = totals[key]
                    total[0] += traffic * part.area
                    total[1] = max(total[1], traffic)
                    total[2] += part.area
                    covered = unary_union([p for p in footprints if part.intersects(p)])
                    total[3] += part.difference(covered).area
        z.append(row)
    summaries = [{"id": key, "mean": v[0] / v[2], "peak": v[1],
                  "untouched_percent": 100 * v[3] / v[2]} for key, v in totals.items() if v[2]]
    return {"x": xs, "y": ys, "z": z}, summaries
