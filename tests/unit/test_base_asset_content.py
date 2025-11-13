import pytest
from pdg3dtiles import Base, Asset, Content, BoundingVolume


class Dummy(Base):
    required_keys = ["x"]
    type_definitions = {"x": int}

    def __init__(self, x=1):
        self.x = x


def test_base_validate_and_copy(tmp_path):
    d = Dummy(7)
    d.validate()
    p = tmp_path / "d.json"
    d.to_file(str(p), minify=True)
    d2 = Dummy.from_file(str(p))
    assert isinstance(d2, Dummy)
    c = d.copy()
    assert isinstance(c, Dummy)


def test_asset_types_and_required():
    a = Asset(version="1.0", tilesetVersion="v", extensions={"x": 1}, extras={"y": 2})
    a.validate()
    with pytest.raises(ValueError):
        # wrong type
        bad = Asset(version=1)  # type: ignore
        bad.validate()


def test_content_init_with_bv_list_and_dict():
    # Content should builds BoundingVolume from both list and dict inputs
    lst = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
    c1 = Content(boundingVolume=lst, uri="tile.b3dm")
    assert isinstance(c1.boundingVolume, BoundingVolume)
    dct = {"region": [-1, -1, 1, 1, 0, 0]}
    c2 = Content(boundingVolume=dct, uri="tile2.b3dm")
    assert isinstance(c2.boundingVolume, BoundingVolume)


def test_content_requires_uri():
    # raises error if missing required 'uri'
    with pytest.raises(ValueError):
        Content()
