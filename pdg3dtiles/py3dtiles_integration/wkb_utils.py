from __future__ import annotations

import math
import struct

import mapbox_earcut as earcut
import numpy as np
import numpy.typing as npt

CoordinateType = npt.NDArray[np.float32]
LineType = list[CoordinateType]
PolygonType = list[LineType]
MultiPolygonsType = list[PolygonType]

PolygonAsTriangleType = list[npt.NDArray[np.float32]]


class TriangleSoup:
    def __init__(self) -> None:
        self.triangles: list[PolygonAsTriangleType] = []

    @property
    def vertices(self) -> npt.NDArray[np.float32]:
        return np.unique(np.concatenate(self.triangles[0]), axis=0)

    @property
    def triangle_indices(self) -> npt.NDArray[np.uint32]:
        flattened = np.concatenate(self.triangles[0])

        vertex_map: dict[bytes, int] = {}
        indices: list[int] = []

        next_index = 0
        for v in flattened:
            key = v.tobytes()
            if key not in vertex_map:
                vertex_map[key] = next_index
                next_index += 1
            indices.append(vertex_map[key])

        return np.array(indices, dtype=np.uint32).reshape(-1, 3)

    @staticmethod
    def from_wkb_multipolygon(
        wkb: bytes, associated_data: list[bytes] | None = None
    ) -> "TriangleSoup":
        """
        Build a TriangleSoup from a WKB multipolygon.

        associated_data can contain parallel multipolygons whose vertices should
        be triangulated in the same way as the primary geometry.
        """
        multipolygons: list[MultiPolygonsType] = [parse(bytes(wkb))]

        if associated_data is None:
            associated_data = []

        for additional_wkb in associated_data:
            multipolygons.append(parse(bytes(additional_wkb)))

        triangles_array: list[PolygonAsTriangleType] = [
            [] for _ in range(len(multipolygons))
        ]

        for i in range(len(multipolygons[0])):
            polygon: PolygonType = multipolygons[0][i]
            additional_polygons = [mp[i] for mp in multipolygons[1:]]
            triangles = triangulate(polygon, additional_polygons)

            for array, tri in zip(triangles_array, triangles):
                array += tri

        ts = TriangleSoup()
        ts.triangles = triangles_array
        return ts

    def get_position_array(self) -> bytes:
        """
        Return a binary array of vertex positions.
        """
        vertex_array = vertex_attribute_to_array(self.triangles[0])
        return b"".join(vertex.tobytes() for vertex in vertex_array)

    def get_data_array(self, index: int) -> bytes:
        """
        Return a binary array of vertex-associated data.
        """
        vertex_triangles = self.triangles[1 + index]
        vertex_array = vertex_attribute_to_array(vertex_triangles)
        return b"".join(vertex.tobytes() for vertex in vertex_array)

    def get_data(self, index: int) -> npt.NDArray[np.float32]:
        """
        Return vertex-associated data as a numpy array.
        """
        vertex_triangles = self.triangles[1 + index]
        return np.array(vertex_attribute_to_array(vertex_triangles))

    def get_normal_array(self) -> bytes:
        """
        Return a binary array of vertex normals.
        """
        vertex_array = self.compute_normals()
        return b"".join(vertex.tobytes() for vertex in vertex_array)

    def compute_normals(self) -> npt.NDArray[np.float32]:
        """
        Compute per-face normals and expand them to per-vertex normals.
        """
        normals: list[CoordinateType] = []

        for t in self.triangles[0]:
            u_vec = t[1] - t[0]
            v_vec = t[2] - t[0]
            normal = np.cross(u_vec, v_vec)
            norm = np.linalg.norm(normal)

            if norm == 0:
                normals.append(np.array([0, 0, 1], dtype=np.float32))
            else:
                normals.append(normal / norm)

        return np.array(face_attribute_to_array(normals))

    def get_bbox(self) -> list[npt.NDArray[np.float32]]:
        """
        Return the bounding box as:
        [[minX, minY, minZ], [maxX, maxY, maxZ]]
        """
        mins = np.array([np.min(t, axis=0) for t in self.triangles[0]])
        maxs = np.array([np.max(t, axis=0) for t in self.triangles[0]])
        return [np.min(mins, axis=0), np.max(maxs, axis=0)]


def face_attribute_to_array(triangles: list[CoordinateType]) -> list[CoordinateType]:
    array: list[CoordinateType] = []
    for face in triangles:
        array += [face, face, face]
    return array


def vertex_attribute_to_array(triangles: PolygonAsTriangleType) -> list[CoordinateType]:
    array: list[CoordinateType] = []
    for face in triangles:
        for vertex in face:
            array.append(vertex)
    return array


def parse(wkb: bytes) -> MultiPolygonsType:
    """
    Parse a WKB multipolygon using legacy-compatible behavior.
    """
    multipolygon: MultiPolygonsType = []

    byteorder = struct.unpack("b", wkb[0:1])
    bo = "<" if byteorder[0] else ">"

    geomtype = struct.unpack(bo + "I", wkb[1:5])[0]

    has_z = (geomtype in [1006, 2147483654]) or (geomtype == 1015)

    pnt_offset = 24 if has_z else 16
    pnt_unpack = bo + ("ddd" if has_z else "dd")

    geom_nb = struct.unpack(bo + "I", wkb[5:9])[0]
    offset = 9

    for _ in range(geom_nb):
        offset += 5

        line_nb = struct.unpack(bo + "I", wkb[offset : offset + 4])[0]
        offset += 4

        polygon: PolygonType = []
        for _ in range(line_nb):
            point_nb = struct.unpack(bo + "I", wkb[offset : offset + 4])[0]
            offset += 4

            line: LineType = []
            for _ in range(point_nb - 1):
                pt = np.array(
                    struct.unpack(pnt_unpack, wkb[offset : offset + pnt_offset]),
                    dtype=np.float32,
                )
                offset += pnt_offset
                line.append(pt)

            offset += pnt_offset
            polygon.append(line)

        multipolygon.append(polygon)

    return multipolygon


def triangulate(
    polygon: PolygonType, additional_polygons: list[PolygonType] | None = None
) -> list[PolygonAsTriangleType]:
    """
    Triangulates 3D polygons by projecting them to the dominant 2D plane,
    triangulating there, and mapping indices back to the original 3D vertices.
    """
    vect_prod = np.array([0, 0, 0], dtype=np.float32)
    for i in range(len(polygon[0])):
        curr_edge = polygon[0][i]
        next_edge = polygon[0][(i + 1) % len(polygon[0])]
        vect_prod += np.array(
            [
                (curr_edge[1] - next_edge[1]) * (next_edge[2] + curr_edge[2]),
                (curr_edge[2] - next_edge[2]) * (next_edge[0] + curr_edge[0]),
                (curr_edge[0] - next_edge[0]) * (next_edge[1] + curr_edge[1]),
            ],
            dtype=np.float32,
        )

    if additional_polygons is None:
        additional_polygons = []

    polygon_2d: list[float] = []

    # Earcut wants start indices of inner rings only.
    holes = []
    delta = 0
    for p in polygon:
        delta += len(p)
        holes.append(delta)

    hole_start_indices: list[int] = []
    delta = len(polygon[0])
    for ring in polygon[1:]:
        hole_start_indices.append(delta)
        delta += len(ring)

    if math.fabs(vect_prod[0]) > math.fabs(vect_prod[1]) and math.fabs(
        vect_prod[0]
    ) > math.fabs(vect_prod[2]):
        # yz projection
        for linestring in polygon:
            for point in linestring:
                polygon_2d.extend([point[1], point[2]])
    elif math.fabs(vect_prod[1]) > math.fabs(vect_prod[2]):
        # xz projection
        for linestring in polygon:
            for point in linestring:
                polygon_2d.extend([point[0], point[2]])
    else:
        # xy projection
        for linestring in polygon:
            for point in linestring:
                polygon_2d.extend([point[0], point[1]])

    polygon_2d_numpy = np.array(polygon_2d, dtype=np.float32).reshape(-1, 2)
    ring_end_indices = np.array(holes, dtype=np.uint32)
    triangles_idx = earcut.triangulate_float32(polygon_2d_numpy, ring_end_indices)

    arrays: list[PolygonAsTriangleType] = [
        [] for _ in range(len(additional_polygons) + 1)
    ]
    for i in range(0, len(triangles_idx), 3):
        t = triangles_idx[i : i + 3]
        p0 = unflatten(polygon, hole_start_indices, int(t[0]))
        p1 = unflatten(polygon, hole_start_indices, int(t[1]))
        p2 = unflatten(polygon, hole_start_indices, int(t[2]))

        cross_product = np.cross(p1 - p0, p2 - p0)
        invert = np.dot(vect_prod, cross_product) < 0

        if invert:
            arrays[0].append(np.array([p1, p0, p2], dtype=np.float32))
        else:
            arrays[0].append(np.array([p0, p1, p2], dtype=np.float32))

        for array, additional_polygon in zip(arrays[1:], additional_polygons):
            pp0 = unflatten(additional_polygon, hole_start_indices, int(t[0]))
            pp1 = unflatten(additional_polygon, hole_start_indices, int(t[1]))
            pp2 = unflatten(additional_polygon, hole_start_indices, int(t[2]))
            if invert:
                array.append(np.array([pp1, pp0, pp2], dtype=np.float32))
            else:
                array.append(np.array([pp0, pp1, pp2], dtype=np.float32))

    return arrays


def unflatten(array: PolygonType, lengths: list[int], index: int) -> CoordinateType:
    for i in reversed(range(len(lengths))):
        lgth = lengths[i]
        if index >= lgth:
            return array[i + 1][index - lgth]
    return array[0][index]


__all__ = [
    "CoordinateType",
    "LineType",
    "PolygonType",
    "MultiPolygonsType",
    "PolygonAsTriangleType",
    "TriangleSoup",
    "face_attribute_to_array",
    "vertex_attribute_to_array",
    "parse",
    "triangulate",
    "unflatten",
]