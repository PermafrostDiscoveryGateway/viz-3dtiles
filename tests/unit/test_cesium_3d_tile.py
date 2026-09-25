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
