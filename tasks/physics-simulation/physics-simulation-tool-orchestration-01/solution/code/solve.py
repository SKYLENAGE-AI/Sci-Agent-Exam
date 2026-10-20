#!/usr/bin/env python3
"""Reference workflow for the magnetized laser-plasma harmonic task."""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal


@dataclass
class HarmonicRun:
    run_id: str
    namelist_path: str
    probe_h5: str
    fields_h5: str
    target_harmonic: int
    min_power_ratio: float
    max_frequency_error_fraction: float
    expected_phase_lag_rad: float
    phase_tolerance_rad: float
    min_peak_prominence: float
    min_charge_coupling_ratio: float
    max_charge_coupling_ratio: float
    required_probe_fields: list[str]
    required_field_fields: list[str]
    time_dataset: str
    iteration_dataset: str
    signal_group: str
    analysis_time_min_omega_p_inv: float
    analysis_time_max_omega_p_inv: float
    min_window_samples: int
    fundamental_band_half_width_omega0: float
    harmonic_band_half_width_omega0: float
    window_function: str
    detrend_method: str
    power_normalization: str
    harmonic_power_definition: str
    prominence_definition: str
    phase_definition: str
    energy_modulation_definition: str
    energy_dataset: str


CATALOG_HEADERS = [
    "run_id",
    "namelist_path",
    "probe_h5",
    "fields_h5",
    "target_harmonic",
    "min_power_ratio",
    "max_frequency_error_fraction",
    "expected_phase_lag_rad",
    "phase_tolerance_rad",
    "min_peak_prominence",
    "min_charge_coupling_ratio",
    "max_charge_coupling_ratio",
]

AUDIT_HEADERS = [
    "run_id",
    "target_harmonic",
    "sample_count",
    "peak_frequency_omega0",
    "frequency_error_fraction",
    "harmonic_to_fundamental_power_ratio",
    "peak_prominence_ratio",
    "charge_coupling_ratio",
    "polarization_phase_lag_rad",
    "validated",
]

NOISE_FLOOR_HEADERS = [
    "target_harmonic",
    "harmonic_peak_power",
    "off_harmonic_median_power",
    "off_harmonic_bin_count",
    "peak_prominence_ratio",
]

CHARGE_COUPLING_HEADERS = [
    "target_harmonic",
    "rho_band_power",
    "ey_harmonic_band_power",
    "charge_coupling_ratio",
    "min_charge_coupling_ratio",
    "max_charge_coupling_ratio",
    "charge_coupling_valid",
]


def run_subprocess(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return proc.stdout


def query_catalog(data_dir: Path) -> list[HarmonicRun]:
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
      AND instr(d.required_probe_fields, 'Ey') > 0
      AND instr(d.required_probe_fields, 'Bz') > 0
    ORDER BY r.run_id;
    """
    stdout = run_subprocess(["sqlite3", "-header", "-csv", str(data_dir / "run_catalog.sqlite"), sql])
    rows = list(csv.DictReader(stdout.splitlines()))
    if not rows:
        raise RuntimeError("expected accepted harmonic-probe candidates")
    out: list[HarmonicRun] = []
    for row in rows:
        out.append(HarmonicRun(
            run_id=row["run_id"],
            namelist_path=row["namelist_path"],
            probe_h5=row["probe_h5"],
            fields_h5=row["fields_h5"],
            target_harmonic=int(row["target_harmonic"]),
            min_power_ratio=float(row["min_power_ratio"]),
            max_frequency_error_fraction=float(row["max_frequency_error_fraction"]),
            expected_phase_lag_rad=float(row["expected_phase_lag_rad"]),
            phase_tolerance_rad=float(row["phase_tolerance_rad"]),
            min_peak_prominence=float(row["min_peak_prominence"]),
            min_charge_coupling_ratio=float(row["min_charge_coupling_ratio"]),
            max_charge_coupling_ratio=float(row["max_charge_coupling_ratio"]),
            required_probe_fields=[v.strip() for v in row["required_probe_fields"].split(",") if v.strip()],
            required_field_fields=[v.strip() for v in row["required_field_fields"].split(",") if v.strip()],
            time_dataset=row["time_dataset"],
            iteration_dataset=row["iteration_dataset"],
            signal_group=row["signal_group"],
            analysis_time_min_omega_p_inv=float(row["analysis_time_min_omega_p_inv"]),
            analysis_time_max_omega_p_inv=float(row["analysis_time_max_omega_p_inv"]),
            min_window_samples=int(row["min_window_samples"]),
            fundamental_band_half_width_omega0=float(row["fundamental_band_half_width_omega0"]),
            harmonic_band_half_width_omega0=float(row["harmonic_band_half_width_omega0"]),
            window_function=row["window_function"],
            detrend_method=row["detrend_method"],
            power_normalization=row["power_normalization"],
            harmonic_power_definition=row["harmonic_power_definition"],
            prominence_definition=row["prominence_definition"],
            phase_definition=row["phase_definition"],
            energy_modulation_definition=row["energy_modulation_definition"],
            energy_dataset=row["energy_dataset"],
        ))
    return out


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


def h5dump_tree(path: Path) -> str:
    proc = subprocess.run(
        ["h5dump", "-n", path.name],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        cwd=path.parent,
    )
    return proc.stdout


def principal_angle(value: float | np.ndarray) -> np.ndarray:
    return (np.asarray(value) + np.pi) % (2.0 * np.pi) - np.pi


def make_window(name: str, count: int) -> np.ndarray:
    if name == "hann":
        return signal.windows.hann(count, sym=False)
    if name == "blackmanharris":
        return signal.windows.blackmanharris(count, sym=False)
    if name == "flattop":
        return signal.windows.flattop(count, sym=False)
    raise RuntimeError(f"unsupported window function {name!r}")


def load_probe_signal(data_dir: Path, run: HarmonicRun) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with h5py.File(data_dir / run.probe_h5, "r") as h:
        times = np.asarray(h[run.time_dataset], dtype=float)
        iterations = np.asarray(h[run.iteration_dataset], dtype=int)
        if len(times) != len(iterations):
            raise RuntimeError("probe time and iteration arrays have different lengths")
        group = h[run.signal_group]
        missing = [field for field in run.required_probe_fields if field not in group]
        if missing:
            raise RuntimeError(f"missing probe field(s): {missing}")
        ey = np.asarray(group["Ey"], dtype=float)
        bz = np.asarray(group["Bz"], dtype=float)
        rho = np.asarray(group["Rho"], dtype=float)
        if not (len(ey) == len(bz) == len(rho) == len(times)):
            raise RuntimeError("probe signal row counts do not match time axis")
        if not (np.all(np.isfinite(ey)) and np.all(np.isfinite(bz)) and np.all(np.isfinite(rho))):
            raise RuntimeError("probe signals contain nonfinite values")
    order = np.argsort(times)
    return iterations[order], times[order], ey[order], bz[order], rho[order]


def load_field_energy(data_dir: Path, run: HarmonicRun) -> tuple[np.ndarray, np.ndarray]:
    with h5py.File(data_dir / run.fields_h5, "r") as h:
        rows = np.asarray(h[run.energy_dataset], dtype=float)
    if rows.ndim != 2 or rows.shape[1] < 3 or not np.all(np.isfinite(rows)):
        raise RuntimeError("invalid electromagnetic energy table")
    order = np.argsort(rows[:, 1])
    return rows[:, 1][order], rows[:, 2][order]


def compute_energy_modulation(energy: np.ndarray, run: HarmonicRun) -> float:
    if run.energy_modulation_definition != "relative_swing_over_mean=(max-min)/mean_over_full_energy_table":
        raise RuntimeError(f"unsupported energy modulation definition {run.energy_modulation_definition!r}")
    return float((np.max(energy) - np.min(energy)) / (np.mean(energy) + 1e-30))


def prepare_fft(times: np.ndarray, ey: np.ndarray, bz: np.ndarray, rho: np.ndarray, run: HarmonicRun, namelist: dict) -> dict:
    mask = (
        (times >= run.analysis_time_min_omega_p_inv)
        & (times <= run.analysis_time_max_omega_p_inv)
    )
    if int(mask.sum()) < run.min_window_samples:
        raise RuntimeError("not enough samples in harmonic analysis window")
    t = times[mask]
    ey_win = ey[mask].astype(float)
    bz_win = bz[mask].astype(float)
    rho_win = rho[mask].astype(float)
    if run.detrend_method == "mean":
        ey_win = ey_win - float(np.mean(ey_win))
        bz_win = bz_win - float(np.mean(bz_win))
        rho_win = rho_win - float(np.mean(rho_win))
    elif run.detrend_method != "none":
        raise RuntimeError(f"unsupported detrend method {run.detrend_method!r}")
    dt = float(np.median(np.diff(t)))
    if dt <= 0.0 or not math.isfinite(dt):
        raise RuntimeError("invalid probe time spacing")
    window = make_window(run.window_function, len(t))
    if run.power_normalization != "sum_abs_rfft_squared_after_dividing_coefficients_by_window_sum":
        raise RuntimeError(f"unsupported power normalization {run.power_normalization!r}")
    ey_coeff = np.fft.rfft(ey_win * window) / float(np.sum(window))
    bz_coeff = np.fft.rfft(bz_win * window) / float(np.sum(window))
    rho_coeff = np.fft.rfft(rho_win * window) / float(np.sum(window))
    omega = 2.0 * np.pi * np.fft.rfftfreq(len(t), d=dt)
    omega0 = float(namelist["laser_omega0"])
    norm_freq = omega / omega0
    ey_power = np.abs(ey_coeff) ** 2
    return {
        "iterations": None,
        "times": t,
        "ey_windowed": ey_win * window,
        "bz_windowed": bz_win * window,
        "rho_windowed": rho_win * window,
        "window": window,
        "norm_freq": norm_freq,
        "ey_coeff": ey_coeff,
        "bz_coeff": bz_coeff,
        "rho_coeff": rho_coeff,
        "ey_power": ey_power,
        "rho_power": np.abs(rho_coeff) ** 2,
        "dt": dt,
    }


def band_mask(norm_freq: np.ndarray, center: float, half_width: float) -> np.ndarray:
    return np.abs(norm_freq - center) <= half_width


def integer_harmonic_centers(norm_freq: np.ndarray) -> range:
    return range(1, int(np.floor(float(np.max(norm_freq)))) + 1)


def evaluate_candidate(run: HarmonicRun, fft: dict) -> dict:
    norm_freq = fft["norm_freq"]
    ey_power = fft["ey_power"]
    rho_power = fft["rho_power"]
    fund_mask = band_mask(norm_freq, 1.0, run.fundamental_band_half_width_omega0)
    harm_mask = band_mask(norm_freq, float(run.target_harmonic), run.harmonic_band_half_width_omega0)
    if int(fund_mask.sum()) == 0 or int(harm_mask.sum()) == 0:
        raise RuntimeError("empty spectral band")
    fund_power = float(np.sum(ey_power[fund_mask]))
    harm_power = float(np.sum(ey_power[harm_mask]))
    rho_harm_power = float(np.sum(rho_power[harm_mask]))
    if fund_power <= 0.0 or not math.isfinite(fund_power):
        raise RuntimeError("invalid fundamental power")
    idxs = np.where(harm_mask)[0]
    peak_idx = int(idxs[np.argmax(ey_power[harm_mask])])
    peak_freq = float(norm_freq[peak_idx])
    ratio = harm_power / fund_power
    charge_coupling = rho_harm_power / (harm_power + 1e-30)
    freq_err = (peak_freq - float(run.target_harmonic)) / float(run.target_harmonic)
    forbidden = np.zeros_like(norm_freq, dtype=bool)
    for center in integer_harmonic_centers(norm_freq):
        forbidden |= band_mask(norm_freq, float(center), run.harmonic_band_half_width_omega0)
    if run.prominence_definition != "peak_power_over_median_off_harmonic_power_above_0p2_omega0_excluding_all_integer_harmonic_bands_floor_frequency_axis_with_harmonic_band_half_width":
        raise RuntimeError(f"unsupported prominence definition {run.prominence_definition!r}")
    off_harmonic = (norm_freq > 0.2) & (~forbidden)
    if int(off_harmonic.sum()) == 0:
        raise RuntimeError("empty off-harmonic noise-floor band")
    noise = float(np.median(ey_power[off_harmonic]))
    peak_power = float(ey_power[peak_idx])
    prominence = float(peak_power / (noise + 1e-30))
    phase_lag = float(principal_angle(np.angle(fft["bz_coeff"][peak_idx] / (fft["ey_coeff"][peak_idx] + 1e-30))))
    phase_error = float(abs(principal_angle(phase_lag - run.expected_phase_lag_rad)))
    validated = (
        abs(freq_err) <= run.max_frequency_error_fraction
        and ratio >= run.min_power_ratio
        and prominence >= run.min_peak_prominence
        and run.min_charge_coupling_ratio <= charge_coupling <= run.max_charge_coupling_ratio
        and phase_error <= run.phase_tolerance_rad
    )
    return {
        "run_id": run.run_id,
        "target_harmonic": run.target_harmonic,
        "sample_count": int(len(fft["times"])),
        "peak_frequency_omega0": peak_freq,
        "frequency_error_fraction": float(freq_err),
        "harmonic_to_fundamental_power_ratio": float(ratio),
        "peak_prominence_ratio": prominence,
        "rho_band_power": rho_harm_power,
        "charge_coupling_ratio": charge_coupling,
        "min_charge_coupling_ratio": run.min_charge_coupling_ratio,
        "max_charge_coupling_ratio": run.max_charge_coupling_ratio,
        "charge_coupling_valid": bool(run.min_charge_coupling_ratio <= charge_coupling <= run.max_charge_coupling_ratio),
        "polarization_phase_lag_rad": phase_lag,
        "phase_error_rad": phase_error,
        "fundamental_power": fund_power,
        "harmonic_power": harm_power,
        "harmonic_peak_power": peak_power,
        "off_harmonic_median_power": noise,
        "off_harmonic_bin_count": int(off_harmonic.sum()),
        "validated": validated,
    }


def select_validated_run(data_dir: Path, candidates: list[HarmonicRun]) -> tuple[HarmonicRun, dict, dict, list[dict], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    validated = []
    audit_rows = []
    probe_trees = {candidate.probe_h5: h5dump_tree(data_dir / candidate.probe_h5) for candidate in candidates}
    for candidate in candidates:
        namelist = parse_namelist(data_dir / candidate.namelist_path)
        signal_tuple = load_probe_signal(data_dir, candidate)
        _, times, ey, bz, rho = signal_tuple
        fft = prepare_fft(times, ey, bz, rho, candidate, namelist)
        metrics = evaluate_candidate(candidate, fft)
        audit_rows.append(metrics)
        if metrics["validated"]:
            validated.append((candidate, namelist, fft, metrics, signal_tuple))
    if len(validated) != 1:
        raise RuntimeError(f"expected exactly one validated harmonic candidate, got {len(validated)}")
    selected = validated[0]
    selected[2]["probe_trees"] = probe_trees
    return selected


def write_csv(path: Path, rows: list[dict], headers: list[str] | None = None) -> None:
    headers = headers or list(rows[0])
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def write_catalog_selection(path: Path, run: HarmonicRun) -> None:
    write_csv(path, [{
        "run_id": run.run_id,
        "namelist_path": run.namelist_path,
        "probe_h5": run.probe_h5,
        "fields_h5": run.fields_h5,
        "target_harmonic": run.target_harmonic,
        "min_power_ratio": f"{run.min_power_ratio:.12g}",
        "max_frequency_error_fraction": f"{run.max_frequency_error_fraction:.12g}",
        "expected_phase_lag_rad": f"{run.expected_phase_lag_rad:.12g}",
        "phase_tolerance_rad": f"{run.phase_tolerance_rad:.12g}",
        "min_peak_prominence": f"{run.min_peak_prominence:.12g}",
        "min_charge_coupling_ratio": f"{run.min_charge_coupling_ratio:.12g}",
        "max_charge_coupling_ratio": f"{run.max_charge_coupling_ratio:.12g}",
    }], CATALOG_HEADERS)


def main(argv: list[str]) -> int:
    results = Path(argv[1]) if len(argv) > 1 else Path("/home/agent/results")
    data_dir = Path(os.environ.get("ORCHESTRATE_DATA_DIR", "/home/agent/data"))
    if not data_dir.exists():
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "environment" / "data"
            if candidate.exists():
                data_dir = candidate
                break
    intermediate = results / "intermediate"
    figures = results / "figures"
    code = results / "code"
    for path in (intermediate, figures, code):
        path.mkdir(parents=True, exist_ok=True)

    candidates = query_catalog(data_dir)
    run, namelist, fft, selected_metrics, signal_tuple = select_validated_run(data_dir, candidates)
    all_metrics = []
    for candidate in candidates:
        nm = parse_namelist(data_dir / candidate.namelist_path)
        _, times, ey, bz, rho = load_probe_signal(data_dir, candidate)
        metrics = evaluate_candidate(candidate, prepare_fft(times, ey, bz, rho, candidate, nm))
        all_metrics.append(metrics)

    write_catalog_selection(intermediate / "catalog_selection.csv", run)
    audit_rows = []
    for row in sorted(all_metrics, key=lambda item: item["run_id"]):
        out = {key: row[key] for key in AUDIT_HEADERS if key != "validated"}
        out["validated"] = "true" if row["validated"] else "false"
        audit_rows.append(out)
    write_csv(intermediate / "candidate_audit.csv", audit_rows, AUDIT_HEADERS)
    (intermediate / "namelist_summary.json").write_text(json.dumps(namelist, indent=2, sort_keys=True) + "\n")
    (intermediate / "probe_h5dump_tree.txt").write_text(fft["probe_trees"][run.probe_h5])
    (intermediate / "fields_h5dump_tree.txt").write_text(h5dump_tree(data_dir / run.fields_h5))

    iterations, times, ey, bz, rho = signal_tuple
    window_mask = (
        (times >= run.analysis_time_min_omega_p_inv)
        & (times <= run.analysis_time_max_omega_p_inv)
    )
    window_rows = []
    fft_iter = iterations[window_mask]
    for iteration, t, weight, ey_w, bz_w in zip(fft_iter, fft["times"], fft["window"], fft["ey_windowed"], fft["bz_windowed"]):
        window_rows.append({
            "iteration": int(iteration),
            "time_omega_p_inv": f"{t:.8f}",
            "window_weight": f"{weight:.12e}",
            "Ey_windowed": f"{ey_w:.12e}",
            "Bz_windowed": f"{bz_w:.12e}",
        })
    write_csv(intermediate / "windowed_signal.csv", window_rows)

    spectrum_rows = []
    for row in sorted(all_metrics, key=lambda item: item["target_harmonic"]):
        spectrum_rows.append({
            "target_harmonic": int(row["target_harmonic"]),
            "peak_frequency_omega0": f"{row['peak_frequency_omega0']:.12e}",
            "band_power": f"{row['harmonic_power']:.12e}",
            "band_power_ratio_to_fundamental": f"{row['harmonic_to_fundamental_power_ratio']:.12e}",
            "peak_prominence_ratio": f"{row['peak_prominence_ratio']:.12e}",
            "polarization_phase_lag_rad": f"{row['polarization_phase_lag_rad']:.12e}",
        })
    write_csv(intermediate / "harmonic_spectrum.csv", spectrum_rows)

    noise_floor_rows = []
    for row in sorted(all_metrics, key=lambda item: item["target_harmonic"]):
        noise_floor_rows.append({
            "target_harmonic": int(row["target_harmonic"]),
            "harmonic_peak_power": f"{row['harmonic_peak_power']:.12e}",
            "off_harmonic_median_power": f"{row['off_harmonic_median_power']:.12e}",
            "off_harmonic_bin_count": int(row["off_harmonic_bin_count"]),
            "peak_prominence_ratio": f"{row['peak_prominence_ratio']:.12e}",
        })
    write_csv(intermediate / "noise_floor_audit.csv", noise_floor_rows, NOISE_FLOOR_HEADERS)

    charge_rows = []
    for row in sorted(all_metrics, key=lambda item: item["target_harmonic"]):
        charge_rows.append({
            "target_harmonic": int(row["target_harmonic"]),
            "rho_band_power": f"{row['rho_band_power']:.12e}",
            "ey_harmonic_band_power": f"{row['harmonic_power']:.12e}",
            "charge_coupling_ratio": f"{row['charge_coupling_ratio']:.12e}",
            "min_charge_coupling_ratio": f"{row['min_charge_coupling_ratio']:.12e}",
            "max_charge_coupling_ratio": f"{row['max_charge_coupling_ratio']:.12e}",
            "charge_coupling_valid": "true" if row["charge_coupling_valid"] else "false",
        })
    write_csv(intermediate / "charge_coupling_audit.csv", charge_rows, CHARGE_COUPLING_HEADERS)

    energy_times, energy = load_field_energy(data_dir, run)
    write_csv(intermediate / "field_energy.csv", [
        {"time_omega_p_inv": f"{t:.8f}", "electromagnetic_field_energy": f"{e:.12e}"}
        for t, e in zip(energy_times, energy)
    ])
    harmonic_validation = {
        "sample_count": int(selected_metrics["sample_count"]),
        "window_function": run.window_function,
        "frequency_resolution_omega0": float(np.median(np.diff(fft["norm_freq"]))),
        "fundamental_power": selected_metrics["fundamental_power"],
        "selected_harmonic_power": selected_metrics["harmonic_power"],
        "selected_peak_prominence": selected_metrics["peak_prominence_ratio"],
        "selected_phase_error_rad": selected_metrics["phase_error_rad"],
        "energy_modulation_index": compute_energy_modulation(energy, run),
    }
    (intermediate / "harmonic_validation.json").write_text(json.dumps(harmonic_validation, indent=2, sort_keys=True) + "\n")
    phase_validation = {
        "ey_bz_phase_lag_rad": selected_metrics["polarization_phase_lag_rad"],
        "expected_phase_lag_rad": run.expected_phase_lag_rad,
        "phase_error_rad": selected_metrics["phase_error_rad"],
        "phase_tolerance_rad": run.phase_tolerance_rad,
    }
    (intermediate / "polarization_validation.json").write_text(json.dumps(phase_validation, indent=2, sort_keys=True) + "\n")

    verdict = "magnetized_harmonic_confirmed" if selected_metrics["validated"] else "harmonic_diagnostic_inconsistent"
    answer = {
        "selected_run_id": run.run_id,
        "selected_harmonic_order": int(run.target_harmonic),
        "harmonic_frequency_omega0": selected_metrics["peak_frequency_omega0"],
        "frequency_error_fraction": selected_metrics["frequency_error_fraction"],
        "harmonic_to_fundamental_power_ratio": selected_metrics["harmonic_to_fundamental_power_ratio"],
        "magnetization_parameter": namelist["magnetization_parameter"],
        "polarization_phase_lag_rad": selected_metrics["polarization_phase_lag_rad"],
        "verdict": verdict,
    }
    (results / "answer.json").write_text(json.dumps(answer, indent=2, sort_keys=True) + "\n")

    plt.figure(figsize=(7.0, 4.6))
    harmonic_axis = fft["norm_freq"]
    plt.semilogy(harmonic_axis, fft["ey_power"], lw=1.0, label="Ey spectral power")
    for center in (1, run.target_harmonic):
        plt.axvline(center, color="tab:red" if center == run.target_harmonic else "0.35", lw=1.0, alpha=0.8)
    plt.xlim(0.4, 5.2)
    plt.xlabel("angular frequency / omega0")
    plt.ylabel("windowed spectral power")
    plt.legend(frameon=False, fontsize=8)
    plt.tight_layout()
    plt.savefig(figures / "harmonic_spectrum.png", dpi=160)
    plt.close()

    shutil.copyfile(Path(__file__), code / "solve.py")
    report = f"""# Magnetized Laser-Plasma Harmonic Diagnostic

The workflow used the local SQLite catalog to enumerate accepted `harmonic_probe` candidates for a laser-plasma harmonic-generation diagnostic, then joined each candidate to the diagnostic contract that defines the signal group, time axis, spectral window, band widths, detrending, normalization, prominence, modulation, and phase conventions. The catalog run rows supplied the candidate-specific validation thresholds. The selected candidate is `{run.run_id}` at harmonic order `{run.target_harmonic}` because its windowed `Ey` spectrum has a validated peak, power ratio, prominence, and `Ey`/`Bz` phase relation, while the other accepted harmonic candidates fail at least one catalog validation rule.

The Smilei-style namelist was parsed with Python call-recording stubs for `Main`, `ExternalField`, `LaserPlanar1D`, `Species`, `DiagProbe`, and `DiagFields`. This recovered the laser fundamental frequency, laser amplitude, simulation cadence, probe and field lists, and the `Bz` field perpendicular to the x-propagating laser. The resulting magnetization parameter is `{namelist['magnetization_parameter']:.8f}`, so the harmonic interpretation is tied to a magnetized laser-plasma setup rather than an unmagnetized spectrum-only analysis.

The probe HDF5 structures for accepted candidates were inspected with `h5dump -n` before their probe arrays were loaded for candidate validation, and the selected probe tree was preserved as the probe handoff artifact. After selection, the selected field HDF5 structure was inspected with `h5dump -n` before loading electromagnetic energy for the separate late-time consistency diagnostic. The probe HDF5 contract supplied the signal group and dataset names used for `Ey`, `Bz`, and the charge channel `Rho`.

The signal stage used the contract analysis window and `{run.window_function}` window function, detrended the selected trace according to the contract, and computed the real FFT in normalized angular-frequency units. Mean removal suppresses DC leakage into low-frequency bins, while the finite window sets the frequency resolution and confines the harmonic decision to contract-defined bands. The selected harmonic peak is at `{selected_metrics['peak_frequency_omega0']:.8f}` times the laser frequency, with signed frequency error `{selected_metrics['frequency_error_fraction']:.6e}`. Its band-power ratio to the fundamental is `{selected_metrics['harmonic_to_fundamental_power_ratio']:.8f}`, which quantifies harmonic-band conversion relative to the laser fundamental, and its peak prominence `{selected_metrics['peak_prominence_ratio']:.6e}` guards against accepting noise-floor or leakage structure as a harmonic. The noise-floor audit records the off-harmonic median background used for that prominence calculation rather than treating the threshold as an isolated scalar.

The charge-channel handoff applies the same spectral window and power normalization to `Rho` and compares the `Rho` harmonic-band power with the selected `Ey` harmonic-band power. The selected charge-coupling ratio is `{selected_metrics['charge_coupling_ratio']:.8f}`, which keeps the plasma-response evidence separate from the electromagnetic conversion and phase checks while still participating in candidate validation.

Polarization validation was performed from the complex FFT coefficients, not from a visual peak alone. The selected harmonic `Ey`/`Bz` phase lag is `{selected_metrics['polarization_phase_lag_rad']:.8f}` rad, with phase error `{selected_metrics['phase_error_rad']:.6e}` rad against the selected catalog rule. This supports the verdict `{verdict}` when combined with the spectral power and frequency checks.

The intermediate artifacts expose the handoffs: catalog selection, candidate audit, namelist summary, HDF5 trees, windowed signal samples, harmonic spectrum rows, noise-floor audit rows, charge-coupling rows, polarization validation, electromagnetic energy, and harmonic validation metadata. The submitted `code/solve.py` honors the caller-provided output directory while reading `ORCHESTRATE_DATA_DIR` when set, so the same offline workflow can regenerate `answer.json`, intermediate handoffs, and the figure into a scratch results directory. The energy modulation index is interpreted only as a late-time consistency metric; it cannot replace the catalog frequency, power, prominence, charge-coupling, and phase checks that set the verdict. The figure `harmonic_spectrum.png` shows the computed spectrum with the fundamental and selected harmonic locations.

Limitations: this is an offline Smilei-style diagnostic bundle rather than a fresh PIC campaign. The conclusion depends on the mounted diagnostic cadence, the finite FFT window, the single probe boundary signal, and the catalog-defined validation thresholds; production follow-up would vary resolution, plasma density, pulse envelope, and magnetic-field strength.
"""
    (results / "report.md").write_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
