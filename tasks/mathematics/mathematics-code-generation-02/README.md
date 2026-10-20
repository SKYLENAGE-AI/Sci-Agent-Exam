# Mathematics Code Generation 02

## Source Record

- Title: "On the Existence of Optimal (v, 5, 1) and (v, 6, 1) Binary Cyclically Permutable Constant-Weight Codes"
- Authors: Tsonka Baicheva and Svetlana Topalova
- Venue/date: Axioms 2026, 15(1), article 35; published January 1, 2026
- Identifier: https://doi.org/10.3390/axioms15010035
- License and eligibility: Open-access CC-BY article, published after the benchmark cutoff, with the PDF mounted under `environment/data/`.

## Task Summary

This task asks the solver to implement a Python module for auditing binary cyclically permutable constant-weight codes (CPCWs) using the conventions in Baicheva and Topalova (2026). The submitted module must expose the documented public API, compute the structured `answer.json`, produce a short scientific report, and include self-tests.

The task is in the Mathematics domain, Combinatorics subdomain. It is configured as `SCI-11` / `Mathematics` in `task.toml`.

## Required Work

The solver must implement:

- residue normalization in `Z_v`;
- ordered modular difference lists for CPCW codewords;
- auto-correlation and cross-correlation checks from ordered difference multisets;
- CPCW validity, optimality against the source upper bound, perfectness, uncovered residues, and repeated differences;
- Appendix A row decoding for source-table codewords;
- Section 3.2 and Section 3.3 necessary-condition screening;
- source-claim summaries using mounted claim rows and the source article;
- policy summaries, final review recommendation, and blocker propagation.

The expected output artifacts are:

- `code/cpcw_audit.py`;
- `answer.json` with the documented top-level key order and row schemas;
- `report.md` with `Context`, `Methods`, `Results`, and `Limitations`;
- `tests/test_cpcw_audit.py` with at least one source-example test and one invalid-input test.

## Data And Coverage

The visible packet contains the source PDF, JSON inputs for codebook instances, feasibility cases, source claims, and review policy, plus a data dictionary, starter module, helper module, and public digest check.

Programmatic validation imports the submitted module and recomputes expected outputs independently. It checks both visible fixtures and hidden same-schema inputs covering:

- CPCW audit behavior on full and Appendix-format codebooks;
- invalid input handling;
- Section 3.2 and Section 3.3 screening cases;
- source-claim classification across Section 3.1, Tables 3-4, Appendix A, and mounted construction/screening evidence;
- certification policy rows;
- final recommendation and review blocker precedence;
- `answer.json` top-level key order.

Hidden cases use the same schemas and source rules as the visible packet while varying parameters, identifiers, marker classes, and policy interactions.

## Valid Implementation Approaches

Known valid approaches include direct set or `Counter`-based ordered-difference audits, equivalent modular arithmetic loops, deterministic enumeration of the small Section 3.2 screening systems, and any source-claim/review-policy pipeline that preserves the required API and output schema.

Implementations do not need to mirror the reference module structure. They must compute the same CPCW, screening, source-review, policy, and report outputs from the mounted inputs and the source article.

## Reviewer Notes

The README records the source identity, authors, DOI, publication date, license eligibility, task scope, hidden-case rationale, and valid implementation approaches.

The oracle and verifier are kept in sync: `solution/solve.py` emits the same review-blocker precedence explanation as `solution/report.md`, `answer.json` key order is enforced programmatically, and source-status identifier lists are sorted by the documented contract.

The rubric includes an explicit negative criterion, `Must NOT recommend final certification when blockers remain.`

Local validation for the current revision:

- Reference solution programmatic score: `1.0`.
- Oracle self-tests: `11 passed`.
- Public digest: `d92aa22439a3a3f474f63bd72c9838d089d850c3a74a5a62baa0a53590a632da`.
- Python compile and whitespace checks pass.
