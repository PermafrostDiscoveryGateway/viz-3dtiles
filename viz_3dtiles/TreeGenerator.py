import os
from .BoundingVolume import BoundingVolume
from .Cesium3DTile import Cesium3DTile
from .Tileset import Tileset, Asset, Content


def leaf_tile_from_gdf(
    gdf,
    dir='.',
    filename='tileset',
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None,
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
    ts = Tileset(**tileset_data)
    ts.to_file(os.path.join(dir, filename + '.json'))
    return ts


def combine_leaf_tiles(
    tile_list,
    dir='.',
    filename='tileset',
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None
):
    pass


def parent_tile_from_child_json(
    children,
    dir='.',
    filename='tileset',
    geometricError=None,
    tilesetVersion=None,
    boundingVolume=None
):
    pass
