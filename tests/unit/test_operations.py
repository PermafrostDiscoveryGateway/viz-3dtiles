import json

import pytest


def test_convert_leaf_returns_real_content_and_tileset(tmp_path):
    import geopandas as gpd
    from shapely.geometry import Polygon
    from pdg3dtiles.operations import convert_leaf

    source = tmp_path / "source.gpkg"
    gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (1, 0), (0, 1)])], crs="EPSG:4326"
    ).to_file(source)
    content, tileset = convert_leaf(
        source, tmp_path / "model.b3dm", tmp_path / "tileset.json"
    )
    assert content.is_file() and tileset.is_file()
    data = json.loads(tileset.read_text())
    assert data["root"]["content"]["uri"] == "model.b3dm"
    assert data["root"]["boundingVolume"]


def test_convert_leaf_needs_overwrite_for_existing_outputs(tmp_path):
    import geopandas as gpd
    from shapely.geometry import Polygon
    from pdg3dtiles.operations import convert_leaf

    source = tmp_path / "source.gpkg"
    gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (1, 0), (0, 1)])], crs="EPSG:4326"
    ).to_file(source)
    content, tileset = tmp_path / "model.b3dm", tmp_path / "tileset.json"
    convert_leaf(source, content, tileset)
    with pytest.raises(FileExistsError):
        convert_leaf(source, content, tileset)
    convert_leaf(source, content, tileset, overwrite=True)
    assert content.is_file() and tileset.is_file()


def test_leaf_failure_leaves_neither_output(tmp_path, monkeypatch):
    import geopandas as gpd
    from shapely.geometry import Polygon
    from pdg3dtiles import operations

    source = tmp_path / "source.gpkg"
    gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (1, 0), (0, 1)])], crs="EPSG:4326"
    ).to_file(source)
    content, tileset = tmp_path / "model.b3dm", tmp_path / "tileset.json"

    def _fail(*_args, **_kwargs):
        raise RuntimeError("no leaf")

    monkeypatch.setattr(operations, "leaf_tile_from_gdf", _fail)
    with pytest.raises(RuntimeError, match="no leaf"):
        operations.convert_leaf(source, content, tileset)
    assert not content.exists() and not tileset.exists()


def test_failed_overwrite_keeps_previous_outputs(tmp_path, monkeypatch):
    import geopandas as gpd
    from shapely.geometry import Polygon
    from pdg3dtiles import operations

    source = tmp_path / "source.gpkg"
    gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (1, 0), (0, 1)])], crs="EPSG:4326"
    ).to_file(source)
    content, tileset = tmp_path / "model.b3dm", tmp_path / "tileset.json"
    operations.convert_leaf(source, content, tileset)
    before = (content.read_bytes(), tileset.read_bytes())

    def _fail(*_args, **_kwargs):
        raise RuntimeError("no leaf")

    monkeypatch.setattr(operations, "leaf_tile_from_gdf", _fail)
    with pytest.raises(RuntimeError, match="no leaf"):
        operations.convert_leaf(source, content, tileset, overwrite=True)
    assert (content.read_bytes(), tileset.read_bytes()) == before


def test_compose_tileset_is_canonical_and_aliases_delegate(tmp_path):
    from pdg3dtiles.operations import compose_parent, compose_root, compose_tileset

    child = '{"asset":{"version":"1.0"},"geometricError":1,"root":{"boundingVolume":{"region":[0,0,1,1,0,1]},"geometricError":1,"refine":"ADD","content":{"uri":"model.b3dm"}}}'
    children = [tmp_path / name for name in ("a.json", "b.json")]
    for path in children:
        path.write_text(child)
    canonical = compose_tileset(children, tmp_path / "canonical.json")
    assert canonical.is_file()
    assert compose_parent(children, tmp_path / "parent.json").read_text() == canonical.read_text()
    assert compose_root(children, tmp_path / "root.json").read_text() == canonical.read_text()
    with pytest.raises(FileExistsError):
        compose_tileset(children, tmp_path / "canonical.json")
    assert compose_tileset(children, tmp_path / "canonical.json", overwrite=True).is_file()
    with pytest.raises(ValueError):
        compose_tileset([], tmp_path / "empty.json")


def test_parent_and_root_use_only_explicit_children(tmp_path):
    from pdg3dtiles.operations import compose_parent, compose_root

    child = '{"asset":{"version":"1.0"},"geometricError":1,"root":{"boundingVolume":{"region":[0,0,1,1,0,1]},"geometricError":1,"refine":"ADD","content":{"uri":"model.b3dm"}}}'
    children = [tmp_path / name for name in ("a.json", "b.json")]
    for path in children:
        path.write_text(child)
    parent = compose_parent(children, tmp_path / "parent.json")
    root = compose_root(children, tmp_path / "root.json")
    assert parent.is_file() and root.is_file()
    assert [
        child["content"]["uri"]
        for child in json.loads(parent.read_text())["root"]["children"]
    ] == [
        "a.json",
        "b.json",
    ]
    assert [
        child["content"]["uri"]
        for child in json.loads(root.read_text())["root"]["children"]
    ] == [
        "a.json",
        "b.json",
    ]


def test_compose_tileset_accepts_any_output_suffix(tmp_path):
    from pdg3dtiles.operations import compose_tileset

    child = tmp_path / "child.json"
    child.write_text(
        '{"asset":{"version":"1.0"},"geometricError":1,"root":{"boundingVolume":{"region":[0,0,1,1,0,1]},"geometricError":1,"refine":"ADD","content":{"uri":"model.b3dm"}}}'
    )
    output = compose_tileset([child], tmp_path / "root.tileset")
    assert output.is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["child.json", "root.tileset"]
