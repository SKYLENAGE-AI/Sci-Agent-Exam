"""Deterministic offline replay of assay retention and evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from ntab_preprocess.assay_filter import (
    ASSAY_KEY,
    assay_statistics,
    filter_assay_types,
    select_document_representatives,
)
from ntab_preprocess.similarity import compound_novelty_table
from ntab_preprocess.target_mirroring import assay_pair_audit, policy_excluded_assays


ACTIVITY_COLUMNS = {
    "record_id",
    "split",
    "doc_chembl_id",
    "assay_chembl_id",
    "target_chembl_id",
    "ligand_chembl_id",
    "standard_type",
    "pchembl_relation",
    "pchembl_value_filled",
    "prediction",
}
DOC_COLUMNS = {"assay_chembl_id", "doc_chembl_id", "document_year"}
FP_COLUMNS = {"ligand_chembl_id", "earliest_publication_year", "fingerprint_hex"}
TARGET_COLUMNS = {"target_a", "target_b", "sequence_identity"}


class ReplayInputError(ValueError):
    """Raised when a mounted input violates the declared contract."""


def _read_tsv(path: Path, required: set[str]) -> pd.DataFrame:
    if not path.is_file():
        raise ReplayInputError(f"missing input file: {path}")
    frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ReplayInputError(f"{path.name} missing columns: {', '.join(missing)}")
    return frame


def _number(frame: pd.DataFrame, column: str, *, nullable: bool) -> pd.Series:
    source = frame[column].replace(["", "NA"], pd.NA)
    parsed = pd.to_numeric(source, errors="coerce")
    invalid = source.notna() & parsed.isna()
    if invalid.any() or (not nullable and parsed.isna().any()):
        bad = frame.loc[invalid | parsed.isna(), column].astype(str).head(3).tolist()
        raise ReplayInputError(f"{column} contains invalid numeric values: {bad}")
    return parsed


def _validate_inputs(
    activities: pd.DataFrame,
    assay_docs: pd.DataFrame,
    target_identities: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    activities = activities.copy()
    assay_docs = assay_docs.copy()
    target_identities = target_identities.copy()
    if activities["record_id"].duplicated().any():
        raise ReplayInputError("record_id must be unique")
    if not set(activities["pchembl_relation"]).issubset({"=", ">", "<"}):
        raise ReplayInputError("pchembl_relation contains an unsupported token")
    valid_types = set(config["assay_policy"]["accepted_standard_types"])
    if not set(activities["standard_type"]).issubset(valid_types):
        raise ReplayInputError("standard_type contains an unsupported value")
    activities["pchembl_value_filled"] = _number(
        activities, "pchembl_value_filled", nullable=True
    )
    activities["prediction"] = _number(activities, "prediction", nullable=True)
    assay_docs["document_year"] = _number(
        assay_docs, "document_year", nullable=False
    ).astype(int)
    context = activities[
        ["assay_chembl_id", "split", "doc_chembl_id", "target_chembl_id", "standard_type"]
    ].drop_duplicates()
    if not context.groupby("assay_chembl_id").size().eq(1).all():
        raise ReplayInputError("each assay must map to one split, document, target, and readout")
    if not context.groupby("doc_chembl_id")["split"].nunique().eq(1).all():
        raise ReplayInputError("each document must belong to one split")
    mapping = assay_docs.drop_duplicates()
    if mapping["assay_chembl_id"].duplicated().any():
        raise ReplayInputError("assay document mapping must be one-to-one")
    if not mapping.groupby("doc_chembl_id")["document_year"].nunique().eq(1).all():
        raise ReplayInputError("each document must map to one publication year")
    expected = context[["assay_chembl_id", "doc_chembl_id"]].sort_values(
        "assay_chembl_id"
    ).reset_index(drop=True)
    observed = mapping[["assay_chembl_id", "doc_chembl_id"]].sort_values(
        "assay_chembl_id"
    ).reset_index(drop=True)
    if not expected.equals(observed):
        raise ReplayInputError("assay_documents.tsv must exactly match activity assay mappings")
    duplicate_groups = activities.groupby(
        ASSAY_KEY + ["ligand_chembl_id"], dropna=False, sort=False
    )
    for _, group in duplicate_groups:
        if len(group) <= 1:
            continue
        columns = ["pchembl_relation", "pchembl_value_filled", "prediction"]
        if any(group[column].nunique(dropna=False) != 1 for column in columns):
            raise ReplayInputError("duplicate assay-ligand rows must agree on values")
    if (target_identities["target_a"] >= target_identities["target_b"]).any():
        raise ReplayInputError("target identity rows must use canonical non-diagonal orientation")
    if target_identities.duplicated(["target_a", "target_b"]).any():
        raise ReplayInputError("target identity pairs must be unique")
    target_identities["sequence_identity"] = _number(
        target_identities, "sequence_identity", nullable=True
    )
    finite_identity = target_identities["sequence_identity"].dropna()
    if ((finite_identity < 0.0) | (finite_identity > 1.0)).any():
        raise ReplayInputError("sequence_identity must lie in [0, 1]")
    expected_pairs: set[tuple[str, str]] = set()
    contexts = activities[["doc_chembl_id", "target_chembl_id"]].drop_duplicates()
    for _, targets in contexts.groupby("doc_chembl_id", sort=False):
        unique = sorted(targets["target_chembl_id"].astype(str).unique())
        for index, left in enumerate(unique):
            for right in unique[index + 1 :]:
                expected_pairs.add((left, right))
    observed_pairs = set(
        target_identities[["target_a", "target_b"]].itertuples(index=False, name=None)
    )
    if observed_pairs != expected_pairs:
        raise ReplayInputError("target_identity.tsv must exactly cover distinct co-document target pairs")
    return activities, mapping, target_identities


def _digest(values: list[str]) -> str:
    payload = ("\n".join(sorted(values)) + "\n").encode() if values else b""
    return hashlib.sha256(payload).hexdigest()


def _status(n_cpd: int, std: float, policy: dict[str, Any]) -> str:
    if n_cpd < int(policy["minimum_unique_compounds"]):
        return "too_few_unique_compounds"
    if not math.isfinite(std):
        return "undefined_experimental_sd"
    if std < float(policy["minimum_experimental_sd"]):
        return "low_experimental_sd"
    return "qualifying"


def _inventory_rows(
    activities: pd.DataFrame,
    analysed: pd.DataFrame,
    base_qualified: pd.DataFrame,
    eligible: pd.DataFrame,
    retained: pd.DataFrame,
    pairs: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    policy = config["assay_policy"]
    affected = set(policy["apply_to_splits"])
    retained_keys = set(
        tuple(row)
        for row in retained[["split", "assay_chembl_id", "standard_type"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    base_keys = set(
        tuple(row)
        for row in base_qualified[["split", "assay_chembl_id", "standard_type"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    eligible_keys = set(
        tuple(row)
        for row in eligible[["split", "assay_chembl_id", "standard_type"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    mirror_counts: dict[tuple[str, str, str], int] = {}
    active_pairs = pairs[pairs["mirroring_flag"].astype(bool) & pairs["policy_applies"].astype(bool)]
    for row in active_pairs.itertuples(index=False):
        for key in (
            (str(row.split), str(row.assay_a), str(row.standard_type_a)),
            (str(row.split), str(row.assay_b), str(row.standard_type_b)),
        ):
            mirror_counts[key] = mirror_counts.get(key, 0) + 1
    output: list[dict[str, object]] = []
    group_columns = ["split", "doc_chembl_id", "assay_chembl_id", "standard_type"]
    for key, raw in activities.groupby(group_columns, sort=True):
        split, document_id, assay_id, standard_type = map(str, key)
        applies = split in affected
        tier = analysed[
            (analysed["split"].astype(str) == split)
            & (analysed["assay_chembl_id"].astype(str) == assay_id)
            & (analysed["standard_type"].astype(str) == standard_type)
        ]
        _, stats = assay_statistics(tier, bool(policy["only_equal_relation"]) if applies else False)
        if stats.empty:
            n_cpd = 0
            std = float("nan")
        else:
            n_cpd = int(stats.iloc[0]["n_cpd"])
            std = float(stats.iloc[0]["std"])
        assay_key = (split, assay_id, standard_type)
        base_status = _status(n_cpd, std, policy) if applies else "not_evaluated"
        final_status = (
            "target_mirroring_excluded"
            if base_status == "qualifying" and assay_key in base_keys and assay_key not in eligible_keys
            else base_status
        )
        output.append(
            {
                "split": split,
                "document_id": document_id,
                "assay_id": assay_id,
                "standard_type": standard_type,
                "n_input_rows": len(raw),
                "n_tier_rows": len(tier),
                "n_unique_compounds": n_cpd,
                "experimental_sd": std,
                "base_eligibility_status": base_status,
                "target_mirroring_pair_count": mirror_counts.get(assay_key, 0),
                "mirroring_policy_applies": applies,
                "eligibility_status": final_status,
                "retained": assay_key in retained_keys,
            }
        )
    return pd.DataFrame(output).sort_values(
        ["split", "document_id", "assay_id", "standard_type"], ignore_index=True
    )


def _document_rows(inventory: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, object]] = []
    for (split, document_id), group in inventory.groupby(["split", "document_id"], sort=True):
        base = group[group["base_eligibility_status"] == "qualifying"]
        qualifying = group[group["eligibility_status"] == "qualifying"]
        retained = group[group["retained"]]
        document_pairs = pairs[
            (pairs["split"].astype(str) == str(split))
            & (pairs["document_id"].astype(str) == str(document_id))
        ]
        output.append(
            {
                "split": str(split),
                "document_id": str(document_id),
                "n_candidate_assays": len(group),
                "n_base_qualifying_assays": len(base) if str(split) != "train" else "NA",
                "n_target_mirroring_pairs": int(document_pairs["mirroring_flag"].astype(bool).sum()),
                "n_mirroring_excluded_assays": int((group["eligibility_status"] == "target_mirroring_excluded").sum()),
                "n_qualifying_assays": len(qualifying) if str(split) != "train" else "NA",
                "n_retained_assays": len(retained),
                "retained_assay_sha256": _digest(retained["assay_id"].astype(str).tolist()),
            }
        )
    return pd.DataFrame(output)


def _performance_rows(retained: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, object]] = []
    key = ["split", "doc_chembl_id", "assay_chembl_id", "standard_type"]
    for values, group in retained.groupby(key, sort=True):
        split, document_id, assay_id, standard_type = map(str, values)
        complete = group.dropna(subset=["pchembl_value_filled", "prediction"])
        labels = complete["pchembl_value_filled"].to_numpy(dtype=float)
        predictions = complete["prediction"].to_numpy(dtype=float)
        if len(complete) >= 2 and len(set(labels)) >= 2 and len(set(predictions)) >= 2:
            pearson_r = float(pearsonr(predictions, labels).statistic)
        else:
            pearson_r = float("nan")
        r2 = pearson_r * pearson_r if math.isfinite(pearson_r) else float("nan")
        mae = float(np.mean(np.abs(predictions - labels))) if len(complete) else float("nan")
        output.append(
            {
                "split": split,
                "document_id": document_id,
                "assay_id": assay_id,
                "standard_type": standard_type,
                "n_complete_predictions": len(complete),
                "pearson_r": pearson_r,
                "r2": r2,
                "mae": mae,
            }
        )
    return pd.DataFrame(output).sort_values(
        ["split", "document_id", "assay_id", "standard_type"], ignore_index=True
    )


def _summary_rows(
    inventory: pd.DataFrame,
    pairs: pd.DataFrame,
    performance: pd.DataFrame,
    analysed: pd.DataFrame,
) -> pd.DataFrame:
    output: list[dict[str, object]] = []
    for split in sorted(inventory["split"].unique()):
        inv = inventory[inventory["split"] == split]
        perf = performance[performance["split"] == split]
        split_pairs = pairs[pairs["split"].astype(str) == str(split)]
        retained_ids = perf["assay_id"].astype(str).tolist()
        finite_r2 = perf["r2"].dropna()
        output.append(
            {
                "split": split,
                "n_documents": inv["document_id"].nunique(),
                "n_candidate_assays": len(inv),
                "n_tier_compounds": int(
                    analysed.loc[analysed["split"].astype(str) == split, "ligand_chembl_id"].nunique()
                ),
                "n_base_qualifying_assays": int((inv["base_eligibility_status"] == "qualifying").sum()) if split != "train" else "NA",
                "n_target_mirroring_pairs": int(split_pairs["mirroring_flag"].astype(bool).sum()),
                "n_mirroring_excluded_assays": int((inv["eligibility_status"] == "target_mirroring_excluded").sum()),
                "n_qualifying_assays": int((inv["eligibility_status"] == "qualifying").sum()) if split != "train" else "NA",
                "n_retained_assays": len(perf),
                "n_evaluable_assays": len(finite_r2),
                "mean_r2": float(finite_r2.mean()) if len(finite_r2) else float("nan"),
                "retained_assay_sha256": _digest(retained_ids),
            }
        )
    return pd.DataFrame(output)


def _write_tsv(frame: pd.DataFrame, path: Path) -> None:
    rendered = frame.copy()
    for column in rendered.columns:
        if pd.api.types.is_float_dtype(rendered[column]):
            rendered[column] = rendered[column].map(
                lambda value: "NA" if pd.isna(value) else f"{float(value):.8f}"
            )
    rendered = rendered.fillna("NA")
    rendered.to_csv(path, sep="\t", index=False, lineterminator="\n")


def _coverage(activities: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "fixture": "public",
                "n_splits": activities["split"].nunique(),
                "n_documents": activities["doc_chembl_id"].nunique(),
                "n_assays": activities["assay_chembl_id"].nunique(),
                "n_activity_rows": len(activities),
            }
        ]
    )


def run_replay(
    config_path: Path,
    fixture_dir: Path,
    output_dir: Path,
    *,
    require_match: bool = False,
) -> dict[str, object]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    activities = _read_tsv(fixture_dir / "activities.tsv", ACTIVITY_COLUMNS)
    assay_docs = _read_tsv(fixture_dir / "assay_documents.tsv", DOC_COLUMNS)
    fingerprints = _read_tsv(fixture_dir / "compound_fingerprints.tsv", FP_COLUMNS)
    target_identities = _read_tsv(fixture_dir / "target_identity.tsv", TARGET_COLUMNS)
    activities, assay_docs, target_identities = _validate_inputs(
        activities, assay_docs, target_identities, config
    )
    policy = config["assay_policy"]
    novelty_policy = config["novelty_tier"]
    novelty = compound_novelty_table(
        activities, assay_docs, fingerprints, list(novelty_policy["apply_to_splits"]),
        dict(novelty_policy["reference_cutoff_year_by_split"]),
        float(novelty_policy["max_similarity_exclusive"]),
    )
    keep = set(novelty.loc[novelty["novelty_status"].isin(["in_tier", "not_evaluated"]), ["split", "ligand_id"]].itertuples(index=False, name=None))
    analysed = activities[[tuple(map(str, x)) in keep for x in activities[["split", "ligand_chembl_id"]].itertuples(index=False, name=None)]].copy()
    base_qualified = filter_assay_types(
        analysed,
        assay_docs,
        list(policy["apply_to_splits"]),
        bool(policy["only_equal_relation"]),
        int(policy["minimum_unique_compounds"]),
        float(policy["minimum_experimental_sd"]),
        False,
    )
    provisional = select_document_representatives(
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
    inventory = _inventory_rows(
        activities, analysed, base_qualified, eligible, retained, pairs, config
    )
    documents = _document_rows(inventory, pairs)
    performance = _performance_rows(retained)
    summary = _summary_rows(inventory, pairs, performance, analysed)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_tsv(novelty, output_dir / "compound_novelty.tsv")
    _write_tsv(pairs, output_dir / "assay_pair_audit.tsv")
    _write_tsv(inventory, output_dir / "assay_inventory.tsv")
    _write_tsv(documents, output_dir / "document_retention.tsv")
    _write_tsv(performance, output_dir / "assay_performance.tsv")
    _write_tsv(summary, output_dir / "summary.tsv")

    release = _read_tsv(
        fixture_dir / "release_summary.tsv",
        {"fixture", "n_splits", "n_documents", "n_assays", "n_activity_rows"},
    )
    for column in ("n_splits", "n_documents", "n_assays", "n_activity_rows"):
        release[column] = _number(release, column, nullable=False).astype(int)
    differences = [] if _coverage(activities).equals(release) else ["release input-coverage counts differ"]
    receipt: dict[str, object] = {
        "status": "match" if not differences else "mismatch",
        "release_match": not differences,
        "difference_count": len(differences),
        "differences": differences,
        "output_files": [
            "compound_novelty.tsv",
            "assay_pair_audit.tsv",
            "assay_inventory.tsv",
            "document_retention.tsv",
            "assay_performance.tsv",
            "summary.tsv",
        ],
    }
    (output_dir / "reproduction.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    if require_match and differences:
        raise ReplayInputError("release summary mismatch: " + "; ".join(differences))
    return receipt


def main(argv: list[str] | None = None) -> int:
    project = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=project.parent / "analysis_config.json")
    parser.add_argument("--data-dir", type=Path, default=project / "fixtures" / "public")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-match", action="store_true")
    args = parser.parse_args(argv)
    try:
        receipt = run_replay(args.config, args.data_dir, args.output_dir, require_match=args.require_match)
    except (ReplayInputError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
