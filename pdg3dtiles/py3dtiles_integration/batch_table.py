from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Literal, Union
import numpy as np
import numpy.typing as npt
from py3dtiles.exceptions import (
    Invalid3dtilesError,
    InvalidBatchTableError,
)
from py3dtiles.typing import BatchTableHeaderDataType
from .constants import COMPONENT_TYPE_NUMPY_MAPPING, DTYPE_TO_COMPONENT_TYPE_MAPPING
if TYPE_CHECKING:
    from py3dtiles.tileset.content import TileContentHeader

TYPE_LENGTH_MAPPING = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
}

ComponentLiteralType = Literal[
    "BYTE",
    "UNSIGNED_BYTE",
    "SHORT",
    "UNSIGNED_SHORT",
    "INT",
    "UNSIGNED_INT",
    "FLOAT",
    "DOUBLE",
]

ComponentNumpyType = Union[
    np.int8, np.uint8, np.int16, np.uint16, np.int32, np.uint32, np.float32, np.float64
]

PropertyLiteralType = Literal["SCALAR", "VEC2", "VEC3", "VEC4"]


class BatchTableHeader:
    def __init__(self, data: BatchTableHeaderDataType | None = None) -> None:
        self.data = data if data is not None else {}

    @property
    def properties(self) -> BatchTableHeaderDataType:
        return self.data

    @properties.setter
    def properties(self, value: BatchTableHeaderDataType) -> None:
        self.data = value

    def add_property_from_array(self, property_name: str, array: Any) -> None:
        if isinstance(array, np.ndarray):
            self.data[property_name] = array.tolist()
        else:
            self.data[property_name] = array

    def to_array(self) -> npt.NDArray[np.uint8]:
        if not self.data:
            return np.empty((0,), dtype=np.uint8)

        json_str = json.dumps(self.data, separators=(",", ":"))
        if len(json_str) % 8 != 0:
            json_str += " " * (8 - len(json_str) % 8)
        return np.frombuffer(json_str.encode("utf-8"), dtype=np.uint8)


class BatchTableBody:
    def __init__(self, data: list[npt.NDArray[ComponentNumpyType]] | None = None):
        self.data = data if data is not None else []

    def to_array(self) -> npt.NDArray[np.uint8]:
        if not self.data:
            return np.empty((0,), dtype=np.uint8)

        chunks = [data.view(np.uint8) for data in self.data]
        total_nbytes = sum(data.nbytes for data in self.data)

        if total_nbytes % 8 != 0:
            padding_str = " " * (8 - total_nbytes % 8)
            chunks.append(np.frombuffer(padding_str.encode("utf-8"), dtype=np.uint8))

        return np.concatenate(chunks, dtype=np.uint8)

    @property
    def nbytes(self) -> int:
        return sum(data.nbytes for data in self.data)


class BatchTable:
    """
    Only the JSON header has been implemented for now. According to the batch
    table documentation, the binary body is useful for storing long arrays of
    data.
    """

    def __init__(self) -> None:
        self.header = BatchTableHeader()
        self.body = BatchTableBody()

    def add_property_as_json(self, property_name: str, array: Any) -> None:
        if isinstance(array, np.ndarray):
            self.header.data[property_name] = array.tolist()
        else:
            self.header.data[property_name] = array

    def get_length(self) -> int | None:
        if len(list(self.header.properties.keys())) == 0:
            return None
        if "id" in self.header.properties:
            return len(self.header.properties["id"])
        first_key = list(self.header.properties.keys())[0]
        return len(self.header.properties[first_key])

    def add_property_as_binary(
        self,
        property_name: str,
        array: npt.NDArray[ComponentNumpyType],
        property_type: PropertyLiteralType,
    ) -> None:
        component_type = DTYPE_TO_COMPONENT_TYPE_MAPPING.get(array.dtype)
        if component_type is None:
            raise ValueError(
                f"Cannot find a component_type corresponding to the dtype ${array.dtype}"
            )

        self.header.data[property_name] = {
            "byteOffset": self.body.nbytes,
            "componentType": component_type,
            "type": property_type,
        }

        transformed_array = array.reshape(-1)
        self.body.data.append(transformed_array)

    def get_property_names(self) -> Iterator[str]:
        return iter(self.header.data.keys())

    def get_binary_property(
        self, property_name_to_fetch: str
    ) -> npt.NDArray[ComponentNumpyType]:
        binary_property_index = 0
        for property_name, property_definition in self.header.data.items():
            if isinstance(property_definition, list):
                continue
            if property_name_to_fetch == property_name:
                return self.body.data[binary_property_index]
            binary_property_index += 1
        raise ValueError(f"The property {property_name_to_fetch} is not found")

    @staticmethod
    def merge(b1: "BatchTable", b2: "BatchTable") -> "BatchTable":
        new_bt = BatchTable()
        for property_name, property_definition in b1.header.data.items():
            other_property_definition = b2.header.data.get(property_name)
            if isinstance(property_definition, list) and isinstance(other_property_definition, list):
                new_bt.add_property_as_json(
                    property_name, [*property_definition, *other_property_definition]
                )
            elif isinstance(property_definition, dict) and isinstance(other_property_definition, dict):
                component_type_1 = property_definition["componentType"]
                component_type_2 = other_property_definition["componentType"]
                type_1 = property_definition["type"]
                type_2 = other_property_definition["type"]

                if component_type_1 != component_type_2:
                    raise InvalidBatchTableError(
                        f"componentType differs for {property_name}. First dtype is {component_type_1}, second is {component_type_2}"
                    )
                if type_1 != type_2:
                    raise InvalidBatchTableError(
                        f"type differs between the 2 batch_table properties. First type is {type_1}, second is {type_2}"
                    )

                binary_property_1 = b1.get_binary_property(property_name)
                binary_property_2 = b2.get_binary_property(property_name)
                new_binary_property = np.concatenate((binary_property_1, binary_property_2))
                new_bt.add_property_as_binary(property_name, new_binary_property, type_1)
            else:
                raise InvalidBatchTableError(
                    f"Cannot merge batch tables if their property differ. Type of {property_name} is {type(property_definition)} in self, but is {type(other_property_definition)} in other"
                )

        for property_name in b2.header.data:
            if property_name not in new_bt.header.data:
                raise InvalidBatchTableError(
                    f"Missing {property_name} in first batch table"
                )
        return new_bt

    def to_array(self) -> npt.NDArray[np.uint8]:
        batch_table_header_array = self.header.to_array()
        batch_table_body_array = self.body.to_array()
        return np.concatenate((batch_table_header_array, batch_table_body_array))

    @staticmethod
    def from_array(
        tile_header: "TileContentHeader",
        array: npt.NDArray[np.uint8],
        batch_len: int = 0,
    ) -> "BatchTable":
        batch_table = BatchTable()
        batch_table_header_length = tile_header.bt_json_byte_length
        batch_table_body_array = array[batch_table_header_length:]
        batch_table_header_array = array[0:batch_table_header_length]

        jsond = json.loads(batch_table_header_array.tobytes().decode("utf-8") or "{}")
        batch_table.header.data = jsond

        previous_byte_offset = 0
        for bt_property in batch_table.header.data:
            if bt_property == "extensions" or bt_property == "extras":
                continue

            property_definition = batch_table.header.data[bt_property]

            if isinstance(property_definition, list):
                continue

            if previous_byte_offset != property_definition["byteOffset"]:
                raise Invalid3dtilesError(
                    f"The byte offset is {property_definition['byteOffset']} but the byte offset computed is {previous_byte_offset}"
                )

            numpy_type = COMPONENT_TYPE_NUMPY_MAPPING[property_definition["componentType"]]
            end_byte_offset = property_definition["byteOffset"] + (
                np.dtype(numpy_type).itemsize
                * TYPE_LENGTH_MAPPING[property_definition["type"]]
                * batch_len
            )
            batch_table.body.data.append(
                batch_table_body_array[
                    property_definition["byteOffset"]: end_byte_offset
                ].view(numpy_type)
            )
            previous_byte_offset = end_byte_offset

        return batch_table