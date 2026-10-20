# Context

Baicheva and Topalova (2026) define binary cyclically permutable constant-weight codes as k-subsets of Z_v whose translates satisfy auto-correlation and cross-correlation conditions. The implementation audits visible candidate codebooks against those definitions.

# Methods

Each codeword is represented as a sorted tuple of residues modulo v. Duplicate residues after reduction modulo v are rejected as invalid input. For a codeword C, the implementation computes the ordered modular difference multiset Delta C = {a - b mod v : a,b in C and a != b}. The auto-correlation check requires the k(k-1) ordered differences of each codeword to be distinct. The cross-correlation check requires the ordered difference sets of distinct codewords to be disjoint.
The starter's circular-distance screening profile is useful for triage, but it is not the paper's submitted audit convention because it collapses directed residues and can preserve a plausible but non-final review.
Rows tagged with the Appendix A table representation are expanded by prepending 0 before they are audited as k-subsets of Z_v.

The source upper bound is floor((v - 1)/(k(k - 1))). A valid codebook meeting that bound is reported as optimal. A valid codebook whose ordered differences cover every nonzero residue of Z_v is reported as perfect; otherwise an optimal codebook is an optimal partial case.
For optimal k(k-1)t+2 cases, the half-turn residue can be the single uncovered nonzero difference, but that gap still keeps the audited CPCW codebook outside the perfect category.

For length k(k-1)t+2 screens, the module uses Theorem 1 when v is congruent to 2 modulo 4 and Theorem 2 when v is congruent to 0 modulo 4. It records Section 3.3 as part of the screen when the specific recursive parity obstruction from the source excludes a case after the primary system has a nonnegative solution. The result remains a necessary-condition screen rather than an existence proof: a nonnegative primary-system solution is still only necessary.
The source claim review combines three evidence surfaces. Mounted optimal codebooks, Appendix entries, and known construction entries in the source tables give construction evidence. Screen or source exclusion markers give exclusion evidence. Section 3.1 source markers are resolved through the k=5 Table 3 or k=6 Table 4 status entry for the same length, and Section 3.2 source markers are resolved through the mounted feasibility screen row for the same parameter when present. Search-gap and question-mark source markers remain unresolved unless construction or exclusion evidence is also present.
The review recommendation follows the mounted recommendation policy after source-claim, parameter-review, and certification summaries have been computed.

# Results

Visible decisions: case_122_appendix_k5=optimal_partial, case_122_candidate_k6=valid_subbound, case_21_k5=optimal_perfect, case_43_alpha_k5=optimal_partial, case_43_beta_k5=invalid, case_43_gamma_k5=invalid, case_90_k5=optimal_partial.
Optimal visible instances are ['case_122_appendix_k5', 'case_21_k5', 'case_43_alpha_k5', 'case_90_k5'].
Perfect visible instances are ['case_21_k5'].
Invalid visible instances are ['case_43_beta_k5', 'case_43_gamma_k5'].
The case_43_alpha_k5 uncovered nonzero differences are [14, 29].
The case_90_k5 row follows the Appendix A table representation and reaches the source bound after expansion.
For case_43_alpha_k5, zero is not part of the nonzero-residue audit, and the remaining uncovered nonzero residues prevent perfectness while the codebook reaches the upper bound.
The case_43_gamma_k5 instance is invalid because repeated modular ordered differences violate the auto-correlation condition.
The case_43_beta_k5 instance is invalid because the two codewords share ordered modular differences.
The uncovered_nonzero_differences field lists residues absent from the union of ordered differences and diagnoses failure to be perfect, while repeated_ordered_differences diagnose auto-correlation or cross-correlation failures.
The first invalid visible instance is case_43_beta_k5.
Feasibility screen decisions: case_102_k5=excluded_by_primary_system, case_122_k6=survives_necessary_screen, case_152_k6=survives_necessary_screen, case_82_k5=survives_necessary_screen, case_92_k6=excluded_by_recursive_parity.
Parameter cases surviving the necessary-condition screen are ['case_122_k6', 'case_152_k6', 'case_82_k5'].
Parameter cases excluded by the necessary-condition screen are ['case_102_k5', 'case_92_k6'].
The Section 3.3 recursive parity certificate is applied as a case-level exclusion; surviving Section 3.2 rows remain unresolved by this mounted screen.
Parameter review decisions: v102_k5=excluded_by_screen, v122_k5=constructed_optimal, v122_k6=candidate_partial_evidence, v152_k6=unresolved_by_mounted_evidence, v21_k5=constructed_optimal, v43_k5=constructed_optimal, v82_k5=unresolved_by_mounted_evidence, v90_k5=constructed_optimal, v92_k6=excluded_by_screen.
Parameters with mounted optimal construction evidence are ['v122_k5', 'v21_k5', 'v43_k5', 'v90_k5'].
Parameters excluded by the mounted screen are ['v102_k5', 'v92_k6'].
Parameters unresolved by the mounted evidence are ['v122_k6', 'v152_k6', 'v82_k5'].
Source claim review decisions: v102_k5=excluded_by_source, v106_k6=constructed_optimal, v122_k5=constructed_optimal, v122_k6=unresolved_by_source, v123_k6=unresolved_by_source, v125_k6=constructed_optimal, v126_k5=constructed_optimal, v126_k6=unresolved_by_source, v143_k5=unresolved_by_source, v144_k5=unresolved_by_source, v151_k6=constructed_optimal, v167_k5=unresolved_by_source, v42_k5=excluded_by_source, v62_k6=constructed_optimal, v63_k6=constructed_optimal, v64_k6=excluded_by_source, v83_k5=constructed_optimal, v90_k5=constructed_optimal, v92_k6=excluded_by_source.
Source claims with construction evidence are ['v106_k6', 'v122_k5', 'v125_k6', 'v126_k5', 'v151_k6', 'v62_k6', 'v63_k6', 'v83_k5', 'v90_k5'].
Source claims with exclusion evidence are ['v102_k5', 'v42_k5', 'v64_k6', 'v92_k6'].
Source claims unresolved by the reviewed evidence are ['v122_k6', 'v123_k6', 'v126_k6', 'v143_k5', 'v144_k5', 'v167_k5'].
Policy review decisions: case_122_appendix_k5@full_difference_certificate=False, case_122_candidate_k6@full_difference_certificate=False, case_21_k5@full_difference_certificate=True, case_43_alpha_k5@full_difference_certificate=False, case_43_beta_k5@full_difference_certificate=False, case_43_gamma_k5@full_difference_certificate=False, case_90_k5@full_difference_certificate=False.
The full_difference_certificate policy requires CPCW validity, source-bound attainment, and zero uncovered nonzero differences. The Appendix 122-by-5 construction reaches the source bound but leaves one uncovered nonzero residue, so it remains outside that certification.
Across multiple policy rows, policy_certified_instance_ids and policy_uncertified_instance_ids are set summaries of any certified and any uncertified policy decisions, so an instance may appear in both lists when different policies disagree.
Policy-certified instances are ['case_21_k5'].
Policy-uncertified instances are ['case_122_appendix_k5', 'case_122_candidate_k6', 'case_43_alpha_k5', 'case_43_beta_k5', 'case_43_gamma_k5', 'case_90_k5'].
Review recommendation is requires_followup.
The submitted review_blockers list reflects the recommendation policy's selected requires_followup precedence rather than every nonempty diagnostic list in the summaries.
Review blockers are ['requires_followup:v122_k6', 'requires_followup:v123_k6', 'requires_followup:v126_k6', 'requires_followup:v143_k5', 'requires_followup:v144_k5', 'requires_followup:v152_k6', 'requires_followup:v167_k5', 'requires_followup:v82_k5'].

# Limitations

This implementation audits finite candidate codebooks; it does not search exhaustively for new optimal CPCW codes. The implementation assumes exact integer residues and does not certify isomorphism classes of cyclic partial designs. Large search problems for k=5 or k=6 remain outside this direct audit workflow.
