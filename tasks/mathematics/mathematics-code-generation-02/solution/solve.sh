#!/usr/bin/env bash
# Canonical reference-solution runner. Do not hard-code paths to solve.py.
#
# The QC/prod harness invokes this script with no arguments, with the solution
# mounted at /home/agent/solution and a writable output directory at
# /home/agent/results. The optional first argument is useful when regenerating
# golden artifacts into a different directory.
set -euo pipefail

# Keep Python bytecode and numba caches out of a read-only solution mount.
export PYTHONDONTWRITEBYTECODE=1
export NUMBA_CACHE_DIR="${TMPDIR:-/tmp}/numba_cache"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
RESULTS="${1:-/home/agent/results}"
mkdir -p "$RESULTS"
python3 "$HERE/solve.py" "$RESULTS"
