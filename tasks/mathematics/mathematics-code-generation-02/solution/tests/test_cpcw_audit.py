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
