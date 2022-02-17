from shapely.geometry import Polygon, MultiPolygon
import geopandas as gpd
from geopandas.geodataframe import GeoDataFrame
import numpy as np
from py3dtiles import GlTF, TriangleSoup, B3dm
from pprint import pprint
import os

# Canada ice-wedge polygon file with 89 polygons, matches FME conversion
file="/data/example.shp"
#file="/data/datasets/canada/WV02_20120801221347_103001001BC96000_12AUG01221347-M1BS-500060498180_01_P001_u16rf3413_pansh/WV02_20120801221347_103001001BC96000_12AUG01221347-M1BS-500060498180_01_P001_u16rf3413_pansh.shp"
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

# Convert polygon points from xy to xyz
tolerance = 0.000001 # The simplification tolerance level
point_x_values_4978 = [] # Used to calculate max/min for bounding box
point_y_values_4978 = [] # Used to calculate max/min for bounding box
point_z_values_4978 = [] # Used to calculate max/min for bounding box

row = 0
for feature in gdf.iterfeatures():
    polygon = Polygon(feature["geometry"]["coordinates"][0])
    
    # Replace the row's geometry in the GeoDataFrame
    print(f"Processing {row + 1} of {len(gdf)}")
    ext_ring_z = []

    print(f"Caching xyz points")
    for point in polygon.exterior.coords:
        # create an exterior ring with xyz values, not just xy
        # Use a .1 meter elevation for now. May need to dynamically retrieve this from the data if elevation is there
        x,y,z = point[0], point[1], 0.1
        ext_ring_z.append((x, y, z))
    # Build the new PolygonZ
    polygon_z = Polygon(ext_ring_z)
    gdf["geometry"][row] = polygon_z
    row += 1

# Transform the incoming shapes from a geographic 4326 CRS to
# the Cesium-internal earth-centered, earth-fixed (ECEF) 4978 CRS
# See https://medium.com/terria/georeferencing-3d-models-for-cesium-7ccf609ee2ef
gdf_4978 = gdf.to_crs(epsg=4978)

polygons_z_4978 = [] # List of polygons for glTF Multipolygon
row = 0
for feature in gdf_4978.iterfeatures():
    print(f"Processing {row + 1} of {len(gdf_4978)} in EPSG", final_epsg)

    #Create a PolygonZ
    polygon_4978 = Polygon(feature["geometry"]["coordinates"][0])
        
    # Cache the x,y,z values for max/min calc later
    # TODO: Look into faster ways to do this
    print(f"Caching xyz points")
    for point in polygon_4978.exterior.coords:
        # Cache the x,y,z values
        x, y, z = point[0], point[1], point[2]

        point_x_values_4978.append(x)
        point_y_values_4978.append(y)
        point_z_values_4978.append(z)
    # Save the Polygon to a list
    polygons_z_4978.append(polygon_4978)
    row += 1

# Use the simplified polygon to create a WKB
miltipolygon_z_4978 = MultiPolygon(polygons_z_4978)


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


transform = np.array(
    [[
        1.0, 0.0,  0.0, 0.0,
        0.0, 0.0, -1.0, 0.0,
        0.0, 1.0,  0.0, 0.0,
        0.0, 0.0,  0.0, 1.0
    ]], dtype=float)

transform = transform.flatten('F')

# generate the glTF part from the binary arrays.
geometry = { 'position': positions, 'normal': normals, 'bbox': box_degrees_4978}
print("creating glTF")
gltf = GlTF.from_binary_arrays([geometry], transform=transform, batched=False)

#with open(save_as+".glb", "bw") as f:
#   f.write(bytes(gltf.to_array()))

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

