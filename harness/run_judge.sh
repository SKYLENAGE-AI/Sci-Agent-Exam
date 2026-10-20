#!/usr/bin/env bash
# run_judge.sh — Docker-based QC judge workflow
#
# Evaluates the golden reference solution (from solution/) using the task's
# test.sh pipeline (check_programmatic.py + llm_judge.py). This is the QC
# quality check flow: it confirms the grading pipeline works on a known-good
# solution.
#
# Usage:
#   ./run_judge.sh <task-name> [--all]
#
# Examples:
#   ./run_judge.sh bioinformatics-code-generation-03
#   ./run_judge.sh --all                               # run all 100 tasks
#
# The script:
#   1. Builds the Docker image from the task's environment/Dockerfile
#   2. Copies the golden solution into the expected /home/agent/results/ path
#   3. Runs test.sh (programmatic + LLM judge)
#   4. Extracts the reward score from /logs/verifier/reward.txt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
TASKS_DIR="$WORKSPACE/tasks"
HARNESS_DIR="$SCRIPT_DIR"
OUTPUT_BASE="$WORKSPACE/outputs/judge"

# Load .env
if [ -f "$WORKSPACE/.env" ]; then
    set -a
    source "$WORKSPACE/.env"
    set +a
fi

usage() {
    echo "Usage: $0 <task-name> [--all]"
    echo "  <task-name>    Name of a task directory under tasks/"
    echo "  --all          Run judge on all tasks"
    exit 1
}

CURRENT_IDX=0
TOTAL_TASKS=0

run_judge_for_task() {
    local TASK_NAME="$1"
    local TASK_DIR="$TASKS_DIR/$TASK_NAME"
    local OUTPUT_DIR="$OUTPUT_BASE/$TASK_NAME"

    if [ ! -d "$TASK_DIR" ]; then
        echo "ERROR: Task directory not found: $TASK_DIR"
        return 1
    fi

    CURRENT_IDX=$((CURRENT_IDX + 1))
    echo "============================================"
    echo "  [${CURRENT_IDX}/${TOTAL_TASKS}] QC Judge: $TASK_NAME"
    echo "============================================"

    mkdir -p "$OUTPUT_DIR"

    # Read task type from task.toml
    local TASK_TYPE
    TASK_TYPE=$(python3 -c "
import sys
for line in open('$TASK_DIR/task.toml'):
    if line.strip().startswith('task_type'):
        print(line.split('=')[1].strip().strip('\"'))
        break
" 2>/dev/null || echo "unknown")

    local IMAGE_TAG="sciagent-judge-${TASK_NAME}:latest"

    # Step 1: Build Docker image (with pip mirror for speed)
    echo "[1/4] Building Docker image..."
    bash "$HARNESS_DIR/build_image.sh" "$TASK_DIR" "$IMAGE_TAG" \
        > "$OUTPUT_DIR/docker-build.log" 2>&1 || {
        echo "  ERROR: Docker build failed. See $OUTPUT_DIR/docker-build.log"
        return 1
    }
    echo "  Image: $IMAGE_TAG"

    # Step 2: Prepare run — mount solution as results, tests, and harness adapter
    echo "[2/4] Preparing evaluation..."

    # Step 3: Run test.sh inside Docker
    echo "[3/4] Running judge pipeline (judge model: ${JUDGE_MODEL:-unset})..."

    # We mount:
    #  - solution/ -> /home/agent/solution/ (for solve.sh to copy into results)
    #  - tests/    -> /tests/               (test.sh, check_programmatic.py, llm_judge.py, rubric.json)
    #  - harness/  -> /harness/             (judge_adapter.py)
    #  - output/   -> /logs/verifier/       (reward.txt output)
    #
    # The flow: run solve.sh to populate /home/agent/results/, then run test.sh

    docker run --rm \
        -v "$TASK_DIR/solution:/home/agent/solution:ro" \
        -v "$TASK_DIR/tests:/tests:ro" \
        -v "$HARNESS_DIR:/harness:ro" \
        -v "$OUTPUT_DIR:/output" \
        -e "SCICODE_TASK_TYPE=$TASK_TYPE" \
        -e "JUDGE_API_KEY=${JUDGE_API_KEY:-}" \
        -e "JUDGE_BASE_URL=${JUDGE_BASE_URL:-}" \
        -e "JUDGE_MODEL=${JUDGE_MODEL:-}" \
        -e "ANTHROPIC_API_KEY=${JUDGE_API_KEY:-dummy}" \
        "$IMAGE_TAG" \
        bash -c '
            set -e
            # Step A: Run golden solution to populate /home/agent/results/
            echo "=== Running golden solution ==="
            mkdir -p /home/agent/results
            if [ -f /home/agent/solution/solve.sh ]; then
                bash /home/agent/solution/solve.sh /home/agent/results
            elif [ -f /home/agent/solution/solve.py ]; then
                python3 /home/agent/solution/solve.py /home/agent/results
            else
                echo "ERROR: No solve.sh or solve.py found"
                exit 1
            fi

            echo "=== Results produced: ==="
            find /home/agent/results -type f | head -20

            # Step B: Run programmatic check
            echo "=== Running programmatic check ==="
            mkdir -p /tmp/eval /logs/verifier
            echo "0.0" > /logs/verifier/reward.txt

            python3 /tests/check_programmatic.py \
                --output /home/agent/results/ \
                --result-file /tmp/eval/programmatic.json \
                > /logs/verifier/check_programmatic.log 2>&1 || true

            echo "Programmatic result:"
            cat /tmp/eval/programmatic.json 2>/dev/null || echo "{\"score\": 0.0}"

            # Step C: Run LLM judge (via adapter for internal API)
            echo "=== Running LLM judge ==="
            if [ -n "${JUDGE_BASE_URL:-}" ] && [ -n "${JUDGE_API_KEY:-}" ]; then
                python3 /harness/judge_adapter.py /tests/llm_judge.py \
                    --agent-output /home/agent/results/ \
                    --rubric /tests/rubric.json \
                    --result-file /tmp/eval/llm_judge.json \
                    > /logs/verifier/llm_judge.log 2>&1 || true
            else
                echo "WARN: JUDGE_BASE_URL/JUDGE_API_KEY not set, running native llm_judge.py"
                python3 /tests/llm_judge.py \
                    --agent-output /home/agent/results/ \
                    --rubric /tests/rubric.json \
                    --result-file /tmp/eval/llm_judge.json \
                    > /logs/verifier/llm_judge.log 2>&1 || true
            fi

            echo "LLM judge result:"
            cat /tmp/eval/llm_judge.json 2>/dev/null || echo "{\"score_fraction\": 0.0}"

            # Step D: Aggregate scores (reuse logic from test.sh)
            echo "=== Aggregating scores ==="
            python3 - <<PYEOF
import json, math, os
from pathlib import Path

prog = json.loads(Path("/tmp/eval/programmatic.json").read_text()) if Path("/tmp/eval/programmatic.json").exists() else {"score": 0.0}
llm = json.loads(Path("/tmp/eval/llm_judge.json").read_text()) if Path("/tmp/eval/llm_judge.json").exists() else {"score_fraction": 0.0}

SCORING_WEIGHTS = {
    "code_generation": (0.70, 0.30),
    "error_diagnosis": (0.65, 0.35),
    "tool_orchestration": (0.55, 0.45),
    "end_to_end": (0.50, 0.50),
    "end_to_end_analysis": (0.50, 0.50),
    "hypothesis_validation": (0.50, 0.50),
    "result_interpretation": (0.45, 0.55),
    "literature_synthesis": (0.20, 0.80),
}
task_type = os.environ.get("SCICODE_TASK_TYPE", "").strip().lower().replace("-", "_")
weights = SCORING_WEIGHTS.get(task_type, (0.50, 0.50))
prog_w, judge_w = weights

prog_score = float(prog.get("score", 0.0))
llm_score = float(llm.get("score_fraction", 0.0))
prog_score = max(0.0, min(1.0, prog_score))
llm_score = max(0.0, min(1.0, llm_score))

final = prog_w * prog_score + judge_w * llm_score
Path("/logs/verifier/reward.txt").write_text(str(round(final, 4)))

details = {
    "final_reward": round(final, 4),
    "task_type": task_type,
    "judge_model": os.environ.get("JUDGE_MODEL", ""),
    "components": {
        "programmatic": {"weight": prog_w, "score": round(prog_score, 4)},
        "llm_judge": {"weight": judge_w, "score": round(llm_score, 4)},
    },
    "programmatic_details": prog,
    "llm_judge_details": llm,
}
Path("/logs/verifier/reward_details.json").write_text(json.dumps(details, indent=2))
print(f"Final reward: {final:.4f} (prog={prog_score:.4f}*{prog_w:.2f} + judge={llm_score:.4f}*{judge_w:.2f})")
PYEOF

            # Copy all logs to output
            cp -r /logs/verifier/* /output/ 2>/dev/null || true
            cp -r /tmp/eval/* /output/ 2>/dev/null || true
        ' \
        2>&1 | tee "$OUTPUT_DIR/run.log"

    # Step 4: Report results
    echo ""
    echo "[4/4] Results:"
    if [ -f "$OUTPUT_DIR/reward.txt" ]; then
        local REWARD
        REWARD=$(cat "$OUTPUT_DIR/reward.txt")
        echo "  Reward: $REWARD"
        echo "  Details: $OUTPUT_DIR/reward_details.json"
    else
        echo "  WARNING: No reward.txt produced"
    fi
    echo "  Full log: $OUTPUT_DIR/run.log"
    echo ""

    return 0
}

# --- Main ---

if [ $# -eq 0 ]; then
    usage
fi

if [ "$1" = "--all" ]; then
    echo "Running QC judge on all tasks..."
    echo ""
    RESULTS_FILE="$OUTPUT_BASE/summary.tsv"
    echo -e "task\treward\ttask_type" > "$RESULTS_FILE"

    FAIL_COUNT=0
    TOTAL=0
    TOTAL_TASKS=$(ls -d "$TASKS_DIR"/*/ | wc -l)
    for TASK_DIR in "$TASKS_DIR"/*/; do
        TASK_NAME=$(basename "$TASK_DIR")
        TOTAL=$((TOTAL + 1))
        if run_judge_for_task "$TASK_NAME"; then
            REWARD=$(cat "$OUTPUT_BASE/$TASK_NAME/reward.txt" 2>/dev/null || echo "0.0")
            TASK_TYPE=$(python3 -c "
for line in open('$TASKS_DIR/$TASK_NAME/task.toml'):
    if line.strip().startswith('task_type'):
        print(line.split('=')[1].strip().strip('\"'))
        break
" 2>/dev/null || echo "unknown")
            echo -e "$TASK_NAME\t$REWARD\t$TASK_TYPE" >> "$RESULTS_FILE"
        else
            echo -e "$TASK_NAME\tERROR\t" >> "$RESULTS_FILE"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    done

    echo ""
    echo "============================================"
    echo "  Summary: $((TOTAL - FAIL_COUNT))/$TOTAL tasks completed"
    echo "  Results: $RESULTS_FILE"
    echo "============================================"
else
    TOTAL_TASKS=1
    run_judge_for_task "$1"
fi
