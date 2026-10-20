from pathlib import Path
import json
import shutil

import pandas as pd

from ntab_preprocess.offline_replay import run_replay


def _project() -> Path:
    return Path(__file__).resolve().parents[1]


def test_public_replay_writes_complete_receipt(tmp_path: Path) -> None:
    project = _project()
    receipt = run_replay(
        project.parent / "analysis_config.json",
        project / "fixtures" / "public",
        tmp_path,
    )
    assert set(receipt["output_files"]) == {
        "compound_novelty.tsv",
        "assay_pair_audit.tsv",
        "assay_inventory.tsv",
        "document_retention.tsv",
        "assay_performance.tsv",
        "summary.tsv",
    }
    assert receipt["release_match"] is True
    stored = json.loads((tmp_path / "reproduction.json").read_text())
    assert stored["status"] == "match"
    assert stored["difference_count"] == 0

    inventory = pd.read_csv(tmp_path / "assay_inventory.tsv", sep="\t", dtype=str)
    novelty = pd.read_csv(tmp_path / "compound_novelty.tsv", sep="\t", dtype=str)
    pairs = pd.read_csv(tmp_path / "assay_pair_audit.tsv", sep="\t", dtype=str)
    assert not novelty.duplicated(["split", "ligand_id"]).any()
    assert not inventory.duplicated(
        ["split", "document_id", "assay_id", "standard_type"]
    ).any()
    pair_key = [
        "split", "document_id", "assay_a", "standard_type_a",
        "assay_b", "standard_type_b",
    ]
    assert not pairs.duplicated(pair_key).any()
    assert (
        pairs[["assay_a", "standard_type_a"]].apply(tuple, axis=1)
        < pairs[["assay_b", "standard_type_b"]].apply(tuple, axis=1)
    ).all()
    assert set(pairs["mirroring_flag"]) <= {"True", "False"}
    assert set(pairs["policy_applies"]) <= {"True", "False"}
    documents = pd.read_csv(tmp_path / "document_retention.tsv", sep="\t", dtype=str)
    assert not documents.duplicated(["split", "document_id"]).any()
    performance = pd.read_csv(tmp_path / "assay_performance.tsv", sep="\t", dtype=str)
    assert not performance.duplicated(
        ["split", "document_id", "assay_id", "standard_type"]
    ).any()
    summary = pd.read_csv(tmp_path / "summary.tsv", sep="\t", dtype=str)
    assert set(summary["split"]) == {"train", "validation", "test"}


def test_fixture_uses_opaque_keys_and_declared_cardinality() -> None:
    fixture = _project() / "fixtures" / "public"
    activities = pd.read_csv(fixture / "activities.tsv", sep="\t", dtype=str)
    mapping = pd.read_csv(fixture / "assay_documents.tsv", sep="\t", dtype=str)
    fingerprints = pd.read_csv(fixture / "compound_fingerprints.tsv", sep="\t", dtype=str)
    identities = pd.read_csv(
        fixture / "target_identity.tsv", sep="\t", dtype=str, keep_default_na=False
    )
    assert activities["record_id"].is_unique
    assert activities["record_id"].str.fullmatch(r"REC_[0-9a-f]{12}").all()
    assert activities["doc_chembl_id"].str.fullmatch(r"DOC_[0-9a-f]{12}").all()
    assert activities["assay_chembl_id"].str.fullmatch(r"ASY_[0-9a-f]{12}").all()
    assert activities["target_chembl_id"].str.fullmatch(r"TGT_[0-9a-f]{12}").all()
    assert activities["ligand_chembl_id"].str.fullmatch(r"CMP_[0-9a-f]{12}").all()
    assert not activities["record_id"].is_monotonic_increasing
    context = activities.groupby("assay_chembl_id")[
        ["split", "doc_chembl_id", "target_chembl_id", "standard_type"]
    ].nunique()
    assert context.eq(1).all().all()
    assert mapping["assay_chembl_id"].is_unique
    assert set(mapping["assay_chembl_id"]) == set(activities["assay_chembl_id"])
    assert set(fingerprints["ligand_chembl_id"]) == set(activities["ligand_chembl_id"])
    assert fingerprints["fingerprint_hex"].str.fullmatch(r"[0-9a-f]{512}").all()
    assert (identities["target_a"] < identities["target_b"]).all()
    assert not identities.duplicated(["target_a", "target_b"]).any()
    expected_pairs = set()
    for _, document in activities.groupby("doc_chembl_id"):
        targets = sorted(document["target_chembl_id"].unique())
        expected_pairs.update(
            (left, right)
            for index, left in enumerate(targets)
            for right in targets[index + 1 :]
        )
    assert set(
        identities[["target_a", "target_b"]].itertuples(index=False, name=None)
    ) == expected_pairs


def test_replay_is_invariant_to_input_row_permutation(tmp_path: Path) -> None:
    project = _project()
    fixture = tmp_path / "fixture"
    shutil.copytree(project / "fixtures" / "public", fixture)
    for name in (
        "activities.tsv", "assay_documents.tsv", "compound_fingerprints.tsv",
        "target_identity.tsv",
    ):
        path = fixture / name
        frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
        frame.iloc[::-1].to_csv(path, sep="\t", index=False, lineterminator="\n")

    original = tmp_path / "original"
    permuted = tmp_path / "permuted"
    config = project.parent / "analysis_config.json"
    run_replay(config, project / "fixtures" / "public", original)
    run_replay(config, fixture, permuted)
    comparisons = (
        ("compound_novelty.tsv", ["split", "ligand_id"]),
        (
            "assay_pair_audit.tsv",
            [
                "split", "document_id", "assay_a", "standard_type_a",
                "assay_b", "standard_type_b",
            ],
        ),
        ("assay_inventory.tsv", ["split", "document_id", "assay_id", "standard_type"]),
        ("document_retention.tsv", ["split", "document_id"]),
        ("assay_performance.tsv", ["split", "document_id", "assay_id", "standard_type"]),
        ("summary.tsv", ["split"]),
    )
    for name, key in comparisons:
        left = pd.read_csv(original / name, sep="\t", dtype=str).sort_values(key).reset_index(drop=True)
        right = pd.read_csv(permuted / name, sep="\t", dtype=str).sort_values(key).reset_index(drop=True)
        pd.testing.assert_frame_equal(left, right)
