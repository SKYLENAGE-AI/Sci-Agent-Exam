# Data dictionary

Blank CSV cells mean "not reported" or "not identifiable" as specified below;
they are never numerical zero. Artifact IDs are opaque. Registry row order and
filenames do not confer authority.

## `artifact_registry.csv`

| Column | Meaning |
| --- | --- |
| `artifact_id` | Opaque identifier that must be propagated to derived outputs. |
| `path` | Path relative to the data directory. |
| `scientific_role` | Semantic role of the artifact. |
| `review_state` | `final` or `superseded`. |
| `claim_authority` | Boolean defining whether the artifact may support the final claim assessment. Exactly one `reported_segment_energetics` row is authoritative. |
| `superseded_by` | Replacement artifact ID when applicable. |
| `provenance` | Origin of the record. |

Code must select the row whose `scientific_role` is
`reported_segment_energetics`, `review_state` is `final`, and
`claim_authority` is true, then load the path recorded in that row.

## `reported_energetics.csv`

| Column | Meaning |
| --- | --- |
| `segment` | Reported reaction segment or comparison calculation. |
| `state` | Source label for a minimum or transition state. |
| `state_role` | Role within the reported segment. |
| `reference_zero` | State or reactant set assigned zero for that segment. |
| `delta_g_kcal_mol` | Gibbs energy at 298.15 K and 1 atm relative to `reference_zero`, kcal/mol. |
| `delta_e_wb97xd_kcal_mol` | omegaB97XD/def2-TZVPP electronic energy relative to the segment zero, kcal/mol. |
| `delta_e_dlpno_ccsdt_kcal_mol` | DLPNO-CCSD(T)/def2-TZVPP single point on the omegaB97XD geometry, relative to the segment zero, kcal/mol. |
| `imaginary_frequency_count` | Number of reported imaginary harmonic frequencies. |
| `irc_backward`, `irc_forward` | Adjacent minima reached by the reported IRC. |

`A -> TS1 -> B` is the carbonyl-insertion segment; `C -> TS2 -> D` is
H2 activation/product-complex formation. `UNCAT_TS` is a comparison transition
state relative to its own reactants.

## `screening_summary.csv`

This is the result identified by its matching registry row. Its fields are a
derived cycle energy span, predicted turnover frequency, rate-control state,
largest transition-state electronic-method discrepancy, cycle-status label,
and claim verdict. Interpret these fields only within the artifact's registry
status and provenance.

## Mechanistic tables

`natural_charges.csv` reports natural atomic charges in |e| for omegaB97XD and
M06. `bond_metrics.csv` reports selected distances in angstrom. Atom and state
labels follow the source; blank cells mean the label is absent in that state.

## `calculation_settings.json`

The constants are exact task inputs. `barrier_sensitivity_kcal_mol` is a
deterministic symmetric perturbation, not a standard error, probability model,
or confidence interval.

## Required `bounded_calculations.csv` metrics

| Metric | Unit |
| --- | --- |
| `k_ts1_298_s_inv` | `s^-1` |
| `k_ts2_298_s_inv` | `s^-1` |
| `segment_rate_ratio_ts1_to_ts2` | `dimensionless` |
| `k_ts2_minus_perturbation_298_s_inv` | `s^-1` |
| `k_ts2_plus_perturbation_298_s_inv` | `s^-1` |
| `barrier_acceleration_vs_uncatalyzed` | `dimensionless` |
| `delta_e_method_ts1_kcal_mol` | `kcal/mol` |
| `delta_e_method_ts2_kcal_mol` | `kcal/mol` |

## Required `reference_audit.csv` comparisons

`comparison` names encode signed `lhs - rhs` differences:

| Comparison | LHS | RHS |
| --- | --- | --- |
| `ts1_minus_a` | TS1 | A |
| `ts2_minus_c` | TS2 | C |
| `c_minus_b` | C | B |
| `d_minus_a` | D | A |

`status` is `identifiable` only when both states' reported Gibbs energies use
the same `reference_zero`; otherwise it is `not_identifiable`.

## Decision semantics

The compound claim has two parts: supported local elementary chemistry and an
identifiable turnover-capable cycle.

- `supported`: the authoritative records validate the required local
  transition states/IRCs, place the requested cycle comparisons on one Gibbs
  reference, and contain a released-product plus regenerated-catalyst state.
- `partially_supported`: the local transition-state/IRC evidence is valid, but
  at least one required cross-segment comparison or the released-product plus
  regenerated-catalyst state is absent.
- `not_supported`: authoritative records contradict the proposed local
  transition-state connectivity.
- `inconclusive`: the authoritative artifact lacks enough stationary-point
  information to decide whether the local steps are valid.

`cycle_energy_span_status` is `identifiable` only when both requested
cross-segment comparisons are identifiable and a row with
`state_role=released_product_and_regenerated_catalyst` is present.
`turnover_frequency_status` follows the same eligibility boundary for this
task; the actual microkinetic value is not requested. These semantics define
eligibility, not a claim that a calculated cycle is experimentally realized.
