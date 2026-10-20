#!/usr/bin/env bash
# Orchestrator — writes /logs/verifier/reward.txt with the final scalar score.
# Scoring uses the fixed programmatic/judge split for SCICODE_TASK_TYPE.
# Programmatic is check_programmatic.py's numerical score. The judge engine runs a
# deterministic required-artifact preflight before rubric scoring; the rubric then
# assesses scientific meaning, reasoning, validation, and interpretation.
#
# Fault-tolerance: a 0.0 reward.txt is written upfront and an EXIT trap
# preserves it, so a killed verifier yields a real 0.0 reward instead of
# Harbor's RewardFileNotFoundError.

mkdir -p /tmp/eval /logs/verifier

# >>> numpy self-heal (harbor no-rebuild) >>>
if ! python3 -c "import numpy" >/dev/null 2>&1; then
  echo "[test.sh] numpy import broken — repairing before scoring $(date -u +%FT%TZ)" >> /logs/verifier/test-trace.log
  _SP=$(python3 -c "import site;print(site.getsitepackages()[0])" 2>/dev/null)
  _NPV=$(pip show numpy 2>/dev/null | awk '/^Version:/{print $2}')
  pip uninstall -y numpy >/dev/null 2>&1 || true
  rm -rf "$_SP"/numpy "$_SP"/numpy-*.dist-info "$_SP"/numpy.libs 2>/dev/null || true
  pip install --no-cache-dir "numpy==${_NPV:-1.24.4}" >> /logs/verifier/test-trace.log 2>&1
  python3 -c "import numpy; print('[test.sh] numpy repaired', numpy.__version__)" >> /logs/verifier/test-trace.log 2>&1 || echo "[test.sh] numpy repair FAILED" >> /logs/verifier/test-trace.log
fi
# <<< numpy self-heal <<<


# Diagnostic: confirm test.sh is actually being invoked and trace its lifecycle.
{
  echo "[test.sh] started $(date -u +%FT%TZ)"
  echo "[test.sh] pwd=$(pwd) uid=$(id -u) gid=$(id -g)"
  echo "[test.sh] /home/agent/results listing:"
  ls -la /home/agent/results/ 2>&1 || echo "  (missing)"
  echo "[test.sh] /tests listing:"
  ls -la /tests/ 2>&1 || echo "  (missing)"
  echo "[test.sh] which python3: $(command -v python3 || echo MISSING)"
  echo "[test.sh] ANTHROPIC_API_KEY set: $([ -n "${ANTHROPIC_API_KEY:-}" ] && echo yes || echo NO)"
} >> /logs/verifier/test-trace.log 2>&1

# Always leave behind a reward.txt even if a later line kills us
echo "0.0" > /logs/verifier/reward.txt
trap 'echo "[test.sh] exited $(date -u +%FT%TZ) rc=$?" >> /logs/verifier/test-trace.log' EXIT

# Helper: capture each substep's stdout+stderr into a per-step trace file so
# setup failures (argparse errors, missing files, import errors) are recoverable
# from artifacts instead of vanishing into Harbor's truncated console buffer.
SETUP_ERRORS=()

run_substep() {
  # $1 = label (used for the per-step trace + setup_errors)
  # $2 = result_file we expect the substep to write
  # $3 = fallback JSON to emit if the substep failed entirely
  # remaining args = the command to run
  local LABEL="$1" RESULT_FILE="$2" FALLBACK="$3"
  shift 3
  local TRACE="/logs/verifier/${LABEL}.log"

  if [ ! -f "$1" ]; then
    local MSG="$LABEL: script not found at $1"
    echo "::error::$MSG"
    echo "$MSG" | tee "$TRACE"
    echo "$FALLBACK" > "$RESULT_FILE"
    SETUP_ERRORS+=("$MSG")
    return 0
  fi

  python3 "$@" >"$TRACE" 2>&1
  local RC=$?
  cat "$TRACE"

  if [ $RC -ne 0 ]; then
    local DETAIL=""
    if [ -s "$RESULT_FILE" ]; then
      if ! DETAIL=$(python3 -c 'import json,sys; value=json.load(open(sys.argv[1])); print(value.get("error", "") if isinstance(value, dict) else "")' "$RESULT_FILE" 2>/dev/null); then
        DETAIL=""
        echo "$FALLBACK" > "$RESULT_FILE"
      fi
    else
      echo "$FALLBACK" > "$RESULT_FILE"
    fi
    local MSG="$LABEL exited $RC — see $TRACE"
    if [ -n "$DETAIL" ]; then
      MSG="$LABEL: $DETAIL (exit $RC — see $TRACE)"
    fi
    echo "::error::$MSG"
    SETUP_ERRORS+=("$MSG")
    return 0
  fi

  if [ ! -s "$RESULT_FILE" ]; then
    local MSG="$LABEL produced no result file at $RESULT_FILE"
    echo "::error::$MSG"
    echo "$FALLBACK" > "$RESULT_FILE"
    SETUP_ERRORS+=("$MSG")
    return 0
  fi
}

# Step 1: Programmatic numerical checks
echo "=== Programmatic checks ==="
run_substep "check_programmatic" /tmp/eval/programmatic.json \
  '{"score": 0.0, "error": "check_programmatic.py failed"}' \
  /tests/check_programmatic.py \
  --output /home/agent/results/ \
  --result-file /tmp/eval/programmatic.json

# Step 2: LLM-as-judge
echo "=== LLM judge ==="
run_substep "llm_judge" /tmp/eval/llm_judge.json \
  '{"score_fraction": 0.0, "error": "llm_judge.py failed"}' \
  /tests/llm_judge.py \
  --agent-output /home/agent/results/ \
  --rubric /tests/rubric.json \
  --result-file /tmp/eval/llm_judge.json

# Export setup errors as JSON for the aggregation step.
{
  printf '['
  FIRST=1
  for E in ${SETUP_ERRORS[@]+"${SETUP_ERRORS[@]}"}; do
    if [ "$FIRST" -eq 1 ]; then FIRST=0; else printf ','; fi
    printf '%s' "$E" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()), end="")'
  done
  printf ']'
} > /tmp/eval/setup_errors.json

# Step 3: aggregate
# NB: this MUST use `if ! python3 - <<'PY' ... PY then ... fi` shape rather
# than `python3 - <<'PY' 2>&1 || { ... }`. The latter is a bash parse error
# because the heredoc body swallows the `}` of the brace group — the script
# never starts, the upfront 0.0 reward.txt is the only thing Harbor ever sees,
# and every task silently scores 0.000 regardless of agent quality.
echo "=== Computing final reward ==="
if ! python3 - <<'PY' 2>&1
import json
import math
import os
from pathlib import Path

prog = json.loads(Path('/tmp/eval/programmatic.json').read_text())
llm = json.loads(Path('/tmp/eval/llm_judge.json').read_text())
setup_errors = []
se_path = Path('/tmp/eval/setup_errors.json')
if se_path.is_file():
    try:
        setup_errors = json.loads(se_path.read_text() or '[]')
    except Exception:
        setup_errors = []
# Always carry the component's structured error text. run_substep also records
# its exit/log context, but older scripts may have emitted only one of the two.
for label, blob in (('check_programmatic', prog), ('llm_judge', llm)):
    err = blob.get('error') if isinstance(blob, dict) else None
    if err and not any(str(err) in str(existing) for existing in setup_errors):
        setup_errors.append(f"{label}: {err}")

def bounded_component_score(blob, key, label):
    """Return a valid component score, failing the component closed otherwise."""
    raw = blob.get(key) if isinstance(blob, dict) else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        setup_errors.append(
            f"{label}: {key} must be a JSON number in [0, 1], got {raw!r}"
        )
        return 0.0

    score = float(raw)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        setup_errors.append(
            f"{label}: {key} must be finite and in [0, 1], got {raw!r}"
        )
        return 0.0
    return score


prog_score = bounded_component_score(prog, 'score', 'check_programmatic')
llm_score = bounded_component_score(llm, 'score_fraction', 'llm_judge')

# Programmatic is the numerical grader outright: no structural grader exists.
programmatic = prog_score

SCORING_WEIGHTS = {
    'code_generation': (0.70, 0.30),
    'error_diagnosis': (0.65, 0.35),
    'tool_orchestration': (0.55, 0.45),
    'end_to_end': (0.50, 0.50),
    'end_to_end_analysis': (0.50, 0.50),
    'hypothesis_validation': (0.50, 0.50),
    'result_interpretation': (0.45, 0.55),
    'literature_synthesis': (0.20, 0.80),
}
task_type = os.environ.get('SCICODE_TASK_TYPE', '').strip().lower().replace('-', '_')
weights = SCORING_WEIGHTS.get(task_type)
if weights is None:
    setup_errors.append(
        'aggregation: SCICODE_TASK_TYPE must name a recognized task type, '
        f'got {task_type or "<unset>"!r}'
    )
    programmatic_weight, judge_weight = 0.0, 0.0
else:
    programmatic_weight, judge_weight = weights
final = programmatic_weight * programmatic + judge_weight * llm_score

Path('/logs/verifier/reward.txt').write_text(str(round(final, 4)))

details = {
    'final_reward': round(final, 4),
    'setup_errors': setup_errors,
    'components': {
        # Alias the AutoQC bot expects (workflow reads components.programmatic.score).
        'programmatic': {
            'weight': programmatic_weight,
            'score': round(programmatic, 4),
        },
        'llm_judge': {'weight': judge_weight, 'score': llm_score},
    },
    'programmatic_details': prog,
    'llm_judge_details': llm,
}
Path('/logs/verifier/reward_details.json').write_text(json.dumps(details, indent=2))
print(f"Final reward: {final:.4f}")
print(f"  task type:                {task_type or '<unset>'}")
print(f"  programmatic (numerical): {programmatic:.4f} × {programmatic_weight:.2f} = {programmatic_weight * programmatic:.4f}")
print(f"  llm_judge:                {llm_score:.4f} × {judge_weight:.2f} = {judge_weight * llm_score:.4f}")
if setup_errors:
    print("\n::warning::Verifier setup errors detected — final reward may not reflect agent quality:")
    for err in setup_errors:
        print(f"  - {err}")
PY
then
  echo "::error::aggregation step failed, leaving reward.txt at 0.0"
fi

echo "=== Verifier complete ==="
echo "Reward file: $(cat /logs/verifier/reward.txt)"
