"""Same-document target-mirroring evidence for the offline replay."""

from __future__ import annotations

from itertools import combinations
import math
from typing import Any

import pandas as pd
from scipy.stats import pearsonr


PAIR_COLUMNS = [
    "split",
    "document_id",
    "assay_a",
    "standard_type_a",
    "assay_b",
    "standard_type_b",
    "target_a",
    "target_b",
    "n_shared_compounds",
    "target_identity",
    "pearson_r",
    "r2",
    "pair_status",
    "mirroring_flag",
    "policy_applies",
]


def _identity_map(target_identities: pd.DataFrame) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    for row in target_identities.itertuples(index=False):
        left, right = str(row.target_a), str(row.target_b)
        value = float(row.sequence_identity) if pd.notna(row.sequence_identity) else float("nan")
        result[(left, right)] = value
    return result


def _pair_status(
    n_shared: int,
    identity: float,
    r2: float,
    policy: dict[str, Any],
) -> str:
    if n_shared < int(policy["minimum_shared_compounds"]):
        return "too_few_shared_compounds"
    if not math.isfinite(identity):
        return "missing_target_identity"
    if identity >= float(policy["maximum_sequence_identity_exclusive"]):
        return "target_identity_not_below_threshold"
    if not math.isfinite(r2):
        return "undefined_correlation"
    if r2 < float(policy["minimum_r2_inclusive"]):
        return "low_correlation"
    return "target_mirroring"


def assay_pair_audit(
    activities: pd.DataFrame,
    target_identities: pd.DataFrame,
    policy: dict[str, Any],
) -> pd.DataFrame:
    """Audit every same-document assay/readout pair from raw source-valid rows."""
    prepared = activities.copy()
    if bool(policy["only_equal_relation"]):
        prepared = prepared[prepared["pchembl_relation"] == "="]
    prepared = prepared.dropna(subset=["pchembl_value_filled"])
    endpoint = ["assay_chembl_id", "standard_type"]
    prepared = prepared.drop_duplicates(subset=endpoint + ["ligand_chembl_id"])
    identity = _identity_map(target_identities)
    applies = set(map(str, policy["apply_to_splits"]))
    output: list[dict[str, object]] = []
    grouping = ["split", "doc_chembl_id"]
    for (split, document), raw_document_rows in activities.groupby(grouping, sort=True):
        document_rows = prepared[
            (prepared["split"].astype(str) == str(split))
            & (prepared["doc_chembl_id"].astype(str) == str(document))
        ]
        contexts = (
            raw_document_rows[["assay_chembl_id", "standard_type", "target_chembl_id"]]
            .drop_duplicates()
            .sort_values(endpoint)
        )
        endpoints = list(contexts.itertuples(index=False, name=None))
        for left, right in combinations(endpoints, 2):
            assay_a, standard_a, target_a = map(str, left)
            assay_b, standard_b, target_b = map(str, right)
            a = document_rows[
                (document_rows["assay_chembl_id"].astype(str) == assay_a)
                & (document_rows["standard_type"].astype(str) == standard_a)
            ][["ligand_chembl_id", "pchembl_value_filled"]].rename(
                columns={"pchembl_value_filled": "value_a"}
            )
            b = document_rows[
                (document_rows["assay_chembl_id"].astype(str) == assay_b)
                & (document_rows["standard_type"].astype(str) == standard_b)
            ][["ligand_chembl_id", "pchembl_value_filled"]].rename(
                columns={"pchembl_value_filled": "value_b"}
            )
            shared = a.merge(b, on="ligand_chembl_id", how="inner", validate="one_to_one")
            values_a = shared["value_a"].to_numpy(dtype=float)
            values_b = shared["value_b"].to_numpy(dtype=float)
            if len(shared) >= 2 and len(set(values_a)) >= 2 and len(set(values_b)) >= 2:
                r = float(pearsonr(values_a, values_b).statistic)
            else:
                r = float("nan")
            r2 = r * r if math.isfinite(r) else float("nan")
            if target_a == target_b:
                sequence_identity = 1.0
            else:
                sequence_identity = identity[tuple(sorted((target_a, target_b)))]
            status = _pair_status(len(shared), sequence_identity, r2, policy)
            output.append(
                {
                    "split": str(split),
                    "document_id": str(document),
                    "assay_a": assay_a,
                    "standard_type_a": standard_a,
                    "assay_b": assay_b,
                    "standard_type_b": standard_b,
                    "target_a": target_a,
                    "target_b": target_b,
                    "n_shared_compounds": len(shared),
                    "target_identity": sequence_identity,
                    "pearson_r": r,
                    "r2": r2,
                    "pair_status": status,
                    "mirroring_flag": status == "target_mirroring",
                    "policy_applies": str(split) in applies,
                }
            )
    return pd.DataFrame(output, columns=PAIR_COLUMNS).sort_values(
        ["split", "document_id", "assay_a", "standard_type_a", "assay_b", "standard_type_b"],
        ignore_index=True,
    )


def policy_excluded_assays(pair_audit: pd.DataFrame) -> set[tuple[str, str, str]]:
    """Return policy-active assay/readout endpoints incident to mirror edges."""
    excluded: set[tuple[str, str, str]] = set()
    active = pair_audit[
        pair_audit["mirroring_flag"].astype(bool)
        & pair_audit["policy_applies"].astype(bool)
    ]
    for row in active.itertuples(index=False):
        excluded.add((str(row.split), str(row.assay_a), str(row.standard_type_a)))
        excluded.add((str(row.split), str(row.assay_b), str(row.standard_type_b)))
    return excluded
