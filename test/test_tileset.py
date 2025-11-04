import os
import pytest
from pdg3dtiles import Tileset, Tile, Content, BoundingVolumeRegion, BoundingVolume

def test_tileset_minimal_init_and_to_dict():
    ts = Tileset()
    d = ts.to_dict()
    assert "asset" in d and "root" in d

def test_tileset_add_children_passthrough():
    ts = Tileset()
    child = Tile(content=Content(uri="c.b3dm"))
    ts.add_children([child])
    assert ts.root.children and len(ts.root.children) == 1