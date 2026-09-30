"""Cut large polygons into bounded parts before triangulation.

Triangulating a big polygon in ECEF yields a few huge, thin triangles whose
straight chords sink below the ellipsoid (about L^2 / (8 R): 12 m at 25 km,
196 m at 100 km). A polygon lifted only a few metres is then hidden by a
depth-tested globe wherever such a triangle spans its interior. Splitting the
polygon into parts no larger than ``max_extent`` bounds every triangle edge by
the part diagonal, so the sag stays small, and it keeps triangle quality (and
count) proportional to area rather than to the length of earcut's slivers.
"""

from __future__ import annotations

import shapely
from shapely.geometry import MultiPolygon, Polygon, box


def _polygon_parts(geometry):
    return [
        part
        for part in shapely.get_parts(geometry)
        if isinstance(part, Polygon) and not part.is_empty and part.area > 0
    ]


def _clip(geometry, bounds, max_extent, out):
    minx, miny, maxx, maxy = bounds
    if max(maxx - minx, maxy - miny) <= max_extent:
        out.extend(_polygon_parts(geometry))
        return
    if maxx - minx >= maxy - miny:
        mid = (minx + maxx) / 2
        halves = ((minx, miny, mid, maxy), (mid, miny, maxx, maxy))
    else:
        mid = (miny + maxy) / 2
        halves = ((minx, miny, maxx, mid), (minx, mid, maxx, maxy))
    for half in halves:
        piece = shapely.intersection(geometry, box(*half))
        if not piece.is_empty:
            _clip(piece, half, max_extent, out)


def clip_to_max_extent(geometry, max_extent):
    """Return ``geometry`` as a MultiPolygon whose parts span at most ``max_extent``.

    ``max_extent`` is in the geometry's own units. Geometry that already fits
    is returned unchanged. Works on 2D input; clipping discards Z.
    """
    if max_extent is None:
        return geometry
    if max_extent <= 0:
        raise ValueError("max_extent must be positive")

    minx, miny, maxx, maxy = geometry.bounds
    if max(maxx - minx, maxy - miny) <= max_extent:
        return geometry

    parts = []
    _clip(geometry, (minx, miny, maxx, maxy), max_extent, parts)
    return MultiPolygon(parts)
