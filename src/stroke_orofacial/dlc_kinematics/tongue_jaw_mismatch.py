"""Phase 7a.5 — Tongue-jaw mismatch trial classifier + plotter.

Identifies trials where the mouse shows post-cue jaw movement WITHOUT
licking. Scientific rationale (Priya, 2026-04-30): post-stroke
(bilateral) lack of licking is NOT due to perceptual or motivational
deficits — the dissociation isolates the deficit to **tongue motor
control specifically**. Mismatch trials are the primary positive
evidence for this interpretation, not just a QC gate.

Ported from canonical tongue notebook
(``20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb``,
SHA256 ``ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643``,
Cell 53 classifier + Cell 55 plotter — vendored byte-identically at
``docs/legacy_snippets/tongue_jaw_mismatch.py``).

Hybrid B1.5 sub-variant (locked decision #1, 2026-04-30): two modules,
single phase. The jaw per-trial scalars Cell 53 emits inline are
extracted to a separate
:mod:`stroke_orofacial.dlc_kinematics.jaw_pertrial` module (Phase 7a.5
Task 4); this module CONSUMES that module's output and adds the cross-
bodypart classifier + 4 plot families.

Inputs
------
- 7a.2 jaw interpolated_traces parquet (``y_final``)
- 7a.2 tongue interpolated_traces parquet (``x_final``, ``y_final``)
- 7a.5 jaw_pertrial endpoints JSON (per-trial ``jaw_pass_qc``)
- :class:`SessionManifest` + ``trial_events`` (auto-derivable from
  spout_behavior via the 7a.3 V3 helper)

Outputs (atomic)
----------------
- ``<outputs>/dlc_kinematics/tongue_jaw_mismatch/candidate_trials/<animal>/<YYYYMMDD>.parquet``
  (per-session candidate trials, ~21 cols + file-level metadata; locked
  decision #3 — per-session cadence, NOT legacy per-mouse aggregated).
- ``<outputs>/dlc_kinematics/tongue_jaw_mismatch/within_session/<animal>/<YYYYMMDD>/``
  (within-session PNGs: individual_trials_2col + session_overlay_grid_4x2).
- ``<outputs>/dlc_kinematics/tongue_jaw_mismatch/cross_session/<animal>/``
  (cross-session PNGs: cross_session_overlay + cross_session_binned).

Predicate (verbatim from Cell 53):

    candidate_no_lick_with_jaw_move = quiet_tongue_pass AND jaw_pass_qc

- ``quiet_tongue_pass``: zero peaks via the Cell 33 dy/dt slope detector
  applied to the ``(70, 5000)`` ms post-reward window. Detector is
  invoked with mismatch-specific knobs (no smoothing, no MIN_FINITE
  filter, accept-no-fall like Cells 36/39/42 — see
  :func:`_build_tongue_detector_params`). Note: this re-runs the
  detector locally on raw traces; it does NOT consume the 7a.3 V3
  endpoints JSON's ``n_licks`` count, which is computed for a different
  window + with V3-strict detector knobs.
- ``jaw_pass_qc``: pulled from
  :class:`stroke_orofacial.dlc_kinematics.JawPertrialResult` (the 7a.5
  jaw_pertrial module computes this via per-trial baseline + threshold
  + sustained-density check). Trials are co-indexed by
  ``(trial_index, side)`` between the jaw_pertrial JSON and the
  ``trial_events`` sequence.

Schema deviations from legacy 37-col CSV (deliberate, locked at Task 4):

- Per-row schema reduces to ~21 cols (per-session parquet metadata
  carries the invariants legacy repeated per-row: window knobs,
  threshold knobs, direction_mode, NPZ provenance paths).
- ``jaw_thresh_abs`` carries the *applied* threshold value (legacy's
  ``jaw_thresh_px_used`` numeric) — collapses legacy's redundant dual-
  float convention.
- New categorical ``jaw_thresh_px_used`` column with values
  ``"sd_scaled"`` / ``"px_floor"`` / ``"none"`` (no legacy counterpart;
  derived from ``jaw_pertrial`` output).
"""

from __future__ import annotations

# matplotlib backend MUST be set before any pyplot import (headless
# cohort renders + deterministic CI). Same precedent as tongue_visual.py.
import matplotlib

matplotlib.use("Agg")

import datetime  # noqa: E402  (ordering after backend setup is intentional)
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Literal, Sequence  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from stroke_orofacial.animals import AnimalInfo, get_animal  # noqa: E402
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_kinematics._detector import (  # noqa: E402
    _slope_detect_lick_peaks,
)
from stroke_orofacial.dlc_kinematics.jaw_pertrial import (  # noqa: E402
    JAW_PERTRIAL_VERSION,
    build_jaw_pertrial,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    TrialEvent,
    _derive_trial_events_from_spout_behavior,
)
from stroke_orofacial.manifest import SessionManifest, build_manifest  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402

# Version stamped into every emitted parquet/PNG. Bumping requires a
# DECISIONS entry + 14-session legacy_approximate parity re-run.
TONGUE_JAW_MISMATCH_VERSION: str = "v7a.5"
INTERPOLATION_VERSION: str = "v5p3"

# Cohort-default jaw direction mode. Per locked decision #5 (kickoff
# 2026-04-30), per-mouse override infrastructure is dropped; the
# cohort-default ``"above_or_below"`` is the only supported mode and is
# recorded in file-level metadata for forensic completeness.
_JAW_DIRECTION_MODE: str = "above_or_below"


# ============================================================================
# Public dataclass
# ============================================================================


@dataclass(frozen=True)
class TongueJawMismatchResult:
    """In-memory container for the candidate-trials emit (pre-write).

    Mirrors the :class:`JawPertrialResult` shape: ``trials`` is the per-
    trial DataFrame (~21 cols); ``metadata`` is the file-level metadata
    dict embedded into the parquet's schema metadata at write time.
    """

    trials: pd.DataFrame
    metadata: dict[str, Any]


# ============================================================================
# Public API — classifier
# ============================================================================


def classify_tongue_jaw_mismatch(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: Sequence[TrialEvent] | None,
    params: dict[str, Any] | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
    animal_info: AnimalInfo | None = None,
) -> Path | None:
    """Classify mismatch trials for one session and write the parquet atomically.

    Returns the emitted parquet path, or ``None`` if ``overwrite="skip"``
    AND the target file already exists. Internally:

    1. Resolve / build ``trial_events`` (auto-derive if ``None``).
    2. Build (or reuse-on-skip) the jaw_pertrial endpoints JSON for this
       session — the classifier consumes ``jaw_pass_qc`` from there.
    3. Run the local Cell 33 detector on the tongue trace inside the
       quiet-tongue window per trial.
    4. Combine per the predicate; emit the candidate-trials parquet.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )
    if animal_info is None:
        animal_info = get_animal(manifest.animal)
    if manifest.excluded:
        return None
    if params is None:
        params = load_defaults()

    out_path = resolver.tongue_jaw_mismatch_candidate_trials_parquet(
        manifest.animal, manifest.date,
    )
    if overwrite == "skip" and out_path.exists():
        return out_path

    if trial_events is None:
        trial_events = _derive_trial_events_from_spout_behavior(
            animal=manifest.animal, date=manifest.date,
            resolver=resolver, manifest=manifest,
        )

    # Ensure the upstream jaw_pertrial JSON exists (idempotent: skip-and-
    # exists short-circuits without recompute). Use ``overwrite=skip`` so
    # repeated cohort runs don't churn the upstream emit; production
    # callers running the upstream first see this as a no-op.
    jaw_json_path = build_jaw_pertrial(
        manifest=manifest, resolver=resolver, trial_events=trial_events,
        params=params, overwrite="skip", animal_info=animal_info,
    )
    if jaw_json_path is None:
        # Manifest excluded — already short-circuited above; defensive.
        return None
    jaw_endpoints = json.loads(jaw_json_path.read_text(encoding="utf-8"))

    result = _build_classifier_result(
        manifest=manifest, resolver=resolver,
        trial_events=trial_events, jaw_endpoints=jaw_endpoints,
        params=params, animal_info=animal_info,
    )
    _write_candidate_trials_parquet_atomic(out_path, result.trials, result.metadata)
    return out_path


def classify_tongue_jaw_mismatch_by_animal_date(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    trial_events: Sequence[TrialEvent] | None = None,
    **kwargs: Any,
) -> Path | None:
    """Convenience wrapper. Auto-derives trial_events if ``None``."""
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.kinematics.tongue_jaw_mismatch",
    )
    kwargs.setdefault("animal_info", animal_info)
    return classify_tongue_jaw_mismatch(
        manifest=manifest, resolver=resolver,
        trial_events=trial_events, **kwargs,
    )


# ============================================================================
# Public API — plotters
# ============================================================================


def render_within_session_figures(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    params: dict[str, Any] | None = None,
    *,
    candidate_trials_df: pd.DataFrame | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, list[Path]]:
    """Render the 2 within-session figure families for one ``(animal, date)``.

    Returns a dict keyed by family name with the list of emitted PNG paths:

    - ``"individual_trials"``: 1 PNG per session (legacy
      ``{mouse}_{date}_individualTrials2col_candidateVsNoncandidate_jawBaselineSub.png``).
      Two-column layout: candidates left, non-candidates right.
    - ``"session_overlay_grid"``: 1 PNG per session (legacy
      ``{mouse}_{date}_sessionOverlayGrid4x2_jawBaselineSub.png``).
      4×2 grid (overlay-cand / overlay-noncand / mean±SEM-cand / mean±SEM-noncand
      × L / R sides).

    The renderer creates the per-session output directory; this function
    is idempotent under ``overwrite="skip"`` (returns existing paths if
    all family files exist).
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )
    if params is None:
        params = load_defaults()

    within_session_dir = resolver.tongue_jaw_mismatch_within_session_dir(
        animal, date,
    )
    individual_path = within_session_dir / (
        f"{animal}_{date.strftime('%Y%m%d')}"
        f"_individualTrials2col_candidateVsNoncandidate_jawBaselineSub.png"
    )
    grid_path = within_session_dir / (
        f"{animal}_{date.strftime('%Y%m%d')}"
        f"_sessionOverlayGrid4x2_jawBaselineSub.png"
    )
    out: dict[str, list[Path]] = {
        "individual_trials": [individual_path],
        "session_overlay_grid": [grid_path],
    }
    if (
        overwrite == "skip"
        and individual_path.exists()
        and grid_path.exists()
    ):
        return out

    if candidate_trials_df is None:
        ct_path = resolver.tongue_jaw_mismatch_candidate_trials_parquet(
            animal, date,
        )
        if not ct_path.exists():
            raise FileNotFoundError(
                f"candidate_trials parquet missing for {animal}/{date.isoformat()} "
                f"at {ct_path}. Run classify_tongue_jaw_mismatch first.",
            )
        candidate_trials_df = pd.read_parquet(ct_path)

    # Need traces for plotting — re-load both bodyparts from 7a.2 parquets.
    jaw_y, fps_jaw, n_frames_jaw = _load_bodypart_y_final(
        resolver, animal, date, bodypart="jaw",
    )
    tongue_y, _, _ = _load_bodypart_y_final(
        resolver, animal, date, bodypart="tongue",
    )

    plotter_cfg = params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]

    within_session_dir.mkdir(parents=True, exist_ok=True)

    if plotter_cfg["individual_trials"]["enabled"]:
        fig = _plot_individual_trials_2col(
            candidate_trials_df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=plotter_cfg, animal=animal, date=date,
        )
        _save_and_close(fig, individual_path, dpi=plotter_cfg["individual_trials"]["dpi"])

    if plotter_cfg["session_overlay_grid"]["enabled"]:
        fig = _plot_session_overlay_grid_4x2(
            candidate_trials_df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=plotter_cfg, animal=animal, date=date,
        )
        _save_and_close(fig, grid_path, dpi=plotter_cfg["individual_trials"]["dpi"])

    return out


def render_cross_session_figures(
    animal: str,
    resolver: PathResolver,
    params: dict[str, Any] | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
    animal_info: AnimalInfo | None = None,
) -> dict[str, Path]:
    """Render the 2 cross-session figure families for one mouse.

    Returns a dict keyed by family name with the emitted PNG path:

    - ``"cross_session_overlay"``: per-mouse, all sessions overlaid.
      Pre-stroke = grey, post-stroke = plasma colormap by relative day.
    - ``"cross_session_binned"``: per-mouse, day-binned by
      ``animal_info.bin_days`` (PS46-50: 2; PS51/54/55: 7 — sourced from
      ``configs/animals.yaml`` per the 7a.4 day-binned precedent).

    Reads all per-session candidate_trials parquets under
    ``<outputs>/dlc_kinematics/tongue_jaw_mismatch/candidate_trials/{animal}/``
    and the corresponding 7a.2 jaw + tongue traces. Sessions with
    missing traces are skipped with a console warning.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )
    if params is None:
        params = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)

    cross_dir = resolver.tongue_jaw_mismatch_cross_session_dir(animal)
    overlay_path = cross_dir / (
        f"{animal}_crossSessionOverlay2x2_jawBaselineSub.png"
    )
    binned_path = cross_dir / (
        f"{animal}_crossSessionBinned2x2_bins{animal_info.bin_days}"
        f"_jawBaselineSub.png"
    )
    out: dict[str, Path] = {
        "cross_session_overlay": overlay_path,
        "cross_session_binned": binned_path,
    }
    if (
        overwrite == "skip"
        and overlay_path.exists()
        and binned_path.exists()
    ):
        return out

    plotter_cfg = params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]

    sessions = _gather_sessions_for_animal(animal, resolver, animal_info)
    if not sessions:
        raise FileNotFoundError(
            f"No candidate_trials parquets found for {animal} under "
            f"{resolver.pipeline_outputs('dlc_kinematics') / 'tongue_jaw_mismatch' / 'candidate_trials' / animal}. "
            f"Run classify_tongue_jaw_mismatch on individual sessions first.",
        )

    cross_dir.mkdir(parents=True, exist_ok=True)

    if plotter_cfg["cross_session_overlay"]["enabled"]:
        fig = _plot_cross_session_overlay(
            sessions, animal=animal, plotter_cfg=plotter_cfg,
        )
        _save_and_close(fig, overlay_path, dpi=plotter_cfg["individual_trials"]["dpi"])

    if plotter_cfg["cross_session_binned"]["enabled"]:
        fig = _plot_cross_session_binned(
            sessions, animal=animal, bin_days=animal_info.bin_days,
            plotter_cfg=plotter_cfg,
        )
        _save_and_close(fig, binned_path, dpi=plotter_cfg["individual_trials"]["dpi"])

    return out


# ============================================================================
# Core compute (private)
# ============================================================================


def _build_classifier_result(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: Sequence[TrialEvent],
    jaw_endpoints: dict[str, Any],
    params: dict[str, Any],
    animal_info: AnimalInfo,
) -> TongueJawMismatchResult:
    """Pure-compute path: build the per-trial DataFrame + metadata dict."""
    cfg = params["dlc_kinematics"]["tongue_jaw_mismatch"]
    classifier_cfg = cfg["classifier"]
    quiet_win_ms = tuple(classifier_cfg["quiet_tongue_win_ms"])
    detector_params = _build_tongue_detector_params(classifier_cfg["tongue_detector"])

    jp_params = params["dlc_kinematics"]["jaw_pertrial"]

    # Load tongue trace for the local detector. Jaw is read by the
    # plotter on demand; classifier doesn't need it.
    tongue_y, fps, n_frames = _load_bodypart_y_final(
        resolver, manifest.animal, manifest.date, bodypart="tongue",
    )
    tongue_x_path = resolver.interpolated_trace(
        bodypart="tongue", animal=manifest.animal, date=manifest.date,
    )
    tongue_x = pd.read_parquet(tongue_x_path, columns=["x_final"])[
        "x_final"
    ].to_numpy(dtype=np.float64, copy=False)

    # Per-trial detector run (count tongue licks in the quiet window).
    rows: list[dict[str, Any]] = []
    jaw_pertrial_block = jaw_endpoints["jaw_pertrial"]
    jaw_trial_indices = jaw_endpoints["trial_indices"]
    jaw_sides = jaw_endpoints["sides"]
    jaw_lookup = {
        (int(ti), str(sd)): k
        for k, (ti, sd) in enumerate(zip(jaw_trial_indices, jaw_sides))
    }

    rel_day = animal_info.day_relative_to_stroke(manifest.date)
    for ev in trial_events:
        # Tongue snippet around reward, generous enough to span the
        # quiet window.
        pre_f = abs(_ms_to_frames(min(0.0, quiet_win_ms[0]), fps))
        post_f = abs(_ms_to_frames(max(0.0, quiet_win_ms[1]), fps))
        t_ms_local = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))
        y_w = _snippet(tongue_y, ev.reward_frame_idx, pre_f, post_f, n_frames)
        x_w = _snippet(tongue_x, ev.reward_frame_idx, pre_f, post_f, n_frames)

        peaks = _slope_detect_lick_peaks(
            y_t=y_w, x_t=x_w, t_ms=t_ms_local, fps=fps,
            detect_win_ms=quiet_win_ms, detector_params=detector_params,
        )
        n_licks = int(len(peaks))
        peak_times_ms = [float(t) for t in peaks.peak_times_ms]
        quiet_tongue_pass = bool(n_licks == 0)

        # Jaw side: pull from jaw_pertrial endpoints by (trial_index, side).
        jaw_idx = jaw_lookup.get((int(ev.trial_index), str(ev.side)))
        if jaw_idx is None:
            raise KeyError(
                f"jaw_pertrial endpoints missing trial "
                f"({ev.trial_index}, {ev.side!r}) for "
                f"{manifest.animal}/{manifest.date.isoformat()}. "
                f"Trial-events drift between modules — re-run "
                f"build_jaw_pertrial with the same trial_events first.",
            )
        jp = {
            k: v[jaw_idx] for k, v in jaw_pertrial_block.items()
        }
        jaw_pass_qc = bool(jp["jaw_pass_qc"])

        candidate = bool(quiet_tongue_pass and jaw_pass_qc)

        rows.append(dict(
            mouse=manifest.animal,
            date=manifest.date.isoformat(),
            rel_day=int(rel_day),
            trial_index=int(ev.trial_index),
            side=str(ev.side),
            reward_frame_idx=int(ev.reward_frame_idx),
            fps=float(fps),
            n_licks_in_quiet_win=int(n_licks),
            tongue_peak_times_ms=peak_times_ms,
            quiet_tongue_pass=bool(quiet_tongue_pass),
            jaw_baseline_mean=jp["jaw_baseline_mean"],
            jaw_baseline_sd=jp["jaw_baseline_sd"],
            jaw_peak_pos_deflection=jp["jaw_peak_pos_deflection"],
            jaw_peak_neg_deflection=jp["jaw_peak_neg_deflection"],
            jaw_peak_abs_deflection=jp["jaw_peak_abs_deflection"],
            jaw_peak_selected_deflection=jp["jaw_peak_selected_deflection"],
            jaw_thresh_abs=jp["jaw_thresh_abs"],
            jaw_thresh_px_used=str(jp["jaw_thresh_px_used"]),
            jaw_n_frames_over_thresh=int(jp["jaw_n_frames_over_thresh"]),
            jaw_pass_qc=bool(jaw_pass_qc),
            candidate_no_lick_with_jaw_move=bool(candidate),
        ))

    df = pd.DataFrame(rows)

    metadata = {
        "schema_version": TONGUE_JAW_MISMATCH_VERSION,
        "feature_extraction_version": TONGUE_JAW_MISMATCH_VERSION,
        "interpolation_version": INTERPOLATION_VERSION,
        "jaw_pertrial_version": JAW_PERTRIAL_VERSION,
        "animal": manifest.animal,
        "date": manifest.date.isoformat(),
        "fps": float(fps),
        "n_frames": int(n_frames),
        "n_trials": int(len(df)),
        "quiet_tongue_win_ms_lo": float(quiet_win_ms[0]),
        "quiet_tongue_win_ms_hi": float(quiet_win_ms[1]),
        "max_licks_for_quiet": 0,
        "jaw_baseline_win_ms_lo": float(jp_params["baseline_win_ms"][0]),
        "jaw_baseline_win_ms_hi": float(jp_params["baseline_win_ms"][1]),
        "jaw_detect_win_ms_lo": float(jp_params["detect_win_ms"][0]),
        "jaw_detect_win_ms_hi": float(jp_params["detect_win_ms"][1]),
        "jaw_thresh_sd_multiplier": float(
            jp_params["deflection_threshold_sd_multiplier"],
        ),
        "jaw_thresh_min_px": float(jp_params["deflection_threshold_min_px"]),
        "jaw_sustained_density_threshold": float(
            jp_params["sustained_density_threshold"],
        ),
        "jaw_sustained_window_n_frames": int(
            jp_params["sustained_window_n_frames"],
        ),
        "jaw_direction_mode": _JAW_DIRECTION_MODE,
        "tongue_detector_slope_thr_px_per_s": float(
            classifier_cfg["tongue_detector"]["slope_thr_px_per_s"],
        ),
        "tongue_detector_rise_min_ms": float(
            classifier_cfg["tongue_detector"]["rise_min_ms"],
        ),
        "tongue_detector_fall_min_ms": float(
            classifier_cfg["tongue_detector"]["fall_min_ms"],
        ),
        "tongue_detector_min_peak_y_abs": float(
            classifier_cfg["tongue_detector"]["min_peak_y_abs"],
        ),
        "tongue_detector_peak_pad_ms": float(
            classifier_cfg["tongue_detector"]["peak_pad_ms"],
        ),
        "tongue_detector_do_smooth_y_for_detection": bool(
            classifier_cfg["tongue_detector"]["do_smooth_y_for_detection"],
        ),
    }
    return TongueJawMismatchResult(trials=df, metadata=metadata)


def _build_tongue_detector_params(tongue_detector_cfg: dict[str, Any]) -> dict[str, Any]:
    """Compose a :func:`_slope_detect_lick_peaks`-compatible params dict.

    The YAML ``tongue_jaw_mismatch.classifier.tongue_detector`` block carries
    the 6 user-tunable knobs. The remaining V3 detector knobs are pinned
    at mismatch-specific invariants (per kickoff §3a + Task 5):

    - ``min_finite_samples_per_lick = 0`` — Cell 53 had no MIN_FINITE filter.
    - ``smooth_ms_detect_y = 0.0`` — irrelevant since smoothing is disabled.
    - ``strict_no_fallback = True`` — Cell 53 sets this constant.
    - ``accept_peaks_without_fall_run = True`` — Cell 53 finds the fall but
      does NOT reject peaks lacking one (matches Cells 36/39/42 legacy
      behavior, not Cell 33 strict). The relevant Cell 53 lines (vendored
      at ``docs/legacy_snippets/tongue_jaw_mismatch.py``):

          end_idx = j_peak
          if fall_min_f > 1:
              f0, f1 = _first_run_from(fall_mask, fall_min_f, start=j_peak)
              if f0 is not None:
                  end_idx = max(end_idx, f1 - 1)
          ypk = float(yseg0[j_peak])
          if (MIN_PEAK_Y_ABS is not None) and (abs(ypk) >= MIN_PEAK_Y_ABS):
              ...peaks.append(...)

      acceptance is purely on ``MIN_PEAK_Y_ABS``; the fall-run search only
      advances ``end_idx`` for the next-rise scan.
    """
    return {
        **tongue_detector_cfg,
        "min_finite_samples_per_lick": 0,
        "smooth_ms_detect_y": 0.0,
        "strict_no_fallback": True,
        "accept_peaks_without_fall_run": True,
    }


# ============================================================================
# Loaders + numeric helpers
# ============================================================================


def _load_bodypart_y_final(
    resolver: PathResolver, animal: str, date: datetime.date,
    *, bodypart: Literal["tongue", "jaw"],
) -> tuple[np.ndarray, float, int]:
    """Read ``y_final`` + ``fps`` + ``n_frames`` from a 7a.2 interpolated_traces parquet."""
    path = resolver.interpolated_trace(
        bodypart=bodypart, animal=animal, date=date,
    )
    if not path.exists():
        raise FileNotFoundError(
            f"7a.2 {bodypart} interpolated_traces parquet missing for "
            f"{animal}/{date.isoformat()} at {path}. "
            f"Run build_interpolated_trace first.",
        )
    df = pd.read_parquet(path, columns=["y_final"])
    schema = pq.read_schema(path)
    raw_meta = schema.metadata or {}
    fps = float(raw_meta[b"fps"].decode("utf-8"))
    n_frames = int(raw_meta[b"n_frames"].decode("utf-8"))
    y_final = df["y_final"].to_numpy(dtype=np.float64, copy=False)
    return y_final, fps, n_frames


def _ms_to_frames(ms: float, fps: float) -> int:
    return int(np.round((ms / 1000.0) * fps))


def _snippet(
    arr: np.ndarray, center_fr: int, pre_f: int, post_f: int, n_frames: int,
) -> np.ndarray:
    """Per-trial slice with NaN padding when reward is near a session edge.

    Mirrors Cell 53's ``_snippet`` byte-for-byte. Identical to the
    :func:`stroke_orofacial.dlc_kinematics.jaw_pertrial._snippet` helper;
    duplicated locally to keep the cross-module import surface minimal.
    """
    T = pre_f + post_f + 1
    lo = center_fr - pre_f
    hi = center_fr + post_f
    out = np.full(T, np.nan, dtype=float)
    src_lo = max(lo, 0)
    src_hi = min(hi, n_frames - 1)
    if src_hi < src_lo:
        return out
    dst_lo = src_lo - lo
    dst_hi = dst_lo + (src_hi - src_lo)
    out[dst_lo:dst_hi + 1] = arr[src_lo:src_hi + 1]
    return out


def _gather_sessions_for_animal(
    animal: str, resolver: PathResolver, animal_info: AnimalInfo,
) -> list[dict[str, Any]]:
    """Discover all per-session candidate_trials parquets for ``animal``,
    pair with their tongue + jaw traces, and decorate with rel_day.

    Returns a list of dicts (one per eligible session) with keys
    ``date``, ``rel_day``, ``trials_df``, ``jaw_y``, ``tongue_y``,
    ``fps``, ``n_frames``. Sessions with missing traces are skipped
    with a console warning."""
    candidate_dir = (
        resolver.pipeline_outputs("dlc_kinematics")
        / "tongue_jaw_mismatch" / "candidate_trials" / animal
    )
    if not candidate_dir.exists():
        return []
    parquets = sorted(candidate_dir.glob("*.parquet"))
    out: list[dict[str, Any]] = []
    for p in parquets:
        m = re.match(r"(\d{8})\.parquet$", p.name)
        if m is None:
            continue
        d = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        try:
            jaw_y, fps, n_frames = _load_bodypart_y_final(
                resolver, animal, d, bodypart="jaw",
            )
            tongue_y, _, _ = _load_bodypart_y_final(
                resolver, animal, d, bodypart="tongue",
            )
        except FileNotFoundError as e:
            print(f"[warn] {animal}/{d.isoformat()}: skipping ({e})")
            continue
        df = pd.read_parquet(p)
        rel_day = animal_info.day_relative_to_stroke(d)
        out.append(dict(
            date=d, rel_day=int(rel_day),
            trials_df=df, jaw_y=jaw_y, tongue_y=tongue_y,
            fps=fps, n_frames=n_frames,
        ))
    return out


# ============================================================================
# Atomic writers
# ============================================================================


def _write_candidate_trials_parquet_atomic(
    path: Path, df: pd.DataFrame, metadata: dict[str, Any],
) -> None:
    """Write the candidate-trials parquet atomically (temp + os.replace).

    Mirrors :func:`stroke_orofacial.dlc_kinematics._writers._write_traces_parquet_atomic`
    pattern (4-line helper vendored locally per Task 5 kickoff).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta_bytes = {
        k.encode("utf-8"): str(v).encode("utf-8")
        for k, v in metadata.items()
    }
    existing = table.schema.metadata or {}
    merged = {**{bytes(k): bytes(v) for k, v in existing.items()}, **meta_bytes}
    table = table.replace_schema_metadata(merged)
    tmp_path = path.with_name(path.name + ".tmp")
    pq.write_table(table, str(tmp_path), compression="snappy")
    os.replace(tmp_path, path)


def _save_and_close(fig: Figure, path: Path, *, dpi: float) -> None:
    """Save a figure atomically (temp + replace) and close it.

    Mirrors :func:`stroke_orofacial.dlc_kinematics.tongue_visual._save_and_close`
    — the temp filename keeps the ``.png`` extension and adds a ``.tmp``
    middle segment so matplotlib's format-by-extension inference works.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp" + path.suffix)
    fig.savefig(tmp, dpi=float(dpi), bbox_inches="tight", format="png")
    plt.close(fig)
    tmp.replace(path)


# ============================================================================
# Plot families (4)
# ============================================================================


# Per-trial snippet window for plotting (legacy Cell 55 VIEW_WIN_MS).
_PLOT_VIEW_WIN_MS: tuple[float, float] = (-500.0, 5000.0)
_SIDE_COLORS: dict[str, str] = {"L": "dodgerblue", "R": "mediumvioletred"}
_REWARD_COLOR: str = "red"
_TONGUE_LS: str = ":"

# Phase 7a.5 C6.2 legacy axis-label parity (Priya 2026-05-01). Match
# Cell 55 ``_jaw_ylabel(mode="baseline_subtracted")`` → "Jaw Y - baseline (px)"
# verbatim. The C6.1 string "Jaw - base (px)" was a paraphrase; the new
# value matches legacy byte-for-byte.
_LEGACY_JAW_YLABEL: str = "Jaw Y - baseline (px)"
_LEGACY_TONGUE_YLABEL: str = "Tongue Y (px)"
_LEGACY_XLABEL: str = "Time relative to reward (ms)"


def _format_candidate_count_text(
    side: str, df_total: pd.DataFrame, df_candidates: pd.DataFrame,
) -> str:
    """Per-panel candidate sub-title text. Mirrors legacy Cell 55
    ``_format_candidate_count_text`` byte-for-byte (vendored at
    ``docs/legacy_snippets/tongue_jaw_mismatch.py:1074-1078``)."""
    n_total = int(np.sum(df_total["side"].astype(str) == side))
    n_cand = int(np.sum(df_candidates["side"].astype(str) == side))
    if n_total == 0:
        return ""
    return f"{side} candidate trials: {n_cand}/{n_total}"


def _format_noncandidate_count_text(
    side: str, df_total: pd.DataFrame, df_candidates: pd.DataFrame,
) -> str:
    """Per-panel non-candidate sub-title text. Legacy Cell 55
    ``_format_noncandidate_count_text``."""
    n_total = int(np.sum(df_total["side"].astype(str) == side))
    n_cand = int(np.sum(df_candidates["side"].astype(str) == side))
    n_non = n_total - n_cand
    if n_total == 0:
        return ""
    return f"{side} non-candidate trials: {n_non}/{n_total}"


def _build_plot_snippets(
    df: pd.DataFrame, jaw_y: np.ndarray, tongue_y: np.ndarray, fps: float,
    n_frames: int,
) -> list[dict[str, Any]]:
    """Per-row plot snippet builder. Returns a list aligned with ``df``."""
    pre_f = abs(_ms_to_frames(_PLOT_VIEW_WIN_MS[0], fps))
    post_f = abs(_ms_to_frames(_PLOT_VIEW_WIN_MS[1], fps))
    t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        ct = int(r["reward_frame_idx"])
        jaw_yw = _snippet(jaw_y, ct, pre_f, post_f, n_frames)
        tong_yw = _snippet(tongue_y, ct, pre_f, post_f, n_frames)
        baseline_mean = float(r["jaw_baseline_mean"]) if r["jaw_baseline_mean"] is not None else float("nan")
        if np.isfinite(baseline_mean):
            jaw_yw_bs = jaw_yw - baseline_mean
        else:
            jaw_yw_bs = np.full_like(jaw_yw, np.nan)
        rows.append(dict(
            t_ms=t_ms,
            jaw_y=jaw_yw_bs,
            tongue_y=tong_yw,
            side=str(r["side"]),
            candidate=bool(r["candidate_no_lick_with_jaw_move"]),
            trial_index=int(r["trial_index"]),
        ))
    return rows


# ---------- Range helpers (Phase 7a.5 C6.2 — legacy parity) ------------


def _percentile_cap_range(
    values: list[np.ndarray], *,
    pmax: float = 99.9, pmin: float | None = None, pad_frac: float = 0.05,
) -> tuple[float, float] | None:
    """Compute a padded data range with optional percentile capping.

    Mirrors legacy Cell 55's ``_limits_from_values`` mode="percentile_cap":
    cap the upper extreme at the ``pmax`` percentile (default 99.9), use
    the raw min if ``pmin`` is None (legacy default), then expand
    symmetrically by ``pad_frac`` of the range. Each input array
    contributes only its finite entries; arrays where everything is NaN
    are dropped.

    Returns ``None`` if no finite values exist across all inputs.
    """
    finite_chunks = [
        v[np.isfinite(v)] for v in values if np.any(np.isfinite(v))
    ]
    if not finite_chunks:
        return None
    cat = np.concatenate(finite_chunks)
    if cat.size == 0:
        return None
    if pmin is None:
        lo = float(np.nanmin(cat))
    else:
        lo = float(np.nanpercentile(cat, float(pmin)))
    hi = float(np.nanpercentile(cat, float(pmax)))
    if lo == hi:
        return lo - 1.0, hi + 1.0
    pad = (hi - lo) * float(pad_frac)
    return lo - pad, hi + pad


def _collect_overlay_arrays(
    rows_for_row: list[dict[str, Any]],
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Gather jaw + tongue per-trial arrays for the overlay-row Y-range compute."""
    jaw_collect: list[np.ndarray] = []
    tong_collect: list[np.ndarray] = []
    for s in rows_for_row:
        jaw_collect.append(s["jaw_y"])
        tong_collect.append(s["tongue_y"])
    return jaw_collect, tong_collect


def _collect_mean_sem_arrays(
    rows_for_row: list[dict[str, Any]],
    *,
    include_trials: bool = False,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Gather (mu ± sem) extremes per side group for the mean±SEM Y-range compute.

    Per-bodypart, twin-axis-independent: jaw range comes from jaw_mu±sem
    only; tongue range comes from tongue_mu±sem only. The natural visual
    offset between jaw and tongue traces emerges from the data
    distributions (per-bodypart auto-scale), not from any explicit
    hardcoded values.

    Phase 7a.5 C6.3 (Priya 2026-05-01): when ``include_trials=True``,
    individual trial trace values are concatenated alongside the
    (mu ± sem) extremes BEFORE the downstream percentile cap is applied.
    This matches legacy ``_limits_from_rows`` (vendored at
    ``docs/legacy_snippets/tongue_jaw_mismatch.py:946-961``), which always
    concatenates per-trial data across all rows. The default
    ``include_trials=False`` is a deliberate modern deviation: when
    ``show_trial_overlays`` is False, no trial lines are drawn so we
    compute bounds from mean-trace data only (avoids over-pessimistic
    axes caused by trials nobody is going to see). When
    ``show_trial_overlays`` is True, callers pass ``include_trials=True``
    so the rendered trial overlays are NOT clipped by the auto-scaled
    axis. The percentile-cap (``pmax=99.9``) downstream still keeps
    isolated outlier samples from blowing up the range.
    """
    jaw_collect: list[np.ndarray] = []
    tong_collect: list[np.ndarray] = []
    for side in ("L", "R"):
        sub = [r for r in rows_for_row if r["side"] == side]
        if not sub:
            continue
        jawM = np.vstack([s["jaw_y"] for s in sub])
        tongM = np.vstack([s["tongue_y"] for s in sub])
        mu_j, sem_j = _mean_sem(jawM)
        mu_t, sem_t = _mean_sem(tongM)
        jaw_collect.extend([mu_j - sem_j, mu_j + sem_j, mu_j])
        tong_collect.extend([mu_t - sem_t, mu_t + sem_t, mu_t])
        if include_trials:
            for s in sub:
                jaw_collect.append(np.asarray(s["jaw_y"], float))
                tong_collect.append(np.asarray(s["tongue_y"], float))
    return jaw_collect, tong_collect


def _collect_cross_session_arrays(
    panel_items: list[dict[str, Any]],
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Gather (mu ± sem) extremes from cross-session panel items."""
    jaw_collect: list[np.ndarray] = []
    tong_collect: list[np.ndarray] = []
    for it in panel_items:
        jaw_collect.extend([
            it["jaw_mu"] - it["jaw_sem"],
            it["jaw_mu"] + it["jaw_sem"],
            it["jaw_mu"],
        ])
        tong_collect.extend([
            it["tong_mu"] - it["tong_sem"],
            it["tong_mu"] + it["tong_sem"],
            it["tong_mu"],
        ])
    return jaw_collect, tong_collect


def _plot_individual_trials_2col(
    df: pd.DataFrame, jaw_y: np.ndarray, tongue_y: np.ndarray, fps: float,
    *, plotter_cfg: dict[str, Any], animal: str, date: datetime.date,
) -> Figure:
    """Two-column individual-trial figure: candidates left, non-candidates right.

    Phase 7a.5 C6.2 (Priya 2026-05-01) port-fidelity round: replicate
    legacy Cell 55 ``_plot_individual_two_col`` layout exactly.

    Layout (from vendored Cell 55):
    - figsize = ``(18, max(12, 1.8 * n_rows))`` — width 18 in, height
      grows with n_rows × ``ROW_HEIGHT=1.8``.
    - DPI = 200 (legacy ``FIG_DPI``).
    - ``tight_layout()`` (no rect arg).
    - Per-subplot title: ``fontsize=9, loc="left"``.
    - Column header: ``fontsize=12, fontweight="bold"``.
    - Y-axis labels use ``_LEGACY_JAW_YLABEL`` / ``_LEGACY_TONGUE_YLABEL``
      (no explicit fontsize → matplotlib default).

    Priya C6.1 ``sort_by_side`` is preserved as a per-column sort
    deviation from legacy (legacy sorts by ``jaw_abs`` desc; the modern
    convention sorts by ``(side, trial_index)``).
    """
    n_frames = int(len(jaw_y))
    rows = _build_plot_snippets(df, jaw_y, tongue_y, fps, n_frames)
    rows_cand = [r for r in rows if r["candidate"]]
    rows_non = [r for r in rows if not r["candidate"]]

    cfg = plotter_cfg["individual_trials"]
    if bool(cfg.get("sort_by_side", False)):
        def _side_then_trial(r: dict[str, Any]) -> tuple[int, int]:
            return (0 if r["side"] == "L" else 1, int(r["trial_index"]))
        rows_cand = sorted(rows_cand, key=_side_then_trial)
        rows_non = sorted(rows_non, key=_side_then_trial)

    n_rows = max(len(rows_cand), len(rows_non), 1)

    fig_w = float(cfg["figure_width_inches"])
    fig_h_min = float(cfg.get("figure_height_inches", 12.0))
    row_h = float(cfg.get("row_height_inches", 1.8))
    fig_h = max(fig_h_min, row_h * n_rows)
    fig, axes = plt.subplots(
        nrows=n_rows, ncols=2, figsize=(fig_w, fig_h), sharex=True, squeeze=False,
    )
    axes[0, 0].set_title("Candidate trials", fontsize=12, fontweight="bold")
    axes[0, 1].set_title("Non-candidate trials", fontsize=12, fontweight="bold")
    for cix, group in enumerate([rows_cand, rows_non]):
        for rix in range(n_rows):
            ax = axes[rix, cix]
            if rix >= len(group):
                ax.axis("off")
                continue
            row = group[rix]
            color = _SIDE_COLORS.get(row["side"], "k")
            ax.plot(row["t_ms"], row["jaw_y"], color=color, lw=1.4)
            ax.axvline(0, color=_REWARD_COLOR, linestyle=":", lw=1.0, alpha=0.8)
            ax.axhline(0, color="0.5", linestyle="--", lw=0.8, alpha=0.6)
            ax2 = ax.twinx()
            ax2.plot(row["t_ms"], row["tongue_y"], color=color, lw=1.0,
                     linestyle=_TONGUE_LS, alpha=0.95)
            ax.set_ylabel(_LEGACY_JAW_YLABEL, color=color)
            ax2.set_ylabel(_LEGACY_TONGUE_YLABEL, color=color)
            ax.tick_params(axis="y", labelcolor=color)
            ax2.tick_params(axis="y", labelcolor=color)
            ax.grid(True, alpha=0.2)
            grp = "candidate" if row["candidate"] else "non-candidate"
            ax.set_title(
                f"{grp} | {row['side']} trial {row['trial_index']}",
                fontsize=9, loc="left",
            )
    for cix in range(2):
        axes[-1, cix].set_xlabel(_LEGACY_XLABEL)
    fig.suptitle(
        f"{animal} {date.strftime('%Y%m%d')} | individual trials | "
        f"col1=candidate, col2=non-candidate",
        y=0.995,
    )
    fig.tight_layout()
    return fig


def _mean_sem(M: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """NaN-aware mean + SEM over rows (axis=0)."""
    mu = np.nanmean(M, axis=0)
    n_eff = np.sum(np.isfinite(M), axis=0)
    sd = np.nanstd(M, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        sem = sd / np.sqrt(np.maximum(1, n_eff))
    sem[n_eff < 2] = np.nan
    return mu, sem


def _plot_session_overlay_grid_4x2(
    df: pd.DataFrame, jaw_y: np.ndarray, tongue_y: np.ndarray, fps: float,
    *, plotter_cfg: dict[str, Any], animal: str, date: datetime.date,
) -> Figure:
    """4-row × 2-col grid: overlay-cand / overlay-noncand / mean±SEM-cand /
    mean±SEM-noncand × L / R sides.

    Phase 7a.5 C6.2 (Priya 2026-05-01) port-fidelity round: replicate
    legacy Cell 55 ``_plot_session_grid`` layout + Y-axis behavior.

    - **Fix 3 revised** (per-bodypart twin-axis auto-scale): each panel
      uses twin Y axes (jaw left, tongue right). Each axis auto-scales
      to its own bodypart's data using the same percentile-cap pipeline
      legacy uses (``_limits_from_rows`` mode "percentile_cap" with
      ``pmax=99.9``, ``pmin=None``, ``pad_frac=0.05``). Per-row shared-Y
      across L+R: row jaw range = padded percentile-cap union of (L jaw
      data, R jaw data). Per-bodypart independence is preserved by
      computing jaw and tongue ranges separately. The visual offset
      between jaw and tongue traces emerges naturally from the data
      distributions — NO hardcoded ranges.

    - **Fix 4** (faint trial overlays): when
      ``mean_sem_axis.show_trial_overlays`` is True, individual-trial
      lines are drawn underneath the mean±SEM band on the bottom two
      rows. Z-order: trial overlays first, then mean line, then SEM
      fill (matches legacy code order — note that visually the SEM fill
      ends up on top of the mean line because matplotlib renders later
      calls last; this is bit-equivalent to legacy's drawing order).

    - **Fix 5** (legacy sub-titles): per-panel title format matches
      legacy ``_format_candidate_count_text`` /
      ``_format_noncandidate_count_text`` — e.g.
      "overlay candidate | side=L\\nL candidate trials: 38/96".
    """
    n_frames = int(len(jaw_y))
    rows = _build_plot_snippets(df, jaw_y, tongue_y, fps, n_frames)

    cfg = plotter_cfg["session_overlay_grid"]
    shared_y = bool(cfg.get("shared_y_axis_per_plot_type_row", False))
    mean_sem_cfg = cfg.get("mean_sem_axis") or {}
    pad_frac = float(mean_sem_cfg.get("pad_fraction", 0.05))
    pmax = float(mean_sem_cfg.get("percentile_cap_max", 99.9))
    pmin_raw = mean_sem_cfg.get("percentile_cap_min", None)
    pmin = float(pmin_raw) if pmin_raw is not None else None
    show_overlays = bool(mean_sem_cfg.get("show_trial_overlays", True))
    overlay_jaw_alpha = float(mean_sem_cfg.get("trial_overlay_jaw_alpha", 0.08))
    overlay_tongue_alpha = float(mean_sem_cfg.get("trial_overlay_tongue_alpha", 0.04))
    overlay_jaw_lw = float(mean_sem_cfg.get("trial_overlay_jaw_linewidth", 0.8))
    overlay_tongue_lw = float(mean_sem_cfg.get("trial_overlay_tongue_linewidth", 0.7))

    # Legacy total/candidate dataframes for the sub-title helpers.
    df_total = df.copy()
    df_candidates = df[df["candidate_no_lick_with_jaw_move"]].copy()

    fig, axes = plt.subplots(
        nrows=4, ncols=2,
        figsize=(float(cfg["figure_width_inches"]), float(cfg["figure_height_inches"])),
        sharex=True,
    )
    fig.subplots_adjust(
        hspace=float(cfg.get("hspace", 0.38)),
        wspace=float(cfg.get("wspace", 0.22)),
    )
    row_specs = [
        ("overlay candidate",     True,  False),
        ("overlay non-candidate", False, False),
        ("mean±SEM candidate",    True,  True),
        ("mean±SEM non-candidate", False, True),
    ]
    for rix, (label, cand_flag, mean_sem) in enumerate(row_specs):
        rows_for_row = [r for r in rows if r["candidate"] == cand_flag]

        # Per-row shared-Y compute via percentile-cap. Each bodypart
        # auto-scales independently; the row range is the union of L+R.
        # C6.3: when faint trial overlays are drawn under the mean±SEM
        # band, include their values in the percentile-cap input so the
        # rendered trial lines aren't clipped by the auto-scaled axis.
        if shared_y:
            if mean_sem:
                jaw_arrs, tong_arrs = _collect_mean_sem_arrays(
                    rows_for_row, include_trials=show_overlays,
                )
            else:
                jaw_arrs, tong_arrs = _collect_overlay_arrays(rows_for_row)
            row_jaw_lim = _percentile_cap_range(
                jaw_arrs, pmax=pmax, pmin=pmin, pad_frac=pad_frac,
            )
            row_tong_lim = _percentile_cap_range(
                tong_arrs, pmax=pmax, pmin=pmin, pad_frac=pad_frac,
            )
        else:
            row_jaw_lim, row_tong_lim = None, None

        for cix, side in enumerate(["L", "R"]):
            ax = axes[rix, cix]
            ax2 = ax.twinx()
            sub = [r for r in rows_for_row if r["side"] == side]
            color = _SIDE_COLORS[side]

            # Legacy sub-title (Fix 5): "{row_label} | side={side}\n{count_text}".
            if cand_flag:
                count_text = _format_candidate_count_text(
                    side, df_total, df_candidates,
                )
            else:
                count_text = _format_noncandidate_count_text(
                    side, df_total, df_candidates,
                )
            panel_title = f"{label} | side={side}"
            if count_text:
                panel_title += f"\n{count_text}"
            ax.set_title(panel_title, fontsize=10)

            if not sub:
                ax.text(0.5, 0.5, "no trials", ha="center", va="center",
                        transform=ax.transAxes, fontsize=11, color="0.5")
                ax.set_xticks([])
                ax.set_yticks([])
                ax2.set_yticks([])
                continue
            t_ms = sub[0]["t_ms"]
            if mean_sem:
                # Z-order matches legacy code order: faint trials → mean line → SEM fill.
                if show_overlays:
                    for s in sub:
                        ax.plot(
                            s["t_ms"], s["jaw_y"],
                            color=color, lw=overlay_jaw_lw,
                            alpha=overlay_jaw_alpha, linestyle="-",
                        )
                        ax2.plot(
                            s["t_ms"], s["tongue_y"],
                            color=color, lw=overlay_tongue_lw,
                            alpha=overlay_tongue_alpha, linestyle=_TONGUE_LS,
                        )
                jawM = np.vstack([s["jaw_y"] for s in sub])
                tongM = np.vstack([s["tongue_y"] for s in sub])
                jaw_mu, jaw_sem = _mean_sem(jawM)
                tong_mu, tong_sem = _mean_sem(tongM)
                ax.plot(t_ms, jaw_mu, color=color, lw=2.0, alpha=0.95)
                ax2.plot(
                    t_ms, tong_mu, color=color, lw=1.5,
                    linestyle=_TONGUE_LS, alpha=0.95,
                )
                ok = np.isfinite(jaw_mu) & np.isfinite(jaw_sem)
                if np.any(ok):
                    ax.fill_between(
                        t_ms[ok], (jaw_mu - jaw_sem)[ok],
                        (jaw_mu + jaw_sem)[ok],
                        color=color, alpha=0.10, lw=0,
                    )
                okt = np.isfinite(tong_mu) & np.isfinite(tong_sem)
                if np.any(okt):
                    ax2.fill_between(
                        t_ms[okt], (tong_mu - tong_sem)[okt],
                        (tong_mu + tong_sem)[okt],
                        color=color, alpha=0.06, lw=0,
                    )
            else:
                for s in sub:
                    ax.plot(s["t_ms"], s["jaw_y"], color=color, lw=1.0, alpha=0.20)
                    ax2.plot(
                        s["t_ms"], s["tongue_y"], color=color, lw=0.9,
                        alpha=0.10, linestyle=_TONGUE_LS,
                    )
            ax.axvline(0, color=_REWARD_COLOR, linestyle=":", lw=1.0, alpha=0.8)
            ax.axhline(0, color="0.5", linestyle="--", lw=0.8, alpha=0.6)
            ax.set_ylabel(_LEGACY_JAW_YLABEL, color="k")
            ax2.set_ylabel(_LEGACY_TONGUE_YLABEL, color="k")
            ax.grid(True, alpha=0.15)
            if row_jaw_lim is not None:
                ax.set_ylim(*row_jaw_lim)
            if row_tong_lim is not None:
                ax2.set_ylim(*row_tong_lim)
            if rix == 3:
                ax.set_xlabel(_LEGACY_XLABEL)
    fig.suptitle(
        f"{animal} {date.strftime('%Y%m%d')} | within-session overlay grid",
        y=0.995,
    )
    fig.tight_layout()
    return fig


def _aggregate_session_means(
    sessions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per-(date, side, candidate) mean ± SEM bundle for cross-session plots."""
    items: list[dict[str, Any]] = []
    for s in sessions:
        rows = _build_plot_snippets(
            s["trials_df"], s["jaw_y"], s["tongue_y"], s["fps"], s["n_frames"],
        )
        if not rows:
            continue
        t_ms = rows[0]["t_ms"]
        for side in ("L", "R"):
            for cand_flag in (True, False):
                sub = [
                    r for r in rows
                    if r["side"] == side and r["candidate"] == cand_flag
                ]
                if not sub:
                    continue
                jawM = np.vstack([r["jaw_y"] for r in sub])
                tongM = np.vstack([r["tongue_y"] for r in sub])
                jaw_mu, jaw_sem = _mean_sem(jawM)
                tong_mu, tong_sem = _mean_sem(tongM)
                items.append(dict(
                    date=s["date"], rel_day=int(s["rel_day"]),
                    side=side, candidate=cand_flag,
                    t_ms=t_ms, jaw_mu=jaw_mu, jaw_sem=jaw_sem,
                    tong_mu=tong_mu, tong_sem=tong_sem,
                    n_trials=len(sub),
                ))
    return items


def _color_for_rel_day(
    rel_day: int, max_post: int, *, cmap_name: str = "plasma",
) -> tuple[float, float, float, float]:
    """Pre-stroke = grey 0.65; post-stroke = ``cmap_name`` colormap by rel_day."""
    if rel_day <= 0 or max_post <= 0:
        return (0.65, 0.65, 0.65, 1.0)
    cmap = plt.get_cmap(cmap_name)
    norm = max(1, max_post)
    return cmap(min(1.0, rel_day / norm))


def _add_cross_session_colorbar(
    fig: Figure, *, cmap_name: str, max_post: int,
    rect: tuple[float, float, float, float] = (0.90, 0.22, 0.015, 0.56),
    label: str = "Post-stroke day",
) -> None:
    """Right-side colorbar mapping post-stroke day → color.

    Mirrors legacy Cell 55's :func:`_add_cross_session_colorbar` (vendored at
    ``docs/legacy_snippets/tongue_jaw_mismatch.py:1317-1322``): default
    cax position ``[0.90, 0.22, 0.015, 0.56]``, label ``"Post-stroke day"``,
    normalization ``vmin=1, vmax=max_post``.
    """
    if max_post <= 0:
        return
    from matplotlib import cm as _cm
    from matplotlib.colors import Normalize

    norm = Normalize(vmin=1, vmax=int(max_post))
    cmap = plt.get_cmap(cmap_name)
    sm = _cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cax = fig.add_axes(list(rect))
    cb = fig.colorbar(sm, cax=cax)
    cb.set_label(label)


def _plot_cross_session_2x2(
    items: list[dict[str, Any]], *, animal: str, title_suffix: str,
    cfg: dict[str, Any] | None = None,
) -> Figure:
    """Shared 2×2 cross-session plotter: rows=cand/noncand, cols=L/R.

    Phase 7a.5 C6.2 (Priya 2026-05-01) port-fidelity round: replicate
    legacy Cell 55 ``_plot_cross_session_grid`` layout exactly.

    - figsize, hspace, wspace from the per-family YAML block.
    - ``tight_layout(rect=[0.0, 0.0, 0.88, 0.98])`` reserves the right
      12% for the colorbar (legacy idiom — different from C6.1's
      ``subplots_adjust(right=0.88)`` which composed badly with axis-label
      growth).
    - Colorbar at ``cfg["colorbar_rect"]`` (legacy default
      ``[0.90, 0.22, 0.015, 0.56]``) with label "Post-stroke day".
    - Axis labels use ``_LEGACY_JAW_YLABEL`` / ``_LEGACY_TONGUE_YLABEL``
      (no explicit fontsize → matplotlib default ~10, larger than the
      C6.1 ``fontsize=8``).
    - Per-bodypart twin-axis percentile-cap auto-scale per row (Fix 3
      revised — same pipeline as session_overlay_grid mean±SEM rows).
    """
    cfg = cfg or {}
    fig_w = float(cfg.get("figure_width_inches", 13.0))
    fig_h = float(cfg.get("figure_height_inches", 8.5))
    hspace = float(cfg.get("hspace", 0.34))
    wspace = float(cfg.get("wspace", 0.24))
    tlrect = list(cfg.get("tight_layout_rect", [0.0, 0.0, 0.88, 0.98]))
    cbar_rect = tuple(cfg.get("colorbar_rect", [0.90, 0.22, 0.015, 0.56]))
    shared_y = bool(cfg.get("shared_y_axis_per_plot_type_row", False))
    include_colorbar = bool(cfg.get("include_colorbar", False))
    cmap_name = str(cfg.get("colormap", "plasma"))

    # Percentile-cap knobs default to legacy values; per-cross-session
    # overrides not exposed yet (would only be added on a Priya request).
    pad_frac = float(cfg.get("pad_fraction", 0.05))
    pmax = float(cfg.get("percentile_cap_max", 99.9))
    pmin_raw = cfg.get("percentile_cap_min", None)
    pmin = float(pmin_raw) if pmin_raw is not None else None

    fig, axes = plt.subplots(2, 2, figsize=(fig_w, fig_h), sharex=True)
    fig.subplots_adjust(hspace=hspace, wspace=wspace)
    post_days = sorted({it["rel_day"] for it in items if it["rel_day"] > 0})
    max_post = max(post_days) if post_days else 0
    for rix, cand_flag in enumerate([True, False]):
        # Per-row shared-Y across L+R, percentile-cap auto-scaled per bodypart.
        if shared_y:
            row_items = [it for it in items if it["candidate"] == cand_flag]
            jaw_arrs, tong_arrs = _collect_cross_session_arrays(row_items)
            row_jaw_lim = _percentile_cap_range(
                jaw_arrs, pmax=pmax, pmin=pmin, pad_frac=pad_frac,
            )
            row_tong_lim = _percentile_cap_range(
                tong_arrs, pmax=pmax, pmin=pmin, pad_frac=pad_frac,
            )
        else:
            row_jaw_lim, row_tong_lim = None, None
        for cix, side in enumerate(["L", "R"]):
            ax = axes[rix, cix]
            ax2 = ax.twinx()
            panel = [
                it for it in items
                if it["side"] == side and it["candidate"] == cand_flag
            ]
            label = "candidate" if cand_flag else "non-candidate"
            n_trials_total = sum(it["n_trials"] for it in panel)
            n_groups = len(panel)
            ax.set_title(
                f"{label} | side={side}\nn_trials={n_trials_total} | n_groups={n_groups}",
                fontsize=10,
            )
            if not panel:
                ax.text(
                    0.5, 0.5, "no sessions", ha="center", va="center",
                    transform=ax.transAxes, fontsize=11, color="0.5",
                )
                ax.set_xticks([])
                ax.set_yticks([])
                ax2.set_yticks([])
                continue
            for it in panel:
                color = _color_for_rel_day(
                    it["rel_day"], max_post, cmap_name=cmap_name,
                )
                ax.plot(it["t_ms"], it["jaw_mu"], color=color, lw=0.9, alpha=0.85)
                ok = np.isfinite(it["jaw_mu"]) & np.isfinite(it["jaw_sem"])
                if np.any(ok):
                    ax.fill_between(
                        it["t_ms"][ok],
                        (it["jaw_mu"] - it["jaw_sem"])[ok],
                        (it["jaw_mu"] + it["jaw_sem"])[ok],
                        color=color, alpha=0.07,
                    )
                ax2.plot(
                    it["t_ms"], it["tong_mu"], color=color, lw=0.9,
                    alpha=0.85, linestyle=_TONGUE_LS,
                )
            ax.axvline(0, color=_REWARD_COLOR, linestyle=":", lw=1.0, alpha=0.8)
            ax.axhline(0, color="0.5", linestyle="--", lw=0.8, alpha=0.6)
            ax.set_ylabel(_LEGACY_JAW_YLABEL, color="k")
            ax2.set_ylabel(_LEGACY_TONGUE_YLABEL, color="k")
            ax.grid(True, alpha=0.15)
            if row_jaw_lim is not None:
                ax.set_ylim(*row_jaw_lim)
            if row_tong_lim is not None:
                ax2.set_ylim(*row_tong_lim)
            if rix == 1:
                ax.set_xlabel(_LEGACY_XLABEL)
    fig.suptitle(
        f"{animal} | {title_suffix} | pre-stroke=grey, post-stroke={cmap_name} "
        f"(day 0 treated as pre)",
        y=0.995,
    )
    # Legacy reserves the right 12% via tight_layout(rect=...) — see
    # vendored Cell 55 line 1777. Compose with the colorbar add_axes call
    # below.
    fig.tight_layout(rect=tlrect)
    if include_colorbar:
        _add_cross_session_colorbar(
            fig, cmap_name=cmap_name, max_post=max_post, rect=cbar_rect,
        )
    return fig


def _plot_cross_session_overlay(
    sessions: list[dict[str, Any]], *, animal: str,
    plotter_cfg: dict[str, Any] | None = None,
) -> Figure:
    """Cross-session per-session-mean overlays (no day-binning)."""
    items = _aggregate_session_means(sessions)
    overlay_cfg = (plotter_cfg or {}).get("cross_session_overlay", {})
    return _plot_cross_session_2x2(
        items, animal=animal,
        title_suffix="cross-session session overlays (mean ± SEM per session)",
        cfg=overlay_cfg,
    )


def _bin_label(bin_start: int, bin_end: int) -> str:
    return f"d{bin_start:+d}" if bin_start == bin_end else f"d{bin_start:+d}..d{bin_end:+d}"


def _bin_index(rel_day: int, bin_days: int) -> tuple[int, int, int]:
    """Pre/post asymmetric binning matching legacy Cell 55:
    pre-stroke (rel_day <= 0): bin_end aligns at 0; post-stroke: bin_start at 1.
    """
    b = max(1, int(bin_days))
    rd = int(rel_day)
    if rd <= 0:
        idx = (-rd) // b
        bin_end = -(idx * b)
        bin_start = bin_end - (b - 1)
    else:
        idx = (rd - 1) // b
        bin_start = 1 + idx * b
        bin_end = bin_start + (b - 1)
    return idx, bin_start, bin_end


def _plot_cross_session_binned(
    sessions: list[dict[str, Any]], *, animal: str, bin_days: int,
    plotter_cfg: dict[str, Any] | None = None,
) -> Figure:
    """Cross-session day-binned overlays. Bin width = ``animal_info.bin_days``."""
    session_items = _aggregate_session_means(sessions)
    grouped: dict[tuple, list[dict[str, Any]]] = {}
    for it in session_items:
        _, bin_start, bin_end = _bin_index(it["rel_day"], bin_days)
        key = (it["side"], it["candidate"], bin_start, bin_end)
        grouped.setdefault(key, []).append(it)
    binned: list[dict[str, Any]] = []
    for (side, cand_flag, bin_start, bin_end), members in grouped.items():
        t_ms = members[0]["t_ms"]
        jawM = np.vstack([m["jaw_mu"] for m in members])
        tongM = np.vstack([m["tong_mu"] for m in members])
        jaw_mu, jaw_sem = _mean_sem(jawM)
        tong_mu, tong_sem = _mean_sem(tongM)
        rep_day = 0 if bin_end <= 0 else int(0.5 * (bin_start + bin_end))
        binned.append(dict(
            side=side, candidate=cand_flag,
            rel_day=rep_day, n_trials=int(sum(m["n_trials"] for m in members)),
            t_ms=t_ms, jaw_mu=jaw_mu, jaw_sem=jaw_sem,
            tong_mu=tong_mu, tong_sem=tong_sem,
            label=_bin_label(bin_start, bin_end),
        ))
    binned_cfg = (plotter_cfg or {}).get("cross_session_binned", {})
    return _plot_cross_session_2x2(
        binned, animal=animal,
        title_suffix=f"cross-session binned overlays (bin size = {bin_days} days)",
        cfg=binned_cfg,
    )
