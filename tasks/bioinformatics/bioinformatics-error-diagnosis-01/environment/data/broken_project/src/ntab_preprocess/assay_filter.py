"""Utilities for deterministic assay-record filtering."""

from __future__ import annotations

import pandas as pd


ASSAY_KEY = ["assay_chembl_id", "standard_type"]


def _prepared_split(df_split: pd.DataFrame, only_equal_relation: bool) -> pd.DataFrame:
    prepared = df_split.copy()
    if only_equal_relation:
        prepared = prepared[prepared["pchembl_relation"] == "="]
    prepared = prepared.dropna(subset=["pchembl_value_filled"])
    return prepared.drop_duplicates(subset=ASSAY_KEY + ["ligand_chembl_id"])


def assay_statistics(
    df_split: pd.DataFrame,
    only_equal_relation: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the analysis rows and one statistics row per assay/readout unit."""
    prepared = _prepared_split(df_split, only_equal_relation)
    if prepared.empty:
        return prepared, pd.DataFrame(columns=ASSAY_KEY + ["n_cpd", "std"])
    statistics = (
        prepared.groupby(ASSAY_KEY, sort=True)
        .agg(
            n_cpd=("ligand_chembl_id", "nunique"),
            std=("pchembl_value_filled", "std"),
        )
        .reset_index()
    )
    return prepared, statistics


def _filter_single_split(
    df_split: pd.DataFrame,
    assay_docs_df: pd.DataFrame,
    only_equal_relation: bool,
    min_cpd_per_assay: int,
    min_std: float,
    one_assay_per_doc: bool,
) -> pd.DataFrame:
    """Return rows retained for one caller-supplied split."""
    prepared, candidates = assay_statistics(df_split, only_equal_relation)
    if candidates.empty:
        return prepared

    passing = candidates[
        (candidates["n_cpd"] >= min_cpd_per_assay)
        & (candidates["std"] >= min_std)
    ].copy()

    if one_assay_per_doc:
        doc_map = assay_docs_df[["assay_chembl_id", "doc_chembl_id"]].drop_duplicates()
        passing = passing.merge(
            doc_map,
            on="assay_chembl_id",
            how="left",
            validate="many_to_one",
        )
        if passing["doc_chembl_id"].isna().any():
            raise ValueError("every filtered assay must map to one document")
        passing = (
            passing.sort_values(
                ["doc_chembl_id", "n_cpd", "assay_chembl_id", "standard_type"],
                ascending=[True, False, True, True],
            )
            .groupby("doc_chembl_id", sort=True, as_index=False)
            .first()
        )

    passing = passing[ASSAY_KEY]
    return prepared.merge(passing, on=ASSAY_KEY, how="inner", validate="many_to_one")


def filter_assay_types(
    activities_df: pd.DataFrame,
    assay_docs_df: pd.DataFrame,
    apply_to: list[str],
    only_equal_relation: bool,
    min_cpd_per_assay: int,
    min_std: float,
    one_assay_per_doc: bool,
) -> pd.DataFrame:
    """Apply the requested assay-record policy to exact split labels."""
    apply_set = {str(value) for value in apply_to}
    affected = activities_df["split"].astype(str).isin(apply_set)
    parts = [activities_df[~affected].copy()]
    for split in sorted(apply_set):
        df_split = activities_df[activities_df["split"].astype(str) == split].copy()
        if df_split.empty:
            continue
        parts.append(
            _filter_single_split(
                df_split,
                assay_docs_df,
                only_equal_relation,
                min_cpd_per_assay,
                min_std,
                one_assay_per_doc,
            )
        )
    return pd.concat(parts, ignore_index=True)


def select_document_representatives(
    qualifying_rows: pd.DataFrame,
    assay_docs_df: pd.DataFrame,
    apply_to: list[str],
) -> pd.DataFrame:
    """Keep the largest qualifying assay/readout per document in affected splits."""
    apply_set = {str(value) for value in apply_to}
    affected = qualifying_rows["split"].astype(str).isin(apply_set)
    unaffected_rows = qualifying_rows[~affected].copy()
    candidate_rows = qualifying_rows[affected].copy()
    if candidate_rows.empty:
        return unaffected_rows.reset_index(drop=True)
    counts = (
        candidate_rows.groupby(["split"] + ASSAY_KEY, sort=True)["ligand_chembl_id"]
        .nunique()
        .rename("n_cpd")
        .reset_index()
    )
    doc_map = assay_docs_df[["assay_chembl_id", "doc_chembl_id"]].drop_duplicates()
    counts = counts.merge(doc_map, on="assay_chembl_id", how="left", validate="many_to_one")
    winners = (
        counts.sort_values(
            ["split", "doc_chembl_id", "n_cpd", "assay_chembl_id", "standard_type"],
            ascending=[True, True, False, True, True],
        )
        .groupby(["split", "doc_chembl_id"], sort=True, as_index=False)
        .first()
    )[["split"] + ASSAY_KEY]
    retained = candidate_rows.merge(
        winners, on=["split"] + ASSAY_KEY, how="inner", validate="many_to_one"
    )
    return pd.concat([unaffected_rows, retained], ignore_index=True)
