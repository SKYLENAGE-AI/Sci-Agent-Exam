# Sci-Agent-Exam

A compact, self-contained extract of a scientific software-engineering agent
benchmark: the **harbor run logic** that drives one evaluation end-to-end, plus
**five complete example tasks** spanning five scientific domains and five task
types. The layout follows the
[Terminal-Bench-Science](https://terminal-bench-science.ai/) conventions (one
task = `instruction.md` + `environment/` + `tests/` + `solution/`, driven by the
[`harbor`](https://github.com/harbor-framework/harbor) runner).

This is a *representative extract*, not the full benchmark: large-scale batch
runners, result aggregation, and the complete task set are omitted. Everything
needed to understand and reproduce a single evaluation is included.

> **📊 Live leaderboard:** <https://skylenage-ai.github.io/Sci-Agent-Exam/leaderboard/>
> — 10 frontier agents across 11 scientific fields and 7 task types, sortable by
> Programmatic / LLM-Judge / Combined / Pass@0.95. Source + generator in
> [`leaderboard/`](leaderboard/).

---

## 1. What the benchmark measures

Each **task** is a self-contained scientific problem shipped as a Docker
environment plus input data (datasets, source code, mounted papers). An **agent**
(an LLM driving a coding CLI) is dropped into the container with only the task
instruction and must produce a set of deliverables — code, result tables, a
figure, a short report, and a machine-readable `answer.json`. The deliverables
are then scored by a **two-component verifier**:

- a **programmatic check** (`tests/check_programmatic.py`) — deterministic
  numerical / schema / file checks, and
- an **LLM judge** (`tests/llm_judge.py`) — rubric-based grading of scientific
  meaning, reasoning, and interpretation against `tests/rubric.json`.

The final reward is a fixed, per-task-type weighted sum of the two (see §4). This
two-channel design is the core of the benchmark: execution correctness and
scientific judgement are measured separately.

---

## 2. Repository layout

```
Sci-Agent-Exam/
├── README.md                   ← this file
├── task-template.toml          ← annotated template for the task.toml schema
├── harness/                    ← harbor run logic (core evaluation code)
│   ├── run_harbor_task.sh      ← MAIN: run one task through harbor
│   ├── docker_claude_agent.sh  ← in-container agent entrypoint (prompt + setup)
│   ├── build_image.sh          ← build a task image on the shared base
│   ├── base/Dockerfile         ← shared base image (Python, Node, agent CLI, common deps)
│   ├── run_judge.sh            ← standalone verifier flow (grades the golden solution)
│   └── judge_adapter.py        ← routes the judge through an OpenAI-compatible API
├── leaderboard/                ← self-contained results webpage + its data
│   ├── build.py                ← generator: data/leaderboard.json → index.html
│   ├── index.html              ← the rendered leaderboard (open in a browser)
│   └── data/leaderboard.json   ← all scores + model / category metadata
└── tasks/                      ← five example tasks, grouped by domain (see tasks/README.md)
    ├── bioinformatics/bioinformatics-error-diagnosis-01/
    ├── chemistry/chemistry-result-interpretation-02/
    ├── materials-science/materials-science-literature-synthesis-02/
    ├── mathematics/mathematics-code-generation-02/
    └── physics-simulation/physics-simulation-tool-orchestration-01/
```

Each task directory has a fixed structure:

```
<task>/
├── instruction.md           ← the only thing the agent is shown
├── task.toml                ← metadata, I/O schema, scoring task type, verifier env
├── metadata.json            ← domain + bookkeeping (anonymized)
├── README.md                ← human-readable task record (source, license, difficulty)
├── environment/
│   ├── Dockerfile           ← builds on the shared base, installs the task stack
│   ├── requirements.lock    ← exact pip pins captured from the evaluation image
│   └── data/                ← input datasets, source code, mounted papers
├── tests/                   ← the verifier (NEVER shown to the agent)
│   ├── test.sh              ← orchestrator → writes /logs/verifier/reward.txt
│   ├── check_programmatic.py
│   ├── llm_judge.py         ← task-agnostic rubric judge
│   ├── judge_config.json    ← per-task judge inputs
│   └── rubric.json          ← weighted PASS/FAIL criteria
└── solution/                ← golden reference (solve.py/solve.sh + answer.json + artifacts)
```

---

## 3. The evaluation flow

```
run_harbor_task.sh <task> <agent> [model]
        │
        ▼
   harbor run -p tasks/<domain>/<task> -a <agent> -m <model>
        │
        ├─ builds environment/Dockerfile (on the shared sciagent-bench:base image)
        ├─ runs the AGENT in the container
        │     • agent sees ONLY /home/agent/data/ + the instruction
        │     • writes deliverables to /home/agent/results/
        │
        └─ runs the VERIFIER (tests/test.sh), with no network egress
              • check_programmatic.py  → programmatic.json
              • llm_judge.py           → llm_judge.json   (rubric grading)
              • weighted combine       → /logs/verifier/reward.txt  (final scalar)
```

**Isolation guarantee.** The agent is only ever given the instruction and the
`data/` directory. The `tests/` directory (rubric, programmatic checks, golden
solution) is never mounted into the agent container — only into the verifier
step, which runs with no network egress. This keeps the agent from reading or
targeting the grader.

`harness/run_judge.sh` is a standalone variant used for QC: it runs the **golden
solution** through the exact `check_programmatic.py` + `llm_judge.py` pipeline,
confirming the grader behaves on a known-good answer.

---

## 4. Scoring

The final reward is a weighted sum of the two components, with weights fixed per
task type (`tests/test.sh`; the task type is set in each `task.toml`
`[verifier.env]` as `SCICODE_TASK_TYPE`):

| Task type | Programmatic | LLM judge |
|---|---|---|
| code_generation | 0.70 | 0.30 |
| error_diagnosis | 0.65 | 0.35 |
| tool_orchestration | 0.55 | 0.45 |
| end_to_end_analysis / hypothesis_validation | 0.50 | 0.50 |
| result_interpretation | 0.45 | 0.55 |
| literature_synthesis | 0.20 | 0.80 |

```
final_reward = prog_weight * programmatic_score + judge_weight * judge_score_fraction
```

Both component scores are clamped to `[0, 1]`. The LLM judge grades `rubric.json`
one criterion at a time (PASS/FAIL) and reports
`score_fraction = Σ(weight of PASS) / Σ(weight of all)`. A required-artifact
preflight runs before rubric scoring: a missing/invalid deliverable pre-fails
only the criteria that declared it as an input, so independent work is still
graded against the full denominator. `test.sh` writes a `0.0` reward upfront and
preserves it on any crash, so an aborted verifier yields a real `0.0` rather than
a harness error.

---

## 5. The five example tasks

Chosen to span five scientific domains **and** five task types, across the full
scoring-weight range (0.70/0.30 down to 0.20/0.80).

| Domain | Task type | Prog / Judge | Task |
|---|---|---|---|
| Mathematics | code_generation | 0.70 / 0.30 | `mathematics/mathematics-code-generation-02` |
| Bioinformatics | error_diagnosis | 0.65 / 0.35 | `bioinformatics/bioinformatics-error-diagnosis-01` |
| Physics Simulation | tool_orchestration | 0.55 / 0.45 | `physics-simulation/physics-simulation-tool-orchestration-01` |
| Chemistry | result_interpretation | 0.45 / 0.55 | `chemistry/chemistry-result-interpretation-02` |
| Materials Science | literature_synthesis | 0.20 / 0.80 | `materials-science/materials-science-literature-synthesis-02` |

Each task's `README.md` records its external source (paper / dataset / codebase)
and that source's license. Each ships with its golden reference solution under
`solution/`. See [`tasks/README.md`](tasks/README.md) for one-line descriptions.

---

## 6. Running an evaluation

**Prerequisites:** Docker, Python 3.12, and `harbor==0.20.0`.

```bash
uv tool install "harbor==0.20.0"   # or: pip install "harbor==0.20.0"
```

**Credentials** (any OpenAI/Anthropic-compatible gateway, or the vendor APIs directly):

```bash
# Used by run_harbor_task.sh (agent + in-container verifier, Anthropic protocol):
export LITELLM_PROXY_API_BASE="https://<your-llm-proxy>"   # LLM proxy base URL
export LITELLM_PROXY_API_KEY="<key>"
# tests/llm_judge.py reads ANTHROPIC_*; run_harbor_task.sh defaults them from the
# proxy vars above if unset:
export ANTHROPIC_BASE_URL="$LITELLM_PROXY_API_BASE"
export ANTHROPIC_API_KEY="$LITELLM_PROXY_API_KEY"
```

For the standalone QC flow (`run_judge.sh`, §6 below), which routes the judge
through an OpenAI-compatible endpoint via `judge_adapter.py`, also set (e.g. in a
top-level `.env`, which `run_judge.sh` sources):

```bash
export JUDGE_BASE_URL="https://<your-llm-proxy>"
export JUDGE_API_KEY="<key>"
export JUDGE_MODEL="<judge-model-id>"
# If JUDGE_BASE_URL/JUDGE_API_KEY are unset, run_judge.sh falls back to the native
# Anthropic llm_judge.py path (which uses ANTHROPIC_API_KEY).
```

**Run a task with an agent** (the shared base image is built automatically on
first run):

```bash
bash harness/run_harbor_task.sh bioinformatics-error-diagnosis-01 claude-code <model-id>
```

The bare task slug is resolved to its domain directory; you can also pass
`bioinformatics/bioinformatics-error-diagnosis-01` explicitly.

**QC the grader against the golden solution (no agent):**

```bash
bash harness/run_judge.sh data-science-hypothesis-validation-02
# → prints the final reward and writes reward_details.json
```

---

## 7. Reproducibility & environment

- Each `environment/Dockerfile` builds on the shared `sciagent-bench:base` image
  (`harness/base/Dockerfile`: Python 3.11, Node 22, the agent CLI, and common
  agent/judge tooling) and installs the task's scientific stack from
  `environment/requirements.lock`. Those locks are the **exact pip pins captured
  from the evaluation images** (Python 3.11.15), so a rebuild reproduces the
  environment the results were produced in.
- The scientific stack is intentionally kept out of the base image: tasks pin
  different major versions (e.g. `numpy` 1.24 vs 1.26), so each task layer
  installs its own to avoid ABI corruption.

---

## 8. Notes on anonymity & scope

- Author / institution / infrastructure identifiers have been removed: build-
  pipeline fields, internal image names, writer identities, and regional package
  mirrors are stripped. LLM endpoints are supplied entirely via environment
  variables.
- **Scientific-source attributions are deliberately kept.** Each task cites the
  real paper, dataset, or open-source project it derives from, together with that
  source's license (e.g. Smilei / CeCILL-B, MDAnalysis / GPL, pytorch-lightning /
  Apache-2.0, and CC-BY papers). Only sources whose license permits
  redistribution and derivative use are included.
- `judge_adapter.py` adapts the native-Anthropic `llm_judge.py` to any
  OpenAI-compatible streaming endpoint, so the pipeline is not tied to one vendor.
