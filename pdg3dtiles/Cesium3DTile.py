# -*- coding: utf-8 -*-
import geopandas
from geopandas.geodataframe import GeoDataFrame
from shapely.geometry import Polygon, MultiPolygon, LinearRing
from shapely import get_coordinates
from .py3dtiles_integration.wkb_utils import TriangleSoup
from .py3dtiles_integration.b3dm import B3dm
from .py3dtiles_integration.b3dm_feature_table import B3dmFeatureTable
from .py3dtiles_integration.batch_table import BatchTable
import numpy as np
import os
import uuid
import logging
from pathlib import Path

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
        self.save_to = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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
        self.geometries = []
        self.gltf = None
        self.batch_table = None
        self.max_width = 0
        self.min_tileset_z = 0
        self.max_tileset_z = 0

        if gdf.crs is None:
            if crs is None:
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
        
        self.geodataframe["geometry"] = self.geodataframe["geometry"].apply(self.to_multipolygon)
        logger.info(f"Reprojecting geometries to EPSG:{self.CESIUM_EPSG}")
        gdf_4978 = self.geodataframe.to_crs(epsg=self.CESIUM_EPSG)

        self.transformed_geometries = gdf_4978.geometry

        # this is to filter out any geometries that did not tessellate
        valid_mask = self.tesselate()
        self.geodataframe = self.geodataframe.loc[valid_mask].copy()
        self.transformed_geometries = self.transformed_geometries.loc[valid_mask].copy()
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
        num_cols = self.geodataframe.select_dtypes(include="number").columns
        if len(num_cols) > 0:
            self.geodataframe[num_cols] = self.geodataframe[num_cols].replace(
                [np.inf, -np.inf], np.nan
            )

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
            self.geodataframe = self.geodataframe.iloc[: self.max_features]
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
        min_tileset_z = None
        max_tileset_z = None
        max_width = 0
        valid_mask = []

        for i, geom in enumerate(self.transformed_geometries):
            if i % 100 == 0:  # Log progress every 100 geometries
                logger.debug(
                    f"Processing geometry {i+1}/{len(self.transformed_geometries)}"
                )

            multipolygon = geom
            ts = TriangleSoup.from_wkb_multipolygon(multipolygon.wkb)
            positions = ts.get_position_array()
            normals = ts.get_normal_array()

            is_valid = len(positions) > 0
            valid_mask.append(is_valid)

            if not is_valid:
                continue

            coords = get_coordinates(geom, include_z=True)
            z_vals = coords[:, 2]
            minz = float(z_vals.min())
            maxz = float(z_vals.max())

            if min_tileset_z is None or minz < min_tileset_z:
                min_tileset_z = minz
            if max_tileset_z is None or maxz > max_tileset_z:
                max_tileset_z = maxz

            minx, miny, maxx_geom, maxy_geom = multipolygon.bounds
            dx = maxx_geom - minx
            dy = maxy_geom - miny
            tile_span = max(dx, dy)
            if tile_span > max_width:
                max_width = tile_span

            self.geometries.append({
                "position": positions,
                "normal": normals,
            })

        if not self.geometries:
            self.max_width = 0
            self.max_tileset_z = 0
            self.min_tileset_z = 0
            logger.info("Tessellation complete. No valid geometries found.")
            return valid_mask

        self.max_width = max_width
        self.max_tileset_z = max_tileset_z
        self.min_tileset_z = min_tileset_z

        logger.info(
            f"Tessellation complete. Processed {len(self.geometries)} geometries"
        )
        return valid_mask

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
        if not self.geometries:
            logger.warning("Skipping B3DM creation: no tessellated geometries.")
            return

        points_list = []
        normals_list = []
        triangles_list = []
        batchids_list = []
        kept_indices = []
        vertex_offset = 0

        for geom_index, geom in enumerate(self.geometries):
            raw_points = geom["position"]
            raw_normals = geom["normal"]

            logger.debug(
                f"position type={type(raw_points)}, normal type={type(raw_normals)}"
            )

            if isinstance(raw_points, (bytes, bytearray)):
                points = np.frombuffer(raw_points, dtype=np.float32)
            else:
                points = np.asarray(raw_points, dtype=np.float32)

            if isinstance(raw_normals, (bytes, bytearray)):
                normals = np.frombuffer(raw_normals, dtype=np.float32)
            else:
                normals = np.asarray(raw_normals, dtype=np.float32)

            points = points.reshape(-1, 3)
            normals = normals.reshape(-1, 3)

            if len(points) == 0:
                logger.warning(f"Skipping geometry {geom_index}: no points")
                continue

            if len(points) % 3 != 0:
                logger.warning(
                    f"Skipping geometry {geom_index}: expanded triangle vertices "
                    f"are not divisible by 3: {len(points)}"
                )
                continue

            unique_points = np.unique(points, axis=0)

            if len(unique_points) < 4:
                logger.warning(
                    f"Skipping geometry {geom_index}: "
                    f"fewer than 4 unique points"
                )
                continue

            spread = np.ptp(unique_points, axis=0)

            if np.count_nonzero(spread > 1e-5) < 2:
                logger.warning(
                    f"Skipping geometry {geom_index}: "
                    f"too small coordinate spread {spread}"
                )
                continue

            triangles = np.arange(len(points), dtype=np.uint32).reshape(-1, 3)
            triangles = triangles + vertex_offset
            batchids = np.full(len(points), len(points_list), dtype=np.float32)

            points_list.append(points)
            normals_list.append(normals)
            triangles_list.append(triangles)
            batchids_list.append(batchids)
            kept_indices.append(geom_index)
            vertex_offset += len(points)

        if not points_list:
            logger.warning("Skipping B3DM creation: no valid tessellated arrays.")
            return

        self.geodataframe = self.geodataframe.iloc[kept_indices].copy()
        self.transformed_geometries = self.transformed_geometries.iloc[kept_indices].copy()
        all_points = np.vstack(points_list).astype(np.float32)
        all_normals = np.vstack(normals_list).astype(np.float32)
        all_triangles = np.vstack(triangles_list).astype(np.uint32)
        all_batchids = np.concatenate(batchids_list).astype(np.float32)

        # Reverse for Cesium-facing orientation.
        all_triangles = all_triangles[:, [0, 2, 1]]
        all_normals = -all_normals

        feature_table = B3dmFeatureTable()
        feature_table.set_batch_length(len(points_list))

        logger.info(f"B3dm module in use: {B3dm.__module__}")
        logger.info(f"Feature table data before tile creation: {feature_table.header.data}")
        logger.info(f"Batch IDs shape: {all_batchids.shape}")

        tile = B3dm.from_numpy_arrays(
            points=all_points,
            triangles=all_triangles,
            normal=all_normals,
            batchids=all_batchids,
            batch_table=self.create_batch_table(),
            feature_table=feature_table,
        )

        output_path = Path(self.save_to) / self.get_filename()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving B3DM tile to: {output_path}")

        if getattr(self, "debugCreateGLB", False):
            glb_path = output_path.with_suffix(".glb")
            logger.info(f"Saving debug GLB file to: {glb_path}")
            tile.save_debug_glb(glb_path)

        tile.save_as(output_path)
        logger.info("B3DM tile creation complete")

    def get_filename(self):
        return self.save_as + self.FILE_EXT
