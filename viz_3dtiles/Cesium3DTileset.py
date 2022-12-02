import json
from .BoundingVolume import BoundingVolume
from .Cesium3DTile import Cesium3DTile
import os


class Base():
    """
    A base class to extend to create other Cesium 3D Tile classes. This class
    mainly deals with reading and writing to JSON files, and validating the
    object.

    Attributes
    ----------
    required_keys: list of str
        A list of keys that must be present in the JSON object for the object
        to be valid.
    type_definitions: dict
        A dictionary of keys and types that must be present in the JSON object
        for the object to be valid.
    """

    required_keys = []
    type_definitions = {}

    def __init__(self):
        pass

    def validate(self):
        """
        Validate this object. Raises a ValueError if the object is invalid.
        """

        cls_name = self.__class__.__name__

        # check that all required keys are present
        for key in self.required_keys:
            if key not in self.__dict__:
                raise ValueError(
                    f'The following required key is missing: {key} '
                    f'for class {cls_name}')

        # check that the types are correct
        for key, value in self.__dict__.items():
            if key in self.type_definitions:
                if value is not None:
                    # check that the value is one of the required types
                    req_types = self.type_definitions[key]
                    if not isinstance(req_types, list):
                        req_types = [req_types]
                    if not any([isinstance(value, req_type)
                               for req_type in req_types]):
                        raise ValueError(
                            f'{key} in the {cls_name} class must be of type '
                            f'type {req_types}, but is type {type(value)}')
            # check that there are no extra/invalid keys
            else:
                raise ValueError(
                    f'{key} is not a valid key for class {cls_name}')

    def copy(self):
        """
        Return a copy of the tileset.
        """
        json_str = json.dumps(self.to_dict())
        json_data = json.loads(json_str)
        return self.from_json(json_data)

    @staticmethod
    def parse_json(data=None):
        """
        Parse a JSON file before passing to the init method.

        Parameters
        ----------
        data: dict
            A dict read from a JSON file.

        Returns
        -------
        Returns the parsed dict.
        """
        return data

    @classmethod
    def from_json(cls, data):
        """
        Parse a JSON object into a Base object.

        Parameters
        ----------
        data : dict
            A dict read in from a JSON file.
        """
        data = cls.parse_json(data)
        return cls(**data)

    @classmethod
    def from_file(cls, path):
        """
        Read a JSON file into a Base object.
        """
        with open(path) as f:
            tileset = cls.from_json(json.load(f))
            tileset.file_path = path
            return tileset

    def __str__(self):
        return self.to_dict().__str__()

    def __repr__(self):
        return self.__str__()

    def to_json(self):
        """
        Convert this object to a JSON string.
        """
        # return json.dumps(self.to_dict(), indent=2)
        return self.to_dict()

    def to_dict(self):
        d = self.__dict__.copy()
        if 'file_path' in d:
            del d['file_path']
        none_keys = []
        for key, value in d.items():
            # if the value has a to_dict method, call it
            if hasattr(value, 'to_dict'):
                d[key] = value.to_dict()
            # if the value is None, remove it
            if value is None:
                none_keys.append(key)
        for key in none_keys:
            del d[key]

        return d

    def to_file(self, path, minify=True):
        """
        Write this object to a JSON file.

        Parameters
        ----------
        path: str
            Path to a JSON file.
        """
        separators = (',', ': ')
        indent = 2
        if minify:
            separators = (',', ':')
            indent = None

        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, separators=separators, indent=indent)
            self.file_path = path


class Asset(Base):
    """
        Metadata about the entire tileset, like the 3D Tile version and
        application version. A class that represents the schema defined at
        https://github.com/CesiumGS/3d-tiles/blob/main/specification/schema/asset.schema.json

        Attributes
        ----------
        version: str
            The 3D Tiles version. The version defines the JSON schema for the
            tileset JSON and the base set of tile formats.

        tilesetVersion: str
            Application-specific version of this tileset, e.g., for when an
            existing tileset is updated.

        extensions: dict
            Dictionary object with extension-specific objects.

        extras: dict
            Application-specific data.
    """

    required_keys = ['version']

    type_definitions = {
        'version': str,
        'tilesetVersion': str,
        'extensions': dict,
        'extras': dict,
    }

    def __init__(
            self,
            version='1.0',
            tilesetVersion=None,
            extensions=None,
            extras=None):
        self.version = version
        self.tilesetVersion = tilesetVersion
        self.extensions = extensions
        self.extras = extras


class Content(Base):
    """
    A class that represents a Cesium 3D Tile Content object. This object is
    used to define the content of a Cesium 3D Tile and is based on the schema
    that is defined at
    https://github.com/CesiumGS/3d-tiles/blob/main/specification/schema/content.schema.json

    Attributes
    ----------

    boundingVolume: BoundingVolume
            An optional bounding volume that tightly encloses tile content.
            tile.boundingVolume provides spatial coherence and
            tile.content.boundingVolume enables tight view frustum culling.
            When this is omitted, tile.boundingVolume is used.

    uri: string
        A uri that points to tile content. When the uri is relative, it is
        relative to the referring tileset JSON file.

    extensions: dict
        Dictionary object with extension-specific objects.

    extras: dict
       Application-specific data.

    """

    required_keys = ['uri']

    type_definitions = {
        'boundingVolume': BoundingVolume,
        'uri': str,
        'extensions': dict,
        'extras': dict,
    }

    def __init__(self,
                 boundingVolume=None,
                 uri=None,
                 extensions=None,
                 extras=None
                 ):
        """
        Initialize a Content object.
        """
        if boundingVolume:
            if isinstance(boundingVolume, (list, dict)):
                boundingVolume = BoundingVolume(boundingVolume)
            if not isinstance(boundingVolume, BoundingVolume):
                raise ValueError(
                    'boundingVolume must be a BoundingVolume object')

        self.boundingVolume = boundingVolume
        self.uri = uri
        self.extensions = extensions
        self.extras = extras

        self.validate()

    @classmethod
    def from_b3dm(cls, b3dm):
        # Get the bounding volume from the b3dm file
        boundingVolume = BoundingVolume.from_b3dm(b3dm)
        # Get URI
        uri = b3dm.get_uri()
        return cls(boundingVolume, uri)

    @staticmethod
    def make_relative_uri(uri, base_uri):
        pass


class Tile(Base):

    required_keys = ['boundingVolume', 'geometricError']

    type_definitions = {
        'boundingVolume': BoundingVolume,
        'viewerRequestVolume': BoundingVolume,
        'geometricError': [float, int],
        'refine': str,
        'transform': list,
        'content': Content,
        'children': list,
        'extensions': dict,
        'extras': dict
    }

    # The allowed options for the refine property. The first option is the
    # default, and will not be serialized to JSON.
    refine_opts = ['ADD', 'REPLACE']

    def __init__(
        self,
        boundingVolume=[-180, -90, 180, 90, 0, 0],
        viewerRequestVolume=None,
        geometricError=0,
        refine='ADD',
        transform=None,
        content=None,
        children=None,
        extensions=None,
        extras=None
    ):
        """
        Parameters
        ----------
        boundingVolume : BoundingVolume or list
            The bounding volume that encloses the tile.

        viewerRequestVolume : BoundingVolume or list
            Optional bounding volume that defines the volume the viewer must be
            inside of before the tile's content will be requested and before
            the tile will be refined based on geometricError.

        geometricError : float or int
            The error, in meters, introduced if this tile is rendered and its
            children are not. At runtime, the geometric error is used to
            compute screen space error (SSE), i.e., the error measured in
            pixels.

        refine : "ADD" or "REPLACE"
            Specifies if additive or replacement refinement is used when
            traversing the tileset for rendering. This property is required for
            the root tile of a tileset; it is optional for all other tiles. The
            default is to inherit from the parent tile.

        transform : list
            A floating-point 4x4 affine transformation matrix, stored in
            column-major order, that transforms the tile's content--i.e., its
            features as well as content.boundingVolume, boundingVolume, and
            viewerRequestVolume--from the tile's local coordinate system to the
            parent tile's coordinate system, or, in the case of a root tile,
            from the tile's local coordinate system to the tileset's coordinate
            system. `transform` does not apply to any volume property when the
            volume is a region, defined in EPSG:4979 coordinates. `transform`
            scales the `geometricError` by the maximum scaling factor from the
            matrix.

        content : Content or dict
            Metadata about the tile's content and a link to the content. When
            this is omitted the tile is just used for culling.

        children : list of Tile or dict
            An array of objects that define child tiles. Each child tile
            content is fully enclosed by its parent tile's bounding volume and,
            generally, has a geometricError less than its parent tile's
            geometricError. For leaf tiles, the length of this array is zero,
            and children may not be defined.

        extensions : dict
            Dictionary object with extension-specific objects.

        extras : dict
            Application-specific data.

        """

        if content:
            if isinstance(content, dict):
                content = Content(**content)
            if not isinstance(content, Content):
                raise ValueError('content must be a Content object')

        if boundingVolume:
            if isinstance(boundingVolume, list):
                boundingVolume = BoundingVolume(boundingVolume)
            if isinstance(boundingVolume, dict):
                boundingVolume = BoundingVolume.from_json(boundingVolume)
            if not isinstance(boundingVolume, BoundingVolume):
                raise ValueError(
                    'boundingVolume must be a BoundingVolume object')

        if viewerRequestVolume:
            if isinstance(viewerRequestVolume, list):
                viewerRequestVolume = BoundingVolume(viewerRequestVolume)
            if isinstance(viewerRequestVolume, dict):
                viewerRequestVolume = BoundingVolume.from_json(
                    viewerRequestVolume)
            if not isinstance(viewerRequestVolume, BoundingVolume):
                raise ValueError(
                    'viewerRequestVolume must be a BoundingVolume object')

        if children:
            if not isinstance(children, list):
                raise ValueError('children must be a list')
            for i in range(len(children)):
                child = children[i]
                if isinstance(child, dict):
                    children[i] = Tile(**child)
                if not isinstance(children[i], Tile):
                    raise ValueError('children must be a list of Tile objects')

        self.boundingVolume = boundingVolume
        self.viewerRequestVolume = viewerRequestVolume
        self.geometricError = geometricError
        self.refine = refine
        self.transform = transform
        self.content = content
        self.children = children
        self.extensions = extensions
        self.extras = extras

        self.validate()

    def validate(self):
        """
        Validate the tile.
        """
        super().validate()
        if self.refine not in self.refine_opts:
            raise ValueError(
                'refine must be one of the following: {}'.format(
                    self.refine_opts))
        # Check if transform is a list of 16 floats
        if self.transform:
            if len(self.transform) != 16:
                raise ValueError('transform must be a list of 16 floats')
            for i in range(16):
                if not isinstance(self.transform[i], float):
                    raise ValueError('transform must be a list of 16 floats')
        # Validate content
        if self.content:
            self.content.validate()

        # TODO: ensure that root tile BoundingVolume completely encloses the
        # content BoundingVolume

        # Validate children
        if self.children:
            for child in self.children:
                if not isinstance(child, Tile):
                    raise ValueError('children must be a list of Tile objects')
                child.validate()

    def to_dict(self):
        """
        Convert the tile to a JSON object.
        """
        data = super().to_dict()
        if self.children:
            data['children'] = [child.to_dict() for child in self.children]
        # If the refine value is default, remove it
        if data['refine'] and data['refine'] == self.refine_opts[0]:
            del data['refine']
        return data

    def add_children(self, children, bv_method=None, bv_source='content'):
        """
        Add children to the tile and optionally update the tile's root bounding
        volume. The content bounding volume is not updated.

        Parameters
        ----------
        children : list of Tile or dict
            An array of objects that define child tiles.
        bv_method : None or "update" or "replace"
            How to update the current tile's root bounding volume as children
            are added. If None (default), the bounding volume is not changed.
            If "update", the children bounding volumes are added to the tile's
            bounding volume. If "replace", the children's combined bounding
            volumes replace the tile's current bounding volume. Note that
            bounding volumes must all be of the same type to be added (i.e.,
            all must be either 'box' or 'region').
        bv_source: "root" or "content"
            When updating the current tile's root bounding volume (when
            bv_method is set to "update" or "replace"), should this method add
            the children's *root* bounding volumes, or the children's *content*
            bounding volumes (if they exist)? If set to "content" (default),
            then the method will first search for a child's content bounding
            volume, and will add it to the tile's root bounding volume if they
            exist. If a child has no content bounding volume, then the root
            bounding volume will be added instead.
        """

        new_bv = None
        if bv_method == 'update':
            new_bv = self.boundingVolume

        if not isinstance(children, list):
            raise ValueError('children must be a list')
        for i in range(len(children)):
            child = children[i]
            if isinstance(child, dict):
                children[i] = Tile(**child)
                child = children[i]
            if not isinstance(child, Tile):
                raise ValueError('children must be a list of Tile objects')
            if bv_method is not None:
                child_content = child.content
                child_bv = None
                if child_content:
                    child_bv = child_content.boundingVolume
                if bv_source == "root" or child_bv is None:
                    child_bv = child.boundingVolume
                if child_bv:
                    if new_bv is None:
                        new_bv = child_bv
                    else:
                        new_bv = new_bv.add(child_bv)

        if self.children is None:
            self.children = []
        self.children.extend(children)

        if new_bv is not None:
            self.boundingVolume = new_bv

    def add_content(self, content):
        """
        Add content to the tile. This will replace the existing content.

        Parameters
        ----------
        content : Content or dict
            content to add to the tile.
        """

        if isinstance(content, dict):
            content = Content(**content)
        if not isinstance(content, Content):
            raise ValueError('content must be a Content object')

        self.content = content


class Tileset(Base):
    """
    A class that represents a Cesium 3D Tile Set object. This object is used to
    define the content of a Cesium 3D Tile and is based on the schema that is
    defined at
    https://github.com/CesiumGS/3d-tiles/blob/main/specification/schema/tileset.schema.json

    Attributes
    ----------

        asset: Asset
            Metadata about the entire tileset. A dict that comprises the version
            and tileset version.

        properties: dict
            A dictionary object of metadata about per-feature properties.

        geometricError: float
            The error, in meters, introduced if this tileset is not rendered. At runtime, the geometric error is used to compute screen space error (SSE), i.e., the error measured in pixels.

        root: Tile
            The root tile of the tileset.
    """

    required_keys = ['asset', 'geometricError', 'root']

    type_definitions = {
        'asset': Asset,
        'properties': dict,
        'geometricError': [float, int],
        'root': Tile,
        'extensionsUsed': list,
        'extensionsRequired': list
    }

    def __init__(
        self,
        asset={'version': '1.0'},
        properties=None,
        geometricError=0,
        root=None,
        extensionsUsed=None,
        extensionsRequired=None,
    ):
        """
        Initialize a Tileset object.

        Parameters
        ----------
        """

        if isinstance(asset, dict):
            asset = Asset(**asset)
        if not isinstance(asset, Asset):
            raise ValueError('asset must be a Asset object')

        if root:
            if isinstance(root, dict):
                root = Tile(**root)
            if not isinstance(root, Tile):
                raise ValueError('root must be a Tile object')
        else:
            root = Tile()

        self.asset = asset
        self.geometricError = geometricError
        self.properties = properties
        self.root = root
        self.extensionsUsed = extensionsUsed
        self.extensionsRequired = extensionsRequired

    def add_children(self, children, bv_method=None, bv_source="content"):
        """
        Add children to the root of the tileset.

        Parameters
        ----------
        children : list of Tile or dict
            An array of objects that define child tiles.
        bv_method : None or "update" or "replace"
            How to update the tileset's bounding volume as children are added.
            If None, the bounding volume is not changed. If "update", the
            children bounding volumes are added to the tileset's bounding volume.
            If "replace", the children's combined bounding volumes replace the
            tileset's current bounding volume. Note that bounding volumes must all
            be of the same type to be added (i.e., all must be either 'box' or
            'region').
        bv_source: "root" or "content"
            When updating the current tile's root bounding volume, should this
            method add the children's root bounding volumes, or the children's
            content bounding volumes (if they exist)? If set to "content"
            (default), then the method will first search for content bounding
            volumes in the children, and will add those to the tile's root
            bounding volume. If a child has no content bounding volume, then
            the root bounding volume will be added instead.
        """
        # The root is a Tile object
        self.root.add_children(children, bv_method, bv_source)

    def add_content(self, content, bv=None):
        """
        Add content to the root of the tileset.

        Parameters
        ----------
        content : Content or dict
            An object or dict that gives the uri plus optional metadata about
            the content (e.g. b3dm or another tileset) of this tileset
        """
        self.root.add_content(content, bv)

    @classmethod
    def from_Cesium3DTiles(cls, tiles, file_path='tileset.json'):
        """
        Create a Tileset object from a list of 1 or more Cesium3DTiles objects,
        and write it to a file.

        Parameters
        ----------
        tiles : Cesium3DTile or list of Cesium3DTile
            A single Cesium3DTile or list of Cesium3DTile objects.
        file_path : str
            The path to the tileset file to write. If the save_to path in the
            Cesium3DTiles is relative, then the file_path must also be relative.
            If the save_to paths are absolute, then the file_path must be absolute.
            This is because the file_path is compared to the tile.save_to paths
            to create a relative path from the tileset JSON.

        Returns
        -------
        Tileset
            A Tileset object.
        """

        if not isinstance(tiles, list):
            tiles = [tiles]
        if not all(isinstance(t, Cesium3DTile) for t in tiles):
            raise ValueError('tiles must be a list of Cesium3DTile objects')

        
        ge = 0
        tile_objs = []

        for t in tiles:
            ge =+ t.max_width
            tile_bv = BoundingVolume.from_z_polygons(t.transformed_geometries)
            uri = os.path.join(t.save_to, t.get_filename())
            uri = os.path.relpath(uri, os.path.dirname(file_path))
            tile_obj = Tile(
                boundingVolume=tile_bv,
                geometricError=t.max_width,
                content=Content(
                    uri=uri
                )
            )
            tile_objs.append(tile_obj)

        if len(tile_objs) == 1:
            root = tile_objs[0]
        else:
            root = Tile(
                geometricError=ge
            )
            root.add_children(tile_objs, bv_method="replace", bv_source="root")

        ts = cls(
            geometricError = ge,
            root = root
        )

        ts.to_file(file_path)

        return ts