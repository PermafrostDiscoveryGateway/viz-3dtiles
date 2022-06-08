# -*- coding: utf-8 -*-
import json
import os
from pathlib import Path
from statistics import mean
import numpy as np
import open3d as o3d


class Cesium3DTileset:

    FILE_EXT = "json"

    def __init__(self, tiles=[]):
        self.tiles = [tiles]
        self.save_as = "tileset"
        self.save_to = "~/"
        self.bbox = []
        return

    def set_json_filename(self, filename):
        '''
        Set the filename of the tileset.json
        '''
        self.save_as = filename

    def set_save_to_path(self, path):
        """
        Set the filepath, but not the filename or extension, of tileset.json.
        If the path does not exist, it will be created (handled by package
        py3dtiles)

        Parameters
        ----------
        path : string
            The destination filepath of the json.
        """
        self.save_to = path

    def add_tile(self, tile):
        self.tiles.append(tile)

    def get_boundingbox(self):
        """
            Find the oriented bounding box for the tile. Return it an array of
            12 numbers that define an oriented bounding box in a right-handed
            3-axis (x, y, z) Cartesian coordinate system where the z-axis is
            up. The first three elements define the x, y, and z values for the
            center of the box. The next three elements (with indices 3, 4, and
            5) define the x-axis direction and half-length. The next three
            elements (indices 6, 7, and 8) define the y-axis direction and
            half-length. The last three elements (indices 9, 10, and 11) define
            the z-axis direction and half-length.

            Returns
            -------
            list
                A list of 12 numbers that define an oriented bounding box as
                required by the 3D Tiles Specification 1.0
        """

        # TODO: Support tilesets with more than one tile.
        tile = self.tiles[0]
        gdf = tile.geodataframe
        coords = gdf.geometry.apply(lambda x: x.exterior.coords)
        points = np.vstack([p for p in coords])

        points3d = o3d.utility.Vector3dVector(points)
        obb = o3d.geometry.OrientedBoundingBox.create_from_points(points3d)

        centroid = obb.center
        ext = obb.extent / 2.0
        rotation = obb.R

        x = rotation.dot([ext[0], 0, 0])
        y = rotation.dot([0, ext[1], 0])
        z = rotation.dot([0, 0, ext[2]])

        return np.concatenate([centroid,x,y,z]).tolist()

    def to_json(self):

        tile = self.tiles[0]

        tileset = {
            "asset": {
                "version": "0.0"
            },
            "properties": {
                "Class": {}
            },
            "root": {
                "refine": "ADD",
                "content": {}
            }
        }

        # Create the content for this tile
        tileset["root"]["content"] = {
            "boundingVolume": {"box": self.get_boundingbox()},
            "url": tile.get_filename()
        }
        # Add the bounding box to the root of the tileset
        tileset["root"]["boundingVolume"] = {"box": self.get_boundingbox()}
        tileset["geometricError"] = tile.max_width
        tileset["root"]["geometricError"] = tile.max_width

        # Create the tileset.json Serializing json
        json_object = json.dumps(tileset, indent=4)

        return json_object

    def get_filename(self):
        return self.save_to + self.save_as + "." + self.FILE_EXT

    def write_file(self):
        # Write to sample.json

        # create file if doesn't exist.
        filepath = Path(self.get_filename())
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.touch(exist_ok=True)

        with open(self.get_filename(), "w") as outfile:
            outfile.write(self.to_json())

        # print("Tileset saved to " + self.get_filename())

    def create_parent_json(
        self,
        json_paths=[],
        save_to=None,
        save_as="tileset.json",
        remove_children=True
    ):
        """
            Merge all the tileset json files into one main tileset.json file.

            Parameters
            ----------

            json_paths : list of strings
                The paths to the tileset json files to be merged

            save_to : string (optional)
                Set the filepath, but not the filename or extension, of
                tileset.json. If set to None, then the save_to path on the
                tileset instance will be used.

            save_as : string (optional)
                Set the filename of the tileset, without the extension.
                Defaults to "tileset". If set to None, then the save_as string
                on the tileset instance will be used.

            remove_children : bool
                If True, then the children json files will be removed after
                they are merged into the parent.
        """

        if save_to is None:
            save_to = self.save_to

        if save_as is None:
            save_as = self.save_as

        # The tileset.json should be saved at the root of this directory
        parent_json_path = os.path.join(save_to, save_as + "." + self.FILE_EXT)

        tileset = {
            "asset": {
                "version": "0.0"
            },
            "root": {
                "boundingVolume": {"box": []},
                "geometricError": None,
                "refine": "ADD",
                "children": []
            }
        }

        # Parent bounding volume is the union of all B3DM bounding volumes
        all_bvs = []

        # Parent geometric error
        all_ges = []

        # Check that all the JSON files exist
        for json_path in json_paths:

            if not os.path.isfile(json_path):
                raise ValueError(f"JSON file {json_path} does not exist")

            # Read in the json
            with open(json_path, "r") as f:
                j = json.load(f)

            # Get the bounding volume
            bv = j["root"]["boundingVolume"]["box"]
            # Get the geometric error
            ge = j["root"]["geometricError"]

            # The URI of the B3DM file should be relative to the parent
            # tileset.json file. URL in child JSON is just the filename + ext
            # of the B3DM file (not the full path). Assume the child JSON is
            # saved in the same directory as the child B3DM.
            child_filename = j["root"]["content"]["url"]
            child_fullpath = os.path.join(
                os.path.dirname(json_path), child_filename)
            rel_uri = os.path.relpath(child_fullpath, save_to)

            # Make the json/dict
            child = {
                "geometricError": ge,
                "boundingVolume": {"box": bv},
                "refine": "ADD",
                "content": {
                    "boundingVolume": {"box": bv},
                    "uri": rel_uri
                }
            }

            # Add the child to the tileset
            tileset["root"]["children"].append(child)

            # Add the bounding volume to the list of all bounding volumes
            all_bvs.append(bv)

            # Add the geometric error to the list of all geometric errors
            all_ges.append(ge)

        # Calculate the parent bounding volume
        mid_x = mean([bv[0] for bv in all_bvs])
        mid_y = mean([bv[1] for bv in all_bvs])
        mid_z = mean([bv[2] for bv in all_bvs])
        width = sum([bv[3] for bv in all_bvs])
        length = sum([bv[7] for bv in all_bvs])
        parent_bounding_volume = [
            mid_x, mid_y, mid_z, width,
            0, 0, 0, length, 0, 0, 0, 0]

        # Calculate the parent geometric error
        parent_geometric_error = sum(all_ges)

        # Update the tileset
        tileset["root"]["boundingVolume"]["box"] = parent_bounding_volume
        tileset["root"]["geometricError"] = parent_geometric_error

        # Write the tileset.json
        with open(parent_json_path, "w") as f:
            json.dump(tileset, f, indent=4)

        if remove_children:
            # Remove the children
            for j in json_paths:
                os.remove(j)
