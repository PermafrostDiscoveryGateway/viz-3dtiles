#!/usr/local/opt/python3
from viz_3dtiles import Cesium3DTile, Cesium3DTileset
import os

# usage: from ./viz-3dtiles run `python test/test.py`

# Output Tileset directory -- view `tileset.json`
save_to=os.path.dirname(os.path.abspath(__file__))+"/run-cesium/tilesets/test/"

# Create a 3D Tile from the Example shp file
tile = Cesium3DTile()
tile.filter_by_attributes={"centroid_within_tile": True}
tile.save_to=save_to # model.b3dm save path
tile.from_file(filepath=os.path.dirname(os.path.abspath(__file__))+"/example_data/example.shp")

# Create a tileset to contain the 3D Tile just created
tileset = Cesium3DTileset(tiles=[tile])
tileset.save_to=save_to 
tileset.write_file()
