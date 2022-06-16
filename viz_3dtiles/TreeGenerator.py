import os
from .BoundingVolume import BoundingVolume
from .Cesium3DTile import Cesium3DTile
from .Tileset import Tileset, Asset, Content


def leaf_tile_from_gdf(
    gdf,
    dir='',
    filename='tileset',
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None,
    minify_json=True
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
    tile.from_geodataframe(gdf)
    gdf = tile.geodataframe
    tile_bounding_volume = BoundingVolume.from_gdf(gdf)
    tile.get_filename()

    # Only set the optional content bounding volume if it differs from the root
    # tile bounding volume
    root_bounding_volume = tile_bounding_volume
    content_bounding_volume = None
    if(boundingVolume):
        root_bounding_volume = BoundingVolume(boundingVolume)
        content_bounding_volume = tile_bounding_volume

    asset = Asset(tilesetVersion=tilesetVersion)

    content = Content(
        uri=tile.get_filename(),
        boundingVolume=content_bounding_volume
    )

    root_tile_data = {
        'boundingVolume': root_bounding_volume,
        'geometricError': geometricError or tile.max_width,
        'content': content
    }
    tileset_data = {
        'asset': asset,
        'geometricError': geometricError or tile.max_width,
        'root': root_tile_data
    }
    tileset = Tileset(**tileset_data)
    json_path = os.path.join(dir, filename + '.json')
    tileset.to_file(json_path, minify=minify_json)
    return tile, tileset


def combine_leaf_tiles(
    tile_list,
    dir='',
    filename='tileset',
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None,
    minify_json=True
):
    pass


def parent_tile_from_children_json(
    children,
    dir='',
    filename='tileset',
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None,
    minify_json=True
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
        volume will be the calculated oriented bounding box (OBB) of the
        GeoDataFrame. The OBB will be used for the content bounding volume in
        either case.
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
                'Child tilesets must all be saved to a file before '
                'being added to a parent tile. This is required because the parent '
                'tile needs relative paths to the child tileset JSON.')
        child_paths = [child.file_path for child in children]
    else:
        raise ValueError(
            'Children must be a list of paths or Tileset objects.')

    # Check that all the child JSON files exist
    if any(not os.path.exists(child_path) for child_path in child_paths):
        raise ValueError('One or more child JSON files does not exist.')

    child_geo_errors = []
    child_tilesets = []
    child_root_tiles = []

    for i in range(len(child_paths)):
        # Read in the relevant parts of the child data
        cp = child_paths[i]
        child_tileset = Tileset.from_file(cp)
        child_root = child_tileset.root
        rel_path_to_child = os.path.relpath(cp, dir)
        geometric_error = child_tileset.geometricError
        # update the content to only contain the URI for the child json,
        # relative to the new parent json
        child_root.content = Content(uri=rel_path_to_child)
        child_root.children = None
        # Append child data parts to lists
        child_geo_errors.append(geometric_error)
        child_tilesets.append(child_tileset)
        child_root_tiles.append(child_root)

    # Use the first child's tileset info to create the parent tileset
    new_tileset = child_tilesets[0].copy()
    new_tileset.root.content = None
    new_tileset.root.children = None

    # Add the children to the parent tileset
    bv_method = 'replace' if boundingVolume is None else None
    new_tileset.add_children(child_root_tiles, bv_method)

    # Update other parameters to the parent tileset
    if boundingVolume:
        new_tileset.root.boundingVolume = BoundingVolume(boundingVolume)

    if tilesetVersion:
        new_tileset.asset.tilesetVersion = tilesetVersion

    if geometricError is not None:
        new_tileset.geometricError = geometricError
    else:
        new_tileset.geometricError = max(child_geo_errors)

    # make output directory if it doesn't exist, then save
    if not os.path.exists(dir):
        os.makedirs(dir, exist_ok=True)
    out_path = os.path.join(dir, filename + '.json')
    new_tileset.to_file(out_path, minify=minify_json)
    return new_tileset
