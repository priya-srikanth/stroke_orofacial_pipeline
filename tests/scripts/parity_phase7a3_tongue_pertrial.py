r"""Phase 7a.3 V3 parity harness — legacy CSV/NPZ vs consolidated outputs, 14 sessions.

Modelled on ``tests/scripts/parity_phase7a_interpolation.py``: same scope-filter
(animals.yaml session windows), same exit-code legend, same ``by_status`` /
``ParityResult`` shape — extended per-cell because each session has 4
comparators (Cells 33/36/39/42).

Usage::

    python tests/scripts/parity_phase7a3_tongue_pertrial.py \
        --mode {default, legacy_approximate} \
        --sessions auto \
        --atol 1e-6

    # one-off:
    python tests/scripts/parity_phase7a3_tongue_pertrial.py \
        --mode legacy_approximate --animal PS46 --date 20250307

Modes:

- ``default`` runs the consolidated module with V3-locked knobs from
  ``configs/defaults.yaml``. Cohort outputs are emit-confirmation only —
  the comparators run regardless, but mismatches do not fail because the
  V3 knob changes (windows, MIN_PEAK_Y_ABS, MIN_FINITE_SAMPLES_PER_LICK,
  bout_max_ili=300) are intentional deviations from legacy.
- ``legacy_approximate`` overrides V3 knobs to legacy-faithful values and
  re-emits to a TEMP output_root (Option O1). Comparators run with
  ``atol=1e-6``; mismatches DO fail (this is the parity gate).

Knob overrides for legacy_approximate (per kickoff §4 + C5.2 per-cell
schema 2026-04-28):

WINDOW knobs (single-value, applied at the tongue_pertrial root):

    | knob path                                  | default     | override         |
    |--------------------------------------------|-------------|------------------|
    | tongue_pertrial.lick12_detect_win_ms       | [70, 3000]  | [70, 2000]       |
    | tongue_pertrial.lick_count_detect_win_ms   | [70, 8000]  | [0, 8000]        |
    | tongue_pertrial.lick_count_apply_win_ms    | [70, 5000]  | [0, 5000]        |
    | tongue_pertrial.lick_count_bin_win_ms      | [70, 5070]  | [0, 5000]        |
    | tongue_pertrial.licking_dyn_apply_win_ms   | [70, 5000]  | [0, 2500]        |
    | tongue_pertrial.angle_detect_win_ms        | [70, 8000]  | [70, 3000]       |

PER-CELL knobs (C5.2 — legacy had per-cell-different values for these,
which the shared detector + bout dicts can't represent. The harness sets
overrides via ``detector_per_cell:`` / ``bout_per_cell:``):

    cell33: legacy MIN_PEAK_Y_ABS=20 (pre-existing) + MIN_FINITE absent.
            override: {"min_finite_samples_per_lick": 1}.
    cell36: legacy MIN_FINITE=5 (pre-existing) + MIN_PEAK_Y absent.
            override: {"min_peak_y_abs": 0.0}.
    cell39: both absent in legacy.
            override: {"min_peak_y_abs": 0.0,
                       "min_finite_samples_per_lick": 1}.
    cell42: both absent in legacy + bout_max_ili=400.
            detector override: {"min_peak_y_abs": 0.0,
                                "min_finite_samples_per_lick": 1};
            bout override: {"max_ili_ms": 400.0}.
    cell50: per-trial scalars are NEW V3 features; no legacy parity.
            empty override.

The "no filter" override values are 5b.3a per Task 5b instructions:
``min_peak_y_abs=0.0`` makes the gate ``abs(y_peak) < 0.0`` always-False
(legacy didn't filter on this); ``min_finite_samples_per_lick=1`` makes
the gate ``n_finite < 1`` always-False (any detected peak has its center
sample finite, so n_finite >= 1).

Exit codes (inherit 7a.2 harness):

    0 — all compared sessions within atol
    1 — at least one comparator returned status="fail"
    2 — (reserved; 7a.3 has no stub state)
    3 — every session skip_missing (MICROSCOPE unreachable)
    4 — scope filter rejected all sessions (config error)

Cell 50 visual gate is **DEFERRED** in this harness (per kickoff §5b.7);
followup phase will compare consolidated angle outputs against legacy
``angle_phase_exploratory`` figures. Numerical parity on Cells 33/36/39/42
is the blocking gate for the 7a.3 PR.
"""
from __future__ import annotations

import argparse
import ast
import copy
import datetime as dt
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# --- Constants (mirror 7a.2 harness) -------------------------------------

ATOL_DEFAULT = 1e-6

MICROSCOPE_ROOT = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
    r"\DeepLabCut\O2_analysis"
)

INTERP_VERSION = "v5p3"
CAM = "cam2"
CENTER_MODE = "centered_spout_midpoint"

# 14 parity sessions per interpolation-strategy.md §6 (mirror of 7a.2).
PARITY_SESSIONS_PRIMARY = [
    ("PS46", dt.date(2025, 3, 7)),  ("PS46", dt.date(2025, 3, 10)), ("PS46", dt.date(2025, 3, 13)),
    ("PS54", dt.date(2025, 5, 6)),  ("PS54", dt.date(2025, 5, 9)),  ("PS54", dt.date(2025, 5, 12)),
    ("PS55", dt.date(2025, 5, 1)),  ("PS55", dt.date(2025, 5, 4)),  ("PS55", dt.date(2025, 5, 7)),
]
PARITY_SESSIONS_STRESS = [
    ("PS51", dt.date(2025, 4, 30)),
    ("PS54", dt.date(2025, 5, 1)),
    ("PS55", dt.date(2025, 5, 2)),
]
PARITY_SESSIONS_LATE = [
    ("PS54", dt.date(2025, 6, 7)),
    ("PS55", dt.date(2025, 6, 7)),
]
PARITY_SESSIONS_14 = (
    PARITY_SESSIONS_PRIMARY + PARITY_SESSIONS_STRESS + PARITY_SESSIONS_LATE
)

# legacy_approximate knob overrides (per kickoff §4 + C5.2 per-cell schema
# 2026-04-28). Window knobs are single-valued at the tongue_pertrial root;
# detector + bout filters are per-cell because legacy had per-cell-different
# values that the shared dicts can't represent.
LEGACY_APPROXIMATE_OVERRIDES: dict = {
    "lick12_detect_win_ms": [70, 2000],
    "lick_count_detect_win_ms": [0, 8000],
    "lick_count_apply_win_ms": [0, 5000],
    "lick_count_bin_win_ms": [0, 5000],
    "licking_dyn_apply_win_ms": [0, 2500],
    "angle_detect_win_ms": [70, 3000],
    "detector_per_cell": {
        # 5b.3a: "no filter" sentinel values rather than a skip-filter flag.
        # Equivalent semantics, zero module changes.
        #
        # C5.5 (2026-04-29): legacy Cell 33 has strict-no-fall-run rejection
        # (cell33.py:351-353), but Cells 36/39/42 always append peaks
        # regardless of fall validation. ``accept_peaks_without_fall_run``
        # set per-cell to flip the strictness for legacy_approximate.
        #
        # Cell 33 legacy: MIN_PEAK_Y_ABS=20 (pre-existing) → keep V3 default
        #   of 20.0. MIN_FINITE_SAMPLES_PER_LICK absent → override to 1.
        #   DO_SMOOTH_Y = False in legacy (V3 default True) → override.
        #   Strict-no-fall-run rejection: Cell 33 has it → keep default
        #   (accept_peaks_without_fall_run=False).
        "cell33": {
            "min_finite_samples_per_lick": 1,
            "do_smooth_y_for_detection": False,
        },
        # Cell 36 legacy: MIN_FINITE=5 (pre-existing) → keep V3 default of 5.
        #   MIN_PEAK_Y_ABS absent → override to 0.0.
        #   DO_SMOOTH_DETECT = False in legacy (V3 default True) → override.
        #   Cell 36 always appends peaks → set accept_peaks_without_fall_run.
        "cell36": {
            "min_peak_y_abs": 0.0,
            "do_smooth_y_for_detection": False,
            "accept_peaks_without_fall_run": True,
        },
        # Cell 39 legacy: both filters absent → override both to "no filter".
        #   DO_SMOOTH_Y = False in legacy (V3 default True) → override.
        #   Cell 39 always appends peaks → set accept_peaks_without_fall_run.
        "cell39": {
            "min_peak_y_abs": 0.0,
            "min_finite_samples_per_lick": 1,
            "do_smooth_y_for_detection": False,
            "accept_peaks_without_fall_run": True,
        },
        # Cell 42 legacy: both filters absent → override both.
        #   DO_SMOOTH_Y = False in legacy (V3 default True) → override.
        #   Cell 42 always appends peaks → set accept_peaks_without_fall_run.
        "cell42": {
            "min_peak_y_abs": 0.0,
            "min_finite_samples_per_lick": 1,
            "do_smooth_y_for_detection": False,
            "accept_peaks_without_fall_run": True,
        },
        # Cell 50 per-trial scalars are NEW V3 features (no legacy parity);
        # cell50 keeps V3 default detector behavior (including smoothing ON,
        # which matches legacy DO_SMOOTH_Y_FOR_DETECTION=True).
        "cell50": {},
    },
    "bout_per_cell": {
        # Cell 42 legacy: bout.max_ili=400 (V3 unified to 300).
        "cell42": {"max_ili_ms": 400.0},
        # Other cells use the V3 default (300); no override needed.
        "cell33": {},
        "cell36": {},
        "cell39": {},
        "cell50": {},
    },
}


# --- Dataclasses ---------------------------------------------------------


@dataclass
class CellComparison:
    """One per-cell comparator outcome for a (animal, date)."""

    cell: str   # "33" / "36" / "39" / "42"
    status: str  # "pass" / "fail" / "skip_missing" / "skip_no_legacy"
    max_abs_delta: float | None = None
    n_compared: int = 0
    note: str = ""


@dataclass
class SessionParityResult:
    """One (animal, date) outcome — wraps 4 per-cell comparators."""

    animal: str
    date: dt.date
    overall: str  # "pass" / "fail" / "skip_missing" / "skip_scope"
    cells: list[CellComparison] = field(default_factory=list)
    note: str = ""


# --- Scope filter (mirror 7a.2) ------------------------------------------


def load_scope(animals_yaml_path: Path) -> dict[str, tuple[dt.date, dt.date]]:
    with open(animals_yaml_path) as f:
        animals = yaml.safe_load(f)
    out: dict[str, tuple[dt.date, dt.date]] = {}
    for animal, blob in animals.items():
        scope = blob.get("sessions") or {}
        start = scope.get("start")
        end = scope.get("end")
        if isinstance(start, str):
            start = dt.date.fromisoformat(start)
        if isinstance(end, str):
            end = dt.date.fromisoformat(end)
        if start is not None and end is not None:
            out[animal] = (start, end)
    return out


def is_in_scope(
    animal: str, date: dt.date, scope: dict[str, tuple[dt.date, dt.date]],
) -> bool:
    if animal not in scope:
        return False
    start, end = scope[animal]
    return start <= date <= end


# --- Params builder ------------------------------------------------------


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursive deep merge of nested dicts."""
    out = copy.deepcopy(base)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def build_params(mode: str) -> dict:
    """Return defaults.yaml dict with mode-specific knob overrides applied."""
    from stroke_orofacial.config_loader import load_defaults

    params = load_defaults()
    if mode == "default":
        return params
    if mode == "legacy_approximate":
        tp = params["dlc_kinematics"]["tongue_pertrial"]
        params["dlc_kinematics"]["tongue_pertrial"] = _deep_merge(
            tp, LEGACY_APPROXIMATE_OVERRIDES,
        )
        return params
    raise ValueError(f"Unknown mode {mode!r}")


# --- Resolvers (canonical inputs + temp outputs) -------------------------


class _HarnessResolver:
    """Wrap a canonical PathResolver, redirect ONLY the 7a.3 output paths.

    The legacy_approximate emit needs to:
      - Read 7a.2 tongue parquet, centered_spout_midpoint parquet, licks NPZ,
        and alignment template from the CANONICAL MICROSCOPE paths.
      - Write the 7a.3 outputs (angle parquet, traces parquet, endpoints
        JSON) to a TEMP path so the canonical default-mode outputs aren't
        clobbered (Option O1 per Task 5b).

    A single PathResolver(output_root=temp) redirects pipeline_outputs(...)
    for both reads and writes (since interpolated_trace + centered_spout_midpoint
    both go through pipeline_outputs("dlc_analysis")). This wrapper inverts
    that: every method delegates to the canonical resolver UNLESS it's one
    of the three 7a.3 output resolvers, in which case the temp root is
    used.
    """

    def __init__(self, canonical, temp_output_root: Path) -> None:
        self._canonical = canonical
        self._temp = temp_output_root

    def __getattr__(self, name: str):
        # Delegate any unrecognised attribute to the canonical resolver.
        return getattr(self._canonical, name)

    def tongue_pertrial_angle_parquet(
        self, animal: str, date: dt.date,
    ) -> Path:
        date_str = date.strftime("%Y%m%d")
        out = (
            self._temp / "dlc_kinematics" / "features" / "tongue"
            / animal / f"{date_str}.parquet"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_pertrial_licking_dynamics_traces_parquet(
        self, animal: str, date: dt.date,
    ) -> Path:
        date_str = date.strftime("%Y%m%d")
        out = (
            self._temp / "dlc_kinematics" / "licking_dynamics" / "traces"
            / animal / f"{date_str}.parquet"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_pertrial_endpoints_json(
        self, animal: str, date: dt.date,
    ) -> Path:
        date_str = date.strftime("%Y%m%d")
        out = (
            self._temp / "dlc_kinematics" / "endpoints"
            / animal / f"{date_str}.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out


def _build_resolver(mode: str, emit_root: Path) -> object:
    """Return a resolver that reads canonical inputs + writes per-mode outputs.

    For ``default`` mode: ``emit_root`` is the canonical pipeline outputs root,
    so we can use a real ``PathResolver()`` (no override needed). For
    ``legacy_approximate`` mode: ``emit_root`` is the temp dir; we wrap a
    canonical resolver with :class:`_HarnessResolver` so inputs still come
    from MICROSCOPE.
    """
    from stroke_orofacial.paths import PathResolver

    canonical = PathResolver()
    if mode == "legacy_approximate":
        return _HarnessResolver(canonical, emit_root)
    return canonical


# --- Emitter -------------------------------------------------------------


def _emit_session(
    animal: str, date: dt.date, mode: str, output_root: Path,
) -> tuple[dict[str, Path], list]:
    """Emit consolidated outputs for one session.

    Returns ``(paths_dict, trial_events)`` where trial_events is the
    list returned by the auto-derive (used by comparators to re-key
    legacy per-side trial_index → consolidated chronological-across-sides
    trial_index per Option α 2026-04-28).
    """
    from stroke_orofacial.animals import get_animal
    from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
        _derive_trial_events_from_spout_behavior,
        build_tongue_pertrial,
    )
    from stroke_orofacial.manifest import build_manifest

    resolver = _build_resolver(mode, output_root)
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.kinematics.tongue_pertrial",
    )
    trial_events = _derive_trial_events_from_spout_behavior(
        animal=animal, date=date, resolver=resolver, manifest=manifest,
    )
    params = build_params(mode)
    paths = build_tongue_pertrial(
        manifest=manifest, resolver=resolver,
        trial_events=trial_events, params=params,
        overwrite="force", animal_info=animal_info,
    )
    return paths, trial_events


# --- Legacy readers ------------------------------------------------------


def _legacy_animal_dir(animal: str) -> Path:
    return (
        MICROSCOPE_ROOT / animal / f"{animal}_tongue_kinematics"
        / "kinematics_figures" / CENTER_MODE
    )


def _filter_rows_by_date(df: pd.DataFrame, date: dt.date) -> pd.DataFrame:
    """Filter pertrial-CSV rows to ``date`` (column is ``date`` as YYYYMMDD str)."""
    date_str = date.strftime("%Y%m%d")
    return df[df["date"].astype(str) == date_str].reset_index(drop=True)


def _load_legacy_lick12_csv(animal: str, date: dt.date) -> pd.DataFrame:
    """Cell 33 per-trial CSV.

    Path: ``…/lick_metrics/firstlick_metrics/{animal}_cam2_lick1lick2_pertrial_v5p3.csv``.
    Multi-session aggregate; filtered by ``date`` here.
    """
    path = (
        _legacy_animal_dir(animal) / "lick_metrics" / "firstlick_metrics"
        / f"{animal}_{CAM}_lick1lick2_pertrial_{INTERP_VERSION}.csv"
    )
    if not path.exists():
        raise FileNotFoundError(f"Legacy Cell 33 CSV not found: {path}")
    df = pd.read_csv(path)
    return _filter_rows_by_date(df, date)


def _load_legacy_peak_velocity_npz(animal: str, date: dt.date) -> dict:
    """Cell 36 NPZ.

    Path: ``…/velocity_metrics/{animal}_cam2_peakvel_first5_pertrial_lickresolved_BOTHAGG_v5p3.npz``.
    Returns the per-session subset of trial_meta + vy_peaks_bylick + vxy_peaks_bylick.
    """
    path = (
        _legacy_animal_dir(animal) / "velocity_metrics"
        / (
            f"{animal}_{CAM}_peakvel_first5_pertrial_lickresolved_BOTHAGG_"
            f"{INTERP_VERSION}.npz"
        )
    )
    if not path.exists():
        raise FileNotFoundError(f"Legacy Cell 36 NPZ not found: {path}")
    data = np.load(path, allow_pickle=True)
    trial_meta = data["trial_meta"]  # object array of dicts
    vy = data["vy_peaks_bylick"]      # (n_trials_total, 5)
    vxy = data["vxy_peaks_bylick"]    # (n_trials_total, 5)
    date_str = date.strftime("%Y%m%d")
    keep = np.array(
        [str(m.get("date")) == date_str for m in trial_meta],
        dtype=bool,
    )
    return {
        "trial_meta": [trial_meta[i] for i in np.where(keep)[0]],
        "vy_peaks_bylick": vy[keep, :],
        "vxy_peaks_bylick": vxy[keep, :],
    }


def _load_legacy_n_licks_csv(animal: str, date: dt.date) -> pd.DataFrame:
    """Cell 39 per-trial CSV.

    Filename embeds DATE_START-DATE_END; we glob and pick the file whose
    range covers ``date``.
    """
    fig_dir = (
        _legacy_animal_dir(animal) / "lick_metrics" / "licks_per_trial"
    )
    if not fig_dir.exists():
        raise FileNotFoundError(f"Legacy Cell 39 dir not found: {fig_dir}")
    candidates = sorted(fig_dir.glob(
        f"{animal}_{CAM}_licksPerTrial_pertrial_*-*_{INTERP_VERSION}.csv"
    ))
    if not candidates:
        raise FileNotFoundError(
            f"No Cell 39 pertrial CSV for {animal} in {fig_dir}",
        )
    chosen = _pick_csv_covering_date(candidates, date)
    if chosen is None:
        raise FileNotFoundError(
            f"No Cell 39 pertrial CSV covers date {date} in {fig_dir}; "
            f"candidates: {[c.name for c in candidates]}",
        )
    df = pd.read_csv(chosen)
    return _filter_rows_by_date(df, date)


def _load_legacy_licking_dyn_csv(animal: str, date: dt.date) -> pd.DataFrame:
    """Cell 42 per-session × side traces CSV.

    Filename embeds ``minTrialsPerBin{N}_{DATE_START}-{DATE_END}_{INTERP_VERSION}.csv``;
    legacy default ``MIN_TRIALS_PER_BIN=3``. Glob for that and pick the
    file whose date range covers ``date``.
    """
    fig_dir = _legacy_animal_dir(animal) / "lick_metrics" / "lick_rate"
    if not fig_dir.exists():
        raise FileNotFoundError(f"Legacy Cell 42 dir not found: {fig_dir}")
    candidates = sorted(fig_dir.glob(
        f"{animal}_{CAM}_ILIwithinBout_perSessionTraces_minTrialsPerBin3_*-*_"
        f"{INTERP_VERSION}.csv"
    ))
    if not candidates:
        raise FileNotFoundError(
            f"No Cell 42 perSessionTraces CSV (minTrialsPerBin3) for "
            f"{animal} in {fig_dir}",
        )
    chosen = _pick_csv_covering_date(candidates, date)
    if chosen is None:
        raise FileNotFoundError(
            f"No Cell 42 perSessionTraces CSV covers date {date} in {fig_dir}; "
            f"candidates: {[c.name for c in candidates]}",
        )
    df = pd.read_csv(chosen)
    return _filter_rows_by_date(df, date)


def _pick_csv_covering_date(candidates: list[Path], date: dt.date) -> Path | None:
    """Pick the CSV whose embedded date range covers ``date``.

    Filenames look like ``..._YYYYMMDD-YYYYMMDD_v5p3.csv``. Parse the range
    from the stem; pick the first match (typically the most-recent run).
    """
    target = date.strftime("%Y%m%d")
    for c in sorted(candidates, key=lambda p: p.name, reverse=True):
        stem = c.stem
        # Find a YYYYMMDD-YYYYMMDD substring
        for token in stem.split("_"):
            if "-" in token and len(token) == 17:
                try:
                    lo_str, hi_str = token.split("-")
                    if len(lo_str) == 8 and len(hi_str) == 8:
                        if lo_str <= target <= hi_str:
                            return c
                except ValueError:
                    continue
    return None


# --- Consolidated reader -------------------------------------------------


def _load_consolidated(
    animal: str, date: dt.date, mode: str, output_root: Path,
) -> dict:
    """Load all three 7a.3 V3 outputs for one (animal, date).

    Uses the same resolver shape as :func:`_emit_session` so the temp-rooted
    legacy_approximate outputs are read back from the right place.
    """
    import json

    resolver = _build_resolver(mode, output_root)
    ep_path = resolver.tongue_pertrial_endpoints_json(animal, date)
    traces_path = resolver.tongue_pertrial_licking_dynamics_traces_parquet(
        animal, date,
    )
    angle_path = resolver.tongue_pertrial_angle_parquet(animal, date)
    if not ep_path.exists():
        raise FileNotFoundError(f"Consolidated endpoints JSON missing: {ep_path}")
    if not traces_path.exists():
        raise FileNotFoundError(f"Consolidated traces parquet missing: {traces_path}")
    with open(ep_path) as f:
        endpoints = json.load(f)
    traces = pd.read_parquet(traces_path)
    return {
        "endpoints": endpoints,
        "traces": traces,
        "angle_path": angle_path,  # for visual gate (deferred)
    }


# --- Re-keying: legacy (side, trial_index) → consolidated chronological ---


def _per_side_chronological_indices(
    sides: list[str], trial_events: list,
) -> dict[str, list[int]]:
    """For each side, list the consolidated indices in chronological order.

    Legacy CSV's ``trial_index`` enumerates within each side independently
    (chronological per-side). Consolidated ``trial_indices`` is unique-per-row
    chronological-across-sides (Option α). The k-th L-trial in legacy
    (side="L", trial_index=k) corresponds to the k-th element of
    ``out["L"]`` here — which is the consolidated index.
    """
    pos_by_side: dict[str, list[tuple[int, int]]] = {"L": [], "R": []}
    for k, ev in enumerate(trial_events):
        if ev.side in pos_by_side:
            pos_by_side[ev.side].append((ev.tone_frame_idx, k))
    # trial_events is already sorted by tone_frame_idx (per
    # _derive_trial_events_from_spout_behavior contract), so the
    # per-side ordering here is implicitly chronological.
    return {
        side: [k for _, k in sorted(items)]  # explicit sort for safety
        for side, items in pos_by_side.items()
    }


def _legacy_to_consolidated_indices(
    legacy_df: pd.DataFrame, per_side_chrono: dict[str, list[int]],
) -> tuple[np.ndarray, np.ndarray]:
    """Map legacy per-side trial_index → consolidated chronological index.

    Returns parallel arrays ``(legacy_row_idx, consolidated_idx)``. Rows
    where the legacy (side, trial_index) doesn't fit the per-side
    chronological list (e.g. legacy detected more trials than the
    auto-derive in our temp output_root — should be rare since both
    consume the same upstream NPZ) are silently dropped.
    """
    legacy_rows: list[int] = []
    cons_rows: list[int] = []
    for legacy_row_idx, row in legacy_df.iterrows():
        side = str(row["side"])
        ti = int(row["trial_index"])
        chrono_list = per_side_chrono.get(side, [])
        if 0 <= ti < len(chrono_list):
            legacy_rows.append(int(legacy_row_idx))
            cons_rows.append(chrono_list[ti])
    return np.asarray(legacy_rows, dtype=np.int64), np.asarray(cons_rows, dtype=np.int64)


# --- Comparators ---------------------------------------------------------


def _max_abs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """NaN-aware max|a − b|; both NaN at same index counts as zero delta."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        return float("inf")
    both_nan = np.isnan(a) & np.isnan(b)
    diff = np.abs(a - b)
    diff[both_nan] = 0.0
    if np.all(np.isnan(diff)):
        return 0.0  # vacuous: nothing finite to compare
    return float(np.nanmax(diff))


def _compare_cell33(
    legacy_df: pd.DataFrame, consolidated: dict,
    per_side_chrono: dict[str, list[int]], atol: float,
) -> CellComparison:
    if legacy_df.empty:
        return CellComparison("33", "skip_no_legacy", note="empty legacy slice")
    legacy_rows, cons_rows = _legacy_to_consolidated_indices(
        legacy_df, per_side_chrono,
    )
    if len(legacy_rows) == 0:
        return CellComparison("33", "skip_no_legacy", note="re-key matched 0 rows")
    metrics = consolidated["endpoints"]["tongue"]["lick1_lick2_metrics"]
    cols = (
        "lick1_y_peak", "lick1_t_peak_ms", "lick1_x_at_ypeak",
        "lick2_y_peak", "lick2_t_peak_ms", "lick2_x_at_ypeak",
    )
    max_d = 0.0
    for col in cols:
        legacy_v = legacy_df[col].to_numpy(dtype=np.float64)[legacy_rows]
        cons_v = np.asarray(metrics[col], dtype=np.float64)[cons_rows]
        d = _max_abs_delta(legacy_v, cons_v)
        if d > max_d:
            max_d = d
    status = "pass" if max_d <= atol else "fail"
    return CellComparison(
        "33", status, max_abs_delta=max_d, n_compared=len(legacy_rows),
        note=f"6 cols × {len(legacy_rows)} trials",
    )


def _compare_cell36(
    legacy_npz: dict, consolidated: dict,
    per_side_chrono: dict[str, list[int]], atol: float,
) -> CellComparison:
    trial_meta = legacy_npz.get("trial_meta", [])
    vy_legacy = legacy_npz.get("vy_peaks_bylick")
    vxy_legacy = legacy_npz.get("vxy_peaks_bylick")
    if not trial_meta or vy_legacy is None or len(vy_legacy) == 0:
        return CellComparison("36", "skip_no_legacy", note="empty legacy slice")
    metrics = consolidated["endpoints"]["tongue"]["peak_velocity_per_lick"]
    vy_cons = np.asarray(metrics["vy_peaks_bylick"], dtype=np.float64)
    vxy_cons = np.asarray(metrics["vxy_peaks_bylick"], dtype=np.float64)

    # Re-key: legacy trial_meta has (side, trial_index) per row.
    legacy_rows: list[int] = []
    cons_rows: list[int] = []
    for i, m in enumerate(trial_meta):
        side = str(m.get("side"))
        ti = int(m.get("trial_index", -1))
        chrono_list = per_side_chrono.get(side, [])
        if 0 <= ti < len(chrono_list):
            legacy_rows.append(i)
            cons_rows.append(chrono_list[ti])
    if not legacy_rows:
        return CellComparison("36", "skip_no_legacy", note="re-key matched 0 rows")
    legacy_idx = np.asarray(legacy_rows, dtype=np.int64)
    cons_idx = np.asarray(cons_rows, dtype=np.int64)

    d_vy = _max_abs_delta(vy_legacy[legacy_idx, :], vy_cons[cons_idx, :])
    d_vxy = _max_abs_delta(vxy_legacy[legacy_idx, :], vxy_cons[cons_idx, :])
    max_d = max(d_vy, d_vxy)
    status = "pass" if max_d <= atol else "fail"
    return CellComparison(
        "36", status, max_abs_delta=max_d, n_compared=len(legacy_rows),
        note=f"vy + vxy, shape ({len(legacy_rows)}, 5)",
    )


def _compare_cell39(
    legacy_df: pd.DataFrame, consolidated: dict,
    per_side_chrono: dict[str, list[int]], atol: float,
) -> CellComparison:
    if legacy_df.empty:
        return CellComparison("39", "skip_no_legacy", note="empty legacy slice")
    legacy_rows, cons_rows = _legacy_to_consolidated_indices(
        legacy_df, per_side_chrono,
    )
    if len(legacy_rows) == 0:
        return CellComparison("39", "skip_no_legacy", note="re-key matched 0 rows")
    family = consolidated["endpoints"]["tongue"]["n_licks_family"]
    # Map legacy → consolidated column names
    pairs = [
        ("n_licks_in_countwin", np.asarray(family["n_licks"], dtype=np.float64)),
        ("n_leftward_dirwin", np.asarray(family["n_left"], dtype=np.float64)),
        ("n_rightward_dirwin", np.asarray(family["n_right"], dtype=np.float64)),
        ("has_ge10_in_countwin",
         np.asarray(family["lick_ge10"], dtype=np.float64)),
    ]
    max_d = 0.0
    for legacy_col, cons_arr in pairs:
        if legacy_col not in legacy_df.columns:
            continue
        legacy_v = legacy_df[legacy_col].to_numpy(dtype=np.float64)[legacy_rows]
        cons_v = cons_arr[cons_rows]
        d = _max_abs_delta(legacy_v, cons_v)
        if d > max_d:
            max_d = d
    # Per-bin counts: legacy has licks_bin{i}_count cols; consolidated
    # has n_licks_per_bin (list[int][5]).
    n_licks_per_bin = np.asarray(family["n_licks_per_bin"], dtype=np.float64)
    if n_licks_per_bin.ndim == 2:
        for bi in range(min(n_licks_per_bin.shape[1], 5)):
            legacy_col = f"licks_bin{bi}_count"
            if legacy_col not in legacy_df.columns:
                continue
            legacy_v = legacy_df[legacy_col].to_numpy(dtype=np.float64)[legacy_rows]
            cons_v = n_licks_per_bin[cons_rows, bi]
            d = _max_abs_delta(legacy_v, cons_v)
            if d > max_d:
                max_d = d
    status = "pass" if max_d <= atol else "fail"
    return CellComparison(
        "39", status, max_abs_delta=max_d, n_compared=len(legacy_rows),
        note=f"4 scalars + 5 bins × {len(legacy_rows)} trials",
    )


def _parse_list_cell(s) -> np.ndarray:
    """Parse a list-shaped CSV cell back to ndarray (legacy emits via ``list.tolist()``)."""
    if isinstance(s, (list, np.ndarray)):
        return np.asarray(s, dtype=np.float64)
    if isinstance(s, str):
        try:
            return np.asarray(ast.literal_eval(s), dtype=np.float64)
        except (ValueError, SyntaxError):
            return np.array([], dtype=np.float64)
    return np.array([], dtype=np.float64)


def _compare_cell42(
    legacy_df: pd.DataFrame, consolidated: dict, atol: float,
) -> CellComparison:
    """Compare per-session × side traces (4 columns at 20 ms bins).

    Legacy CSV stores traces as Python-list strings (from ``.tolist()``)
    in cells; we parse via :func:`ast.literal_eval`. Consolidated traces
    parquet has columns ``timebin_ms``, ``side``, ``lick_rate_per_t``,
    ``ili_within_bout_rate_per_t``, ``p_lick_per_t``, ``p_within_bout_per_t``.

    Cross-comparator field map (kickoff §4):

    | legacy col          | consolidated col              |
    |---------------------|-------------------------------|
    | lick_rate_mean_hz   | lick_rate_per_t               |
    | bout_rate_mean_hz   | ili_within_bout_rate_per_t    |
    | p_lick              | p_lick_per_t                  |
    | bout_state_frac     | p_within_bout_per_t           |
    """
    if legacy_df.empty:
        return CellComparison("42", "skip_no_legacy", note="empty legacy slice")
    traces = consolidated["traces"]
    pairs = [
        ("lick_rate_mean_hz", "lick_rate_per_t"),
        ("bout_rate_mean_hz", "ili_within_bout_rate_per_t"),
        ("p_lick", "p_lick_per_t"),
        ("bout_state_frac", "p_within_bout_per_t"),
    ]
    max_d = 0.0
    n_compared = 0
    for _, lg_row in legacy_df.iterrows():
        side = str(lg_row["side"])
        cons_side = traces[traces["side"] == side]
        if cons_side.empty:
            continue
        cons_t = cons_side["timebin_ms"].to_numpy(dtype=np.float64)
        legacy_t = _parse_list_cell(lg_row.get("t_ms"))
        if legacy_t.size == 0 or cons_t.size == 0:
            continue
        # Common timebin overlap (legacy may use a different apply window
        # in default mode; legacy_approximate forces alignment).
        common, idx_lg, idx_cs = np.intersect1d(
            legacy_t, cons_t, assume_unique=False, return_indices=True,
        )
        if common.size == 0:
            continue
        for legacy_col, cons_col in pairs:
            legacy_v = _parse_list_cell(lg_row.get(legacy_col))
            cons_v = cons_side[cons_col].to_numpy(dtype=np.float64)
            if legacy_v.size != legacy_t.size:
                continue
            d = _max_abs_delta(legacy_v[idx_lg], cons_v[idx_cs])
            if d > max_d:
                max_d = d
            n_compared += int(common.size)
    if n_compared == 0:
        return CellComparison(
            "42", "skip_no_legacy", note="no overlapping timebins after parse",
        )
    status = "pass" if max_d <= atol else "fail"
    return CellComparison(
        "42", status, max_abs_delta=max_d, n_compared=n_compared,
        note=f"4 traces × {n_compared} bins",
    )


# --- Per-session driver --------------------------------------------------


def parity_one_session(
    animal: str, date: dt.date, mode: str, atol: float, output_root: Path,
) -> SessionParityResult:
    """Emit + compare one session in ``mode`` under ``output_root``."""
    try:
        _, trial_events = _emit_session(animal, date, mode, output_root)
    except FileNotFoundError as e:
        return SessionParityResult(
            animal, date, overall="skip_missing", note=f"emit: {e}",
        )

    try:
        consolidated = _load_consolidated(animal, date, mode, output_root)
    except FileNotFoundError as e:
        return SessionParityResult(
            animal, date, overall="skip_missing",
            note=f"consolidated load: {e}",
        )

    per_side_chrono = _per_side_chronological_indices(
        sides=consolidated["endpoints"]["sides"], trial_events=trial_events,
    )

    cells: list[CellComparison] = []
    # Cell 33
    try:
        legacy_33 = _load_legacy_lick12_csv(animal, date)
        cells.append(_compare_cell33(legacy_33, consolidated, per_side_chrono, atol))
    except FileNotFoundError as e:
        cells.append(CellComparison("33", "skip_missing", note=str(e)))
    # Cell 36
    try:
        legacy_36 = _load_legacy_peak_velocity_npz(animal, date)
        cells.append(_compare_cell36(legacy_36, consolidated, per_side_chrono, atol))
    except FileNotFoundError as e:
        cells.append(CellComparison("36", "skip_missing", note=str(e)))
    # Cell 39
    try:
        legacy_39 = _load_legacy_n_licks_csv(animal, date)
        cells.append(_compare_cell39(legacy_39, consolidated, per_side_chrono, atol))
    except FileNotFoundError as e:
        cells.append(CellComparison("39", "skip_missing", note=str(e)))
    # Cell 42
    try:
        legacy_42 = _load_legacy_licking_dyn_csv(animal, date)
        cells.append(_compare_cell42(legacy_42, consolidated, atol))
    except FileNotFoundError as e:
        cells.append(CellComparison("42", "skip_missing", note=str(e)))

    statuses = {c.status for c in cells}
    if "fail" in statuses:
        overall = "fail"
    elif statuses == {"skip_missing"} or statuses == {"skip_no_legacy"}:
        overall = "skip_missing"
    else:
        overall = "pass"
    return SessionParityResult(animal, date, overall=overall, cells=cells)


# --- main ----------------------------------------------------------------


def _parse_yyyymmdd(s: str) -> dt.date:
    return dt.date.fromisoformat(f"{s[:4]}-{s[4:6]}-{s[6:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("default", "legacy_approximate"),
                    default="legacy_approximate")
    ap.add_argument("--sessions", choices=("auto",))
    ap.add_argument("--animal")
    ap.add_argument("--date", type=_parse_yyyymmdd)
    ap.add_argument("--atol", type=float, default=ATOL_DEFAULT)
    ap.add_argument("--animals-yaml", default="configs/animals.yaml")
    ap.add_argument(
        "--output-root", default=None,
        help=(
            "Base output_root for emit. Default: temp dir for "
            "legacy_approximate (Option O1 — non-canonical, deleted "
            "after run), real PathResolver for default mode."
        ),
    )
    args = ap.parse_args()

    # Determine session list.
    if args.sessions == "auto":
        todo = list(PARITY_SESSIONS_14)
    elif args.animal and args.date:
        todo = [(args.animal, args.date)]
    else:
        print(
            "error: provide --animal --date or --sessions auto",
            file=sys.stderr,
        )
        return 4

    # Scope filter.
    scope = load_scope(Path(args.animals_yaml))
    out_results: list[SessionParityResult] = []
    cleaned: list[tuple[str, dt.date]] = []
    for animal, date in todo:
        if not is_in_scope(animal, date, scope):
            out_results.append(SessionParityResult(
                animal, date, overall="skip_scope",
                note=f"out of sessions.{{start,end}} for {animal}",
            ))
            continue
        cleaned.append((animal, date))

    # Determine emit root.
    if args.output_root is not None:
        emit_root = Path(args.output_root)
        emit_root.mkdir(parents=True, exist_ok=True)
        tmp_ctx = None
    elif args.mode == "legacy_approximate":
        # Option O1: temp dir, deleted on exit.
        tmp_ctx = tempfile.TemporaryDirectory(prefix="parity_7a3_legacy_approx_")
        emit_root = Path(tmp_ctx.name)
    else:
        # Default mode: real canonical pipeline outputs root.
        from stroke_orofacial.paths import PathResolver
        emit_root = PathResolver().root("microscope_pipeline_outputs")
        tmp_ctx = None

    try:
        for animal, date in cleaned:
            print(
                f"[parity] {animal} {date.isoformat()} mode={args.mode} ...",
                flush=True,
            )
            result = parity_one_session(
                animal, date, args.mode, args.atol, emit_root,
            )
            out_results.append(result)
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()

    # Summary by_status (overall) + per-cell.
    by_status: dict[str, int] = {}
    by_cell_status: dict[str, dict[str, int]] = {}
    for r in out_results:
        by_status[r.overall] = by_status.get(r.overall, 0) + 1
        for c in r.cells:
            d = by_cell_status.setdefault(c.cell, {})
            d[c.status] = d.get(c.status, 0) + 1

    print(f"\nParity summary (mode={args.mode}, atol={args.atol:.1e}):")
    print(f"  by_status (overall): {by_status}")
    for cell in sorted(by_cell_status):
        print(f"  cell {cell}: {by_cell_status[cell]}")
    print()
    for r in out_results:
        if r.overall == "skip_scope":
            continue
        print(f"  {r.animal} {r.date.isoformat()} {r.overall:14s} {r.note}")
        for c in r.cells:
            d_str = (
                f"{c.max_abs_delta:.3e}" if c.max_abs_delta is not None else "—"
            )
            print(
                f"    cell {c.cell}: {c.status:14s}  "
                f"max|Δ|={d_str}  n={c.n_compared}  {c.note}",
            )

    print()
    print("[Cell 50 visual gate] DEFERRED — render not implemented in this "
          "harness; followup phase will compare consolidated angle outputs "
          "against legacy angle_phase_exploratory figures.")

    # Exit code.
    if by_status.get("fail", 0) > 0:
        return 1
    if (
        not any(r.overall == "pass" for r in out_results)
        and by_status.get("skip_scope", 0) == len(out_results)
    ):
        return 4
    if (
        by_status.get("skip_missing", 0) > 0
        and by_status.get("pass", 0) == 0
    ):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
