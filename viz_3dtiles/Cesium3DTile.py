# -*- coding: utf-8 -*-
import geopandas
from geopandas.geodataframe import GeoDataFrame
from shapely.geometry import Polygon, MultiPolygon, LinearRing
from shapely import get_coordinates
from py3dtiles.tileset.content import GlTF, B3dm
from py3dtiles.tileset.batch_table import BatchTable
from py3dtiles.tilers.b3dm.wkb_utils import TriangleSoup
import numpy as np
import os
import uuid


class Cesium3DTile:
    CESIUM_EPSG = 4978
    FILE_EXT = ".b3dm"

    def __init__(self):
        self.geodataframe = GeoDataFrame()
        self.z = 0
        self.save_as = "model"
        self.save_to = (
            os.path.dirname(os.path.abspath(__file__)) + r"../"
        )  # base dir of repo
        self.max_features = 99999999999
        self.geometries = []
        self.gltf = None
        self.debugCreateGLB = False
        self.batch_table = None
        self.max_width = 0
        self.min_tileset_z = 0
        self.max_tileset_z = 0

        # A set of dynamically-generated properties to add to the 3DTile BatchTable.
        # Any properties already set via the original file or Geodataframe will be kept intact.
        self.batch_table_uuid = True
        self.batch_table_centroid = False
        self.batch_table_area = False

        # A dictionary of key:value pairs for which matching polygons will be removed.
        # e.g { centroid_within_tile: True }
        self.filter_by_attributes = {}

    def set_save_to_path(self, path):
        """
        The filepath to save the 3DTile. If the path does not exist, it will be created (handled by package py3dtiles)

        Parameters
        ----------
        path : string
            The destination of the 3DTile.
        """
        self.save_to = path

    def set_b3dm_name(self, name):
        """
        Set the filename, not filepath or extension, of the 3DTile.

        Parameters
        ----------
        name : string
            The filename (not path) of the 3DTile.
        """
        self.save_as = name

    def get_all_properties(self):
        """
        Get all proerties of the Cesium3DTile class as a dictionary.
        """
        return {
            "z": self.z,
            "geodataframe": self.geodataframe,
            "save_as": self.save_as,
            "save_to": self.save_to,
            "max_features": self.max_features,
            "geometries": self.geometries,
            "gltf": self.gltf,
            "debugCreateGLB": self.debugCreateGLB,
            "max_width": self.max_width,
            "min_tileset_z": self.min_tileset_z,
            "max_tileset_z": self.max_tileset_z,
            "filter_by_attributes": self.filter_by_attributes,
        }

    def from_file(self, filepath, crs=None, z=0, drop_staging=False):
        """
        Parameters
        ----------
        filepath : string
            The path to the file to convert
        """
        print("Filepath: " + filepath)
        try:
            gdf: GeoDataFrame = geopandas.read_file(filepath)

            print("Before:", gdf.columns.tolist())

            if drop_staging:
                gdf = gdf.drop(columns=gdf.filter(like="staging_").columns)

            print("After:", gdf.columns.tolist())

            self.from_geodataframe(gdf, crs, z)
        except Exception as e:
            print("Error reading file: " + str(e))
            print("Filepath: " + filepath)

    def from_geodataframe(self, gdf, crs=None, z=0):

        # Set the default z-level that we will set on 2D polygons
        self.z = z

        if gdf.crs == None:
            if crs == None:
                raise Exception(
                    "The vector file must have a CRS defined,"
                    " or a crs parameter must be provided."
                )
            gdf = gdf.set_crs(crs)

        self.geodataframe = gdf

        # Remove rows with inf or nan values
        self.remove_inf_nan()

        # Filter out polygons as needed
        self.filter_polygons()

        gdf["geometry"] = gdf["geometry"].apply(self.to_multipolygon)

        # Re-project polygons to the Cesium CRS for tesselation.
        gdf = gdf.to_crs(epsg=self.CESIUM_EPSG)

        self.transformed_geometries = gdf.geometry

        self.tesselate()
        self.create_gltf()
        self.create_b3dm()

    # Ensure all geometries are MultiPolygon and 3D
    def make_3d(self, geom):
        """Adds a Z-coordinate to a geometry."""
        if geom.has_z:
            exterior = [(x, y, z + self.z) for x, y, z in geom.exterior.coords]
            interior = [
                LinearRing([(x, y, z + self.z) for x, y, z in ring.coords])
                for ring in geom.interiors
            ]
        else:
            exterior = [(x, y, self.z) for x, y in geom.exterior.coords]
            interior = [
                LinearRing([(x, y, self.z) for x, y in ring.coords])
                for ring in geom.interiors
            ]
        return Polygon(exterior, interior)

    def to_multipolygon(self, geom):
        """Converts a Polygon to a MultiPolygon."""
        if isinstance(geom, Polygon):
            return MultiPolygon([self.make_3d(geom)])
        elif isinstance(geom, MultiPolygon):
            return MultiPolygon([self.make_3d(poly) for poly in geom.geoms])
        else:
            raise ValueError("Geometry must be a Polygon or MultiPolygon")

    def remove_inf_nan(self):
        """Remove rows with inf or nan values from the geodataframe."""
        self.geodataframe = self.geodataframe.replace(
            [np.inf, -np.inf], np.nan
        ).dropna()

    def filter_polygons(self):
        # Filter out polygons beyond the maximum
        if self.max_features is not None:
            self.geodataframe = self.geodataframe[0 : self.max_features]

        # Filter polygons with a certain attribute
        for key, value in self.filter_by_attributes.items():
            try:
                self.geodataframe = self.geodataframe[self.geodataframe[key] == value]
            except:
                print("Not filtering out polygons for attribute " + key)

    def tesselate(self):
        min_tileset_z = 9e99
        max_tileset_z = -9e99
        max_width = -9e99

        for geom in self.transformed_geometries:

            multipolygon = geom

            # use the TriangleSoup helper class to transform the wkb into
            # arrays of points and normals
            ts = TriangleSoup.from_wkb_multipolygon(multipolygon.wkb)
            positions = ts.get_position_array()
            normals = ts.get_normal_array()

            # Calculate the bounding box First get the z values since shapely
            # bounds function does not support 3D geom/z values)
            zs = [z for (x, y, z) in get_coordinates(geom, include_z=True)]
            minz = min(zs)
            maxz = max(zs)
            bounds = multipolygon.bounds
            box_degrees = [[bounds[2], bounds[3], maxz], [bounds[0], bounds[1], minz]]

            # Cache the min and max z values for fast retrieval later
            if minz < min_tileset_z:
                min_tileset_z = minz
            if maxz > max_tileset_z:
                max_tileset_z = maxz

            if geom.length > max_width:
                max_width = geom.length

            # generate the glTF part from the binary arrays.
            self.geometries.append(
                {"position": positions, "normal": normals, "bbox": box_degrees}
            )

            self.max_width = max_width
            self.max_tileset_z = max_tileset_z
            self.min_tileset_z = min_tileset_z

    def create_gltf(self):

        transform = np.array(
            [
                [
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    -1.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ]
            ],
            dtype=float,
        )

        transform = transform.flatten("F")

        # print("creating glTF")
        gltf = GlTF.from_binary_arrays(
            self.geometries, transform=transform, batched=True
        )

        if self.debugCreateGLB == True:
            with open(self.save_to + self.save_as + ".glb", "bw") as f:
                f.write(bytes(gltf.to_array()))

        self.gltf = gltf

    def create_batch_table(self):
        # print("Creating Batch table")

        bt = BatchTable()

        if self.batch_table_uuid == True:
            values = []
            for i in range(0, len(self.geodataframe)):
                u = uuid.uuid4()
                values.append(u.urn)
            self.geodataframe["uuid"] = values

        attributes = self.geodataframe.columns.drop("geometry")

        for attr in attributes:
            # print("Adding " + attr)
            values = []
            for v in self.geodataframe[attr].values:
                values.append(str(v))
            bt.header.add_property_from_array(property_name=attr, array=values)

        self.batch_table = bt

        return bt

    def create_b3dm(self):

        # --- Convert to b3dm -----
        # create a b3dm tile_content directly from the glTF.
        # print("Creating b3dm file")
        t = B3dm.from_glTF(self.gltf, bt=self.create_batch_table())

        # to save our tile as a .b3dm file
        t.save_as(os.path.join(self.save_to, self.get_filename()))

    def get_filename(self):
        return self.save_as + self.FILE_EXT
