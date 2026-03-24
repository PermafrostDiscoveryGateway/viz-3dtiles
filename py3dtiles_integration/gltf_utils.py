from __future__ import annotations

from typing import Any, NamedTuple, cast

import numpy as np
import numpy.typing as npt
import pygltflib

from py3dtiles.points import Points


def get_component_type_from_dtype(dt: np.dtype[Any]) -> int:
    val = None
    if dt == np.int8:
        val = pygltflib.BYTE
    elif dt == np.uint8:
        val = pygltflib.UNSIGNED_BYTE
    elif dt == np.int16:
        val = pygltflib.SHORT
    elif dt == np.uint16:
        val = pygltflib.UNSIGNED_SHORT
    elif dt == np.uint32:
        val = pygltflib.UNSIGNED_INT
    elif dt == np.float32:
        val = pygltflib.FLOAT
    else:
        raise ValueError(f"Cannot find a component type suitable for {dt}")
    return cast(int, val)


def get_dtype_from_component_type(component_type: int) -> np.dtype[Any]:
    if component_type == pygltflib.BYTE:
        return np.dtype(np.int8)
    elif component_type == pygltflib.UNSIGNED_BYTE:
        return np.dtype(np.uint8)
    elif component_type == pygltflib.SHORT:
        return np.dtype(np.int16)
    elif component_type == pygltflib.UNSIGNED_SHORT:
        return np.dtype(np.uint16)
    elif component_type == pygltflib.UNSIGNED_INT:
        return np.dtype(np.uint32)
    elif component_type == pygltflib.FLOAT:
        return np.dtype(np.float32)
    else:
        raise ValueError(f"Invalid value given for component_type: {component_type}")


def get_num_components_from_type(accessor_type: str) -> int:
    if accessor_type == pygltflib.SCALAR:
        return 1
    elif accessor_type == pygltflib.VEC2:
        return 2
    elif accessor_type == pygltflib.VEC3:
        return 3
    # the noqa because I just find it easier to read that way
    elif accessor_type == pygltflib.VEC4:  # noqa: SIM114
        return 4
    elif accessor_type == pygltflib.MAT2:
        return 4
    elif accessor_type == pygltflib.MAT3:
        return 9
    elif accessor_type == pygltflib.MAT4:
        return 16
    else:
        raise ValueError(f"Unknown accessor type: {accessor_type}")


class GltfAttribute(NamedTuple):
    """
    A high level representation of a gltf attribute

    `accessor_type` can only take `values autorized by the spec <https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#_accessor_type>`_.

    `component_type` should take `these values <https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#_accessor_componenttype>`_.
    """

    name: str
    accessor_type: str  # Literal["SCALAR", "VEC2", "VEC3"] # pygltflib.SCALAR | pygltflib.VEC2 | pygltflib.VEC3
    component_type: (
        int  # pygltflib.UNSIGNED_BYTE | pygltflib.UNSIGNED_INT | pygltflib.FLOAT
    )
    array: npt.NDArray[np.uint8 | np.uint16 | np.uint32 | np.float32]


class GltfPrimitive:
    """
    A data structure storing all information to create a glTF mesh's primitive.

    This is intended for higher-level usage than pygltflib.Primitive.

    The transformation will be done automatically while transforming a `GltfMesh`.

    :param triangles: array of triangle indices, must have a (n, 3) shape.
    :param material: a glTF material. If not set, a default material is created.
    :param texture_uri: the URI of the texture image if the primitive is textured.
    :param mode: the draw mode, one of the constants exposed by pygltflib:
        POINT, LINES, LINE_LOOP, LINE_STRIP, TRIANGLES, TRIANGLE_STRIP or
        TRIANGLE_FAN.
    """

    def __init__(
        self,
        triangles: npt.NDArray[np.uint8 | np.uint16 | np.uint32] | None = None,
        material: pygltflib.Material | None = None,
        texture_uri: str | None = None,
        mode: int = pygltflib.TRIANGLES,
    ) -> None:
        self.triangles: GltfAttribute | None = (
            GltfAttribute(
                "INDICE",
                pygltflib.SCALAR,
                get_component_type_from_dtype(triangles.dtype),
                triangles,
            )
            if triangles is not None
            else None
        )
        self.material: pygltflib.Material | None = material
        self.texture_uri: str | None = texture_uri
        self.mode = mode


class GltfMesh:
    """
    A data structure representing a mesh.

    This is intended for higher-level usage than pygltflib.Mesh, which are an exact translation of the specification.

    This is intented to be easier to construct by keeping a more hierarchical and logical organization. `GltfMesh` are constructed with all the vertices, normals, uvs and additional attributes, and an optional list of `GltfPrimitive` that contains indices and material information.

    Use `gltf_from_meshes` or `populate_gltf_from_mesh` to convert it to GLTF format.

    :param points: array of vertex positions, must have a (n, 3) shape.
    :param primitives: array of GltfPrimitive
    :param normals: array of vertex normals for the whole mesh, must have a (n, 3) shape.
    :param batchids: array of batch table IDs, must have a (n) shape.
    :param additional_attributes: additional attributes to add to the primitive.
    :param uvs: array of texture coordinates, must have a (n, 2) shape.
    """

    def __init__(
        self,
        points: npt.NDArray[np.float32 | np.uint16],
        name: str | None = None,
        normals: npt.NDArray[np.float32] | None = None,
        primitives: list[GltfPrimitive] | None = None,
        batchids: npt.NDArray[np.uint32 | np.float32] | None = None,
        batchids_component_type: int | None = None,
        uvs: npt.NDArray[np.float32] | None = None,
        additional_attributes: list[GltfAttribute] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """
        A data structure storing all information to create a glTF mesh's primitive.

        """
        if points is None or len(points.shape) < 2 or points.shape[1] != 3:
            raise ValueError(
                "points arguments should be an array of coordinate triplets (of shape (N, 3))"
            )
        self.points: GltfAttribute = GltfAttribute(
            "POSITION", pygltflib.VEC3, pygltflib.FLOAT, points
        )
        self.name = name
        self.primitives = primitives or []
        if not self.primitives:
            self.primitives.append(GltfPrimitive())
        self.normals: GltfAttribute | None = (
            GltfAttribute("NORMAL", pygltflib.VEC3, pygltflib.FLOAT, normals)
            if normals is not None
            else None
        )
        self.batchids: GltfAttribute | None = (
            GltfAttribute(
                "_BATCHID",
                pygltflib.SCALAR,
                batchids_component_type
                if batchids_component_type is not None
                else get_component_type_from_dtype(batchids.dtype),
                batchids,
            )
            if batchids is not None
            else None
        )
        self.uvs: GltfAttribute | None = (
            GltfAttribute("TEXCOORD_0", pygltflib.VEC2, pygltflib.FLOAT, uvs)
            if uvs is not None
            else None
        )
        self.additional_attributes: list[GltfAttribute] = (
            additional_attributes if additional_attributes is not None else []
        )
        self.properties = properties


def gltf_from_points(points: Points, name: str | None = None) -> pygltflib.GLTF2:
    attributes = []
    if points.colors is not None:
        attributes.append(
            GltfAttribute(
                "COLOR_0",
                pygltflib.VEC3,
                get_component_type_from_dtype(points.colors.dtype),
                points.colors,
            )
        )
    for field, array in points.extra_fields.items():
        component_type = get_component_type_from_dtype(array.dtype)
        if component_type == pygltflib.UNSIGNED_INT:
            # The spec says "Application-specific attribute semantics MUST NOT use unsigned int component type."
            # so upgrading to float in this case
            component_type = pygltflib.FLOAT
            array = array.astype(np.float32)

        attributes.append(
            GltfAttribute(
                f"_{field.upper()}",
                pygltflib.SCALAR,
                component_type,
                array,
            )
        )

    primitive = GltfPrimitive(mode=pygltflib.POINTS)
    mesh = GltfMesh(
        name=name,
        points=points.positions,
        primitives=[primitive],
        additional_attributes=attributes,
    )
    return gltf_from_meshes(meshes=[mesh])


def gltf_from_meshes(
    meshes: list[GltfMesh], transform: npt.NDArray[np.float32] | None = None
) -> pygltflib.GLTF2:
    """
    Builds a GLTF2 instance from a list of meshes.
    """

    gltf = pygltflib.GLTF2(
        scene=0,
        scenes=[pygltflib.Scene(nodes=[])],
        nodes=[],
        meshes=[],
    )

    # insert the default material
    # if we don't add it there, we would have to test if one primitive doesn't have one and add
    # only in this case, but we'd need to remember the material_id of the default material.
    # For a few bytes, it's not worthy to do all this.
    # it also makes debugging easier. material_id = 0 is the default material, and that's it.
    # Note that the specification is ambiguous here, it's not clear if a gltf should always have a
    # default material OR if it's the viewer's job.
    gltf.materials.append(pygltflib.Material())

    for i, mesh in enumerate(meshes):
        node = pygltflib.Node(
            mesh=i,
            matrix=(transform.flatten("F").tolist() if transform is not None else None),
        )
        gltf.scenes[0].nodes.append(i)
        gltf.nodes.append(node)

        populate_gltf_from_mesh(
            gltf,
            mesh,
        )

    gltf.buffers = [pygltflib.Buffer(byteLength=len(gltf.binary_blob()))]
    if len(gltf.textures) > 0:
        gltf.samplers.append(
            pygltflib.Sampler(
                magFilter=pygltflib.LINEAR,
                minFilter=pygltflib.LINEAR_MIPMAP_LINEAR,
                wrapS=pygltflib.REPEAT,
                wrapT=pygltflib.REPEAT,
            )
        )

    return gltf


def _set_texture_to_primitive(
    gltf: pygltflib.GLTF2, material: pygltflib.Material, texture_uri: str
) -> None:
    gltf.images.append(pygltflib.Image(uri=texture_uri))
    gltf.textures.append(pygltflib.Texture(sampler=0, source=len(gltf.images) - 1))

    if material.pbrMetallicRoughness is None:
        material.pbrMetallicRoughness = pygltflib.PbrMetallicRoughness()
    if material.pbrMetallicRoughness.baseColorTexture is None:
        material.pbrMetallicRoughness.baseColorTexture = pygltflib.TextureInfo()

    material.pbrMetallicRoughness.baseColorTexture.index = len(gltf.textures) - 1


def _create_gltf_primitive(
    gltf: pygltflib.GLTF2, primitive: GltfPrimitive
) -> pygltflib.Primitive:
    material_id = None
    if primitive.material:

        gltf.materials.append(primitive.material)
        material_id = len(gltf.materials) - 1
    else:
        # default material
        # it will always be 0 by internal py3dtiles convention
        material_id = 0

    return pygltflib.Primitive(
        attributes=pygltflib.Attributes(),
        material=material_id,
        mode=primitive.mode,
    )


def populate_gltf_from_mesh(
    gltf: pygltflib.GLTF2,
    mesh: GltfMesh,
) -> None:
    """
    Add a GltfMesh to a pygltflib.GLTF2

    This method takes care of all the nitty-gritty work about setting buffer, bufferViews, accessors and primitives.
    """
    # see https://gitlab.com/dodgyville/pygltflib/#create-a-mesh
    gltf_binary_blob = cast(bytes, gltf.binary_blob()) or b""

    attributes_array: list[GltfAttribute | None] = [
        mesh.points,
        mesh.normals,
        mesh.uvs,
        mesh.batchids,
    ]
    attributes_array.extend(mesh.additional_attributes)

    attributes_indices_by_name: dict[str, int] = {}
    for attribute in attributes_array:
        if attribute is None:
            continue
        attributes_indices_by_name[attribute.name] = len(gltf.accessors)

        array_blob = prepare_gltf_component(
            gltf,
            attribute,
            len(gltf_binary_blob),
        )

        gltf_binary_blob += array_blob

    gltf_mesh = pygltflib.Mesh(name=mesh.name, extras=mesh.properties)
    for primitive in mesh.primitives:

        # deal with texture
        if primitive.texture_uri:
            # if we have a texture_uri, we need a material to bear it
            if primitive.material is None:
                primitive.material = pygltflib.Material()
            _set_texture_to_primitive(gltf, primitive.material, primitive.texture_uri)
            primitive.material.pbrMetallicRoughness.baseColorTexture.texCoord = (
                attributes_indices_by_name.get("TEXCOORD_0")
            )

        # deal with material
        gltf_primitive = _create_gltf_primitive(gltf, primitive)
        gltf_mesh.primitives.append(gltf_primitive)

        # all primitive shares the same attributes. What they take is determined by the triangles
        # we need to do that because the spec mandates that all attribute accessors of a primitives have the same count
        # this is efficient because we store the attributes data only once
        for name, index in attributes_indices_by_name.items():
            setattr(gltf_primitive.attributes, name, index)
        # triangles
        if primitive.triangles is not None:
            gltf_primitive.indices = len(gltf.accessors)
            indice_blob = prepare_gltf_component(
                gltf,
                primitive.triangles,
                len(gltf_binary_blob),
                pygltflib.ELEMENT_ARRAY_BUFFER,
            )

            gltf_binary_blob += indice_blob

    gltf.meshes.append(gltf_mesh)
    gltf.set_binary_blob(gltf_binary_blob)


def prepare_gltf_component(
    gltf: pygltflib.GLTF2,
    attribute: GltfAttribute,
    byte_offset: int,
    buffer_view_target: int = pygltflib.ARRAY_BUFFER,
) -> bytes:
    array = attribute.array
    array_blob = array.flatten().tobytes()
    # note: triangles are sometimes expressed as array of face vertex indices, but from the gltf point of view, it is a flat scalar array
    count = (
        array.size if attribute.accessor_type == pygltflib.SCALAR else array.shape[0]
    )
    buffer_view = pygltflib.BufferView(
        buffer=0,  # Everything is stored in the same buffer for sake of simplicity
        byteOffset=byte_offset,
        byteLength=len(array_blob),
        target=buffer_view_target,
    )
    gltf.bufferViews.append(buffer_view)
    accessor = pygltflib.Accessor(
        bufferView=len(gltf.bufferViews) - 1,
        componentType=attribute.component_type,
        count=count,
        type=attribute.accessor_type,
    )

    # min / max for positions, mandatory
    if attribute.name == "POSITION":
        accessor.min = np.min(attribute.array, axis=0).tolist()
        accessor.max = np.max(attribute.array, axis=0).tolist()

    gltf.accessors.append(accessor)
    return array_blob


def get_vertex_count(gltf: pygltflib.GLTF2) -> int:
    vertex_count = 0
    # it's not correct to simply count the accessor of type VEC3 (because they might not all be positions).
    # Also, because you can reuse accessors with different index, you cannot just sum accessors count
    # we need to sum the *unique* accessors
    # please note that this will *not* give you the number of necessary draw calls, because of indices as well.
    accessor_ids: list[int] = []
    for mesh in gltf.meshes:
        for primitive in mesh.primitives:
            accessor_ids.append(primitive.attributes.POSITION)
    for acc_id in set(accessor_ids):
        vertex_count += gltf.accessors[acc_id].count
    return vertex_count


def get_non_standard_attribute_names(gltf: pygltflib.GLTF2) -> set[str]:
    standard_attributes = {
        "POSITION",
        "NORMAL",
        "TANGENT",
        "TEXCOORD_0",
        "TEXCOORD_1",
        "COLOR_0",
        "JOINTS_0",
        "WEIGHTS_0",
    }
    all_attrs = []
    for mesh in gltf.meshes:
        for primitive in mesh.primitives:
            # note: vars(...) is a dict, iterable on the keys
            # so this gives a set containing all the keys
            attrs = set(vars(primitive.attributes)) - standard_attributes
            all_attrs.append(attrs)

    return set.intersection(*all_attrs)


def get_array_from_accessor(
    accessor: pygltflib.Accessor, buffer_view: pygltflib.BufferView, data: bytes
) -> npt.NDArray[Any]:
    num_element = get_num_components_from_type(accessor.type)
    bv_byte_offset = 0 if buffer_view.byteOffset is None else buffer_view.byteOffset
    acc_byte_offset = 0 if accessor.byteOffset is None else accessor.byteOffset

    arr = np.frombuffer(
        data,
        dtype=get_dtype_from_component_type(accessor.componentType),
        count=accessor.count * num_element,
        offset=bv_byte_offset + acc_byte_offset,
    )
    if num_element > 1:
        arr = arr.reshape((-1, num_element))
    return arr


def _get_attribute_from_primitive(
    attribute_name: str, gltf: pygltflib.GLTF2, primitive: pygltflib.Primitive
) -> npt.NDArray[Any] | None:
    blob = gltf.binary_blob()
    if not hasattr(primitive.attributes, attribute_name):
        return None
    accessor_id = getattr(primitive.attributes, attribute_name)
    if accessor_id is None:
        return None
    attr_accessor = gltf.accessors[accessor_id]
    # is there an index ?
    arr = get_array_from_accessor(
        attr_accessor, gltf.bufferViews[attr_accessor.bufferView], blob
    )
    if primitive.indices is not None:
        # get index
        indices_accessor = gltf.accessors[primitive.indices]
        if indices_accessor.bufferView is None:
            raise ValueError(
                "Accessor without bufferView! Please note that sparse accessors are not yet supported"
            )
        buffer_view = gltf.bufferViews[indices_accessor.bufferView]
        indices = get_array_from_accessor(indices_accessor, buffer_view, blob)
        arr = arr[indices]
    return arr


def get_attribute(
    gltf: pygltflib.GLTF2, attribute_name: str
) -> npt.NDArray[Any] | None:
    """
    Get all the values having this attribute_name in this gltf, respecting the indices if there are some.

    The returning array contains all the value in a structured manner: `get_attribute(gltf, 'POSITION')` will give back an array of 3-elements arrays.

    Note: this method guarantees to walk the meshes and primitives always in the same order, but there is no guarantee that each mesh has this particular attribute.

    Warning: this method only supports gltf with a buffer format of BINARYBLOB (see pygltflib BufferFormat enum)
    """
    if len(gltf.buffers) == 0:
        raise ValueError("This gltf has no buffers")
    if len(gltf.buffers) > 1:
        raise ValueError("This method doesn't support gltf with several buffers yet")
    if gltf.identify_uri(gltf.buffers[0].uri) != pygltflib.BufferFormat.BINARYBLOB:
        raise ValueError(
            "This method only supports gltf with one buffer in the BINARYBLOB format"
        )
    if gltf.binary_blob() is None:
        return None
    values: list[npt.NDArray[Any]] = []
    for mesh in gltf.meshes:
        for primitive in mesh.primitives:
            arr = _get_attribute_from_primitive(attribute_name, gltf, primitive)
            if arr is not None:
                values.append(arr)
    if len(values) == 0:
        return None
    else:
        return np.concatenate(values)  # type: ignore [no-any-return] # for some reason mypy doesn't infer the type correctly here