#!/usr/local/opt/python3
from viz_3dtiles import Cesium3DTile, Cesium3DTileset
from polygon_geohasher.polygon_geohasher import geohash_to_polygon, polygon_to_geohashes
from shapely import geometry
import geopandas
from geopandas.geodataframe import GeoDataFrame
import os

tileset = Cesium3DTileset()
tile = Cesium3DTile()
# Tileset (future) location
save_to=os.path.dirname(os.path.abspath(__file__))+"/run-cesium/tilesets/test/"

# A polygon of the entire world
polygon = geometry.Polygon([(-180, 90), (180, 90),
                            (180, -90), (-180, -90)])

# Convert the polygons at level 1 to 3d tiles
hashes=polygon_to_geohashes(polygon, 2)

data = {"id": [], "geometry": []}

for hash in hashes:
    data["id"].append(hash)
    data["geometry"].append(geohash_to_polygon(hash))

gdf=geopandas.GeoDataFrame(data, crs="EPSG:4326")

tile.from_geodataframe(gdf)  
tileset.add_tile(tile)

tileset.save_to=tile.save_to
tileset.write_file()