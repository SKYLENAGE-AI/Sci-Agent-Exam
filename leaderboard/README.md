# Sci-Agent-Exam — Leaderboard

A single-file, dependency-free webpage that renders the **Sci-Agent-Exam**
leaderboard: 10 frontier LLM agents across 11 scientific fields and 7 research
task types, scored on two axes (programmatic execution and LLM-judge
presentation) plus a `Pass@0.95` reliability metric.

**Live:** <https://skylenage-ai.github.io/Sci-Agent-Exam/leaderboard/>

```
leaderboard/
├── build.py                 # generator: data/leaderboard.json -> index.html
├── index.html               # the generated page (open directly in a browser)
├── data/
│   └── leaderboard.json      # all numbers + model / category metadata
└── README.md
```

## Viewing

`index.html` is fully self-contained (inline CSS + JS, no network, no fonts to
fetch). Just open it:

```bash
# open directly
xdg-open index.html            # or: open index.html  (macOS)

# or serve it
python3 -m http.server 8000    # then visit http://localhost:8000/
```

The page lets you:

- **filter** by scientific field or research task type (the chips), and
- **sort** by any of the four columns — Programmatic, LLM, Combined, Pass@0.95 —
  by clicking its header (click again to flip ascending / descending). The score
  bar re-colors and re-scales to whichever metric is active.

## Rebuilding

All content lives in `data/leaderboard.json`. Edit that file and regenerate:

```bash
python3 build.py               # writes index.html
python3 build.py out.html      # or a custom path
```

`build.py` needs only the Python standard library.

## Data: `data/leaderboard.json`

```jsonc
{
  "meta":   { "n_tasks": 120, "pass_threshold": 0.95, ... },
  "models": [ { "id", "name", "prov", "color" }, ... ],   // display order
  "fields": [ { "key", "ic", "label", "n", "hero"? }, ... ],
  "task_types": [ { "key", "ic", "label", "n" }, ... ],
  "scores": { "<model-id>": { "<category-key>": { "p", "j", "c", "r" } } }
}
```

Each score cell is on a 0–1 scale:

| field | meaning |
|-------|---------|
| `p` | **Programmatic** — deterministic execution / numerical / schema checks |
| `j` | **LLM-Judge** — rubric-based grading of the scientific write-up |
| `c` | **Combined** — `0.55·p + 0.45·j` (per-task-type weighted; see paper §4) |
| `r` | **Pass@0.95** — per-task fraction of runs whose combined score ≥ 0.95, macro-averaged over tasks |

`p`, `j`, `c` are macro-averaged over the tasks in each category. `overall`
Programmatic / LLM / Combined / Pass@0.95 reproduce the paper's main results
table exactly (GPT-6 Astra: 77.7 / 85.3 / 80.9 / 26.0). Per-category Pass@0.95 is
computed with the same methodology from the run-level logs; the paper reports
Pass@0.95 only at the `overall` level.

All runs are from the **Claude Code harness at high effort**, scored rows only
(infra failures, refusals, and in-progress runs excluded), with per task a mean
of up to three time-uniform runs.

## Publishing (GitHub Pages)

The page is static, so hosting needs no build step. After pushing the repo to
`SKYLENAGE-AI/Sci-Agent-Exam`, enable Pages once:

1. **Settings → Pages**.
2. **Source: Deploy from a branch**.
3. **Branch: `master`**, folder **`/ (root)`** → **Save**.

GitHub serves the repo as-is; the leaderboard is then live at

```
https://skylenage-ai.github.io/Sci-Agent-Exam/leaderboard/
```

(the owner subdomain is lowercased; the repo path keeps its original case). It
may take a minute on the first deploy. No Actions workflow is required — every
later `git push` that changes `leaderboard/index.html` republishes automatically.
