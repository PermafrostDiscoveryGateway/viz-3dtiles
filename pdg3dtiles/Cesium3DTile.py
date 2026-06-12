# -*- coding: utf-8 -*-
import logging
import math
import os
import uuid
from pathlib import Path

import geopandas
import numpy as np
import pygltflib
from geopandas.geodataframe import GeoDataFrame
from py3dtiles.tileset.content import gltf_utils
from py3dtiles.tileset.content.b3dm import B3dm
from py3dtiles.tileset.content.b3dm_feature_table import B3dmFeatureTable
from py3dtiles.tileset.content.batch_table import BatchTable
from py3dtiles.tileset.content.gltf import Gltf
from shapely import get_coordinates
from shapely.geometry import LinearRing, MultiPolygon, Polygon

from .triangulation import triangulate_multipolygon

# Initialize logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Cesium3DTile:
    CESIUM_EPSG = 4978
    FILE_EXT = ".b3dm"
    DEFAULT_FALLBACK_Z = 1.0

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

    def from_file(self, filepath, crs=None, z=None, drop_staging=False):
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

    def from_geodataframe(self, gdf, crs=None, z=None):

        # Set the fallback z-level for 2D polygons only. Existing 3D input
        # keeps its own z values.
        self.z = self._normalize_fallback_z(z)
        self.geometries = []
        self.gltf = None
        self.batch_table = None
        self.max_width = 0
        self.min_tileset_z = 0
        self.max_tileset_z = 0
        self.geometric_error = 0

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

        self.geodataframe["geometry"] = self.geodataframe["geometry"].apply(
            self.to_multipolygon
        )
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
        """Ensure a polygon has Z, using self.z only for 2D coordinates."""
        if geom.has_z:
            exterior = [
                (coord[0], coord[1], coord[2]) for coord in geom.exterior.coords
            ]
            interior = [
                LinearRing([(coord[0], coord[1], coord[2]) for coord in ring.coords])
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

    @classmethod
    def _normalize_fallback_z(cls, z):
        if z is None:
            return cls.DEFAULT_FALLBACK_Z
        try:
            z = float(z)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid 2D polygon fallback z %r; using %sm.",
                z,
                cls.DEFAULT_FALLBACK_Z,
            )
            return cls.DEFAULT_FALLBACK_Z
        if not math.isfinite(z):
            logger.warning(
                "Non-finite 2D polygon fallback z %r; using %sm.",
                z,
                cls.DEFAULT_FALLBACK_Z,
            )
            return cls.DEFAULT_FALLBACK_Z
        return z

    @staticmethod
    def _geometry_has_z(geom):
        if isinstance(geom, Polygon):
            return geom.has_z
        if isinstance(geom, MultiPolygon):
            return all(poly.has_z for poly in geom.geoms)
        return False

    @staticmethod
    def _metric_gdf_for_error(gdf):
        if gdf.crs is None:
            return gdf
        try:
            if not gdf.crs.is_geographic:
                return gdf
            estimated_crs = gdf.estimate_utm_crs()
            if estimated_crs is not None:
                return gdf.to_crs(estimated_crs)
        except Exception as exc:
            logger.debug("Could not estimate local metric CRS: %s", exc)
        return gdf.to_crs(epsg=3857)

    @classmethod
    def _compute_geometric_error(cls, gdf):
        """Estimate per-tile geometric error from local footprint radius."""
        try:
            metric_gdf = cls._metric_gdf_for_error(
                gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
            )
        except Exception as exc:
            logger.debug("Could not project geometries for geometric error: %s", exc)
            metric_gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

        max_distance = 0.0
        for geom in metric_gdf.geometry:
            if geom is None or geom.is_empty:
                continue
            try:
                distance = float(geom.hausdorff_distance(geom.centroid))
            except Exception as exc:
                logger.debug("Could not compute Hausdorff distance: %s", exc)
                continue
            if math.isfinite(distance):
                max_distance = max(max_distance, distance)
        return max(max_distance, 1.0)

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
        geometric_error = self._compute_geometric_error(self.geodataframe)
        valid_mask = []

        for i, geom in enumerate(self.transformed_geometries):
            if i % 100 == 0:  # Log progress every 100 geometries
                logger.debug(
                    f"Processing geometry {i+1}/{len(self.transformed_geometries)}"
                )

            multipolygon = geom
            mesh = triangulate_multipolygon(multipolygon)
            positions = mesh.positions
            normals = mesh.normals
            indices = mesh.indices

            is_valid = len(positions) > 0 and len(indices) > 0
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

            self.geometries.append(
                {
                    "position": positions,
                    "normal": normals,
                    "indices": indices,
                }
            )

        if not self.geometries:
            self.max_width = 0
            self.max_tileset_z = 0
            self.min_tileset_z = 0
            logger.info("Tessellation complete. No valid geometries found.")
            return valid_mask

        self.max_width = max_width
        self.geometric_error = geometric_error
        self.max_tileset_z = max_tileset_z
        self.min_tileset_z = min_tileset_z

        logger.info(
            f"Tessellation complete. Processed {len(self.geometries)} geometries"
        )
        return valid_mask

    def create_batch_table(self):
        logger.debug("Creating batch table")

        bt = BatchTable()

        if self.batch_table_uuid is True:
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
            bt.add_property_as_json(property_name=attr, array=values)

        self.batch_table = bt
        logger.debug("Batch table creation complete")

        return bt

    def _build_b3dm(self):
        logger.info("Building B3DM tile content")
        if not self.geometries:
            logger.warning("Skipping B3DM creation: no tessellated geometries.")
            return

        meshes = []
        kept_indices = []
        total_vertices = 0
        total_indices = 0
        min_bounds = np.full(3, np.inf, dtype=np.float64)
        max_bounds = np.full(3, -np.inf, dtype=np.float64)

        for geom_index, geom in enumerate(self.geometries):
            raw_points = geom["position"]
            raw_normals = geom["normal"]
            raw_indices = geom["indices"]

            logger.debug(
                "position type=%s, normal type=%s, indices type=%s",
                type(raw_points),
                type(raw_normals),
                type(raw_indices),
            )

            points = np.asarray(raw_points, dtype=np.float64).reshape(-1, 3)
            normals = np.asarray(raw_normals, dtype=np.float32).reshape(-1, 3)
            indices = np.asarray(raw_indices, dtype=np.uint32).reshape(-1, 3)

            if len(points) == 0 or len(indices) == 0:
                logger.warning(f"Skipping geometry {geom_index}: no points")
                continue

            if normals.shape != points.shape:
                logger.warning(
                    f"Skipping geometry {geom_index}: normals shape {normals.shape} "
                    f"does not match points shape {points.shape}"
                )
                continue

            if not np.isfinite(points).all() or not np.isfinite(normals).all():
                logger.warning(f"Skipping geometry {geom_index}: non-finite vertices")
                continue

            if np.max(indices) >= len(points):
                logger.warning(
                    f"Skipping geometry {geom_index}: invalid triangle index"
                )
                continue

            spread = np.ptp(points, axis=0)

            if np.count_nonzero(spread > 1e-5) < 2:
                logger.warning(
                    f"Skipping geometry {geom_index}: "
                    f"too small coordinate spread {spread}"
                )
                continue

            meshes.append((points, normals, indices))
            kept_indices.append(geom_index)
            total_vertices += len(points)
            total_indices += indices.size
            min_bounds = np.minimum(min_bounds, points.min(axis=0))
            max_bounds = np.maximum(max_bounds, points.max(axis=0))

        if not meshes:
            logger.warning("Skipping B3DM creation: no valid tessellated arrays.")
            return

        if total_vertices > np.iinfo(np.uint32).max:
            raise ValueError(
                "Generated glTF exceeds uint32 index capacity; split input features "
                "into multiple tiles before creating B3DM content."
            )

        if len(kept_indices) != len(self.geometries):
            self.geodataframe = self.geodataframe.iloc[kept_indices].copy()
            self.transformed_geometries = self.transformed_geometries.iloc[
                kept_indices
            ].copy()

        # RTC_CENTER: subtract the tile centroid so vertex offsets are small (~meters).
        # ECEF coords are about 4-6M meters so float32 only gives about 0.5m resolution; small
        # offsets from the center give sub-millimeter float32 precision instead.
        rtc_center = (min_bounds + max_bounds) / 2

        all_points = np.empty((total_vertices, 3), dtype=np.float32)
        all_normals = np.empty((total_vertices, 3), dtype=np.float32)
        index_dtype = (
            np.uint16 if total_vertices <= np.iinfo(np.uint16).max else np.uint32
        )
        all_indices = np.empty(total_indices, dtype=index_dtype)
        all_batchids = np.empty(total_vertices, dtype=np.float32)

        vertex_cursor = 0
        index_cursor = 0
        for batch_index, (points, normals, indices) in enumerate(meshes):
            vertex_count = len(points)
            index_count = indices.size
            vertex_slice = slice(vertex_cursor, vertex_cursor + vertex_count)
            index_slice = slice(index_cursor, index_cursor + index_count)

            np.subtract(
                points,
                rtc_center,
                out=all_points[vertex_slice],
                casting="unsafe",
            )
            all_normals[vertex_slice] = normals
            all_batchids[vertex_slice] = batch_index
            np.add(
                indices.reshape(-1),
                vertex_cursor,
                out=all_indices[index_slice],
                casting="unsafe",
            )

            vertex_cursor += vertex_count
            index_cursor += index_count

        all_indices = all_indices.reshape(-1, 3)

        # Z-up to Y-up rotation stored as a glTF node matrix (column-major, 4x4).
        # Cesium auto-applies Y-up to Z-up at the b3dm level; the two rotations cancel
        # so vertices end up at their correct ECEF positions.
        transform = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        ).flatten(
            "F"
        )  # column-major for glTF node.matrix

        feature_table = B3dmFeatureTable()
        feature_table.set_batch_length(len(meshes))
        # Store RTC_CENTER as inline JSON so Cesium reads it at float64 precision.
        feature_table.header.data["RTC_CENTER"] = rtc_center.tolist()

        logger.info(f"B3dm module in use: {B3dm.__module__}")
        logger.info(
            f"Feature table data before tile creation: {feature_table.header.data}"
        )
        logger.info(f"Batch IDs shape: {all_batchids.shape}")

        batchid_attribute = gltf_utils.GltfAttribute(
            "_BATCHID",
            pygltflib.SCALAR,
            pygltflib.FLOAT,
            all_batchids,
        )
        mesh = gltf_utils.GltfMesh(
            all_points,
            primitives=[
                gltf_utils.GltfPrimitive(
                    indices=all_indices,
                    material=pygltflib.Material(doubleSided=True),
                )
            ],
            normals=all_normals,
            additional_attributes=[batchid_attribute],
        )
        tile = B3dm.from_meshes(
            [mesh],
            batch_table=self.create_batch_table(),
            feature_table=feature_table,
            transform=transform,
        )

        self.gltf = Gltf(tile.body.gltf)
        return tile

    def create_gltf(self):
        logger.info("Creating glTF content")
        tile = self._build_b3dm()
        if tile is None:
            return

        if getattr(self, "debugCreateGLB", False):
            glb_path = Path(self.save_to) / f"{self.save_as}.glb"
            logger.info(f"Saving debug GLB file to: {glb_path}")
            self._save_debug_glb(tile, glb_path)

        logger.info("glTF creation complete")

    def create_b3dm(self):
        logger.info("Creating B3DM tile")
        tile = self._build_b3dm()
        if tile is None:
            return

        output_path = Path(self.save_to) / self.get_filename()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving B3DM tile to: {output_path}")

        if getattr(self, "debugCreateGLB", False):
            glb_path = output_path.with_suffix(".glb")
            logger.info(f"Saving debug GLB file to: {glb_path}")
            self._save_debug_glb(tile, glb_path)

        tile.save_as(output_path)
        logger.info("B3DM tile creation complete")

    @staticmethod
    def _save_debug_glb(tile, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tile.body.gltf.set_min_alignment(8)
        with open(path, "wb") as f:
            f.write(b"".join(tile.body.gltf.save_to_bytes()))

    def get_filename(self):
        return self.save_as + self.FILE_EXT
