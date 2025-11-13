import os
import geopandas as gpd
from pdg3dtiles import leaf_tile_from_gdf, parent_tile_from_children_json

# usage: from ./viz-3dtiles run `python test/test_tree.py`

try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
except:
    base_dir = ""
output_directory = os.path.join(base_dir, "run-cesium", "tilesets", "test_tree")
input_geopackage_dir = os.path.join(base_dir, "example_data", "tiled-geopackage")

# Get all of the geopackage file paths in the input directory
input_paths = []
for root, dirs, files in os.walk(input_geopackage_dir):
    for file in files:
        if file.endswith(".gpkg"):
            input_paths.append(os.path.join(root, file))

# Make a B3DM and tileset JSON file for each of the geopackage files
leaf_tiles = []
for input_path in input_paths:
    # Get the tile from the geopackage
    gdf = gpd.read_file(input_path)
    # Get output path and filename that mirrors the input path
    output_dir = os.path.dirname(
        input_path.replace(input_geopackage_dir, output_directory)
    )
    base_filename = os.path.basename(input_path).split(".")[0]
    # Get the tile from the geopackage
    tile, tileset = leaf_tile_from_gdf(gdf, dir=output_dir, filename=base_filename)
    leaf_tiles.append(tileset)

# Make a parent tileset JSON file that points to each of the leaf tiles
parent_tile_from_children_json(
    children=leaf_tiles,
    dir=os.path.join(output_directory, "WorldCRS84Quad", "12", "762"),
    filename="455",
)
