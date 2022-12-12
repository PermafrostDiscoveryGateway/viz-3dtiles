import numpy as np
import open3d as o3d
from shapely.geometry import Polygon
from shapely import get_coordinates
import json


class BoundingVolume(object):

    def __init__(self, values=None):
        """
        Initialize a BoundingVolumeBox or a BoundingVolumeRegion.

        Parameters
        ----------
        values : list or dict
            A list or dict of 6 or 12 numbers representing the bounding volume
            as described in the Cesium3DTileset specification. A list of 6
            numbers will create a BoundingVolumeRegion, while a list of 12
            numbers will create a BoundingVolumeBox. Values may alternatively
            be a dict a single item that has either the 'box' or 'region' key
            mapped to the list of 6 or 12 numbers. Finally, values can also be
            passed as a dict of west, south, east, north, min_height, and
            max_height keys, with values in degrees (EPSG:4978) and meters.
        """
        # Check that values is a list or array
        if not isinstance(values, (list, np.ndarray, dict)):
            raise ValueError(
                'BoundingVolume values must be a list of 6 or 12 numbers, or a'
                ' dict of west, east, south, and north degrees')
        if isinstance(values, dict):
            box_vals = values.get('box')
            region_vals = values.get('region')
            if box_vals is not None:
                values = box_vals
            elif region_vals is not None:
                values = region_vals
        if self.is_degree_dict(values) or len(values) == 6:
            self.__class__ = BoundingVolumeRegion
            self.__init__(values)
        elif len(values) == 12:
            self.__class__ = BoundingVolumeBox
            self.__init__(values)
        else:
            raise ValueError(
                'BoundingVolume values must be a list of 12 numbers '
                '(to create a box) or 6 numbers (to create a region)')

    @staticmethod
    def is_degree_dict(values):
        """
        Check if values is a dict of west, east, south, and north degrees.
        """
        degrees = ['west', 'east', 'south', 'north']
        return isinstance(values, dict) and all(k in values for k in degrees)

    @ classmethod
    def from_points(cls, points, type='box'):
        if type == 'box':
            return BoundingVolumeBox.from_points(points)
        elif type == 'region':
            return BoundingVolumeRegion.from_points(points)

    @ classmethod
    def from_gdf(cls, gdf, type='box'):
        if type == 'box':
            return BoundingVolumeBox.from_gdf(gdf)
        elif type == 'region':
            return BoundingVolumeRegion.from_gdf(gdf)

    @ classmethod
    def from_z_polygons(cls, polys, type='box'):
        """
        Create a BoundingVolumeBox or BoundingVolumeRegion given
        a list of Z POLYGONS
        """
        points = get_coordinates(polys, include_z=True)
        if type == 'box':
            return BoundingVolumeBox.from_points(points)
        elif type == 'region':
            return BoundingVolumeRegion.from_points(points)

    @ classmethod
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

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)

    def to_dict(self):
        """
        Convert the box to a dict of 6 or 12 numbers.

        Returns
        -------
        box : dict
            A 6 or 12 element dict of numbers representing the bounding volume.
        """
        return {self.JSON_KEY: self.to_list()}

    def to_list(self):
        """
        Convert the box to list of 6 or 12 numbers.

        Returns
        -------
        box : list
            A 6 or 12 element list of numbers representing the bounding volume.
        """
        return self.to_array().tolist()


class BoundingVolumeBox(BoundingVolume):
    """
        A bounding volume box to use in a Cesium3DTileset. A bounding volume
        box is an oriented bounding box or a minimum area bounding box.
    """

    CESIUM_EPSG = 4978
    JSON_KEY = 'box'

    def __init__(self, values):
        """
        Initialize the box with a 12 element array.

        Parameters
        ----------
        values : list
            A list of 12 elements that define the box as per Cesium's 3DTileset
            specification, where: The first three elements define the x, y, and
            z values for the center of the box, the next three elements (with
            indices 3, 4, and 5) define the x axis direction and half-length,
            the next three elements (with indices 6, 7, and 8) define the y
            axis direction and half-length, and the last three elements
            (indices 9, 10, and 11) define the z axis direction and
            half-length.
        """

        # Check that list is a list
        assert isinstance(values, list)
        # Check that array is a 12 element array
        assert len(values) == 12
        self.center = values[0:3]
        self.xAxis = values[3:6]
        self.yAxis = values[6:9]
        self.zAxis = values[9:12]

    @ classmethod
    def from_points(cls, points):
        """
        Compute the oriented bounding box for a set of 3D points.

        Parameters
        ----------
        points : list of lists or numpy.ndarray
            A list or array of 3D points, each point of length 3.
        """
        # Check that list is a list or numpy array
        if isinstance(points, list):
            points = np.array(points)
        if not isinstance(points, np.ndarray):
            raise ValueError("points must be a list or numpy array")

        # Check that points are 3D
        assert len(points[0]) == 3

        points3d = o3d.utility.Vector3dVector(points)
        obb = o3d.geometry.OrientedBoundingBox.create_from_points(points3d)

        centroid = obb.center
        ext = obb.extent / 2.0
        rotation = obb.R

        x = rotation.dot([ext[0], 0, 0])
        y = rotation.dot([0, ext[1], 0])
        z = rotation.dot([0, 0, ext[2]])

        box = np.concatenate([centroid, x, y, z]).tolist()

        return cls(box)

    @ classmethod
    def from_gdf(cls, gdf):
        """
        Create a bounding volume box from a GeoPandas GeoDataFrame. Only
        polygon geometries are supported so far (i.e. the GeoDataFrame geometry
        column must be ONLY polygons).
        """

        # Check that the geometry contains polygons only
        num_non_polys = sum(gdf.geometry.type.unique() != 'Polygon')
        if num_non_polys > 0:
            raise ValueError('GeoDataFrame geometry can only contain polygons')

        # Check if there are z coordinates and add 0 if not
        if gdf.has_z.all() == False:
            gdf['geometry'] = gdf['geometry'].apply(lambda poly: Polygon(
                [(x, y, 0) for x, y in poly.exterior.coords]))

        # Check that the CRS is not None
        if gdf.crs is None:
            raise ValueError('GeoDataFrame must have a CRS')

        # check that the EPSG is correct
        if gdf.crs.to_epsg() != cls.CESIUM_EPSG:
            gdf = gdf.to_crs(epsg=cls.CESIUM_EPSG)

        coords = gdf.geometry.apply(lambda x: x.exterior.coords)
        points = np.vstack([p for p in coords])
        return cls.from_points(points)

    def get_corners(self):
        """
        Compute the 8 corner vertices of the oriented bounding box.

        Returns
        -------
        corners : numpy.ndarray
            An array of 8 3D points, each point of length 3.
        """
        center = np.array(self.center)
        xAxis = np.array(self.xAxis)
        yAxis = np.array(self.yAxis)
        zAxis = np.array(self.zAxis)

        # Make 8 copies of the center point. We will add or subtract the x, y,
        # and z axes to these points to get the corners of the box.
        corners = np.tile(center, (8, 1))

        corners[0] -= xAxis
        corners[0] -= yAxis
        corners[0] -= zAxis

        corners[1] -= xAxis
        corners[1] -= yAxis
        corners[1] += zAxis

        corners[2] -= xAxis
        corners[2] += yAxis
        corners[2] -= zAxis

        corners[3] -= xAxis
        corners[3] += yAxis
        corners[3] += zAxis

        corners[4] += xAxis
        corners[4] -= yAxis
        corners[4] -= zAxis

        corners[5] += xAxis
        corners[5] -= yAxis
        corners[5] += zAxis

        corners[6] += xAxis
        corners[6] += yAxis
        corners[6] -= zAxis

        corners[7] += xAxis
        corners[7] += yAxis
        corners[7] += zAxis

        return corners

    def add(self, other, inplace=False):
        """
        Add a box to this box.

        Parameters
        ----------
        other : BoundingVolumeBox or list
            The box to add to this box, represented as an instance of a
            BoundingVolumeBox or as a 12 element list.
        """
        other = self.__check_list_create_box(other)

        # Compute the 8 corner vertices of the box
        corners = self.get_corners()
        other_corners = other.get_corners()
        new_points = np.concatenate([corners, other_corners])
        new_box = BoundingVolumeBox.from_points(new_points)

        if inplace:
            self.update(new_box)
        else:
            return new_box

    def update(self, new_box):
        """
        Update the box with a new box. This will update the center, xAxis,
        yAxis, and zAxis of the box.

        Parameters
        ----------
        new_box : BoundingVolumeBox or list
            The box to update this box with, represented as an instance of a
            BoundingVolumeBox or as a 12 element list.
        """
        new_box = self.__check_list_create_box(new_box)

        self.center = new_box.center
        self.xAxis = new_box.xAxis
        self.yAxis = new_box.yAxis
        self.zAxis = new_box.zAxis

    def to_array(self):
        """
        Convert the box to a 12 element array.

        Returns
        -------
        box : numpy.ndarray
            A 12 element array representing the box.
        """
        return np.concatenate(
            [self.center, self.xAxis, self.yAxis, self.zAxis])

    @ staticmethod
    def __check_list_create_box(list_or_box):
        if isinstance(list_or_box, list):
            list_or_box = BoundingVolumeBox(list_or_box)
        assert isinstance(list_or_box, BoundingVolumeBox)
        return list_or_box


class BoundingVolumeRegion(BoundingVolume):
    """
        A bounding volume region to use in a Cesium3DTileset. A bounding volume
        defined by a box that is aligned to the coordinate reference system.
        The boundingVolume.region property is an array of six numbers that
        define the bounding geographic region with latitude, longitude, and
        height coordinates with the order [west, south, east, north, minimum
        height, maximum height]. It is also known as an Axis-Aligned Bounding
        Box.
    """

    CESIUM_EPSG = 4979
    JSON_KEY = 'region'

    def __init__(self, values):
        """
        Initialize the region with a list of 6 numbers that define the bounding
        geographic region with latitude, longitude, and height coordinates.

        Parameters
        ----------
        values : list
            A list of [west, south, east, north, minimum height, maximum
            height]. Latitudes and longitudes are in the WGS 84 datum as
            defined in EPSG 4979 and are in radians. Heights are in meters
            above (or below) the WGS 84 ellipsoid.
        """

        if self.is_degree_dict(values):
            values = self.values_list_from_degrees(**values)

        # Check that list is a list
        assert isinstance(values, list)
        # Check that array is a 12 element array
        assert len(values) == 6

        # Get the 3 values that define the minimum point along the x, y, and z
        # axes.
        self.west = values[0]
        self.south = values[1]
        self.east = values[2]
        self.north = values[3]
        self.min_height = values[4]
        self.max_height = values[5]

    @ classmethod
    def from_degrees(
            cls,
            west,
            south,
            east,
            north,
            min_height=0,
            max_height=0):
        """
        Create a bounding volume region from degrees.

        Parameters
        ----------
        west : float
            The west longitude in degrees.
        south : float
            The south latitude in degrees.
        east : float
            The east longitude in degrees.
        north : float
            The north latitude in degrees.
        min_height : float
            The minimum height in meters.
        max_height : float
            The maximum height in meters.

        Returns
        -------
        region : BoundingVolumeRegion
            A bounding volume region with the given values.
        """

        # Convert the degrees to radians
        vals = cls.values_list_from_degrees(vals)
        return cls(vals)

    @staticmethod
    def values_list_from_degrees(west,
            south,
            east,
            north,
            min_height=0,
            max_height=0):
        return np.deg2rad([west, south, east, north]).tolist() + \
            [min_height, max_height]

    @ classmethod
    def from_points(cls, points):
        """
        Compute the bounding volume region for a set of points. The x and y
        values of the points are assumed in EPSG 4979. The z values are assumed
        to be in meters above (or below) the WGS 84 ellipsoid. If no z values
        are provided, the z values are assumed to be zero.

        Parameters
        ----------
        points : list of lists or numpy.ndarray
            A list or array of 3D points, each point of length 2 or 3.
        """
        # Check that list is a list or numpy array
        if isinstance(points, list):
            points = np.array(points)
        if not isinstance(points, np.ndarray):
            raise ValueError('points must be a list or numpy array')

        # Check that array is a 2 or 3 element array
        if points.shape[1] != 3 and points.shape[1] != 2:
            raise ValueError('points must be a 2 or 3 element array')

        # Get the 3 values that define the minimum point along the x, y, and z
        # axes.
        west = np.min(points[:, 0])
        south = np.min(points[:, 1])
        east = np.max(points[:, 0])
        north = np.max(points[:, 1])

        # If there are no z values, set the min and max to zero
        if points.shape[1] == 2:
            min_height = 0
            max_height = 0
        else:
            min_height = np.min(points[:, 2])
            max_height = np.max(points[:, 2])

        coords = np.deg2rad([west, south, east, north])
        values = np.concatenate([coords, [min_height, max_height]]).tolist()

        return cls(values)

    @ classmethod
    def from_gdf(cls, gdf):
        """
        Create a bounding volume region from a GeoPandas GeoDataFrame. Only
        polygon geometries are supported so far (i.e. the GeoDataFrame geometry
        column must be ONLY polygons).
        """

        # Check that the geometry contains polygons only
        num_non_polys = sum(gdf.geometry.type.unique() != 'Polygon')
        if num_non_polys > 0:
            raise ValueError('GeoDataFrame geometry can only contain polygons')

        # Check that the CRS is not None
        if gdf.crs is None:
            raise ValueError('GeoDataFrame must have a CRS')

        # check that the EPSG is correct
        if gdf.crs.to_epsg() != cls.CESIUM_EPSG:
            gdf = gdf.to_crs(epsg=cls.CESIUM_EPSG)

        coords = gdf.geometry.apply(lambda x: x.exterior.coords)
        points = np.vstack([p for p in coords])
        return cls.from_points(points)

    def get_corners(self):
        """
        Compute the 8 corner vertices of the bounding volume region.

        Returns
        -------
        corners : numpy.ndarray
            An array of 8 3D points, with x and y in degrees, and Z in meters.
        """
        coords = self.get_coords()
        heights = self.get_heights()
        # Compute the 8 corner vertices of the region
        corners = np.array([
            [coords[0], coords[1], heights[0]],
            [coords[0], coords[1], heights[1]],
            [coords[0], coords[3], heights[0]],
            [coords[0], coords[3], heights[1]],
            [coords[2], coords[1], heights[0]],
            [coords[2], coords[1], heights[1]],
            [coords[2], coords[3], heights[0]],
            [coords[2], coords[3], heights[1]]
        ])
        return corners

    def get_coords(self):
        """
        Get the west, south, east, north coordinates of this region in degrees

        Returns
        -------
        coords : numpy.ndarray
            The array of outermost coordinates of the region, in the order
            [west, south, east, north].
        """
        coords = np.array([
            self.west, self.south,
            self.east, self.north
        ])
        return np.rad2deg(coords)

    def get_heights(self):
        """
        Get the minimum and maximum heights of the region.

        Returns
        -------
        heights : numpy.ndarray
            The array of minimum and maximum heights of the region, in the order
            [min_height, max_height].
        """
        return [self.min_height, self.max_height]

    def add(self, other, inplace=False):
        """
        Add a region to this region.

        Parameters
        ----------
        other : BoundingVolumeRegion or list
            The region to add to this region, represented as an instance of a
            BoundingVolumeRegion or as list of 6 numbers.
        inplace : bool
            If True, add the region to this region in-place. If False, return a new
            region.
        """
        other = self.__check_list_create_region(other).to_array()
        this = self.to_array()

        # Add the two regions
        coords_other = np.rad2deg(other[0:4])
        this_coords = np.rad2deg(this[0:4])
        new_coords = [
            min(this_coords[0], coords_other[0]),
            min(this_coords[1], coords_other[1]),
            max(this_coords[2], coords_other[2]),
            max(this_coords[3], coords_other[3])
        ]
        new_coords = np.deg2rad(new_coords)

        new_heights = [
            min(this[4], other[4]),
            max(this[5], other[5])
        ]

        new_values = np.concatenate([new_coords, new_heights]).tolist()

        if inplace:
            self.update(new_values)
        else:
            return BoundingVolumeRegion(new_values)

    def update(self, new_bv):
        """
        Update the region with a new region. This will update the coordinates
        and heights of the region.

        Parameters
        ----------
        new_bv : BoundingVolumeRegion or list
            The region to update this region with, represented as an instance of a
            BoundingVolumeRegion or a a list of 6 numbers
        """
        new_bv = self.__check_list_create_region(new_bv)

        # Update the region
        self.west = new_bv.west
        self.south = new_bv.south
        self.east = new_bv.east
        self.north = new_bv.north
        self.min_height = new_bv.min_height
        self.max_height = new_bv.max_height

    def to_array(self):
        """
        Convert the region to a 6 element array.

        Returns
        -------
        region : numpy.ndarray
            A 6 element array representing the region.
        """
        return np.array([
            self.west,
            self.south,
            self.east,
            self.north,
            self.min_height,
            self.max_height
        ])

    @ staticmethod
    def __check_list_create_region(list_or_region):
        if isinstance(list_or_region, list):
            list_or_region = BoundingVolumeRegion(list_or_region)
        assert isinstance(list_or_region, BoundingVolumeRegion)
        return list_or_region
