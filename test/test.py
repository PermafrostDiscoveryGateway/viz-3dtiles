#!/usr/local/opt/python3
from viz_3dtiles import Cesium3DTile, Tileset
import os

# usage: from ./viz-3dtiles run `python test/test.py`

# Output Tileset directory -- view `tileset.json`
base_dir = os.path.dirname(os.path.abspath(__file__))
save_to = os.path.join(base_dir, "run-cesium", "tilesets", "test")

# Create a 3D Tile from the Example shp file
tile = Cesium3DTile()
tile.filter_by_attributes = {"centroid_within_tile": True}
tile.save_to = save_to  # model.b3dm save path
tile.from_file(
    os.path.join(base_dir, "example_data", "example.shp"), crs="EPSG:3413", z=05.2
)

# Create a tileset to contain the 3D Tile just created
tileset = Tileset.from_Cesium3DTiles(tile, os.path.join(save_to, "tileset.json"))
