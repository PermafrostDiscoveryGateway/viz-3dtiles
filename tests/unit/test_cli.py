import subprocess
import sys


def test_module_cli_composes_tileset_from_unrelated_directory(tmp_path):
    child = tmp_path / "child.json"
    child.write_text(
        '{"asset":{"version":"1.0"},"geometricError":1,"root":{"boundingVolume":{"region":[0,0,1,1,0,1]},"geometricError":1,"refine":"ADD","content":{"uri":"model.b3dm"}}}'
    )
    output = tmp_path / "root.json"

    completed = subprocess.run(
        [sys.executable, "-m", "pdg3dtiles", "compose-tileset", str(output), str(child)],
        check=True,
        capture_output=True,
        cwd=tmp_path,
        text=True,
    )

    assert completed.stdout.strip().endswith("root.json")
    assert output.is_file()


def test_module_cli_failure_returns_nonzero(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdg3dtiles",
            "compose-tileset",
            str(tmp_path / "root.json"),
            str(tmp_path / "missing.json"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
