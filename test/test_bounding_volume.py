import numpy as np
import pytest

from pdg3dtiles import BoundingVolume, BoundingVolumeBox, BoundingVolumeRegion

def test_bv_dispatch_box_and_region():
    box_vals = [0,0,0, 1,0,0, 0,1,0, 0,0,1]
    region_vals = [-1.0, -0.5, 1.0, 0.5, 0, 100]
    assert isinstance(BoundingVolume(box_vals), BoundingVolumeBox)
    assert isinstance(BoundingVolume(region_vals), BoundingVolumeRegion)

def test_bv_from_degree_dict_to_region():
    region = BoundingVolume({"west": -123, "south": 37, "east": -122, "north": 38, "min_height": 0, "max_height": 1000})
    assert isinstance(region, BoundingVolumeRegion)
    assert np.isclose(region.get_coords(), [-123, 37, -122, 38]).all()
    assert region.get_heights() == [0, 1000]

def test_bv_from_json_roundtrip():
    # JSON serialization/deserialization should work
    data = {"region": [-1.0, -0.5, 1.0, 0.5, 0, 100]}
    bv = BoundingVolume.from_json(data)
    j = bv.to_json()
    assert isinstance(j, str)
    d = bv.to_dict()
    assert "region" in d or "box" in d

def test_invalid_bv_values():
    with pytest.raises(ValueError):
        BoundingVolume("not a list")
    with pytest.raises(ValueError):
        BoundingVolume.from_json({})
