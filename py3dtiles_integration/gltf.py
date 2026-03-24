from __future__ import annotations

from typing import Any, cast

import numpy as np
import numpy.typing as npt
from pygltflib import GLTF2

from py3dtiles.exceptions import InvalidGltfError
from py3dtiles.tileset.content.gltf import Gltf as UpstreamGltf
from py3dtiles_integration import gltf_utils


class Gltf(UpstreamGltf):
    """
    Compatibility wrapper for old viz-3dtiles usage.

    This restores:
    - GlTF.from_array(...)
    - GlTF.from_binary_arrays(...)
    - GlTF alias
    - batch_length tracking
    """

    def __init__(self, gltf: GLTF2 | None = None) -> None:
        super().__init__(gltf)
        self.batch_length: int = 0

    @property
    def header(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._gltf.to_dict())

    @property
    def body(self) -> npt.NDArray[np.uint8] | None:
        binary_blob = self._gltf.binary_blob()
        if binary_blob is None:
            return None
        return np.frombuffer(binary_blob, dtype=np.uint8)

    @classmethod
    def from_bytes(cls, data: bytes) -> "Gltf":
        parsed = GLTF2().load_from_bytes(data)
        return cls(parsed)

    @classmethod
    def from_array(cls, array: npt.NDArray[np.uint8]) -> "Gltf":
        """
        Old API compatibility: GlTF.from_array(array)
        """
        return cls.from_bytes(array.tobytes())

    @classmethod
    def from_binary_arrays(
        cls,
        arrays: list[dict[str, Any]],
        transform: npt.NDArray[np.float32] | None,
        batched: bool = True,
        uri: str | None = None,
        texture_uri: str | None = None,
    ) -> "Gltf":
        """
        Old API compatibility used by viz-3dtiles.

        Expected geometry dict keys:
        - position: bytes of float32 xyz triples
        - normal: bytes of float32 xyz triples
        - uv: optional bytes of float32 uv pairs
        - properties: optional metadata dict
        """
        del uri

        if not arrays:
            raise InvalidGltfError("'arrays' must contain at least one geometry.")

        textured = "uv" in arrays[0]
        meshes: list[gltf_utils.GltfMesh] = []

        for i, geometry in enumerate(arrays):
            if "position" not in geometry:
                raise InvalidGltfError("Missing 'position' in geometry.")
            if "normal" not in geometry:
                raise InvalidGltfError("Missing 'normal' in geometry.")

            positions = np.frombuffer(geometry["position"], dtype=np.float32).reshape((-1, 3))
            normals = np.frombuffer(geometry["normal"], dtype=np.float32).reshape((-1, 3))

            uvs = (
                np.frombuffer(geometry["uv"], dtype=np.float32).reshape((-1, 2))
                if textured and geometry.get("uv") is not None
                else None
            )

            batchids = np.full(positions.shape[0], i, dtype=np.float32) if batched else None

            meshes.append(
                gltf_utils.GltfMesh(
                    points=positions,
                    normals=normals,
                    uvs=uvs,
                    batchids=batchids,
                    batchids_component_type=(
                        gltf_utils.get_component_type_from_dtype(batchids.dtype)
                        if batchids is not None
                        else None
                    ),
                    primitives=[
                        gltf_utils.GltfPrimitive(
                            texture_uri=texture_uri if textured else None
                        )
                    ],
                    properties=geometry.get("properties"),
                )
            )

        # Assume upstream from_meshes is a classmethod using cls(...)
        result = cls.from_meshes(meshes, transform=transform)
        result.batch_length = len(arrays) if batched else 0
        return result


GlTF = Gltf