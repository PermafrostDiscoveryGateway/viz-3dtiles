#!/usr/local/opt/python3
from viz_3dtiles import Cesium3DTile, Tileset
import os

# usage: from ./viz-3dtiles run `python test/test_multiple.py`

try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
except BaseException:
    base_dir = ''

output_directory = os.path.join(
    base_dir,
    'run-cesium',
    'tilesets',
    'test_multiple')
input_geopackage_dir = os.path.join(
    base_dir, 'example_data', 'tiled-geopackage')

# Get all of the geopackage file paths in the input directory
input_paths = []
for root, dirs, files in os.walk(input_geopackage_dir):
    for file in files:
        if file.endswith('.gpkg'):
            input_paths.append(os.path.join(root, file))

# Make a B3DM file for each of the geopackage files
tile_parts = []
for i in range(len(input_paths)):
    input_path = input_paths[i]
    # Get the base name of the input file
    tile = Cesium3DTile()
    tile.save_to = output_directory
    tile.save_as = 'model_' + str(i)
    tile.from_file(input_path)
    tile_parts.append(tile)

# Create a tileset to contain the 3D Tile just created
tileset = Tileset.from_Cesium3DTiles(
    tile_parts, os.path.join(
        output_directory, 'tileset.json'))
