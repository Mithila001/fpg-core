from shapely.geometry import Polygon, box

from fpg_core.floor_plan_post_processing.config import WallExtensionConfig
from fpg_core.floor_plan_post_processing.processors.wall_extension import (
    _patches,
    _problems,
)


def test_problem_detection_finds_pockets_recesses_and_exterior_steps() -> None:
    footprint = box(0, 0, 20, 20).difference(box(8, 8, 12, 12))
    pockets, recesses, steps = _problems(footprint, WallExtensionConfig(), 1e-6)
    assert len(pockets) == 1
    assert pockets[0].area == 16

    stepped = Polygon(((0, 0), (20, 0), (20, 20), (12, 20), (12, 14), (0, 14)))
    _, _, steps = _problems(stepped, WallExtensionConfig(), 1e-6)
    assert steps

    recessed = Polygon(
        ((0, 0), (20, 0), (20, 20), (14, 20), (14, 8), (6, 8), (6, 20), (0, 20))
    )
    _, recesses, _ = _problems(recessed, WallExtensionConfig(), 1e-6)
    assert recesses


def test_candidate_patches_stay_inside_target_and_obey_grid() -> None:
    room = box(0, 0, 10, 10)
    target = box(0, 10, 10, 20)
    patches = list(_patches(room, target, 10, 5, 1, 1e-6))
    assert patches
    assert all(target.covers(patch) for patch in patches)
    assert all(all(value.is_integer() for value in patch.bounds) for patch in patches)
