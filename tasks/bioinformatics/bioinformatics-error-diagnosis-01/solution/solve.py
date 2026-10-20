#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


BROKEN = '''    provisional = select_document_representatives(
        base_qualified, assay_docs, list(policy["apply_to_splits"])
    )
    pairs = assay_pair_audit(
        provisional, target_identities, config["target_mirroring_policy"]
    )
    excluded = policy_excluded_assays(pairs)
    eligible = base_qualified[
        [
            tuple(map(str, row)) not in excluded
            for row in base_qualified[["split", "assay_chembl_id", "standard_type"]]
            .itertuples(index=False, name=None)
        ]
    ].copy()
    retained = select_document_representatives(
        eligible, assay_docs, list(policy["apply_to_splits"])
    )
'''

REPAIRED = '''    pairs = assay_pair_audit(
        activities, target_identities, config["target_mirroring_policy"]
    )
    excluded = policy_excluded_assays(pairs)
    eligible = base_qualified[
        [
            tuple(map(str, row)) not in excluded
            for row in base_qualified[["split", "assay_chembl_id", "standard_type"]]
            .itertuples(index=False, name=None)
        ]
    ].copy()
    retained = select_document_representatives(
        eligible, assay_docs, list(policy["apply_to_splits"])
    )
'''

REPORT = Path(__file__).with_name("report.md").read_text(encoding="utf-8")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def table_key(rows: list[dict[str, str]], columns: tuple[str, ...]) -> set[tuple[str, ...]]:
    return {tuple(row[column] for column in columns) for row in rows}


def finite_split_means(path: Path) -> dict[str, float]:
    means: dict[str, float] = {}
    for row in read_tsv(path):
        value = row["mean_r2"]
        if value not in ("", "NA"):
            means[row["split"]] = float(value)
    return means


def bias_direction(broken: Path, repaired: Path) -> str:
    before = finite_split_means(broken / "summary.tsv")
    after = finite_split_means(repaired / "summary.tsv")
    directions: list[int] = []
    for split in sorted(before.keys() & after.keys()):
        left, right = before[split], after[split]
        if abs(left - right) <= 1e-6 + 1e-9 * max(abs(left), abs(right)):
            continue
        directions.append(1 if left > right else -1)
    if not directions:
        return "no_effect"
    if all(value > 0 for value in directions):
        return "optimistic"
    if all(value < 0 for value in directions):
        return "pessimistic"
    return "mixed"


def classify_answer(broken: Path, repaired: Path, release_match: bool) -> dict[str, object]:
    novelty_name = "compound_novelty.tsv"
    pair_name = "assay_pair_audit.tsv"
    inventory_name = "assay_inventory.tsv"
    novelty_invariant = (broken / novelty_name).read_bytes() == (repaired / novelty_name).read_bytes()
    before_pairs = table_key(
        read_tsv(broken / pair_name),
        ("split", "document_id", "assay_a", "standard_type_a", "assay_b", "standard_type_b"),
    )
    after_pairs = table_key(
        read_tsv(repaired / pair_name),
        ("split", "document_id", "assay_a", "standard_type_a", "assay_b", "standard_type_b"),
    )
    base_columns = (
        "split", "document_id", "assay_id", "standard_type", "n_input_rows",
        "n_tier_rows", "n_unique_compounds", "experimental_sd", "base_eligibility_status",
    )
    base_invariant = table_key(read_tsv(broken / inventory_name), base_columns) == table_key(
        read_tsv(repaired / inventory_name), base_columns
    )
    pair_population_restored = before_pairs < after_pairs
    diagnosed = novelty_invariant and base_invariant and pair_population_restored
    if not diagnosed:
        raise RuntimeError("replay comparison does not identify one pair-population alignment defect")
    return {
        "bug_type": "data_alignment",
        "earliest_fault": "eligibility_construction",
        "repair_scope": "eligibility_only",
        "bias_direction": bias_direction(broken, repaired),
        "fixed": bool(release_match and diagnosed),
    }


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/agent/results").resolve()
    task_root = Path(__file__).resolve().parents[1]
    mounted = Path("/home/agent/data")
    data_root = mounted if mounted.is_dir() else task_root / "environment" / "data"
    code = output / "code" / "ntab"
    output.mkdir(parents=True, exist_ok=True)
    code.parent.mkdir(parents=True, exist_ok=True)
    if code.exists():
        shutil.rmtree(code)
    shutil.copytree(
        data_root / "broken_project",
        code,
        ignore=shutil.ignore_patterns(".pytest_cache", "__pycache__", "*.pyc"),
    )
    module = code / "src" / "ntab_preprocess" / "offline_replay.py"
    source = module.read_text(encoding="utf-8")
    if source.count(BROKEN) != 1:
        raise RuntimeError("target-context audit repair target is absent or ambiguous")
    module.write_text(source.replace(BROKEN, REPAIRED), encoding="utf-8")

    replay_args = [
        "--config", str(data_root / "analysis_config.json"),
        "--data-dir", str(code / "fixtures" / "public"),
        "--require-match",
    ]
    with tempfile.TemporaryDirectory(prefix="ntab-broken-") as temporary:
        broken_output = Path(temporary)
        subprocess.run(
            [sys.executable, str(data_root / "broken_project" / "scripts" / "reproduce.py"),
             *replay_args[:-1], "--output-dir", str(broken_output), replay_args[-1]],
            check=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        subprocess.run(
            [sys.executable, str(code / "scripts" / "reproduce.py"),
             *replay_args[:-1], "--output-dir", str(output), replay_args[-1]],
            check=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        repaired_receipt = json.loads((output / "reproduction.json").read_text(encoding="utf-8"))
        answer = classify_answer(broken_output, output, repaired_receipt.get("release_match") is True)
    (output / "answer.json").write_text(json.dumps(answer, indent=2) + "\n")
    (output / "report.md").write_text(REPORT, encoding="utf-8")

    def digest(value: object) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def column_digest(filename: str, column: str) -> str:
        with (output / filename).open(encoding="utf-8", newline="") as handle:
            values = [row[column] for row in csv.DictReader(handle, delimiter="\t")]
        return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()

    receipt_path = output / "reproduction.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["_sealed_contract"] = {
        "answer": {key: digest(value) for key, value in answer.items()},
        "report": {"report": hashlib.sha256((output / "report.md").read_bytes()).hexdigest()},
        "code": {"project": hashlib.sha256(module.read_bytes()).hexdigest()},
        "assay_inventory": {
            column: column_digest("assay_inventory.tsv", column)
            for column in ("split", "document_id", "assay_id", "standard_type", "n_input_rows", "n_tier_rows", "n_unique_compounds", "experimental_sd", "base_eligibility_status", "target_mirroring_pair_count", "mirroring_policy_applies", "eligibility_status", "retained")
        },
        "compound_novelty": {
            column: column_digest("compound_novelty.tsv", column)
            for column in ("split", "ligand_id", "earliest_publication_year", "first_mounted_document_year", "reference_cutoff_year", "max_tanimoto", "nearest_reference_ligand_id", "in_configured_tier", "novelty_status")
        },
        "assay_pair_audit": {
            column: column_digest("assay_pair_audit.tsv", column)
            for column in ("split", "document_id", "assay_a", "standard_type_a", "assay_b", "standard_type_b", "target_a", "target_b", "n_shared_compounds", "target_identity", "pearson_r", "r2", "pair_status", "mirroring_flag", "policy_applies")
        },
        "document_retention": {
            column: column_digest("document_retention.tsv", column)
            for column in ("split", "document_id", "n_candidate_assays", "n_base_qualifying_assays", "n_target_mirroring_pairs", "n_mirroring_excluded_assays", "n_qualifying_assays", "n_retained_assays", "retained_assay_sha256")
        },
        "assay_performance": {
            column: column_digest("assay_performance.tsv", column)
            for column in ("split", "document_id", "assay_id", "standard_type", "n_complete_predictions", "pearson_r", "r2", "mae")
        },
        "summary": {
            column: column_digest("summary.tsv", column)
            for column in ("split", "n_documents", "n_candidate_assays", "n_tier_compounds", "n_base_qualifying_assays", "n_target_mirroring_pairs", "n_mirroring_excluded_assays", "n_qualifying_assays", "n_retained_assays", "n_evaluable_assays", "mean_r2", "retained_assay_sha256")
        },
        "reproduction": {key: digest(value) for key, value in receipt.items()},
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
