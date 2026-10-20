# Mounted data contract

All TSV files are UTF-8 with a header and tab separators. Identifiers are opaque strings and rows
may be permuted without changing mapped-back scientific results. Empty fields and literal `NA` are
missing. Generated TSVs use literal `NA`. This document defines schemas, joins, units, fixed
technical conventions, completeness, and serialization. The mounted paper remains the scientific
authority for individual-ligand novelty and same-document target-mirroring conventions.

## Public fixture

The deterministic purpose-built ChEMBL-style fixture is under
`/home/agent/data/broken_project/fixtures/public/`. It is not a redistributed ChEMBL extract.
`fixture_manifest.json` records raw counts and SHA-256 hashes.

### `activities.tsv`

`record_id` is unique. An assay maps to exactly one split, document, target, standard type, and
source-document year.
Exact duplicate assay-ligand records may occur only when relation, experimental value, and
prediction agree; they represent duplicate records, not additional unique compounds.

| Column | Type / unit | Definition |
| :--- | :--- | :--- |
| `record_id` | string | Unique activity-row identifier. |
| `split` | enum | `train`, `validation`, or `test`. |
| `doc_chembl_id` | string | Source-document identifier. |
| `assay_chembl_id` | string | Assay identifier. |
| `target_chembl_id` | string | Single-protein target identifier. |
| `ligand_chembl_id` | string | Compound identifier. |
| `standard_type` | enum | `IC50`, `Ki`, or `Kd`; each assay uses one type. |
| `pchembl_relation` | enum | Reported relation `=`, `>`, or `<`. |
| `pchembl_value_filled` | float, pChEMBL | Experimental `-log10(molar)` affinity; empty or `NA` is missing. |
| `prediction` | float, pChEMBL | Model prediction; empty or `NA` is missing. |

### `compound_fingerprints.tsv`

Exactly one row is present for every `ligand_chembl_id` in `activities.tsv`. A compound may occur
in several assays, documents, or splits.

| Column | Type / unit | Definition |
| :--- | :--- | :--- |
| `ligand_chembl_id` | string | Compound identifier and join key to `activities.tsv`. |
| `earliest_publication_year` | integer year | Earliest ChEMBL publication year represented by the full mounted compound catalog; it may predate every source document in which that compound appears in mounted activities. |
| `fingerprint_hex` | 512-character lowercase hexadecimal string | One synthetic 2048-bit binary fingerprint. Decode as ordinary big-endian hexadecimal; bit positions are compared consistently across compounds. |

Tanimoto similarity is dimensionless and equals the number of set bits in the intersection divided
by the number of set bits in the union. A zero-union comparison has similarity `1.0`. The fixture
provides precomputed binary fingerprints, so no structure parsing or fingerprint generation is
required. They exercise the paper's 2048-bit Morgan/Tanimoto interface but do not represent real
molecules.

### `assay_documents.tsv`

Exactly one row per `assay_chembl_id`, with columns `assay_chembl_id`, `doc_chembl_id`, and
`document_year`. `document_year` is the integer publication year of that assay's source document.
The assay-to-document mapping must match `activities.tsv`, and every assay mapped to the same
document must have the same year and split. Missing, extra, nonintegral, or conflicting values are
invalid.

### `target_identity.tsv`

Exactly one row is present for every distinct unordered target pair induced by assays that
co-occur in a mounted document. Required columns are `target_a`, `target_b`, and
`sequence_identity`. Rows use canonical identity `target_a < target_b`; duplicates, diagonals,
missing pairs, and extra pairs are invalid. `sequence_identity` is overall target-sequence identity,
dimensionless in `[0,1]`, or `NA`. A same-target assay pair needs no diagonal row and has identity
`1.0` by definition. Lookup is unordered even though generated target fields follow assay order.

### `release_summary.tsv`

One row with identity `fixture=public` and nonnegative integer fields `n_splits`, `n_documents`,
`n_assays`, and `n_activity_rows`. It is read-only input-coverage evidence and is never an input to
novelty, eligibility, retention, or performance.

## Fixed analysis values

`analysis_config.json` supplies fixed operational values. The assay/readout unit is
`(split, doc_chembl_id, assay_chembl_id, standard_type)`; each mounted assay has one readout.

The configured novelty tier applies to exact `validation` and `test` labels and has an exclusive
maximum Tanimoto similarity of `0.35`. The configured reference cutoff is 2022 for validation and
2023 for test; these values are fixture policy, not values reported by the mounted paper. A year
predates a cutoff only when it is strictly smaller. The mounted paper resolves the scientific
role of compound catalog provenance relative to source-document chronology. Train is not assigned
to the configured evaluation tier.

Reference comparisons do not exclude the query identifier. If the source-consistent reference
population contains the same `ligand_chembl_id` as the query, that row is eligible for comparison
and has Tanimoto similarity `1.0` to itself. This is a fixed technical convention for the replay,
not a claim about a separate chemical entity.

The validation and test policies apply to exact split labels. Their experimental population:

- retains only `pchembl_relation = "="` rows;
- excludes missing experimental pChEMBL without imputation;
- collapses exact duplicate `(assay_chembl_id, standard_type, ligand_chembl_id)` records;
- counts unique compounds in that resulting population;
- computes experimental pChEMBL sample SD with `ddof=1`;
- uses inclusive thresholds of at least 10 unique compounds and SD at least 0.5;
- limits each document to at most one retained assay;
- defines assay size as the resulting unique-compound count; and
- resolves an exact size tie by lexicographically smallest `assay_chembl_id`, then
  `standard_type`.

The mounted paper resolves how compound novelty, shared assay-pair evidence, target identity, and
activity correlation define the scientific evidence units. The supplied fixture policy applies a
separate target-mirroring exclusion in validation and test: an otherwise qualifying assay incident
to at least one `target_mirroring` pair has final status `target_mirroring_excluded`. This
exclusion precedence is a task configuration, not a claim that the paper prescribes a production
filter. The `train` split is outside both configured eligibility policies and remains unchanged.
Missing predictions can change performance completeness but never novelty, target-mirroring
evidence, eligibility, or retention.

## Generated artifacts

### `compound_novelty.tsv`

Complete row domain: every `(split, ligand_id)` combination induced by the distinct compounds in
each `activities.tsv` split, including in-tier, out-of-tier, and train-control rows. Required
columns:

`split`, `ligand_id`, `earliest_publication_year`, `first_mounted_document_year`,
`reference_cutoff_year`, `max_tanimoto`, `nearest_reference_ligand_id`,
`in_configured_tier`, `novelty_status`.

`first_mounted_document_year` is the minimum `document_year` among that compound's mounted
activity rows. It is a required diagnostic trace and can differ from
`earliest_publication_year`; neither field may be missing for a mounted compound.

For validation and test, `max_tanimoto` is the compound's maximum similarity under the
source-consistent cutoff reference population. Exact maximum-similarity ties use the
lexicographically smallest reference identifier. `in_configured_tier` is `True` exactly when the
maximum is strictly less than `0.35`; status is `in_tier` or `out_of_tier`. For train,
`reference_cutoff_year`, `max_tanimoto`, and `nearest_reference_ligand_id` are `NA`,
`in_configured_tier` is `NA`, and status is `not_evaluated`.
If a configured cutoff has no reference compounds, `max_tanimoto` is `0.0` and
`nearest_reference_ligand_id` is `NA`.

### `assay_pair_audit.tsv`

Complete row domain: every canonical unordered pair of distinct assays in each mounted document,
including target-mirroring, rejected, undefined, train-control, and no-effect pairs. Row identity
is `(split, document_id, assay_a, standard_type_a, assay_b, standard_type_b)`, with
`assay_a < assay_b`. Required columns:

`split`, `document_id`, `assay_a`, `standard_type_a`, `assay_b`, `standard_type_b`, `target_a`,
`target_b`, `n_shared_compounds`, `target_identity`, `pearson_r`, `r2`, `pair_status`,
`policy_applies`, `mirroring_flag`.

`target_a` and `target_b` correspond to `assay_a` and `assay_b`; the sequence-identity lookup is
canonicalized independently. Pair evidence uses the source-consistent assay-pair population. A
shared compound has `pchembl_relation = "="` and finite experimental pChEMBL in both assays after
exact duplicate collapse. `n_shared_compounds` counts those paired compound identifiers. Pearson
`r` is computed on their paired pChEMBL values and is defined only with at least two pairs and
nonconstant values on both sides; `r2 = r ** 2`.

`pair_status` uses this precedence: `too_few_shared_compounds`, `missing_target_identity`,
`target_identity_not_below_threshold`, `undefined_correlation`, `low_correlation`, then
`target_mirroring`. A target-mirroring pair has at least 10 shared compounds, overall sequence
identity strictly below `0.90`, and R-squared at least `0.60`. `mirroring_flag` is `True` exactly
for that status. `policy_applies` is `True` for validation/test and `False` for train. Train rows
are audited as evidence but never trigger the configured exclusion.

### `assay_inventory.tsv`

Complete row domain: every assay/readout unit present in `activities.tsv`, including affected,
unaffected, ineligible, qualifying-but-not-retained, and retained units. Required columns:

`split`, `document_id`, `assay_id`, `standard_type`, `n_input_rows`, `n_tier_rows`,
`n_unique_compounds`, `experimental_sd`, `base_eligibility_status`,
`target_mirroring_pair_count`, `mirroring_policy_applies`, `eligibility_status`, `retained`.

`n_tier_rows` is the number of mounted activity rows in the source-consistent configured analysis
population before relation filtering, experimental-missing removal, and exact duplicate collapse.
For train it equals `n_input_rows`.

For validation/test, `base_eligibility_status` is exactly one of
`too_few_unique_compounds`, `undefined_experimental_sd`, `low_experimental_sd`, or `qualifying`,
with precedence given in the configuration. `target_mirroring_pair_count` is the number of
policy-active `target_mirroring` rows incident to that assay. `mirroring_policy_applies` is `True`
for validation/test and `False` for train. Final `eligibility_status` equals the base status
unless an otherwise qualifying assay is incident to at least one target-mirroring pair, in which
case it is `target_mirroring_excluded`. Train has `not_evaluated` for both statuses, is not
excluded, and has pair count `0`. `retained` serializes as `True` or `False`.

### `document_retention.tsv`

Complete row domain: every `(split, document_id)`, including documents with no qualifying or no
retained assay. Required columns:

`split`, `document_id`, `n_candidate_assays`, `n_base_qualifying_assays`,
`n_target_mirroring_pairs`, `n_mirroring_excluded_assays`, `n_qualifying_assays`,
`n_retained_assays`, `retained_assay_sha256`.

`n_candidate_assays` counts mounted assay/readout units in the document, and
`n_base_qualifying_assays` counts `base_eligibility_status = "qualifying"` units.
`n_qualifying_assays` counts final `eligibility_status = "qualifying"` units.
`n_target_mirroring_pairs` counts complete audit rows for the document with status
`target_mirroring`; `n_mirroring_excluded_assays` counts distinct validation/test assays whose
final status is `target_mirroring_excluded`. For train, `n_base_qualifying_assays` and
`n_qualifying_assays` are `NA`, and `n_mirroring_excluded_assays` is `0` because exclusion does
not apply, while the observed pair count remains numeric. The digest is SHA-256 of UTF-8 text
formed by sorting retained assay IDs, joining with newline characters, and appending one final
newline. An empty membership hashes the empty byte string.

### `assay_performance.tsv`

Complete row domain: every retained assay/readout unit. Required columns:

`split`, `document_id`, `assay_id`, `standard_type`, `n_complete_predictions`, `pearson_r`, `r2`,
`mae`.

Performance uses rows retained by the submitted assay filter. Within each assay, experimental and
predicted pChEMBL must both be finite. Pearson `r` is defined only with at least two complete pairs
and nonconstant values on both sides; `r2 = r ** 2`. MAE is in pChEMBL. Undefined values are `NA`.

### `summary.tsv`

Complete row domain: `test`, `train`, and `validation`, one row each. Required columns:

`split`, `n_documents`, `n_candidate_assays`, `n_tier_compounds`,
`n_base_qualifying_assays`, `n_target_mirroring_pairs`, `n_mirroring_excluded_assays`,
`n_qualifying_assays`, `n_retained_assays`, `n_evaluable_assays`, `mean_r2`,
`retained_assay_sha256`.

`n_tier_compounds` counts distinct compound identifiers in the configured analysis population;
for train it counts all distinct train compounds. Pair and excluded-assay counts aggregate the
document fields. Train `n_base_qualifying_assays` and `n_qualifying_assays` are `NA`, while
`n_mirroring_excluded_assays` is `0`.
`mean_r2` is the unweighted arithmetic mean across retained assays with defined R-squared. The
membership digest uses the same serialization as `document_retention.tsv` over all retained assays
in the split.

### `reproduction.json`

Required fields are `status` (`match` or `mismatch`), `release_match` (boolean),
`difference_count` (integer), `differences` (array of strings), and `output_files`.
`output_files` contains `compound_novelty.tsv`, `assay_pair_audit.tsv`, `assay_inventory.tsv`,
`document_retention.tsv`, `assay_performance.tsv`, and `summary.tsv` exactly once each. The receipt
records only the coarse release comparison and does not replace any table.

Finite floats compare with absolute tolerance `1e-6` and relative tolerance `1e-9`. Integer-valued
fields compare numerically and must be integral. Identifiers, statuses, booleans, digests, and
missing tokens compare exactly. Additional columns are permitted; additional, duplicate, or
omitted rows are not.
