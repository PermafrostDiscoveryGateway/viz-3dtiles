# -*- coding: utf-8 -*-
import json

class Cesium3DTileset:

    FILE_EXT="json"

    def __init__(self, tiles=[]):
        self.tiles = tiles
        self.save_as="tileset"
        self.save_to="~/"
        self.bbox = []
        return

    def add_tile(self, tile):
        self.tiles.append(tile)
    
    def get_boundingbox(self):
        print(f"boundingVolume box for Cesium tileset")

        # TODO: Support tilesets with more than one tile. Iterate over tiles and find bounding box of all.
        tile = self.tiles[0]
        gdf = tile.geodataframe

        minx=min(gdf.bounds.minx)
        maxx=max(gdf.bounds.maxx)
        miny=min(gdf.bounds.miny)
        maxy=max(gdf.bounds.maxy)
        bounding_volume_box = [(minx + maxx)/2, 
                            (miny + maxy)/2, 
                            (tile.min_tileset_z + tile.max_tileset_z)/2,
                            maxx - minx, 0, 0,
                            0, maxy - miny, 0,
                            0, 0, 0]

        self.bbox = bounding_volume_box

        return bounding_volume_box
    
    def to_json(self):

        tile = self.tiles[0]

        tileset = {
            "asset" : {
                "version" : "0.0"
            },
            "properties" : {
                "Class" : {}
            },
            "root" : {
                "refine" : "ADD",
                "content" : {}
            }
        }

        # Create the content for this tile
        tileset["root"]["content"] = {
            "boundingVolume" : { "box": self.bbox },
            "url": tile.get_filename()
        }
        # Add the bounding box to the root of the tileset
        tileset["root"]["boundingVolume"] = { "box": self.get_boundingbox() }
        tileset["geometricError"] = tile.max_width
        tileset["root"]["geometricError"] = tile.max_width

        # Create the tileset.json
        # Serializing json 
        json_object = json.dumps(tileset, indent = 4)

        return json_object

    def get_filename(self):
        return self.save_to + self.save_as + "." + self.FILE_EXT
    
    def write_file(self):
        
        # Writing to sample.json
        with open(self.get_filename(), "w") as outfile:
            outfile.write(self.to_json())
        
        print("Tileset saved to " + self.get_filename())
