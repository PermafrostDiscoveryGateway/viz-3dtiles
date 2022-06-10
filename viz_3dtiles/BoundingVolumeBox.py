import numpy as np
import open3d as o3d
from shapely.geometry import Polygon


class BoundingVolumeBox(object):
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

    @classmethod
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

    @classmethod
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
            gdf['geometry'] = gdf['geometry'].apply(lambda poly: 
                Polygon([(x, y, 0) for x, y in poly.exterior.coords])
            )

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

    def to_list(self):
        """
        Convert the box to a 12 element list.

        Returns
        -------
        box : list
            A 12 element list representing the box.
        """
        return self.to_array().tolist()

    def to_json_dict(self):
        return {self.JSON_KEY: self.to_list()}

    @staticmethod
    def __check_list_create_box(list_or_box):
        if isinstance(list_or_box, list):
            list_or_box = BoundingVolumeBox(list_or_box)
        assert isinstance(list_or_box, BoundingVolumeBox)
        return list_or_box
