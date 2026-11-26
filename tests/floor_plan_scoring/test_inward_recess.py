from dataclasses import replace

import pytest
from shapely.affinity import rotate, translate
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from fpg_core.domain import (
    ExecutionMode,
    FloorPlan,
    FloorPlanGenerationSpec,
    FloorPlanRoom,
    FloorSpec,
    Point,
    RoomId,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)
from fpg_core.domain import Polygon as RoomPolygon
from fpg_core.floor_plan_scoring import (
    ENCLOSED_VOIDS_KEY,
    INWARD_RECESS_KEY,
    FloorPlanScoringInput,
    InwardRecessSettings,
    InwardRecessVisualizationData,
    ScoringConfigurationError,
    create_default_config,
    score_floor_plan,
)

RATIO = "INWARD_RECESS_DEPTH_TO_WIDTH_EXCEEDED"
LEVELS = "INWARD_RECESS_TOO_MANY_LEVELS"
BRANCHES = "INWARD_RECESS_TOO_MANY_BRANCHES"
DEFAULT_SETTINGS = InwardRecessSettings()


def score(shapes, settings=DEFAULT_SETTINGS, mode=ExecutionMode.DEBUG):
    def boundary(shape):
        return RoomPolygon(
            tuple(Point(x, y) for x, y in list(shape.exterior.coords)[:-1])
        )

    rooms = [
        FloorPlanRoom(RoomId(name), RoomType.BEDROOM, name, boundary(shape))
        for name, shape in shapes
    ]
    specification = FloorPlanGenerationSpec(
        FloorSpec(300, 300),
        tuple(
            RoomSpec(room.id, room.room_type, room.name, RoomSizeSpec(1, 300, 1, 90000))
            for room in rooms
        ),
        (),
    )
    config = create_default_config()
    execution = score_floor_plan(
        FloorPlanScoringInput(
            FloorPlan(boundary(box(0, 0, 300, 300)), rooms),
            specification,
            replace(
                config,
                evaluators=tuple(
                    replace(rule, settings=settings)
                    if rule.key == INWARD_RECESS_KEY
                    else rule
                    for rule in config.evaluators
                ),
            ),
        ),
        mode=mode,
    )
    return execution


def recess_result(shapes, settings=DEFAULT_SETTINGS):
    execution = score(shapes, settings)
    assert execution.details is not None
    item = next(
        entry
        for entry in execution.details.evaluator_results
        if entry.evaluator_key == INWARD_RECESS_KEY
    )
    assert isinstance(item.visualization_payload, InwardRecessVisualizationData)
    return item, item.visualization_payload.recesses


def recess_rooms(width, depth):
    return [
        ("back", box(0, 0, width + 20, 10)),
        ("left", box(0, 10, 10, depth + 10)),
        ("right", box(width + 10, 10, width + 20, depth + 10)),
    ]


@pytest.mark.parametrize(
    ("width", "depth", "passes"),
    [
        (10, 10, True),
        (10, 20, False),
        (20, 20, True),
        (40, 30, True),
        (40, 60, False),
        (10, 10.0000005, True),
        (10, 10.000002, False),
    ],
)
def test_rectangular_ratio_and_critical_contract(width, depth, passes):
    rooms = recess_rooms(width, depth)
    item, (recess,) = recess_result(rooms)
    assert item.passed_threshold == passes
    assert score(rooms, mode=ExecutionMode.PRODUCTION).result.passed_critical == passes
    assert recess.region.width == width
    assert recess.region.depth == pytest.approx(depth)
    assert recess.region.level == recess.branch_count == 1
    assert recess.region.area == pytest.approx(width * depth)
    assert recess.direction == (0, -1)
    assert set(recess.entrance) == {(10, depth + 10), (10 + width, depth + 10)}
    assert Polygon(*recess.region.polygons[0]).equals(
        box(10, 10, 10 + width, 10 + depth)
    )
    assert {
        entry.room_id: entry.shared_length for entry in recess.region.room_boundaries
    } == {
        "back": width,
        "left": pytest.approx(depth),
        "right": pytest.approx(depth),
    }
    assert {finding.code for finding in item.findings} == (set() if passes else {RATIO})
    if not passes:
        assert item.findings[0].subject_ids == ("back", "left", "right")


def shape_with_cut(*cuts):
    return [("building", box(0, 0, 100, 100).difference(unary_union(cuts)))]


def test_stepped_asymmetric_inner_recess_cannot_hide_behind_wide_mouth():
    rooms = shape_with_cut(box(20, 90, 65, 100), box(30, 65, 40, 90))
    item, (recess,) = recess_result(rooms, InwardRecessSettings(max_recess_levels=2))
    assert recess.region.depth_to_width_ratio == pytest.approx(35 / 45)
    outer, inner = recess.sections
    assert (outer.level, inner.level, inner.parent_indices) == (1, 2, (0,))
    assert inner.depth_to_width_ratio == 2.5
    assert Polygon(*inner.polygons[0]).equals(box(30, 65, 40, 90))
    assert inner.violation_codes == (RATIO,)
    assert {finding.code for finding in item.findings} == {RATIO}


def test_real_step_adds_level_while_widening_does_not():
    narrow = shape_with_cut(box(20, 90, 70, 100), box(20, 80, 60, 90))
    wide = shape_with_cut(box(20, 90, 60, 100), box(20, 80, 70, 90))
    assert {finding.code for finding in recess_result(narrow)[0].findings} == {LEVELS}
    assert recess_result(narrow, InwardRecessSettings(max_recess_levels=2))[
        0
    ].passed_threshold
    assert recess_result(wide)[0].passed_threshold


def test_perpendicular_arms_are_measured_within_their_main_recess():
    rooms = shape_with_cut(box(40, 98, 60, 100), box(5, 94, 95, 98))
    item, (recess,) = recess_result(rooms)
    assert recess.region.depth_to_width_ratio == 0.3
    arms = [section for section in recess.sections if section.direction[0]]
    assert {section.direction for section in arms} == {(-1, 0), (1, 0)}
    assert [(section.depth, section.width) for section in arms] == [(35, 4), (35, 4)]
    assert all(
        section.parent_indices and section.violation_codes == (RATIO,)
        for section in arms
    )
    assert len(item.findings) == 2


@pytest.mark.parametrize("max_levels", [1, 2, 3])
def test_branch_count_is_independent_of_nesting_depth(max_levels):
    rooms = shape_with_cut(
        box(10, 90, 90, 100),
        box(15, 85, 30, 90),
        box(40, 85, 55, 90),
        box(65, 85, 80, 90),
    )
    item, (recess,) = recess_result(
        rooms, InwardRecessSettings(max_recess_levels=max_levels)
    )
    assert recess.branch_count == 3
    assert recess.region.level == 2
    assert [part.parent_indices for part in recess.sections] == [(), (0,), (0,), (0,)]
    assert {finding.code for finding in item.findings} == [
        {LEVELS, BRANCHES},
        {BRANCHES},
        set(),
    ][max_levels - 1]


def test_multiple_recesses_are_independent():
    rooms = shape_with_cut(box(10, 90, 30, 100), box(60, 75, 80, 100))
    item, recesses = recess_result(rooms)
    assert sorted(recess.region.depth for recess in recesses) == [10, 25]
    assert len(item.findings) == 1


def test_asymmetric_lips_set_the_mouth_at_the_first_two_sided_slice():
    rooms = recess_rooms(10, 20)
    rooms[1] = ("left", box(0, 10, 10, 40))
    _, (recess,) = recess_result(rooms)
    assert set(recess.entrance) == {(10, 30), (20, 30)}
    assert recess.region.depth == 20


def test_blind_arm_can_turn_back_toward_the_mouth():
    rooms = shape_with_cut(
        box(20, 70, 30, 100),
        box(20, 60, 60, 70),
        box(50, 70, 60, 95),
    )
    _, (recess,) = recess_result(rooms)
    assert recess.region.depth == 40
    assert recess.region.area == 950
    primary = [part for part in recess.sections if part.direction[1]]
    assert [part.depth for part in primary] == [30, 10, 25]
    assert [part.parent_indices for part in primary] == [(), (0,), (1,)]
    assert primary[-1].direction == (0, 1)


def test_corners_and_through_gaps_do_not_count_as_recesses():
    for rooms in (
        shape_with_cut(box(0, 80, 20, 100)),
        [("west", box(0, 0, 20, 80)), ("east", box(30, 10, 50, 70))],
    ):
        item, recesses = recess_result(rooms)
        assert recesses == ()
        assert item.passed_threshold


def test_enclosed_void_is_handled_by_the_interior_ring_evaluator():
    rooms = [*recess_rooms(10, 20), ("cap", box(0, 30, 30, 40))]
    execution = score(rooms)
    assert execution.details is not None
    items = {
        entry.evaluator_key: entry for entry in execution.details.evaluator_results
    }
    assert items[ENCLOSED_VOIDS_KEY].findings[0].code == "ENCLOSED_VOID_DETECTED"
    recess = items[INWARD_RECESS_KEY].visualization_payload
    assert isinstance(recess, InwardRecessVisualizationData)
    assert recess.recesses == ()


def test_invalid_room_union_returns_a_critical_failure():
    rooms = [("crossed", Polygon([(0, 0), (20, 20), (0, 20), (20, 0)]))]
    item, recesses = recess_result(rooms)
    assert recesses == ()
    assert item.findings[0].code == "ROOM_UNION_UNAVAILABLE"
    assert not score(rooms).result.passed_critical


@pytest.mark.parametrize(
    ("angle", "direction"), [(0, (0, -1)), (90, (1, 0)), (180, (0, 1)), (270, (-1, 0))]
)
def test_order_boundary_segmentation_translation_and_rotation(angle, direction):
    rooms = [
        ("back", box(0, 0, 30, 10)),
        ("left_upper", box(0, 17, 10, 30)),
        ("left_lower", box(0, 10, 10, 17)),
        ("right", Polygon([(20, 10), (30, 10), (30, 30), (20, 30), (20, 23)])),
    ]
    rooms = [
        (name, translate(rotate(shape, angle, origin=(0, 0)), 100, 100))
        for name, shape in reversed(rooms)
    ]
    _, (recess,) = recess_result(rooms)
    assert (recess.region.width, recess.region.depth, recess.region.area) == (
        10,
        20,
        200,
    )
    assert recess.region.level == recess.branch_count == len(recess.sections) == 1
    assert recess.direction == direction
    assert recess.region.violation_codes == (RATIO,)


@pytest.mark.parametrize(
    "settings",
    [
        {"max_recess_levels": True},
        {"max_recess_levels": 1.5},
        {"max_recess_levels": 0},
        {"max_depth_to_width_ratio": 0},
        {"max_depth_to_width_ratio": float("inf")},
        {"tolerance": -1},
    ],
)
def test_invalid_configuration(settings):
    with pytest.raises(ScoringConfigurationError):
        InwardRecessSettings(**settings)
