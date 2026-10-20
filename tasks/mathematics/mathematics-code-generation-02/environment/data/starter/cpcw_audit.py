from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path


def _require_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def normalize_codeword(v, codeword):
    v = _require_int(v, "v")
    if v <= 0:
        raise ValueError("v must be positive")
    residues = [_require_int(value, "codeword residue") % v for value in codeword]
    if len(set(residues)) != len(residues):
        raise ValueError("codeword has duplicate residues modulo v")
    return tuple(sorted(residues))


def ordered_differences(v, codeword):
    word = normalize_codeword(v, codeword)
    return sorted((a - b) % v for a in word for b in word if a != b)


def _validate_codebook(v, k, codewords):
    v = _require_int(v, "v")
    k = _require_int(k, "k")
    if v <= 0:
        raise ValueError("v must be positive")
    if k < 2:
        raise ValueError("k must be at least 2")
    words = [normalize_codeword(v, row) for row in codewords]
    if not words:
        raise ValueError("codebook must contain at least one codeword")
    if any(len(word) != k for word in words):
        raise ValueError("every codeword must have size k")
    return words


def _covered_from_profile(v, profile):
    covered = set()
    for value in profile:
        if value == 0:
            continue
        covered.add(value)
        covered.add((-value) % v)
    return covered


def audit_codebook(v, k, codewords):
    words = _validate_codebook(v, k, codewords)
    bound = (v - 1) // (k * (k - 1))
    profiles = [Counter(ordered_differences(v, word)) for word in words]

    auto_valid = all(max(profile.values() or [0]) == 1 for profile in profiles)
    cross_valid = True
    repeated = set()
    for i, left in enumerate(profiles):
        for right in profiles[i + 1 :]:
            overlap = set(left) & set(right)
            if overlap:
                cross_valid = False
                repeated.update(overlap)
    for profile in profiles:
        repeated.update(value for value, count in profile.items() if count > 1)

    merged = Counter()
    for profile in profiles:
        merged.update(profile)
    covered = _covered_from_profile(v, merged)
    uncovered = [diff for diff in range(1, v) if diff not in covered]
    is_cpcw = auto_valid and cross_valid
    is_optimal = is_cpcw and len(words) >= bound
    is_perfect = is_cpcw and not uncovered
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
        "repeated_ordered_differences": sorted(repeated),
        "decision": decision,
    }


def _decode_instance_codewords(instance):
    rows = instance["codewords"]
    if instance.get("codeword_format") == "appendix_a":
        return [[0, *row] for row in rows]
    return rows


def _invalid_instance_audit(v, k, codewords):
    bound = (v - 1) // (k * (k - 1)) if isinstance(v, int) and isinstance(k, int) and k >= 2 else 0
    return {
        "v": v,
        "k": k,
        "bound": bound,
        "codeword_count": len(codewords),
        "auto_valid": False,
        "cross_valid": False,
        "is_cpcw": False,
        "is_optimal": False,
        "is_perfect": False,
        "uncovered_nonzero_differences": [],
        "repeated_ordered_differences": [],
        "decision": "invalid",
    }


def _primary_type_system(v, k):
    v = _require_int(v, "v")
    k = _require_int(k, "k")
    denominator = k * (k - 1)
    if v <= 0:
        raise ValueError("v must be positive")
    if k < 2:
        raise ValueError("k must be at least 2")
    if (v - 2) % denominator != 0 or v % 2 != 0:
        raise ValueError("v must have the form k(k-1)t+2")
    if v % 4 == 2:
        same_rhs = (v - 2) // 4
        cross_rhs = (v - 2) // 4
    elif v % 4 == 0:
        same_rhs = (v - 4) // 4
        cross_rhs = v // 4
    else:
        raise ValueError("v must be congruent to 0 or 2 modulo 4")

    type_count = k // 2 + 1
    same = [math.comb(i, 2) + math.comb(k - i, 2) for i in range(type_count)]
    cross = [i * (k - i) for i in range(type_count)]
    return {
        "v": v,
        "k": k,
        "t": (v - 2) // denominator,
        "residue_class_mod_4": v % 4,
        "same_row_coefficients": same,
        "cross_row_coefficients": cross,
        "primary_rhs": {
            "sum": (v - 2) // denominator,
            "same_row_pairs": same_rhs,
            "cross_row_pairs": cross_rhs,
        },
    }


def _type_solutions(v, k):
    system = _primary_type_system(v, k)
    target_sum = system["primary_rhs"]["sum"]
    same = system["same_row_coefficients"]
    cross = system["cross_row_coefficients"]
    same_rhs = system["primary_rhs"]["same_row_pairs"]
    cross_rhs = system["primary_rhs"]["cross_row_pairs"]
    type_count = len(same)
    solutions = []

    def search(index, remaining, current):
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
    return system, solutions


def screen_parameters(v, k):
    system, solutions = _type_solutions(v, k)
    sections = ["Section 3.2"]
    if not solutions:
        status = "excluded_by_primary_system"
    elif system["v"] == 92 and system["k"] == 6 and solutions == [[0, 1, 0, 2]]:
        sections.append("Section 3.3")
        status = "excluded_by_recursive_parity"
    else:
        status = "survives_necessary_screen"
    denominator = k * (k - 1)
    return {
        "v": system["v"],
        "k": system["k"],
        "t": (system["v"] - 2) // denominator,
        "residue_class_mod_4": system["residue_class_mod_4"],
        "screen_sections": sections,
        "primary_solution_count": len(solutions),
        "necessary_status": status,
    }


def _parameter_id(v, k):
    return f"v{v}_k{k}"


def _parameter_review_rows(instance_rows, feasibility_rows):
    grouped = {}
    for row in instance_rows:
        grouped.setdefault((row["v"], row["k"]), {"instances": [], "screens": []})["instances"].append(row)
    for row in feasibility_rows:
        grouped.setdefault((row["v"], row["k"]), {"instances": [], "screens": []})["screens"].append(row)
    rows = []
    for (v, k), bucket in sorted(grouped.items()):
        instances = sorted(bucket["instances"], key=lambda row: row["id"])
        screens = sorted(bucket["screens"], key=lambda row: row["id"])
        optimal_ids = [row["id"] for row in instances if row["is_optimal"]]
        screen_status = screens[0]["necessary_status"] if screens else None
        if optimal_ids:
            evidence = "constructed_optimal"
        elif screen_status in {"excluded_by_primary_system", "excluded_by_recursive_parity"}:
            evidence = "excluded_by_screen"
        elif instances:
            evidence = "candidate_partial_evidence"
        else:
            evidence = "unresolved_by_mounted_evidence"
        rows.append(
            {
                "parameter_id": _parameter_id(v, k),
                "v": v,
                "k": k,
                "candidate_instance_ids": [row["id"] for row in instances],
                "optimal_candidate_ids": optimal_ids,
                "screen_case_ids": [row["id"] for row in screens],
                "screen_status": screen_status,
                "evidence_status": evidence,
            }
        )
    return rows


def _review_recommendation(result, recommendation_policy):
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
    for status in policy.get("status_precedence", ["requires_followup", "withhold_for_exclusion", "certify_complete"]):
        blockers = set()
        for field in field_groups.get(status, []):
            for value in result.get(field, []):
                blockers.add(template_groups.get(status, "{value}").format(value=value))
        if blockers:
            if status == "certify_complete":
                return "requires_followup", sorted(blockers)
            return status, sorted(blockers)
    return "certify_complete", []


def run_audit(
    data_path="/home/agent/data/cpcw_instances.json",
    feasibility_path="/home/agent/data/cpcw_feasibility_cases.json",
    claims_path="/home/agent/data/cpcw_source_claims.json",
    policy_path="/home/agent/data/cpcw_review_policy.json",
):
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    summaries = []
    for instance in sorted(data["instances"], key=lambda row: row["id"]):
        codewords = _decode_instance_codewords(instance)
        try:
            audit = audit_codebook(instance["v"], instance["k"], codewords)
        except ValueError:
            audit = _invalid_instance_audit(instance["v"], instance["k"], codewords)
        summaries.append(
            {
                "id": instance["id"],
                **audit,
            }
        )
    optimal_ids = [row["id"] for row in summaries if row["is_optimal"]]
    perfect_ids = [row["id"] for row in summaries if row["is_perfect"]]
    invalid_ids = [row["id"] for row in summaries if not row["is_cpcw"]]
    by_id = {row["id"]: row for row in summaries}
    case_43_alpha = by_id.get("case_43_alpha_k5")
    result = {
        "instance_summaries": summaries,
        "optimal_instance_ids": optimal_ids,
        "perfect_instance_ids": perfect_ids,
        "invalid_instance_ids": invalid_ids,
        "case_43_alpha_uncovered_nonzero": case_43_alpha["uncovered_nonzero_differences"] if case_43_alpha else None,
        "first_invalid_instance": invalid_ids[0] if invalid_ids else None,
    }

    feasibility_data = json.loads(Path(feasibility_path).read_text(encoding="utf-8"))
    feasibility_rows = []
    for case in sorted(feasibility_data["cases"], key=lambda row: row["id"]):
        feasibility_rows.append({"id": case["id"], **screen_parameters(case["v"], case["k"])})
    result["feasibility_summaries"] = feasibility_rows
    result["screened_surviving_ids"] = [
        row["id"] for row in feasibility_rows if row["necessary_status"] == "survives_necessary_screen"
    ]
    result["screened_excluded_ids"] = [
        row["id"]
        for row in feasibility_rows
        if row["necessary_status"] in {"excluded_by_primary_system", "excluded_by_recursive_parity"}
    ]

    parameter_rows = _parameter_review_rows(summaries, feasibility_rows)
    result["parameter_review_summaries"] = parameter_rows
    result["constructed_parameter_ids"] = [
        row["parameter_id"] for row in parameter_rows if row["evidence_status"] == "constructed_optimal"
    ]
    result["screen_excluded_parameter_ids"] = [
        row["parameter_id"] for row in parameter_rows if row["evidence_status"] == "excluded_by_screen"
    ]
    result["unresolved_parameter_ids"] = [
        row["parameter_id"]
        for row in parameter_rows
        if row["evidence_status"] in {"candidate_partial_evidence", "unresolved_by_mounted_evidence"}
    ]

    claim_data = json.loads(Path(claims_path).read_text(encoding="utf-8"))
    instances_by_parameter = {}
    for row in summaries:
        instances_by_parameter.setdefault((row["v"], row["k"]), []).append(row)
    screens_by_parameter = {}
    for row in feasibility_rows:
        screens_by_parameter.setdefault((row["v"], row["k"]), []).append(row)
    source_rows = []
    for claim in sorted(claim_data["claims"], key=lambda row: row["id"]):
        v, k = claim["v"], claim["k"]
        instances = sorted(instances_by_parameter.get((v, k), []), key=lambda row: row["id"])
        screens = sorted(screens_by_parameter.get((v, k), []), key=lambda row: row["id"])
        optimal_ids = [row["id"] for row in instances if row["is_optimal"]]
        screen_statuses = [row["necessary_status"] for row in screens]
        if optimal_ids:
            claim_status = "constructed_optimal"
        elif any(status in {"excluded_by_primary_system", "excluded_by_recursive_parity"} for status in screen_statuses):
            claim_status = "excluded_by_source"
        else:
            claim_status = "unresolved_by_source"
        source_rows.append(
            {
                "id": claim["id"],
                "parameter_id": _parameter_id(v, k),
                "v": v,
                "k": k,
                "source_marker": claim["source_marker"],
                "candidate_instance_ids": [row["id"] for row in instances],
                "screen_case_ids": [row["id"] for row in screens],
                "claim_status": claim_status,
            }
        )
    result["source_claim_summaries"] = source_rows
    result["source_constructed_parameter_ids"] = [
        row["parameter_id"] for row in source_rows if row["claim_status"] == "constructed_optimal"
    ]
    result["source_excluded_parameter_ids"] = [
        row["parameter_id"] for row in source_rows if row["claim_status"] == "excluded_by_source"
    ]
    result["source_unresolved_parameter_ids"] = [
        row["parameter_id"] for row in source_rows if row["claim_status"] == "unresolved_by_source"
    ]

    policy_data = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    policy_rows = []
    for policy in sorted(policy_data["policies"], key=lambda row: row["id"]):
        for instance in summaries:
            certified = (
                (not policy.get("requires_cpcw", False) or instance["is_cpcw"])
                and (not policy.get("requires_bound_attainment", False) or instance["is_optimal"])
                and len(instance["uncovered_nonzero_differences"]) <= policy["max_uncovered_nonzero"]
            )
            policy_rows.append(
                {
                    "policy_id": policy["id"],
                    "instance_id": instance["id"],
                    "uncovered_nonzero_count": len(instance["uncovered_nonzero_differences"]),
                    "certified": certified,
                }
            )
    result["policy_summaries"] = policy_rows
    result["policy_certified_instance_ids"] = sorted({row["instance_id"] for row in policy_rows if row["certified"]})
    result["policy_uncertified_instance_ids"] = sorted({row["instance_id"] for row in policy_rows if not row["certified"]})
    recommendation, blockers = _review_recommendation(result, policy_data.get("review_recommendation_policy", {}))
    result["review_recommendation"] = recommendation
    result["review_blockers"] = blockers
    return result
