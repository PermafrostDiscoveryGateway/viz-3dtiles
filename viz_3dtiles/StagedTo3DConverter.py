
import logging
import os
import json
from statistics import mean

import geopandas as gpd
import pdgstaging

from . import Cesium3DTile
from . import Cesium3DTileset


logger = logging.getLogger(__name__)


class StagedTo3DConverter():
    """
        Processes staged vector data into Cesium 3D tiles according to the
        settings in a config file or dict. This class acts as the orchestrator
        of the other viz-3dtiles classes, and coordinates the sending and
        receiving of information between them.
    """

    def __init__(
        self,
        config
    ):
        """
            Initialize the StagedTo3DConverter class.

            Parameters
            ----------

            config : dict or str
                A dictionary of configuration settings or a path to a config
                JSON file. (See help(pdgstaging.ConfigManager))
        """

        self.config = pdgstaging.ConfigManager(config)
        self.tiles = pdgstaging.TilePathManager(
            **self.config.get_path_manager_config())

        # For now, manually add directory for the 3D tiles. We should add this
        # to the ConfigManager & TilePathManager class
        b3dm_ext = Cesium3DTile.FILE_EXT
        b3dm_dir = self.config.get('dir_3dtiles')
        self.tiles.add_base_dir('3dtiles', dir_path=b3dm_dir, ext=b3dm_ext)

    def all_staged_to_3dtiles(
        self,
        parent_json=False
    ):
        """
            Process all staged vector tiles into 3D tiles.

            Parameters
            ----------

            parent_json : bool
                If True, then a single parent tileset.json file will be created
                that encompasses all the 3D Tiles created. The children json
                files will subsequently be removed.
        """

        # Get the list of staged vector tiles
        paths = self.tiles.get_filenames_from_dir('staged')
        # Process each tile
        for path in paths:
            self.staged_to_3dtile(path)

        if parent_json:
            self.create_parent_json()

    def staged_to_3dtile(
        self,
        path
    ):
        # Get information about the tile from the path
        tile = self.tiles.tile_from_path(path)
        out_path = self.tiles.path_from_tile(tile, '3dtiles')

        # Get the filename of the tile WITHOUT the extension
        tile_filename = os.path.splitext(os.path.basename(out_path))[0]
        # Get the base of the path, without the filename
        tile_dir = os.path.dirname(out_path) + os.path.sep

        # Log the event
        logger.info(
            f'Creating 3dtile from {path} for tile {tile} to {out_path}.')

        # Read in the staged vector tile
        gdf = gpd.read_file(path)

        # Remove polygons with centroids that are outside the tile boundary
        prop_cent_in_tile = self.config.polygon_prop('centroid_within_tile')
        gdf = gdf[gdf[prop_cent_in_tile]]

        # Check if deduplication should be performed
        dedup_here = self.config.deduplicate_at('3dtiles')
        dedup_method = self.config.get_deduplication_method()

        # Deduplicate if required
        if dedup_here and (dedup_method is not None):
            dedup_config = self.config.get_deduplication_config(gdf)
            dedup = dedup_method(gdf, **dedup_config)
            gdf = dedup['keep']

        # Create & save the b3dm file
        tile3d = Cesium3DTile()
        tile3d.set_save_to_path(tile_dir)
        tile3d.set_b3dm_name(tile_filename)
        tile3d.from_geodataframe(gdf)

        # Create & save the tileset json
        tileset = Cesium3DTileset(tiles=[tile3d])
        tileset.set_save_to_path(tile_dir)
        tileset.set_json_filename(tile_filename)
        tileset.write_file()

    def create_parent_json(self, remove_children=True):
        """
            Merge all the tileset json files into one main tileset.json file.

            Parameters
            ----------

            remove_children : bool
                If True, then the children json files will be removed after
                they are merged into the parent.
        """

        # Get the list of b3dm files
        b3dms = self.tiles.get_filenames_from_dir('3dtiles')

        # Extensions will be used to find the json file associated with each
        # b3dm file
        b3dm_ext = Cesium3DTile.FILE_EXT
        json_ext = '.' + Cesium3DTileset.FILE_EXT

        # Get the base directory where the 3D tiles are stored
        dir3d = self.tiles.get_base_dir('3dtiles')['path']
        # The tileset.json should be saved at the root of this directory
        parent_json_path = os.path.join(dir3d, 'tileset.json')

        tileset = {
            "asset": {
                "version": "0.0"
            },
            "geometricError": None,
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

        json_paths = []

        # Check that all the JSON files exist
        for b3dm in b3dms:

            # Get the JSON path
            json_path = b3dm.replace(b3dm_ext, json_ext)

            if not os.path.isfile(json_path):
                raise ValueError(f'JSON file {json_path} does not exist')

            # Track the paths that will be used (to remove if required)
            json_paths.append(json_path)

            # Read in the json
            with open(json_path, 'r') as f:
                j = json.load(f)

            # Get the bounding volume
            bv = j['root']['boundingVolume']['box']
            # Get the geometric error
            ge = j['root']['geometricError']

            # The URI of the B3DM file should be relative to the tileset.json
            uri = os.path.relpath(b3dm, dir3d)

            # Make the json/dict
            child = {
                "geometricError": ge,
                "boundingVolume": {"box": bv},
                "refine": "ADD",
                "content": {
                    "boundingVolume": {"box": bv},
                    "uri": uri
                }
            }

            # Add the child to the tileset
            tileset['root']['children'].append(child)

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
        parent_geometric_error = max(all_ges)

        # Update the tileset
        tileset['root']['boundingVolume']['box'] = parent_bounding_volume
        tileset['root']['geometricError'] = parent_geometric_error
        tileset['geometricError'] = parent_geometric_error

        # Write the tileset.json
        with open(parent_json_path, 'w') as f:
            json.dump(tileset, f, indent=4)

        if remove_children:
            # Remove the children
            for j in json_paths:
                os.remove(j)
