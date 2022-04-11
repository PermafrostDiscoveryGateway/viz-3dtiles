#!/usr/local/opt/python3
from viz_3dtiles import Cesium3DTile, Cesium3DTileset
import os

# Tileset (future) location
save_to=os.path.dirname(os.path.abspath(__file__))+"/run-cesium/tilesets/test/"

# Create a 3D Tile from the Example shp file
tile = Cesium3DTile()
tile.filter_by_attributes={"centroid_within_tile": True}
tile.from_file(filepath=os.path.dirname(os.path.abspath(__file__))+"/data/example.shp")

# Create a tileset to contain the 3D Tile just created
tileset = Cesium3DTileset(tiles=[tile])
tileset.save_to=save_to+"run-cesium/tilesets/test/"
tileset.write_file()





