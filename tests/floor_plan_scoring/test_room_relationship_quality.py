from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast

import pytest
from shapely.geometry import box

from fpg_core.domain import ExecutionMode, RoomType
from fpg_core.floor_plan_scoring import (
    EvaluationStatus,
    RoomClusteringRule,
    RoomProximityRule,
    RoomRelationshipQualityEvaluator,
    RoomRelationshipQualitySettings,
    ScoringConfigurationError,
)

PROXIMITY = RoomProximityRule(
    rule_id="kitchen_dining",
    source_type=RoomType.KITCHEN,
    target_type=RoomType.DINING_ROOM,
    preferred_maximum_distance=5,
    zero_score_distance=30,
)
CLUSTERING = RoomClusteringRule(
    rule_id="bedrooms",
    room_types=(RoomType.BEDROOM,),
    preferred_maximum_distance=50,
    zero_score_distance=100,
    weight=0.5,
)


def room(room_id, kind, x, y=0):
    polygon = box(x, y, x + 10, y + 10)
    return SimpleNamespace(
        room_id=room_id,
        room_type=kind,
        polygon=polygon,
        centroid=(polygon.centroid.x, polygon.centroid.y),
    )


def evaluate(rooms, proximity=(), clustering=(), mode=ExecutionMode.DEBUG):
    return RoomRelationshipQualityEvaluator().evaluate(
        cast(Any, SimpleNamespace(rooms=rooms, mode=mode)),
        RoomRelationshipQualitySettings(proximity, clustering),
    )


@pytest.mark.parametrize(
    ("x", "y", "distance", "expected"),
    [
        (10, 0, 0, 100),
        (10, 10, 0, 100),
        (15, 0, 5, 100),
        (27.5, 0, 17.5, 50),
        (40, 0, 30, 0),
        (41, 0, 31, 0),
    ],
)
def test_proximity_boundary_distance_and_normalization(x, y, distance, expected):
    result = evaluate(
        [
            room("k", RoomType.KITCHEN, 0),
            room("d", RoomType.DINING_ROOM, x, y),
        ],
        (PROXIMITY,),
    )
    assert result.score == expected
    assert (
        cast(Any, result.visualization_payload)["rules"][0]["pairs"][0]["distance"]
        == distance
    )


def test_each_source_uses_its_own_nearest_other_room():
    rooms = [
        room("k1", RoomType.KITCHEN, 0),
        room("d1", RoomType.DINING_ROOM, 10),
        room("k2", RoomType.KITCHEN, 100),
        room("d2", RoomType.DINING_ROOM, 127.5),
    ]
    result = evaluate(rooms, (PROXIMITY,))
    assert result.score == 75
    assert [
        (pair["source_id"], pair["target_id"])
        for pair in cast(Any, result.visualization_payload)["rules"][0]["pairs"]
    ] == [("k1", "d1"), ("k2", "d2")]
    same_type = replace(PROXIMITY, target_type=RoomType.KITCHEN)
    assert evaluate(rooms, (same_type,)).score == 0
    assert evaluate(rooms[:1], (same_type,)).status is EvaluationStatus.NOT_APPLICABLE


def test_farthest_centroids_and_applicable_weighting():
    bedrooms = [room("b1", RoomType.BEDROOM, 0), room("b2", RoomType.BEDROOM, 30)]
    assert evaluate(bedrooms, clustering=(CLUSTERING,)).score == 100
    assert (
        evaluate(bedrooms[:1], clustering=(CLUSTERING,)).status
        is EvaluationStatus.NOT_APPLICABLE
    )
    bedrooms.append(room("b3", RoomType.BEDROOM, 75))
    rooms = [
        *bedrooms,
        room("k", RoomType.KITCHEN, 0, 20),
        room("d", RoomType.DINING_ROOM, 10, 20),
    ]
    disabled = replace(PROXIMITY, rule_id="disabled", enabled=False, weight=30)
    missing = replace(
        CLUSTERING, rule_id="missing", room_types=(RoomType.BEDROOM, RoomType.GARAGE)
    )
    result = evaluate(rooms, (PROXIMITY, disabled), (CLUSTERING, missing))
    assert result.score == pytest.approx((100 + 50 * 0.5) / 1.5)
    assert result.metrics[0].value == 2
    cluster = cast(Any, result.visualization_payload)["rules"][1]
    assert (cluster["pair"], cluster["distance"], cluster["score"]) == (
        ("b1", "b3"),
        75,
        50,
    )
    assert cluster["room_ids"] == ["b1", "b2", "b3"]
    production = evaluate(
        rooms, (PROXIMITY, disabled), (CLUSTERING, missing), ExecutionMode.PRODUCTION
    )
    assert production.score == result.score
    assert production.visualization_payload is None
    assert (
        evaluate(bedrooms, (PROXIMITY,), (missing,)).status
        is EvaluationStatus.NOT_APPLICABLE
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"source_type": "kitchen"},
        {"target_type": "unknown"},
        {"rule_id": " "},
        {"preferred_maximum_distance": -1},
        {"preferred_maximum_distance": float("nan")},
        {"zero_score_distance": 5},
        {"zero_score_distance": float("inf")},
        {"weight": 0},
        {"weight": float("inf")},
    ],
)
def test_invalid_rule_values_are_rejected(changes):
    with pytest.raises(ScoringConfigurationError):
        replace(PROXIMITY, **changes)


def test_invalid_clustering_types_and_duplicate_rule_ids_are_rejected():
    with pytest.raises(ScoringConfigurationError):
        replace(CLUSTERING, room_types=())
    with pytest.raises(ScoringConfigurationError):
        RoomRelationshipQualitySettings(
            (PROXIMITY,),
            (replace(CLUSTERING, rule_id=PROXIMITY.rule_id),),
        )
