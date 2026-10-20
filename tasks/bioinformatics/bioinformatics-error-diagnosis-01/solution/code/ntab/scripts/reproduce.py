#!/usr/bin/env python3
"""Run the mounted public replay without installing the project."""

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from ntab_preprocess.offline_replay import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

