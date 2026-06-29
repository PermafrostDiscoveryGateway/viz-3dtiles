from __future__ import annotations

from dataclasses import dataclass

import mapbox_earcut as earcut
import numpy as np
import numpy.typing as npt
from shapely.geometry import MultiPolygon, Polygon


@dataclass(slots=True)
class TriangulatedMesh:
    positions: npt.NDArray[np.float64]
    normals: npt.NDArray[np.float32]
    indices: npt.NDArray[np.uint32]


def empty_mesh() -> TriangulatedMesh:
    return TriangulatedMesh(
        positions=np.empty((0, 3), dtype=np.float64),
        normals=np.empty((0, 3), dtype=np.float32),
        indices=np.empty((0, 3), dtype=np.uint32),
    )


def triangulate_multipolygon(geometry: Polygon | MultiPolygon) -> TriangulatedMesh:
    """Triangulate a Shapely polygon while preserving float64 ECEF vertices."""
    polygons = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]

    position_chunks: list[npt.NDArray[np.float64]] = []
    normal_chunks: list[npt.NDArray[np.float32]] = []
    index_chunks: list[npt.NDArray[np.uint32]] = []
    vertex_offset = 0

    for polygon in polygons:
        mesh = _triangulate_polygon(polygon)
        if mesh.positions.size == 0:
            continue

        position_chunks.append(mesh.positions)
        normal_chunks.append(mesh.normals)
        index_chunks.append(mesh.indices + vertex_offset)
        vertex_offset += mesh.positions.shape[0]

    if not position_chunks:
        return empty_mesh()

    return TriangulatedMesh(
        positions=np.concatenate(position_chunks, axis=0),
        normals=np.concatenate(normal_chunks, axis=0),
        indices=np.concatenate(index_chunks, axis=0),
    )


def _triangulate_polygon(polygon: Polygon) -> TriangulatedMesh:
    exterior = _ring_to_array(polygon.exterior)
    if exterior is None or exterior.shape[0] < 3:
        return empty_mesh()

    rings = [exterior]
    for interior in polygon.interiors:
        ring = _ring_to_array(interior)
        if ring is not None and ring.shape[0] >= 3:
            rings.append(ring)

    vertices = np.ascontiguousarray(np.vstack(rings), dtype=np.float64)
    if not np.isfinite(vertices).all():
        return empty_mesh()

    polygon_normal = _newell_normal(rings[0])
    if not np.any(polygon_normal):
        return empty_mesh()

    projected = _project_for_earcut(vertices, polygon_normal)
    ring_end_indices = np.cumsum([ring.shape[0] for ring in rings], dtype=np.uint32)
    triangle_indices = earcut.triangulate_float32(projected, ring_end_indices)

    if triangle_indices.size == 0:
        return empty_mesh()

    triangles = np.ascontiguousarray(triangle_indices.reshape((-1, 3)), dtype=np.uint32)
    _orient_triangles(vertices, triangles, polygon_normal)
    normals = _vertex_normals(vertices, triangles, polygon_normal)

    return TriangulatedMesh(positions=vertices, normals=normals, indices=triangles)


def _ring_to_array(ring: object) -> npt.NDArray[np.float64] | None:
    coords = np.asarray(getattr(ring, "coords"), dtype=np.float64)
    if coords.ndim != 2 or coords.shape[0] < 4:
        return None

    if coords.shape[1] == 2:
        coords = np.column_stack((coords, np.zeros(coords.shape[0], dtype=np.float64)))
    elif coords.shape[1] > 3:
        coords = coords[:, :3]

    if np.allclose(coords[0], coords[-1], rtol=0.0, atol=1e-12):
        coords = coords[:-1]

    return np.ascontiguousarray(coords, dtype=np.float64)


def _newell_normal(ring: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    current = ring
    next_point = np.roll(ring, -1, axis=0)
    return np.array(
        [
            np.sum(
                (current[:, 1] - next_point[:, 1]) * (next_point[:, 2] + current[:, 2])
            ),
            np.sum(
                (current[:, 2] - next_point[:, 2]) * (next_point[:, 0] + current[:, 0])
            ),
            np.sum(
                (current[:, 0] - next_point[:, 0]) * (next_point[:, 1] + current[:, 1])
            ),
        ],
        dtype=np.float64,
    )


def _project_for_earcut(
    vertices: npt.NDArray[np.float64], normal: npt.NDArray[np.float64]
) -> npt.NDArray[np.float32]:
    axis = int(np.argmax(np.abs(normal)))
    if axis == 0:
        projected = vertices[:, [1, 2]]
    elif axis == 1:
        projected = vertices[:, [0, 2]]
    else:
        projected = vertices[:, [0, 1]]

    # ECEF coordinates are large. Translate before float32 earcut input so
    # triangulation sees local meter-scale offsets instead of million-meter values.
    local_projected = projected - projected[0]
    return np.ascontiguousarray(local_projected, dtype=np.float32)


def _orient_triangles(
    vertices: npt.NDArray[np.float64],
    triangles: npt.NDArray[np.uint32],
    polygon_normal: npt.NDArray[np.float64],
) -> None:
    p0 = vertices[triangles[:, 0]]
    p1 = vertices[triangles[:, 1]]
    p2 = vertices[triangles[:, 2]]
    cross_products = np.cross(p1 - p0, p2 - p0)
    inverted = cross_products @ polygon_normal < 0

    if inverted.any():
        first = triangles[inverted, 0].copy()
        triangles[inverted, 0] = triangles[inverted, 1]
        triangles[inverted, 1] = first


def _vertex_normals(
    vertices: npt.NDArray[np.float64],
    triangles: npt.NDArray[np.uint32],
    polygon_normal: npt.NDArray[np.float64],
) -> npt.NDArray[np.float32]:
    p0 = vertices[triangles[:, 0]]
    p1 = vertices[triangles[:, 1]]
    p2 = vertices[triangles[:, 2]]
    face_normals = np.cross(p1 - p0, p2 - p0)

    lengths = np.linalg.norm(face_normals, axis=1)
    valid = lengths > 0
    face_normals[valid] /= lengths[valid, None]
    face_normals[~valid] = _unit_normal(polygon_normal)

    normals = np.zeros(vertices.shape, dtype=np.float64)
    for column in range(3):
        np.add.at(normals, triangles[:, column], face_normals)

    lengths = np.linalg.norm(normals, axis=1)
    fallback = _unit_normal(polygon_normal)
    valid = lengths > 0
    normals[valid] /= lengths[valid, None]
    normals[~valid] = fallback

    return normals.astype(np.float32)


def _unit_normal(normal: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    length = np.linalg.norm(normal)
    if length == 0:
        return np.array([0.0, 0.0, 1.0], dtype=np.float64)
    return normal / length
