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
import logging

# Initialize logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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
        logger.info(f"Processing file: {filepath}")
        try:
            gdf: GeoDataFrame = geopandas.read_file(filepath)

            logger.debug(f"Columns before processing: {gdf.columns.tolist()}")

            if drop_staging:
                staging_columns = gdf.filter(like="staging_").columns
                if len(staging_columns) > 0:
                    logger.info(f"Dropping staging columns: {staging_columns.tolist()}")
                    gdf = gdf.drop(columns=staging_columns)

            logger.debug(f"Columns after processing: {gdf.columns.tolist()}")

            self.from_geodataframe(gdf, crs, z)
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {str(e)}")
            raise

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
        logger.info(f"Reprojecting geometries to EPSG:{self.CESIUM_EPSG}")
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
        original_count = len(self.geodataframe)
        # Replace inf values with nan in numeric columns only
        self.geodataframe = self.geodataframe.replace([np.inf, -np.inf], np.nan)
        logger.debug(f"Only dropping rows with NaN geometry values")
        # Only drop rows where the geometry is null/invalid
        self.geodataframe = self.geodataframe[self.geodataframe.geometry.notna()]
        removed_count = original_count - len(self.geodataframe)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} rows with inf/nan values")

    def filter_polygons(self):
        # Filter out polygons beyond the maximum
        if self.max_features is not None:
            original_count = len(self.geodataframe)
            self.geodataframe = self.geodataframe[0 : self.max_features]
            if len(self.geodataframe) < original_count:
                logger.info(
                    f"Limited features to {self.max_features} (was {original_count})"
                )

        # Filter polygons with a certain attribute
        for key, value in self.filter_by_attributes.items():
            try:
                original_count = len(self.geodataframe)
                self.geodataframe = self.geodataframe[self.geodataframe[key] == value]
                filtered_count = len(self.geodataframe)
                logger.info(
                    f"Filtered by {key}={value}: {original_count} -> {filtered_count} features"
                )
            except Exception as e:
                logger.warning(
                    f"Could not filter polygons by attribute '{key}': {str(e)}"
                )

    def tesselate(self):
        logger.info("Starting tessellation process")
        min_tileset_z = 9e99
        max_tileset_z = -9e99
        max_width = -9e99

        for i, geom in enumerate(self.transformed_geometries):
            if i % 100 == 0:  # Log progress every 100 geometries
                logger.debug(
                    f"Processing geometry {i+1}/{len(self.transformed_geometries)}"
                )

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

        logger.info(
            f"Tessellation complete. Processed {len(self.geometries)} geometries"
        )
        logger.debug(f"Z range: {min_tileset_z:.2f} to {max_tileset_z:.2f}")

    def create_gltf(self):
        logger.info("Creating glTF content")

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

        gltf = GlTF.from_binary_arrays(
            self.geometries, transform=transform, batched=True
        )

        if self.debugCreateGLB == True:
            glb_path = self.save_to + self.save_as + ".glb"
            logger.debug(f"Saving debug GLB file to: {glb_path}")
            with open(glb_path, "bw") as f:
                f.write(bytes(gltf.to_array()))

        self.gltf = gltf
        logger.info("glTF creation complete")

    def create_batch_table(self):
        logger.debug("Creating batch table")

        bt = BatchTable()

        if self.batch_table_uuid == True:
            logger.debug("Adding UUID column to batch table")
            values = []
            for i in range(0, len(self.geodataframe)):
                u = uuid.uuid4()
                values.append(u.urn)
            self.geodataframe["uuid"] = values

        attributes = self.geodataframe.columns.drop("geometry")
        logger.debug(
            f"Adding {len(attributes)} attributes to batch table: {attributes.tolist()}"
        )

        for attr in attributes:
            values = []
            for v in self.geodataframe[attr].values:
                values.append(str(v))
            bt.header.add_property_from_array(property_name=attr, array=values)

        self.batch_table = bt
        logger.debug("Batch table creation complete")

        return bt

    def create_b3dm(self):
        logger.info("Creating B3DM tile")
        # --- Convert to b3dm -----
        # create a b3dm tile_content directly from the glTF.
        t = B3dm.from_glTF(self.gltf, bt=self.create_batch_table())

        # to save our tile as a .b3dm file
        output_path = os.path.join(self.save_to, self.get_filename())
        logger.info(f"Saving B3DM tile to: {output_path}")
        t.save_as(output_path)
        logger.info("B3DM tile creation complete")

    def get_filename(self):
        return self.save_as + self.FILE_EXT
