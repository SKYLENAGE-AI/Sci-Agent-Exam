"""Fingerprint and Tanimoto operations used by the offline benchmark replay."""

import multiprocessing
from functools import partial

import numpy as np
try:  # Optional for the mounted precomputed-fingerprint replay.
    from rdkit import Chem, DataStructs
    from rdkit.Chem import AllChem, rdFingerprintGenerator
    from rdkit.DataStructs.cDataStructs import ExplicitBitVect
except ImportError:  # pragma: no cover - legacy SMILES helpers only
    Chem = DataStructs = AllChem = rdFingerprintGenerator = None
    ExplicitBitVect = object
from tqdm import tqdm


def parse_fingerprint_hex(value: str, bits: int = 2048) -> int:
    """Parse one fixed-width precomputed binary fingerprint."""
    token = str(value)
    if len(token) != bits // 4 or token.lower() != token:
        raise ValueError("fingerprint_hex must be fixed-width lowercase hexadecimal")
    parsed = int(token, 16)
    if parsed.bit_length() > bits:
        raise ValueError("fingerprint exceeds configured bit width")
    return parsed


def int_tanimoto(left: int, right: int) -> float:
    union = (left | right).bit_count()
    return (left & right).bit_count() / union if union else 1.0


def compound_novelty_table(
    activities,
    assay_documents,
    fingerprints,
    apply_to_splits: list[str],
    reference_cutoff_year_by_split: dict[str, int],
    threshold: float,
):
    """Compute complete split-compound novelty against the declared prior-year pool."""
    import pandas as pd

    catalog = fingerprints.copy()
    catalog["earliest_publication_year"] = pd.to_numeric(
        catalog["earliest_publication_year"], errors="raise"
    ).astype(int)
    catalog["_fp"] = pd.Series(
        [parse_fingerprint_hex(value) for value in catalog["fingerprint_hex"]],
        index=catalog.index,
        dtype=object,
    )
    if catalog["ligand_chembl_id"].duplicated().any():
        raise ValueError("compound fingerprint identifiers must be unique")
    fp_by_id = catalog.set_index("ligand_chembl_id")["_fp"].to_dict()
    year_by_id = catalog.set_index("ligand_chembl_id")["earliest_publication_year"].to_dict()
    observed = set(activities["ligand_chembl_id"].astype(str))
    if observed != set(fp_by_id):
        raise ValueError("compound_fingerprints.tsv must exactly cover activity ligands")
    document_year = assay_documents[["doc_chembl_id", "document_year"]].drop_duplicates()
    occurrence = activities[["ligand_chembl_id", "doc_chembl_id"]].merge(
        document_year, on="doc_chembl_id", how="left", validate="many_to_one"
    )
    if occurrence["document_year"].isna().any():
        raise ValueError("every mounted activity document must have a publication year")
    first_mounted_document_year = (
        occurrence.assign(document_year=pd.to_numeric(occurrence["document_year"], errors="raise"))
        .groupby("ligand_chembl_id")["document_year"].min().astype(int).to_dict()
    )
    output = []
    for (split, ligand), _ in activities.groupby(["split", "ligand_chembl_id"], sort=True):
        split, ligand = str(split), str(ligand)
        if split not in set(apply_to_splits):
            output.append({"split": split, "ligand_id": ligand,
                "earliest_publication_year": year_by_id[ligand],
                "first_mounted_document_year": first_mounted_document_year[ligand],
                "reference_cutoff_year": "NA",
                "max_tanimoto": float("nan"), "nearest_reference_ligand_id": "NA",
                "in_configured_tier": "NA", "novelty_status": "not_evaluated"})
            continue
        cutoff = int(reference_cutoff_year_by_split[split])
        reference_ids = sorted(
            x for x in observed if year_by_id[x] < cutoff
        )
        if not reference_ids:
            maximum, nearest = 0.0, "NA"
        else:
            scored = [(int_tanimoto(fp_by_id[ligand], fp_by_id[x]), x) for x in reference_ids]
            maximum, nearest = sorted(scored, key=lambda x: (-x[0], x[1]))[0]
        in_tier = maximum < float(threshold)
        output.append({"split": split, "ligand_id": ligand,
            "earliest_publication_year": year_by_id[ligand],
            "first_mounted_document_year": first_mounted_document_year[ligand],
            "reference_cutoff_year": cutoff,
            "max_tanimoto": maximum, "nearest_reference_ligand_id": nearest,
            "in_configured_tier": in_tier, "novelty_status": "in_tier" if in_tier else "out_of_tier"})
    return pd.DataFrame(output)


# ---------------------------------------------------------------------------
# ECFP4 fingerprint computation
# ---------------------------------------------------------------------------


def _process_one(args: tuple[str, str]) -> tuple[str, np.ndarray] | None:
    """Parse one SMILES and return (name, fingerprint) or None on failure.

    Must be a module-level function so it can be pickled for multiprocessing.
    """
    name, smi = args
    fpgen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    mol = Chem.MolFromSmiles(smi, sanitize=True)
    if mol is None:
        print(f"WARNING: could not parse SMILES, skipping. name={name}, smiles={smi}")
        return None
    mol = AllChem.RemoveAllHs(mol)
    return name, fpgen.GetFingerprintAsNumPy(mol)


def compute_ecfp4_fingerprints(
    mol_names: list[str],
    smiles: list[str],
    n_jobs: int = 1,
    chunksize: int = 256,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute ECFP4 fingerprints (radius=2, size=2048) for a list of molecules.

    Molecules that fail to parse are skipped and excluded from the output.

    Preprocessing applied:
    - Sanitization via RDKit (aromaticity, valence checking)
    - Explicit Hs removed
    - Note: multi-component SMILES (e.g. salts like "CC(=O)[O-].[Na+]") are NOT
      stripped to the largest fragment. ~4% of ChEMBL SMILES are affected. This is
      a conscious choice to keep the preprocessing simple; be aware that counterion
      fragments will influence the fingerprint for those molecules.

    Args:
        mol_names: Molecule identifiers, one per SMILES.
        smiles: SMILES strings.
        n_jobs: Number of worker processes. 1 = single-process (default).
            -1 = use all available CPUs (``multiprocessing.cpu_count()``).
        chunksize: Number of molecules sent to each worker at a time.
            Larger values reduce IPC overhead but increase memory per worker.

    Returns:
        Tuple of (names, fingerprints) as numpy arrays, with failed parses removed.
        names shape: (N,), fingerprints shape: (N, 2048).
    """
    pairs = list(zip(mol_names, smiles))

    if n_jobs == -1:
        n_jobs = multiprocessing.cpu_count()

    if n_jobs == 1:
        results = [_process_one(p) for p in tqdm(pairs, desc="Computing ECFP4")]
    else:
        with multiprocessing.Pool(processes=n_jobs) as pool:
            results = list(
                tqdm(
                    pool.imap(_process_one, pairs, chunksize=chunksize),
                    total=len(pairs),
                    desc=f"Computing ECFP4 ({n_jobs} workers)",
                )
            )

    out_names = []
    out_fps = []
    for r in results:
        if r is not None:
            out_names.append(r[0])
            out_fps.append(r[1])

    return np.array(out_names), np.array(out_fps)


# ---------------------------------------------------------------------------
# Tanimoto similarity filter
# ---------------------------------------------------------------------------


def _np_to_bitvect(fp: np.ndarray) -> ExplicitBitVect:
    """Convert a 1D uint8 numpy array to an RDKit ExplicitBitVect."""
    ebv = ExplicitBitVect(len(fp))
    for idx in np.where(fp == 1)[0]:
        ebv.SetBit(int(idx))
    return ebv


def _compute_max_similarity(
    args: tuple[int, ExplicitBitVect],
    reference_bvs: list[ExplicitBitVect],
    reference_ids: np.ndarray,
) -> tuple[int, float, str | None]:
    """Return (candidate_index, max_similarity, most_similar_reference_id)."""
    idx, candidate_bv = args
    if len(reference_bvs) == 0:
        return idx, 0.0, None
    similarities = DataStructs.BulkTanimotoSimilarity(candidate_bv, reference_bvs)
    best = int(np.argmax(similarities))
    return idx, float(similarities[best]), reference_ids[best]


def filter_by_tanimoto(
    candidate_fps: np.ndarray,
    reference_fps: np.ndarray,
    reference_ids: np.ndarray,
    threshold: float,
    n_jobs: int = 1,
    chunksize: int = 256,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each candidate fingerprint, compute the maximum Tanimoto similarity
    against all reference fingerprints.

    Args:
        candidate_fps: Binary fingerprints to evaluate, shape (N, fp_size).
        reference_fps: Binary fingerprints to compare against, shape (M, fp_size).
        reference_ids: Identifiers for each reference fingerprint, shape (M,).
        threshold: A candidate is considered novel if its max similarity is
            strictly less than this value.
        n_jobs: Number of worker processes. 1 = single-process (default).
            -1 = use all available CPUs.
        chunksize: Number of candidates sent to each worker at a time.

    Returns:
        Tuple of three arrays, all of length N:
        - is_novel: bool array, True where max similarity < threshold.
        - max_similarities: float array of max Tanimoto similarity per candidate.
        - most_similar_ids: array of the reference ID with highest similarity
            per candidate (None if reference set is empty).
    """
    if len(candidate_fps) == 0:
        return (
            np.empty(0, dtype=bool),
            np.empty(0, dtype=float),
            np.empty(0, dtype=object),
        )

    reference_bvs = [_np_to_bitvect(fp) for fp in reference_fps]
    candidate_bvs = [(i, _np_to_bitvect(fp)) for i, fp in enumerate(candidate_fps)]

    worker = partial(
        _compute_max_similarity,
        reference_bvs=reference_bvs,
        reference_ids=reference_ids,
    )

    if n_jobs == -1:
        n_jobs = multiprocessing.cpu_count()

    if n_jobs == 1:
        results = [worker(item) for item in tqdm(candidate_bvs, desc="Tanimoto filter")]
    else:
        with multiprocessing.Pool(processes=n_jobs) as pool:
            results = list(
                tqdm(
                    pool.imap(worker, candidate_bvs, chunksize=chunksize),
                    total=len(candidate_bvs),
                    desc=f"Tanimoto filter ({n_jobs} workers)",
                )
            )

    # pool.imap preserves order, but sort defensively in case this is
    # ever switched to imap_unordered.
    results.sort(key=lambda r: r[0])

    max_similarities = np.array([r[1] for r in results], dtype=float)
    most_similar_ids = np.array([r[2] for r in results], dtype=object)
    is_novel = max_similarities < threshold

    return is_novel, max_similarities, most_similar_ids
