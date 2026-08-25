"""CLI entry point for the local movie CSV importer."""

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "movies.py"), run_name="__main__")
