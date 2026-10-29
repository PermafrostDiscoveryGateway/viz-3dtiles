import numpy as np
import geopandas as gpd
from shapely.geometry import Point

from pdg3dtiles import Cesium3DTile


def test_create_batch_table_excludes_staging_properties():
    tile = Cesium3DTile()
    tile.batch_table_uuid = False
    tile.geodataframe = gpd.GeoDataFrame(
        {
            "name": ["feature"],
            "staging_area": [12.5],
            "staging_centroid_tile": ["8/1/2"],
            "geometry": [Point(0, 0)],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )

    batch_table = tile.create_batch_table()

    assert set(batch_table.header.data) == {"name"}


def _flat_square_gdf(half_size_m=60_000):
    # ~120 km square in EPSG:3413 near Greenland: earcut alone yields 2 huge triangles.
    from shapely.geometry import box

    return gpd.GeoDataFrame(
        {"name": ["big"]},
        geometry=[box(-half_size_m, -half_size_m, half_size_m, half_size_m)],
        crs="EPSG:3413",
    )


def _heights(tile):
    from pyproj import Transformer

    to_lla = Transformer.from_crs(4978, 4979, always_xy=True)
    points = np.vstack([g["position"] for g in tile.geometries])
    return to_lla.transform(points[:, 0], points[:, 1], points[:, 2])[2]


def _triangle_centroid_heights(tile):
    from pyproj import Transformer

    to_lla = Transformer.from_crs(4978, 4979, always_xy=True)
    out = []
    for g in tile.geometries:
        c = g["position"][g["indices"]].mean(axis=1)
        out.append(to_lla.transform(c[:, 0], c[:, 1], c[:, 2])[2])
    return np.concatenate(out)


def test_large_flat_polygon_stays_above_the_ellipsoid(tmp_path):
    tile = Cesium3DTile()
    tile.save_to = str(tmp_path)
    tile.from_geodataframe(_flat_square_gdf(), z=8.0)

    # Unclipped, the two huge triangles put their centroids ~hundreds of metres
    # below the ellipsoid, where a depth-tested globe hides them.
    assert _triangle_centroid_heights(tile).min() > 0.0
    assert len(tile.geometries) == 1  # still one feature, not one per part


def test_max_extent_none_disables_clipping(tmp_path):
    tile = Cesium3DTile()
    tile.save_to = str(tmp_path)
    tile.max_extent = None
    tile.from_geodataframe(_flat_square_gdf(), z=8.0)

    assert _triangle_centroid_heights(tile).min() < -100.0


def test_geographic_crs_input_is_clipped_too(tmp_path):
    from shapely.geometry import box

    gdf = gpd.GeoDataFrame(
        {"name": ["big"]}, geometry=[box(-30, 75, -24, 77)], crs="EPSG:4326"
    )
    tile = Cesium3DTile()
    tile.save_to = str(tmp_path)
    tile.from_geodataframe(gdf, z=8.0)

    assert _triangle_centroid_heights(tile).min() > 0.0


def test_geometry_with_its_own_z_is_not_clipped(tmp_path):
    from shapely.geometry import Polygon

    ring = [(-60_000, -60_000, 50), (60_000, -60_000, 50), (60_000, 60_000, 50), (-60_000, 60_000, 50)]
    gdf = gpd.GeoDataFrame({"name": ["3d"]}, geometry=[Polygon(ring)], crs="EPSG:3413")
    tile = Cesium3DTile()
    tile.save_to = str(tmp_path)
    tile.from_geodataframe(gdf)

    assert sum(len(g["indices"]) for g in tile.geometries) == 2
