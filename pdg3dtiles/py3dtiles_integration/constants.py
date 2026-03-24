from typing import Any

import numpy as np

DTYPE_TO_COMPONENT_TYPE_MAPPING: dict[np.dtype[Any], str] = {
    np.dtype("int8"): "BYTE",
    np.dtype("uint8"): "UNSIGNED_BYTE",
    np.dtype("int16"): "SHORT",
    np.dtype("uint16"): "UNSIGNED_SHORT",
    np.dtype("int32"): "INT",
    np.dtype("uint32"): "UNSIGNED_INT",
    np.dtype("float32"): "FLOAT",
    np.dtype("float64"): "DOUBLE",
}

COMPONENT_TYPE_NUMPY_MAPPING = {
    value: key.type for key, value in DTYPE_TO_COMPONENT_TYPE_MAPPING.items()
}