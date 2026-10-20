#!/usr/bin/env python3
"""Programmatic checks for the harmonic diagnostic orchestration task."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import h5py
import numpy as np
from scipy import signal


RTOL = 1e-5
ATOL = 1e-7
TIME_ATOL = 1e-6
PHASE_ERROR_ATOL = 2.5e-7

CHECK_WEIGHTS = {
    "answer_harmonic_identity": 7.0,
    "answer_spectral_metrics": 8.0,
    "answer_magnetization_phase": 6.0,
    "answer_verdict": 4.0,
    "catalog_selection": 4.0,
    "candidate_audit": 5.0,
    "namelist_summary": 4.0,
    "windowed_signal": 5.0,
    "harmonic_spectrum": 7.0,
    "noise_floor_audit": 4.0,
    "charge_coupling_audit": 6.0,
    "harmonic_validation": 5.0,
    "polarization_validation": 5.0,
    "field_energy": 3.0,
    "rerunnable_offline_pipeline": 5.0,
    "rerunnable_harmonic_switch_fixture": 10.0,
    "rerunnable_contract_window_fixture": 8.0,
    "rerunnable_contract_schema_fixture": 8.0,
    "rerunnable_window_function_fixture": 7.0,
    "rerunnable_charge_coupling_fixture": 7.0,
    "rejects_invalid_hdf5_schema_fixture": 4.0,
    "rejects_incompatible_row_fixture": 4.0,
    "rejects_nonfinite_signal_fixture": 4.0,
    "rejects_no_valid_candidate_fixture": 5.0,
    "rejects_multiple_valid_candidates_fixture": 4.0,
    "rejects_too_short_window_fixture": 4.0,
}


def weight_for(name: str) -> float:
    weight = float(CHECK_WEIGHTS[name])
    if not math.isfinite(weight) or weight <= 0.0:
        raise ValueError(f"bad weight for {name}")
    return weight


def safe_check(name: str, fn) -> dict:
    try:
        passed, detail = fn()
        return {"name": name, "passed": bool(passed), "weight": weight_for(name), "detail": detail}
    except Exception as exc:
        return {"name": name, "passed": False, "weight": weight_for(name), "detail": f"{type(exc).__name__}: {exc}"}


def close_num(actual, expected, *, rtol=RTOL, atol=ATOL) -> bool:
    return isinstance(actual, (int, float)) and math.isclose(float(actual), float(expected), rel_tol=rtol, abs_tol=atol)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def data_dir() -> Path:
    return Path(os.environ.get("ORCHESTRATE_DATA_DIR", "/home/agent/data"))


def principal_angle(value):
    return (np.asarray(value) + np.pi) % (2.0 * np.pi) - np.pi


def accepted_records(root: Path) -> list[dict]:
    sql = """
    SELECT r.run_id, r.namelist_path, r.probe_h5, r.fields_h5,
           r.target_harmonic, r.min_power_ratio, r.max_frequency_error_fraction,
           r.expected_phase_lag_rad, r.phase_tolerance_rad, r.min_peak_prominence,
           r.min_charge_coupling_ratio, r.max_charge_coupling_ratio,
           d.required_probe_fields, d.required_field_fields, d.time_dataset,
           d.iteration_dataset, d.signal_group, d.analysis_time_min_omega_p_inv,
           d.analysis_time_max_omega_p_inv, d.min_window_samples,
           d.fundamental_band_half_width_omega0, d.harmonic_band_half_width_omega0,
           d.window_function, d.detrend_method, d.power_normalization,
           d.harmonic_power_definition, d.prominence_definition,
           d.phase_definition, d.energy_modulation_definition, d.energy_dataset
    FROM runs r
    JOIN diagnostic_contract d ON d.diagnostic_family = r.diagnostic_family
    WHERE r.scenario = 'laser_plasma_harmonics'
      AND r.status = 'accepted'
      AND r.diagnostic_family = 'harmonic_probe'
    ORDER BY r.run_id;
    """
    with sqlite3.connect(root / "run_catalog.sqlite") as con:
        con.row_factory = sqlite3.Row
        rows = [dict(row) for row in con.execute(sql)]
    if not rows:
        raise ValueError("expected accepted harmonic candidates")
    for row in rows:
        row["required_probe_fields"] = [v.strip() for v in row["required_probe_fields"].split(",") if v.strip()]
        row["required_field_fields"] = [v.strip() for v in row["required_field_fields"].split(",") if v.strip()]
    return rows


def parse_namelist(path: Path) -> dict:
    calls = {name: [] for name in ("Main", "Species", "ExternalField", "LaserPlanar1D", "DiagProbe", "DiagFields", "DiagScalar")}

    def record(name: str):
        def inner(**kwargs):
            calls[name].append(kwargs)
            return kwargs
        return inner

    env = {"math": math}
    env.update({name: record(name) for name in calls})
    exec(compile(path.read_text(), str(path), "exec"), env, {})
    main = calls["Main"][0]
    laser = calls["LaserPlanar1D"][0]
    probe = calls["DiagProbe"][0]
    fields = calls["DiagFields"][0]
    species = {entry["name"]: entry for entry in calls["Species"]}
    external = {entry["field"]: entry["profile"] for entry in calls["ExternalField"]}
    omega0 = float(laser.get("omega", main.get("reference_angular_frequency_SI")))
    b0z = float(external.get("Bz", 0.0))
    return {
        "geometry": main["geometry"],
        "grid_length": float(main["grid_length"][0]),
        "cell_length": float(main["cell_length"][0]),
        "timestep": float(main["timestep"]),
        "simulation_time": float(main["simulation_time"]),
        "laser_box_side": laser["box_side"],
        "laser_omega0": omega0,
        "laser_a0": float(laser["a0"]),
        "external_magnetic_field": {"component": "Bz", "value": b0z},
        "magnetization_parameter": b0z / omega0,
        "electron_density": float(species["electron"]["number_density"]),
        "probe_every": int(probe["every"]),
        "probe_fields": list(probe["fields"]),
        "field_fields": list(fields["fields"]),
    }


def make_window(name: str, count: int) -> np.ndarray:
    if name == "hann":
        return signal.windows.hann(count, sym=False)
    if name == "blackmanharris":
        return signal.windows.blackmanharris(count, sym=False)
    if name == "flattop":
        return signal.windows.flattop(count, sym=False)
    raise ValueError(f"unsupported window {name!r}")


def load_probe(root: Path, record: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with h5py.File(root / str(record["probe_h5"]), "r") as h:
        times = np.asarray(h[str(record["time_dataset"])], dtype=float)
        iterations = np.asarray(h[str(record["iteration_dataset"])], dtype=int)
        group = h[str(record["signal_group"])]
        missing = [field for field in record["required_probe_fields"] if field not in group]
        if missing:
            raise ValueError(f"missing probe fields {missing}")
        ey = np.asarray(group["Ey"], dtype=float)
        bz = np.asarray(group["Bz"], dtype=float)
        rho = np.asarray(group["Rho"], dtype=float)
    if not (len(times) == len(iterations) == len(ey) == len(bz) == len(rho)):
        raise ValueError("incompatible probe row counts")
    if not (np.all(np.isfinite(times)) and np.all(np.isfinite(ey)) and np.all(np.isfinite(bz)) and np.all(np.isfinite(rho))):
        raise ValueError("nonfinite probe data")
    order = np.argsort(times)
    return iterations[order], times[order], ey[order], bz[order], rho[order]


def load_energy(root: Path, record: dict) -> tuple[np.ndarray, np.ndarray]:
    with h5py.File(root / str(record["fields_h5"]), "r") as h:
        rows = np.asarray(h[str(record["energy_dataset"])], dtype=float)
    if rows.ndim != 2 or rows.shape[1] < 3 or not np.all(np.isfinite(rows)):
        raise ValueError("invalid energy table")
    order = np.argsort(rows[:, 1])
    return rows[:, 1][order], rows[:, 2][order]


def energy_modulation(energy: np.ndarray, record: dict) -> float:
    if record["energy_modulation_definition"] != "relative_swing_over_mean=(max-min)/mean_over_full_energy_table":
        raise ValueError("unsupported energy modulation definition")
    return float((np.max(energy) - np.min(energy)) / (np.mean(energy) + 1e-30))


def prepare_fft(times: np.ndarray, ey: np.ndarray, bz: np.ndarray, rho: np.ndarray, record: dict, namelist: dict) -> dict:
    mask = (times >= float(record["analysis_time_min_omega_p_inv"])) & (times <= float(record["analysis_time_max_omega_p_inv"]))
    if int(mask.sum()) < int(record["min_window_samples"]):
        raise ValueError("too few harmonic-window samples")
    t = times[mask]
    y = ey[mask].astype(float)
    b = bz[mask].astype(float)
    r = rho[mask].astype(float)
    if record["detrend_method"] == "mean":
        y = y - float(np.mean(y))
        b = b - float(np.mean(b))
        r = r - float(np.mean(r))
    elif record["detrend_method"] != "none":
        raise ValueError("unsupported detrend")
    dt = float(np.median(np.diff(t)))
    window = make_window(str(record["window_function"]), len(t))
    if record["power_normalization"] != "sum_abs_rfft_squared_after_dividing_coefficients_by_window_sum":
        raise ValueError("unsupported power normalization")
    ey_coeff = np.fft.rfft(y * window) / float(np.sum(window))
    bz_coeff = np.fft.rfft(b * window) / float(np.sum(window))
    rho_coeff = np.fft.rfft(r * window) / float(np.sum(window))
    norm_freq = (2.0 * np.pi * np.fft.rfftfreq(len(t), d=dt)) / float(namelist["laser_omega0"])
    return {
        "times": t,
        "mask": mask,
        "window": window,
        "ey_windowed": y * window,
        "bz_windowed": b * window,
        "rho_windowed": r * window,
        "norm_freq": norm_freq,
        "ey_coeff": ey_coeff,
        "bz_coeff": bz_coeff,
        "rho_coeff": rho_coeff,
        "ey_power": np.abs(ey_coeff) ** 2,
        "rho_power": np.abs(rho_coeff) ** 2,
    }


def band_mask(norm_freq: np.ndarray, center: float, half_width: float) -> np.ndarray:
    return np.abs(norm_freq - center) <= half_width


def integer_harmonic_centers(norm_freq: np.ndarray) -> range:
    return range(1, int(np.floor(float(np.max(norm_freq)))) + 1)


def evaluate(record: dict, fft: dict) -> dict:
    norm_freq = fft["norm_freq"]
    ey_power = fft["ey_power"]
    rho_power = fft["rho_power"]
    fund = band_mask(norm_freq, 1.0, float(record["fundamental_band_half_width_omega0"]))
    harm = band_mask(norm_freq, float(record["target_harmonic"]), float(record["harmonic_band_half_width_omega0"]))
    if int(fund.sum()) == 0 or int(harm.sum()) == 0:
        raise ValueError("empty spectral band")
    fund_power = float(np.sum(ey_power[fund]))
    harm_power = float(np.sum(ey_power[harm]))
    rho_harm_power = float(np.sum(rho_power[harm]))
    idxs = np.where(harm)[0]
    peak_idx = int(idxs[np.argmax(ey_power[harm])])
    peak_freq = float(norm_freq[peak_idx])
    freq_err = (peak_freq - float(record["target_harmonic"])) / float(record["target_harmonic"])
    charge_coupling = rho_harm_power / (harm_power + 1e-30)
    forbidden = np.zeros_like(norm_freq, dtype=bool)
    for center in integer_harmonic_centers(norm_freq):
        forbidden |= band_mask(norm_freq, float(center), float(record["harmonic_band_half_width_omega0"]))
    if record["prominence_definition"] != "peak_power_over_median_off_harmonic_power_above_0p2_omega0_excluding_all_integer_harmonic_bands_floor_frequency_axis_with_harmonic_band_half_width":
        raise ValueError("unsupported prominence definition")
    off_harmonic = (norm_freq > 0.2) & (~forbidden)
    if int(off_harmonic.sum()) == 0:
        raise ValueError("empty off-harmonic noise-floor band")
    noise = float(np.median(ey_power[off_harmonic]))
    peak_power = float(ey_power[peak_idx])
    prominence = float(peak_power / (noise + 1e-30))
    phase = float(principal_angle(np.angle(fft["bz_coeff"][peak_idx] / (fft["ey_coeff"][peak_idx] + 1e-30))))
    phase_error = float(abs(principal_angle(phase - float(record["expected_phase_lag_rad"]))))
    ratio = harm_power / fund_power
    valid = (
        abs(freq_err) <= float(record["max_frequency_error_fraction"])
        and ratio >= float(record["min_power_ratio"])
        and prominence >= float(record["min_peak_prominence"])
        and float(record["min_charge_coupling_ratio"]) <= charge_coupling <= float(record["max_charge_coupling_ratio"])
        and phase_error <= float(record["phase_tolerance_rad"])
    )
    return {
        "run_id": record["run_id"],
        "target_harmonic": int(record["target_harmonic"]),
        "sample_count": int(len(fft["times"])),
        "peak_frequency_omega0": peak_freq,
        "frequency_error_fraction": float(freq_err),
        "harmonic_to_fundamental_power_ratio": float(ratio),
        "peak_prominence_ratio": prominence,
        "rho_band_power": rho_harm_power,
        "charge_coupling_ratio": charge_coupling,
        "min_charge_coupling_ratio": float(record["min_charge_coupling_ratio"]),
        "max_charge_coupling_ratio": float(record["max_charge_coupling_ratio"]),
        "charge_coupling_valid": bool(float(record["min_charge_coupling_ratio"]) <= charge_coupling <= float(record["max_charge_coupling_ratio"])),
        "polarization_phase_lag_rad": phase,
        "phase_error_rad": phase_error,
        "fundamental_power": fund_power,
        "harmonic_power": harm_power,
        "harmonic_peak_power": peak_power,
        "off_harmonic_median_power": noise,
        "off_harmonic_bin_count": int(off_harmonic.sum()),
        "validated": bool(valid),
    }


def expectations(root: Path | None = None) -> dict:
    root = root or data_dir()
    audit = []
    candidates = []
    for record in accepted_records(root):
        namelist = parse_namelist(root / str(record["namelist_path"]))
        iterations, times, ey, bz, rho = load_probe(root, record)
        fft = prepare_fft(times, ey, bz, rho, record, namelist)
        metrics = evaluate(record, fft)
        audit.append(metrics)
        if metrics["validated"]:
            candidates.append((record, namelist, iterations, times, ey, bz, rho, fft, metrics))
    if len(candidates) != 1:
        raise ValueError(f"expected one validated candidate, got {len(candidates)}")
    record, namelist, iterations, times, ey, bz, rho, fft, metrics = candidates[0]
    energy_times, energy = load_energy(root, record)
    verdict = "magnetized_harmonic_confirmed" if metrics["validated"] else "harmonic_diagnostic_inconsistent"
    answer = {
        "selected_run_id": record["run_id"],
        "selected_harmonic_order": int(record["target_harmonic"]),
        "harmonic_frequency_omega0": metrics["peak_frequency_omega0"],
        "frequency_error_fraction": metrics["frequency_error_fraction"],
        "harmonic_to_fundamental_power_ratio": metrics["harmonic_to_fundamental_power_ratio"],
        "magnetization_parameter": namelist["magnetization_parameter"],
        "polarization_phase_lag_rad": metrics["polarization_phase_lag_rad"],
        "verdict": verdict,
    }
    return {
        "record": record,
        "namelist": namelist,
        "iterations": iterations,
        "times": times,
        "ey": ey,
        "bz": bz,
        "rho": rho,
        "fft": fft,
        "metrics": metrics,
        "audit": sorted(audit, key=lambda row: row["run_id"]),
        "energy_times": energy_times,
        "energy": energy,
        "answer": answer,
    }


def bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    raise ValueError(f"bad boolean {value!r}")


def compare_answer(actual: dict, expected: dict) -> bool:
    return (
        actual.get("selected_run_id") == expected["selected_run_id"]
        and int(actual.get("selected_harmonic_order", -1)) == expected["selected_harmonic_order"]
        and close_num(actual.get("harmonic_frequency_omega0"), expected["harmonic_frequency_omega0"])
        and close_num(actual.get("frequency_error_fraction"), expected["frequency_error_fraction"])
        and close_num(actual.get("harmonic_to_fundamental_power_ratio"), expected["harmonic_to_fundamental_power_ratio"])
        and close_num(actual.get("magnetization_parameter"), expected["magnetization_parameter"])
        and close_num(actual.get("polarization_phase_lag_rad"), expected["polarization_phase_lag_rad"])
        and actual.get("verdict") == expected["verdict"]
    )


def compare_catalog(rows: list[dict], expected: dict) -> tuple[bool, str]:
    if len(rows) != 1:
        return False, f"expected one catalog row, got {len(rows)}"
    row = rows[0]
    keys = ("run_id", "namelist_path", "probe_h5", "fields_h5")
    ok = all(row.get(key) == expected[key] for key in keys)
    ok = ok and int(row.get("target_harmonic", -1)) == int(expected["target_harmonic"])
    for key in ("min_power_ratio", "max_frequency_error_fraction", "expected_phase_lag_rad", "phase_tolerance_rad", "min_peak_prominence", "min_charge_coupling_ratio", "max_charge_coupling_ratio"):
        ok = ok and close_num(float(row.get(key, "nan")), float(expected[key]))
    return ok, "catalog selection matches source-derived validated harmonic"


def compare_audit(rows: list[dict], expected_rows: list[dict]) -> tuple[bool, str]:
    rows = sorted(rows, key=lambda row: row["run_id"])
    if len(rows) != len(expected_rows):
        return False, "candidate audit row count mismatch"
    for row, exp in zip(rows, expected_rows):
        if row.get("run_id") != exp["run_id"] or int(row.get("target_harmonic", -1)) != int(exp["target_harmonic"]):
            return False, "candidate audit identity mismatch"
        if int(row.get("sample_count", -1)) != int(exp["sample_count"]):
            return False, "candidate sample count mismatch"
        if bool_value(row.get("validated")) != bool(exp["validated"]):
            return False, "candidate validation flag mismatch"
        for key in ("peak_frequency_omega0", "frequency_error_fraction", "harmonic_to_fundamental_power_ratio", "peak_prominence_ratio", "charge_coupling_ratio", "polarization_phase_lag_rad"):
            if not close_num(float(row.get(key, "nan")), float(exp[key])):
                return False, f"candidate {key} mismatch"
    return True, "candidate audit matches source-derived spectral validation"


def compare_namelist(summary: dict, expected: dict) -> tuple[bool, str]:
    field = summary.get("external_magnetic_field", {})
    ok = (
        summary.get("geometry") == expected["geometry"]
        and close_num(summary.get("grid_length"), expected["grid_length"])
        and close_num(summary.get("cell_length"), expected["cell_length"])
        and close_num(summary.get("timestep"), expected["timestep"])
        and close_num(summary.get("simulation_time"), expected["simulation_time"])
        and summary.get("laser_box_side") == expected["laser_box_side"]
        and close_num(summary.get("laser_omega0"), expected["laser_omega0"])
        and close_num(summary.get("laser_a0"), expected["laser_a0"])
        and field.get("component") == "Bz"
        and close_num(field.get("value"), expected["external_magnetic_field"]["value"])
        and close_num(summary.get("magnetization_parameter"), expected["magnetization_parameter"])
        and close_num(summary.get("electron_density"), expected["electron_density"])
        and int(summary.get("probe_every", -1)) == int(expected["probe_every"])
        and set(summary.get("probe_fields", [])) == set(expected["probe_fields"])
        and set(summary.get("field_fields", [])) == set(expected["field_fields"])
    )
    return ok, "namelist summary matches Smilei-style laser and perpendicular magnetic-field deck"


def compare_window(rows: list[dict], expected: dict) -> tuple[bool, str]:
    fft = expected["fft"]
    iterations = expected["iterations"][fft["mask"]]
    rows = sorted(rows, key=lambda row: float(row["time_omega_p_inv"]))
    if len(rows) != len(fft["times"]):
        return False, "windowed signal row count mismatch"
    for i, row in enumerate(rows):
        if int(row["iteration"]) != int(iterations[i]):
            return False, "windowed iteration mismatch"
        if not close_num(float(row["time_omega_p_inv"]), float(fft["times"][i]), atol=TIME_ATOL, rtol=0.0):
            return False, "windowed time mismatch"
        if not close_num(float(row["window_weight"]), float(fft["window"][i])):
            return False, "window weight mismatch"
        if not close_num(float(row["Ey_windowed"]), float(fft["ey_windowed"][i])):
            return False, "windowed Ey mismatch"
        if not close_num(float(row["Bz_windowed"]), float(fft["bz_windowed"][i])):
            return False, "windowed Bz mismatch"
    return True, "windowed signal handoff matches contract-defined analysis window"


def compare_spectrum(rows: list[dict], expected_rows: list[dict]) -> tuple[bool, str]:
    rows = sorted(rows, key=lambda row: int(row["target_harmonic"]))
    exp = sorted(expected_rows, key=lambda row: int(row["target_harmonic"]))
    if len(rows) != len(exp):
        return False, "spectrum row count mismatch"
    for row, target in zip(rows, exp):
        if int(row["target_harmonic"]) != int(target["target_harmonic"]):
            return False, "spectrum harmonic mismatch"
        checks = {
            "peak_frequency_omega0": target["peak_frequency_omega0"],
            "band_power": target["harmonic_power"],
            "band_power_ratio_to_fundamental": target["harmonic_to_fundamental_power_ratio"],
            "peak_prominence_ratio": target["peak_prominence_ratio"],
            "polarization_phase_lag_rad": target["polarization_phase_lag_rad"],
        }
        for key, value in checks.items():
            if not close_num(float(row.get(key, "nan")), float(value)):
                return False, f"spectrum {key} mismatch"
    return True, "harmonic spectrum rows match source-derived FFT bands"


def compare_noise_floor(rows: list[dict], expected_rows: list[dict]) -> tuple[bool, str]:
    rows = sorted(rows, key=lambda row: int(row["target_harmonic"]))
    exp = sorted(expected_rows, key=lambda row: int(row["target_harmonic"]))
    if len(rows) != len(exp):
        return False, "noise-floor row count mismatch"
    for row, target in zip(rows, exp):
        if int(row["target_harmonic"]) != int(target["target_harmonic"]):
            return False, "noise-floor harmonic mismatch"
        if int(row.get("off_harmonic_bin_count", -1)) != int(target["off_harmonic_bin_count"]):
            return False, "noise-floor bin-count mismatch"
        checks = {
            "harmonic_peak_power": target["harmonic_peak_power"],
            "off_harmonic_median_power": target["off_harmonic_median_power"],
            "peak_prominence_ratio": target["peak_prominence_ratio"],
        }
        for key, value in checks.items():
            if not close_num(float(row.get(key, "nan")), float(value)):
                return False, f"noise-floor {key} mismatch"
    return True, "noise-floor audit matches off-harmonic prominence calculation"


def compare_charge_coupling(rows: list[dict], expected_rows: list[dict]) -> tuple[bool, str]:
    rows = sorted(rows, key=lambda row: int(row["target_harmonic"]))
    exp = sorted(expected_rows, key=lambda row: int(row["target_harmonic"]))
    if len(rows) != len(exp):
        return False, "charge-coupling row count mismatch"
    for row, target in zip(rows, exp):
        if int(row["target_harmonic"]) != int(target["target_harmonic"]):
            return False, "charge-coupling harmonic mismatch"
        if bool_value(row.get("charge_coupling_valid")) != bool(target["charge_coupling_valid"]):
            return False, "charge-coupling validity mismatch"
        checks = {
            "rho_band_power": target["rho_band_power"],
            "ey_harmonic_band_power": target["harmonic_power"],
            "charge_coupling_ratio": target["charge_coupling_ratio"],
            "min_charge_coupling_ratio": target["min_charge_coupling_ratio"],
            "max_charge_coupling_ratio": target["max_charge_coupling_ratio"],
        }
        for key, value in checks.items():
            if not close_num(float(row.get(key, "nan")), float(value)):
                return False, f"charge-coupling {key} mismatch"
    return True, "charge-coupling audit matches rho-to-Ey harmonic response"


def compare_harmonic_validation(summary: dict, expected: dict) -> tuple[bool, str]:
    fft = expected["fft"]
    metrics = expected["metrics"]
    energy = expected["energy"]
    expected_mod = energy_modulation(energy, expected["record"])
    ok = (
        int(summary.get("sample_count", -1)) == int(metrics["sample_count"])
        and summary.get("window_function") == expected["record"]["window_function"]
        and close_num(summary.get("frequency_resolution_omega0"), float(np.median(np.diff(fft["norm_freq"]))))
        and close_num(summary.get("fundamental_power"), metrics["fundamental_power"])
        and close_num(summary.get("selected_harmonic_power"), metrics["harmonic_power"])
        and close_num(summary.get("selected_peak_prominence"), metrics["peak_prominence_ratio"])
        and close_num(summary.get("selected_phase_error_rad"), metrics["phase_error_rad"], rtol=0.0, atol=PHASE_ERROR_ATOL)
        and 0.0 <= float(summary.get("selected_phase_error_rad")) <= float(expected["record"]["phase_tolerance_rad"])
        and close_num(summary.get("energy_modulation_index"), expected_mod)
    )
    return ok, "harmonic validation summary matches FFT and field-energy diagnostics"


def compare_phase(summary: dict, expected: dict) -> tuple[bool, str]:
    record = expected["record"]
    metrics = expected["metrics"]
    ok = (
        close_num(summary.get("ey_bz_phase_lag_rad"), metrics["polarization_phase_lag_rad"])
        and close_num(summary.get("expected_phase_lag_rad"), float(record["expected_phase_lag_rad"]))
        and close_num(summary.get("phase_error_rad"), metrics["phase_error_rad"], rtol=0.0, atol=PHASE_ERROR_ATOL)
        and 0.0 <= float(summary.get("phase_error_rad")) <= float(record["phase_tolerance_rad"])
        and close_num(summary.get("phase_tolerance_rad"), float(record["phase_tolerance_rad"]))
    )
    return ok, "polarization validation matches selected complex FFT coefficients"


def compare_energy(rows: list[dict], expected: dict) -> tuple[bool, str]:
    rows = sorted(rows, key=lambda row: float(row["time_omega_p_inv"]))
    if len(rows) != len(expected["energy_times"]):
        return False, "energy row count mismatch"
    times = np.asarray([float(row["time_omega_p_inv"]) for row in rows])
    energy = np.asarray([float(row["electromagnetic_field_energy"]) for row in rows])
    ok = np.allclose(times, expected["energy_times"], rtol=0.0, atol=TIME_ATOL) and np.allclose(energy, expected["energy"], rtol=RTOL, atol=ATOL)
    return bool(ok), "field energy table matches mounted diagnostic"


def replace_probe_signal(root: Path, amplitudes: dict[int, float], lags: dict[int, float]) -> None:
    namelist = parse_namelist(root / "smilei_inputs" / "tst1d_laser_magnetized_harmonics.py")
    omega0 = float(namelist["laser_omega0"])
    with h5py.File(root / "diagnostics" / "Probes0.h5", "r+") as h:
        times = np.asarray(h["time_omega_p_inv"], dtype=float)
        phases = {1: 0.27, 2: -0.44, 3: 0.82, 4: -1.22, 5: 1.7}
        ey = sum(a * np.sin(n * omega0 * times + phases[n]) for n, a in amplitudes.items())
        bz = sum((a * 0.94) * np.sin(n * omega0 * times + phases[n] + lags[n]) for n, a in amplitudes.items())
        group = h["signals/xmin"]
        group["Ey"][...] = ey
        group["Bz"][...] = bz
        group["Rho"][...] = 0.08 * np.sin(3 * omega0 * times + phases[3] + math.pi / 2)
        group["Jx"][...] = 0.06 * np.cos(3 * omega0 * times + phases[3] - 0.25)


def copy_with_harmonic_switch(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    replace_probe_signal(dst, {1: 1.0, 2: 0.19, 3: 0.035, 4: 0.025, 5: 0.006}, {1: 0.03, 2: -0.20, 3: -1.18, 4: 0.75, 5: 0.1})
    with sqlite3.connect(dst / "run_catalog.sqlite") as con:
        con.execute("""
            UPDATE runs
               SET min_charge_coupling_ratio=0.0,
                   max_charge_coupling_ratio=1.0
             WHERE scenario='laser_plasma_harmonics'
               AND diagnostic_family='harmonic_probe'
        """)
        con.commit()


def copy_with_contract_window(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with sqlite3.connect(dst / "run_catalog.sqlite") as con:
        con.execute("UPDATE diagnostic_contract SET analysis_time_min_omega_p_inv=51.2, analysis_time_max_omega_p_inv=153.6 WHERE diagnostic_family='harmonic_probe'")
        con.commit()


def copy_with_schema_rename(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    replace_probe_signal(dst, {1: 1.0, 2: 0.030, 3: 0.160, 4: 0.020, 5: 0.006}, {1: 0.03, 2: -0.20, 3: -1.18, 4: 0.75, 5: 0.1})
    with h5py.File(dst / "diagnostics" / "Probes0.h5", "r+") as h:
        h.move("time_omega_p_inv", "probe_time")
        h.move("iteration", "probe_iteration")
        h.move("signals/xmin", "boundary/xmin")
    with sqlite3.connect(dst / "run_catalog.sqlite") as con:
        con.execute("UPDATE diagnostic_contract SET time_dataset='probe_time', iteration_dataset='probe_iteration', signal_group='boundary/xmin' WHERE diagnostic_family='harmonic_probe'")
        con.commit()


def copy_with_hann_window(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with sqlite3.connect(dst / "run_catalog.sqlite") as con:
        con.execute("UPDATE diagnostic_contract SET window_function='hann' WHERE diagnostic_family='harmonic_probe'")
        con.commit()


def copy_with_charge_coupling_shift(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with h5py.File(dst / "diagnostics" / "Probes0.h5", "r+") as h:
        rho = h["signals/xmin/Rho"]
        rho[...] = np.asarray(rho, dtype=float) * 1.25
    with sqlite3.connect(dst / "run_catalog.sqlite") as con:
        con.execute("""
            UPDATE runs
               SET max_charge_coupling_ratio=0.60
             WHERE scenario='laser_plasma_harmonics'
               AND diagnostic_family='harmonic_probe'
        """)
        con.commit()


def copy_missing_probe_field(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with h5py.File(dst / "diagnostics" / "Probes0.h5", "r+") as h:
        del h["signals/xmin/Bz"]


def copy_bad_row_count(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with h5py.File(dst / "diagnostics" / "Probes0.h5", "r+") as h:
        values = np.asarray(h["time_omega_p_inv"], dtype=float)
        del h["time_omega_p_inv"]
        h.create_dataset("time_omega_p_inv", data=values[:-11])


def copy_nonfinite_signal(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with h5py.File(dst / "diagnostics" / "Probes0.h5", "r+") as h:
        ey = h["signals/xmin/Ey"]
        ey[128] = np.nan


def copy_no_valid_candidate(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with sqlite3.connect(dst / "run_catalog.sqlite") as con:
        con.execute("UPDATE runs SET min_power_ratio=9.0 WHERE diagnostic_family='harmonic_probe'")
        con.commit()


def copy_multiple_valid_candidates(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with sqlite3.connect(dst / "run_catalog.sqlite") as con:
        con.execute("UPDATE runs SET min_power_ratio=0.0, phase_tolerance_rad=10.0 WHERE diagnostic_family='harmonic_probe'")
        con.commit()


def copy_too_short_window(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    with sqlite3.connect(dst / "run_catalog.sqlite") as con:
        con.execute("""
            UPDATE diagnostic_contract
               SET analysis_time_min_omega_p_inv=40.0,
                   analysis_time_max_omega_p_inv=40.2,
                   min_window_samples=64
             WHERE diagnostic_family='harmonic_probe'
        """)
        con.commit()


def results_fingerprint(root: Path) -> tuple:
    if not root.exists():
        return ()
    entries = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append((rel, "symlink", os.readlink(path)))
        elif path.is_dir():
            entries.append((rel, "dir"))
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append((rel, "file", digest))
        else:
            entries.append((rel, "other"))
    return tuple(entries)


def restore_results(results_dir: Path, backup: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    for child in list(results_dir.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in backup.iterdir():
        target = results_dir / child.name
        if child.is_dir() and not child.is_symlink():
            shutil.copytree(child, target, symlinks=True)
        else:
            shutil.copy2(child, target)


def run_pipeline(results_dir: Path, fixture_root: Path) -> tuple[bool, str, Path]:
    solve_py = results_dir / "code" / "solve.py"
    if not solve_py.exists():
        return False, "code/solve.py missing", Path()
    out = fixture_root.parent / "rerun_output"
    backup = fixture_root.parent / "submitted_results_backup"
    shutil.copytree(results_dir, backup, symlinks=True)
    before = results_fingerprint(results_dir)
    env = os.environ.copy()
    env["ORCHESTRATE_DATA_DIR"] = str(fixture_root)
    restore_error = ""
    try:
        proc = subprocess.run(["python3", str(solve_py), str(out)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300, env=env)
    finally:
        if results_fingerprint(results_dir) != before:
            try:
                restore_results(results_dir, backup)
            except Exception as exc:
                restore_error = f"{type(exc).__name__}: {exc}"
    if restore_error:
        return False, f"submitted results changed during rerun and could not be restored: {restore_error}", out
    if proc.returncode != 0:
        return False, proc.stderr[-500:], out
    return True, "pipeline ran", out


def compare_rerun_peak_and_count(out: Path, actual: dict, exp: dict, base: dict) -> bool:
    summary = read_json(out / "intermediate" / "harmonic_validation.json")
    return (
        int(summary.get("sample_count", -1)) == int(exp["metrics"]["sample_count"])
        and close_num(actual.get("harmonic_frequency_omega0"), exp["answer"]["harmonic_frequency_omega0"])
        and not close_num(
            actual.get("harmonic_to_fundamental_power_ratio"),
            base["answer"]["harmonic_to_fundamental_power_ratio"],
            rtol=1e-3,
            atol=0.0,
        )
    )


def compare_window_function_probe(out: Path, exp: dict) -> bool:
    summary = read_json(out / "intermediate" / "harmonic_validation.json")
    return (
        summary.get("window_function") == exp["record"]["window_function"]
        and close_num(summary.get("selected_harmonic_power"), exp["metrics"]["harmonic_power"])
        and close_num(summary.get("selected_peak_prominence"), exp["metrics"]["peak_prominence_ratio"])
    )


def compare_charge_coupling_probe(out: Path, exp: dict, base: dict) -> bool:
    ok, _ = compare_charge_coupling(read_csv_rows(out / "intermediate" / "charge_coupling_audit.csv"), exp["audit"])
    if not ok:
        return False
    selected = int(exp["answer"]["selected_harmonic_order"])
    changed_row = next(row for row in exp["audit"] if int(row["target_harmonic"]) == selected)
    base_row = next(row for row in base["audit"] if int(row["target_harmonic"]) == selected)
    return not close_num(
        changed_row["charge_coupling_ratio"],
        base_row["charge_coupling_ratio"],
        rtol=1e-3,
        atol=0.0,
    )


def check_rerun(results_dir: Path, copy_fn, detail: str, mode: str = "answer") -> tuple[bool, str]:
    base = expectations()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "data"
        copy_fn(data_dir(), root)
        exp = expectations(root)
        ok_run, msg, out = run_pipeline(results_dir, root)
        if not ok_run:
            return False, msg
        actual = read_json(out / "answer.json")
        if mode == "answer":
            ok = compare_answer(actual, exp["answer"])
        elif mode == "harmonic_switch":
            ok = (
                actual.get("selected_run_id") == exp["answer"]["selected_run_id"]
                and int(actual.get("selected_harmonic_order", -1)) == exp["answer"]["selected_harmonic_order"]
                and close_num(actual.get("harmonic_frequency_omega0"), exp["answer"]["harmonic_frequency_omega0"])
                and actual.get("selected_harmonic_order") != base["answer"]["selected_harmonic_order"]
            )
        elif mode == "peak_and_count":
            ok = compare_rerun_peak_and_count(out, actual, exp, base)
        elif mode == "window_function":
            ok = compare_window_function_probe(out, exp)
        elif mode == "charge_coupling":
            ok = compare_charge_coupling_probe(out, exp, base)
        else:
            raise ValueError(f"unknown rerun comparison mode {mode!r}")
        return bool(ok), detail


def check_rejection(results_dir: Path, copy_fn, detail: str) -> tuple[bool, str]:
    if not (results_dir / "code" / "solve.py").exists():
        return False, "code/solve.py missing"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "data"
        copy_fn(data_dir(), root)
        ok_run, _, out = run_pipeline(results_dir, root)
        return (not ok_run and not (out / "answer.json").exists()), detail


def check(results_dir: Path) -> tuple[float, list[dict]]:
    answer = read_json(results_dir / "answer.json") if (results_dir / "answer.json").exists() else {}
    inter = results_dir / "intermediate"
    exp = expectations()
    source_answer = exp["answer"]
    checks: list[dict] = []
    checks.append(safe_check("answer_harmonic_identity", lambda: (
        answer.get("selected_run_id") == source_answer["selected_run_id"]
        and int(answer.get("selected_harmonic_order", -1)) == source_answer["selected_harmonic_order"],
        "selected catalog row and harmonic order",
    )))
    checks.append(safe_check("answer_spectral_metrics", lambda: (
        close_num(answer.get("harmonic_frequency_omega0"), source_answer["harmonic_frequency_omega0"])
        and close_num(answer.get("frequency_error_fraction"), source_answer["frequency_error_fraction"])
        and close_num(answer.get("harmonic_to_fundamental_power_ratio"), source_answer["harmonic_to_fundamental_power_ratio"]),
        "frequency error and harmonic power ratio",
    )))
    checks.append(safe_check("answer_magnetization_phase", lambda: (
        close_num(answer.get("magnetization_parameter"), source_answer["magnetization_parameter"])
        and close_num(answer.get("polarization_phase_lag_rad"), source_answer["polarization_phase_lag_rad"]),
        "magnetization and polarization phase",
    )))
    checks.append(safe_check("answer_verdict", lambda: (answer.get("verdict") == source_answer["verdict"], "verdict enum")))
    checks.append(safe_check("catalog_selection", lambda: compare_catalog(read_csv_rows(inter / "catalog_selection.csv"), exp["record"])))
    checks.append(safe_check("candidate_audit", lambda: compare_audit(read_csv_rows(inter / "candidate_audit.csv"), exp["audit"])))
    checks.append(safe_check("namelist_summary", lambda: compare_namelist(read_json(inter / "namelist_summary.json"), exp["namelist"])))
    checks.append(safe_check("windowed_signal", lambda: compare_window(read_csv_rows(inter / "windowed_signal.csv"), exp)))
    checks.append(safe_check("harmonic_spectrum", lambda: compare_spectrum(read_csv_rows(inter / "harmonic_spectrum.csv"), exp["audit"])))
    checks.append(safe_check("noise_floor_audit", lambda: compare_noise_floor(read_csv_rows(inter / "noise_floor_audit.csv"), exp["audit"])))
    checks.append(safe_check("charge_coupling_audit", lambda: compare_charge_coupling(read_csv_rows(inter / "charge_coupling_audit.csv"), exp["audit"])))
    checks.append(safe_check("harmonic_validation", lambda: compare_harmonic_validation(read_json(inter / "harmonic_validation.json"), exp)))
    checks.append(safe_check("polarization_validation", lambda: compare_phase(read_json(inter / "polarization_validation.json"), exp)))
    checks.append(safe_check("field_energy", lambda: compare_energy(read_csv_rows(inter / "field_energy.csv"), exp)))
    checks.append(safe_check("rerunnable_offline_pipeline", lambda: check_rerun(results_dir, lambda s, d: shutil.copytree(s, d), "pipeline reproduces baseline answer", "answer")))
    checks.append(safe_check("rerunnable_harmonic_switch_fixture", lambda: check_rerun(results_dir, copy_with_harmonic_switch, "pipeline updates selected identity when the validated harmonic order switches", "harmonic_switch")))
    checks.append(safe_check("rerunnable_contract_window_fixture", lambda: check_rerun(results_dir, copy_with_contract_window, "pipeline updates sample count and peak for a changed analysis-window contract", "peak_and_count")))
    checks.append(safe_check("rerunnable_contract_schema_fixture", lambda: check_rerun(results_dir, copy_with_schema_rename, "pipeline recovers sample count and peak after HDF5 dataset names change", "peak_and_count")))
    checks.append(safe_check("rerunnable_window_function_fixture", lambda: check_rerun(results_dir, copy_with_hann_window, "pipeline updates selected power and prominence for a changed spectral window convention", "window_function")))
    checks.append(safe_check("rerunnable_charge_coupling_fixture", lambda: check_rerun(results_dir, copy_with_charge_coupling_shift, "pipeline updates charge-coupling audit when Rho harmonic response changes", "charge_coupling")))
    checks.append(safe_check("rejects_invalid_hdf5_schema_fixture", lambda: check_rejection(results_dir, copy_missing_probe_field, "reject missing required probe field")))
    checks.append(safe_check("rejects_incompatible_row_fixture", lambda: check_rejection(results_dir, copy_bad_row_count, "reject incompatible time/signal row counts")))
    checks.append(safe_check("rejects_nonfinite_signal_fixture", lambda: check_rejection(results_dir, copy_nonfinite_signal, "reject nonfinite probe signal")))
    checks.append(safe_check("rejects_no_valid_candidate_fixture", lambda: check_rejection(results_dir, copy_no_valid_candidate, "reject zero validated harmonic candidates")))
    checks.append(safe_check("rejects_multiple_valid_candidates_fixture", lambda: check_rejection(results_dir, copy_multiple_valid_candidates, "reject multiple validated harmonic candidates")))
    checks.append(safe_check("rejects_too_short_window_fixture", lambda: check_rejection(results_dir, copy_too_short_window, "reject too-short analysis window")))
    total = sum(float(item["weight"]) for item in checks)
    earned = sum(float(item["weight"]) for item in checks if item["passed"])
    return (earned / total if total else 0.0), checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=Path("/home/agent/results"))
    ap.add_argument("--result-file", type=Path, default=Path("/tmp/eval/programmatic.json"))
    args = ap.parse_args()
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
