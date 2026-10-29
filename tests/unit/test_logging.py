import subprocess
import sys


def test_import_does_not_install_root_logging_handler():
    code = "import logging; before = len(logging.getLogger().handlers); import pdg3dtiles; assert len(logging.getLogger().handlers) == before"
    subprocess.run([sys.executable, "-c", code], check=True)
