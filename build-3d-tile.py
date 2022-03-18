from shapely.geometry import Polygon, MultiPolygon
from shapely import ops
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
max_features=1500

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

gdf['geometry'] = gdf['geometry'].simplify(tolerance)

row = 0
for feature in gdf.iterfeatures():
    if row > max_features-1:
        break

    # Build the new PolygonZ with a static z value
    polygon = ops.transform(lambda x, y: (x, y, 0.5), Polygon(feature["geometry"]["coordinates"][0]))

    gdf["geometry"][row] = polygon
    row += 1

# Transform the incoming shapes from a geographic 4326 CRS to
# the Cesium-internal earth-centered, earth-fixed (ECEF) 4978 CRS
# See https://medium.com/terria/georeferencing-3d-models-for-cesium-7ccf609ee2ef
gdf_4978 = gdf.to_crs(epsg=4978)


min_tileset_z=9e99
max_tileset_z=-9e99
geometries=[]
row = 0
for feature in gdf_4978.iterfeatures():
    if row > max_features-1:
        break
    print(f"Processing {row + 1} of {len(gdf_4978)} in EPSG", final_epsg)

    # Create a multipolygon for only this polygon feature
    polygon=Polygon(feature["geometry"]["coordinates"][0])
    multipolygon = MultiPolygon([polygon])

    # use the TriangleSoup helper class to transform the wkb into arrays of points and normals
    print(f"Tesselating polygon to generate position and normal arrays")
    ts = TriangleSoup.from_wkb_multipolygon(multipolygon.wkb)
    positions = ts.getPositionArray()
    normals = ts.getNormalArray()

    # Calculate the bounding box 
    # First get the z values since shapely bounds function does not support 3D geom/z values)
    z = [z for (x,y,z) in feature["geometry"]["coordinates"][0]]
    minz=min(z)
    maxz=max(z)
    box_degrees = [ [multipolygon.bounds[2], multipolygon.bounds[3], maxz],
                    [multipolygon.bounds[0], multipolygon.bounds[1], minz] ]

    # Cache the min and max z values for fast retrieval later
    if minz < min_tileset_z:
        min_tileset_z=minz
    if maxz > max_tileset_z:
        max_tileset_z=maxz

    # generate the glTF part from the binary arrays.
    geometries.append({ 'position': positions, 'normal': normals, 'bbox': box_degrees})

    row += 1

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

minx=min(gdf_4978.bounds.minx)
maxx=max(gdf_4978.bounds.maxx)
miny=min(gdf_4978.bounds.miny)
maxy=max(gdf_4978.bounds.maxy)
bounding_volume_box = [(minx + maxx)/2, 
                       (miny + maxy)/2, 
                       (min_tileset_z + max_tileset_z)/2,
                       maxx - minx, 0, 0,
                       0, maxy - miny, 0,
                       0, 0, 0]

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