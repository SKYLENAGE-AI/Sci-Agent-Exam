# Diagnose a joint novelty and target-mirroring benchmark regression

> **Execution mode:** Run this task end-to-end autonomously. Write every final artifact to
> `/home/agent/results/`; your turn ends only when all deliverables below are on disk.
>
> **File-writing convention:** Write files directly from Python or with a single-step file write.
> Do not assemble files with chained shell appends or heredocs.

## Scientific context

The supplied project is an offline fork of the Novelty-Tiered Affinity Benchmark repository. Its
validation/test replay combines individual-ligand novelty, assay predictability, same-document
target-mirroring evidence, document representation, and performance evaluation. A silent
regression leaves the project executable, its retained tests green, and its coarse release receipt
unchanged while changing the scientific population that reaches evaluation.

The mounted paper at `/home/agent/data/2026.06.29.735309v1.full.pdf` is the primary scientific
authority for interpreting the leakage mechanisms and bounding claims. The normative fixed
operational contract for this offline replay is `/home/agent/data/analysis_config.json`, including
its thresholds, precedence, and fixture-specific integration policy. The descriptive
`/home/agent/data/data_dictionary.md` defines mounted inputs, artifact semantics, units,
missing-value behavior, and serialization. `/home/agent/data/source_manifest.json` is optional
integrity and provenance support for the mounted sources; it does not define the analysis method.
Use the paper to distinguish paper-backed scientific
conventions from task-specific integration policy and to justify the scientific interpretation
and claim limits; the mounted contract files do not identify the defective pipeline stage or the
smallest sufficient repair.

## Symptom and reproduction

```text
cd /home/agent/data/broken_project && python3 scripts/reproduce.py --output-dir /tmp/ntab-public --require-match
```

The command exits zero and writes complete compound-novelty, same-document assay-pair,
assay-inventory, document-retention, retained-assay-performance, summary, and receipt artifacts.
Agreement with `release_summary.tsv` covers raw input counts only; it does not validate novelty
membership, target-mirroring evidence, assay eligibility, document representation, or the evidence
reaching performance evaluation.

## Task

Diagnose the earliest scientific regression using the complete project, executable replay, raw
activity table, compound fingerprint and catalog-provenance table, assay-document chronology,
target-pair sequence identities, mounted paper, and release receipt. Apply the smallest
source-consistent patch and regenerate every deliverable from the repaired project.

Compare the leading explanation with at least two plausible alternatives while changing one
scientific factor at a time. Trace the repair through every compound, same-document assay pair,
assay, document,
retained-assay performance result, split summary, and the receipt, including unchanged and
ineligible evidence. The patch must generalize across row order, opaque identifiers, document
depth, exact size ties, duplicate records, and unseen valid fixtures.

## Repair constraints

- Preserve package interfaces, mounted fixture bytes, output schemas, thresholds, and behavior
  outside the minimal repair.
- Keep existing tests intact; do not delete, skip, weaken, or rewrite them.
- Do not hardcode fixture identifiers or expected scientific table values into the repaired
  project, and do not replace the project with a clean upstream copy. The `answer.json`
  classifications must be supported by regenerated evidence and the report and must not control
  pipeline computation.
- Keep execution offline and deterministic. `release_summary.tsv` is read-only comparison evidence.
- Bound conclusions to the mounted source and supplied offline fixture.

## Deliverables

Write every path below under `/home/agent/results/`.

| Path | Scientific content |
| :--- | :--- |
| `code/ntab/` | Complete minimally patched project with every mounted fixture path byte-identical. |
| `answer.json` | Compact diagnosis receipt using the schema below. |
| `report.md` | Source-grounded diagnosis, minimal-patch rationale, controlled alternatives, validation, scientific consequences, and claim limits. |
| `compound_novelty.tsv` | Complete repaired per-split compound novelty and configured-tier membership evidence. |
| `assay_pair_audit.tsv` | Complete repaired same-document target-mirroring evidence, including qualifying, rejected, undefined, and no-effect pairs. |
| `assay_inventory.tsv` | Complete repaired assay-level eligibility and retention evidence, including all affected and unaffected assay units. |
| `document_retention.tsv` | Complete repaired document-level candidate, qualifying, and retained membership evidence. |
| `assay_performance.tsv` | Complete repaired performance evidence for every retained assay unit. |
| `summary.tsv` | Complete repaired per-split retention and performance summary. |
| `reproduction.json` | Repaired release-comparison receipt. |

Retain `code/ntab/pyproject.toml`, `code/ntab/UPSTREAM_LICENSE.toml`, all mounted Python package
and script files, `code/ntab/tests/test_public_contract.py`, and the six public fixture files
`activities.tsv`, `compound_fingerprints.tsv`, `assay_documents.tsv`, `target_identity.tsv`,
`release_summary.tsv`, and `fixture_manifest.json`.

`answer.json` schema:

```json
{
  "bug_type": "orientation|unit_conversion|statistical_formula|data_alignment|parser|indexing|sparse_access|numerical_stability|other",
  "earliest_fault": "analysis_population|eligibility_construction|document_representative|performance_evaluation|aggregation|other",
  "repair_scope": "population_only|retention_only|eligibility_only|evaluation_only|aggregation_only|other",
  "bias_direction": "no_effect|optimistic|pessimistic|mixed",
  "fixed": true
}
```

All fields are required, and enum order has no scientific meaning. These broad taxonomies are not
ranked hypotheses. `data_alignment` includes selecting or aligning the wrong record population;
`indexing` covers positional or boundary indexing; `statistical_formula` covers a mathematical
reduction; the other labels retain their ordinary meanings. Classify the earliest defect and
smallest sufficient repair, not downstream consequences. `analysis_population` denotes which
primary activity records enter the replay before any outcome-specific screen is constructed;
`population_only` is reserved for repairing that primary membership. `eligibility_construction`
denotes construction or alignment of an auxiliary evidence unit used specifically to decide
eligibility after the primary activity population exists; `eligibility_only` repairs that evidence
construction or its eligibility use while leaving primary activity membership and unrelated
stages unchanged. The remaining earliest-fault and repair-scope labels refer to their named
pipeline stages. For `bias_direction`, compare broken
and repaired finite split-level `mean_r2` values. `no_effect` means no finite split mean changes.
For the joint leakage screen,
`optimistic` means at least one split has a changed finite `mean_r2` and every such split is higher
in the broken replay; `pessimistic` means every changed finite split is lower; `mixed` means finite
split changes occur in both directions. Only splits with finite means in both replays are eligible;
values equal under the declared numeric tolerances are unchanged, and missing comparisons are
ignored. If no eligible split changes, use `no_effect`. Membership changes do not determine this
field.

Compact output index:

| Artifact | Row identity | Required fields |
| :--- | :--- | :--- |
| `compound_novelty.tsv` | `split`, `ligand_id` | identity plus `earliest_publication_year`, `first_mounted_document_year`, `reference_cutoff_year`, `max_tanimoto`, `nearest_reference_ligand_id`, `in_configured_tier`, `novelty_status` |
| `assay_pair_audit.tsv` | `split`, `document_id`, `assay_a`, `standard_type_a`, `assay_b`, `standard_type_b` | identity plus `target_a`, `target_b`, `n_shared_compounds`, `target_identity`, `pearson_r`, `r2`, `pair_status`, `policy_applies`, `mirroring_flag` |
| `assay_inventory.tsv` | `split`, `document_id`, `assay_id`, `standard_type` | identity plus `n_input_rows`, `n_tier_rows`, `n_unique_compounds`, `experimental_sd`, `base_eligibility_status`, `target_mirroring_pair_count`, `mirroring_policy_applies`, `eligibility_status`, `retained` |
| `document_retention.tsv` | `split`, `document_id` | identity plus `n_candidate_assays`, `n_base_qualifying_assays`, `n_target_mirroring_pairs`, `n_mirroring_excluded_assays`, `n_qualifying_assays`, `n_retained_assays`, `retained_assay_sha256` |
| `assay_performance.tsv` | `split`, `document_id`, `assay_id`, `standard_type` | identity plus `n_complete_predictions`, `pearson_r`, `r2`, `mae` |
| `summary.tsv` | `split` | `split`, `n_documents`, `n_candidate_assays`, `n_tier_compounds`, `n_base_qualifying_assays`, `n_target_mirroring_pairs`, `n_mirroring_excluded_assays`, `n_qualifying_assays`, `n_retained_assays`, `n_evaluable_assays`, `mean_r2`, `retained_assay_sha256` |
| `reproduction.json` | one receipt | `status`, `release_match`, `difference_count`, `differences`, `output_files` |

Rows may appear in any order. Generated TSVs serialize missing numeric values as literal `NA`.
Finite floats are accepted with absolute tolerance `1e-6` and relative tolerance `1e-9`;
integer-valued fields must be integral and compare numerically. Identifiers, enums, digests, and
missing tokens compare exactly. Boolean tokens compare by their case-insensitive `true`/`false`
meaning. Additional columns are permitted, but additional,
duplicate, or omitted rows are not. Every artifact must be complete and freshly regenerated from
submitted code.

The terms paired-pChEMBL, target-identity, and correlation name descriptive fields or concepts in
the visible artifact vocabulary. The mounted contract files prescribe the replay's operational
definitions and thresholds. Their
presence does not identify which pipeline stage is defective or which minimal source-consistent
repair is sufficient. Use the mounted paper to justify the scientific relationship among the
configured evidence axes, distinguish source convention from fixture policy, and bound the
resulting claims.

The integer-valued TSV fields are the three year fields and every count field prefixed `n_`.
The boolean fields are `in_configured_tier`, `policy_applies`, `mirroring_flag`,
`mirroring_policy_applies`, and `retained`. Digests, identifiers, split/readout labels, and status
fields are strings. All remaining numeric fields are finite floats or `NA` as permitted by their
row context. These type rules and the compact index are the entire mechanically enforced table
contract; the dictionary supplies definitions and units, not additional hidden fields or formats.

`compound_novelty.tsv` uses `novelty_status` values `in_tier` and `out_of_tier` for validation or
test and `not_evaluated` for train. Each `retained_assay_sha256` is the SHA-256 of UTF-8 text made
by sorting the retained assay IDs, joining them with newline characters, and appending one final
newline; empty membership hashes the empty byte string. The split-level digest uses the same
serialization over all retained assays in that split.

`assay_pair_audit.tsv` uses `pair_status` precedence `too_few_shared_compounds`,
`missing_target_identity`, `target_identity_not_below_threshold`, `undefined_correlation`,
`low_correlation`, then `target_mirroring`. For validation and test, `base_eligibility_status` is
one of `too_few_unique_compounds`, `undefined_experimental_sd`, `low_experimental_sd`, or
`qualifying`; final `eligibility_status` uses those values plus `target_mirroring_excluded` for an
otherwise qualifying mirror-incident assay. Both assay-status fields are `not_evaluated` for
train.

In `reproduction.json`, `status` is `match` or `mismatch`, `release_match` is a boolean,
`difference_count` is an integer equal to the length of the string array `differences`, and
`output_files` is an order-insensitive array containing each of the six declared TSV filenames
exactly once. `match` denotes a true `release_match` with no differences; `mismatch` denotes a
false `release_match` with at least one reported difference.

## Report evidence contract

Explain how the configured individual-compound novelty and same-document target-mirroring screens
instantiate the paper-described leakage axes, and justify the source-backed interpretation and
claim limits; identify the earliest defect and minimal repair; compare at least two
distinct alternatives using controlled discriminators and explicit invariants; reconcile all
primary and secondary artifacts including no-effect rows; demonstrate row-order, opaque-ID, and
deeper-document generalization; reconcile ligand-novelty and target-context evidence; distinguish
novelty membership, target-mirroring evidence, assay eligibility, and prediction completeness;
interpret retained-assay performance and split aggregation at their actual units;
distinguish observations, source conventions, counterfactuals, and bounded inferences; and state
what this synthetic offline replay cannot establish.
