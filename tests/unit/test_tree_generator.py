import json
import math

from pdg3dtiles import parent_tile_from_children_json


def test_parent_default_geometric_error_uses_child_error_not_region_size(tmp_path):
    """Parent geometric error defaults to max child error, not region size."""
    broad_region = {
        "region": [-math.pi, -math.pi / 2, 0.0, math.pi / 2, -1.0, 1.0]
    }
    child_paths = []

    for index, geometric_error in enumerate((10.0, 20.0)):
        child_path = tmp_path / f"child-{index}.json"
        child_path.write_text(
            json.dumps(
                {
                    "asset": {"version": "1.0"},
                    "geometricError": geometric_error,
                    "root": {
                        "boundingVolume": broad_region,
                        "geometricError": geometric_error,
                        "refine": "ADD",
                    },
                }
            )
        )
        child_paths.append(str(child_path))

    parent = parent_tile_from_children_json(
        children=child_paths,
        dir=str(tmp_path),
        filename="parent",
        boundingVolume=broad_region,
    )

    assert parent.geometricError == 20.0
    assert parent.root.geometricError == 20.0


def _overflowing_gdf():
    """One polygon whose centroid is inside the nominal tile but which spills out."""
    import geopandas as gpd
    from shapely.geometry import box

    # Nominal tile footprint is lon/lat [-10, 70, -9, 71]; the polygon covers
    # [-10.5, 70.2, -8.0, 70.8], so its centroid (-9.25, 70.5) sits inside the tile.
    return gpd.GeoDataFrame({"id": [1]}, geometry=[box(-10.5, 70.2, -8.0, 70.8)], crs="EPSG:4326")


def _region_deg(bounding_volume):
    west, south, east, north = (math.degrees(v) for v in bounding_volume.to_list()[:4])
    return west, south, east, north


def test_leaf_region_contains_geometry_that_overflows_nominal_tile(tmp_path):
    """A leaf tile's region must enclose its content even if the caller passes a
    smaller nominal footprint; otherwise Cesium culls the overflowing geometry."""
    from pdg3dtiles import leaf_tile_from_gdf

    nominal = {"west": -10.0, "south": 70.0, "east": -9.0, "north": 71.0}

    _, tileset = leaf_tile_from_gdf(
        _overflowing_gdf(), dir=str(tmp_path), filename="leaf", z=8.0, boundingVolume=nominal
    )

    west, south, east, north = _region_deg(tileset.root.boundingVolume)
    assert west <= -10.5 + 1e-6 and east >= -8.0 - 1e-6
    assert south <= 70.0 + 1e-6 and north >= 71.0 - 1e-6  # still covers the nominal tile


def test_parent_region_contains_children_that_overflow_nominal_footprint(tmp_path):
    """A parent's region must enclose its children even when the caller passes a
    smaller nominal footprint."""
    child_region = [
        math.radians(v) for v in (-10.5, 70.2, -8.0, 70.8)
    ] + [7.0, 9.0]
    child_path = tmp_path / "child.json"
    child_path.write_text(
        json.dumps(
            {
                "asset": {"version": "1.0"},
                "geometricError": 5.0,
                "root": {
                    "boundingVolume": {"region": child_region},
                    "geometricError": 5.0,
                    "refine": "ADD",
                },
            }
        )
    )

    parent = parent_tile_from_children_json(
        children=[str(child_path)],
        dir=str(tmp_path),
        filename="parent",
        boundingVolume={"west": -10.0, "south": 70.0, "east": -9.0, "north": 71.0},
        boundingVolumeSource="root",
    )

    west, south, east, north = _region_deg(parent.root.boundingVolume)
    assert west <= -10.5 + 1e-6 and east >= -8.0 - 1e-6
    assert south <= 70.0 + 1e-6 and north >= 71.0 - 1e-6
