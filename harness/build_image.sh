#!/usr/bin/env bash
# build_image.sh — Build task Docker image on top of a shared base image
#
# Two-layer strategy:
#   1. Build sciagent-bench:base once (common packages, Claude Code CLI)
#   2. Rewrite each task's Dockerfile FROM line to use the base, then build
#
# Usage:
#   ./build_image.sh <task-dir> <image-tag>

set -euo pipefail

TASK_DIR="$1"
IMAGE_TAG="$2"
DOCKERFILE="$TASK_DIR/environment/Dockerfile"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_IMAGE="${BASE_IMAGE_OVERRIDE:-sciagent-bench:base}"

if [ ! -f "$DOCKERFILE" ]; then
    echo "ERROR: Dockerfile not found: $DOCKERFILE"
    exit 1
fi

# Step 1: Build base image if it doesn't exist yet
if ! docker image inspect "${BASE_IMAGE}" &>/dev/null; then
    echo "[build] Building base image ${BASE_IMAGE}..."
    docker build -t "${BASE_IMAGE}" -f "${SCRIPT_DIR}/base/Dockerfile" "${SCRIPT_DIR}/base"
    echo "[build] Base image ready."
fi

# Step 2: Rewrite the task Dockerfile to use the base image
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

python3 - "${DOCKERFILE}" "${TMP_DIR}/Dockerfile" "${BASE_IMAGE}" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
base = sys.argv[3]

lines = src.read_text(encoding="utf-8").splitlines()
new_lines = []
replaced = False
for line in lines:
    if not replaced and line.strip().upper().startswith("FROM"):
        new_lines.append(f"FROM {base}")
        replaced = True
    else:
        new_lines.append(line)
dst.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
PY

echo "[build] ${IMAGE_TAG} (from ${BASE_IMAGE})"
docker build -t "${IMAGE_TAG}" \
    -f "${TMP_DIR}/Dockerfile" \
    "${TASK_DIR}/environment/"
echo "[build] ${IMAGE_TAG} OK"
