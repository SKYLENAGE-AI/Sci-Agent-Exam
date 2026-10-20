# Magnetized Laser-Plasma Harmonic Diagnostic Orchestration

## Scientific Objective

Build an offline multi-tool workflow for a PIC-diagnostic validation reviewer who needs to decide whether a Smilei-style laser-plasma run shows validated harmonic generation when an external magnetic field is applied perpendicular to the laser propagation direction. Evaluate the accepted harmonic-probe candidates in the local run catalog, recover the Smilei namelist quantities needed to interpret the laser frequency and magnetization, inspect the HDF5 diagnostic schemas, compute the contract-defined harmonic spectrum from the selected probe signal, validate the polarization phase relation and charge-channel plasma response, and report whether one harmonic branch satisfies the catalog and diagnostic-contract rules.

## Tool Access

Use the installed local interfaces only:

- `sqlite3` CLI, invoked against `/home/agent/data/run_catalog.sqlite`, for candidate and diagnostic-contract lookup.
- Python 3 with `h5py` for HDF5 array loading.
- `h5dump` CLI for HDF5 structure inspection before numerical extraction.
- Python `numpy`, `scipy`, and `matplotlib` for signal windowing, FFT-band power calculations, validation tables, and the diagnostic figure.

All required inputs are under `/home/agent/data/`; the workflow must run with no network. The executable pipeline must read from the directory named by `ORCHESTRATE_DATA_DIR` when that environment variable is set, and otherwise default to `/home/agent/data/`. The expected workload fits on one CPU, under 1 GB RAM, and should complete in a few minutes.

## Inputs

| Path | Role |
| :--- | :--- |
| `/home/agent/data/run_catalog.sqlite` | Local run catalog and diagnostic contract. It contains accepted, rejected, and decoy harmonic candidates plus schema names, spectral-window conventions, band definitions, and validation thresholds for the harmonic diagnostic family. |
| `/home/agent/data/smilei_inputs/tst1d_laser_magnetized_harmonics.py` | Smilei benchmark-style Python namelist snapshot for a laser propagating along x with an externally applied perpendicular magnetic field. |
| `/home/agent/data/diagnostics/Probes0.h5` | Smilei-style probe diagnostic with a contract-defined time axis, iteration axis, signal group, and time-resolved `Ey`, `Bz`, charge, and current channels. |
| `/home/agent/data/diagnostics/Fields0.h5` | Smilei-style field diagnostic with electromagnetic-energy scalar data for a late-time consistency handoff. |
| `/home/agent/data/diagnostic_manifest.json` | Input manifest and units. |
| `/home/agent/data/source_url.txt` | Provenance URL for the upstream open-source project; it is not an analysis input. |

## Workflow Stages

1. Query the SQLite catalog and diagnostic contract to identify accepted `laser_plasma_harmonics` candidates in the `harmonic_probe` diagnostic family. For each accepted candidate, the catalog row supplies the namelist path, HDF5 paths, candidate harmonic order, power-ratio threshold, frequency-error threshold, phase-lag expectation, phase tolerance, peak-prominence threshold, and charge-coupling bounds. The diagnostic contract supplies dataset names, signal group, spectral window, band widths, detrending, power normalization, harmonic-power, prominence, energy-modulation, and phase conventions.
2. Parse the Smilei namelist with local Python stubs or an equivalent structured method. The laser fundamental frequency, laser amplitude, timestep, simulation duration, probe and field lists, plasma density, and perpendicular magnetic-field component must come from the namelist rather than hardcoded assumptions. Use these values to report the magnetization parameter.
3. Inspect the selected HDF5 probe and field files with `h5dump` before numerical extraction with `h5py`; preserve the selected tree handoffs. Load arrays only through the dataset names and signal group specified by the diagnostic contract.
4. For every accepted harmonic candidate, apply the diagnostic contract's analysis time window, detrending rule, window function, frequency-band definitions, and power normalization to the probe `Ey` signal. Use the laser frequency recovered from the namelist to express spectral peaks in normalized harmonic order.
5. Validate each candidate using the catalog thresholds for harmonic peak frequency error, harmonic-to-fundamental band-power ratio, peak prominence, charge-channel coupling, and complex `Ey`/`Bz` phase lag. Report `frequency_error_fraction` as the signed offset `(peak_frequency_omega0 - target_harmonic) / target_harmonic`; use its absolute value only for threshold acceptance. Compute charge coupling as the `Rho` harmonic-band power divided by the `Ey` harmonic-band power for the same candidate band, using the same analysis window, detrending, and power normalization as the `Ey` spectrum. The phase lag must follow the diagnostic contract, and the phase-error fields must report the magnitude of the difference from the candidate's catalog expectation. Select exactly one accepted candidate for downstream reporting. Stop or document exclusion instead of silently carrying zero candidates, multiple candidates, rejected records, incompatible datasets, nonfinite signals, or too-short analysis windows forward.
6. Use the field HDF5 electromagnetic-energy diagnostic only as a separate late-time consistency handoff; do not use it as the primary harmonic spectrum or polarization observable.
7. Produce a rerunnable offline pipeline in `code/solve.py` that regenerates all deliverables from `ORCHESTRATE_DATA_DIR` when set. The pipeline should fail cleanly without emitting a final scientific `answer.json` when the mounted catalog or HDF5 data violate the stated validation requirements.

## Required Handoffs And Validation

Write content-bearing artifacts under `/home/agent/results/intermediate/`:

- `catalog_selection.csv`: the selected catalog row.
- `candidate_audit.csv`: validation summary for every accepted harmonic-probe candidate considered.
- `namelist_summary.json`: recovered Smilei laser, plasma, diagnostic, and magnetic-field quantities.
- `probe_h5dump_tree.txt` and `fields_h5dump_tree.txt`: HDF5 structure inspections.
- `windowed_signal.csv`: contract-windowed probe signal used for the selected spectral calculation.
- `harmonic_spectrum.csv`: harmonic-band spectrum and polarization rows for all accepted candidates.
- `noise_floor_audit.csv`: off-harmonic noise-floor evidence used in the peak-prominence calculation for all accepted candidates.
- `charge_coupling_audit.csv`: charge-channel harmonic coupling evidence for all accepted candidates.
- `harmonic_validation.json`: selected spectral-window, power, prominence, phase-error, and energy-modulation validation summary.
- `polarization_validation.json`: selected complex `Ey`/`Bz` phase-lag validation.
- `field_energy.csv`: electromagnetic-field energy by time.

Use normalized Smilei units: time in omega_p^-1, angular frequencies normalized by the namelist laser frequency omega0, and magnetic field in Smilei normalized units.

Exact intermediate schemas:

- `catalog_selection.csv`: exactly one row with headers `run_id`, `namelist_path`, `probe_h5`, `fields_h5`, `target_harmonic`, `min_power_ratio`, `max_frequency_error_fraction`, `expected_phase_lag_rad`, `phase_tolerance_rad`, `min_peak_prominence`, `min_charge_coupling_ratio`, and `max_charge_coupling_ratio`.
- `candidate_audit.csv`: one row per accepted `harmonic_probe` candidate, sorted by `run_id`, with headers `run_id`, `target_harmonic`, `sample_count`, `peak_frequency_omega0`, `frequency_error_fraction`, `harmonic_to_fundamental_power_ratio`, `peak_prominence_ratio`, `charge_coupling_ratio`, `polarization_phase_lag_rad`, and `validated`. Use `validated` as `true` or `false`.
- `namelist_summary.json`:

```json
{
  "geometry": "string",
  "grid_length": 0.0,
  "cell_length": 0.0,
  "timestep": 0.0,
  "simulation_time": 0.0,
  "laser_box_side": "string",
  "laser_omega0": 0.0,
  "laser_a0": 0.0,
  "external_magnetic_field": {
    "component": "string",
    "value": 0.0
  },
  "magnetization_parameter": 0.0,
  "electron_density": 0.0,
  "probe_every": 0,
  "probe_fields": ["string"],
  "field_fields": ["string"]
}
```

- `probe_h5dump_tree.txt` and `fields_h5dump_tree.txt`: text output from `h5dump -n`, `h5dump -H`, or an equivalent HDF5 tree inspection for the selected files.
- `windowed_signal.csv`: chronological selected-window rows with headers `iteration`, `time_omega_p_inv`, `window_weight`, `Ey_windowed`, and `Bz_windowed`.
- `harmonic_spectrum.csv`: rows sorted by `target_harmonic` with headers `target_harmonic`, `peak_frequency_omega0`, `band_power`, `band_power_ratio_to_fundamental`, `peak_prominence_ratio`, and `polarization_phase_lag_rad`.
- `noise_floor_audit.csv`: rows sorted by `target_harmonic` with headers `target_harmonic`, `harmonic_peak_power`, `off_harmonic_median_power`, `off_harmonic_bin_count`, and `peak_prominence_ratio`. The off-harmonic floor must follow the diagnostic contract's prominence convention rather than the target harmonic band itself.
- `charge_coupling_audit.csv`: rows sorted by `target_harmonic` with headers `target_harmonic`, `rho_band_power`, `ey_harmonic_band_power`, `charge_coupling_ratio`, `min_charge_coupling_ratio`, `max_charge_coupling_ratio`, and `charge_coupling_valid`. Use `charge_coupling_valid` as `true` or `false`.
- `harmonic_validation.json`:

```json
{
  "sample_count": 0,
  "window_function": "string",
  "frequency_resolution_omega0": 0.0,
  "fundamental_power": 0.0,
  "selected_harmonic_power": 0.0,
  "selected_peak_prominence": 0.0,
  "selected_phase_error_rad": 0.0,
  "energy_modulation_index": 0.0
}
```

- `polarization_validation.json`:

```json
{
  "ey_bz_phase_lag_rad": 0.0,
  "expected_phase_lag_rad": 0.0,
  "phase_error_rad": 0.0,
  "phase_tolerance_rad": 0.0
}
```

- `field_energy.csv`: chronological rows with headers `time_omega_p_inv` and `electromagnetic_field_energy`. The energy-modulation index in `harmonic_validation.json` must follow the diagnostic contract's energy-modulation convention.

## Deliverables

Write every file below under `/home/agent/results/`.

| Path | Description |
| :--- | :--- |
| `answer.json` | Final selected harmonic branch, spectral metrics, magnetic-field metric, polarization metric, and verdict. |
| `report.md` | Scientific report describing the tool sequence, handoffs, parameters, validations, results, and limitations, including that this analyzes a shipped offline diagnostic fixture rather than a new PIC campaign. |
| `code/solve.py` | Executable offline pipeline. `python code/solve.py [output_dir]` should regenerate the deliverables from `ORCHESTRATE_DATA_DIR` when set, otherwise from `/home/agent/data/`. |
| `intermediate/catalog_selection.csv` | Selected catalog row handoff. |
| `intermediate/candidate_audit.csv` | Accepted harmonic-candidate validation audit. |
| `intermediate/namelist_summary.json` | Parsed Smilei laser-plasma and magnetization quantities. |
| `intermediate/probe_h5dump_tree.txt` | Probe HDF5 structure inspection. |
| `intermediate/fields_h5dump_tree.txt` | Field HDF5 structure inspection. |
| `intermediate/windowed_signal.csv` | Windowed probe signal used for spectral analysis. |
| `intermediate/harmonic_spectrum.csv` | Harmonic-band spectrum and phase table. |
| `intermediate/noise_floor_audit.csv` | Off-harmonic noise-floor and prominence audit table. |
| `intermediate/charge_coupling_audit.csv` | Charge-channel harmonic-coupling audit table. |
| `intermediate/harmonic_validation.json` | Selected harmonic validation summary. |
| `intermediate/polarization_validation.json` | Selected `Ey`/`Bz` phase validation summary. |
| `intermediate/field_energy.csv` | Electromagnetic-field energy validation table. |
| `figures/harmonic_spectrum.png` | Diagnostic plot of the computed `Ey` spectrum with the fundamental and selected harmonic locations. |

`answer.json` must follow this exact top-level schema:

```json
{
  "selected_run_id": "string",
  "selected_harmonic_order": 0,
  "harmonic_frequency_omega0": 0.0,
  "frequency_error_fraction": 0.0,
  "harmonic_to_fundamental_power_ratio": 0.0,
  "magnetization_parameter": 0.0,
  "polarization_phase_lag_rad": 0.0,
  "verdict": "string"
}
```

`verdict` must be one of `magnetized_harmonic_confirmed` or `harmonic_diagnostic_inconsistent`. Use `magnetized_harmonic_confirmed` only when exactly one accepted harmonic-probe candidate satisfies the catalog and diagnostic-contract spectral, charge-coupling, and polarization validation rules.

Numerical tolerances used by the deterministic checker are RTOL 1e-5 and ATOL 1e-7 for dimensionless quantities; time values use ATOL 1e-6 omega_p^-1.
