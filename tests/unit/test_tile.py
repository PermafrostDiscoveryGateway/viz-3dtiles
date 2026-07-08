import numpy as np
import pytest
from pdg3dtiles import Tile, Content, BoundingVolumeRegion


def region(w, s, e, n, z0=0, z1=0):
    return {"region": [*np.deg2rad([w, s, e, n]).tolist(), z0, z1]}


def test_tile_init_defaults_and_validate():
    t = Tile()
    t.validate()


def test_tile_refine_and_transform_checks():
    with pytest.raises(ValueError):
        Tile(refine="BAD")
    with pytest.raises(ValueError):
        Tile(transform=[0.0] * 15)  # wrong length


def test_tile_add_children_and_bv_update_replace():
    parent = Tile(boundingVolume=region(-2, -2, 2, 2, 0, 10), geometricError=10)
    c1 = Tile(
        boundingVolume=region(-1, -1, 0, 0, 0, 5),
        geometricError=5,
        content=Content(uri="a.b3dm"),
    )
    c2 = Tile(
        boundingVolume=region(0, 0, 1, 1, 0, 8),
        geometricError=4,
        content=Content(uri="b.b3dm"),
    )

    parent.add_children([c1, c2], bv_method="replace", bv_source="root")
    assert parent.children and len(parent.children) == 2
    deg = np.rad2deg(parent.boundingVolume.to_array()[:4])
    assert deg[0] <= -1 and deg[2] >= 1


def test_tile_add_content():
    t = Tile()
    t.add_content(Content(uri="c.b3dm"))
    assert t.content.uri == "c.b3dm"
