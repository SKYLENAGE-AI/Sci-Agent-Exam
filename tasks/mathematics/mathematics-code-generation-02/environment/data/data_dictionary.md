Input files are mounted under `/home/agent/data/`.

`axioms-15-00035-v2.pdf` is the source article. Relevant locations include Section 1.1, Section 3.1, Sections 3.2-3.3, Tables 3-4, and Appendix A.

The starter project is mounted under `/home/agent/data/starter/`.

`cpcw_instances.json` contains candidate codebooks to audit. Each instance has:

- `id`: stable string identifier.
- `v`: modulus for `Z_v`.
- `k`: required codeword weight.
- `codeword_format`: representation tag. Values are `full` and `appendix_a`; `appendix_a` refers to Appendix A in the source article.
- `codewords`: array of candidate codeword rows, represented as integer residues according to `codeword_format`.

`cpcw_feasibility_cases.json` contains parameter cases for the necessary-condition screen from the source article. Each case has:

- `id`: stable string identifier.
- `v`: code length.
- `k`: codeword weight.
- `source_section`: paper section pointer for the screening definitions.

The direct callable `screen_parameters(v, k)` returns the computed fields `v`, `k`, `t`, `residue_class_mod_4`, `screen_sections`, `primary_solution_count`, and `necessary_status`. The case `id` belongs to mounted feasibility rows and is added by `run_audit` when it builds `feasibility_summaries`.

Direct callable return contracts:

- `normalize_codeword(v, codeword)` returns an ascending tuple of distinct integer residues reduced modulo `v`.
- `ordered_differences(v, codeword)` returns the sorted difference-list values for one codeword.
- `audit_codebook(v, k, codewords)` returns a dictionary with exactly these keys: `v`, `k`, `bound`, `codeword_count`, `auto_valid`, `cross_valid`, `is_cpcw`, `is_optimal`, `is_perfect`, `uncovered_nonzero_differences`, `repeated_ordered_differences`, and `decision`.
- `screen_parameters(v, k)` returns a dictionary with exactly the computed fields named above.
- `run_audit(...)` returns the complete `answer.json` mapping with the top-level keys and schemas below.

`cpcw_source_claims.json` contains parameter claim rows to review against mounted construction evidence, screening evidence, and source article markers. Each claim has:

- `id`: stable string identifier.
- `v`: code length.
- `k`: codeword weight.
- `source_marker`: paper marker string copied into the local review sheet. Marker strings use the form `<paper_anchor>_v<length>`, with anchors such as `appendix_a`, `table_3`, `table_4`, `section_3_1`, `section_3_2`, and `section_3_3`.

Use the source article location indicated by `source_marker` when preparing source-claim rows. Section markers are paper anchors; the claim row's `v` and `k` identify the parameter being reviewed.

`cpcw_review_policy.json` contains certification policy rows. Each policy has:

- `id`: stable string identifier.
- `requires_cpcw`: Boolean.
- `requires_bound_attainment`: Boolean.
- `max_uncovered_nonzero`: integer.

It may also contain `review_recommendation_policy` with:

- `status_precedence`: recommendation values in precedence order.
- `followup_fields`: answer-list fields that trigger follow-up.
- `withhold_fields`: answer-list fields that trigger withholding.
- `certification_fields`: answer-list fields used for certification closure.
- `blocker_templates`: string templates for `review_blockers`, keyed by the field category names above.

Use `review_recommendation_policy` when preparing `review_recommendation` and `review_blockers`.

`cpcw_profile_helper.py` is a Python helper included with the packet.

Output lists of differences must use residues from `1` through `v-1`, sorted ascending. Summary row collections in `answer.json` are ordered by their stable identifiers: `id`, `parameter_id`, or `(policy_id, instance_id)`. Derived identifier lists and `review_blockers` are sorted ascending by string value. Derived lists named `*_parameter_ids` are unique parameter-ID sets.

`answer.json` must be a JSON object with exactly these top-level keys in this order:

1. `instance_summaries`
2. `optimal_instance_ids`
3. `perfect_instance_ids`
4. `invalid_instance_ids`
5. `case_43_alpha_uncovered_nonzero`
6. `first_invalid_instance`
7. `feasibility_summaries`
8. `screened_surviving_ids`
9. `screened_excluded_ids`
10. `parameter_review_summaries`
11. `constructed_parameter_ids`
12. `screen_excluded_parameter_ids`
13. `unresolved_parameter_ids`
14. `source_claim_summaries`
15. `source_constructed_parameter_ids`
16. `source_excluded_parameter_ids`
17. `source_unresolved_parameter_ids`
18. `policy_summaries`
19. `policy_certified_instance_ids`
20. `policy_uncertified_instance_ids`
21. `review_recommendation`
22. `review_blockers`

Each `instance_summaries` row contains exactly `id`, `v`, `k`, `bound`, `codeword_count`, `auto_valid`, `cross_valid`, `is_cpcw`, `is_optimal`, `is_perfect`, `uncovered_nonzero_differences`, `repeated_ordered_differences`, and `decision`. The decision enum is `optimal_perfect`, `optimal_partial`, `valid_subbound`, or `invalid`.

Difference-list fields are sorted residue values.

`case_43_alpha_uncovered_nonzero` is the sorted `uncovered_nonzero_differences` list for `case_43_alpha_k5`, or `null` when absent. `first_invalid_instance` is the first invalid instance ID in sorted `id` order, or `null` when absent.

Each `feasibility_summaries` row contains exactly `id`, `v`, `k`, `t`, `residue_class_mod_4`, `screen_sections`, `primary_solution_count`, and `necessary_status`.

Each `parameter_review_summaries` row contains exactly `parameter_id`, `v`, `k`, `candidate_instance_ids`, `optimal_candidate_ids`, `screen_case_ids`, `screen_status`, and `evidence_status`. `parameter_id` is `v{v}_k{k}`. `evidence_status` is `constructed_optimal`, `excluded_by_screen`, `candidate_partial_evidence`, or `unresolved_by_mounted_evidence`.

For parameter summaries, `screened_surviving_ids` lists rows whose `necessary_status` is `survives_necessary_screen`. `screened_excluded_ids` lists rows whose `necessary_status` is `excluded_by_primary_system` or `excluded_by_recursive_parity`.

Parameter review summaries combine audited candidate-instance evidence and parameter-case screening evidence.

Source claim summaries combine audited candidate-instance evidence, parameter-case screening evidence, and source claim rows.

Each `source_claim_summaries` row contains exactly `id`, `parameter_id`, `v`, `k`, `source_marker`, `candidate_instance_ids`, `screen_case_ids`, and `claim_status`. `claim_status` is `constructed_optimal`, `excluded_by_source`, or `unresolved_by_source`.

Policy summaries combine audited candidate-instance evidence and policy rows.

Each `policy_summaries` row contains exactly `policy_id`, `instance_id`, `uncovered_nonzero_count`, and `certified`.

`policy_certified_instance_ids` is the sorted set of instance IDs certified by at least one policy row. `policy_uncertified_instance_ids` is the sorted set of instance IDs uncertified by at least one policy row. These two lists can overlap when different policy rows make different certification decisions for the same instance.

Review recommendation fields combine source claim, parameter review, and policy summaries.

`review_recommendation` is `requires_followup`, `withhold_for_exclusion`, or `certify_complete`. Evaluate `status_precedence` in order and select the first status whose configured fields contain at least one value. `review_blockers` contains the `blocker_templates` expansions for that selected status. If only certification fields contain values, use `requires_followup` with the certification-field blockers. If no configured fields contain values, use `certify_complete` and an empty blocker list.
