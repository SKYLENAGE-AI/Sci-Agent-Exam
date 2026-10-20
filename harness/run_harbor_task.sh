#!/usr/bin/env bash
# run_harbor_task.sh — run a single benchmark task through `harbor`.
# Dataset = ./tasks; model traffic is routed through an OpenAI/Anthropic-compatible
# LLM proxy (configured via env vars below). Environment-build timeout is enlarged
# because each task builds its own scientific Docker image.
#
# Usage:  bash run_harbor_task.sh <task-slug|domain/slug> <agent> [model] [extra harbor args...]
# e.g.:   bash run_harbor_task.sh bioinformatics-error-diagnosis-01 claude-code <model> --ak reasoning_effort=high
#         bash run_harbor_task.sh physics-simulation-tool-orchestration-01 oracle
# Tasks live under tasks/<domain>/<slug>/; the bare <slug> is resolved to its domain.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"       # repo root (contains ./tasks)
TASKS_DIR="$REPO_ROOT/tasks"

TASK="${1:?usage: run_harbor_task.sh <task-slug> <agent> [model] [harbor args...]}"
AGENT="${2:?need agent}"
shift 2
CLI_MODEL=""
if [ "$#" -gt 0 ] && [[ "$1" != -* ]]; then CLI_MODEL="$1"; shift; fi

# Resolve the task: accept either "<domain>/<slug>" or a bare "<slug>" (one level deep).
if [ ! -d "$TASKS_DIR/$TASK" ]; then
  MATCHES=("$TASKS_DIR"/*/"$TASK")
  if [ -d "${MATCHES[0]}" ]; then
    TASK="$(basename "$(dirname "${MATCHES[0]}")")/$TASK"
  else
    echo "ERROR: no task dir for '$TASK' under $TASKS_DIR (looked for tasks/$TASK and tasks/*/$TASK)" >&2
    exit 2
  fi
fi

# ---- LLM proxy credentials ----
# Point these at any OpenAI/Anthropic-compatible gateway (or the vendor APIs directly).
export LITELLM_PROXY_API_BASE="${LITELLM_PROXY_API_BASE:?set LITELLM_PROXY_API_BASE (LLM proxy base URL)}"
export LITELLM_PROXY_API_KEY="${LITELLM_PROXY_API_KEY:?set LITELLM_PROXY_API_KEY}"
# Both the agent (claude-code / Anthropic protocol) and the verifier
# (tests/llm_judge.py, Anthropic SDK) route through the same proxy.
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-$LITELLM_PROXY_API_BASE}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$LITELLM_PROXY_API_KEY}"

# ---- harbor version pin (0.20.0) ----
if ! harbor --version 2>/dev/null | grep -q '0\.20\.0'; then
  echo "ERROR: harbor is not 0.20.0 (found $(harbor --version 2>/dev/null))." >&2
  exit 2
fi

MODEL="${CLI_MODEL:-${MODEL:-}}"
if [ -z "$MODEL" ] && [ "$AGENT" != "oracle" ]; then
  echo "ERROR: a model is required for non-oracle agents." >&2; exit 2
fi

# ---- shared base image ----
# Task environment Dockerfiles do `FROM sciagent-bench:base`. Build it once from
# harness/base/Dockerfile if it is not present yet.
BASE_IMAGE="${BASE_IMAGE_OVERRIDE:-sciagent-bench:base}"
if ! docker image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
  echo "[run_harbor_task] building shared base image $BASE_IMAGE ..."
  docker build -t "$BASE_IMAGE" "$SCRIPT_DIR/base"
fi

OUTPUT_DIR="${OUTPUT_DIR:-$SCRIPT_DIR/harbor_jobs}"
JOB_NAME="${JOB_NAME:-$TASK-$(date +%s)-$$}"
BUILD_MULT="${BUILD_MULT:-5}"        # environment-build timeout multiplier
TO_MULT="${TO_MULT:-2}"

ARGS=(-y -p "tasks/$TASK" -o "$OUTPUT_DIR" --job-name "$JOB_NAME" --no-delete
      --environment-build-timeout-multiplier "$BUILD_MULT" --timeout-multiplier "$TO_MULT")
[ -n "$MODEL" ] && ARGS+=(-m "$MODEL")

cd "$REPO_ROOT"
echo "[run_harbor_task] task=$TASK agent=$AGENT model=${MODEL:-<oracle>} judge=$(grep -m1 '^JUDGE_MODEL' "$TASKS_DIR/$TASK/tests/llm_judge.py" 2>/dev/null | sed 's/.*= *//')"
exec harbor run "${ARGS[@]}" -a "$AGENT" "$@"
