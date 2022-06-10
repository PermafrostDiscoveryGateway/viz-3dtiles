from .BoundingVolumeBox import BoundingVolumeBox
from .BoundingVolumeRegion import BoundingVolumeRegion
import numpy as np


class BoundingVolume(object):

    def __init__(self, values=None):
        # Check that values is a list or array
        if not isinstance(values, list) and not isinstance(values, np.ndarray):
            raise ValueError('BoundingVolume values must be a list')
        if len(values) == 12:
            self.__class__ = BoundingVolumeBox
            self.__init__(values)
        elif len(values) == 6:
            self.__class__ = BoundingVolumeRegion
            self.__init__(values)
        else:
            raise ValueError(
                'BoundingVolume values must be a list of 12 numbers '
                '(to create a box) or 6 numbers (to create a region)')

    @classmethod
    def from_points(cls, points, type='box'):
        if type == 'box':
            return BoundingVolumeBox.from_points(points)
        elif type == 'region':
            return BoundingVolumeRegion.from_points(points)

    @classmethod
    def from_gdf(cls, gdf, type='box'):
        if type == 'box':
            return BoundingVolumeBox.from_gdf(gdf)
        elif type == 'region':
            return BoundingVolumeRegion.from_gdf(gdf)

    @classmethod
    def from_json(cls, json_data):
        """
        Parse a dict created from JSON into a BoundingVolume object. The source
        JSON should have the format: {'box': [x, y, z, ...x_axis array...,
        ...y_axis array..., ...z_axis array...]} OR {'region': [west, south,
        east, north, minimum height, maximum height]}
        """
        if not isinstance(json_data, dict):
            raise ValueError('json_data must be a dictionary')
        values = json_data.get('box') or json_data.get('region')
        if not values:
            raise ValueError('json_data must have a box or region key')
        return cls(values)

