#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_TOP_KEYS = [
    "instance_summaries",
    "optimal_instance_ids",
    "perfect_instance_ids",
    "invalid_instance_ids",
    "case_43_alpha_uncovered_nonzero",
    "first_invalid_instance",
    "feasibility_summaries",
    "screened_surviving_ids",
    "screened_excluded_ids",
    "parameter_review_summaries",
    "constructed_parameter_ids",
    "screen_excluded_parameter_ids",
    "unresolved_parameter_ids",
    "source_claim_summaries",
    "source_constructed_parameter_ids",
    "source_excluded_parameter_ids",
    "source_unresolved_parameter_ids",
    "policy_summaries",
    "policy_certified_instance_ids",
    "policy_uncertified_instance_ids",
    "review_recommendation",
    "review_blockers",
]

WEIGHTS = {
    "visible_answer_audit_values": 0.003,
    "visible_answer_screen_values": 0.002,
    "visible_answer_parameter_values": 0.002,
    "module_visible_run_audit_explicit": 0.003,
    "module_visible_run_audit_default": 0.003,
    "module_ordered_difference_semantics": 0.050,
    "module_direct_audit_behavior": 0.045,
    "hidden_same_schema_instances": 0.055,
    "appendix_format_semantics": 0.035,
    "feasibility_direct_semantics": 0.015,
    "hidden_feasibility_cases": 0.035,
    "parameter_review_hidden": 0.025,
    "source_scope_direct": 0.015,
    "source_scope_run_audit": 0.020,
    "source_scope_parameter_review": 0.020,
    "source_claim_visible": 0.015,
    "source_claim_hidden": 0.350,
    "source_policy_scope_hidden": 0.055,
    "policy_visible": 0.003,
    "policy_hidden": 0.015,
    "review_outcome_visible": 0.006,
    "review_outcome_hidden": 0.215,
    "invalid_input_handling": 0.010,
    "module_normalization_contract": 0.003,
}

HIDDEN_CASES = [
    "api_generated_perfect_k6_31",
    "api_generated_translate_collision_31",
    "api_generated_valid_partial_43",
    "api_generated_case_92_k6",
    "api_generated_case_142_k5",
    "api_generated_case_152_k6",
]

SOURCE_SCOPE_CASES = [
    (92, 6),
    (152, 6),
    (332, 6),
    (392, 6),
    (572, 6),
    (632, 6),
    (812, 6),
    (872, 6),
    (1052, 6),
    (1112, 6),
    (1292, 6),
    (1352, 6),
    (1532, 6),
    (1592, 6),
    (1772, 6),
]


def _source_section_for_case(v: int, k: int) -> str:
    return "Section 3.3" if (v, k) == (92, 6) else "Section 3.2"


def _feasibility_case(case_id: str, v: int, k: int) -> dict[str, Any]:
    return {
        "id": case_id,
        "v": v,
        "k": k,
        "source_section": _source_section_for_case(v, k),
    }


def _norm_word(v: int, word: list[int]) -> tuple[int, ...]:
    residues = []
    for value in word:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("non-integer residue")
        residues.append(value % v)
    if len(set(residues)) != len(residues):
        raise ValueError("duplicate residue")
    return tuple(sorted(residues))


def _ordered_diffs(v: int, word: list[int]) -> list[int]:
    normalized = _norm_word(v, word)
    return sorted((a - b) % v for a in normalized for b in normalized if a != b)


def _audit(v: int, k: int, codewords: list[list[int]]) -> dict[str, Any]:
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise ValueError("bad v")
    if isinstance(k, bool) or not isinstance(k, int) or k < 2:
        raise ValueError("bad k")
    if not codewords:
        raise ValueError("empty codebook")
    words = [_norm_word(v, word) for word in codewords]
    if any(len(word) != k for word in words):
        raise ValueError("bad word size")

    bound = (v - 1) // (k * (k - 1))
    counters = [Counter(_ordered_diffs(v, list(word))) for word in words]
    auto_valid = all(len(counter) == k * (k - 1) and 0 not in counter for counter in counters)

    cross_valid = True
    cross_repeated: set[int] = set()
    for i in range(len(counters)):
        for j in range(i + 1, len(counters)):
            overlap = set(counters[i]) & set(counters[j])
            if overlap:
                cross_valid = False
                cross_repeated.update(overlap)

    total = Counter()
    for counter in counters:
        total.update(counter)
    repeated = sorted(diff for diff, count in total.items() if diff != 0 and (count > 1 or diff in cross_repeated))
    used = {diff for diff in total if diff != 0}
    uncovered = [diff for diff in range(1, v) if diff not in used]
    is_cpcw = auto_valid and cross_valid
    is_optimal = is_cpcw and len(words) == bound
    is_perfect = is_cpcw and not uncovered and len(words) * k * (k - 1) == v - 1
    if is_perfect:
        decision = "optimal_perfect"
    elif is_optimal:
        decision = "optimal_partial"
    elif is_cpcw:
        decision = "valid_subbound"
    else:
        decision = "invalid"

    return {
        "v": v,
        "k": k,
        "bound": bound,
        "codeword_count": len(words),
        "auto_valid": auto_valid,
        "cross_valid": cross_valid,
        "is_cpcw": is_cpcw,
        "is_optimal": is_optimal,
        "is_perfect": is_perfect,
        "uncovered_nonzero_differences": uncovered,
        "repeated_ordered_differences": repeated,
        "decision": decision,
    }


def _decode_instance_codewords(inst: dict[str, Any]) -> list[list[int]]:
    fmt = inst.get("codeword_format", "full")
    codewords = inst["codewords"]
    if fmt == "full":
        return codewords
    if fmt == "appendix_a":
        return [[0, *word] for word in codewords]
    raise ValueError("bad codeword_format")


def _primary_type_system(v: int, k: int) -> dict[str, Any]:
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise ValueError("bad v")
    if isinstance(k, bool) or not isinstance(k, int) or k not in (5, 6):
        raise ValueError("bad k")
    denominator = k * (k - 1)
    if (v - 2) % denominator != 0 or v % 2 != 0:
        raise ValueError("bad length")
    if v % 4 == 2:
        theorem_label = "theorem_1"
        same_rhs = (v - 2) // 4
        cross_rhs = (v - 2) // 4
    elif v % 4 == 0:
        theorem_label = "theorem_2"
        same_rhs = (v - 4) // 4
        cross_rhs = v // 4
    else:
        raise ValueError("bad residue class")
    type_count = k // 2 + 1
    same = [math.comb(i, 2) + math.comb(k - i, 2) for i in range(type_count)]
    cross = [i * (k - i) for i in range(type_count)]
    return {
        "v": v,
        "k": k,
        "t": (v - 2) // denominator,
        "residue_class_mod_4": v % 4,
        "theorem_label": theorem_label,
        "type_count": type_count,
        "same_row_coefficients": same,
        "cross_row_coefficients": cross,
        "primary_rhs": {
            "sum": (v - 2) // denominator,
            "same_row_pairs": same_rhs,
            "cross_row_pairs": cross_rhs,
        },
    }


def _type_solutions(v: int, k: int) -> list[list[int]]:
    system = _primary_type_system(v, k)
    target_sum = system["primary_rhs"]["sum"]
    same = system["same_row_coefficients"]
    cross = system["cross_row_coefficients"]
    same_rhs = system["primary_rhs"]["same_row_pairs"]
    cross_rhs = system["primary_rhs"]["cross_row_pairs"]
    type_count = system["type_count"]
    solutions: list[list[int]] = []

    def search(index: int, remaining: int, current: list[int]) -> None:
        if index == type_count - 1:
            candidate = current + [remaining]
            if (
                sum(a * c for a, c in zip(candidate, same)) == same_rhs
                and sum(a * c for a, c in zip(candidate, cross)) == cross_rhs
            ):
                solutions.append(candidate)
            return
        for value in range(remaining + 1):
            search(index + 1, remaining - value, current + [value])

    search(0, target_sum, [])
    return solutions


def _has_recursive_obstruction(v: int, k: int, solutions: list[list[int]]) -> bool:
    return v == 92 and k == 6 and solutions == [[0, 1, 0, 2]]


def _screen(v: int, k: int) -> dict[str, Any]:
    system = _primary_type_system(v, k)
    solutions = _type_solutions(v, k)
    obstruction = _has_recursive_obstruction(v, k, solutions)
    certificate = None
    if obstruction:
        certificate = {
            "source_section": "Section 3.3",
            "level_v": 46,
            "active_type_vector": [0, 1, 0, 2],
            "recursive_rhs": 11,
            "lhs_parity": "even",
            "rhs_parity": "odd",
            "contradiction": True,
        }
    if not solutions:
        status = "excluded_by_primary_system"
    elif obstruction:
        status = "excluded_by_recursive_parity"
    else:
        status = "survives_necessary_screen"
    sections = ["Section 3.2"]
    if obstruction:
        sections.append("Section 3.3")
    return {
        "v": system["v"],
        "k": system["k"],
        "t": system["t"],
        "residue_class_mod_4": system["residue_class_mod_4"],
        "screen_sections": sections,
        "primary_solution_count": len(solutions),
        "necessary_status": status,
    }


def _parameter_id(v: int, k: int) -> str:
    return f"v{v}_k{k}"


_TABLE_3_EXCLUDED = {42, 62, 102, 142}
_TABLE_3_OPEN = {143, 144, 146, 162, 167}
_TABLE_3_CONSTRUCTED = set(range(41, 182)) - _TABLE_3_EXCLUDED - _TABLE_3_OPEN
_TABLE_4_EXCLUDED = {61, 64, 65, 92}
_TABLE_4_OPEN = {122, 123, 124, 126}
_TABLE_4_CONSTRUCTED = set(range(61, 152)) - _TABLE_4_EXCLUDED - _TABLE_4_OPEN
_APPENDIX_A_K5 = (
    set(range(90, 101))
    | set(range(103, 105))
    | set(range(106, 121))
    | set(range(122, 124))
    | set(range(126, 132))
    | set(range(133, 135))
    | set(range(136, 141))
    | set(range(147, 161))
    | {166}
    | set(range(168, 181))
)
_APPENDIX_A_K6 = set(range(106, 121)) | {125} | set(range(127, 151))


def _marker_length(source_marker: str) -> int | None:
    if "_v" not in source_marker:
        return None
    suffix = source_marker.rsplit("_v", 1)[1]
    if not suffix.isdigit():
        return None
    return int(suffix)


def _marker_status(source_marker: str, v: int, k: int) -> str:
    marker_v = _marker_length(source_marker)
    if marker_v is not None and marker_v != v:
        return "unresolved_by_source"
    anchor = source_marker.rsplit("_v", 1)[0]
    if anchor == "appendix_a":
        if k == 5 and v in _APPENDIX_A_K5:
            return "constructed_optimal"
        if k == 6 and v in _APPENDIX_A_K6:
            return "constructed_optimal"
        return "unresolved_by_source"
    if source_marker == "section_3_3_v92" and v == 92 and k == 6:
        return "excluded_by_source"
    if anchor == "section_3_2":
        return "unresolved_by_source"
    if anchor == "table_3" or (anchor == "section_3_1" and k == 5):
        if v in _TABLE_3_EXCLUDED:
            return "excluded_by_source"
        if v in _TABLE_3_OPEN:
            return "unresolved_by_source"
        if v in _TABLE_3_CONSTRUCTED:
            return "constructed_optimal"
        return "unresolved_by_source"
    if anchor == "table_4" or (anchor == "section_3_1" and k == 6):
        if v in _TABLE_4_EXCLUDED:
            return "excluded_by_source"
        if v in _TABLE_4_OPEN:
            return "unresolved_by_source"
        if v in _TABLE_4_CONSTRUCTED:
            return "constructed_optimal"
        return "unresolved_by_source"
    return "unresolved_by_source"


def _parameter_review_rows(instance_rows: list[dict[str, Any]], feasibility_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_parameter: dict[tuple[int, int], dict[str, list[dict[str, Any]]]] = {}
    for row in instance_rows:
        by_parameter.setdefault((row["v"], row["k"]), {"instances": [], "screens": []})["instances"].append(row)
    for row in feasibility_rows:
        by_parameter.setdefault((row["v"], row["k"]), {"instances": [], "screens": []})["screens"].append(row)

    rows: list[dict[str, Any]] = []
    for (v, k), grouped in sorted(by_parameter.items(), key=lambda item: _parameter_id(item[0][0], item[0][1])):
        instances = sorted(grouped["instances"], key=lambda row: row["id"])
        screens = sorted(grouped["screens"], key=lambda row: row["id"])
        candidate_ids = [row["id"] for row in instances]
        optimal_ids = [
            row["id"]
            for row in instances
            if row["decision"] in {"optimal_perfect", "optimal_partial"}
        ]
        screen_status = screens[0]["necessary_status"] if screens else None
        if optimal_ids:
            evidence_status = "constructed_optimal"
        elif screen_status in {"excluded_by_primary_system", "excluded_by_recursive_parity"}:
            evidence_status = "excluded_by_screen"
        elif candidate_ids:
            evidence_status = "candidate_partial_evidence"
        else:
            evidence_status = "unresolved_by_mounted_evidence"
        rows.append(
            {
                "parameter_id": _parameter_id(v, k),
                "v": v,
                "k": k,
                "candidate_instance_ids": candidate_ids,
                "optimal_candidate_ids": optimal_ids,
                "screen_case_ids": [row["id"] for row in screens],
                "screen_status": screen_status,
                "evidence_status": evidence_status,
            }
        )
    return rows


def _source_claim_rows(
    instance_rows: list[dict[str, Any]],
    feasibility_rows: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    instances_by_parameter: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in instance_rows:
        instances_by_parameter.setdefault((row["v"], row["k"]), []).append(row)
    screens_by_parameter: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in feasibility_rows:
        screens_by_parameter.setdefault((row["v"], row["k"]), []).append(row)

    result = []
    for claim in sorted(claim_rows, key=lambda row: row["id"]):
        v = claim["v"]
        k = claim["k"]
        marker = claim["source_marker"]
        key = (v, k)
        instances = sorted(instances_by_parameter.get(key, []), key=lambda row: row["id"])
        screens = sorted(screens_by_parameter.get(key, []), key=lambda row: row["id"])
        candidate_ids = [row["id"] for row in instances]
        optimal_ids = [
            row["id"]
            for row in instances
            if row["decision"] in {"optimal_perfect", "optimal_partial"}
        ]
        screen_statuses = [row["necessary_status"] for row in screens]
        marker_status = _marker_status(marker, v, k)
        if optimal_ids or marker_status == "constructed_optimal":
            status = "constructed_optimal"
        elif (
            marker_status == "excluded_by_source"
            or any(item in {"excluded_by_primary_system", "excluded_by_recursive_parity"} for item in screen_statuses)
        ):
            status = "excluded_by_source"
        else:
            status = "unresolved_by_source"
        result.append(
            {
                "id": claim["id"],
                "parameter_id": f"v{v}_k{k}",
                "v": v,
                "k": k,
                "source_marker": marker,
                "candidate_instance_ids": candidate_ids,
                "screen_case_ids": [row["id"] for row in screens],
                "claim_status": status,
            }
        )
    return result


def _policy_rows(instance_rows: list[dict[str, Any]], policy_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for policy in sorted(policy_rows, key=lambda row: row["id"]):
        max_uncovered = policy["max_uncovered_nonzero"]
        for instance in sorted(instance_rows, key=lambda row: row["id"]):
            certified = (
                ((not policy.get("requires_cpcw", False)) or instance["is_cpcw"])
                and ((not policy.get("requires_bound_attainment", False)) or instance["is_optimal"])
                and len(instance["uncovered_nonzero_differences"]) <= max_uncovered
            )
            rows.append(
                {
                    "policy_id": policy["id"],
                    "instance_id": instance["id"],
                    "uncovered_nonzero_count": len(instance["uncovered_nonzero_differences"]),
                    "certified": certified,
                }
            )
    return rows


def _expected(
    data: dict[str, Any],
    feasibility_data: dict[str, Any] | None = None,
    claim_data: dict[str, Any] | None = None,
    policy_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []
    for inst in sorted(data["instances"], key=lambda row: row["id"]):
        rows.append({"id": inst["id"], **_audit(inst["v"], inst["k"], _decode_instance_codewords(inst))})
    optimal = [row["id"] for row in rows if row["is_optimal"]]
    perfect = [row["id"] for row in rows if row["is_perfect"]]
    invalid = [row["id"] for row in rows if not row["is_cpcw"]]
    by_id = {row["id"]: row for row in rows}
    case_43_alpha = by_id.get("case_43_alpha_k5")
    result = {
        "instance_summaries": rows,
        "optimal_instance_ids": optimal,
        "perfect_instance_ids": perfect,
        "invalid_instance_ids": invalid,
        "case_43_alpha_uncovered_nonzero": case_43_alpha["uncovered_nonzero_differences"] if case_43_alpha else None,
        "first_invalid_instance": invalid[0] if invalid else None,
    }
    if feasibility_data is not None:
        feasibility_rows = []
        for case in sorted(feasibility_data["cases"], key=lambda row: row["id"]):
            feasibility_rows.append({"id": case["id"], **_screen(case["v"], case["k"])})
        result["feasibility_summaries"] = feasibility_rows
        result["screened_surviving_ids"] = [
            row["id"]
            for row in feasibility_rows
            if row["necessary_status"] == "survives_necessary_screen"
        ]
        result["screened_excluded_ids"] = [
            row["id"]
            for row in feasibility_rows
            if row["necessary_status"] in {"excluded_by_primary_system", "excluded_by_recursive_parity"}
        ]
    else:
        feasibility_rows = []
    parameter_rows = _parameter_review_rows(rows, feasibility_rows)
    result["parameter_review_summaries"] = parameter_rows
    result["constructed_parameter_ids"] = sorted(
        row["parameter_id"]
        for row in parameter_rows
        if row["evidence_status"] == "constructed_optimal"
    )
    result["screen_excluded_parameter_ids"] = sorted(
        row["parameter_id"]
        for row in parameter_rows
        if row["evidence_status"] == "excluded_by_screen"
    )
    result["unresolved_parameter_ids"] = sorted(
        row["parameter_id"]
        for row in parameter_rows
        if row["evidence_status"] in {"candidate_partial_evidence", "unresolved_by_mounted_evidence"}
    )
    if claim_data is not None:
        source_rows = _source_claim_rows(rows, feasibility_rows, claim_data["claims"])
    else:
        source_rows = []
    result["source_claim_summaries"] = source_rows
    result["source_constructed_parameter_ids"] = sorted({
        row["parameter_id"]
        for row in source_rows
        if row["claim_status"] == "constructed_optimal"
    })
    result["source_excluded_parameter_ids"] = sorted({
        row["parameter_id"]
        for row in source_rows
        if row["claim_status"] == "excluded_by_source"
    })
    result["source_unresolved_parameter_ids"] = sorted({
        row["parameter_id"]
        for row in source_rows
        if row["claim_status"] == "unresolved_by_source"
    })
    if policy_data is not None:
        policy_rows = _policy_rows(rows, policy_data["policies"])
    else:
        policy_rows = []
    result["policy_summaries"] = policy_rows
    result["policy_certified_instance_ids"] = sorted(
        {row["instance_id"] for row in policy_rows if row["certified"]}
    )
    result["policy_uncertified_instance_ids"] = sorted(
        {row["instance_id"] for row in policy_rows if not row["certified"]}
    )
    recommendation_policy = {}
    if policy_data is not None:
        recommendation_policy = policy_data.get("review_recommendation_policy", {})
    recommendation, blockers = _review_recommendation(result, recommendation_policy)
    result["review_recommendation"] = recommendation
    result["review_blockers"] = blockers
    return result


def _review_recommendation(result: dict[str, Any], recommendation_policy: dict[str, Any] | None) -> tuple[str, list[str]]:
    policy = recommendation_policy or {}
    field_groups = {
        "requires_followup": policy.get(
            "followup_fields",
            ["source_unresolved_parameter_ids", "unresolved_parameter_ids"],
        ),
        "withhold_for_exclusion": policy.get(
            "withhold_fields",
            ["source_excluded_parameter_ids", "screen_excluded_parameter_ids"],
        ),
        "certify_complete": policy.get("certification_fields", ["policy_uncertified_instance_ids"]),
    }
    templates = policy.get("blocker_templates", {})
    template_groups = {
        "requires_followup": templates.get("followup_fields", "requires_followup:{value}"),
        "withhold_for_exclusion": templates.get("withhold_fields", "withhold_for_exclusion:{value}"),
        "certify_complete": templates.get("certification_fields", "policy_gap:{value}"),
    }
    precedence = policy.get(
        "status_precedence",
        ["requires_followup", "withhold_for_exclusion", "certify_complete"],
    )
    for status in precedence:
        blockers: set[str] = set()
        for field in field_groups.get(status, []):
            for value in result.get(field, []):
                blockers.add(template_groups.get(status, "{value}").format(value=value))
        if blockers:
            if status == "certify_complete":
                return "requires_followup", sorted(blockers)
            return status, sorted(blockers)
    return "certify_complete", []


def _same(a: Any, b: Any) -> bool:
    return _canonicalize(a) == _canonicalize(b)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "screen_sections" and isinstance(item, list):
                result[key] = sorted(_canonicalize(section) for section in item)
            else:
                result[key] = _canonicalize(item)
        return result
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _required_keys_match(actual: Any, expected: dict[str, Any], keys: list[str]) -> bool:
    if not isinstance(actual, dict):
        return False
    return all(actual.get(key) == expected[key] for key in keys)


def _value_score(answer: Any, expected: dict[str, Any]) -> float:
    if not isinstance(answer, dict):
        return 0.0
    total = len(REQUIRED_TOP_KEYS)
    hits = sum(1 for key in REQUIRED_TOP_KEYS if _same(answer.get(key), expected.get(key)))
    return hits / total


def _answer_keys_score(answer: Any, expected: dict[str, Any], keys: list[str]) -> float:
    if not isinstance(answer, dict):
        return 0.0
    if list(answer.keys()) != REQUIRED_TOP_KEYS:
        return 0.0
    return sum(1 for key in keys if _same(answer.get(key), expected.get(key))) / len(keys)


def _load_module(output: Path):
    module_path = output / "code" / "cpcw_audit.py"
    if not module_path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("submitted_cpcw_audit", module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        return None
    return module


def _primary_system_matches(actual: Any, expected: dict[str, Any]) -> bool:
    if not isinstance(actual, dict):
        return False
    for key in ("screen_sections", "primary_solution_count", "necessary_status"):
        if actual.get(key) != expected[key]:
            return False
    return True


def _affine_word(v: int, word: list[int], multiplier: int, shift: int) -> list[int]:
    return sorted(((multiplier * value) + shift) % v for value in word)


def _generated_hidden_instances() -> dict[str, Any]:
    paper_43 = [0, 1, 3, 7, 19]
    perfect_31 = [0, 1, 3, 8, 12, 18]
    return {
        "instances": [
            {
                "id": "api_generated_perfect_k6_31",
                "v": 31,
                "k": 6,
                "codeword_format": "full",
                "codewords": [_affine_word(31, perfect_31, 3, 4)],
            },
            {
                "id": "api_generated_translate_collision_31",
                "v": 31,
                "k": 6,
                "codeword_format": "full",
                "codewords": [
                    _affine_word(31, perfect_31, 3, 4),
                    _affine_word(31, perfect_31, 3, 15),
                ],
            },
            {
                "id": "api_generated_valid_partial_43",
                "v": 43,
                "k": 5,
                "codeword_format": "full",
                "codewords": [_affine_word(43, paper_43, 2, 9)],
            },
        ]
    }


def _generated_basic_hidden_instances() -> dict[str, Any]:
    paper_43 = [0, 1, 3, 7, 19]
    perfect_31 = [0, 1, 3, 8, 12, 18]
    return {
        "instances": [
            {
                "id": "api_generated_perfect_k6_31",
                "v": 31,
                "k": 6,
                "codeword_format": "full",
                "codewords": [_affine_word(31, perfect_31, 3, 4)],
            },
            {
                "id": "api_generated_translate_collision_31",
                "v": 31,
                "k": 6,
                "codeword_format": "full",
                "codewords": [
                    _affine_word(31, perfect_31, 3, 4),
                    _affine_word(31, perfect_31, 3, 15),
                ],
            },
            {
                "id": "api_generated_valid_partial_43",
                "v": 43,
                "k": 5,
                "codeword_format": "full",
                "codewords": [_affine_word(43, paper_43, 2, 9)],
            },
        ]
    }


def _generated_appendix_instances() -> dict[str, Any]:
    return {
        "instances": [
            {
                "id": "api_generated_appendix_122_k5",
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
            },
            {
                "id": "api_generated_appendix_106_k6",
                "v": 106,
                "k": 6,
                "codeword_format": "appendix_a",
                "codewords": [
                    [1, 3, 7, 15, 36],
                    [5, 45, 56, 65, 84],
                    [10, 26, 44, 57, 74],
                ],
            },
            {
                "id": "api_generated_appendix_125_k6",
                "v": 125,
                "k": 6,
                "codeword_format": "appendix_a",
                "codewords": [
                    [1, 3, 19, 31, 54],
                    [5, 47, 64, 93, 104],
                    [7, 41, 50, 77, 110],
                    [4, 67, 80, 105, 119],
                ],
            },
            {
                "id": "api_generated_appendix_142_k6",
                "v": 142,
                "k": 6,
                "codeword_format": "appendix_a",
                "codewords": [
                    [1, 3, 7, 15, 46],
                    [9, 29, 61, 87, 114],
                    [10, 35, 75, 86, 108],
                    [5, 23, 93, 106, 123],
                ],
            },
            {
                "id": "api_generated_appendix_166_k5",
                "v": 166,
                "k": 5,
                "codeword_format": "appendix_a",
                "codewords": [
                    [1, 5, 39, 140],
                    [3, 15, 88, 117],
                    [7, 35, 107, 150],
                    [11, 32, 116, 129],
                    [9, 19, 77, 95],
                    [2, 46, 113, 121],
                    [17, 79, 109, 142],
                    [6, 42, 112, 152],
                ],
            },
        ]
    }


def _generated_hidden_feasibility() -> dict[str, Any]:
    cases = []
    for k, t_values in ((5, (5, 7)), (6, (3, 4, 6))):
        for t in t_values:
            v = k * (k - 1) * t + 2
            cases.append(_feasibility_case(f"api_generated_case_{v}_k{k}", v, k))
    return {"cases": cases}


def _generated_review_instances() -> dict[str, Any]:
    paper_43 = [0, 1, 3, 7, 19]
    perfect_31 = [0, 1, 3, 8, 12, 18]
    return {
        "instances": [
            {
                "id": "api_generated_appendix_122_k5",
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
            },
            {
                "id": "api_generated_candidate_82_k5",
                "v": 82,
                "k": 5,
                "codeword_format": "full",
                "codewords": [_affine_word(82, paper_43, 3, 11)],
            },
            {
                "id": "api_generated_perfect_k6_31",
                "v": 31,
                "k": 6,
                "codeword_format": "full",
                "codewords": [_affine_word(31, perfect_31, 5, 2)],
            },
        ]
    }


def _generated_review_feasibility() -> dict[str, Any]:
    return {
        "cases": [
            _feasibility_case("api_generated_case_82_k5", 82, 5),
            _feasibility_case("api_generated_case_92_k6", 92, 6),
            _feasibility_case("api_generated_case_122_k5", 122, 5),
            _feasibility_case("api_generated_case_142_k5", 142, 5),
            _feasibility_case("api_generated_case_182_k6", 182, 6),
        ]
    }


def _generated_source_claims() -> dict[str, Any]:
    claims = [
        {"id": "api_claim_table3_constructed_083_k5", "v": 83, "k": 5, "source_marker": "table_3_v83"},
        {"id": "api_claim_table3_constructed_090_k5", "v": 90, "k": 5, "source_marker": "table_3_v90"},
        {"id": "api_claim_table3_excluded_062_k5", "v": 62, "k": 5, "source_marker": "table_3_v62"},
        {"id": "api_claim_table3_excluded_142_k5", "v": 142, "k": 5, "source_marker": "table_3_v142"},
        {"id": "api_claim_table3_open_143_k5", "v": 143, "k": 5, "source_marker": "table_3_v143"},
        {"id": "api_claim_table3_open_167_k5", "v": 167, "k": 5, "source_marker": "table_3_v167"},
        {"id": "api_claim_section31_constructed_083_k5", "v": 83, "k": 5, "source_marker": "section_3_1_v83"},
        {"id": "api_claim_section31_excluded_062_k5", "v": 62, "k": 5, "source_marker": "section_3_1_v62"},
        {"id": "api_claim_section31_excluded_102_k5", "v": 102, "k": 5, "source_marker": "section_3_1_v102"},
        {"id": "api_claim_section31_excluded_142_k5", "v": 142, "k": 5, "source_marker": "section_3_1_v142"},
        {"id": "api_claim_section31_open_162_k5", "v": 162, "k": 5, "source_marker": "section_3_1_v162"},
        {"id": "api_claim_table4_excluded_061_k6", "v": 61, "k": 6, "source_marker": "table_4_v61"},
        {"id": "api_claim_table4_constructed_062_k6", "v": 62, "k": 6, "source_marker": "table_4_v62"},
        {"id": "api_claim_table4_constructed_106_k6", "v": 106, "k": 6, "source_marker": "table_4_v106"},
        {"id": "api_claim_table4_open_123_k6", "v": 123, "k": 6, "source_marker": "table_4_v123"},
        {"id": "api_claim_table4_open_126_k6", "v": 126, "k": 6, "source_marker": "table_4_v126"},
        {"id": "api_claim_section31_constructed_062_k6", "v": 62, "k": 6, "source_marker": "section_3_1_v62"},
        {"id": "api_claim_section31_constructed_106_k6", "v": 106, "k": 6, "source_marker": "section_3_1_v106"},
        {"id": "api_claim_section31_open_122_k6", "v": 122, "k": 6, "source_marker": "section_3_1_v122"},
        {"id": "api_claim_appendix_106_k6", "v": 106, "k": 6, "source_marker": "appendix_a_v106"},
        {"id": "api_claim_appendix_125_k6", "v": 125, "k": 6, "source_marker": "appendix_a_v125"},
        {"id": "api_claim_appendix_142_k6", "v": 142, "k": 6, "source_marker": "appendix_a_v142"},
        {"id": "api_claim_appendix_123_k5", "v": 123, "k": 5, "source_marker": "appendix_a_v123"},
        {"id": "api_claim_table3_constructed_160_k5", "v": 160, "k": 5, "source_marker": "table_3_v160"},
        {"id": "api_claim_table3_constructed_166_k5", "v": 166, "k": 5, "source_marker": "table_3_v166"},
        {"id": "api_claim_table3_excluded_102_k5", "v": 102, "k": 5, "source_marker": "table_3_v102"},
        {"id": "api_claim_section31_constructed_125_k5", "v": 125, "k": 5, "source_marker": "section_3_1_v125"},
        {"id": "api_claim_section31_constructed_151_k5", "v": 151, "k": 5, "source_marker": "section_3_1_v151"},
        {"id": "api_claim_table4_constructed_125_k6", "v": 125, "k": 6, "source_marker": "table_4_v125"},
        {"id": "api_claim_table4_constructed_151_k6", "v": 151, "k": 6, "source_marker": "table_4_v151"},
        {"id": "api_claim_table4_excluded_065_k6", "v": 65, "k": 6, "source_marker": "table_4_v65"},
        {"id": "api_claim_appendix_126_k5", "v": 126, "k": 5, "source_marker": "appendix_a_v126"},
        {"id": "api_claim_appendix_150_k6", "v": 150, "k": 6, "source_marker": "appendix_a_v150"},
        {"id": "api_claim_table3_unsupported_182_k5", "v": 182, "k": 5, "source_marker": "table_3_v182"},
        {"id": "api_claim_table4_unsupported_152_k6", "v": 152, "k": 6, "source_marker": "table_4_v152"},
        {"id": "api_claim_appendix_unsupported_181_k5", "v": 181, "k": 5, "source_marker": "appendix_a_v181"},
        {"id": "api_claim_appendix_unsupported_151_k6", "v": 151, "k": 6, "source_marker": "appendix_a_v151"},
    ]
    for v in (
        42,
        62,
        142,
    ):
        claims.append(
            {
                "id": f"api_claim_table3_matrix_excluded_{v:03d}_k5",
                "v": v,
                "k": 5,
                "source_marker": f"table_3_v{v}",
            }
        )
        claims.append(
            {
                "id": f"api_claim_section31_matrix_excluded_{v:03d}_k5",
                "v": v,
                "k": 5,
                "source_marker": f"section_3_1_v{v}",
            }
        )
    for v in (
        43,
        44,
        45,
        60,
        81,
        88,
        91,
        93,
        94,
        95,
        96,
        97,
        98,
        99,
        100,
        101,
        104,
        105,
        106,
        120,
        121,
        124,
        125,
        132,
        135,
    ):
        claims.append(
            {
                "id": f"api_claim_table3_matrix_constructed_{v:03d}_k5",
                "v": v,
                "k": 5,
                "source_marker": f"table_3_v{v}",
            }
        )
    for v in (
        61,
        64,
        65,
    ):
        claims.append(
            {
                "id": f"api_claim_table4_matrix_excluded_{v:03d}_k6",
                "v": v,
                "k": 6,
                "source_marker": f"table_4_v{v}",
            }
        )
        claims.append(
            {
                "id": f"api_claim_section31_matrix_excluded_{v:03d}_k6",
                "v": v,
                "k": 6,
                "source_marker": f"section_3_1_v{v}",
            }
        )
    for v in (
        63,
        66,
        91,
        93,
        94,
        95,
        96,
        97,
        98,
        99,
        100,
        101,
        104,
        105,
        107,
        108,
        109,
        110,
        111,
        112,
        113,
        114,
        115,
        116,
        117,
    ):
        claims.append(
            {
                "id": f"api_claim_table4_matrix_constructed_{v:03d}_k6",
                "v": v,
                "k": 6,
                "source_marker": f"table_4_v{v}",
            }
        )
    for v in (82, 122, 182, 242, 342, 362, 422, 462, 542, 602, 662, 722):
        claims.append(
            {
                "id": f"api_claim_section32_{v}_k5",
                "v": v,
                "k": 5,
                "source_marker": f"section_3_2_v{v}",
            }
        )
    for v in (122, 152, 182, 212, 242, 272, 332, 392, 572, 632, 812, 872):
        claims.append(
            {
                "id": f"api_claim_section32_{v}_k6",
                "v": v,
                "k": 6,
                "source_marker": f"section_3_2_v{v}",
            }
        )
    for v in (122, 152, 182, 212, 242, 272, 302, 332, 392, 572):
        claims.append(
            {
                "id": f"api_claim_section33_{v}_k6_non92",
                "v": v,
                "k": 6,
                "source_marker": f"section_3_3_v{v}",
            }
        )
    return {"claims": claims}


def _generated_review_cascade_claims() -> dict[str, Any]:
    return {
        "claims": [
            {"id": "api_cascade_section32_unresolved_152_k6", "v": 152, "k": 6, "source_marker": "section_3_2_v152"},
            {"id": "api_cascade_section33_unresolved_122_k6", "v": 122, "k": 6, "source_marker": "section_3_3_v122"},
            {"id": "api_cascade_table4_constructed_062_k6", "v": 62, "k": 6, "source_marker": "table_4_v62"},
            {"id": "api_cascade_table3_excluded_142_k5", "v": 142, "k": 5, "source_marker": "table_3_v142"},
            {"id": "api_cascade_appendix_constructed_125_k6", "v": 125, "k": 6, "source_marker": "appendix_a_v125"},
            {"id": "api_cascade_table3_unsupported_182_k5", "v": 182, "k": 5, "source_marker": "table_3_v182"},
            {"id": "api_cascade_table4_unsupported_152_k6", "v": 152, "k": 6, "source_marker": "table_4_v152"},
            {"id": "api_cascade_appendix_unsupported_181_k5", "v": 181, "k": 5, "source_marker": "appendix_a_v181"},
            {"id": "api_cascade_appendix_unsupported_151_k6", "v": 151, "k": 6, "source_marker": "appendix_a_v151"},
        ]
    }


def _generated_source_claim_instances() -> dict[str, Any]:
    return {
        "instances": [
            {
                "id": "api_source_mounted_appendix_123_k5",
                "v": 123,
                "k": 5,
                "codeword_format": "appendix_a",
                "codewords": [
                    [1, 3, 22, 53],
                    [8, 67, 93, 103],
                    [4, 17, 33, 65],
                    [9, 55, 98, 109],
                    [5, 12, 49, 88],
                    [6, 24, 51, 66],
                ],
            },
        ]
    }


def _generated_source_claim_feasibility() -> dict[str, Any]:
    return {
        "cases": [
            _feasibility_case("api_source_screen_82_k5", 82, 5),
            _feasibility_case("api_source_screen_92_k6", 92, 6),
            _feasibility_case("api_source_screen_152_k6", 152, 6),
            _feasibility_case("api_source_screen_222_k5", 222, 5),
            _feasibility_case("api_source_screen_302_k5", 302, 5),
            _feasibility_case("api_source_screen_482_k5", 482, 5),
        ]
    }


def _source_policy_scope_feasibility() -> dict[str, Any]:
    return {
        "cases": [
            _feasibility_case("api_section_3_3_scope_92_k6", 92, 6),
            _feasibility_case("api_section_3_3_scope_122_k6", 122, 6),
            _feasibility_case("api_section_3_3_scope_152_k6", 152, 6),
            _feasibility_case("api_section_3_3_scope_182_k6", 182, 6),
            _feasibility_case("api_section_3_3_scope_212_k6", 212, 6),
            _feasibility_case("api_section_3_3_scope_242_k6", 242, 6),
            _feasibility_case("api_section_3_3_scope_272_k6", 272, 6),
            _feasibility_case("api_section_3_3_scope_302_k6", 302, 6),
            _feasibility_case("api_section_3_3_scope_332_k6", 332, 6),
            _feasibility_case("api_section_3_3_scope_392_k6", 392, 6),
        ]
    }


def _source_policy_scope_claims() -> dict[str, Any]:
    return {
        "claims": [
            {
                "id": "api_scope_claim_092_k6",
                "v": 92,
                "k": 6,
                "source_marker": "section_3_3_v92",
            },
            {
                "id": "api_scope_claim_122_k6",
                "v": 122,
                "k": 6,
                "source_marker": "section_3_3_v122",
            },
            {
                "id": "api_scope_claim_152_k6",
                "v": 152,
                "k": 6,
                "source_marker": "section_3_3_v152",
            },
            {
                "id": "api_scope_claim_182_k6",
                "v": 182,
                "k": 6,
                "source_marker": "section_3_3_v182",
            },
            {
                "id": "api_scope_claim_212_k6",
                "v": 212,
                "k": 6,
                "source_marker": "section_3_3_v212",
            },
            {
                "id": "api_scope_claim_242_k6",
                "v": 242,
                "k": 6,
                "source_marker": "section_3_3_v242",
            },
            {
                "id": "api_scope_claim_272_k6",
                "v": 272,
                "k": 6,
                "source_marker": "section_3_3_v272",
            },
            {
                "id": "api_scope_claim_302_k6",
                "v": 302,
                "k": 6,
                "source_marker": "section_3_3_v302",
            },
            {
                "id": "api_scope_claim_332_k6",
                "v": 332,
                "k": 6,
                "source_marker": "section_3_3_v332",
            },
            {
                "id": "api_scope_claim_392_k6",
                "v": 392,
                "k": 6,
                "source_marker": "section_3_3_v392",
            },
            {
                "id": "api_scope_table3_claim_062_k5",
                "v": 62,
                "k": 5,
                "source_marker": "table_3_v62",
            },
            {
                "id": "api_scope_section31_claim_062_k5",
                "v": 62,
                "k": 5,
                "source_marker": "section_3_1_v62",
            },
            {
                "id": "api_scope_table3_claim_142_k5",
                "v": 142,
                "k": 5,
                "source_marker": "table_3_v142",
            },
            {
                "id": "api_scope_section31_claim_142_k5",
                "v": 142,
                "k": 5,
                "source_marker": "section_3_1_v142",
            },
            {
                "id": "api_scope_table3_claim_090_k5",
                "v": 90,
                "k": 5,
                "source_marker": "table_3_v90",
            },
            {
                "id": "api_scope_table3_claim_143_k5",
                "v": 143,
                "k": 5,
                "source_marker": "table_3_v143",
            },
            {
                "id": "api_scope_table4_claim_062_k6",
                "v": 62,
                "k": 6,
                "source_marker": "table_4_v62",
            },
            {
                "id": "api_scope_section31_claim_062_k6",
                "v": 62,
                "k": 6,
                "source_marker": "section_3_1_v62",
            },
            {
                "id": "api_scope_table4_claim_064_k6",
                "v": 64,
                "k": 6,
                "source_marker": "table_4_v64",
            },
            {
                "id": "api_scope_section31_claim_064_k6",
                "v": 64,
                "k": 6,
                "source_marker": "section_3_1_v64",
            },
            {
                "id": "api_scope_table4_claim_125_k6",
                "v": 125,
                "k": 6,
                "source_marker": "table_4_v125",
            },
            {
                "id": "api_scope_table4_claim_126_k6",
                "v": 126,
                "k": 6,
                "source_marker": "table_4_v126",
            },
        ]
    }


def _alternate_review_policy(policy_data: dict[str, Any]) -> dict[str, Any]:
    alternate = json.loads(json.dumps(policy_data))
    alternate.setdefault("review_recommendation_policy", {})["status_precedence"] = [
        "withhold_for_exclusion",
        "requires_followup",
        "certify_complete",
    ]
    return alternate


def _hidden_policy_variants(policy_data: dict[str, Any]) -> dict[str, Any]:
    alternate = json.loads(json.dumps(policy_data))
    alternate["policies"] = [
        *alternate.get("policies", []),
        {
            "id": "half_turn_research_certificate",
            "requires_cpcw": True,
            "requires_bound_attainment": True,
            "max_uncovered_nonzero": 1,
        },
        {
            "id": "candidate_inventory",
            "requires_cpcw": True,
            "requires_bound_attainment": False,
            "max_uncovered_nonzero": 200,
        },
    ]
    return alternate


def _module_run_score(
    module,
    data: dict[str, Any],
    feasibility_data: dict[str, Any],
    expected: dict[str, Any],
    claim_data: dict[str, Any] | None = None,
    policy_data: dict[str, Any] | None = None,
) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        if claim_data is not None:
            claims_path.write_text(json.dumps(claim_data), encoding="utf-8")
        else:
            claims_path.write_text(json.dumps({"claims": []}), encoding="utf-8")
        if policy_data is not None:
            policy_path.write_text(json.dumps(policy_data), encoding="utf-8")
        else:
            policy_path.write_text(json.dumps({"policies": []}), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0
    return _value_score(actual, expected)


def _module_default_run_score(module, expected: dict[str, Any]) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0
    default_path = Path("/home/agent/data/cpcw_instances.json")
    if not default_path.is_file():
        return 1.0
    try:
        actual = module.run_audit()
    except Exception:
        return 0.0
    return _value_score(actual, expected)


def _ordered_difference_score(module) -> float:
    if module is None or not hasattr(module, "ordered_differences") or not hasattr(module, "audit_codebook"):
        return 0.0
    try:
        diffs = list(module.ordered_differences(43, [0, 1, 3, 7, 22]))
        counter = Counter(diffs)
        repeated = sorted(diff for diff, count in counter.items() if count > 1)
        audit = module.audit_codebook(43, 5, [[0, 1, 3, 7, 22]])
        valid_k5 = list(module.ordered_differences(43, [0, 1, 3, 7, 19]))
        valid_k6 = list(module.ordered_differences(31, [0, 1, 3, 8, 12, 18]))
    except Exception:
        return 0.0
    checks = [
        len(diffs) == 20,
        diffs == sorted(diffs),
        all(isinstance(diff, int) and 1 <= diff <= 42 for diff in diffs),
        repeated == [21, 22],
        audit.get("auto_valid") is False,
        audit.get("decision") == "invalid",
        valid_k5 == _ordered_diffs(43, [0, 1, 3, 7, 19]),
        valid_k6 == _ordered_diffs(31, [0, 1, 3, 8, 12, 18]),
    ]
    return 1.0 if all(checks) else 0.0


def _feasibility_direct_score(module) -> float:
    required = ["screen_parameters"]
    if module is None or any(not hasattr(module, name) for name in required):
        return 0.0
    checks = []
    try:
        checks.append(_same(module.screen_parameters(82, 5), _screen(82, 5)))
    except Exception:
        checks.append(False)
    try:
        checks.append(_same(module.screen_parameters(102, 5), _screen(102, 5)))
    except Exception:
        checks.append(False)
    try:
        screen_122 = module.screen_parameters(122, 6)
        expected_122 = _screen(122, 6)
        checks.append(_same(screen_122, expected_122))
    except Exception:
        checks.append(False)
    try:
        screen_142 = module.screen_parameters(142, 5)
        expected_142 = _screen(142, 5)
        checks.append(_same(screen_142, expected_142))
    except Exception:
        checks.append(False)
    invalid_calls = [
        lambda: module.screen_parameters(0, 5),
        lambda: module.screen_parameters(82.0, 5),
        lambda: module.screen_parameters(82, 5.0),
        lambda: module.screen_parameters(82, 1),
    ]
    checks.append(_expects_value_error(invalid_calls) == 1.0)
    return sum(1 for check in checks if check) / len(checks)


def _hidden_feasibility_score(
    module,
    codebook_data: dict[str, Any],
    feasibility_data: dict[str, Any],
    expected: dict[str, Any],
) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(codebook_data), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        claims_path.write_text(json.dumps({"claims": []}), encoding="utf-8")
        policy_path.write_text(json.dumps({"policies": []}), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0
    expected_rows = {row["id"]: row for row in expected.get("feasibility_summaries", [])}
    actual_rows = {
        row.get("id"): row
        for row in actual.get("feasibility_summaries", [])
        if isinstance(row, dict)
    }
    row_hits = sum(1 for key, row in expected_rows.items() if _same(actual_rows.get(key), row))
    row_total = max(len(expected_rows), 1)
    list_hits = sum(
        1
        for key in ("screened_surviving_ids", "screened_excluded_ids")
        if actual.get(key) == expected.get(key)
    )
    return (row_hits + list_hits) / (row_total + 2)


def _parameter_review_score(actual: Any, expected: dict[str, Any]) -> float:
    if not isinstance(actual, dict):
        return 0.0
    expected_rows = {
        row["parameter_id"]: row
        for row in expected.get("parameter_review_summaries", [])
        if isinstance(row, dict)
    }
    actual_rows = {
        row.get("parameter_id"): row
        for row in actual.get("parameter_review_summaries", [])
        if isinstance(row, dict)
    }
    row_hits = sum(1 for key, row in expected_rows.items() if _same(actual_rows.get(key), row))
    row_total = max(len(expected_rows), 1)
    list_hits = sum(
        1
        for key in (
            "constructed_parameter_ids",
            "screen_excluded_parameter_ids",
            "unresolved_parameter_ids",
        )
        if actual.get(key) == expected.get(key)
    )
    return (row_hits + list_hits) / (row_total + 3)


def _module_parameter_review_score(
    module,
    data: dict[str, Any],
    feasibility_data: dict[str, Any],
    expected: dict[str, Any],
) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        claims_path.write_text(json.dumps({"claims": []}), encoding="utf-8")
        policy_path.write_text(json.dumps({"policies": []}), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0
    return _parameter_review_score(actual, expected)


def _source_claim_score(actual: Any, expected: dict[str, Any]) -> float:
    if not isinstance(actual, dict):
        return 0.0
    expected_rows = {
        row["id"]: row
        for row in expected.get("source_claim_summaries", [])
        if isinstance(row, dict)
    }
    actual_rows = {
        row.get("id"): row
        for row in actual.get("source_claim_summaries", [])
        if isinstance(row, dict)
    }
    row_hits = sum(1 for key, row in expected_rows.items() if _same(actual_rows.get(key), row))
    row_total = max(len(expected_rows), 1)
    row_fraction = row_hits / row_total

    def canonical_parameter_ids(value: Any) -> list[str] | None:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return None
        return sorted(set(value))

    list_hits = sum(
        1
        for key in (
            "source_constructed_parameter_ids",
            "source_excluded_parameter_ids",
            "source_unresolved_parameter_ids",
        )
        if canonical_parameter_ids(actual.get(key)) == canonical_parameter_ids(expected.get(key))
    )
    list_fraction = list_hits / 3
    return (0.70 * row_fraction) + (0.30 * list_fraction)


def _module_source_claim_score(
    module,
    data: dict[str, Any],
    feasibility_data: dict[str, Any],
    claim_data: dict[str, Any],
    expected: dict[str, Any],
) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        claims_path.write_text(json.dumps(claim_data), encoding="utf-8")
        policy_path.write_text(json.dumps({"policies": []}), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0
    return _source_claim_score(actual, expected)


def _source_policy_scope_score(
    module,
    feasibility_data: dict[str, Any],
    claim_data: dict[str, Any],
    policy_data: dict[str, Any],
    expected: dict[str, Any],
) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps({"instances": []}), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        claims_path.write_text(json.dumps(claim_data), encoding="utf-8")
        policy_path.write_text(json.dumps(policy_data), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0

    expected_rows = {
        row["id"]: row
        for row in expected.get("source_claim_summaries", [])
        if isinstance(row, dict)
    }
    actual_rows = {
        row.get("id"): row
        for row in actual.get("source_claim_summaries", [])
        if isinstance(row, dict)
    }
    row_hits = sum(1 for key, row in expected_rows.items() if _same(actual_rows.get(key), row))
    row_fraction = row_hits / max(len(expected_rows), 1)
    list_hits = sum(
        1
        for key in (
            "source_constructed_parameter_ids",
            "source_excluded_parameter_ids",
            "source_unresolved_parameter_ids",
        )
        if actual.get(key) == expected.get(key)
    )
    list_fraction = list_hits / 3
    review_fraction = _review_outcome_score(actual, expected)
    return (0.60 * row_fraction) + (0.20 * list_fraction) + (0.20 * review_fraction)


def _policy_score(actual: Any, expected: dict[str, Any]) -> float:
    if not isinstance(actual, dict):
        return 0.0
    expected_rows = {
        (row["policy_id"], row["instance_id"]): row
        for row in expected.get("policy_summaries", [])
        if isinstance(row, dict)
    }
    actual_rows = {
        (row.get("policy_id"), row.get("instance_id")): row
        for row in actual.get("policy_summaries", [])
        if isinstance(row, dict)
    }
    row_hits = sum(1 for key, row in expected_rows.items() if _same(actual_rows.get(key), row))
    row_total = max(len(expected_rows), 1)
    list_hits = sum(
        1
        for key in ("policy_certified_instance_ids", "policy_uncertified_instance_ids")
        if actual.get(key) == expected.get(key)
    )
    return (row_hits + list_hits) / (row_total + 2)


def _module_policy_score(
    module,
    data: dict[str, Any],
    feasibility_data: dict[str, Any],
    policy_data: dict[str, Any],
    expected: dict[str, Any],
) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        claims_path.write_text(json.dumps({"claims": []}), encoding="utf-8")
        policy_path.write_text(json.dumps(policy_data), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0
    return _policy_score(actual, expected)


def _review_outcome_score(actual: Any, expected: dict[str, Any]) -> float:
    if not isinstance(actual, dict):
        return 0.0
    recommendation_ok = actual.get("review_recommendation") == expected.get("review_recommendation")
    blockers_ok = actual.get("review_blockers") == expected.get("review_blockers")
    return (1.0 if recommendation_ok else 0.0) * 0.10 + (1.0 if blockers_ok else 0.0) * 0.90


def _module_review_outcome_score(
    module,
    data: dict[str, Any],
    feasibility_data: dict[str, Any],
    claim_data: dict[str, Any],
    policy_data: dict[str, Any],
    expected: dict[str, Any],
) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        claims_path.write_text(json.dumps(claim_data), encoding="utf-8")
        policy_path.write_text(json.dumps(policy_data), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0
    return _review_outcome_score(actual, expected)


def _source_scope_feasibility_data() -> dict[str, Any]:
    return {
        "cases": [
            _feasibility_case(f"api_scope_case_{v}_k{k}", v, k)
            for v, k in SOURCE_SCOPE_CASES
        ]
    }


def _source_scope_direct_score(module) -> float:
    if module is None or not hasattr(module, "screen_parameters"):
        return 0.0
    hits = 0
    for v, k in SOURCE_SCOPE_CASES:
        try:
            actual = module.screen_parameters(v, k)
            expected = _screen(v, k)
        except Exception:
            continue
        if _same(actual, expected):
            hits += 1
    return hits / len(SOURCE_SCOPE_CASES)


def _source_scope_run_audit_score(module) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0

    data = {"instances": []}
    feasibility_data = _source_scope_feasibility_data()
    expected = _expected(data, feasibility_data)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        claims_path.write_text(json.dumps({"claims": []}), encoding="utf-8")
        policy_path.write_text(json.dumps({"policies": []}), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0
    expected_rows = {
        row["id"]: row
        for row in expected.get("feasibility_summaries", [])
        if isinstance(row, dict)
    }
    actual_rows = {
        row.get("id"): row
        for row in actual.get("feasibility_summaries", [])
        if isinstance(row, dict)
    }
    row_hits = sum(1 for key, row in expected_rows.items() if _same(actual_rows.get(key), row))
    list_hits = sum(
        1
        for key in ("screened_surviving_ids", "screened_excluded_ids")
        if actual.get(key) == expected.get(key)
    )
    return (row_hits + list_hits) / (len(expected_rows) + 2)


def _source_scope_parameter_review_score(module) -> float:
    if module is None or not hasattr(module, "run_audit"):
        return 0.0

    data = {"instances": []}
    feasibility_data = _source_scope_feasibility_data()
    expected = _expected(data, feasibility_data)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "instances.json"
        feasibility_path = Path(tmp) / "feasibility.json"
        claims_path = Path(tmp) / "claims.json"
        policy_path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        feasibility_path.write_text(json.dumps(feasibility_data), encoding="utf-8")
        claims_path.write_text(json.dumps({"claims": []}), encoding="utf-8")
        policy_path.write_text(json.dumps({"policies": []}), encoding="utf-8")
        try:
            actual = module.run_audit(str(path), str(feasibility_path), str(claims_path), str(policy_path))
        except Exception:
            return 0.0
    expected_rows = {
        row["parameter_id"]: row
        for row in expected.get("parameter_review_summaries", [])
        if isinstance(row, dict)
    }
    rows = {
        row.get("parameter_id"): row
        for row in actual.get("parameter_review_summaries", [])
        if isinstance(row, dict)
    }
    row_hits = sum(1 for key, row in expected_rows.items() if _same(rows.get(key), row))
    list_hits = sum(
        1
        for key in (
            "constructed_parameter_ids",
            "screen_excluded_parameter_ids",
            "unresolved_parameter_ids",
        )
        if actual.get(key) == expected.get(key)
    )
    return (row_hits + list_hits) / (len(expected_rows) + 3)


def _expects_value_error(calls) -> float:
    passed = 0
    for call in calls:
        try:
            call()
        except ValueError:
            passed += 1
        except Exception:
            pass
    return passed / len(calls)


def _direct_audit_score(module) -> float:
    if module is None or not hasattr(module, "audit_codebook"):
        return 0.0
    cases = [
        (21, 5, [[0, 1, 4, 14, 16]]),
        (43, 5, [[0, 1, 3, 7, 19]]),
        (43, 5, [[0, 1, 3, 7, 19], [0, 5, 13, 22, 33]]),
        (43, 5, [[0, 1, 3, 7, 19], [5, 6, 8, 12, 24]]),
    ]
    hits = 0
    for v, k, codewords in cases:
        try:
            actual = module.audit_codebook(v, k, codewords)
        except Exception:
            continue
        expected = _audit(v, k, codewords)
        if _required_keys_match(actual, expected, list(expected.keys())):
            hits += 1
    return hits / len(cases)


def _normalization_score(module) -> float:
    if module is None or not hasattr(module, "normalize_codeword") or not hasattr(module, "ordered_differences"):
        return 0.0
    checks = []
    try:
        checks.append(module.normalize_codeword(7, [8, 0, 13]) == (0, 1, 6))
    except Exception:
        checks.append(False)
    try:
        module.normalize_codeword(7, [0, 7, 1])
        checks.append(False)
    except ValueError:
        checks.append(True)
    except Exception:
        checks.append(False)
    invalid_calls = [
        lambda: module.normalize_codeword(0, [0, 1]),
        lambda: module.normalize_codeword(7.0, [0, 1]),
        lambda: module.normalize_codeword(7, [0, 1.0]),
        lambda: module.ordered_differences(0, [0, 1]),
        lambda: module.ordered_differences(7, [0, 7, 1]),
        lambda: module.ordered_differences(7, [0, 1.0]),
    ]
    checks.append(_expects_value_error(invalid_calls) == 1.0)
    return sum(1 for item in checks if item) / len(checks)


def _invalid_score(module) -> float:
    if module is None or not hasattr(module, "audit_codebook"):
        return 0.0
    cases = [
        lambda: module.audit_codebook(7, 3, []),
        lambda: module.audit_codebook(7, 3, [[0, 7, 1]]),
        lambda: module.audit_codebook(7, 3, [[0, 1]]),
        lambda: module.audit_codebook(7, 1, [[0]]),
        lambda: module.audit_codebook(0, 3, [[0, 1, 2]]),
        lambda: module.audit_codebook(7.0, 3, [[0, 1, 2]]),
        lambda: module.audit_codebook(7, 3.0, [[0, 1, 2]]),
        lambda: module.audit_codebook(7, 3, [[0, 1, 2.0]]),
    ]
    return _expects_value_error(cases)


def compute_score(output: Path, data_dir: Path) -> dict[str, Any]:
    data = json.loads((data_dir / "cpcw_instances.json").read_text(encoding="utf-8"))
    feasibility_data = json.loads((data_dir / "cpcw_feasibility_cases.json").read_text(encoding="utf-8"))
    claim_data = json.loads((data_dir / "cpcw_source_claims.json").read_text(encoding="utf-8"))
    policy_data = json.loads((data_dir / "cpcw_review_policy.json").read_text(encoding="utf-8"))
    expected_visible = _expected(data, feasibility_data, claim_data, policy_data)
    answer_path = output / "answer.json"
    try:
        answer = json.loads(answer_path.read_text(encoding="utf-8"))
    except Exception:
        answer = None
    module = _load_module(output)

    hidden = _generated_hidden_instances()
    basic_hidden = _generated_basic_hidden_instances()
    appendix_hidden = _generated_appendix_instances()
    hidden_feasibility = _generated_hidden_feasibility()
    review_hidden = _generated_review_instances()
    review_feasibility = _generated_review_feasibility()
    source_claim_instances = _generated_source_claim_instances()
    source_claim_feasibility = _generated_source_claim_feasibility()
    source_claim_hidden = _generated_source_claims()
    review_cascade_instances = {"instances": []}
    review_cascade_feasibility = {"cases": []}
    review_cascade_claims = _generated_review_cascade_claims()
    source_policy_scope_feasibility = _source_policy_scope_feasibility()
    source_policy_scope_claims = _source_policy_scope_claims()
    hidden_policy_data = _hidden_policy_variants(policy_data)
    expected_hidden_feasibility = _expected(basic_hidden, hidden_feasibility)
    expected_review = _expected(review_hidden, review_feasibility)
    expected_source_claim_hidden = _expected(source_claim_instances, source_claim_feasibility, source_claim_hidden)
    expected_source_policy_scope = _expected(
        {"instances": []},
        source_policy_scope_feasibility,
        source_policy_scope_claims,
        policy_data,
    )
    expected_policy_hidden = _expected(review_hidden, review_feasibility, None, hidden_policy_data)
    review_outcome_policy = policy_data
    expected_review_outcome_hidden = _expected(
        review_cascade_instances,
        review_cascade_feasibility,
        review_cascade_claims,
        review_outcome_policy,
    )
    simple_feasibility = {"cases": [_feasibility_case("api_generated_case_82_k5", 82, 5)]}

    details = {
        "visible_answer_audit_values": _answer_keys_score(
            answer,
            expected_visible,
            [
                "instance_summaries",
                "optimal_instance_ids",
                "perfect_instance_ids",
                "invalid_instance_ids",
                "case_43_alpha_uncovered_nonzero",
                "first_invalid_instance",
            ],
        ),
        "visible_answer_screen_values": _answer_keys_score(
            answer,
            expected_visible,
            [
                "feasibility_summaries",
                "screened_surviving_ids",
                "screened_excluded_ids",
            ],
        ),
        "visible_answer_parameter_values": _answer_keys_score(
            answer,
            expected_visible,
            [
                "parameter_review_summaries",
                "constructed_parameter_ids",
                "screen_excluded_parameter_ids",
                "unresolved_parameter_ids",
            ],
        ),
        "module_visible_run_audit_explicit": _module_run_score(
            module,
            data,
            feasibility_data,
            expected_visible,
            claim_data,
            policy_data,
        ),
        "module_visible_run_audit_default": _module_default_run_score(module, expected_visible),
        "module_ordered_difference_semantics": _ordered_difference_score(module),
        "module_direct_audit_behavior": _direct_audit_score(module),
        "hidden_same_schema_instances": _module_run_score(
            module,
            hidden,
            feasibility_data,
            _expected(hidden, feasibility_data, claim_data, policy_data),
            claim_data,
            policy_data,
        ),
        "appendix_format_semantics": _module_run_score(
            module,
            appendix_hidden,
            simple_feasibility,
            _expected(appendix_hidden, simple_feasibility),
        ),
        "feasibility_direct_semantics": _feasibility_direct_score(module),
        "hidden_feasibility_cases": _hidden_feasibility_score(
            module,
            basic_hidden,
            hidden_feasibility,
            expected_hidden_feasibility,
        ),
        "parameter_review_hidden": _module_parameter_review_score(
            module,
            review_hidden,
            review_feasibility,
            expected_review,
        ),
        "invalid_input_handling": _invalid_score(module),
        "module_normalization_contract": _normalization_score(module),
        "source_scope_direct": _source_scope_direct_score(module),
        "source_scope_run_audit": _source_scope_run_audit_score(module),
        "source_scope_parameter_review": _source_scope_parameter_review_score(module),
        "source_claim_visible": _source_claim_score(answer, expected_visible),
        "source_claim_hidden": _module_source_claim_score(
            module,
            source_claim_instances,
            source_claim_feasibility,
            source_claim_hidden,
            expected_source_claim_hidden,
        ),
        "source_policy_scope_hidden": _source_policy_scope_score(
            module,
            source_policy_scope_feasibility,
            source_policy_scope_claims,
            policy_data,
            expected_source_policy_scope,
        ),
        "policy_visible": _policy_score(answer, expected_visible),
        "policy_hidden": _module_policy_score(
            module,
            review_hidden,
            review_feasibility,
            hidden_policy_data,
            expected_policy_hidden,
        ),
        "review_outcome_visible": _review_outcome_score(answer, expected_visible),
        "review_outcome_hidden": _module_review_outcome_score(
            module,
            review_cascade_instances,
            review_cascade_feasibility,
            review_cascade_claims,
            review_outcome_policy,
            expected_review_outcome_hidden,
        ),
    }
    score = sum(WEIGHTS[key] * details[key] for key in WEIGHTS)
    return {"score": round(score, 6), "details": details}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("/home/agent/data"))
    parser.add_argument("--result-file", type=Path)
    args = parser.parse_args()
    result = compute_score(args.output, args.data_dir)
    text = json.dumps(result, indent=2)
    if args.result_file:
        args.result_file.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
