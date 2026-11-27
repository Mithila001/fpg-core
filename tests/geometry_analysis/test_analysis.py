from shapely.geometry import Polygon, box

from fpg_core.geometry_analysis import (
    boundary_distance,
    detect_recesses,
    detect_voids,
    is_rectilinear,
    occupied_footprint,
    room_polygon,
    shared_boundary,
)


def test_room_measurements_and_contact_distinguish_wall_from_corner() -> None:
    first = room_polygon(((0, 0), (2, 0), (2, 2), (0, 2)))
    wall = room_polygon(((2, 0), (4, 0), (4, 2), (2, 2)))
    corner = room_polygon(((2, 2), (4, 2), (4, 4), (2, 4)))

    assert first.area == 4
    assert (first.centroid.x, first.centroid.y) == (1, 1)
    assert shared_boundary(first, wall).length == 2
    assert shared_boundary(first, corner).length == 0
    assert boundary_distance(first, wall) == 0
    assert boundary_distance(first, box(5, 0, 7, 2)) == 3


def test_footprint_void_and_rectilinearity() -> None:
    outer = Polygon(
        ((0, 0), (10, 0), (10, 10), (0, 10)),
        holes=[((2, 2), (2, 4), (4, 4), (4, 2))],
    )
    footprint = occupied_footprint((outer,))

    assert [void.area for void in detect_voids(footprint)] == [4]
    assert is_rectilinear(((0, 0), (2, 0), (2, 1), (0, 1)), 1e-6)
    assert not is_rectilinear(((0, 0), (2, 1), (0, 2)), 1e-6)


def test_recess_detection_can_include_section_entrances() -> None:
    footprint = Polygon(((0, 0), (10, 0), (10, 10), (7, 10), (7, 4), (3, 4), (3, 10), (0, 10)))

    plain = detect_recesses(footprint, 1e-6)
    detailed = detect_recesses(footprint, 1e-6, include_section_entrances=True)

    assert len(plain) == len(detailed) == 1
    assert plain[0].depth == detailed[0].depth == 6
    assert detailed[0].sections
    assert all(section.entrance is not None for section in detailed[0].sections)
