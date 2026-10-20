#!/usr/bin/env python3
"""Check the task's closed, final synthesis and transfer conclusions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


GOLDEN = {
    "synthesis_verdict": "retain_generator_and_require_staged_validation",
    "subclaim_verdicts": {
        "DISCOVERY_FRONT_END_VALUE": "supported",
        "SUN_IS_LAB_READINESS": "unsupported",
        "GENERATED_IDENTITY_IS_DECISION_STABLE": "unsupported",
        "DIRECT_ROUTING_IS_JUSTIFIED": "unsupported",
    },
    "evidence_statuses": {
        "P1_LAYER_GROUP_CONTROL": "directly_supported",
        "P1_SUN_TO_SYNTHESIZABILITY": "extrapolated",
        "P2_BENCHMARK_RANK_TO_SLAYERGEN": "extrapolated",
        "P3_SUCCESS_RATE_TO_SLAYERGEN": "extrapolated",
        "P4_IDENTITY_TRANSFER": "extrapolated",
    },
}

CHECK_WEIGHTS = {
    "synthesis_verdict": 8.0,
    "DISCOVERY_FRONT_END_VALUE": 5.0,
    "SUN_IS_LAB_READINESS": 7.0,
    "GENERATED_IDENTITY_IS_DECISION_STABLE": 7.0,
    "DIRECT_ROUTING_IS_JUSTIFIED": 8.0,
    "P1_LAYER_GROUP_CONTROL": 2.0,
    "P1_SUN_TO_SYNTHESIZABILITY": 2.0,
    "P2_BENCHMARK_RANK_TO_SLAYERGEN": 2.0,
    "P3_SUCCESS_RATE_TO_SLAYERGEN": 2.0,
    "P4_IDENTITY_TRANSFER": 2.0,
}

SUBCLAIM_KEYS = frozenset(GOLDEN["subclaim_verdicts"])
EVIDENCE_STATUS_KEYS = frozenset(GOLDEN["evidence_statuses"])


def _submitted_value(results_dir: Path, name: str):
    """Read one independently weighted scientific conclusion."""
    submitted = json.loads((results_dir / "answer.json").read_text(encoding="utf-8"))
    if not isinstance(submitted, dict):
        raise TypeError("answer root is not an object")
    if name == "synthesis_verdict":
        return submitted.get(name)

    if name in SUBCLAIM_KEYS:
        section_name = "subclaim_verdicts"
    elif name in EVIDENCE_STATUS_KEYS:
        section_name = "evidence_statuses"
    else:
        raise KeyError(f"unknown conclusion: {name}")

    section = submitted.get(section_name)
    if not isinstance(section, dict):
        raise TypeError(f"{section_name} is not an object")
    return section.get(name)


def _check_value(results_dir: Path, name: str, expected: str) -> dict:
    """Evaluate one conclusion without coupling unrelated partial credit."""
    try:
        passed = _submitted_value(results_dir, name) == expected
        detail = ""
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        passed = False
        detail = f"value unavailable: {type(exc).__name__}"
    return {
        "name": name,
        "passed": passed,
        "weight": CHECK_WEIGHTS[name],
        "detail": detail,
    }


def check(results_dir: Path) -> tuple[float, list[dict]]:
    expected = {
        "synthesis_verdict": GOLDEN["synthesis_verdict"],
        **GOLDEN["subclaim_verdicts"],
        **GOLDEN["evidence_statuses"],
    }
    checks = [
        _check_value(results_dir, name, expected_value)
        for name, expected_value in expected.items()
    ]
    total = sum(item["weight"] for item in checks)
    earned = sum(item["weight"] for item in checks if item["passed"])
    return earned / total, checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/home/agent/results"))
    parser.add_argument(
        "--result-file",
        type=Path,
        default=Path("/tmp/eval/programmatic.json"),
    )
    args = parser.parse_args()

    score, checks = check(args.output)
    result = {"score": round(score, 4), "checks": checks}
    args.result_file.parent.mkdir(parents=True, exist_ok=True)
    args.result_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
