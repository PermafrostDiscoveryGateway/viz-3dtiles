import math
import os
from .BoundingVolume import BoundingVolume
from .Cesium3DTile import Cesium3DTile
from .Cesium3DTileset import Tileset, Asset, Content


def _height_preserving_bounding_volume(bounding_volume, fallback_bounding_volume):
    if not isinstance(bounding_volume, dict):
        return BoundingVolume(bounding_volume)

    if not BoundingVolume.is_degree_dict(bounding_volume):
        return BoundingVolume(bounding_volume)

    bounded = dict(bounding_volume)
    if "min_height" not in bounded or "max_height" not in bounded:
        try:
            min_height, max_height = fallback_bounding_volume.get_heights()
        except AttributeError:
            min_height, max_height = 0.0, 1.0
        bounded.setdefault("min_height", min_height)
        bounded.setdefault("max_height", max_height)

    return BoundingVolume(bounded)


def _bounding_volume_geometric_error(bounding_volume):
    """
    Estimate a traversal-friendly geometric error from a bounding volume size.
    """
    if bounding_volume is None:
        return 0.0

    if "to_dict" in dir(bounding_volume):
        bounding_volume = bounding_volume.to_dict()

    values = bounding_volume.get("box") or bounding_volume.get("region")
    if values is None:
        return 0.0

    if len(values) == 12:
        axes = [values[3:6], values[6:9], values[9:12]]
        half_lengths = [math.sqrt(sum(coord * coord for coord in axis)) for axis in axes]
        return max(2.0 * math.sqrt(sum(length * length for length in half_lengths)), 0.0)

    if len(values) == 6:
        west, south, east, north, min_height, max_height = values
        mean_lat = (south + north) / 2.0
        earth_radius_m = 6378137.0
        width = abs(east - west) * earth_radius_m * math.cos(mean_lat)
        height = abs(north - south) * earth_radius_m
        depth = abs(max_height - min_height)
        return max(math.sqrt(width * width + height * height + depth * depth), 0.0)

    return 0.0


def leaf_tile_from_gdf(
    gdf,
    dir="",
    filename="tileset",
    crs=None,
    z=None,
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None,
    minify_json=True,
):
    """
    Create a leaf tile in a Cesium 3D tileset tree. Convert a GeoDataFrame of
    polygons into a Cesium3DTile B3DM file and Cesium3DTileset JSON file.

    Parameters
    ----------
    gdf : GeoDataFrame
        A GeoDataFrame containing polygons to be converted to a Cesium tile.
    dir : str
        The directory to save both the JSON and B3DM files to. If the directory
        does not exist, it will be created.
    filename : str
        The base filename for the tile, excluding base directory and extension.
        The JSON and B3DM files will be saved as <filename>.json and
        <filename>.b3dm. Default is 'tileset'.
    crs : str
        The coordinate reference system of the GeoDataFrame, if the GeoDataFrame
        does not have a CRS set.
    z : float
        If the GeoDataFrame does not have a Z coordinate, then the Z coordinate
        will be set to this value. If omitted, a small visible lift is used.
    geometricError : float
        The geometric error of the tile. If None (default), the geometric error
        will be the max_width calculated when creating the Cesium3DTile (B3DM).
    tilesetVersion : str
        An application specific version for the tileset (optional).
    boundingVolume : list or dict
        A root bounding volume for the tile. If None (default), the bounding
        volume will be the calculated oriented bounding box (OBB) of the
        GeoDataFrame. The OBB will be used for the content bounding volume in
        either case.
    minify_json : bool
        Whether to minify the JSON file. Default is True.

    Returns
    -------
    tile, tileset : Cesium3DTile, Tileset
        The Cesium3DTiles and Cesium3DTileset objects
    """
    tile = Cesium3DTile()
    tile.save_to = dir
    tile.save_as = filename
    tile.from_geodataframe(gdf, crs=crs, z=z)

    json_path = os.path.join(dir, filename + ".json")
    tileset = Tileset.from_Cesium3DTiles(tile, json_path)

    if boundingVolume:
        tileset.root.boundingVolume = _height_preserving_bounding_volume(
            boundingVolume, tileset.root.boundingVolume
        )

    if geometricError is not None:
        tileset.geometricError = geometricError
        tileset.root.geometricError = geometricError

    if tilesetVersion:
        tileset.asset.tilesetVersion = tilesetVersion

    tileset.to_file(json_path, minify=minify_json)
    return tile, tileset


# def combine_leaf_tiles(
#     tile_list,
#     dir='',
#     filename='tileset',
#     geometricError=None,
#     tilesetVersion=None,
#     boundingVolume=None,
#     minify_json=True
# ):
#     pass


def parent_tile_from_children_json(
    children,
    dir="",
    filename="tileset",
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None,
    boundingVolumeSource="content",
    minify_json=True,
):
    """
    Create a parent tile in a Cesium 3D tileset tree. The parent tile will
    inherit properties such as extensionsUsed, extras, properties and
    root.refine, root.transform, etc. from the first child tile. Other
    properties are calculated or can be specified with the geometricError,
    tilesetVersion, and boundingVolume parameters.

    Parameters
    ----------
    children : list of str or list of Tileset
        A list of JSON files or Cesium3DTiles that the parent tile should point
        to. All child tiles must be saved to files, and their file paths must
        be in the same format as the dir parameter for this function. This is
        because the method calculates the relative path the child JSON files
        from the starting from the path where the parent JSON file will be
        saved.
    dir : str
        The directory to save the parent JSON file to. If the directory does
        not exist, it will be created. If the path is relative, then the
        children file paths must also be relative. If the path is absolute,
        then the children file paths must be absolute.
    filename : str
        The base filename for the tile, excluding base directory and extension.
        The JSON file will be saved as <filename>.json. Default is 'tileset'.
    geometricError : float
        The geometric error of the tile. If None (default), the max of the
        child geometric errors will be used.
    tilesetVersion : str
        An application specific version for the tileset (optional). If None,
        the tilesetVersion from the first child tile will be used.
    boundingVolume : list or dict
        A root bounding volume for the tile. If None (default), the bounding
        volume will be the calculated as the union of the child bounding
        volumes.
    boundingVolumeSource : "root" or "content"
        When a boundingVolume is not set, then which of each child's bounding
        volumes should be used to calculate the parent tile's bounding volume.
        This method is passed to bv_source parameter in the Tile.add_children
        method. If set to "content" (default), then the method will first
        search for a child's content bounding volume, and will add it to the
        tile's root bounding volume if they exist. If a child has no content
        bounding volume, then the root bounding volume will be added instead.
    minify_json : bool
        Whether to minify the JSON file. Default is True.


    Returns
    -------
    tileset : Tileset
        The Cesium3DTileset object

    """

    if not isinstance(children, (list, tuple)):
        children = [children]

    # Check the tileset children
    child_paths = []
    if all(isinstance(child, str) for child in children):
        child_paths = children
    elif all(isinstance(child, Tileset) for child in children):
        if any(child.file_path is None for child in children):
            raise ValueError(
                "Child tilesets must all be saved to a file before "
                "being added to a parent tile. This is required because the parent "
                "tile needs relative paths to the child tileset JSON."
            )
        child_paths = [child.file_path for child in children]
    else:
        raise ValueError("Children must be a list of paths or Tileset objects.")

    # Check that all the child JSON files exist
    if any(not os.path.exists(child_path) for child_path in child_paths):
        raise ValueError("One or more child JSON files does not exist.")

    child_geo_errors = []
    child_tilesets = []
    child_root_tiles = []
    rel_child_paths = []

    for i in range(len(child_paths)):
        # Read in the relevant parts of the child data
        cp = child_paths[i]
        child_tileset = Tileset.from_file(cp)
        child_root = child_tileset.root
        rel_path_to_child = os.path.relpath(cp, dir)
        geometric_error = child_tileset.geometricError
        child_root.children = None
        # Append child data parts to lists
        child_geo_errors.append(geometric_error)
        child_tilesets.append(child_tileset)
        child_root_tiles.append(child_root)
        rel_child_paths.append(rel_path_to_child)

    # Use the first child's tileset info to create the parent tileset
    new_tileset = child_tilesets[0].copy()
    new_tileset.root.content = None
    new_tileset.root.children = None

    # Add children first so we can preserve their vertical extent even when an
    # external bounding volume constrains the horizontal tile footprint.
    bv_method = "replace"
    bv_source = boundingVolumeSource
    new_tileset.add_children(child_root_tiles, bv_method, bv_source)

    # All bv info from children is now in parent. Update the children content
    # to only contain the URI for the child json, relative to the new parent
    # json
    for i in range(len(child_root_tiles)):
        child = new_tileset.root.children[i]
        child.content = Content(uri=rel_child_paths[i])

    # Update other parameters to the parent tileset
    if boundingVolume:
        new_tileset.root.boundingVolume = _height_preserving_bounding_volume(
            boundingVolume, new_tileset.root.boundingVolume
        )

    if tilesetVersion:
        new_tileset.asset.tilesetVersion = tilesetVersion

    if geometricError is not None:
        parent_geometric_error = geometricError
    else:
        parent_geometric_error = max(
            child_geo_errors
            + [_bounding_volume_geometric_error(new_tileset.root.boundingVolume)]
        )

    new_tileset.geometricError = parent_geometric_error
    new_tileset.root.geometricError = parent_geometric_error

    # make output directory if it doesn't exist, then save
    if not os.path.exists(dir):
        os.makedirs(dir, exist_ok=True)
    out_path = os.path.join(dir, filename + ".json")
    new_tileset.to_file(out_path, minify=minify_json)
    return new_tileset
