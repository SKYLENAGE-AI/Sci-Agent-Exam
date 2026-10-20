Implement the CPCW audit module for the local reviewer packet. The audit supports review of CPCW validity, optimality, and construction or exclusion evidence for parameter claims in the source article. Use the source paper `/home/agent/data/axioms-15-00035-v2.pdf`, the mounted JSON inputs, `/home/agent/data/data_dictionary.md`, and the starter project at `/home/agent/data/starter/` to produce artifacts.

## Deliverables

1. `/home/agent/results/code/cpcw_audit.py`, an importable Python module exposing `normalize_codeword(v, codeword)`, `ordered_differences(v, codeword)`, `audit_codebook(v, k, codewords)`, `screen_parameters(v, k)`, and `run_audit(data_path="/home/agent/data/cpcw_instances.json", feasibility_path="/home/agent/data/cpcw_feasibility_cases.json", claims_path="/home/agent/data/cpcw_source_claims.json", policy_path="/home/agent/data/cpcw_review_policy.json")`.
2. `/home/agent/results/answer.json`, using exactly the top-level key order and row schemas defined in `/home/agent/data/data_dictionary.md`.
3. `/home/agent/results/report.md`, with sections `Context`, `Methods`, `Results`, and `Limitations`. Cite Baicheva and Topalova (2026), explain how the audit and review use the source article and mounted inputs, summarize the submitted results and recommendation, and include at least two limitations.
4. `/home/agent/results/tests/test_cpcw_audit.py`, a self-contained Python test file with at least two tests, including one test for the paper's `(43,5,1)` example and one invalid-input test that expects `ValueError`.

The module must compute from its inputs and must work on additional data paths with the documented schemas passed to `run_audit`. Raise `ValueError` for non-integer or nonpositive `v`, non-integer `k`, `k < 2`, empty codebooks, non-integer residues, duplicate residues within a codeword after reduction modulo `v`, or codewords whose size differs from `k`.
