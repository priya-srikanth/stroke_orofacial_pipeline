"""Phase 9 Task 2 (Commit A) — Stats inputs materialization driver.

Reads the stamped endpoint inventory at
``.scratch_phase_9/endpoint_inventory.csv`` and emits one
``pipeline_outputs/stats/inputs/<endpoint_slug>/<animal>.parquet`` per
(primary endpoint, cohort animal) pair. The emitted parquet schema is
the 11-column schema locked in the Phase 9 kickoff §Task 2:

  animal, date, rel_day, trial_idx, side, ipsi_contra, endpoint_slug,
  value, is_sentinel, cohort_bin_size, epoch_label

A companion manifest ``.scratch_phase_9/materialize_manifest.csv`` is
written at the end. The manifest columns are:

  endpoint_slug, animal, status, n_rows, n_sentinel, output_path,
  wall_time_s

Commit A scope (this driver):
- ``scalar_per_session`` — 7 endpoints (Cat A primary set). Reuse
  ``spout_behavior.visual_gate._compute_per_session_stats`` + the
  ``compute_lickiness_bySession`` + ``compute_switchiness_bySession``
  helpers from the same module. NPZ-based per-session compute.
- ``scalar_per_trial`` — 24 endpoints. 14 tongue primitives + 3 jaw
  primitives + 6 derived (reductions over vector primitives) +
  ``lickRate_byTrial`` (1; per-trial spout NPZ compute). All read from
  the per-session JSON / NPZ data sources.
- ``bool_per_trial`` — 1 endpoint (``mismatch_candidate_no_lick_with_jaw_move``).
  Reads tongue_jaw_mismatch candidate-trials parquet; casts bool → 0/1
  float.
- ``trajectory_per_animal`` — 1 endpoint (``recovery_trajectories``).
  SKIPPED — handled as a Task 6 plot family, not a Task 2 materialization
  target.

Commit B scope (deferred):
- ``vector_per_session`` — 1 endpoint (``latency_hist``). Per-trial
  first-correct-lick latencies → KS test at Task 4.

Commit C scope (deferred):
- ``scalar_per_animal_bin`` — 12 endpoints (4 UOT + 4 Wasserstein + 4 JS).
  Spatial distribution distance metrics via ``dlc_spatial.render_on_demand``
  + POT/scipy.

Run from the repo root:

  conda run -n stroke_orofacial python scripts/phase_9_stats/materialize_inputs.py

Optional CLI args:
  --animals PS46 PS47    Restrict to a subset; default = all 8 cohort animals.
  --endpoints SLUG1 ...  Restrict to a subset; default = all primary.
  --output-root PATH     Override default pipeline_outputs/stats/inputs/.
  --skip-existing        Don't re-emit parquets that already exist on disk.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stroke_orofacial.animals import AnimalInfo, load_animals
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.visual_gate import (
    compute_criteria_3,
    compute_criteria_4,
    compute_criteria_34,
    compute_criteria_acc_bySession,
    compute_first_correct_lick_sample_idx,
    compute_first_lick_correct,
    compute_firstLickCorrect_bySession,
    compute_latency_bySession,
    compute_lickiness_bySession,
    compute_num_licks_bySession,
    compute_switchiness_bySession,
    compute_trial_lick_delays,
    iter_cohort_a_sessions,
    load_session_plot_data,
    load_visual_gate_config,
)
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INVENTORY_PATH = REPO_ROOT / ".scratch_phase_9" / "endpoint_inventory.csv"
DEFAULT_MANIFEST_PATH = REPO_ROOT / ".scratch_phase_9" / "materialize_manifest.csv"


PARQUET_COLUMNS: tuple[str, ...] = (
    "animal", "date", "rel_day", "trial_idx", "side", "ipsi_contra",
    "endpoint_slug", "value", "is_sentinel", "cohort_bin_size", "epoch_label",
)

MANIFEST_COLUMNS: tuple[str, ...] = (
    "endpoint_slug", "animal", "status", "n_rows", "n_sentinel",
    "output_path", "wall_time_s",
)


# ===========================================================================
# Endpoint inventory loader
# ===========================================================================


@dataclass(frozen=True)
class EndpointSpec:
    """One row of the stamped endpoint_inventory.csv."""
    slug: str
    category: str
    value_type: str
    is_primary: bool
    is_confirmatory: bool
    n_permutations_override: int | None
    comparison_axes_in_scope: tuple[str, ...]
    notes: str

    @property
    def is_derived(self) -> bool:
        return self.category.startswith("kinematics-tongue derived")


def load_inventory(path: Path | str = DEFAULT_INVENTORY_PATH) -> list[EndpointSpec]:
    """Parse endpoint_inventory.csv into ``EndpointSpec`` objects."""
    out: list[EndpointSpec] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n_perm_raw = row["n_permutations_override"].strip()
            n_perm = int(n_perm_raw) if n_perm_raw else None
            axes_raw = row["comparison_axes_in_scope"].strip()
            axes = tuple(a.strip() for a in axes_raw.split(";") if a.strip())
            out.append(EndpointSpec(
                slug=row["endpoint_slug"],
                category=row["category"],
                value_type=row["value_type"],
                is_primary=row["is_primary"].strip().lower() == "true",
                is_confirmatory=row["is_confirmatory"].strip().lower() == "true",
                n_permutations_override=n_perm,
                comparison_axes_in_scope=axes,
                notes=row["notes"],
            ))
    return out


# ===========================================================================
# Per-animal compute cache
# ===========================================================================
#
# A SINGLE PASS over the animal's sessions populates everything every
# materializer needs. The cache lives for the duration of one animal's
# emit; we avoid re-loading NPZs / per-trial JSONs across the ~32
# endpoints by iterating endpoints in the inner loop.


@dataclass
class _SessionScalars:
    """Per-session scalar values for ONE animal (× all sessions).

    Each field is a dict keyed by date_label (YYYYMMDD); inner value is
    either ``dict[side, float]`` (per-side aggregates) or ``dict[side,
    dict[stat_key, float]]`` (for endpoints that compute mean+std).
    """
    dates: list[str] = field(default_factory=list)
    rel_days: dict[str, int] = field(default_factory=dict)

    # 7 Cat A primary endpoints. Each is dict[date][side] → float.
    first_lick_accuracy_all: dict[str, dict[str, float]] = field(default_factory=dict)
    num_correct_licks_per_trial: dict[str, dict[str, float]] = field(default_factory=dict)
    num_all_licks_per_trial: dict[str, dict[str, float]] = field(default_factory=dict)
    num_incorrect_licks_per_trial: dict[str, dict[str, float]] = field(default_factory=dict)
    latency_to_first_correct_lick_s: dict[str, dict[str, float]] = field(default_factory=dict)
    late_lickiness: dict[str, dict[str, float]] = field(default_factory=dict)
    lick_switch_rate: dict[str, dict[str, float]] = field(default_factory=dict)

    # Per-session per-side per-trial lick rate (for lickRate_byTrial).
    # dict[date][side] → list of (trial_idx, rate_hz) pairs.
    lick_rate_per_trial: dict[
        str, dict[str, list[tuple[int, float]]]
    ] = field(default_factory=dict)

    # Per-session per-side per-trial first-correct-lick latency in seconds
    # (for latency_hist; Commit B). NaN if the trial had no correct lick.
    # dict[date][side] → list of (trial_idx, latency_s) pairs.
    latency_per_trial: dict[
        str, dict[str, list[tuple[int, float]]]
    ] = field(default_factory=dict)


def _compute_session_scalars_for_animal(
    animal: str,
    resolver: PathResolver,
    animal_info: AnimalInfo,
    behavior_params: dict[str, Any],
    visual_gate_config: dict[str, Any],
) -> _SessionScalars:
    """Iterate the animal's Cohort A sessions; compute every scalar
    endpoint Phase 9 Commit A needs. Mirrors the structure of
    ``visual_gate._compute_per_session_stats`` but emits a per-(date,
    side) result rather than the per-side longitudinal arrays."""
    scalars = _SessionScalars()
    dates = iter_cohort_a_sessions(animal, resolver)
    scalars.dates = dates
    window_around = behavior_params["window_around_tones"]
    crit3_window = behavior_params["criteria_3"]["window"]
    # Lickiness late-window: start = end of the post-tone trial window
    # (window_around_tones[1]); end = visual_gate.lickiness_window_seconds
    # (default 60). Matches render_lickiness_bySession contract.
    lickiness_start_s = float(window_around[1])
    lickiness_end_s = float(visual_gate_config["lickiness_window_seconds"])

    for date_label in dates:
        session_date = datetime.date(
            int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
        )
        scalars.rel_days[date_label] = animal_info.day_relative_to_stroke(session_date)

        data = load_session_plot_data(animal, date_label, resolver)
        delays = compute_trial_lick_delays(data, window_around)
        fcl_idx = compute_first_correct_lick_sample_idx(data, crit3_window)
        c3 = compute_criteria_3(fcl_idx)
        c4 = compute_criteria_4(data, behavior_params["criteria_4"])
        c34 = compute_criteria_34(c3, c4)
        first_corr = compute_first_lick_correct(delays)

        # Per-side mean+std aggregates.
        flc_zero = compute_firstLickCorrect_bySession(
            first_corr, treat_none_as_zero=True,
        )
        ms_num = compute_num_licks_bySession(delays)
        ms_lat = compute_latency_bySession(
            fcl_idx, data.tones_idx, data.sample_rate,
        )
        ms_lick = compute_lickiness_bySession(
            data,
            late_window_start_seconds=lickiness_start_s,
            late_window_end_seconds=lickiness_end_s,
        )
        sw = compute_switchiness_bySession(delays)
        # criteria_acc consumed by the criteria_performance endpoint
        # (not in Commit A primary set per the stamped inventory but
        # computed cheaply alongside for forward-compat).
        _ = compute_criteria_acc_bySession(c34)

        per_side_zero = {s: flc_zero[s] for s in ("L", "R")}
        scalars.first_lick_accuracy_all[date_label] = per_side_zero
        scalars.num_correct_licks_per_trial[date_label] = {
            s: ms_num["correct"][f"Tone_{s}"]["mean"] for s in ("L", "R")
        }
        scalars.num_all_licks_per_trial[date_label] = {
            s: ms_num["all"][f"Tone_{s}"]["mean"] for s in ("L", "R")
        }
        scalars.num_incorrect_licks_per_trial[date_label] = {
            s: ms_num["incorrect"][f"Tone_{s}"]["mean"] for s in ("L", "R")
        }
        scalars.latency_to_first_correct_lick_s[date_label] = {
            s: ms_lat[s]["mean"] for s in ("L", "R")
        }
        scalars.late_lickiness[date_label] = {s: float(ms_lick[s]) for s in ("L", "R")}
        # lick_switch_rate semantics: side=L → switches FROM L (L->R count)
        # side=R → switches FROM R (R->L count). Documented per Commit A
        # close report; flip later if Priya prefers destination semantics.
        scalars.lick_switch_rate[date_label] = {
            "L": float(sw["L->R"]),
            "R": float(sw["R->L"]),
        }

        # Per-trial lick rate (for lickRate_byTrial). Same inner loop as
        # compute_median_lick_rate_bySession but kept per-trial.
        per_trial_rates: dict[str, list[tuple[int, float]]] = {"L": [], "R": []}
        sr = data.sample_rate
        for side_tone in ("L", "R"):
            for trial_idx, by_side in delays[f"Tone_{side_tone}"].items():
                correct_delays = by_side[f"Lick_{side_tone}"]
                ilis = np.diff(correct_delays)
                if ilis.size == 0:
                    rate = 0.0
                else:
                    med = float(np.median(ilis))
                    rate = 0.0 if med <= 0 else float(1.0 / (med / sr))
                if not np.isfinite(rate):
                    rate = 0.0
                per_trial_rates[side_tone].append((int(trial_idx), rate))
        scalars.lick_rate_per_trial[date_label] = per_trial_rates

        # Per-trial first-correct-lick latency (for latency_hist; Commit B).
        # Mirrors compute_latency_bySession's inner-loop math:
        #   latency_s = (fcl_sample_idx - tone_sample_idx) / sample_rate
        # NaN when the trial had no correct lick (fcl is None).
        per_trial_latencies: dict[str, list[tuple[int, float]]] = {"L": [], "R": []}
        for side_tone in ("L", "R"):
            tones = data.tones_idx[f"Tone_{side_tone}"]
            for tone_idx, fcl in fcl_idx[side_tone].items():
                if fcl is None:
                    lat = float("nan")
                else:
                    lat = float((fcl - int(tones[tone_idx])) / sr)
                per_trial_latencies[side_tone].append((int(tone_idx), lat))
        scalars.latency_per_trial[date_label] = per_trial_latencies
    return scalars


# ===========================================================================
# Per-trial JSON loaders (tongue + jaw)
# ===========================================================================


def _load_tongue_pertrial_json(
    animal: str, date_label: str, resolver: PathResolver,
) -> dict[str, Any] | None:
    """Read tongue_pertrial endpoints JSON for one session.

    Returns the parsed JSON dict, or None if the file doesn't exist
    (the upstream Phase 7a.3 emit didn't run for this session).
    """
    session_date = datetime.date(
        int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
    )
    path = resolver.tongue_pertrial_endpoints_json(animal, session_date)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jaw_pertrial_json(
    animal: str, date_label: str, resolver: PathResolver,
) -> dict[str, Any] | None:
    """Read jaw_pertrial endpoints JSON for one session.

    Returns None if the upstream Phase 7a.5 jaw emit didn't run.
    """
    session_date = datetime.date(
        int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
    )
    path = resolver.jaw_pertrial_endpoints_json(animal, session_date)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_mismatch_parquet(
    animal: str, date_label: str, resolver: PathResolver,
) -> pd.DataFrame | None:
    """Read tongue_jaw_mismatch candidate-trials parquet for one session.

    Returns None if the upstream Phase 7a.5 mismatch emit didn't run.
    """
    session_date = datetime.date(
        int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
    )
    path = resolver.tongue_jaw_mismatch_candidate_trials_parquet(animal, session_date)
    if not path.exists():
        return None
    return pd.read_parquet(path)


# ===========================================================================
# Per-vt materializers — each returns list[dict] of row records
# ===========================================================================
#
# Every materializer returns rows matching :data:`PARQUET_COLUMNS`. The
# driver then filters NaN-vs-sentinel + adds epoch_label + writes parquet.


# Slug → (compute_section, key) for endpoints stored on the session-scalars cache.
_SESSION_SLUG_TO_FIELD: dict[str, str] = {
    "first_lick_accuracy_all": "first_lick_accuracy_all",
    "num_correct_licks_per_trial": "num_correct_licks_per_trial",
    "num_all_licks_per_trial": "num_all_licks_per_trial",
    "num_incorrect_licks_per_trial": "num_incorrect_licks_per_trial",
    "latency_to_first_correct_lick_s": "latency_to_first_correct_lick_s",
    "late_lickiness": "late_lickiness",
    "lick_switch_rate": "lick_switch_rate",
}


def _materialize_scalar_per_session(
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    session_scalars: _SessionScalars,
) -> list[dict[str, Any]]:
    """One row per (date, side) for one scalar_per_session endpoint."""
    field_name = _SESSION_SLUG_TO_FIELD[spec.slug]
    per_session = getattr(session_scalars, field_name)

    rows: list[dict[str, Any]] = []
    for date_label in session_scalars.dates:
        if date_label not in per_session:
            continue
        rel_day = session_scalars.rel_days[date_label]
        session_date = datetime.date(
            int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
        )
        for side in ("L", "R"):
            value = per_session[date_label].get(side)
            is_sentinel = (
                value is None or (isinstance(value, float) and not np.isfinite(value))
            )
            rows.append({
                "animal": animal,
                "date": session_date,
                "rel_day": int(rel_day),
                "trial_idx": None,
                "side": side,
                "ipsi_contra": animal_info.mouse_side_to_ipsi_contra(side),
                "endpoint_slug": spec.slug,
                "value": None if is_sentinel else float(value),
                "is_sentinel": bool(is_sentinel),
                "cohort_bin_size": int(animal_info.bin_days),
                "epoch_label": assign_epoch_label(int(rel_day), animal_info),
            })
    return rows


# tongue scalar_per_trial endpoints → (top-level subdict key, field name)
_TONGUE_SCALAR_PATH: dict[str, tuple[str, str]] = {
    "tongue_lick1_y_peak": ("lick1_lick2_metrics", "lick1_y_peak"),
    "tongue_lick1_t_peak_ms": ("lick1_lick2_metrics", "lick1_t_peak_ms"),
    "tongue_lick1_x_at_ypeak": ("lick1_lick2_metrics", "lick1_x_at_ypeak"),
    "tongue_lick2_y_peak": ("lick1_lick2_metrics", "lick2_y_peak"),
    "tongue_lick2_t_peak_ms": ("lick1_lick2_metrics", "lick2_t_peak_ms"),
    "tongue_lick2_x_at_ypeak": ("lick1_lick2_metrics", "lick2_x_at_ypeak"),
    "tongue_n_licks": ("n_licks_family", "n_licks"),
    "tongue_n_left": ("n_licks_family", "n_left"),
    "tongue_n_right": ("n_licks_family", "n_right"),
    "tongue_mean_within_bout_ili_ms": ("licking_dynamics_reductions", "mean_within_bout_ili_ms"),
    "tongue_lick_rate_hz": ("licking_dynamics_reductions", "lick_rate_hz"),
    "tongue_lick1_angle_at_ypeak": ("tongue_angle", "lick1_angle_at_ypeak"),
    "tongue_lick2_angle_at_ypeak": ("tongue_angle", "lick2_angle_at_ypeak"),
    "tongue_first_peak_t_ms": ("cell50_own_bout_scalars", "first_peak_t_ms"),
}

# tongue derived endpoints → (subdict, vector_field, reducer)
_TONGUE_DERIVED_PATH: dict[str, tuple[str, str, str]] = {
    "tongue_lick1_vy_peak": ("peak_velocity_per_lick", "vy_peaks_bylick", "first"),
    "tongue_max_vy_peak_first5": ("peak_velocity_per_lick", "vy_peaks_bylick", "max_first5"),
    "tongue_median_vy_peak_per_trial": ("peak_velocity_per_lick", "vy_peaks_bylick", "median"),
    "tongue_median_vxy_peak_per_trial": ("peak_velocity_per_lick", "vxy_peaks_bylick", "median"),
    "tongue_median_angle_at_peak_velocity": ("tongue_angle", "angle_at_peak_velocity_bylick", "median"),
    "tongue_median_angle_max_signed_per_lick": ("tongue_angle", "angle_max_signed_per_lick", "median"),
    # Addendum #8 (CSV rows 66-68) — 3 new headline kinematic endpoints
    # using the existing peak_velocity_per_lick.vxy_peaks_bylick vector
    # primitive. Reductions: first / max_first5 / mean_first5 (new).
    "tongue_lick1_vxy_peak": ("peak_velocity_per_lick", "vxy_peaks_bylick", "first"),
    "tongue_max_vxy_peak_first5": ("peak_velocity_per_lick", "vxy_peaks_bylick", "max_first5"),
    "tongue_mean_vxy_peak_first5": ("peak_velocity_per_lick", "vxy_peaks_bylick", "mean_first5"),
}

_JAW_SCALAR_FIELDS: tuple[str, ...] = (
    "jaw_peak_pos_deflection",
    "jaw_peak_selected_deflection",
    "jaw_n_frames_over_thresh",
)


def _reduce_vector_per_trial(vec: list[Any] | None, reducer: str) -> float | None:
    """Apply ``reducer`` to a per-trial vector. Returns None if the
    vector is missing / empty / all-NaN.

    Reducers:
    - ``"first"``: first element. Returns None if vec is empty.
    - ``"max_first5"``: max of first 5 elements; falls back to max of
      whatever exists if fewer than 5 (documented per inventory note
      for tongue_max_vy_peak_first5).
    - ``"mean_first5"``: mean of first 5 finite elements; falls back to
      mean of all finite elements if the first-5 head has no finite
      values. Added per Addendum #8 (CSV row 68
      ``tongue_mean_vxy_peak_first5``) as a sibling reducer to
      ``max_first5`` — different statistical sensitivity (mean vs max).
    - ``"median"``: nanmedian over all finite elements.
    """
    if vec is None:
        return None
    arr = np.asarray(vec, dtype=float)
    if arr.size == 0:
        return None
    finite = arr[np.isfinite(arr)]
    if reducer == "first":
        v = arr[0]
        return None if not np.isfinite(v) else float(v)
    if reducer == "max_first5":
        head = arr[:5]
        head_f = head[np.isfinite(head)]
        if head_f.size == 0:
            # Fall back to full-vector max per inventory note.
            return None if finite.size == 0 else float(np.max(finite))
        return float(np.max(head_f))
    if reducer == "mean_first5":
        head = arr[:5]
        head_f = head[np.isfinite(head)]
        if head_f.size == 0:
            # Fall back to full-vector mean per inventory note.
            return None if finite.size == 0 else float(np.mean(finite))
        return float(np.mean(head_f))
    if reducer == "median":
        return None if finite.size == 0 else float(np.median(finite))
    raise ValueError(f"unknown reducer: {reducer!r}")


def _materialize_tongue_scalar_per_trial(
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    session_scalars: _SessionScalars,
    resolver: PathResolver,
) -> list[dict[str, Any]]:
    """One row per (date, trial_idx, side) for one tongue per-trial scalar."""
    subdict, field_name = _TONGUE_SCALAR_PATH[spec.slug]
    rows: list[dict[str, Any]] = []
    for date_label in session_scalars.dates:
        payload = _load_tongue_pertrial_json(animal, date_label, resolver)
        if payload is None:
            continue
        rows.extend(_emit_tongue_per_trial_rows(
            payload=payload,
            spec=spec,
            animal=animal,
            animal_info=animal_info,
            date_label=date_label,
            session_scalars=session_scalars,
            value_getter=lambda p: p["tongue"][subdict][field_name],
        ))
    return rows


def _materialize_tongue_derived(
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    session_scalars: _SessionScalars,
    resolver: PathResolver,
) -> list[dict[str, Any]]:
    """One row per (date, trial_idx, side) for one derived tongue
    endpoint (numpy reduction over a vector_per_trial primitive)."""
    subdict, vec_field, reducer = _TONGUE_DERIVED_PATH[spec.slug]
    rows: list[dict[str, Any]] = []
    for date_label in session_scalars.dates:
        payload = _load_tongue_pertrial_json(animal, date_label, resolver)
        if payload is None:
            continue
        vectors = payload["tongue"][subdict][vec_field]
        # Reduce vectors → list[float | None] aligned with trial_indices/sides.
        reduced = [_reduce_vector_per_trial(v, reducer) for v in vectors]
        rows.extend(_emit_tongue_per_trial_rows(
            payload=payload,
            spec=spec,
            animal=animal,
            animal_info=animal_info,
            date_label=date_label,
            session_scalars=session_scalars,
            value_getter=lambda _p, _r=reduced: _r,
        ))
    return rows


def _emit_tongue_per_trial_rows(
    *,
    payload: dict[str, Any],
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    date_label: str,
    session_scalars: _SessionScalars,
    value_getter,
) -> list[dict[str, Any]]:
    """Common emit loop for tongue per-trial + tongue-derived endpoints."""
    rel_day = session_scalars.rel_days[date_label]
    session_date = datetime.date(
        int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
    )
    values = value_getter(payload)
    trial_indices = payload["trial_indices"]
    sides = payload["sides"]
    if not (len(values) == len(trial_indices) == len(sides)):
        raise ValueError(
            f"tongue_pertrial payload length mismatch for "
            f"{animal}/{date_label}: values={len(values)}, "
            f"trials={len(trial_indices)}, sides={len(sides)}.",
        )

    out: list[dict[str, Any]] = []
    for v, ti, side in zip(values, trial_indices, sides):
        is_sentinel = v is None or (
            isinstance(v, float) and not np.isfinite(v)
        )
        out.append({
            "animal": animal,
            "date": session_date,
            "rel_day": int(rel_day),
            "trial_idx": int(ti),
            "side": str(side),
            "ipsi_contra": animal_info.mouse_side_to_ipsi_contra(side),
            "endpoint_slug": spec.slug,
            "value": None if is_sentinel else float(v),
            "is_sentinel": bool(is_sentinel),
            "cohort_bin_size": int(animal_info.bin_days),
            "epoch_label": assign_epoch_label(int(rel_day), animal_info),
        })
    return out


def _materialize_jaw_scalar_per_trial(
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    session_scalars: _SessionScalars,
    resolver: PathResolver,
) -> list[dict[str, Any]]:
    """One row per (date, trial_idx, side) for one jaw per-trial scalar."""
    field_name = spec.slug  # jaw_peak_pos_deflection etc. — same name in JSON
    rows: list[dict[str, Any]] = []
    for date_label in session_scalars.dates:
        payload = _load_jaw_pertrial_json(animal, date_label, resolver)
        if payload is None:
            continue
        rel_day = session_scalars.rel_days[date_label]
        session_date = datetime.date(
            int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
        )
        values = payload["jaw_pertrial"][field_name]
        trial_indices = payload["trial_indices"]
        sides = payload["sides"]
        for v, ti, side in zip(values, trial_indices, sides):
            is_sentinel = v is None or (
                isinstance(v, float) and not np.isfinite(v)
            )
            rows.append({
                "animal": animal,
                "date": session_date,
                "rel_day": int(rel_day),
                "trial_idx": int(ti),
                "side": str(side),
                "ipsi_contra": animal_info.mouse_side_to_ipsi_contra(side),
                "endpoint_slug": spec.slug,
                "value": None if is_sentinel else float(v),
                "is_sentinel": bool(is_sentinel),
                "cohort_bin_size": int(animal_info.bin_days),
                "epoch_label": assign_epoch_label(int(rel_day), animal_info),
            })
    return rows


def _materialize_mismatch_bool_per_trial(
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    session_scalars: _SessionScalars,
    resolver: PathResolver,
) -> list[dict[str, Any]]:
    """One row per (date, trial_idx, side) for the mismatch candidate
    bool. Cast bool → 0.0/1.0 float per Phase 9 schema (value: float64
    | null). False ≠ sentinel — both 0/1 are valid; is_sentinel only
    fires if the trial row is missing entirely."""
    if spec.slug != "mismatch_candidate_no_lick_with_jaw_move":
        raise ValueError(f"unexpected bool_per_trial slug: {spec.slug!r}")
    rows: list[dict[str, Any]] = []
    for date_label in session_scalars.dates:
        df = _load_mismatch_parquet(animal, date_label, resolver)
        if df is None or len(df) == 0:
            continue
        rel_day = session_scalars.rel_days[date_label]
        session_date = datetime.date(
            int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
        )
        for _, r in df.iterrows():
            v_bool = bool(r["candidate_no_lick_with_jaw_move"])
            rows.append({
                "animal": animal,
                "date": session_date,
                "rel_day": int(rel_day),
                "trial_idx": int(r["trial_index"]),
                "side": str(r["side"]),
                "ipsi_contra": animal_info.mouse_side_to_ipsi_contra(str(r["side"])),
                "endpoint_slug": spec.slug,
                "value": 1.0 if v_bool else 0.0,
                "is_sentinel": False,
                "cohort_bin_size": int(animal_info.bin_days),
                "epoch_label": assign_epoch_label(int(rel_day), animal_info),
            })
    return rows


def _materialize_latency_hist(
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    session_scalars: _SessionScalars,
) -> list[dict[str, Any]]:
    """One row per (date, trial_idx, side) for latency_hist (vector_per_session).

    Per Addendum #4 the "vector" is the per-session distribution of per-
    trial first-correct-lick latencies. The materialization just emits
    one row per trial with that latency; Task 4's KS runner groups by
    (animal, epoch_label) to build pre vs post latency vectors at test
    time. Per Addendum #5 (B) no granularity multiplexing happens at
    materialize-time — Task 4 pools across sessions within bin/epoch.
    """
    if spec.slug != "latency_hist":
        raise ValueError(f"unexpected vector_per_session slug: {spec.slug!r}")
    rows: list[dict[str, Any]] = []
    for date_label in session_scalars.dates:
        per_date = session_scalars.latency_per_trial.get(date_label, {})
        rel_day = session_scalars.rel_days[date_label]
        session_date = datetime.date(
            int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
        )
        for side in ("L", "R"):
            for ti, lat in per_date.get(side, []):
                is_sentinel = not np.isfinite(lat)
                rows.append({
                    "animal": animal,
                    "date": session_date,
                    "rel_day": int(rel_day),
                    "trial_idx": int(ti),
                    "side": side,
                    "ipsi_contra": animal_info.mouse_side_to_ipsi_contra(side),
                    "endpoint_slug": spec.slug,
                    "value": None if is_sentinel else float(lat),
                    "is_sentinel": bool(is_sentinel),
                    "cohort_bin_size": int(animal_info.bin_days),
                    "epoch_label": assign_epoch_label(int(rel_day), animal_info),
                })
    return rows


def _materialize_lick_rate_by_trial(
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    session_scalars: _SessionScalars,
) -> list[dict[str, Any]]:
    """One row per (date, trial_idx, side) for lickRate_byTrial.

    Per-trial median-ILI → Hz, computed inline alongside
    :func:`_compute_session_scalars_for_animal` (cached on
    ``session_scalars.lick_rate_per_trial``).
    """
    rows: list[dict[str, Any]] = []
    for date_label in session_scalars.dates:
        per_date = session_scalars.lick_rate_per_trial.get(date_label, {})
        rel_day = session_scalars.rel_days[date_label]
        session_date = datetime.date(
            int(date_label[:4]), int(date_label[4:6]), int(date_label[6:8]),
        )
        for side in ("L", "R"):
            for ti, rate in per_date.get(side, []):
                is_sentinel = not np.isfinite(rate)
                rows.append({
                    "animal": animal,
                    "date": session_date,
                    "rel_day": int(rel_day),
                    "trial_idx": int(ti),
                    "side": side,
                    "ipsi_contra": animal_info.mouse_side_to_ipsi_contra(side),
                    "endpoint_slug": spec.slug,
                    "value": None if is_sentinel else float(rate),
                    "is_sentinel": bool(is_sentinel),
                    "cohort_bin_size": int(animal_info.bin_days),
                    "epoch_label": assign_epoch_label(int(rel_day), animal_info),
                })
    return rows


# ===========================================================================
# Driver dispatch
# ===========================================================================


def _dispatch_materializer(
    spec: EndpointSpec,
    animal: str,
    animal_info: AnimalInfo,
    session_scalars: _SessionScalars,
    resolver: PathResolver,
) -> list[dict[str, Any]] | None:
    """Route an endpoint to its value_type-specific materializer.

    Returns None for endpoints OUT OF Commit A scope (vector_per_session,
    scalar_per_animal_bin, trajectory_per_animal) — the driver marks
    the manifest row as ``"skipped_commit_BC"`` for those.
    """
    if spec.value_type == "scalar_per_session":
        return _materialize_scalar_per_session(spec, animal, animal_info, session_scalars)
    if spec.value_type == "vector_per_session" and spec.slug == "latency_hist":
        return _materialize_latency_hist(spec, animal, animal_info, session_scalars)
    if spec.slug == "lickRate_byTrial":
        return _materialize_lick_rate_by_trial(spec, animal, animal_info, session_scalars)
    if spec.is_derived:
        return _materialize_tongue_derived(
            spec, animal, animal_info, session_scalars, resolver,
        )
    if spec.slug in _TONGUE_SCALAR_PATH:
        return _materialize_tongue_scalar_per_trial(
            spec, animal, animal_info, session_scalars, resolver,
        )
    if spec.slug in _JAW_SCALAR_FIELDS:
        return _materialize_jaw_scalar_per_trial(
            spec, animal, animal_info, session_scalars, resolver,
        )
    if spec.value_type == "bool_per_trial":
        return _materialize_mismatch_bool_per_trial(
            spec, animal, animal_info, session_scalars, resolver,
        )
    # Out of Commit A scope.
    return None


def _output_path(resolver: PathResolver, slug: str, animal: str) -> Path:
    """Resolve ``stats/inputs/<slug>/<animal>.parquet`` under the
    PathResolver's output root. Creates the parent dir.

    Uses ``resolver.pipeline_outputs(subdir="stats")`` per the existing
    convention; the writeguard accepts ``stats/`` as a new top-level
    output subtree (parallel to ``spout_behavior/``, ``dlc_kinematics/``,
    ``dlc_analysis/``).
    """
    out_root = resolver.pipeline_outputs(subdir="stats") / "inputs" / slug
    out_root.mkdir(parents=True, exist_ok=True)
    return out_root / f"{animal}.parquet"


def _write_parquet(rows: list[dict[str, Any]], path: Path) -> int:
    """Write rows to parquet. Returns the row count."""
    if not rows:
        # Emit an empty parquet with the correct schema so downstream
        # consumers can still glob over the inputs tree.
        df = pd.DataFrame(columns=list(PARQUET_COLUMNS))
        df = df.astype({
            "animal": object, "date": object, "rel_day": "Int64",
            "trial_idx": "Int64", "side": object, "ipsi_contra": object,
            "endpoint_slug": object, "value": float, "is_sentinel": bool,
            "cohort_bin_size": "Int64", "epoch_label": object,
        })
        df.to_parquet(path, index=False)
        return 0
    df = pd.DataFrame(rows, columns=list(PARQUET_COLUMNS))
    # Use nullable integer dtype for trial_idx so None survives the roundtrip.
    df["trial_idx"] = df["trial_idx"].astype("Int64")
    df["rel_day"] = df["rel_day"].astype("Int64")
    df["cohort_bin_size"] = df["cohort_bin_size"].astype("Int64")
    df.to_parquet(path, index=False)
    return len(df)


# ===========================================================================
# Main
# ===========================================================================


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--animals", nargs="*", default=None)
    p.add_argument("--endpoints", nargs="*", default=None)
    p.add_argument(
        "--output-root", type=Path, default=None,
        help="Override resolver pipeline_outputs root (e.g. tmp_path for tests).",
    )
    p.add_argument(
        "--skip-existing", action="store_true",
        help="Don't re-emit parquets that already exist on disk.",
    )
    p.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST_PATH,
    )
    p.add_argument(
        "--inventory", type=Path, default=DEFAULT_INVENTORY_PATH,
    )
    return p.parse_args()


def _commit_ab_endpoints(specs: list[EndpointSpec]) -> Iterator[EndpointSpec]:
    """Yield primary endpoints in Commit A + Commit B scope (skip the
    spatial value_type ``scalar_per_animal_time`` per Addendum #5 (D)
    rename from ``scalar_per_animal_bin``; skip ``trajectory_per_animal``).
    """
    deferred_vts = {
        "scalar_per_animal_time",   # Commit C (Addendum #5 (D) rename)
        "scalar_per_animal_bin",    # back-compat alias
        "trajectory_per_animal",    # Task 6 plot family, not Task 2
    }
    for spec in specs:
        if not spec.is_primary:
            continue
        if spec.value_type in deferred_vts:
            continue
        yield spec


# Back-compat alias retained for callers / tests.
_commit_a_endpoints = _commit_ab_endpoints


def main() -> int:
    args = _parse_args()
    specs = load_inventory(args.inventory)
    target_specs = [
        s for s in _commit_ab_endpoints(specs)
        if args.endpoints is None or s.slug in args.endpoints
    ]
    animals_map = load_animals()
    cohort = sorted(animals_map.keys())
    target_animals = [
        a for a in cohort
        if args.animals is None or a in args.animals
    ]

    print("Phase 9 Commit A + B materialize")
    print(f"  endpoints in scope: {len(target_specs)}")
    print(f"  animals in scope:   {len(target_animals)}")
    print(f"  total emit targets: {len(target_specs) * len(target_animals)}")
    print()

    resolver_kwargs: dict[str, Any] = {}
    if args.output_root is not None:
        # PathResolver's ``output_root`` kwarg overrides the
        # pipeline_outputs root only (other logical roots are unaffected
        # per the task #20 contract).
        resolver_kwargs["output_root"] = args.output_root
    resolver = PathResolver(**resolver_kwargs) if resolver_kwargs else PathResolver()
    defaults = load_defaults()
    behavior_params = defaults["behavior_report"]
    visual_gate_config = load_visual_gate_config()

    manifest_rows: list[dict[str, Any]] = []
    for animal in target_animals:
        print(f"=== {animal} ===")
        animal_info = animals_map[animal]
        t0 = time.monotonic()
        session_scalars = _compute_session_scalars_for_animal(
            animal, resolver, animal_info, behavior_params, visual_gate_config,
        )
        per_animal_compute_s = time.monotonic() - t0
        print(
            f"  per-animal compute: {len(session_scalars.dates)} sessions, "
            f"{per_animal_compute_s:.1f} s",
        )

        for spec in target_specs:
            out_path = _output_path(resolver, spec.slug, animal)
            if args.skip_existing and out_path.exists():
                manifest_rows.append({
                    "endpoint_slug": spec.slug,
                    "animal": animal,
                    "status": "skipped_existing",
                    "n_rows": 0,
                    "n_sentinel": 0,
                    "output_path": str(out_path),
                    "wall_time_s": 0.0,
                })
                continue
            t1 = time.monotonic()
            try:
                rows = _dispatch_materializer(
                    spec, animal, animal_info, session_scalars, resolver,
                )
            except Exception as exc:
                wall = time.monotonic() - t1
                print(f"  {spec.slug}: ERROR ({type(exc).__name__}: {exc})")
                manifest_rows.append({
                    "endpoint_slug": spec.slug,
                    "animal": animal,
                    "status": f"error: {type(exc).__name__}: {exc}",
                    "n_rows": 0,
                    "n_sentinel": 0,
                    "output_path": str(out_path),
                    "wall_time_s": float(wall),
                })
                continue
            if rows is None:
                manifest_rows.append({
                    "endpoint_slug": spec.slug,
                    "animal": animal,
                    "status": "skipped_commit_C",
                    "n_rows": 0,
                    "n_sentinel": 0,
                    "output_path": "",
                    "wall_time_s": 0.0,
                })
                continue
            n_rows = _write_parquet(rows, out_path)
            n_sentinel = sum(1 for r in rows if r["is_sentinel"])
            wall = time.monotonic() - t1
            manifest_rows.append({
                "endpoint_slug": spec.slug,
                "animal": animal,
                "status": "success",
                "n_rows": int(n_rows),
                "n_sentinel": int(n_sentinel),
                "output_path": str(out_path),
                "wall_time_s": round(wall, 3),
            })

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(args.manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(MANIFEST_COLUMNS))
        w.writeheader()
        for row in manifest_rows:
            w.writerow(row)

    n_success = sum(1 for r in manifest_rows if r["status"] == "success")
    n_skip = sum(1 for r in manifest_rows if r["status"].startswith("skipped"))
    n_error = sum(1 for r in manifest_rows if r["status"].startswith("error"))
    print()
    print(f"Manifest: {args.manifest}")
    print(f"  success: {n_success}")
    print(f"  skipped: {n_skip}")
    print(f"  errors:  {n_error}")
    return 0 if n_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
