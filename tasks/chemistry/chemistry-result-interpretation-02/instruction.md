# Assess the CAl3MgH2- Catalysis Claim

## Scientific question

A computational study proposes gas-phase CAl3MgH2- for acetone hydrogenation
at 298.15 K and 1 atm. Determine how strongly the supplied results support the
reported elementary pathway, a viable catalytic cycle, and practically
meaningful turnover. Resolve provenance before using any supplied result.

## Inputs

All inputs are under `/home/agent/data/`:

- `malhan_thirumoorthy_2026.pdf`: CC BY primary article.
- `artifact_registry.csv`: provenance and claim-authority metadata for the
  versioned result artifacts. Artifact IDs are opaque and row order is not
  meaningful.
- `reported_energetics.csv`: one versioned energetics artifact.
- `screening_summary.csv`: one versioned derived-result artifact.
- `natural_charges.csv` and `bond_metrics.csv`: reported mechanistic
  observables.
- `calculation_settings.json`: constants and the deterministic barrier
  perturbation used for sensitivity analysis.
- `data_dictionary.md`: field semantics, controlled values, units, and output
  metric names.

Do not run new quantum-chemistry calculations or regenerate stationary points.

## Required analysis

1. Use the registry and source article to establish which supplied artifact is
   authoritative for claim assessment. Explain the disposition of the other
   versioned result and test whether its numerical conclusion is scientifically
   licensed by the authoritative records.
2. Interpret the stationary points, IRCs, charges, bond distances, energy
   references, method comparison, and product-complex evidence. State what each
   supports and what remains unestablished. Discuss the consequences of at
   least two task-specific environment or speciation omissions.
3. From the authoritative energetics artifact, calculate the eight metrics
   defined in `data_dictionary.md` using conventional Eyring transition-state
   theory and the supplied settings. Treat the barrier perturbation according
   to its recorded semantics.
4. Audit the Gibbs-energy comparability of the four state pairs defined in
   `data_dictionary.md`. Do not invent missing offsets or replace blank values
   with zero.
5. Give one computational follow-up and one experimental follow-up that directly
   test the most consequential unresolved part of the claim.

Calibrate the controlled verdict from the evidence states using the decision
semantics in `data_dictionary.md`.

## Deliverables

Write every artifact under `/home/agent/results/`:

| Path | Required contents |
| --- | --- |
| `/home/agent/results/report.md` | Source-grounded interpretation, provenance decision, uncertainty, limitations, and follow-up |
| `/home/agent/results/answer.json` | Controlled scientific decisions using the schema below |
| `/home/agent/results/bounded_calculations.csv` | Columns `metric,value,unit,source_artifact_id`; exactly one row per required metric |
| `/home/agent/results/reference_audit.csv` | Columns `comparison,status,value,unit,source_artifact_id`; exactly one row per required comparison |
| `/home/agent/results/code/interpret_cycle.py` | Reproducible implementation exposing `analyze(data_dir, results_dir)` |
| `/home/agent/results/figures/rate_sensitivity.png` | Log-scale 250-400 K comparison of both segment rates with the rate axis labeled in `s^-1` and the recorded perturbation scenario; label whether the curves are a turnover frequency |

`answer.json` must contain exactly these keys and controlled values:

```json
{
  "claim_verdict": "supported|partially_supported|not_supported|inconclusive",
  "authoritative_artifact_id": "string copied from artifact_registry.csv",
  "cycle_energy_span_status": "identifiable|not_identifiable",
  "turnover_frequency_status": "identifiable|not_identifiable",
  "screening_summary_disposition": "authoritative|non_authoritative"
}
```

For an identifiable comparison, report its signed `lhs - rhs` Gibbs-energy
difference and `kcal/mol`. For a non-identifiable comparison, leave `value`
blank and still report `kcal/mol`. Report calculated values with at least three
significant figures. Numeric grading uses 0.5% relative tolerance and `1e-10`
absolute tolerance near zero.

The submitted code must read the artifact path and ID from the registry rather
than relying on a filename, file order, row order, or a fixed artifact ID.
`analyze(data_dir, results_dir)` must reproduce `answer.json`, both CSV files,
the report, and the figure when called with `pathlib.Path`-compatible paths.
