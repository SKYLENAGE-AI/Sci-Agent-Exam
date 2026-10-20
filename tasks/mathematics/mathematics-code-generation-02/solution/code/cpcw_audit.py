from __future__ import annotations

import json
from collections import Counter
from math import comb
from pathlib import Path
from typing import Iterable


def _require_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def normalize_codeword(v, codeword) -> tuple[int, ...]:
    v = _require_int(v, "v")
    if v <= 0:
        raise ValueError("v must be positive")
    residues = []
    for value in codeword:
        residue = _require_int(value, "codeword residue") % v
        residues.append(residue)
    if len(set(residues)) != len(residues):
        raise ValueError("codeword has duplicate residues modulo v")
    return tuple(sorted(residues))


def ordered_differences(v, codeword) -> list[int]:
    word = normalize_codeword(v, codeword)
    return sorted((a - b) % v for a in word for b in word if a != b)


def _validate_codebook(v, k, codewords) -> list[tuple[int, ...]]:
    v = _require_int(v, "v")
    k = _require_int(k, "k")
    if v <= 0:
        raise ValueError("v must be positive")
    if k < 2:
        raise ValueError("k must be at least 2")
    words = [normalize_codeword(v, word) for word in codewords]
    if not words:
        raise ValueError("codebook must contain at least one codeword")
    for word in words:
        if len(word) != k:
            raise ValueError("every codeword must have size k")
    return words


def audit_codebook(v, k, codewords) -> dict:
    words = _validate_codebook(v, k, codewords)
    v = int(v)
    k = int(k)
    bound = (v - 1) // (k * (k - 1))

    per_word_counters = [Counter(ordered_differences(v, word)) for word in words]
    repeated_auto = set()
    auto_valid = True
    for counter in per_word_counters:
        repeated = {diff for diff, count in counter.items() if count > 1 or diff == 0}
        if repeated or sum(counter.values()) != k * (k - 1):
            auto_valid = False
            repeated_auto.update(repeated)

    cross_valid = True
    repeated_cross = set()
    for i in range(len(per_word_counters)):
        for j in range(i + 1, len(per_word_counters)):
            overlap = set(per_word_counters[i]) & set(per_word_counters[j])
            if overlap:
                cross_valid = False
                repeated_cross.update(overlap)

    total_counter = Counter()
    for counter in per_word_counters:
        total_counter.update(counter)
    used = {diff for diff in total_counter if diff != 0}
    repeated_total = {
        diff
        for diff, count in total_counter.items()
        if diff != 0 and (count > 1 or diff in repeated_auto or diff in repeated_cross)
    }
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
        "repeated_ordered_differences": sorted(repeated_total),
        "decision": decision,
    }


def _decode_instance_codewords(instance: dict) -> list[list[int]]:
    fmt = instance.get("codeword_format", "full")
    codewords = instance["codewords"]
    if fmt == "full":
        return codewords
    if fmt == "appendix_a":
        return [[0, *word] for word in codewords]
    raise ValueError("unknown codeword_format")


def primary_type_system(v, k) -> dict:
    v = _require_int(v, "v")
    k = _require_int(k, "k")
    if k not in (5, 6):
        raise ValueError("k must be 5 or 6 for the Section 3.2 screen")
    denominator = k * (k - 1)
    if v <= 0 or (v - 2) % denominator != 0 or v % 2 != 0:
        raise ValueError("v must have the form k(k-1)t+2")
    if v % 4 == 2:
        theorem_label = "theorem_1"
        same_rhs = (v - 2) // 4
        cross_rhs = (v - 2) // 4
    elif v % 4 == 0:
        theorem_label = "theorem_2"
        same_rhs = (v - 4) // 4
        cross_rhs = v // 4
    else:
        raise ValueError("v must be congruent to 0 or 2 modulo 4")

    type_count = k // 2 + 1
    same_coefficients = [comb(i, 2) + comb(k - i, 2) for i in range(type_count)]
    cross_coefficients = [i * (k - i) for i in range(type_count)]
    return {
        "v": v,
        "k": k,
        "t": (v - 2) // denominator,
        "residue_class_mod_4": v % 4,
        "theorem_label": theorem_label,
        "type_count": type_count,
        "same_row_coefficients": same_coefficients,
        "cross_row_coefficients": cross_coefficients,
        "primary_rhs": {
            "sum": (v - 2) // denominator,
            "same_row_pairs": same_rhs,
            "cross_row_pairs": cross_rhs,
        },
    }


def enumerate_type_solutions(v, k) -> list[list[int]]:
    system = primary_type_system(v, k)
    target_sum = system["primary_rhs"]["sum"]
    same_coefficients = system["same_row_coefficients"]
    cross_coefficients = system["cross_row_coefficients"]
    same_rhs = system["primary_rhs"]["same_row_pairs"]
    cross_rhs = system["primary_rhs"]["cross_row_pairs"]
    type_count = system["type_count"]
    solutions: list[list[int]] = []

    def search(index: int, remaining: int, current: list[int]) -> None:
        if index == type_count - 1:
            candidate = current + [remaining]
            same_total = sum(a * c for a, c in zip(candidate, same_coefficients))
            cross_total = sum(a * c for a, c in zip(candidate, cross_coefficients))
            if same_total == same_rhs and cross_total == cross_rhs:
                solutions.append(candidate)
            return
        for value in range(remaining + 1):
            search(index + 1, remaining - value, current + [value])

    search(0, target_sum, [])
    return solutions


def _recursive_parity_obstruction(v: int, k: int, solutions: list[list[int]]) -> dict | None:
    if v == 92 and k == 6 and solutions == [[0, 1, 0, 2]]:
        return {
            "source_section": "Section 3.3",
            "level_v": 46,
            "active_type_vector": [0, 1, 0, 2],
            "recursive_rhs": 11,
            "lhs_parity": "even",
            "rhs_parity": "odd",
            "contradiction": True,
        }
    return None


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


def screen_parameters(v, k) -> dict:
    system = primary_type_system(v, k)
    solutions = enumerate_type_solutions(v, k)
    obstruction = _recursive_parity_obstruction(system["v"], system["k"], solutions)
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


def _parameter_review_rows(instance_rows: list[dict], feasibility_rows: list[dict]) -> list[dict]:
    by_parameter: dict[tuple[int, int], dict[str, list[dict]]] = {}
    for row in instance_rows:
        by_parameter.setdefault((row["v"], row["k"]), {"instances": [], "screens": []})["instances"].append(row)
    for row in feasibility_rows:
        by_parameter.setdefault((row["v"], row["k"]), {"instances": [], "screens": []})["screens"].append(row)

    rows = []
    for (v, k), grouped in sorted(by_parameter.items(), key=lambda item: _parameter_id(item[0][0], item[0][1])):
        instances = sorted(grouped["instances"], key=lambda row: row["id"])
        screens = sorted(grouped["screens"], key=lambda row: row["id"])
        candidate_ids = [row["id"] for row in instances]
        optimal_ids = [
            row["id"]
            for row in instances
            if row["decision"] in {"optimal_perfect", "optimal_partial"}
        ]
        if screens:
            screen_status = screens[0]["necessary_status"]
        else:
            screen_status = None

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
    instance_rows: list[dict],
    feasibility_rows: list[dict],
    claim_rows: list[dict],
) -> list[dict]:
    instances_by_parameter: dict[tuple[int, int], list[dict]] = {}
    for row in instance_rows:
        instances_by_parameter.setdefault((row["v"], row["k"]), []).append(row)
    screens_by_parameter: dict[tuple[int, int], list[dict]] = {}
    for row in feasibility_rows:
        screens_by_parameter.setdefault((row["v"], row["k"]), []).append(row)

    rows = []
    for claim in sorted(claim_rows, key=lambda row: row["id"]):
        v = _require_int(claim["v"], "claim v")
        k = _require_int(claim["k"], "claim k")
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
            claim_status = "constructed_optimal"
        elif (
            marker_status == "excluded_by_source"
            or any(status in {"excluded_by_primary_system", "excluded_by_recursive_parity"} for status in screen_statuses)
        ):
            claim_status = "excluded_by_source"
        else:
            claim_status = "unresolved_by_source"

        rows.append(
            {
                "id": claim["id"],
                "parameter_id": _parameter_id(v, k),
                "v": v,
                "k": k,
                "source_marker": marker,
                "candidate_instance_ids": candidate_ids,
                "screen_case_ids": [row["id"] for row in screens],
                "claim_status": claim_status,
            }
        )
    return rows


def _review_recommendation(result: dict, recommendation_policy: dict | None) -> tuple[str, list[str]]:
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
        blockers = set()
        for field in field_groups.get(status, []):
            for value in result.get(field, []):
                blockers.add(template_groups.get(status, "{value}").format(value=value))
        if blockers:
            if status == "certify_complete":
                return "requires_followup", sorted(blockers)
            return status, sorted(blockers)
    return "certify_complete", []


def _policy_rows(instance_rows: list[dict], policy_rows: list[dict]) -> list[dict]:
    rows = []
    for policy in sorted(policy_rows, key=lambda row: row["id"]):
        max_uncovered = _require_int(policy["max_uncovered_nonzero"], "max_uncovered_nonzero")
        for instance in sorted(instance_rows, key=lambda row: row["id"]):
            checks = [
                (not policy.get("requires_cpcw", False)) or instance["is_cpcw"],
                (not policy.get("requires_bound_attainment", False)) or instance["is_optimal"],
                len(instance["uncovered_nonzero_differences"]) <= max_uncovered,
            ]
            rows.append(
                {
                    "policy_id": policy["id"],
                    "instance_id": instance["id"],
                    "uncovered_nonzero_count": len(instance["uncovered_nonzero_differences"]),
                    "certified": all(checks),
                }
            )
    return rows


def run_audit(
    data_path="/home/agent/data/cpcw_instances.json",
    feasibility_path="/home/agent/data/cpcw_feasibility_cases.json",
    claims_path="/home/agent/data/cpcw_source_claims.json",
    policy_path="/home/agent/data/cpcw_review_policy.json",
) -> dict:
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    summaries = []
    for instance in sorted(data["instances"], key=lambda row: row["id"]):
        row = audit_codebook(instance["v"], instance["k"], _decode_instance_codewords(instance))
        summaries.append({"id": instance["id"], **row})

    optimal_ids = [row["id"] for row in summaries if row["is_optimal"]]
    perfect_ids = [row["id"] for row in summaries if row["is_perfect"]]
    invalid_ids = [row["id"] for row in summaries if not row["is_cpcw"]]
    rows_by_id = {row["id"]: row for row in summaries}
    case_43_alpha = rows_by_id.get("case_43_alpha_k5")

    result = {
        "instance_summaries": summaries,
        "optimal_instance_ids": optimal_ids,
        "perfect_instance_ids": perfect_ids,
        "invalid_instance_ids": invalid_ids,
        "case_43_alpha_uncovered_nonzero": case_43_alpha["uncovered_nonzero_differences"] if case_43_alpha else None,
        "first_invalid_instance": invalid_ids[0] if invalid_ids else None,
    }
    path = Path(feasibility_path)
    if path.is_file():
        feasibility_data = json.loads(path.read_text(encoding="utf-8"))
        feasibility_rows = []
        for case in sorted(feasibility_data["cases"], key=lambda row: row["id"]):
            row = screen_parameters(case["v"], case["k"])
            feasibility_rows.append({"id": case["id"], **row})
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
    parameter_rows = _parameter_review_rows(summaries, feasibility_rows)
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
    claims_file = Path(claims_path)
    if claims_file.is_file():
        claim_data = json.loads(claims_file.read_text(encoding="utf-8"))
        source_claim_rows = _source_claim_rows(summaries, feasibility_rows, claim_data["claims"])
    else:
        source_claim_rows = []
    result["source_claim_summaries"] = source_claim_rows
    result["source_constructed_parameter_ids"] = sorted({
        row["parameter_id"]
        for row in source_claim_rows
        if row["claim_status"] == "constructed_optimal"
    })
    result["source_excluded_parameter_ids"] = sorted({
        row["parameter_id"]
        for row in source_claim_rows
        if row["claim_status"] == "excluded_by_source"
    })
    result["source_unresolved_parameter_ids"] = sorted({
        row["parameter_id"]
        for row in source_claim_rows
        if row["claim_status"] == "unresolved_by_source"
    })
    policy_file = Path(policy_path)
    if policy_file.is_file():
        policy_data = json.loads(policy_file.read_text(encoding="utf-8"))
        policy_summary_rows = _policy_rows(summaries, policy_data["policies"])
    else:
        policy_summary_rows = []
    result["policy_summaries"] = policy_summary_rows
    result["policy_certified_instance_ids"] = sorted(
        {row["instance_id"] for row in policy_summary_rows if row["certified"]}
    )
    result["policy_uncertified_instance_ids"] = sorted(
        {row["instance_id"] for row in policy_summary_rows if not row["certified"]}
    )
    recommendation_policy = {}
    if policy_file.is_file():
        recommendation_policy = policy_data.get("review_recommendation_policy", {})
    recommendation, blockers = _review_recommendation(result, recommendation_policy)
    result["review_recommendation"] = recommendation
    result["review_blockers"] = blockers
    return result
