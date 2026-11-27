from __future__ import annotations

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from ...domain import ExecutionMode, RoomRole, RoomType
from ...geometry_analysis import (
    detect_recesses,
    detect_voids,
    exterior_profile,
    is_rectilinear,
    lines,
    measure_room_shape,
    occupied_footprint,
    polygons,
    shared_boundary,
)
from ..config import WallExtensionConfig
from ..contracts import (
    FloorPlanProcessor,
    ProcessorOutcome,
    ProcessorStatus,
    RepairDiagnostic,
)
from ..geometry import from_shapely, to_shapely
from ..protection import candidate_protection


def _problems(footprint, config, tolerance):
    pockets = [
        p
        for p in detect_voids(footprint)
        if p.area + tolerance >= config.min_pocket_area
    ]
    recesses = []
    for recess in detect_recesses(footprint, tolerance):
        if (
            recess.depth > recess.entrance.length * config.max_recess_ratio + tolerance
            or recess.branch_count > config.max_recess_levels
            or any(
                section.depth > section.width * config.max_recess_ratio + tolerance
                or section.level > config.max_recess_levels
                for section in recess.sections
            )
        ):
            recesses.append(recess.polygon)
    steps = []
    for policy in config.exterior_steps:
        profile = exterior_profile(footprint, policy.direction)
        for step in profile.steps:
            if (
                step.depth + tolerance >= policy.minimum_depth
                and min(step.before.length, step.after.length) + tolerance
                >= policy.minimum_segment_length
                and len(profile.steps) <= policy.preferred_max_steps
            ):
                continue
            before, after = step.before, step.after
            low_side = policy.direction in ("front", "left")
            inner = before if (before.position > after.position) == low_side else after
            low, high = sorted((before.position, after.position))
            if policy.direction in ("front", "back"):
                region = box(inner.start, low, inner.end, high)
            else:
                region = box(low, inner.start, high, inner.end)
            region = region.difference(footprint)
            if any(region.intersection(recess).area > tolerance for recess in recesses):
                continue
            steps.extend(polygons(region))
    return pockets, recesses, steps


def _recess_severity(footprint, tolerance):
    recesses = detect_recesses(footprint, tolerance)
    return (
        max(
            (
                max(
                    (
                        recess.depth / recess.entrance.length,
                        *(section.depth / section.width for section in recess.sections),
                    )
                )
                for recess in recesses
            ),
            default=0,
        ),
        max((recess.branch_count for recess in recesses), default=0),
        max(
            (section.level for recess in recesses for section in recess.sections),
            default=0,
        ),
    )


def _patches(room, target, maximum, minimum, grid, tolerance):
    boundary = shared_boundary(room, target)
    for contact in lines(boundary):
        coordinates = list(contact.coords)
        for a, b in zip(coordinates, coordinates[1:], strict=False):
            segment = LineString((a, b))
            if segment.length + tolerance < minimum:
                continue
            horizontal = abs(a[1] - b[1]) <= tolerance
            start, end = sorted((a[0], b[0]) if horizontal else (a[1], b[1]))
            position = a[1] if horizontal else a[0]
            vertex_values = [
                x if horizontal else y
                for poly in polygons(target)
                for x, y in poly.exterior.coords
            ]
            candidates = (
                start + minimum,
                end - minimum,
                round((start + end) / (2 * grid)) * grid,
            )
            # ponytail: finite width choices can miss a feasible grid split; enumerate more grid cuts if repair coverage needs it.
            cuts = sorted(
                {
                    start,
                    end,
                    *(v for v in (*vertex_values, *candidates) if start < v < end),
                }
            )
            depths = sorted(
                {
                    maximum,
                    round(maximum / (2 * grid)) * grid,
                    *(
                        abs((y if horizontal else x) - position)
                        for poly in polygons(target)
                        for x, y in poly.exterior.coords
                        if tolerance
                        < abs((y if horizontal else x) - position)
                        <= maximum
                    ),
                }
                - {0}
            )
            for low_index, low in enumerate(cuts[:-1]):
                for high in cuts[low_index + 1 :]:
                    if high - low + tolerance < minimum:
                        continue
                    for depth in depths:
                        for sign in (-1, 1):
                            p = (
                                box(
                                    low,
                                    min(position, position + sign * depth),
                                    high,
                                    max(position, position + sign * depth),
                                )
                                if horizontal
                                else box(
                                    min(position, position + sign * depth),
                                    low,
                                    max(position, position + sign * depth),
                                    high,
                                )
                            )
                            if target.buffer(tolerance).covers(p) and all(
                                abs(v / grid - round(v / grid)) <= tolerance
                                for v in p.bounds
                            ):
                                yield p


class WallExtensionProcessor(FloorPlanProcessor):
    processor_id = "wall_extension"
    description = "Repair detected footprint problems through bounded room expansion."
    config_type = WallExtensionConfig

    def is_applicable(self, floor_plan, context, config):
        if config.transformation_version in floor_plan.applied_transformations:
            return False, "this transformation version was already applied"
        if context.specification is None or context.solver_config is None:
            return (
                False,
                "specification and solver configuration are required for safe repair",
            )
        if any(
            not is_rectilinear(
                tuple((point.x, point.y) for point in room.boundary.points),
                context.numeric.tolerance,
            )
            for room in floor_plan.rooms
            if room.role is RoomRole.STANDARD
        ):
            return False, "repair requires rectilinear rooms"
        return True, "applicable"

    def process(self, floor_plan, context, config):
        tolerance = context.numeric.tolerance
        rooms = sorted(
            (r for r in floor_plan.rooms if r.role is RoomRole.STANDARD),
            key=lambda r: str(r.id),
        )
        shapes = {room.id: to_shapely(room.boundary) for room in rooms}
        original_shapes = dict(shapes)
        allowed = to_shapely(floor_plan.boundary)
        distances = {rule.room_type: rule.max_distance for rule in config.rules}
        affected = []
        diagnostics = []
        debug = context.mode is ExecutionMode.DEBUG
        evaluated = 0
        termination = "iteration limit"
        for _ in range(config.max_iterations):
            footprint = occupied_footprint(shapes.values())
            problems = _problems(footprint, config, tolerance)
            severity_before = _recess_severity(footprint, tolerance)
            before = tuple(sum(part.area for part in category) for category in problems)
            if debug:
                for name, targets in zip(
                    ("pocket", "recess", "exterior_step"), problems, strict=True
                ):
                    diagnostics.extend(
                        RepairDiagnostic(
                            "problem",
                            bounds=target.bounds,
                            detail=name,
                            geometry=tuple(target.exterior.coords),
                            associated_room_ids=tuple(
                                room.id
                                for room in rooms
                                if shared_boundary(shapes[room.id], target).length
                                > tolerance
                            ),
                            shared_walls=tuple(
                                (room.id, tuple(line.coords))
                                for room in rooms
                                for line in lines(
                                    shared_boundary(shapes[room.id], target)
                                )
                                if line.length > tolerance
                            ),
                        )
                        for target in targets
                    )
            best = None
            for category, targets in enumerate(problems):
                for target in sorted(targets, key=lambda item: item.bounds):
                    for room in rooms:
                        if room.room_type not in distances:
                            continue
                        original = shapes[room.id]
                        for patch in _patches(
                            original,
                            target,
                            distances[room.room_type],
                            config.min_contact_length,
                            context.numeric.grid_size,
                            tolerance,
                        ):
                            if evaluated >= config.max_candidate_evaluations:
                                break
                            evaluated += 1
                            if not allowed.buffer(tolerance).covers(patch) or any(
                                patch.intersection(other).area > tolerance
                                for ident, other in shapes.items()
                            ):
                                if debug:
                                    diagnostics.append(
                                        RepairDiagnostic(
                                            "rejected",
                                            room.id,
                                            patch.bounds,
                                            "boundary or overlap",
                                        )
                                    )
                                continue
                            candidate = unary_union((original, patch)).simplify(0)
                            if (
                                not isinstance(candidate, Polygon)
                                or not candidate.is_valid
                                or candidate.interiors
                                or not is_rectilinear(
                                    tuple(candidate.exterior.coords)[:-1], tolerance
                                )
                            ):
                                if debug:
                                    diagnostics.append(
                                        RepairDiagnostic(
                                            "rejected",
                                            room.id,
                                            patch.bounds,
                                            "invalid room polygon",
                                        )
                                    )
                                continue
                            old_shape, new_shape = (
                                measure_room_shape(original_shapes[room.id]),
                                measure_room_shape(candidate),
                            )
                            old_short = sum(
                                edge < config.min_residual_edge - tolerance
                                for edge in old_shape.edge_lengths
                            )
                            new_short = sum(
                                edge < config.min_residual_edge - tolerance
                                for edge in new_shape.edge_lengths
                            )
                            if (
                                new_short > old_short
                                or new_shape.concave_corners
                                > old_shape.concave_corners + 2
                            ):
                                if debug:
                                    diagnostics.append(
                                        RepairDiagnostic(
                                            "rejected",
                                            room.id,
                                            patch.bounds,
                                            "room shape",
                                        )
                                    )
                                continue
                            hallway = room.room_type is RoomType.HALLWAY
                            min_width = (
                                config.hallway_min_extension_width
                                if hallway
                                else config.min_extension_width
                            )
                            min_depth = (
                                config.hallway_min_extension_depth
                                if hallway
                                else config.min_extension_depth
                            )
                            old_sections = (
                                old_shape.horizontal_widths + old_shape.vertical_widths
                            )
                            new_sections = (
                                new_shape.horizontal_widths + new_shape.vertical_widths
                            )
                            if (
                                old_sections
                                and new_sections
                                and min(new_sections) + tolerance
                                < min(min_width, min(old_sections))
                            ):
                                if debug:
                                    diagnostics.append(
                                        RepairDiagnostic(
                                            "rejected",
                                            room.id,
                                            patch.bounds,
                                            "narrow room section",
                                        )
                                    )
                                continue
                            contact = shared_boundary(original, patch).length
                            depth = patch.area / contact if contact else 0
                            full_wall = any(
                                abs(line.length - contact) <= tolerance
                                and line.intersection(patch.boundary).length + tolerance
                                >= line.length
                                for line in (
                                    LineString((a, b))
                                    for a, b in zip(
                                        list(original.exterior.coords),
                                        list(original.exterior.coords)[1:],
                                        strict=False,
                                    )
                                )
                            )
                            if contact + tolerance < min_width or (
                                not full_wall and depth + tolerance < min_depth
                            ):
                                if debug:
                                    diagnostics.append(
                                        RepairDiagnostic(
                                            "rejected",
                                            room.id,
                                            patch.bounds,
                                            "extension dimensions",
                                        )
                                    )
                                continue
                            trial = dict(shapes)
                            trial[room.id] = candidate
                            reason = candidate_protection(
                                floor_plan,
                                context,
                                shapes,
                                trial,
                                room.id,
                                area_excess=config.max_area_excess,
                                width_excess=config.max_width_excess,
                            )
                            if reason:
                                if debug:
                                    diagnostics.append(
                                        RepairDiagnostic(
                                            "rejected", room.id, patch.bounds, reason
                                        )
                                    )
                                continue
                            trial_footprint = occupied_footprint(trial.values())
                            after_problems = _problems(
                                trial_footprint, config, tolerance
                            )
                            severity_after = _recess_severity(
                                trial_footprint, tolerance
                            )
                            after = tuple(
                                sum(part.area for part in group)
                                for group in after_problems
                            )
                            moved = any(
                                group
                                and any(
                                    part.difference(unary_union(previous)).area
                                    > tolerance
                                    for part in group
                                )
                                for previous, group in zip(
                                    problems, after_problems, strict=True
                                )
                            )
                            if (
                                moved
                                or any(
                                    a > b + tolerance
                                    for a, b in zip(
                                        severity_after, severity_before, strict=True
                                    )
                                )
                                or any(
                                    a > b + tolerance
                                    for a, b in zip(after, before, strict=True)
                                )
                                or before[category] <= after[category] + tolerance
                            ):
                                if debug:
                                    diagnostics.append(
                                        RepairDiagnostic(
                                            "rejected",
                                            room.id,
                                            patch.bounds,
                                            f"problem measurements {before} -> {after}",
                                        )
                                    )
                                continue
                            if debug:
                                diagnostics.append(
                                    RepairDiagnostic(
                                        "candidate",
                                        room.id,
                                        patch.bounds,
                                        f"problem measurements {before} -> {after}",
                                        tuple(patch.exterior.coords),
                                    )
                                )
                            rank = (
                                before[category] - after[category],
                                -new_shape.concave_corners,
                                -patch.area,
                                str(room.id),
                                tuple(patch.bounds),
                            )
                            if best is None or rank > best[0]:
                                best = (rank, room, candidate)
                        if evaluated >= config.max_candidate_evaluations:
                            break
                    if evaluated >= config.max_candidate_evaluations:
                        break
                if evaluated >= config.max_candidate_evaluations:
                    break
            if best is None:
                termination = (
                    "candidate budget exhausted"
                    if evaluated >= config.max_candidate_evaluations
                    else "no beneficial candidate"
                )
                break
            _, room, candidate = best
            room.boundary = from_shapely(candidate, tolerance)
            if debug:
                spec = next(
                    item for item in context.specification.rooms if item.id == room.id
                )
                bounds = candidate.bounds
                dimensions = (bounds[2] - bounds[0], bounds[3] - bounds[1])
                width = {
                    "x": dimensions[0],
                    "y": dimensions[1],
                    "any": min(dimensions),
                }[spec.size.width_axis.value]
                exception = (
                    spec.size.max_area > 0
                    and candidate.area > spec.size.max_area + tolerance
                ) or width > spec.size.max_width + tolerance
                diagnostics.append(
                    RepairDiagnostic(
                        "accepted",
                        room.id,
                        candidate.bounds,
                        f"problem measurements before {before}; size exception={exception}",
                        tuple(candidate.exterior.coords),
                    )
                )
            shapes[room.id] = candidate
            if room.id not in affected:
                affected.append(room.id)
            if evaluated >= config.max_candidate_evaluations:
                termination = "candidate budget exhausted"
                break
        floor_plan.applied_transformations.add(config.transformation_version)
        return ProcessorOutcome(
            ProcessorStatus.CHANGED if affected else ProcessorStatus.NO_CHANGE,
            "repaired footprint" if affected else "no beneficial repair found",
            tuple(affected),
            metrics={
                "rooms_modified": len(affected),
                "candidates_evaluated": evaluated,
                "termination": termination,
            },
            diagnostics=tuple(diagnostics),
        )
