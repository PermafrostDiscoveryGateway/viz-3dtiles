from shapely.geometry import Polygon, MultiPolygon
import geopandas as gpd
from geopandas.geodataframe import GeoDataFrame
import numpy as np
from py3dtiles import GlTF, TriangleSoup, B3dm
from pprint import pprint
import os

# Canada ice-wedge polygon file with 89 polygons, matches FME conversion
file="/data/example.shp"
directory=os.getcwd()
filepath=directory+file
print("Converting ", filepath)

# Save as - the file name of the result .b3dm file
save_as="run-cesium/tilesets/model"

# Import the shp file
gdf : GeoDataFrame = gpd.read_file(filepath)
gdf = gdf.set_crs("EPSG:3413")
# Use geopandas to easily transform the coordinate system
gdf = gdf.to_crs("EPSG:4326")
final_epsg = 4978
gdf_4978 = gdf.to_crs(epsg=4978)

# gdf_4326 = gdf_4326[0:2] # Limit for debugging

# shapes_4326 = gdf_4326.iterfeatures()
# first_4326 = next(shapes_4326)
# polygon_4326 = Polygon(first_4326["geometry"]["coordinates"][0])

# Create a super simple polygon and gdf for testing
# coords = ((-151.0, 70.0), (-150.0, 70.0), (-150.0, 71.0), (-151.0, 71.0), (-151.0, 70.0))
# polygon_4326 = Polygon(coords)
# gdf_4326 = GeoDataFrame({"Class": [1], "geometry": [polygon_4326]}, crs="EPSG:4326")

# Convert polygon points from xy to xyz
tolerance = 0.000001 # The simplification tolerance level
point_x_values_4978 = [] # Used to calculate max/min for bounding box
point_y_values_4978 = [] # Used to calculate max/min for bounding box
point_z_values_4978 = [] # Used to calculate max/min for bounding box

polygons_z_4978 = [] # List of polygons for glTF Multipolygon

row = 0
for feature in gdf_4978.iterfeatures():
    polygon_4978 = Polygon(feature["geometry"]["coordinates"][0])
    
    # Simplify the polygon to reduce vertices based on the tolerance level
    polygon_simplified_4978 = polygon_4978.simplify(tolerance=tolerance)
    
    # Replace the row's geometry in the GeoDataFrame
    gdf_4978["geometry"][row] = polygon_simplified_4978
    print(f"Processing {row + 1} of {len(gdf_4978)}")
    ext_ring_z_4978 = []

    print(f"Caching xyz points")
    for point in polygon_4978.exterior.coords:
        # create an exterior ring with xyz values, not just xy
        x, y, z = point[0], point[1], 6169085.401505229
        ext_ring_z_4978.append((x, y, z))
        # Cache the x,y,z values for max/min calc later
        point_x_values_4978.append(x)
        point_y_values_4978.append(y)
        point_z_values_4978.append(z)
    # Build the new PolygonZ
    polygon_z_4978 = Polygon(ext_ring_z_4978)
    polygons_z_4978.append(polygon_z_4978)
    row += 1

# Use the simplified polygon to create a WKB
miltipolygon_z_4978 = MultiPolygon(polygons_z_4978)


# Transform the incoming shapes from a geographic 4326 CRS to
# the Cesium-internal earth-centered, earth-fixed (ECEF) 4978 CRS
# See https://medium.com/terria/georeferencing-3d-models-for-cesium-7ccf609ee2ef
# 

# row = 0
# gdf_4978 : GeoDataFrame = gdf_4326.to_crs(crs="EPSG:4978")
# polygons_z_4978 = []
# for feature_4978 in gdf_4978.iterfeatures():
#     # Create a Polygon Shapely object and add it to the list
#     polygon_4978 = Polygon(feature_4978["geometry"]["coordinates"][0])
#     ext_ring_z_4978 = []

#     for point in polygon_4978.exterior.coords:
#         # create an exterior ring with xyz values, not just xy
#         ext_ring_z_4978.append((point[0], point[1], 0.0))
#     polygon_z_4978 = Polygon(ext_ring_z_4978)
#     # Build max/min lists to calculate the bounding box
#     for x, y, z in polygon_z_4978.exterior.coords:
#         point_x_values.append(x)
#         point_y_values.append(y)
#         point_z_values.append(z)
#     # Replace the row's geometry in the GeoDataFrame
#     gdf_4978["geometry"][row] = polygon_z_4978
#     print(f"{row:0d} of {len(gdf_4978)}")
#     row += 1
#     polygons_z_4978.append(polygon_z_4978)

# --- Convert to gltf -----
# use the TriangleSoup helper class to transform the wkb into arrays
# of points and normals
print(f"Tesselating polygons to generate position and normal arrays")
ts = TriangleSoup.from_wkb_multipolygon(miltipolygon_z_4978.wkb)
positions = ts.getPositionArray()
normals = ts.getNormalArray()

print(f"Creating bounding box for gltf - EPSG ", final_epsg)
import math
box_mins_4978 = [min(point_x_values_4978), min(point_y_values_4978), min(point_z_values_4978)]
box_maxs_4978 = [max(point_x_values_4978), max(point_y_values_4978), max(point_z_values_4978)]
box_degrees_4978 = [box_maxs_4978, box_mins_4978]

# define the geometry's world transformation - World coordinates transformation flattend matrix
# transform = np.array([
#              [1, 0, 0, 1842015.125],
#              [0, 1, 0, 5177109.25],
#              [0, 0, 1, 247.87364196777344],
#              [0, 0, 0, 1]], dtype=float)
transform = np.array(
    [[
        1.0, 0.0,  0.0, 0.0,
        0.0, 0.0, -1.0, 0.0,
        0.0, 1.0,  0.0, 0.0,
        0.0, 0.0,  0.0, 1.0
    ]], dtype=float)

#transform = np.array(
#    [
#        1, 0, 0, 1842015.125,
#              0, 1, 0, 5177109.25,
#              0, 0, 1, 247.87364196777344,
#              0, 0, 0, 1
#    ], dtype=float)

transform = transform.flatten('F')

# generate the glTF part from the binary arrays.
# notice that from_binary_arrays accepts array of geometries
# for batching purposes.
geometry = { 'position': positions, 'normal': normals, 'bbox': box_degrees_4978}

# gltf = GlTF.from_binary_arrays([geometry], transform)
print("creating glTF")
gltf = GlTF.from_binary_arrays([geometry], transform=transform, batched=False)

with open(save_as+".glb", "bw") as f:
   f.write(bytes(gltf.to_array()))

# View gltf in vscode plugin
print("glb complete")

# --- TODO: Create tileset JSON file ---
print(f"boundingVolume box for Cesium tile - EPSG ", final_epsg)
bounding_volume_box = [(min(point_x_values_4978) + max(point_x_values_4978))/2, (min(point_y_values_4978) + max(point_y_values_4978))/2, (min(point_z_values_4978) + max(point_z_values_4978))/2,
                        max(point_x_values_4978) - min(point_x_values_4978), 0, 0,
                        0, max(point_y_values_4978) - min(point_y_values_4978), 0,
                        0, 0, 0]

pprint(bounding_volume_box)

# --- Convert to b3dm -----
# create a b3dm tile_content directly from the glTF.
print("Creating b3dm file")
t = B3dm.from_glTF(gltf)

# to save our tile as a .b3dm file
t.save_as(save_as+".b3dm")

print("Done.")
