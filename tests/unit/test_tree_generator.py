import json
import math

from pdg3dtiles import parent_tile_from_children_json


def test_parent_default_geometric_error_uses_child_error_not_region_size(tmp_path):
    """Parent geometric error defaults to max child error, not region size."""
    broad_region = {
        "region": [-math.pi, -math.pi / 2, 0.0, math.pi / 2, -1.0, 1.0]
    }
    child_paths = []

    for index, geometric_error in enumerate((10.0, 20.0)):
        child_path = tmp_path / f"child-{index}.json"
        child_path.write_text(
            json.dumps(
                {
                    "asset": {"version": "1.0"},
                    "geometricError": geometric_error,
                    "root": {
                        "boundingVolume": broad_region,
                        "geometricError": geometric_error,
                        "refine": "ADD",
                    },
                }
            )
        )
        child_paths.append(str(child_path))

    parent = parent_tile_from_children_json(
        children=child_paths,
        dir=str(tmp_path),
        filename="parent",
        boundingVolume=broad_region,
    )

    assert parent.geometricError == 20.0
    assert parent.root.geometricError == 20.0
