# -*- coding: utf-8 -*-
import json
import os
from pathlib import Path
from statistics import mean
import numpy as np
from scipy.spatial import ConvexHull
import shapely


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
        # print(f"boundingVolume box for Cesium tileset")

        # TODO: Support tilesets with more than one tile. Iterate over tiles
        # and find bounding box of all.
        tile = self.tiles[0]
        gdf = tile.geodataframe

        minx = min(gdf.bounds.minx)
        maxx = max(gdf.bounds.maxx)
        miny = min(gdf.bounds.miny)
        maxy = max(gdf.bounds.maxy)
        bounding_volume_box = [(minx + maxx) / 2,
                               (miny + maxy) / 2,
                               (tile.min_tileset_z + tile.max_tileset_z) / 2,
                               maxx - minx, 0, 0,
                               0, maxy - miny, 0,
                               0, 0, 0]

        self.bbox = bounding_volume_box

        return bounding_volume_box

    def get_min_bounding_rect(self):
        """
            Find the smallest bounding rectangle for a set of polygons in a
            GeoDataFrame. Returns a set of points representing the corners of
            the bounding box for the minimum bounding rectangle. Adapted from
            https://stackoverflow.com/a/33619018


            Returns
            -------
            A set of points representing the corners of the bounding box for
            the minimum bounding rectangle.
        """

        # TODO: Support tilesets with more than one tile. Iterate over tiles
        # and find bounding box of all.
        tile = self.tiles[0]
        gdf = tile.geodataframe

        # Get the bounding rectangle for just the x and y coordinates
        # (not z)
        geoms2D = gdf.geometry.apply(
            lambda x: shapely.wkb.loads(
                shapely.wkb.dumps(
                    x, output_dimension=2)))

        # Get all points from all polygons, as a nx2 matrix of coordinates
        coords = geoms2D.apply(lambda x: x.exterior.coords)
        points = np.vstack([p for p in coords])

        pi2 = np.pi / 2.

        # get the convex hull for the points
        hull_points = points[ConvexHull(points).vertices]

        # calculate edge angles
        edges = np.zeros((len(hull_points) - 1, 2))
        edges = hull_points[1:] - hull_points[:-1]

        angles = np.zeros((len(edges)))
        angles = np.arctan2(edges[:, 1], edges[:, 0])

        angles = np.abs(np.mod(angles, pi2))
        angles = np.unique(angles)

        # find rotation matrices
        rotations = np.vstack([
            np.cos(angles),
            np.cos(angles - pi2),
            np.cos(angles + pi2),
            np.cos(angles)]).T

        rotations = rotations.reshape((-1, 2, 2))

        # apply rotations to the hull
        rot_points = np.dot(rotations, hull_points.T)

        # find the bounding points
        min_x = np.nanmin(rot_points[:, 0], axis=1)
        max_x = np.nanmax(rot_points[:, 0], axis=1)
        min_y = np.nanmin(rot_points[:, 1], axis=1)
        max_y = np.nanmax(rot_points[:, 1], axis=1)

        # find the box with the best area
        areas = (max_x - min_x) * (max_y - min_y)
        best_idx = np.argmin(areas)

        # return the best box
        x1 = max_x[best_idx]
        x2 = min_x[best_idx]
        y1 = max_y[best_idx]
        y2 = min_y[best_idx]
        r = rotations[best_idx]

        rval = np.zeros((4, 2))
        rval[0] = np.dot([x1, y2], r)
        rval[1] = np.dot([x2, y2], r)
        rval[2] = np.dot([x2, y1], r)
        rval[3] = np.dot([x1, y1], r)

        return rval

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
