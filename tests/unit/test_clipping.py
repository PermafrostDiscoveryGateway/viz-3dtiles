import pytest
from shapely.geometry import MultiPolygon, Point, Polygon, box

from pdg3dtiles.clipping import clip_to_max_extent


def _extent(poly):
    minx, miny, maxx, maxy = poly.bounds
    return max(maxx - minx, maxy - miny)


def test_small_geometry_is_returned_unchanged():
    geom = MultiPolygon([box(0, 0, 5, 5)])
    assert clip_to_max_extent(geom, 10.0) is geom


def test_large_polygon_is_cut_into_bounded_parts_preserving_area():
    ring = box(0, 0, 95, 37)
    hole = box(40, 10, 60, 30)
    geom = MultiPolygon([Polygon(ring.exterior.coords, [hole.exterior.coords])])

    clipped = clip_to_max_extent(geom, 10.0)

    assert isinstance(clipped, MultiPolygon)
    assert len(clipped.geoms) > 1
    assert all(_extent(p) <= 10.0 + 1e-9 for p in clipped.geoms)
    assert clipped.area == pytest.approx(geom.area, rel=1e-9)
    assert not clipped.intersects(hole.buffer(-1e-6))
    # Parts tile the polygon without overlapping.
    assert sum(p.area for p in clipped.geoms) == pytest.approx(clipped.area)


def test_concave_polygon_keeps_its_shape():
    l_shape = Polygon([(0, 0), (60, 0), (60, 10), (10, 10), (10, 60), (0, 60)])
    clipped = clip_to_max_extent(MultiPolygon([l_shape]), 15.0)
    assert clipped.area == pytest.approx(l_shape.area, rel=1e-9)
    assert clipped.symmetric_difference(l_shape).area < 1e-6


def test_invalid_max_extent_raises():
    with pytest.raises(ValueError):
        clip_to_max_extent(MultiPolygon([box(0, 0, 5, 5)]), 0)


def test_non_polygon_output_from_clipping_is_dropped():
    # A polygon touching a cut line only along an edge must not yield lines.
    geom = MultiPolygon([box(0, 0, 20, 5)])
    clipped = clip_to_max_extent(geom, 10.0)
    assert all(isinstance(p, Polygon) and not isinstance(p, Point) for p in clipped.geoms)
    assert clipped.area == pytest.approx(100.0)
