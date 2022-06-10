import numpy as np


class BoundingVolumeRegion(object):
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

    @classmethod
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

    @classmethod
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

    def to_list(self):
        """
        Convert the region to a 6 element list.

        Returns
        -------
        region : list
            A 12 element list representing the region.
        """
        return self.to_array().tolist()

    @staticmethod
    def __check_list_create_region(list_or_region):
        if isinstance(list_or_region, list):
            list_or_region = BoundingVolumeRegion(list_or_region)
        assert isinstance(list_or_region, BoundingVolumeRegion)
        return list_or_region
