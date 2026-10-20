from __future__ import annotations

import json
import importlib.util
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(os.environ.get("AGENT_ROOT", "/home/agent"))
RESULTS = Path(os.environ.get("RESULTS_DIR", str(ROOT / "results")))
DATA = Path(os.environ.get("DATA_PATH", str(ROOT / "data" / "cpcw_instances.json")))
FEASIBILITY_DATA = Path(
    os.environ.get("FEASIBILITY_DATA_PATH", str(ROOT / "data" / "cpcw_feasibility_cases.json"))
)
CLAIMS_DATA = Path(os.environ.get("CLAIMS_DATA_PATH", str(ROOT / "data" / "cpcw_source_claims.json")))
POLICY_DATA = Path(os.environ.get("POLICY_DATA_PATH", str(ROOT / "data" / "cpcw_review_policy.json")))
MODULE_SOURCE = Path(__file__).with_name("code") / "cpcw_audit.py"


def _load_solution_module():
    spec = importlib.util.spec_from_file_location("cpcw_audit_solution", MODULE_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load solution module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    global RESULTS
    if len(sys.argv) > 1:
        RESULTS = Path(sys.argv[1])
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "code").mkdir(parents=True, exist_ok=True)
    (RESULTS / "tests").mkdir(parents=True, exist_ok=True)

    module_dest = RESULTS / "code" / "cpcw_audit.py"
    if MODULE_SOURCE.resolve() != module_dest.resolve():
        shutil.copyfile(MODULE_SOURCE, module_dest)

    module = _load_solution_module()
    answer = module.run_audit(DATA, FEASIBILITY_DATA, CLAIMS_DATA, POLICY_DATA)
    (RESULTS / "answer.json").write_text(json.dumps(answer, indent=2) + "\n", encoding="utf-8")

    report = [
        "# Context",
        "",
        "Baicheva and Topalova (2026) define binary cyclically permutable constant-weight codes as k-subsets of Z_v whose translates satisfy auto-correlation and cross-correlation conditions. The implementation audits visible candidate codebooks against those definitions.",
        "",
        "# Methods",
        "",
        "Each codeword is represented as a sorted tuple of residues modulo v. Duplicate residues after reduction modulo v are rejected as invalid input. For a codeword C, the implementation computes the ordered modular difference multiset Delta C = {a - b mod v : a,b in C and a != b}. The auto-correlation check requires the k(k-1) ordered differences of each codeword to be distinct. The cross-correlation check requires the ordered difference sets of distinct codewords to be disjoint.",
        "The starter's circular-distance screening profile is useful for triage, but it is not the paper's submitted audit convention because it collapses directed residues and can preserve a plausible but non-final review.",
        "Rows tagged with the Appendix A table representation are expanded by prepending 0 before they are audited as k-subsets of Z_v.",
        "",
        "The source upper bound is floor((v - 1)/(k(k - 1))). A valid codebook meeting that bound is reported as optimal. A valid codebook whose ordered differences cover every nonzero residue of Z_v is reported as perfect; otherwise an optimal codebook is an optimal partial case.",
        "For optimal k(k-1)t+2 cases, the half-turn residue can be the single uncovered nonzero difference, but that gap still keeps the audited CPCW codebook outside the perfect category.",
        "",
        "For length k(k-1)t+2 screens, the module uses Theorem 1 when v is congruent to 2 modulo 4 and Theorem 2 when v is congruent to 0 modulo 4. It records Section 3.3 as part of the screen when the specific recursive parity obstruction from the source excludes a case after the primary system has a nonnegative solution. The result remains a necessary-condition screen rather than an existence proof: a nonnegative primary-system solution is still only necessary.",
        "The source claim review combines three evidence surfaces. Mounted optimal codebooks, Appendix entries, and known construction entries in the source tables give construction evidence. Screen or source exclusion markers give exclusion evidence. Section 3.1 source markers are resolved through the k=5 Table 3 or k=6 Table 4 status entry for the same length, and Section 3.2 source markers are resolved through the mounted feasibility screen row for the same parameter when present. Search-gap and question-mark source markers remain unresolved unless construction or exclusion evidence is also present.",
        "The review recommendation follows the mounted recommendation policy after source-claim, parameter-review, and certification summaries have been computed.",
        "",
        "# Results",
        "",
        "Visible decisions: "
        + ", ".join(f"{row['id']}={row['decision']}" for row in answer["instance_summaries"])
        + ".",
        f"Optimal visible instances are {answer['optimal_instance_ids']}.",
        f"Perfect visible instances are {answer['perfect_instance_ids']}.",
        f"Invalid visible instances are {answer['invalid_instance_ids']}.",
        f"The case_43_alpha_k5 uncovered nonzero differences are {answer['case_43_alpha_uncovered_nonzero']}.",
        "The case_90_k5 row follows the Appendix A table representation and reaches the source bound after expansion.",
        "For case_43_alpha_k5, zero is not part of the nonzero-residue audit, and the remaining uncovered nonzero residues prevent perfectness while the codebook reaches the upper bound.",
        "The case_43_gamma_k5 instance is invalid because repeated modular ordered differences violate the auto-correlation condition.",
        "The case_43_beta_k5 instance is invalid because the two codewords share ordered modular differences.",
        "The uncovered_nonzero_differences field lists residues absent from the union of ordered differences and diagnoses failure to be perfect, while repeated_ordered_differences diagnose auto-correlation or cross-correlation failures.",
        f"The first invalid visible instance is {answer['first_invalid_instance']}.",
        "Feasibility screen decisions: "
        + ", ".join(f"{row['id']}={row['necessary_status']}" for row in answer["feasibility_summaries"])
        + ".",
        f"Parameter cases surviving the necessary-condition screen are {answer['screened_surviving_ids']}.",
        f"Parameter cases excluded by the necessary-condition screen are {answer['screened_excluded_ids']}.",
        "The Section 3.3 recursive parity certificate is applied as a case-level exclusion; surviving Section 3.2 rows remain unresolved by this mounted screen.",
        "Parameter review decisions: "
        + ", ".join(f"{row['parameter_id']}={row['evidence_status']}" for row in answer["parameter_review_summaries"])
        + ".",
        f"Parameters with mounted optimal construction evidence are {answer['constructed_parameter_ids']}.",
        f"Parameters excluded by the mounted screen are {answer['screen_excluded_parameter_ids']}.",
        f"Parameters unresolved by the mounted evidence are {answer['unresolved_parameter_ids']}.",
        "Source claim review decisions: "
        + ", ".join(f"{row['parameter_id']}={row['claim_status']}" for row in answer["source_claim_summaries"])
        + ".",
        f"Source claims with construction evidence are {answer['source_constructed_parameter_ids']}.",
        f"Source claims with exclusion evidence are {answer['source_excluded_parameter_ids']}.",
        f"Source claims unresolved by the reviewed evidence are {answer['source_unresolved_parameter_ids']}.",
        "Policy review decisions: "
        + ", ".join(f"{row['instance_id']}@{row['policy_id']}={row['certified']}" for row in answer["policy_summaries"])
        + ".",
        "The full_difference_certificate policy requires CPCW validity, source-bound attainment, and zero uncovered nonzero differences. The Appendix 122-by-5 construction reaches the source bound but leaves one uncovered nonzero residue, so it remains outside that certification.",
        "Across multiple policy rows, policy_certified_instance_ids and policy_uncertified_instance_ids are set summaries of any certified and any uncertified policy decisions, so an instance may appear in both lists when different policies disagree.",
        f"Policy-certified instances are {answer['policy_certified_instance_ids']}.",
        f"Policy-uncertified instances are {answer['policy_uncertified_instance_ids']}.",
        f"Review recommendation is {answer['review_recommendation']}.",
        "The submitted review_blockers list reflects the recommendation policy's selected requires_followup precedence rather than every nonempty diagnostic list in the summaries.",
        f"Review blockers are {answer['review_blockers']}.",
        "",
        "# Limitations",
        "",
        "This implementation audits finite candidate codebooks; it does not search exhaustively for new optimal CPCW codes. The implementation assumes exact integer residues and does not certify isomorphism classes of cyclic partial designs. Large search problems for k=5 or k=6 remain outside this direct audit workflow.",
        "",
    ]
    (RESULTS / "report.md").write_text("\n".join(report), encoding="utf-8")

    tests = '''\
import importlib.util
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "code" / "cpcw_audit.py"
spec = importlib.util.spec_from_file_location("cpcw_audit", module_path)
cpcw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpcw)


def test_case_43_alpha_uncovered_differences():
    row = cpcw.audit_codebook(
        43,
        5,
        [[0, 1, 3, 7, 19], [0, 5, 13, 22, 33]],
    )
    assert row["is_optimal"]
    assert not row["is_perfect"]
    assert row["uncovered_nonzero_differences"] == [14, 29]


def test_plus_two_optimal_case_is_not_perfect():
    row = cpcw.audit_codebook(
        122,
        5,
        [
            [0, 1, 3, 21, 33],
            [0, 10, 34, 93, 106],
            [0, 8, 36, 76, 111],
            [0, 6, 51, 58, 113],
            [0, 4, 42, 85, 99],
            [0, 5, 49, 74, 105],
        ],
    )
    assert row["is_optimal"]
    assert not row["is_perfect"]
    assert row["uncovered_nonzero_differences"] == [61]


def test_duplicate_residues_raise_value_error():
    try:
        cpcw.audit_codebook(7, 3, [[0, 7, 1]])
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate residues modulo v should raise ValueError")


def test_parameter_screen_uses_residue_class_branch():
    screen_82 = cpcw.screen_parameters(82, 5)
    assert screen_82["primary_solution_count"] == 1
    assert screen_82["necessary_status"] == "survives_necessary_screen"
    assert cpcw.screen_parameters(102, 5)["necessary_status"] == "excluded_by_primary_system"
    screen_92 = cpcw.screen_parameters(92, 6)
    assert screen_92["screen_sections"] == ["Section 3.2", "Section 3.3"]
    assert screen_92["necessary_status"] == "excluded_by_recursive_parity"


def test_appendix_table_row_is_expanded_by_run_audit(tmp_path):
    data = {
        "instances": [
            {
                "id": "appendix_sample",
                "v": 90,
                "k": 5,
                "codeword_format": "appendix_a",
                "codewords": [[1, 3, 7, 18], [5, 25, 33, 52]],
            }
        ]
    }
    feasibility = {"cases": [{"id": "case_82_k5", "v": 82, "k": 5}]}
    data_path = tmp_path / "instances.json"
    feasibility_path = tmp_path / "feasibility.json"
    data_path.write_text(__import__("json").dumps(data), encoding="utf-8")
    feasibility_path.write_text(__import__("json").dumps(feasibility), encoding="utf-8")
    result = cpcw.run_audit(str(data_path), str(feasibility_path))
    assert result["instance_summaries"][0]["codeword_count"] == 2


def test_parameter_review_separates_construction_from_screen(tmp_path):
    data = {
        "instances": [
            {
                "id": "appendix_sample",
                "v": 122,
                "k": 5,
                "codeword_format": "appendix_a",
                "codewords": [
                    [1, 3, 21, 33],
                    [10, 34, 93, 106],
                    [8, 36, 76, 111],
                    [6, 51, 58, 113],
                    [4, 42, 85, 99],
                    [5, 49, 74, 105],
                ],
            }
        ]
    }
    feasibility = {"cases": [{"id": "case_122_k5", "v": 122, "k": 5}]}
    data_path = tmp_path / "instances.json"
    feasibility_path = tmp_path / "feasibility.json"
    data_path.write_text(__import__("json").dumps(data), encoding="utf-8")
    feasibility_path.write_text(__import__("json").dumps(feasibility), encoding="utf-8")
    result = cpcw.run_audit(str(data_path), str(feasibility_path))
    row = result["parameter_review_summaries"][0]
    assert row["parameter_id"] == "v122_k5"
    assert row["evidence_status"] == "constructed_optimal"


def test_source_claim_review_keeps_open_markers_unresolved(tmp_path):
    data = {
        "instances": [
            {
                "id": "partial_candidate",
                "v": 122,
                "k": 6,
                "codeword_format": "full",
                "codewords": [[26, 36, 37, 54, 58, 96]],
            }
        ]
    }
    feasibility = {"cases": [{"id": "case_122_k6", "v": 122, "k": 6}]}
    claims = {
        "claims": [
            {
                "id": "claim_122_k6",
                "v": 122,
                "k": 6,
                "source_marker": "section_3_1_v122",
            }
        ]
    }
    data_path = tmp_path / "instances.json"
    feasibility_path = tmp_path / "feasibility.json"
    claims_path = tmp_path / "claims.json"
    data_path.write_text(__import__("json").dumps(data), encoding="utf-8")
    feasibility_path.write_text(__import__("json").dumps(feasibility), encoding="utf-8")
    claims_path.write_text(__import__("json").dumps(claims), encoding="utf-8")
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(__import__("json").dumps({"policies": []}), encoding="utf-8")
    result = cpcw.run_audit(str(data_path), str(feasibility_path), str(claims_path), str(policy_path))
    assert result["source_claim_summaries"][0]["claim_status"] == "unresolved_by_source"
    assert result["parameter_review_summaries"][0]["evidence_status"] == "candidate_partial_evidence"


def test_source_claim_section_3_2_uses_screen_evidence(tmp_path):
    data = {"instances": []}
    feasibility = {
        "cases": [
            {"id": "case_222_k5", "v": 222, "k": 5},
            {"id": "case_482_k5", "v": 482, "k": 5},
        ]
    }
    claims = {
        "claims": [
            {
                "id": "claim_222_k5",
                "v": 222,
                "k": 5,
                "source_marker": "section_3_2_v222",
            },
            {
                "id": "claim_482_k5",
                "v": 482,
                "k": 5,
                "source_marker": "section_3_2_v482",
            }
        ]
    }
    data_path = tmp_path / "instances.json"
    feasibility_path = tmp_path / "feasibility.json"
    claims_path = tmp_path / "claims.json"
    policy_path = tmp_path / "policy.json"
    data_path.write_text(__import__("json").dumps(data), encoding="utf-8")
    feasibility_path.write_text(__import__("json").dumps(feasibility), encoding="utf-8")
    claims_path.write_text(__import__("json").dumps(claims), encoding="utf-8")
    policy_path.write_text(__import__("json").dumps({"policies": []}), encoding="utf-8")
    result = cpcw.run_audit(str(data_path), str(feasibility_path), str(claims_path), str(policy_path))
    rows = {row["id"]: row for row in result["source_claim_summaries"]}
    assert rows["claim_222_k5"]["screen_case_ids"] == ["case_222_k5"]
    assert rows["claim_222_k5"]["claim_status"] == "excluded_by_source"
    assert rows["claim_482_k5"]["screen_case_ids"] == ["case_482_k5"]
    assert rows["claim_482_k5"]["claim_status"] == "unresolved_by_source"
    assert result["source_excluded_parameter_ids"] == ["v222_k5"]
    assert result["source_unresolved_parameter_ids"] == ["v482_k5"]


def test_policy_certification_uses_uncovered_count(tmp_path):
    data = {
        "instances": [
            {
                "id": "plus_two_optimal",
                "v": 122,
                "k": 5,
                "codeword_format": "appendix_a",
                "codewords": [
                    [1, 3, 21, 33],
                    [10, 34, 93, 106],
                    [8, 36, 76, 111],
                    [6, 51, 58, 113],
                    [4, 42, 85, 99],
                    [5, 49, 74, 105],
                ],
            }
        ]
    }
    feasibility = {"cases": []}
    claims = {"claims": []}
    policy = {
        "policies": [
            {
                "id": "full_difference_certificate",
                "requires_cpcw": True,
                "requires_bound_attainment": True,
                "max_uncovered_nonzero": 0,
            }
        ]
    }
    data_path = tmp_path / "instances.json"
    feasibility_path = tmp_path / "feasibility.json"
    claims_path = tmp_path / "claims.json"
    policy_path = tmp_path / "policy.json"
    data_path.write_text(__import__("json").dumps(data), encoding="utf-8")
    feasibility_path.write_text(__import__("json").dumps(feasibility), encoding="utf-8")
    claims_path.write_text(__import__("json").dumps(claims), encoding="utf-8")
    policy_path.write_text(__import__("json").dumps(policy), encoding="utf-8")
    result = cpcw.run_audit(str(data_path), str(feasibility_path), str(claims_path), str(policy_path))
    row = result["policy_summaries"][0]
    assert row["uncovered_nonzero_count"] == 1
    assert row["certified"] is False
    assert result["policy_certified_instance_ids"] == []


def test_review_recommendation_prioritizes_followup(tmp_path):
    data = {"instances": []}
    feasibility = {"cases": [{"id": "case_122_k6", "v": 122, "k": 6}]}
    claims = {
        "claims": [
            {
                "id": "claim_122_k6",
                "v": 122,
                "k": 6,
                "source_marker": "section_3_1_v122",
            }
        ]
    }
    policy = {
        "policies": [],
        "review_recommendation_policy": {
            "status_precedence": [
                "requires_followup",
                "withhold_for_exclusion",
                "certify_complete",
            ],
            "followup_fields": [
                "source_unresolved_parameter_ids",
                "unresolved_parameter_ids",
            ],
            "withhold_fields": [
                "source_excluded_parameter_ids",
                "screen_excluded_parameter_ids",
            ],
            "certification_fields": [
                "policy_uncertified_instance_ids",
            ],
        },
    }
    data_path = tmp_path / "instances.json"
    feasibility_path = tmp_path / "feasibility.json"
    claims_path = tmp_path / "claims.json"
    policy_path = tmp_path / "policy.json"
    data_path.write_text(__import__("json").dumps(data), encoding="utf-8")
    feasibility_path.write_text(__import__("json").dumps(feasibility), encoding="utf-8")
    claims_path.write_text(__import__("json").dumps(claims), encoding="utf-8")
    policy_path.write_text(__import__("json").dumps(policy), encoding="utf-8")
    result = cpcw.run_audit(str(data_path), str(feasibility_path), str(claims_path), str(policy_path))
    assert result["review_recommendation"] == "requires_followup"
    assert "requires_followup:v122_k6" in result["review_blockers"]


def test_review_recommendation_uses_policy_precedence(tmp_path):
    data = {"instances": []}
    feasibility = {
        "cases": [
            {"id": "case_92_k6", "v": 92, "k": 6},
            {"id": "case_122_k6", "v": 122, "k": 6},
        ]
    }
    claims = {
        "claims": [
            {
                "id": "claim_92_k6",
                "v": 92,
                "k": 6,
                "source_marker": "section_3_3_v92",
            },
            {
                "id": "claim_122_k6",
                "v": 122,
                "k": 6,
                "source_marker": "section_3_1_v122",
            },
        ]
    }
    policy = {
        "policies": [],
        "review_recommendation_policy": {
            "status_precedence": [
                "withhold_for_exclusion",
                "requires_followup",
                "certify_complete",
            ],
            "followup_fields": [
                "source_unresolved_parameter_ids",
                "unresolved_parameter_ids",
            ],
            "withhold_fields": [
                "source_excluded_parameter_ids",
                "screen_excluded_parameter_ids",
            ],
            "certification_fields": [
                "policy_uncertified_instance_ids",
            ],
            "blocker_templates": {
                "followup_fields": "requires_followup:{value}",
                "withhold_fields": "withhold_for_exclusion:{value}",
                "certification_fields": "policy_gap:{value}",
            },
        },
    }
    data_path = tmp_path / "instances.json"
    feasibility_path = tmp_path / "feasibility.json"
    claims_path = tmp_path / "claims.json"
    policy_path = tmp_path / "policy.json"
    data_path.write_text(__import__("json").dumps(data), encoding="utf-8")
    feasibility_path.write_text(__import__("json").dumps(feasibility), encoding="utf-8")
    claims_path.write_text(__import__("json").dumps(claims), encoding="utf-8")
    policy_path.write_text(__import__("json").dumps(policy), encoding="utf-8")
    result = cpcw.run_audit(str(data_path), str(feasibility_path), str(claims_path), str(policy_path))
    assert result["review_recommendation"] == "withhold_for_exclusion"
    assert "withhold_for_exclusion:v92_k6" in result["review_blockers"]
'''
    (RESULTS / "tests" / "test_cpcw_audit.py").write_text(tests, encoding="utf-8")


if __name__ == "__main__":
    main()
