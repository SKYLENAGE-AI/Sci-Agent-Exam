# Tasks

Five complete example tasks, grouped by scientific domain, chosen to span five
task types across the full scoring-weight range. Each is a self-contained Docker environment plus input data; the agent
is shown only `instruction.md` and the mounted `data/` directory, and must write
its deliverables to `/home/agent/results/`. See the top-level
[`README.md`](../README.md) for the run flow, scoring, and the directory contract;
see [`task-template.toml`](../task-template.toml) for the `task.toml` schema.

Every task cites the real scientific source it derives from, with that source's
license. Only sources whose license permits redistribution and derivative use are
included.

| Task | Task type | Prog / Judge |
|---|---|---|
| [mathematics-code-generation-02](mathematics/mathematics-code-generation-02) | code_generation | 0.70 / 0.30 |
| [bioinformatics-error-diagnosis-01](bioinformatics/bioinformatics-error-diagnosis-01) | error_diagnosis | 0.65 / 0.35 |
| [physics-simulation-tool-orchestration-01](physics-simulation/physics-simulation-tool-orchestration-01) | tool_orchestration | 0.55 / 0.45 |
| [chemistry-result-interpretation-02](chemistry/chemistry-result-interpretation-02) | result_interpretation | 0.45 / 0.55 |
| [materials-science-literature-synthesis-02](materials-science/materials-science-literature-synthesis-02) | literature_synthesis | 0.20 / 0.80 |

---

## Mathematics — `mathematics-code-generation-02`
**code_generation.** Implement a reusable Python module that audits and
parameter-screens binary cyclically permutable constant-weight (CPCW) codebooks —
validity, optimality against the source upper bound, perfectness, uncovered
residues, repeated differences, and source-claim review — exposing a documented
API plus a structured `answer.json`, report, and self-tests.
*Source:* Baicheva & Topalova, *On the Existence of Optimal (v,5,1) and (v,6,1)
Binary CPCW Codes*, Axioms (2026), doi:10.3390/axioms15010035 — CC BY 4.0.

## Bioinformatics — `bioinformatics-error-diagnosis-01`
**error_diagnosis.** Diagnose and minimally repair a silent target-mirroring
eligibility regression in an offline protein–ligand affinity benchmark replay,
then regenerate the release summary and supporting evidence tables.
*Sources:* Mattsson & Walters, *Identifying and Addressing Systematic Data Leakage
in Protein-Ligand Affinity Benchmarks*, bioRxiv v1 (2026),
doi:10.64898/2026.06.29.735309 — CC BY 4.0; software fixture is an offline fork of
`bamattsson/ntab` — MIT.

## Physics Simulation — `physics-simulation-tool-orchestration-01`
**tool_orchestration.** Orchestrate SQLite catalog/contract lookup, Smilei
laser-plasma namelist parsing, HDF5 inspection/loading, and FFT diagnostics to
validate harmonic generation in a magnetized particle-in-cell fixture.
*Source:* Smilei (SmileiPIC collaboration), `SmileiPIC/Smilei` @ `49367cf`
(2026-03-12) — CeCILL-B.

## Chemistry — `chemistry-result-interpretation-02`
**result_interpretation.** Resolve versioned computational results and interpret
whether the authoritative DFT evidence establishes catalytic viability and
turnover for acetone hydrogenation by CAl₃MgH₂⁻, distinguishing a proposed
mechanism from demonstrated catalysis.
*Source:* Malhan & Thirumoorthy, Frontiers in Chemistry (2025),
doi:10.3389/fchem.2025.1750798 — CC BY 4.0.

## Materials Science — `materials-science-literature-synthesis-02`
**literature_synthesis.** Synthesize four crystal-discovery studies to decide
whether generated diperiodic structures can be routed directly to experimental
synthesis, reconciling each paper's different stability/novelty endpoint.
*Source:* four CC BY 4.0 papers (incl. Chang et al., *SLayerGen*,
`2605.08262v1`); full attribution in the task README.
