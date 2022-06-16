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
    return tileset, json_path


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
    child_paths,
    dir='',
    filename='tileset',
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None,
    minify_json=True
):

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