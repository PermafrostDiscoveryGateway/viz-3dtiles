from __future__ import annotations

import struct
from typing import Any
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pygltflib

from py3dtiles.exceptions import InvalidB3dmError

from . import gltf_utils
from py3dtiles.tileset.content.b3dm_feature_table import B3dmFeatureTable
from .batch_table import BatchTable
from py3dtiles.tileset.content.tile_content import LegacyTileContent, TileContentBody, TileContentHeader


class B3dm(LegacyTileContent):
    def __init__(self, header: B3dmHeader, body: B3dmBody) -> None:
        super().__init__()

        self.header: B3dmHeader = header
        self.body: B3dmBody = body

    def sync(self) -> None:
        """
        Allow to synchronize headers with contents.
        """

        # extract array
        self.body.gltf.set_min_alignment(8)
        gltf_arr = np.frombuffer(
            b"".join(self.body.gltf.save_to_bytes()), dtype=np.uint8
        )

        # sync the tile header with feature table contents
        self.header.tile_byte_length = B3dmHeader.BYTE_LENGTH + len(gltf_arr)
        self.header.ft_json_byte_length = 0
        self.header.ft_bin_byte_length = 0
        self.header.bt_json_byte_length = 0
        self.header.bt_bin_byte_length = 0

        if self.body.feature_table is not None:
            ft_json = self.body.feature_table.header.to_array()
            ft_bin = self.body.feature_table.body.to_array()
            self.header.tile_byte_length += len(ft_json) + len(ft_bin)
            self.header.ft_json_byte_length = len(ft_json)
            self.header.ft_bin_byte_length = len(ft_bin)

        if self.body.batch_table is not None:
            bt_json = self.body.batch_table.header.to_array()
            bt_bin = self.body.batch_table.body.to_array()
            self.header.tile_byte_length += len(bt_json) + len(bt_bin)
            self.header.bt_json_byte_length = len(bt_json)
            self.header.bt_bin_byte_length = len(bt_bin)

    @staticmethod
    def from_numpy_arrays(
        points: npt.NDArray[np.float32],
        triangles: npt.NDArray[np.uint8] | None = None,
        batch_table: BatchTable | None = None,
        feature_table: B3dmFeatureTable | None = None,
        normal: npt.NDArray[np.float32] | None = None,
        uvs: npt.NDArray[np.float32] | None = None,
        batchids: npt.NDArray[np.uint32] | None = None,
        transform: npt.NDArray[np.float32] | None = None,
        texture_uri: str | None = None,
        material: pygltflib.Material | None = None,
    ) -> B3dm:
        """
        Creates a B3DM body from numpy arrays.

        :param points: array of vertex positions, must have a (n, 3) shape.
        :param triangles: array of triangle indices, must have a (n, 3) shape.
        :param batch_table: a batch table.
        :param feature_table: a feature table.
        :param normals: array of vertex normals, must have a (n, 3) shape.
        :param uvs: array of texture coordinates, must have a (n, 2) shape.
        :param batchids: array of batch table IDs, must have a (n) shape.
        :param texture_uri: the URI of the texture image if the primitive is textured.
        :param material: a glTF material. If not set, a default material is created.
        """
        return B3dm.from_meshes(
            [
                gltf_utils.GltfMesh(
                    points,
                    primitives=[
                        gltf_utils.GltfPrimitive(
                            triangles=triangles,
                            material=material,
                            texture_uri=texture_uri,
                        )
                    ],
                    normals=normal,
                    uvs=uvs,
                    batchids=batchids,
                )
            ],
            batch_table,
            feature_table,
            transform,
        )

    @staticmethod
    def from_meshes(
        meshes: list[gltf_utils.GltfMesh],
        batch_table: BatchTable | None = None,
        feature_table: B3dmFeatureTable | None = None,
        transform: npt.NDArray[np.float32] | None = None,
    ) -> B3dm:
        """
        Create a b3dm from GltfMesh instances. This allows for finer control than `from_numpy_arrays` by allowing several meshes in one b3dm.
        """
        b3dm_header = B3dmHeader()
        b3dm_body = B3dmBody.from_meshes(meshes, transform)
        if batch_table is not None:
            b3dm_body.batch_table = batch_table
        if feature_table is not None:
            b3dm_body.feature_table = feature_table
        b3dm = B3dm(b3dm_header, b3dm_body)
        b3dm.sync()
        return b3dm

    @staticmethod
    def from_gltf(
        gltf: pygltflib.GLTF2,
        batch_table: BatchTable | None = None,
        feature_table: B3dmFeatureTable | None = None,
    ) -> B3dm:
        """
        Wrap a pygltflib.GLTF2 instance into a b3dm. This gives the most control on the scene creation, as pygltflib.GLTF2 instance are as near as possible to the gltf specification.
        """
        b3dm_body = B3dmBody()
        b3dm_body.gltf = gltf
        if batch_table is not None:
            b3dm_body.batch_table = batch_table
        if feature_table is not None:
            b3dm_body.feature_table = feature_table

        b3dm_header = B3dmHeader()
        b3dm = B3dm(b3dm_header, b3dm_body)
        b3dm.sync()

        return b3dm

    @staticmethod
    def from_bytes(data: bytes) -> B3dm:
        arr = np.frombuffer(data, dtype=np.uint8)
        return B3dm.from_array(arr)

    @classmethod
    def from_array(cls, array: npt.NDArray[np.uint8]) -> B3dm:
        # build tile header
        h_arr = array[: B3dmHeader.BYTE_LENGTH]
        b3dm_header = B3dmHeader.from_array(h_arr)

        if b3dm_header.tile_byte_length != len(array):
            raise InvalidB3dmError(
                f"Invalid byte length in header, the size of array is {len(array)}, "
                f"the tile_byte_length for header is {b3dm_header.tile_byte_length}"
            )

        # build tile body
        b_arr = array[B3dmHeader.BYTE_LENGTH :]
        b3dm_body = B3dmBody.from_array(b3dm_header, b_arr)
        b3dm = cls(b3dm_header, b3dm_body)
        b3dm.sync()

        return b3dm

    def get_vertex_count(self) -> int:
        return gltf_utils.get_vertex_count(self.body.gltf)

    def get_vertices(self) -> npt.NDArray[np.float32 | np.uint16] | None:
        return gltf_utils.get_attribute(self.body.gltf, "POSITION")

    def get_colors(self) -> npt.NDArray[np.uint8 | np.uint16 | np.float32] | None:
        return gltf_utils.get_attribute(self.body.gltf, "COLOR_0")

    def get_extra_field(self, fieldname: str) -> npt.NDArray[Any] | None:
        accessor_name = f"_{fieldname.upper()}"
        return gltf_utils.get_attribute(self.body.gltf, accessor_name)
    
    def save_debug_glb(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.body.gltf.set_min_alignment(8)

        with open(path, "wb") as f:
            f.write(b"".join(self.body.gltf.save_to_bytes()))


class B3dmHeader(TileContentHeader):
    BYTE_LENGTH = 28

    def __init__(self) -> None:
        super().__init__()
        self.magic_value = b"b3dm"
        self.version = 1

    def to_array(self) -> npt.NDArray[np.uint8]:
        header_arr = np.frombuffer(self.magic_value, np.uint8)

        header_arr2 = np.array(
            [
                self.version,
                self.tile_byte_length,
                self.ft_json_byte_length,
                self.ft_bin_byte_length,
                self.bt_json_byte_length,
                self.bt_bin_byte_length,
            ],
            dtype=np.uint32,
        )

        return np.concatenate((header_arr, header_arr2.view(np.uint8)))

    @staticmethod
    def from_array(array: npt.NDArray[np.uint8]) -> B3dmHeader:
        h = B3dmHeader()

        if len(array) != B3dmHeader.BYTE_LENGTH:
            raise InvalidB3dmError(
                f"Invalid header byte length, the size of array is {len(array)}, "
                f"the header must have a size of {B3dmHeader.BYTE_LENGTH}"
            )

        h.version = struct.unpack("i", array[4:8].tobytes())[0]
        h.tile_byte_length = struct.unpack("i", array[8:12].tobytes())[0]
        h.ft_json_byte_length = struct.unpack("i", array[12:16].tobytes())[0]
        h.ft_bin_byte_length = struct.unpack("i", array[16:20].tobytes())[0]
        h.bt_json_byte_length = struct.unpack("i", array[20:24].tobytes())[0]
        h.bt_bin_byte_length = struct.unpack("i", array[24:28].tobytes())[0]

        return h


class B3dmBody(TileContentBody):
    def __init__(self) -> None:
        self.batch_table = BatchTable()
        self.feature_table: B3dmFeatureTable = B3dmFeatureTable()
        self.gltf = pygltflib.GLTF2()

    def __str__(self) -> str:
        gltf_byte_components = self.gltf.save_to_bytes()
        infos = {
            "feature_table_batch_length": self.feature_table.get_batch_length(),
            "gltf_magic": pygltflib.MAGIC,
            "gltf_version": self.gltf.asset.version,
            "gltf_length": len(b"".join(gltf_byte_components)),
            "gltf_json_chunk_length": len(gltf_byte_components[5]),
            "gltf_bin_chunk_length": len(gltf_byte_components[-1]),
        }
        return "\n".join(f"{key}: {value}" for key, value in infos.items())

    def to_array(self) -> npt.NDArray[np.uint8]:
        if self.feature_table:
            feature_table = self.feature_table.to_array()
        else:
            feature_table = np.array([], dtype=np.uint8)

        if self.batch_table:
            batch_table = self.batch_table.to_array()
        else:
            batch_table = np.array([], dtype=np.uint8)

        # The glTF part must start and end on an 8-byte boundary
        return np.concatenate(
            (
                feature_table,
                batch_table,
                np.frombuffer(b"".join(self.gltf.save_to_bytes()), dtype=np.uint8),
            )
        )

    @staticmethod
    def from_meshes(
        meshes: list[gltf_utils.GltfMesh],
        transform: npt.NDArray[np.float32] | None = None,
    ) -> B3dmBody:
        gltf = gltf_utils.gltf_from_meshes(meshes, transform=transform)
        return B3dmBody.from_gltf(gltf)

    @staticmethod
    def from_gltf(gltf: pygltflib.GLTF2) -> B3dmBody:
        # build tile body
        b = B3dmBody()
        b.gltf = gltf

        return b

    @staticmethod
    def from_array(b3dm_header: B3dmHeader, array: npt.NDArray[np.uint8]) -> B3dmBody:
        # build feature table
        ft_len = b3dm_header.ft_json_byte_length + b3dm_header.ft_bin_byte_length

        # build batch table
        bt_len = b3dm_header.bt_json_byte_length + b3dm_header.bt_bin_byte_length

        # build glTF
        gltf_len = (
            b3dm_header.tile_byte_length - ft_len - bt_len - B3dmHeader.BYTE_LENGTH
        )
        gltf_arr = array[ft_len + bt_len : ft_len + bt_len + gltf_len]
        gltf = pygltflib.GLTF2.load_from_bytes(b"".join(gltf_arr))

        # build tile body with batch table
        b = B3dmBody()
        b.gltf = gltf
        if ft_len > 0:
            b.feature_table = B3dmFeatureTable.from_array(b3dm_header, array[:ft_len])
        if bt_len > 0:
            batch_len = b.feature_table.get_batch_length()
            b.batch_table = BatchTable.from_array(
                b3dm_header, array[ft_len : ft_len + bt_len], batch_len
            )

        return b