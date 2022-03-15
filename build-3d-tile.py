from shapely.geometry import Polygon, MultiPolygon
import geopandas as gpd
from geopandas.geodataframe import GeoDataFrame
import numpy as np
from py3dtiles import GlTF, TriangleSoup, B3dm
from pprint import pprint
import os
import json
import math

# The file to convert to b3dm and the path to save the b3dm to
file="/data/example.shp"
save_to="run-cesium/tilesets/build-3d-tile-output"

directory=os.getcwd()
filepath=directory+file
print("Converting ", filepath)

# Save as - the file name of the result .b3dm file
save_as_filename="model"

# Limit the number of features converted. Useful for testing huge files.
max_features=15

tileset = {
    "asset" : {
		"version" : "0.0"
	},
    "properties" : {
		"Class" : {}
	},
	"geometricError" : 30,
	"root" : {
        "geometricError" : 30,
        "refine" : "ADD",
        "content" : {}
    }
}

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

#gdf['geometry'] = gdf['geometry'].simplify(tolerance)

row = 0
for feature in gdf.iterfeatures():
    if row > max_features-1:
        break
    polygon = Polygon(feature["geometry"]["coordinates"][0])
    
    # Replace the row's geometry in the GeoDataFrame
    print(f"Processing {row + 1} of {len(gdf)}")
    ext_ring_z = []

    for point in polygon.convex_hull.exterior.coords:
        # create an exterior ring with xyz values, not just xy
        # Use a .1 meter elevation for now. May need to dynamically retrieve this from the data if elevation is there
        x,y,z = point[0], point[1], 50
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
geometries=[]
row = 0
for feature in gdf_4978.iterfeatures():
    if row > max_features-1:
        break
    print(f"Processing {row + 1} of {len(gdf_4978)} in EPSG", final_epsg)
    
    #Create a PolygonZ
    polygon_4978 = Polygon(feature["geometry"]["coordinates"][0])

    point_x_this_polygon=[]
    point_y_this_polygon=[]
    point_z_this_polygon=[]

    # Cache the x,y,z values for max/min calc later
    # TODO: Look into faster ways to do this
    for point in polygon_4978.exterior.coords:
        # Cache the x,y,z values
        x, y, z = point[0], point[1], point[2]

        point_x_values_4978.append(x)
        point_y_values_4978.append(y)
        point_z_values_4978.append(z)

        point_x_this_polygon.append(x)
        point_y_this_polygon.append(y)
        point_z_this_polygon.append(z)

    # Use the simplified polygon to create a WKB
    miltipolygon_z_4978 = MultiPolygon([polygon_4978])

    # use the TriangleSoup helper class to transform the wkb into arrays
    # of points and normals
    print(f"Tesselating polygon to generate position and normal arrays")
    ts = TriangleSoup.from_wkb_multipolygon(miltipolygon_z_4978.wkb)
    positions = ts.getPositionArray()
    normals = ts.getNormalArray()

    box_mins = [min(point_x_this_polygon), min(point_y_this_polygon), min(point_z_this_polygon)]
    box_maxs = [max(point_x_this_polygon), max(point_y_this_polygon), max(point_z_this_polygon)]
    box_degrees = [box_maxs, box_mins]

    # generate the glTF part from the binary arrays.
    geometries.append({ 'position': positions, 'normal': normals, 'bbox': box_degrees})

    row += 1

print(f"Creating bounding box for gltf - EPSG ", final_epsg)
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

print("creating glTF")
gltf = GlTF.from_binary_arrays(geometries, transform=transform, batched=True)

#with open(save_as+".glb", "bw") as f:
#   f.write(bytes(gltf.to_array()))

# --- TODO: Create tileset JSON file ---
print(f"boundingVolume box for Cesium tile - EPSG ", final_epsg)
bounding_volume_box = [(min(point_x_values_4978) + max(point_x_values_4978))/2, (min(point_y_values_4978) + max(point_y_values_4978))/2, (min(point_z_values_4978) + max(point_z_values_4978))/2,
                        max(point_x_values_4978) - min(point_x_values_4978), 0, 0,
                        0, max(point_y_values_4978) - min(point_y_values_4978), 0,
                        0, 0, 0]

pprint(bounding_volume_box)

# Create the content for this tile
tileset["root"]["content"] = {
    "boundingVolume" : { "box": bounding_volume_box },
    "url": save_as_filename + ".b3dm"
}
# Add the bounding box to the root of the tileset
tileset["root"]["boundingVolume"] = { "box": bounding_volume_box }

# Create the tileset.json
# Serializing json 
json_object = json.dumps(tileset, indent = 4)
  
# Writing to sample.json
with open(save_to+"/tileset.json", "w") as outfile:
    outfile.write(json_object)

# --- Convert to b3dm -----
# create a b3dm tile_content directly from the glTF.
print("Creating b3dm file")
t = B3dm.from_glTF(gltf)

# to save our tile as a .b3dm file
t.save_as(save_to+"/"+save_as_filename+".b3dm")

print("Done.")

