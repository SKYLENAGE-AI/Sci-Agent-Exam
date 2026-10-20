"""Deterministic oracle for the versioned-result interpretation task."""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path


SOLUTION_DIR = Path(__file__).resolve().parent
LOCAL_DATA = SOLUTION_DIR.parent / "environment" / "data"
DATA_DIR = Path("/home/agent/data") if Path("/home/agent/data").exists() else LOCAL_DATA
SOURCE_CODE = SOLUTION_DIR / "code" / "interpret_cycle.py"


def load_analysis_module():
    spec = importlib.util.spec_from_file_location("interpret_cycle", SOURCE_CODE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load interpretation module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else SOLUTION_DIR
    results.mkdir(parents=True, exist_ok=True)
    code_dir = results / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    destination_code = code_dir / "interpret_cycle.py"
    if SOURCE_CODE.resolve() != destination_code.resolve():
        shutil.copyfile(SOURCE_CODE, destination_code)
    load_analysis_module().analyze(DATA_DIR, results)


if __name__ == "__main__":
    main()
