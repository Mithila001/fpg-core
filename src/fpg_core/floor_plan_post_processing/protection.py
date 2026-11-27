from __future__ import annotations

import math
from fractions import Fraction
from itertools import combinations

from ..domain import RoomRole, RoomType, RoomWidthAxis
from ..geometry_analysis import (
    directional_exposure,
    exterior_profile,
    shared_boundary,
)


def _exposure_requirement(node, room, shapes, tolerance, scale):
    if "all" in node:
        return all(
            _exposure_requirement(child, room, shapes, tolerance, scale)
            for child in node["all"]
        )
    if "any" in node:
        return any(
            _exposure_requirement(child, room, shapes, tolerance, scale)
            for child in node["any"]
        )
    exposure = directional_exposure(
        shapes[room.id],
        {str(key): value for key, value in shapes.items() if key != room.id},
        node["side"],
    )
    if node["coverage"] == "full_wall":
        return exposure.full_exposure
    minimum = math.ceil(node["minimum_length"] * scale - 1e-9) / scale
    return exposure.longest_exposed_segment + tolerance >= minimum


def _fully_shared(room, rooms, shapes, rule, tolerance, scale):
    count = rule["minimum_shared_sides"]
    if count == 0:
        return True
    totals = []
    for side in ("front", "right", "back", "left"):
        profile = exterior_profile(shapes[room.id], side)
        length = sum(segment.length for segment in profile.segments)
        contact = sum(
            segment.geometry.intersection(shapes[other.id].boundary).length
            for segment in profile.segments
            for other in rooms
            if other.id != room.id
        )
        totals.append((length, contact))
    for group in combinations(range(4), count):
        if (
            count == 2
            and rule["arrangement"] == "adjacent"
            and group[1] - group[0] == 2
        ):
            continue
        if (
            all(totals[i][1] + tolerance >= 1 / scale for i in group)
            and sum(totals[i][0] - totals[i][1] for i in group)
            <= math.floor(rule.get("uncovered_length_tolerance", 0) * scale) / scale
            + tolerance
        ):
            return True
    return False


def candidate_protection(
    floor_plan, context, before, after, changed_id, *, area_excess, width_excess
):
    """Return a reason when an expansion cannot be proven to preserve hard rules."""
    spec = context.specification
    config = context.solver_config
    if spec is None or config is None:
        return "missing specification or solver configuration"
    rooms = [room for room in floor_plan.rooms if room.role is RoomRole.STANDARD]
    room = next((item for item in rooms if item.id == changed_id), None)
    matches = [item for item in spec.rooms if item.id == changed_id]
    if room is None or len(matches) != 1 or matches[0].room_type is not room.room_type:
        return "room specification cannot be resolved"
    size = matches[0].size
    shape = after[changed_id]
    minx, miny, maxx, maxy = shape.bounds
    width, height = maxx - minx, maxy - miny
    measured_width = {
        RoomWidthAxis.X: width,
        RoomWidthAxis.Y: height,
        RoomWidthAxis.ANY: min(width, height),
    }.get(size.width_axis)
    tolerance = context.numeric.tolerance
    if measured_width is None or min(width, height) + tolerance < size.min_width:
        return "room minimum width"
    if measured_width > size.max_width * (1 + width_excess) + tolerance:
        return "room maximum width"
    if shape.area + tolerance < size.min_area or (
        size.max_area > 0 and shape.area > size.max_area * (1 + area_excess) + tolerance
    ):
        return "room area limit"
    # Existing contacts are preserved, including relationships and connectivity.
    for other in rooms:
        if other.id == changed_id:
            continue
        old = shared_boundary(before[changed_id], before[other.id])
        new = shared_boundary(shape, after[other.id])
        if old.difference(new).length > tolerance:
            return "shared-wall contact removed"
    types = {item.room_type for item in rooms}
    scale = config.preparation.coordinate_scale
    for use in config.hard_constraints:
        key, settings = use.key, use.settings
        if key in ("exterior_wall_exposure", "living_room_front"):
            if key == "living_room_front" and RoomType.VERANDA in types:
                continue
            for rule in settings["rules"]:
                selected = [
                    item for item in rooms if item.room_type in rule["room_types"]
                ]
                qualified = sum(
                    _exposure_requirement(
                        rule["requirement"], item, after, tolerance, scale
                    )
                    for item in selected
                )
                match = rule["match"]
                if (match["policy"] == "all" and qualified != len(selected)) or (
                    match["policy"] == "at_least" and qualified < match["count"]
                ):
                    return f"exposure rule {rule['id']}"
        elif key == "front_wall_setback":
            # Expanding even an untargeted room can advance the reference edge.
            front = min(after[item.id].bounds[1] for item in rooms)
            for rule in settings["rules"]:
                when = rule.get("when")
                if when is not None and (
                    (when["room_type"] in types) != when["exists"]
                ):
                    continue
                allowance = Fraction(
                    Fraction(str(rule["maximum_setback"])) * scale // 1, scale
                )
                for item in rooms:
                    if (
                        item.room_type in rule["room_types"]
                        and after[item.id].bounds[1] - front - tolerance > allowance
                    ):
                        return "front wall setback"
        elif key == "fully_shared_wall":
            for item in rooms:
                for rule in settings["rules"]:
                    when = rule.get("when")
                    if (
                        item.room_type in rule["room_types"]
                        and (
                            when is None
                            or ((when["room_type"] in types) == when["exists"])
                        )
                        and not _fully_shared(
                            item, rooms, after, rule, tolerance, scale
                        )
                    ):
                        return "fully shared wall"
        elif key == "aspect_ratio":
            excluded = set(
                settings.get("hallway_room_types", (RoomType.HALLWAY,))
            ) | set(settings.get("excluded_room_types", ()))
            if room.room_type not in excluded:
                override = settings.get("overrides", {}).get(room.room_type, {})
                precision = settings.get("precision", 1000)
                minimum = round(
                    override.get("min_ratio", settings.get("min_ratio", 0.35))
                    * precision
                )
                maximum = round(
                    override.get("max_ratio", settings.get("max_ratio", 2.85))
                    * precision
                )
                if (
                    width * precision + tolerance < height * minimum
                    or width * precision > height * maximum + tolerance
                ):
                    return "aspect ratio"
        elif key == "room_size_hierarchy":
            by_id = {item.id: item for item in rooms}
            ordered = [by_id[item.id] for item in spec.rooms if item.id in by_id]
            anchor = next(
                (
                    item
                    for room_type in settings.get(
                        "anchor_room_types", (RoomType.LIVING_ROOM,)
                    )
                    for item in ordered
                    if item.room_type == room_type
                ),
                None,
            )
            if anchor is not None:
                precision = settings.get("precision", 1000)
                for item in ordered:
                    rule = settings.get("ratios_by_room_type", {}).get(item.room_type)
                    if item.id == anchor.id or rule is None:
                        continue
                    minimum = round(rule.get("min_ratio", 0.0) * precision)
                    maximum = round(rule.get("max_ratio", 1.0) * precision)
                    if (
                        after[item.id].area * precision + tolerance
                        < after[anchor.id].area * minimum
                        or after[item.id].area * precision
                        > after[anchor.id].area * maximum + tolerance
                    ):
                        return "room size hierarchy"
        elif key == "boundary_placement":
            for rule in settings.get("rules", ()):
                if room.room_type not in rule["room_types"]:
                    continue
                side = rule["side"]
                offset = round(rule.get("offset", 0) * scale) / scale
                actual = {"left": minx, "right": maxx, "front": miny, "back": maxy}[
                    side
                ]
                expected = {
                    "left": offset,
                    "right": round(spec.floor.width * scale) / scale - offset,
                    "front": offset,
                    "back": round(spec.floor.length * scale) / scale - offset,
                }[side]
                if abs(actual - expected) > tolerance:
                    return "boundary placement"
        elif key in (
            "hallway_dimensions",
            "hallway_parallel_overlap",
            "hallway_shared_wall",
        ):
            if room.room_type in settings.get(
                "hallway_room_types", (RoomType.HALLWAY,)
            ):
                return f"{key} requires unchanged hallway geometry"
        elif key == "attached_bathroom_pairing":
            bathroom_types = settings.get(
                "attached_bathroom_room_types", (RoomType.ATTACHED_BATHROOM,)
            )
            bedroom_types = settings.get("bedroom_room_types", (RoomType.BEDROOM,))
            for other in rooms:
                if other.id == changed_id:
                    continue
                if not (
                    (
                        room.room_type in bathroom_types
                        and other.room_type in bedroom_types
                    )
                    or (
                        room.room_type in bedroom_types
                        and other.room_type in bathroom_types
                    )
                ):
                    continue
                old = shared_boundary(before[changed_id], before[other.id])
                new = shared_boundary(after[changed_id], after[other.id])
                if old.symmetric_difference(new).length > tolerance:
                    return "attached bathroom pairing changed"
        elif key == "bathroom_hallway_shared_wall":
            for other in rooms:
                if {room.room_type, other.room_type} != {
                    RoomType.BATHROOM,
                    RoomType.HALLWAY,
                }:
                    continue
                old = shared_boundary(before[changed_id], before[other.id])
                new = shared_boundary(after[changed_id], after[other.id])
                if old.symmetric_difference(new).length > tolerance:
                    return "bathroom hallway contact changed"
        elif key in ("room_relations", "hallway_connectivity", "minimum_coverage"):
            continue
        else:
            return f"unsupported hard constraint {key}"
    return None
