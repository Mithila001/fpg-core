"""Hand-authored homes, using Core's serialized floor-plan shape and units."""
from __future__ import annotations

from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOMS = {
    "veranda": ("veranda", "Veranda"),
    "living": ("living_room", "Living room"),
    "kitchen": ("kitchen", "Kitchen"),
    "dining": ("dining_room", "Dining room"),
    "bedroom_1": ("bedroom", "Bedroom 1"),
    "bedroom_2": ("bedroom", "Bedroom 2"),
    "bathroom_1": ("bathroom", "Bathroom"),
    "bathroom_2": ("attached_bathroom", "Attached bathroom"),
    "hallway": ("hallway", "Hallway"),
}

# Each room polygon is authored independently, in project units (10 units/m).
# Doors specify the two rooms, midpoint, and orientation; windows face outside.
LAYOUTS: dict[str, tuple[str, dict[str, tuple], list[tuple]]] = {
    "compact": ("Front veranda home", {
        "veranda": (0, 0, 45, 20), "living": (0, 20, 60, 65),
        "dining": (60, 20, 95, 43), "kitchen": (60, 43, 95, 65),
        "hallway": (0, 65, 95, 78), "bedroom_1": (0, 78, 35, 115),
        "bedroom_2": (35, 78, 70, 115), "bathroom_1": (70, 78, 95, 96),
        "bathroom_2": (70, 96, 95, 115),
    }, [
        ("veranda", "living", 27, 20, "h"), ("living", "dining", 60, 32, "v"),
        ("dining", "kitchen", 78, 43, "h"), ("living", "hallway", 48, 65, "h"),
        ("kitchen", "hallway", 78, 65, "h"), ("hallway", "bedroom_1", 23, 78, "h"),
        ("hallway", "bedroom_2", 48, 78, "h"), ("hallway", "bathroom_1", 83, 78, "h"),
        ("bedroom_2", "bathroom_2", 70, 105, "v"),
    ]),
    "side_hall": ("Side corridor home", {
        "veranda": (0, 0, 45, 18), "living": (0, 18, 45, 55),
        "dining": (45, 0, 80, 35), "kitchen": (45, 35, 80, 65),
        "hallway": (0, 55, 14, 130), "bedroom_1": (14, 75, 47, 100),
        "bedroom_2": (14, 100, 47, 130), "bathroom_1": (14, 55, 45, 75),
        "bathroom_2": (47, 100, 67, 130),
    }, [
        ("veranda", "living", 24, 18, "h"), ("living", "dining", 45, 26, "v"),
        ("dining", "kitchen", 65, 35, "h"), ("living", "hallway", 7, 55, "h"),
        ("hallway", "bathroom_1", 14, 65, "v"), ("hallway", "bedroom_1", 14, 87, "v"),
        ("hallway", "bedroom_2", 14, 115, "v"),
        ("bedroom_2", "bathroom_2", 47, 115, "v"),
    ]),
    "central_hall": ("Central hall home", {
        "veranda": (0, 0, 35, 18), "living": (0, 18, 48, 53),
        "dining": (48, 18, 80, 40), "kitchen": (48, 40, 80, 65),
        "hallway": (35, 53, 48, 130), "bedroom_1": (0, 53, 35, 90),
        "bedroom_2": (0, 90, 35, 130), "bathroom_1": (48, 65, 70, 85),
        "bathroom_2": (48, 85, 70, 105),
    }, [
        ("veranda", "living", 19, 18, "h"), ("living", "dining", 48, 29, "v"),
        ("dining", "kitchen", 64, 40, "h"), ("living", "hallway", 41.5, 53, "h"),
        ("kitchen", "hallway", 48, 59, "v"), ("hallway", "bedroom_1", 35, 74, "v"),
        ("hallway", "bedroom_2", 35, 108, "v"), ("hallway", "bathroom_1", 48, 75, "v"),
        ("hallway", "bathroom_2", 48, 95, "v"),
    ]),
    "l_hall": ("L-shaped hall home", {
        "veranda": (0, 0, 40, 18), "living": (0, 18, 45, 55),
        "dining": (45, 18, 82, 43), "kitchen": (45, 43, 82, 65),
        "hallway": ((0, 55), (45, 55), (45, 65), (82, 65), (82, 78), (0, 78)),
        "bedroom_1": (0, 78, 32, 112), "bedroom_2": (32, 78, 64, 112),
        "bathroom_1": (64, 78, 82, 96), "bathroom_2": (64, 96, 82, 112),
    }, [
        ("veranda", "living", 22, 18, "h"), ("living", "dining", 45, 30, "v"),
        ("dining", "kitchen", 63, 43, "h"), ("living", "hallway", 34, 55, "h"),
        ("kitchen", "hallway", 63, 65, "h"), ("hallway", "bedroom_1", 21, 78, "h"),
        ("hallway", "bedroom_2", 47, 78, "h"), ("hallway", "bathroom_1", 73, 78, "h"),
        ("bedroom_2", "bathroom_2", 64, 104, "v"),
    ]),
}


def _points(coords: list[tuple[float, float]]) -> dict:
    return {"points": [{"x": x, "y": y} for x, y in coords]}


def _coordinates(shape: tuple) -> list[tuple[float, float]]:
    if len(shape) == 4 and isinstance(shape[0], int):
        x1, y1, x2, y2 = shape
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    return list(shape)


def plans() -> dict[str, dict]:
    result = {}
    for key, (name, shapes, doors) in LAYOUTS.items():
        polygons = {room_id: Polygon(_coordinates(shape)) for room_id, shape in shapes.items()}
        outline = unary_union(list(polygons.values()))
        rooms: list[dict] = [{"id": room_id, "room_type": ROOMS[room_id][0], "name": ROOMS[room_id][1],
                  "boundary": _points(_coordinates(shape)), "role": "standard", "parent_room_id": None,
                  "metadata": {"source_room_ids": [], "applied_transformations": []}}
                 for room_id, shape in shapes.items()]
        if key == "central_hall":
            bathroom = next(room for room in rooms if room["id"] == "bathroom_2")
            bathroom["room_type"], bathroom["name"] = "bathroom", "Bathroom 2"
        openings = []
        for index, (source, dest, x, y, direction) in enumerate(doors):
            dx, dy = (5, 0) if direction == "h" else (0, 5)
            openings.append({"id": f"door_{index + 1}", "opening_type": "door",
                             "purpose": "room_connection", "start": {"x": x - dx, "y": y - dy},
                             "end": {"x": x + dx, "y": y + dy}, "connected_room_ids": [source, dest]})
        openings.append({"id": "entrance", "opening_type": "door", "purpose": "main_entrance",
                         "start": {"x": 10, "y": 0}, "end": {"x": 20, "y": 0},
                         "connected_room_ids": ["veranda"]})
        for room_id, polygon in polygons.items():
            if room_id in ("veranda", "hallway"):
                continue
            exterior = polygon.boundary.intersection(outline.boundary)
            segments = list(exterior.geoms) if hasattr(exterior, "geoms") else [exterior]
            segments = [line for line in segments if line.geom_type == "LineString" and line.length >= 14]
            if not segments:
                continue
            segment = max(segments, key=lambda line: line.length)
            start, end = segment.interpolate((segment.length - 10) / 2), segment.interpolate((segment.length + 10) / 2)
            openings.append({"id": f"window_{room_id}", "opening_type": "window", "purpose": "daylight",
                             "start": {"x": start.x, "y": start.y}, "end": {"x": end.x, "y": end.y},
                             "connected_room_ids": [room_id]})
        result[key] = {"name": name, "boundary": _points(list(outline.exterior.coords)[:-1]),
                       "rooms": rooms, "openings": openings, "identity_redirects": {},
                       "applied_transformations": []}
    return result
