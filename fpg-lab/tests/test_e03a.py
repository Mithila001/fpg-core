from fractions import Fraction
from itertools import product
from time import monotonic

import pytest
from fpg_core.domain import RoomSizeSpec, RoomType, RoomWidthAxis

from fpg_lab.flows.e03a import AreaRange, analyze, enumerate_dimensions
from fpg_lab.flows.e03a_config import (
    CONFIG_PATH,
    E02A_PATH,
    Configuration,
    export,
    import_e02a,
    maximum_counts,
    parse,
    save,
)


def test_import_and_explicit_save(tmp_path, monkeypatch):
    original = E02A_PATH.read_bytes()
    starter = parse(CONFIG_PATH.read_bytes())
    draft = starter.model_dump(mode="json")
    draft["rooms"]["bedroom"]["count"] = 8
    draft["rooms"]["attached_bathroom"]["count"] = 5
    draft["rooms"]["bathroom"]["count"] = 2
    imported = import_e02a(draft)
    assert imported.rooms["bedroom"].count == imported.rooms["attached_bathroom"].count == 5
    assert imported.rooms["bathroom"].count == 2
    assert imported.cross_type_rules == starter.cross_type_rules
    assert imported.same_type_rules == starter.same_type_rules
    assert str(imported.aspect_for("garage").max_ratio) == "0.7"
    assert draft["rooms"]["bedroom"]["count"] == 8
    assert E02A_PATH.read_bytes() == original
    draft["rooms"]["bedroom"]["maximum_count"] = 2
    counts = maximum_counts(draft["rooms"], True)
    assert counts["bedroom"]["count"] == counts["attached_bathroom"]["count"] == 2

    saved = tmp_path / "config.json"
    initial = save(starter, None, saved)
    assert parse(export(imported)) == imported
    assert save(imported, initial, saved) == export(imported)
    with pytest.raises(ValueError, match="saved file changed"):
        save(starter, initial, saved)
    assert parse(saved.read_bytes()) == imported

    def fail_replace(*_):
        raise OSError("disk error")

    monkeypatch.setattr(type(saved), "replace", fail_replace)
    with pytest.raises(OSError, match="disk error"):
        save(starter, export(imported), saved)
    assert list(tmp_path.iterdir()) == [saved]
    assert parse(saved.read_bytes()) == imported


def test_dimension_gaps_and_axis():
    deadline = monotonic() + 2
    any_axis = enumerate_dimensions(RoomSizeSpec(2, 2, 4, 9), None, 1000, deadline)
    assert any_axis == {4: ((2, 2),), 6: ((2, 3), (3, 2)), 8: ((2, 4), (4, 2))}
    x = enumerate_dimensions(RoomSizeSpec(2, 2, 4, 9, RoomWidthAxis.X), None, 1000, deadline)
    y = enumerate_dimensions(RoomSizeSpec(2, 2, 4, 9, RoomWidthAxis.Y), None, 1000, deadline)
    assert x[8] == ((2, 4),)
    assert y[8] == ((4, 2),)
    starter = parse(CONFIG_PATH.read_bytes())
    result = analyze(starter)
    assert result.status == "compatible"
    assert 900 in result.supported["bedroom_1"]
    assert max(result.dimensions["living_room_1"]) == 3000
    assert all(
        Fraction(3, 5) <= Fraction(x, y) <= Fraction(9, 5)
        for pairs in result.dimensions["living_room_1"].values()
        for x, y in pairs
    )


def test_exact_support_against_brute_force():
    draft = parse(CONFIG_PATH.read_bytes()).model_dump(mode="json")
    draft["default_aspect"] = None
    for room, settings in draft["rooms"].items():
        count = {"bedroom": 2, "bathroom": 1, "living_room": 1}.get(room, 0)
        settings.update(
            min_width=1,
            max_width=2,
            min_area=2,
            max_area=5,
            minimum_count=count,
            maximum_count=count,
            count=count,
        )
    draft["cross_type_rules"] = [
        {"compared_type": "bathroom", "reference_type": "bedroom", "max_ratio": "0.75"},
        {"compared_type": "bedroom", "reference_type": "living_room", "max_ratio": "0.75"},
        {"compared_type": "garage", "reference_type": "bedroom", "min_ratio": "2"},
    ]
    draft["same_type_rules"] = [{"room_type": "bedroom", "maximum_spread_ratio": "0.5"}]
    config = Configuration.model_validate(draft)
    baseline = analyze(config)
    assert len(baseline.inactive) == 1
    bedroom, living_room = RoomType.BEDROOM, RoomType.LIVING_ROOM
    for locks in (
        {},
        {living_room: AreaRange(4, 5)},
        {bedroom: AreaRange(2, 4), living_room: AreaRange(3, 5)},
        {living_room: AreaRange(2, 3)},
        {living_room: AreaRange(6, 7)},
        {},
    ):
        result = analyze(config, locks, baseline)
        rooms = result.room_ids
        exhaustive = []
        for sizes in product((2, 3, 4, 5), repeat=len(rooms)):
            a, b, bath, living = sizes
            kinds = (bedroom, bedroom, RoomType.BATHROOM, living_room)
            if any(
                not locks[kind].minimum <= area <= locks[kind].maximum
                for kind, area in zip(kinds, sizes, strict=True)
                if kind in locks
            ):
                continue
            if (
                4 * bath <= 3 * min(a, b)
                and 4 * max(a, b) <= 3 * living
                and 2 * max(a, b) <= 3 * min(a, b)
            ):
                exhaustive.append(sizes)
        for i, room in enumerate(rooms):
            expected = tuple(sorted({sizes[i] for sizes in exhaustive}))
            assert result.supported[room] == expected
            assert result.flexibility(room) == 25 * len(expected)
        assert bool(result.witness) == bool(exhaustive)
        if exhaustive:
            assert tuple(result.witness[room][2] for room in rooms) in exhaustive
            maximum_difference = max(abs(a - b) for a, b, _, _ in exhaustive)
            maximum_spread = max(Fraction(abs(a - b), min(a, b)) for a, b, _, _ in exhaustive)
            variation = result.variation[bedroom]
            assert (variation.difference, variation.spread) == (maximum_difference, maximum_spread)
            assert variation.restricted_by_other_rules
        else:
            assert result.category == "Area-range lock"

    equal_draft = {
        **draft,
        "cross_type_rules": (),
        "same_type_rules": [
            {"room_type": "bedroom", "maximum_spread_ratio": "0"},
        ],
    }
    equal = analyze(Configuration.model_validate(equal_draft))
    assert equal.flexibility("bedroom_1") == 100
    assert equal.variation[bedroom].spread == 0
    assert not equal.variation[bedroom].restricted_by_other_rules
    equal_draft["same_type_rules"][0]["maximum_spread_ratio"] = "0.5"
    varied = analyze(Configuration.model_validate(equal_draft), {bedroom: AreaRange(2, 4)})
    assert varied.variation[bedroom].spread == Fraction(1, 2)
    with pytest.raises(ValueError, match="positive whole areas"):
        AreaRange(5, 4)

    draft["cross_type_rules"].append(
        {"compared_type": "living_room", "reference_type": "bathroom", "max_ratio": "0.75"}
    )
    cyclic = Configuration.model_validate(draft)
    assert analyze(cyclic).category == "Combined"
    assert analyze(config, seconds=0).status == "incomplete"
    draft["cross_type_rules"][-1]["min_ratio"] = "1"
    with pytest.raises(ValueError, match="Minimum area ratio exceeds maximum"):
        Configuration.model_validate(draft)
