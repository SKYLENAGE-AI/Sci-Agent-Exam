#!/usr/bin/env python3
"""Resolve result provenance and reproduce the bounded interpretation outputs."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


METRIC_UNITS = {
    "k_ts1_298_s_inv": "s^-1",
    "k_ts2_298_s_inv": "s^-1",
    "segment_rate_ratio_ts1_to_ts2": "dimensionless",
    "k_ts2_minus_perturbation_298_s_inv": "s^-1",
    "k_ts2_plus_perturbation_298_s_inv": "s^-1",
    "barrier_acceleration_vs_uncatalyzed": "dimensionless",
    "delta_e_method_ts1_kcal_mol": "kcal/mol",
    "delta_e_method_ts2_kcal_mol": "kcal/mol",
}

REFERENCE_PAIRS = {
    "ts1_minus_a": ("TS1", "A"),
    "ts2_minus_c": ("TS2", "C"),
    "c_minus_b": ("C", "B"),
    "d_minus_a": ("D", "A"),
}


def _as_bool(value: object) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes"}


def resolve_authoritative_artifact(registry: pd.DataFrame) -> pd.Series:
    """Select the unique final claim-authoritative segment-energetics record."""
    required = {
        "artifact_id",
        "path",
        "scientific_role",
        "review_state",
        "claim_authority",
    }
    if not required.issubset(registry.columns):
        raise ValueError(f"artifact registry lacks columns: {sorted(required - set(registry.columns))}")
    mask = (
        registry["scientific_role"].astype(str).eq("reported_segment_energetics")
        & registry["review_state"].astype(str).str.casefold().eq("final")
        & registry["claim_authority"].map(_as_bool)
    )
    selected = registry.loc[mask]
    if len(selected) != 1:
        raise ValueError(f"expected one authoritative energetics artifact, found {len(selected)}")
    return selected.iloc[0]


def state_row(energies: pd.DataFrame, state: str) -> pd.Series:
    rows = energies.loc[energies["state"].astype(str) == state]
    if len(rows) != 1:
        raise ValueError(f"expected one row for state {state}, found {len(rows)}")
    return rows.iloc[0]


def eyring_rate(delta_g_kcal_mol: float, temperature_k: float, settings: dict) -> float:
    if temperature_k <= 0:
        raise ValueError("temperature must be positive")
    barrier_j_mol = float(delta_g_kcal_mol) * float(settings["joule_per_kcal"])
    prefactor = (
        float(settings["transmission_coefficient"])
        * float(settings["boltzmann_constant_j_k"])
        * float(temperature_k)
        / float(settings["planck_constant_j_s"])
    )
    exponent = -barrier_j_mol / (
        float(settings["gas_constant_j_mol_k"]) * float(temperature_k)
    )
    return prefactor * math.exp(exponent)


def compute_metrics(energies: pd.DataFrame, settings: dict) -> dict[str, float]:
    temperature = float(settings["temperature_k"])
    perturbation = float(settings["barrier_sensitivity_kcal_mol"])
    ts1 = state_row(energies, "TS1")
    ts2 = state_row(energies, "TS2")
    a = state_row(energies, "A")
    c = state_row(energies, "C")
    uncat = state_row(energies, "UNCAT_TS")
    if str(ts1["reference_zero"]) != str(a["reference_zero"]):
        raise ValueError("TS1 and A do not share a Gibbs-energy reference")
    if str(ts2["reference_zero"]) != str(c["reference_zero"]):
        raise ValueError("TS2 and C do not share a Gibbs-energy reference")
    dg1 = float(ts1["delta_g_kcal_mol"]) - float(a["delta_g_kcal_mol"])
    dg2 = float(ts2["delta_g_kcal_mol"]) - float(c["delta_g_kcal_mol"])
    dg_uncat = float(uncat["delta_g_kcal_mol"])
    k1 = eyring_rate(dg1, temperature, settings)
    k2 = eyring_rate(dg2, temperature, settings)
    return {
        "k_ts1_298_s_inv": k1,
        "k_ts2_298_s_inv": k2,
        "segment_rate_ratio_ts1_to_ts2": k1 / k2,
        "k_ts2_minus_perturbation_298_s_inv": eyring_rate(
            dg2 - perturbation, temperature, settings
        ),
        "k_ts2_plus_perturbation_298_s_inv": eyring_rate(
            dg2 + perturbation, temperature, settings
        ),
        "barrier_acceleration_vs_uncatalyzed": math.exp(
            (dg_uncat - dg2)
            * float(settings["joule_per_kcal"])
            / (float(settings["gas_constant_j_mol_k"]) * temperature)
        ),
        "delta_e_method_ts1_kcal_mol": abs(
            float(ts1["delta_e_wb97xd_kcal_mol"])
            - float(ts1["delta_e_dlpno_ccsdt_kcal_mol"])
        ),
        "delta_e_method_ts2_kcal_mol": abs(
            float(ts2["delta_e_wb97xd_kcal_mol"])
            - float(ts2["delta_e_dlpno_ccsdt_kcal_mol"])
        ),
    }


def audit_references(energies: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for comparison, (lhs_state, rhs_state) in REFERENCE_PAIRS.items():
        lhs = state_row(energies, lhs_state)
        rhs = state_row(energies, rhs_state)
        comparable = str(lhs["reference_zero"]) == str(rhs["reference_zero"])
        value = (
            float(lhs["delta_g_kcal_mol"]) - float(rhs["delta_g_kcal_mol"])
            if comparable
            else None
        )
        rows.append(
            {
                "comparison": comparison,
                "status": "identifiable" if comparable else "not_identifiable",
                "value": value,
                "unit": "kcal/mol",
            }
        )
    return rows


def build_answer(
    registry: pd.DataFrame,
    selected: pd.Series,
    energies: pd.DataFrame,
    reference_rows: list[dict[str, object]],
) -> dict[str, str]:
    cross_segment_known = all(
        row["status"] == "identifiable"
        for row in reference_rows
        if row["comparison"] in {"c_minus_b", "d_minus_a"}
    )
    has_release_state = energies["state_role"].astype(str).eq(
        "released_product_and_regenerated_catalyst"
    ).any()
    cycle_status = "identifiable" if cross_segment_known and has_release_state else "not_identifiable"
    transition_states = energies.loc[
        energies["state_role"].astype(str).eq("transition_state")
    ]
    if len(transition_states) < 2:
        claim_verdict = "inconclusive"
    else:
        local_supported = (
            transition_states["imaginary_frequency_count"].astype(float).eq(1).all()
            and transition_states["irc_backward"].astype(str).str.strip().ne("").all()
            and transition_states["irc_forward"].astype(str).str.strip().ne("").all()
        )
        if not local_supported:
            claim_verdict = "not_supported"
        elif cycle_status == "identifiable":
            claim_verdict = "supported"
        else:
            claim_verdict = "partially_supported"
    screening_rows = registry.loc[
        registry["scientific_role"].astype(str).eq("derived_cycle_summary")
    ]
    screening_authoritative = (
        len(screening_rows) == 1
        and str(screening_rows.iloc[0]["review_state"]).casefold() == "final"
        and _as_bool(screening_rows.iloc[0]["claim_authority"])
    )
    return {
        "claim_verdict": claim_verdict,
        "authoritative_artifact_id": str(selected["artifact_id"]),
        "cycle_energy_span_status": cycle_status,
        "turnover_frequency_status": (
            "identifiable" if cycle_status == "identifiable" else "not_identifiable"
        ),
        "screening_summary_disposition": (
            "authoritative" if screening_authoritative else "non_authoritative"
        ),
    }


def write_metrics(
    metrics: dict[str, float], artifact_id: str, output_path: Path
) -> None:
    rows = [
        {
            "metric": name,
            "value": value,
            "unit": METRIC_UNITS[name],
            "source_artifact_id": artifact_id,
        }
        for name, value in metrics.items()
    ]
    pd.DataFrame(rows).to_csv(output_path, index=False, float_format="%.12g")


def write_reference_audit(
    rows: list[dict[str, object]], artifact_id: str, output_path: Path
) -> None:
    enriched = [dict(row, source_artifact_id=artifact_id) for row in rows]
    pd.DataFrame(enriched).to_csv(output_path, index=False, float_format="%.12g")


def make_figure(energies: pd.DataFrame, settings: dict, output_path: Path) -> None:
    ts1 = state_row(energies, "TS1")
    ts2 = state_row(energies, "TS2")
    a = state_row(energies, "A")
    c = state_row(energies, "C")
    dg1 = float(ts1["delta_g_kcal_mol"]) - float(a["delta_g_kcal_mol"])
    dg2 = float(ts2["delta_g_kcal_mol"]) - float(c["delta_g_kcal_mol"])
    perturbation = float(settings["barrier_sensitivity_kcal_mol"])
    temperatures = np.linspace(
        float(settings["plot_temperature_min_k"]),
        float(settings["plot_temperature_max_k"]),
        int(settings["plot_temperature_points"]),
    )
    k1 = np.array([eyring_rate(dg1, t, settings) for t in temperatures])
    k2 = np.array([eyring_rate(dg2, t, settings) for t in temperatures])
    k2_fast = np.array(
        [eyring_rate(dg2 - perturbation, t, settings) for t in temperatures]
    )
    k2_slow = np.array(
        [eyring_rate(dg2 + perturbation, t, settings) for t in temperatures]
    )
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    ax.plot(temperatures, k1, color="#1565c0", linewidth=2.2, label="TS1 segment rate")
    ax.plot(temperatures, k2, color="#c62828", linewidth=2.2, label="TS2 segment rate")
    ax.fill_between(
        temperatures,
        k2_slow,
        k2_fast,
        color="#ef9a9a",
        alpha=0.45,
        label="TS2 deterministic barrier scenario",
    )
    ax.axvline(
        float(settings["temperature_k"]),
        color="#424242",
        linestyle="--",
        linewidth=1.2,
        label="298.15 K",
    )
    ax.set_yscale("log")
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel("Conditional segment Eyring rate (s$^{-1}$)")
    ax.set_title("Segment kinetics; not an identifiable turnover frequency")
    ax.grid(True, which="both", alpha=0.24)
    ax.legend(loc="best", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def write_report(
    data_dir: Path,
    registry: pd.DataFrame,
    selected: pd.Series,
    metrics: dict[str, float],
    reference_rows: list[dict[str, object]],
    answer: dict[str, str],
    output_path: Path,
) -> None:
    charges = pd.read_csv(data_dir / "natural_charges.csv")
    bonds = pd.read_csv(data_dir / "bond_metrics.csv")
    screening_meta = registry.loc[
        registry["scientific_role"].astype(str).eq("derived_cycle_summary")
    ]
    if len(screening_meta) != 1:
        raise ValueError("expected one derived cycle summary artifact")
    screening = pd.read_csv(data_dir / str(screening_meta.iloc[0]["path"])).iloc[0]

    def bond(state: str, name: str) -> float:
        row = bonds.loc[(bonds["state"] == state) & (bonds["bond"] == name)]
        return float(row.iloc[0]["value_angstrom"])

    def charge(state: str, method: str, atom: str) -> float:
        row = charges.loc[(charges["state"] == state) & (charges["method"] == method)]
        return float(row.iloc[0][f"{atom}_charge_e"])

    reference = {row["comparison"]: row for row in reference_rows}
    k2 = metrics["k_ts2_298_s_inv"]
    minutes = 1.0 / k2 / 60.0
    omega_h_charges = (
        f"{charge('TS2', 'omegaB97XD', 'h2'):+.2f}/"
        f"{charge('TS2', 'omegaB97XD', 'h3'):+.2f}"
    )
    m06_h_charges = (
        f"{charge('TS2', 'M06', 'h2'):+.2f}/"
        f"{charge('TS2', 'M06', 'h3'):+.2f}"
    )
    report = f"""# Evidence assessment for CAl3MgH2- acetone hydrogenation

## Provenance decision

The claim-authoritative result is `{selected['artifact_id']}` at
`{selected['path']}`: the registry marks it final, claim-authoritative, and a
transcription of the peer-reviewed segment energetics. The screening export
`{screening['artifact_id']}` is superseded and non-authoritative. Its clean
summary (a {float(screening['cycle_energy_span_kcal_mol']):.2f} kcal/mol energy
span, {float(screening['predicted_tof_298_s_inv']):.3g} s^-1 predicted TOF, and
`{screening['claim_verdict']}` verdict) is internally consistent with
treating TS2's segment barrier as a complete-cycle span, but that premise is
not licensed by the authoritative energy references.

## Mechanistic evidence

TS1 and TS2 each have one imaginary frequency and their reported IRCs connect
A-TS1-B and C-TS2-D, respectively. This validates the two local saddle/minimum
connections, not their dominance or a steady-state catalytic flux. The
structural and charge changes support the proposed chemistry: H2-H3 lengthens
from {bond('C', 'H2-H3'):.2f} to {bond('TS2', 'H2-H3'):.2f} angstrom while
Mg-H2 and O-H3 contract to {bond('TS2', 'Mg-H2'):.2f} and
{bond('TS2', 'O-H3'):.2f} angstrom. TS2 H2/H3 charges are
{omega_h_charges} |e| with omegaB97XD and {m06_h_charges} |e| with M06. The
preserved opposite signs and bond changes jointly support heterolytic H2
cleavage.

The source's recovery argument concerns the catalyst-like geometry inside bound
product complex D. D still contains a 2.17 angstrom Mg-O contact and the paper
describes a stabilizing 2.28 angstrom hydrogen bond to the cluster. It does not
supply product-release thermochemistry or a release transition state, so it
does not demonstrate regenerated free catalyst or repeated turnover (Malhan
and Thirumoorthy, 2026, Table 2 and Figure 5).

## Kinetics, references, and uncertainty

The authoritative barriers give segment Eyring rates of
{metrics['k_ts1_298_s_inv']:.3g} and {k2:.3g} s^-1 at 298.15 K. The TS2 event's
reciprocal time is about {minutes:.1f} minutes under the TST assumptions. These
are segment-conditioned rates, not a TOF. The +/- barrier scenario changes the
TS2 rate to {metrics['k_ts2_minus_perturbation_298_s_inv']:.3g} and
{metrics['k_ts2_plus_perturbation_298_s_inv']:.3g} s^-1; it is deterministic
sensitivity, not a confidence interval.

The reference audit identifies TS1-A ({reference['ts1_minus_a']['value']:.2f}
kcal/mol) and TS2-C ({reference['ts2_minus_c']['value']:.2f} kcal/mol), but
`c_minus_b` and `d_minus_a` are `{reference['c_minus_b']['status']}` and
`{reference['d_minus_a']['status']}`. A and C are different zeros, so the
inter-segment offset is absent. Combining the displayed profiles would mix
reference states. Together with missing product release, this prevents an
energy span, microkinetic closure, and TOF from being identified.

The study optimized geometries and evaluated frequencies with
omegaB97XD/def2-TZVPP (with M06 as a DFT comparison) and applied
DLPNO-CCSD(T)/def2-TZVPP electronic single points on the DFT geometries. The
modeled uncatalyzed/TS2 barrier contrast corresponds to a factor of
{metrics['barrier_acceleration_vs_uncatalyzed']:.3g}, but it is not an observed
rate enhancement, and its different reactant convention does not repair the
missing cycle reference. The electronic single-point discrepancies are only
{metrics['delta_e_method_ts1_kcal_mol']:.2f} and
{metrics['delta_e_method_ts2_kcal_mol']:.2f} kcal/mol at TS1 and TS2. They
support electronic-energy agreement on shared geometries, not full Gibbs,
standard-state, structural, environmental, or model-form uncertainty.

## Scope, verdict, and follow-up

This is a bare gas-phase anion calculation. Counterion and solvation fields
could differentially stabilize ionic intermediates and reorder the barriers.
Aggregation or alternative low-lying cluster structures could replace the
modeled active site, while decomposition would reduce active-species
availability. The article also notes the lack of an effective
laboratory synthesis route for stable planar-tetracoordinate-carbon species,
and reports no rate, catalyst recovery, or turnover count.

The verdict is **{answer['claim_verdict']}**: the two local transformations are
computationally supported, but cycle-level catalytic viability and practical
turnover are not established.

The decisive computational follow-up is a common-standard-state free-energy
cycle including association, B/H2-to-C connection, product release to free
product plus regenerated catalyst, competing paths, and uncertainty, followed
by energy-span or microkinetic analysis. The
experimental follow-up is to realize and characterize the catalyst in a
defined counterion/environment, then measure rate, selectivity, catalyst
recovery, and repeated turnover rather than a single product event.

![Segment-rate sensitivity](figures/rate_sensitivity.png)
"""
    output_path.write_text(report)


def analyze(data_dir: Path, results_dir: Path) -> dict[str, object]:
    data_dir = Path(data_dir)
    results_dir = Path(results_dir)
    registry = pd.read_csv(data_dir / "artifact_registry.csv", dtype=str, keep_default_na=False)
    selected = resolve_authoritative_artifact(registry)
    energies = pd.read_csv(data_dir / str(selected["path"]))
    settings = json.loads((data_dir / "calculation_settings.json").read_text())
    metrics = compute_metrics(energies, settings)
    reference_rows = audit_references(energies)
    answer = build_answer(registry, selected, energies, reference_rows)

    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "figures").mkdir(parents=True, exist_ok=True)
    write_metrics(metrics, str(selected["artifact_id"]), results_dir / "bounded_calculations.csv")
    write_reference_audit(reference_rows, str(selected["artifact_id"]), results_dir / "reference_audit.csv")
    (results_dir / "answer.json").write_text(json.dumps(answer, indent=2))
    make_figure(energies, settings, results_dir / "figures" / "rate_sensitivity.png")
    write_report(
        data_dir,
        registry,
        selected,
        metrics,
        reference_rows,
        answer,
        results_dir / "report.md",
    )
    return {"answer": answer, "metrics": metrics, "reference_audit": reference_rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("/home/agent/data"))
    parser.add_argument("--results-dir", type=Path, default=Path("/home/agent/results"))
    args = parser.parse_args()
    analyze(args.data_dir, args.results_dir)


if __name__ == "__main__":
    main()
