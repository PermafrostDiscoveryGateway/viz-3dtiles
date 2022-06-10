# -*- coding: utf-8 -*-
import geopandas
from geopandas.geodataframe import GeoDataFrame
from shapely.geometry import Polygon, MultiPolygon
from py3dtiles import GlTF, TriangleSoup, B3dm, BatchTable
import numpy as np
import os
import uuid

class Cesium3DTile:
    CESIUM_EPSG = 4978
    FILE_EXT = ".b3dm"

    def __init__(self):
        self.geodataframe = GeoDataFrame()
        self.save_as = "model"
        self.save_to = os.path.dirname(os.path.abspath(__file__))+r"../" # base dir of repo
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
        self.batch_table_uuid=True
        self.batch_table_centroid=False
        self.batch_table_area=False

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

    def from_file(self, filepath, crs="EPSG:3413"):
        """
        Parameters
        ----------
        filepath : string
            The path to the file to convert
        """
        gdf : GeoDataFrame = geopandas.read_file(filepath)

        if gdf.crs == None:
            gdf = gdf.set_crs(crs)

        self.geodataframe = gdf

        #Filter out polygons as needed
        self.filter_polygons()

        if gdf.has_z.all() == False:
            self.add_z()

        self.to_epsg()
        self.tesselate()
        self.create_gltf()
        self.create_b3dm()
        return

    
    def from_geodataframe(self, gdf):
        self.geodataframe = gdf

        #Filter out polygons as needed
        self.filter_polygons()

        if gdf.has_z.all() == False:
            self.add_z()

        self.to_epsg()
        self.tesselate()
        self.create_gltf()
        self.create_b3dm()
    
    def filter_polygons(self):
        #Filter out polygons beyond the maximum
        if self.max_features is not None:
            self.geodataframe = self.geodataframe[0:self.max_features]

        #Filter polygons with a certain attribute
        for key, value in self.filter_by_attributes.items():
            try: 
                self.geodataframe = self.geodataframe[self.geodataframe[key] == value]
            except:
                print("Not filtering out polygons for attribute " + key);

    def add_z(self, z=5.2):
        """
            Add a z-coordinate to the (2D) geodataframe.

            Parameters
            ----------
            z : float
                The z-coordinate to add to the geodataframe (height in meters).
        """
        self.geodataframe['geometry'] = self.geodataframe['geometry'].apply(
            lambda poly: Polygon([(x, y, z) for x, y in poly.exterior.coords]))

    def to_epsg(self, epsg=CESIUM_EPSG):
        self.geodataframe = self.geodataframe.to_crs(epsg=epsg)

    def tesselate(self):
        min_tileset_z=9e99
        max_tileset_z=-9e99
        max_width=-9e99
        row = 0
        for feature in self.geodataframe.iterfeatures():

            # print(f"Processing {row + 1} of {len(self.geodataframe)} in EPSG", self.CESIUM_EPSG)

            # Create a multipolygon for only this polygon feature
            polygon=Polygon(feature["geometry"]["coordinates"][0])
            multipolygon = MultiPolygon([polygon])

            # use the TriangleSoup helper class to transform the wkb into arrays of points and normals
            # print(f"Tesselating polygon to generate position and normal arrays")
            ts = TriangleSoup.from_wkb_multipolygon(multipolygon.wkb)
            positions = ts.getPositionArray()
            normals = ts.getNormalArray()

            # Calculate the bounding box 
            # First get the z values since shapely bounds function does not support 3D geom/z values)
            z = [z for (x,y,z) in feature["geometry"]["coordinates"][0]]
            minz=min(z)
            maxz=max(z)
            box_degrees = [ [multipolygon.bounds[2], multipolygon.bounds[3], maxz],
                            [multipolygon.bounds[0], multipolygon.bounds[1], minz] ]

            # Cache the min and max z values for fast retrieval later
            if minz < min_tileset_z:
                min_tileset_z=minz
            if maxz > max_tileset_z:
                max_tileset_z=maxz
            
            if polygon.length > max_width:
                max_width = polygon.length

            # generate the glTF part from the binary arrays.
            self.geometries.append({ 'position': positions, 'normal': normals, 'bbox': box_degrees})

            self.max_width = max_width
            self.max_tileset_z = max_tileset_z
            self.min_tileset_z = min_tileset_z

            row += 1

    def create_gltf(self):

        transform = np.array(
            [[
                1.0, 0.0,  0.0, 0.0,
                0.0, 0.0, -1.0, 0.0,
                0.0, 1.0,  0.0, 0.0,
                0.0, 0.0,  0.0, 1.0
            ]], dtype=float)

        transform = transform.flatten('F')

        # print("creating glTF")
        gltf = GlTF.from_binary_arrays(self.geometries, transform=transform, batched=True)

        if self.debugCreateGLB == True:
            with open(self.save_to + self.save_as + ".glb", "bw") as f:
                f.write(bytes(gltf.to_array()))
        
        self.gltf = gltf

    def create_batch_table(self):
        # print("Creating Batch table")

        bt = BatchTable()

        if self.batch_table_uuid == True:
            values=[]
            for i in range(0, len(self.geodataframe)):
                u=uuid.uuid4()
                values.append(u.urn)
            self.geodataframe["uuid"] = values

        attributes = self.geodataframe.columns.drop("geometry")

        for attr in attributes:
            # print("Adding " + attr)
            values=[]
            for v in self.geodataframe[attr].values:
                values.append(str(v))
            bt.header.add_property_from_array(propertyName=attr, array=values)

        self.batch_table = bt

        return bt



            
    def create_b3dm(self):

        # --- Convert to b3dm -----
        # create a b3dm tile_content directly from the glTF.
        # print("Creating b3dm file")
        t = B3dm.from_glTF(self.gltf, bt=self.create_batch_table())

        # to save our tile as a .b3dm file
        t.save_as(self.save_to+ self.get_filename())

    def get_filename(self):
        return self.save_as + self.FILE_EXT