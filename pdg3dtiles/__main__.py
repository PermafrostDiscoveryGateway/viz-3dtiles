"""Thin direct CLI: arguments call one function and print output paths."""

import argparse
import json
from pathlib import Path

from .operations import compose_tileset, convert_leaf


def _convert_leaf(args):
    """Run the convert-leaf subcommand and print the output paths.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments carrying the input path, the content and tileset
        output paths, and the conversion options (crs, z, bounding volume,
        geometric error, version, overwrite).

    Returns
    -------
    None
    """
    content, tileset = convert_leaf(
        args.input,
        args.content_output,
        args.tileset_output,
        crs=args.crs,
        z=args.z,
        bounding_volume=json.loads(args.bounding_volume) if args.bounding_volume else None,
        geometric_error=args.geometric_error,
        version=args.version,
        overwrite=args.overwrite,
    )
    print(content)
    print(tileset)


def _compose_tileset(args):
    """Run the compose-tileset subcommand and print the output path.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments carrying the child tileset files, the output
        path, and the overwrite flag.

    Returns
    -------
    None
    """
    print(compose_tileset(args.children, args.output, overwrite=args.overwrite))


def main(argv=None):
    """Parse CLI arguments and run one pdg3dtiles operation.

    Parameters
    ----------
    argv : list of str, optional
        Argument list (defaults to ``sys.argv``) with one of the
        convert-leaf or compose-tileset subcommands.

    Returns
    -------
    int
        0 on success; exits via ``parser.error`` on OSError or ValueError.
    """
    parser = argparse.ArgumentParser(description="Run one pdg3dtiles operation")
    sub = parser.add_subparsers(dest="operation", required=True)

    leaf = sub.add_parser("convert-leaf", help="Convert one staged vector to B3DM + tileset")
    leaf.add_argument("input", help="Staged vector file")
    leaf.add_argument("content_output", help="B3DM content output path")
    leaf.add_argument("tileset_output", help="Leaf tileset JSON output path")
    leaf.add_argument("--crs", default=None)
    leaf.add_argument("--z", type=float, default=None)
    leaf.add_argument("--bounding-volume", default=None, help="JSON bounding volume object")
    leaf.add_argument("--geometric-error", type=float, default=None)
    leaf.add_argument("--version", default=None)
    leaf.add_argument("--overwrite", action="store_true")

    compose = sub.add_parser("compose-tileset", help="Compose one tileset from child tilesets")
    compose.add_argument("output", help="Parent/root tileset output path")
    compose.add_argument("children", nargs="+", help="Child tileset files")
    compose.add_argument("--overwrite", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.operation == "convert-leaf":
            _convert_leaf(args)
        else:
            _compose_tileset(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
