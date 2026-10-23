"""Explicit conversions between staged vectors and Cesium 3D Tiles.

Ordinary functions over explicit file paths: each function writes exactly
the paths it is given and raises on failure.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import geopandas

from .TreeGenerator import leaf_tile_from_gdf, parent_tile_from_children_json


def _require_overwrite(paths, overwrite):
    """Refuse to replace existing outputs unless overwriting is allowed.

    Parameters
    ----------
    paths : iterable of pathlib.Path
        Output paths to check.
    overwrite : bool
        When True, existing files may be replaced.

    Raises
    ------
    FileExistsError
        Naming the first path that already exists.
    """
    for path in paths:
        if path.exists() and not overwrite:
            raise FileExistsError(f"Output already exists: {path}")


def convert_leaf(
    input_path,
    content_output,
    tileset_output,
    *,
    crs=None,
    z=None,
    bounding_volume=None,
    geometric_error=None,
    version=None,
    overwrite=False,
):
    """Convert one staged vector file to B3DM content plus a leaf tileset.

    Both files are generated and validated in a temporary directory, the
    tileset content URI is written relative to the final tileset location,
    and then both are placed. On failure no new output is left behind, and
    outputs that existed before the call (``overwrite=True``) are untouched.

    Parameters
    ----------
    input_path : str or pathlib.Path
        Staged vector file to convert.
    content_output : str or pathlib.Path
        B3DM content output path.
    tileset_output : str or pathlib.Path
        Leaf tileset JSON output path.
    crs : optional
        Coordinate reference system for the input when needed.
    z : float, optional
        Height coordinate used for the leaf tile.
    bounding_volume : optional
        Explicit bounding volume forwarded to the tile generator.
    geometric_error : float, optional
        Geometric error written into the leaf tileset.
    version : optional
        Tileset version written into the leaf tileset.
    overwrite : bool, default False
        When True, replace existing outputs; otherwise reuse is an error.

    Returns
    -------
    tuple of pathlib.Path
        ``(content_path, tileset_path)`` of the placed outputs.

    Raises
    ------
    FileExistsError
        If an output already exists and ``overwrite`` is False.
    ValueError
        If the conversion produces no content.
    """
    content = Path(content_output)
    tileset_path = Path(tileset_output)
    _require_overwrite((content, tileset_path), overwrite)
    preexisting = {path for path in (content, tileset_path) if path.exists()}
    for path in (content, tileset_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(
        tempfile.mkdtemp(prefix=f".{tileset_path.name}.", dir=tileset_path.parent)
    )
    try:
        _, tileset = leaf_tile_from_gdf(
            geopandas.read_file(input_path),
            dir=temp_dir,
            filename=content.stem,
            crs=crs,
            z=z,
            boundingVolume=bounding_volume,
            geometricError=geometric_error,
            tilesetVersion=version,
        )
        content_temp = temp_dir / content.name
        if not content_temp.is_file() or content_temp.stat().st_size == 0:
            raise ValueError("Leaf conversion did not create content")
        tileset.root.content.uri = os.path.relpath(content, tileset_path.parent)
        tileset_temp = temp_dir / f"{content.stem}.json"
        tileset.to_file(tileset_temp)
        json.loads(tileset_temp.read_text())
        content_temp.replace(content)
        tileset_temp.replace(tileset_path)
        return (content, tileset_path)
    except Exception:
        for path in (content, tileset_path):
            if path not in preexisting:
                path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _compose(child_paths, output_path, overwrite, **options):
    """Compose one parent tileset from explicit child tileset files.

    Parameters
    ----------
    child_paths : list of str or pathlib.Path
        Child tileset files to compose; must all exist.
    output_path : str or pathlib.Path
        Parent tileset file to write.
    overwrite : bool
        When True, replace an existing output.
    **options
        Passed to the underlying generator (for example geometricError,
        tilesetVersion, boundingVolume).

    Returns
    -------
    pathlib.Path
        The written parent tileset path.

    Raises
    ------
    ValueError
        When the child list is empty, a child is not a file, or no output
        was created.
    """
    children = tuple(Path(path) for path in child_paths)
    if not children or any(not path.is_file() for path in children):
        raise ValueError("child_paths must be an explicit list of tileset files")
    output = Path(output_path)
    _require_overwrite((output,), overwrite)
    output.parent.mkdir(parents=True, exist_ok=True)
    # The generator always writes ``<filename>.json``, so the temp name must too.
    temporary = output.with_name(f".{output.name}.tmp.json")
    try:
        parent_tile_from_children_json(
            [str(path) for path in children],
            dir=str(output.parent),
            filename=temporary.stem,
            **options,
        )
        if not temporary.is_file():
            raise ValueError("Tileset composition did not create an output")
        json.loads(temporary.read_text())
        temporary.replace(output)
        return output
    finally:
        temporary.unlink(missing_ok=True)


def compose_tileset(child_tilesets, output_path, *, overwrite=False, **options):
    """Compose one tileset from an explicit list of child tileset files.

    Parameters
    ----------
    child_tilesets : list of str or pathlib.Path
        Child tileset files to compose; must all exist.
    output_path : str or pathlib.Path
        Tileset file to write.
    overwrite : bool, default False
        When True, replace an existing output.
    **options
        Passed to the underlying generator (for example geometricError,
        tilesetVersion, boundingVolume, boundingVolumeSource).

    Returns
    -------
    pathlib.Path
        The written tileset path.
    """
    return _compose(child_tilesets, output_path, overwrite, **options)


def compose_parent(child_paths, output_path, *, overwrite=False, **options):
    """Thin alias of compose_tileset for existing callers.

    Parameters
    ----------
    child_paths : list of str or pathlib.Path
        Child tileset files to compose.
    output_path : str or pathlib.Path
        Tileset file to write.
    overwrite : bool, default False
        When True, replace an existing output.
    **options
        Passed through to ``compose_tileset``.

    Returns
    -------
    pathlib.Path
        The written tileset path.
    """
    return compose_tileset(child_paths, output_path, overwrite=overwrite, **options)


def compose_root(child_paths, output_path, *, overwrite=False, **options):
    """Thin alias of compose_tileset for existing callers.

    Parameters
    ----------
    child_paths : list of str or pathlib.Path
        Child tileset files to compose.
    output_path : str or pathlib.Path
        Tileset file to write.
    overwrite : bool, default False
        When True, replace an existing output.
    **options
        Passed through to ``compose_tileset``.

    Returns
    -------
    pathlib.Path
        The written tileset path.
    """
    return compose_tileset(child_paths, output_path, overwrite=overwrite, **options)
