import os
import geopandas as gpd
from viz_3dtiles import leaf_tile_from_gdf

# usage: from ./viz-3dtiles run `python test/test_tree.py`

# Output Tileset directory -- view `tileset.json`
try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
except:
    base_dir = ''
output_directory=os.path.join(base_dir, 'run-cesium', 'tilesets', 'test')
input_shapefile_path=os.path.join(base_dir, 'example_data', 'example.shp')

# Create one leaf tile from the Example shp file
gdf = gpd.read_file(input_shapefile_path)
gdf.set_crs('EPSG:3413', inplace=True)
leaf_tile_from_gdf(
    gdf,
    dir=output_directory,
    filename="leaf-example",
    geometricError=40, # optional
    tilesetVersion="test-01" # optional
)