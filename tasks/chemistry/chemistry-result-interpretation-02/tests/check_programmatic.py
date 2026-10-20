#!/usr/bin/env python3
"""Programmatic checks for provenance-aware catalytic interpretation outputs."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
from PIL import Image


DATA_DIR = Path("/home/agent/data")
RTOL = 5e-3
ATOL = 1e-10
EXPECTED_ANSWER = {
    "claim_verdict": "partially_supported",
    "cycle_energy_span_status": "not_identifiable",
    "turnover_frequency_status": "not_identifiable",
    "screening_summary_disposition": "non_authoritative",
}
EXPECTED_UNITS = {
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
CHECK_WEIGHTS = {
    "claim_verdict": 20.0,
    "authoritative_artifact_id": 5.0,
    "cycle_energy_span_status": 5.0,
    "turnover_frequency_status": 5.0,
    "screening_summary_disposition": 4.0,
    **{name: 1.0 for name in EXPECTED_UNITS},
    "calculation_provenance": 3.0,
    **{f"reference_{name}": 2.0 for name in REFERENCE_PAIRS},
    "reference_provenance": 3.0,
    "runtime_authority_selection": 7.0,
    "runtime_authoritative_calculations": 10.0,
    "runtime_reference_semantics": 10.0,
    "runtime_cycle_eligibility": 8.0,
    "runtime_claim_direction": 12.0,
    "runtime_screening_disposition": 5.0,
    "runtime_report_reproduction": 3.0,
    "runtime_figure_reproduction": 3.0,
}


def _safe_check(name: str, fn) -> dict:
    weight = CHECK_WEIGHTS[name]
    try:
        passed = bool(fn())
        detail = ""
    except Exception as exc:
        passed = False
        detail = f"{type(exc).__name__}: {exc}"
    return {"name": name, "passed": passed, "weight": weight, "detail": detail}


def _as_bool(value: object) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes"}


def select_registry_row(data_dir: Path) -> pd.Series:
    registry = pd.read_csv(
        data_dir / "artifact_registry.csv", dtype=str, keep_default_na=False
    )
    mask = (
        registry["scientific_role"].eq("reported_segment_energetics")
        & registry["review_state"].str.casefold().eq("final")
        & registry["claim_authority"].map(_as_bool)
    )
    rows = registry.loc[mask]
    if len(rows) != 1:
        raise ValueError("registry must contain one final authoritative energetics row")
    return rows.iloc[0]


def state_row(energies: pd.DataFrame, state: str) -> pd.Series:
    rows = energies.loc[energies["state"].astype(str) == state]
    if len(rows) != 1:
        raise ValueError(f"expected one row for {state}")
    return rows.iloc[0]


def expected_context(data_dir: Path) -> dict[str, object]:
    selected = select_registry_row(data_dir)
    registry = pd.read_csv(data_dir / "artifact_registry.csv", dtype=str, keep_default_na=False)
    energies = pd.read_csv(data_dir / str(selected["path"]))
    settings = json.loads((data_dir / "calculation_settings.json").read_text())

    def rate(barrier: float) -> float:
        temperature = float(settings["temperature_k"])
        prefactor = (
            float(settings["transmission_coefficient"])
            * float(settings["boltzmann_constant_j_k"])
            * temperature
            / float(settings["planck_constant_j_s"])
        )
        return prefactor * math.exp(
            -float(barrier)
            * float(settings["joule_per_kcal"])
            / (float(settings["gas_constant_j_mol_k"]) * temperature)
        )

    ts1 = state_row(energies, "TS1")
    ts2 = state_row(energies, "TS2")
    a = state_row(energies, "A")
    c = state_row(energies, "C")
    uncat = state_row(energies, "UNCAT_TS")
    dg1 = float(ts1["delta_g_kcal_mol"]) - float(a["delta_g_kcal_mol"])
    dg2 = float(ts2["delta_g_kcal_mol"]) - float(c["delta_g_kcal_mol"])
    perturbation = float(settings["barrier_sensitivity_kcal_mol"])
    k1 = rate(dg1)
    k2 = rate(dg2)
    metrics = {
        "k_ts1_298_s_inv": k1,
        "k_ts2_298_s_inv": k2,
        "segment_rate_ratio_ts1_to_ts2": k1 / k2,
        "k_ts2_minus_perturbation_298_s_inv": rate(dg2 - perturbation),
        "k_ts2_plus_perturbation_298_s_inv": rate(dg2 + perturbation),
        "barrier_acceleration_vs_uncatalyzed": math.exp(
            (float(uncat["delta_g_kcal_mol"]) - dg2)
            * float(settings["joule_per_kcal"])
            / (
                float(settings["gas_constant_j_mol_k"])
                * float(settings["temperature_k"])
            )
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
    references: dict[str, dict[str, object]] = {}
    for name, (lhs_state, rhs_state) in REFERENCE_PAIRS.items():
        lhs = state_row(energies, lhs_state)
        rhs = state_row(energies, rhs_state)
        comparable = str(lhs["reference_zero"]) == str(rhs["reference_zero"])
        references[name] = {
            "status": "identifiable" if comparable else "not_identifiable",
            "value": (
                float(lhs["delta_g_kcal_mol"]) - float(rhs["delta_g_kcal_mol"])
                if comparable
                else None
            ),
        }
    cross_segment_known = all(
        references[name]["status"] == "identifiable"
        for name in ("c_minus_b", "d_minus_a")
    )
    has_release_state = energies["state_role"].astype(str).eq(
        "released_product_and_regenerated_catalyst"
    ).any()
    transition_states = energies.loc[
        energies["state_role"].astype(str).eq("transition_state")
    ]
    if len(transition_states) < 2:
        verdict = "inconclusive"
    else:
        local_supported = (
            transition_states["imaginary_frequency_count"].astype(float).eq(1).all()
            and transition_states["irc_backward"].astype(str).str.strip().ne("").all()
            and transition_states["irc_forward"].astype(str).str.strip().ne("").all()
        )
        if not local_supported:
            verdict = "not_supported"
        elif cross_segment_known and has_release_state:
            verdict = "supported"
        else:
            verdict = "partially_supported"
    cycle_status = (
        "identifiable" if cross_segment_known and has_release_state else "not_identifiable"
    )
    screening_rows = registry.loc[
        registry["scientific_role"].astype(str).eq("derived_cycle_summary")
    ]
    screening_authoritative = (
        len(screening_rows) == 1
        and str(screening_rows.iloc[0]["review_state"]).casefold() == "final"
        and _as_bool(screening_rows.iloc[0]["claim_authority"])
    )
    return {
        "artifact_id": str(selected["artifact_id"]),
        "metrics": metrics,
        "references": references,
        "answer": {
            "claim_verdict": verdict,
            "cycle_energy_span_status": cycle_status,
            "turnover_frequency_status": cycle_status,
            "screening_summary_disposition": (
                "authoritative" if screening_authoritative else "non_authoritative"
            ),
        },
    }


def close(actual: float, expected: float) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=RTOL, abs_tol=ATOL)


def normalize_unit(value: object) -> str:
    unit = str(value).strip().casefold()
    unit = (
        unit.replace(" ", "")
        .replace("·", "")
        .replace("⋅", "")
        .replace("−", "-")
        .replace("⁻", "-")
        .replace("¹", "1")
    )
    aliases = {
        "s^-1": "s^-1",
        "s-1": "s^-1",
        "1/s": "s^-1",
        "sec^-1": "s^-1",
        "sec-1": "s^-1",
        "dimensionless": "dimensionless",
        "unitless": "dimensionless",
        "1": "dimensionless",
        "kcal/mol": "kcal/mol",
        "kcalmol^-1": "kcal/mol",
        "kcalmol-1": "kcal/mol",
    }
    return aliases.get(unit, unit)


def load_named_rows(path: Path, name_column: str, required: set[str]) -> dict[str, list[dict]]:
    table = pd.read_csv(path)
    if not required.issubset(table.columns):
        raise ValueError(f"{path.name} lacks required columns")
    rows: dict[str, list[dict]] = {}
    for record in table.to_dict(orient="records"):
        rows.setdefault(str(record[name_column]), []).append(record)
    return rows


def load_answer(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def load_rows_or_empty(
    path: Path, name_column: str, required: set[str]
) -> dict[str, list[dict]]:
    try:
        return load_named_rows(path, name_column, required)
    except Exception:
        return {}


def valid_runtime_report(path: Path) -> bool:
    return path.is_file() and bool(path.read_text().strip())


def valid_runtime_png(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            image.verify()
            return image.format == "PNG"
    except Exception:
        return False


def row_metric_ok(rows: dict[str, list[dict]], name: str, expected: float) -> bool:
    matches = rows.get(name, [])
    if len(matches) != 1:
        return False
    row = matches[0]
    return close(row["value"], expected) and (
        normalize_unit(row["unit"]) == normalize_unit(EXPECTED_UNITS[name])
    )


def row_reference_ok(
    rows: dict[str, list[dict]], name: str, expected: dict[str, object]
) -> bool:
    matches = rows.get(name, [])
    if len(matches) != 1:
        return False
    row = matches[0]
    if str(row["status"]) != expected["status"]:
        return False
    if normalize_unit(row["unit"]) != "kcal/mol":
        return False
    if expected["value"] is None:
        return pd.isna(row["value"]) or str(row["value"]).strip() == ""
    return close(row["value"], expected["value"])


def run_runtime_case(results_dir: Path) -> dict[str, object]:
    source_code = results_dir / "code" / "interpret_cycle.py"
    if not source_code.is_file():
        raise FileNotFoundError(source_code)
    with tempfile.TemporaryDirectory(prefix="ri02-runtime-") as temp:
        root = Path(temp)
        data_dir = root / "data"
        output_dir = root / "results"
        data_dir.mkdir()
        output_dir.mkdir()

        for source in DATA_DIR.iterdir():
            if source.is_file():
                shutil.copyfile(source, data_dir / source.name)

        settings = json.loads((DATA_DIR / "calculation_settings.json").read_text())
        settings["barrier_sensitivity_kcal_mol"] = 1.35
        (data_dir / "calculation_settings.json").write_text(json.dumps(settings))

        base = pd.read_csv(DATA_DIR / "reported_energetics.csv")
        authoritative = base.copy()
        authoritative["reference_zero"] = authoritative["reference_zero"].where(
            authoritative["state"] == "UNCAT_TS", "GLOBAL"
        )
        authoritative.loc[authoritative["state"] == "A", "delta_g_kcal_mol"] = 0.0
        authoritative.loc[authoritative["state"] == "TS1", "delta_g_kcal_mol"] = 8.37
        authoritative.loc[authoritative["state"] == "B", "delta_g_kcal_mol"] = -30.06
        authoritative.loc[authoritative["state"] == "C", "delta_g_kcal_mol"] = -28.50
        authoritative.loc[authoritative["state"] == "TS2", "delta_g_kcal_mol"] = -4.37
        authoritative.loc[authoritative["state"] == "D", "delta_g_kcal_mol"] = -13.70
        authoritative.loc[authoritative["state"] == "UNCAT_TS", "delta_g_kcal_mol"] = 67.41
        release_row = {
            "segment": "product_release",
            "state": "P",
            "state_role": "released_product_and_regenerated_catalyst",
            "reference_zero": "GLOBAL",
            "delta_g_kcal_mol": -10.20,
            "delta_e_wb97xd_kcal_mol": -15.10,
            "delta_e_dlpno_ccsdt_kcal_mol": -15.24,
            "imaginary_frequency_count": 0,
            "irc_backward": "",
            "irc_forward": "",
        }
        authoritative = pd.concat(
            [authoritative, pd.DataFrame([release_row])], ignore_index=True
        )
        authoritative = authoritative.sample(frac=1.0, random_state=1907).reset_index(drop=True)
        authoritative.to_csv(data_dir / "energetics_final_q7.csv", index=False)

        decoy = base.copy()
        decoy.loc[decoy["state"] == "TS1", "delta_g_kcal_mol"] = 3.21
        decoy.loc[decoy["state"] == "TS2", "delta_g_kcal_mol"] = 4.56
        decoy.to_csv(data_dir / "reported_energetics.csv", index=False)

        registry = pd.DataFrame(
            [
                {
                    "artifact_id": "decoy-energetics-41",
                    "path": "reported_energetics.csv",
                    "scientific_role": "reported_segment_energetics",
                    "review_state": "superseded",
                    "claim_authority": "false",
                    "superseded_by": "authoritative-q7-1907",
                    "provenance": "runtime decoy",
                },
                {
                    "artifact_id": "runtime-screen-03",
                    "path": "screening_summary.csv",
                    "scientific_role": "derived_cycle_summary",
                    "review_state": "final",
                    "claim_authority": "true",
                    "superseded_by": "",
                    "provenance": "runtime claim-authoritative derived summary",
                },
                {
                    "artifact_id": "authoritative-q7-1907",
                    "path": "energetics_final_q7.csv",
                    "scientific_role": "reported_segment_energetics",
                    "review_state": "final",
                    "claim_authority": "true",
                    "superseded_by": "",
                    "provenance": "runtime authoritative record",
                },
            ]
        ).sample(frac=1.0, random_state=81)
        registry.to_csv(data_dir / "artifact_registry.csv", index=False)

        spec = importlib.util.spec_from_file_location(
            "submitted_interpret_cycle_runtime", source_code
        )
        if spec is None or spec.loader is None:
            raise ImportError("could not load submitted interpret_cycle.py")
        module = importlib.util.module_from_spec(spec)
        code_dir = str(source_code.parent)
        sys.path.insert(0, code_dir)
        try:
            # Register before exec so the module can resolve its own postponed annotations.
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                # Don't leave a half-initialised module registered — a later import
                # of this name must re-execute, not reuse the broken object.
                sys.modules.pop(spec.name, None)
                raise
        finally:
            if sys.path and sys.path[0] == code_dir:
                sys.path.pop(0)
            else:
                try:
                    sys.path.remove(code_dir)
                except ValueError:
                    pass
        analyze = getattr(module, "analyze", None)
        if not callable(analyze):
            raise AttributeError("interpret_cycle.py lacks callable analyze(data_dir, results_dir)")
        analyze(data_dir, output_dir)
        context = expected_context(data_dir)
        answer = load_answer(output_dir / "answer.json")
        metrics = load_rows_or_empty(
            output_dir / "bounded_calculations.csv",
            "metric",
            {"metric", "value", "unit", "source_artifact_id"},
        )
        references = load_rows_or_empty(
            output_dir / "reference_audit.csv",
            "comparison",
            {"comparison", "status", "value", "unit", "source_artifact_id"},
        )
        return {
            "context": context,
            "answer": answer,
            "metrics": metrics,
            "references": references,
            "report_ready": valid_runtime_report(output_dir / "report.md"),
            "figure_ready": valid_runtime_png(
                output_dir / "figures" / "rate_sensitivity.png"
            ),
        }


def check(results_dir: Path) -> tuple[float, list[dict]]:
    context = expected_context(DATA_DIR)
    answer = load_answer(results_dir / "answer.json")
    metrics = load_rows_or_empty(
        results_dir / "bounded_calculations.csv",
        "metric",
        {"metric", "value", "unit", "source_artifact_id"},
    )
    references = load_rows_or_empty(
        results_dir / "reference_audit.csv",
        "comparison",
        {"comparison", "status", "value", "unit", "source_artifact_id"},
    )
    try:
        runtime = run_runtime_case(results_dir)
        runtime_error = None
    except Exception as exc:
        runtime = {}
        runtime_error = exc

    checks = [
        _safe_check("claim_verdict", lambda: answer.get("claim_verdict") == EXPECTED_ANSWER["claim_verdict"]),
        _safe_check(
            "authoritative_artifact_id",
            lambda: answer.get("authoritative_artifact_id") == context["artifact_id"],
        ),
        _safe_check(
            "cycle_energy_span_status",
            lambda: answer.get("cycle_energy_span_status") == EXPECTED_ANSWER["cycle_energy_span_status"],
        ),
        _safe_check(
            "turnover_frequency_status",
            lambda: answer.get("turnover_frequency_status") == EXPECTED_ANSWER["turnover_frequency_status"],
        ),
        _safe_check(
            "screening_summary_disposition",
            lambda: answer.get("screening_summary_disposition") == EXPECTED_ANSWER["screening_summary_disposition"],
        ),
    ]
    checks.extend(
        _safe_check(
            name,
            lambda metric=name: row_metric_ok(metrics, metric, context["metrics"][metric]),
        )
        for name in EXPECTED_UNITS
    )
    checks.append(
        _safe_check(
            "calculation_provenance",
            lambda: all(
                len(metrics.get(name, [])) == 1
                and str(metrics[name][0]["source_artifact_id"]) == context["artifact_id"]
                for name in EXPECTED_UNITS
            ),
        )
    )
    checks.extend(
        _safe_check(
            f"reference_{name}",
            lambda comparison=name: row_reference_ok(
                references, comparison, context["references"][comparison]
            ),
        )
        for name in REFERENCE_PAIRS
    )
    checks.append(
        _safe_check(
            "reference_provenance",
            lambda: all(
                len(references.get(name, [])) == 1
                and str(references[name][0]["source_artifact_id"]) == context["artifact_id"]
                for name in REFERENCE_PAIRS
            ),
        )
    )

    def runtime_ready() -> dict[str, object]:
        if runtime_error is not None:
            raise runtime_error
        return runtime

    checks.append(
        _safe_check(
            "runtime_authority_selection",
            lambda: runtime_ready()["answer"].get("authoritative_artifact_id")
            == runtime_ready()["context"]["artifact_id"],
        )
    )
    checks.append(
        _safe_check(
            "runtime_authoritative_calculations",
            lambda: all(
                row_metric_ok(
                    runtime_ready()["metrics"],
                    name,
                    runtime_ready()["context"]["metrics"][name],
                )
                and len(runtime_ready()["metrics"].get(name, [])) == 1
                and str(runtime_ready()["metrics"][name][0]["source_artifact_id"])
                == runtime_ready()["context"]["artifact_id"]
                for name in EXPECTED_UNITS
            ),
        )
    )
    checks.append(
        _safe_check(
            "runtime_reference_semantics",
            lambda: all(
                row_reference_ok(
                    runtime_ready()["references"],
                    name,
                    runtime_ready()["context"]["references"][name],
                )
                and len(runtime_ready()["references"].get(name, [])) == 1
                and str(runtime_ready()["references"][name][0]["source_artifact_id"])
                == runtime_ready()["context"]["artifact_id"]
                for name in REFERENCE_PAIRS
            ),
        )
    )
    checks.append(
        _safe_check(
            "runtime_cycle_eligibility",
            lambda: runtime_ready()["answer"].get("cycle_energy_span_status")
            == runtime_ready()["context"]["answer"]["cycle_energy_span_status"]
            and runtime_ready()["answer"].get("turnover_frequency_status")
            == runtime_ready()["context"]["answer"]["turnover_frequency_status"],
        )
    )
    checks.append(
        _safe_check(
            "runtime_claim_direction",
            lambda: runtime_ready()["answer"].get("claim_verdict")
            == runtime_ready()["context"]["answer"]["claim_verdict"],
        )
    )
    checks.append(
        _safe_check(
            "runtime_screening_disposition",
            lambda: runtime_ready()["answer"].get("screening_summary_disposition")
            == runtime_ready()["context"]["answer"]["screening_summary_disposition"],
        )
    )
    checks.append(
        _safe_check(
            "runtime_report_reproduction",
            lambda: runtime_ready()["report_ready"],
        )
    )
    checks.append(
        _safe_check(
            "runtime_figure_reproduction",
            lambda: runtime_ready()["figure_ready"],
        )
    )

    total_weight = sum(float(item["weight"]) for item in checks)
    earned_weight = sum(float(item["weight"]) for item in checks if item["passed"])
    return earned_weight / total_weight, checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/home/agent/results"))
    parser.add_argument("--result-file", type=Path, default=Path("/tmp/eval/programmatic.json"))
    args = parser.parse_args()
    try:
        score, checks = check(args.output)
        result = {"score": round(score, 4), "checks": checks}
    except Exception as exc:
        result = {"score": 0.0, "error": f"{type(exc).__name__}: {exc}"}
    args.result_file.parent.mkdir(parents=True, exist_ok=True)
    args.result_file.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
