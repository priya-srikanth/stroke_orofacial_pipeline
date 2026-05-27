"""Phase 7a.5 — Jaw per-trial features.

Extracted from canonical tongue notebook
(``20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb``,
SHA256 ``ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643``,
Cell 53 inline-detection logic — vendored byte-identically at
``docs/legacy_snippets/tongue_jaw_mismatch.py`` Cell 53,
sha256 ``5ed7b814cf2b5a53...``).

Reusable building block for jaw-related per-trial analyses; mirrors
``tongue_pertrial.py`` architecture at smaller scale. The 7a.3-jaw audit
(PR #87) confirmed the JAW NOTEBOOK has no per-trial features — the per-
trial logic actually lives inside the tongue notebook's mismatch
classifier (Cell 53), and is extracted here as its own module per
hybrid B1.5 sub-variant (Phase 7a.5 locked decision #1, 2026-04-30).

Inputs
------
- 7a.2 jaw interpolated_traces parquet
  (``frame_idx``, ``y_final``, ``fps`` + ``n_frames`` in file metadata)
- :class:`SessionManifest` (animal, date)
- ``trial_events`` (per-trial tone frame + side; ``TrialEvent.tone_frame_idx``
  field name PRESERVED per Phase 7b-light Addendum #1 — DataFrame column /
  on-disk surface) — supplied by caller
  or auto-derived via the 7a.3 V3 helper
  :func:`stroke_orofacial.dlc_kinematics.tongue_pertrial._derive_trial_events_from_spout_behavior`

Outputs (atomic, one JSON file per session)
-------------------------------------------
- ``<outputs>/dlc_kinematics/per_trial/jaw/<animal>/<YYYYMMDD>.json``
  (per-trial scalars + metadata; ``schema_version="v7a.5"``)

Per-trial scalars (8 fields, co-indexed with ``trial_indices`` + ``sides``)
--------------------------------------------------------------------------
1.  ``jaw_baseline_mean`` — mean of ``y_final`` over ``baseline_win_ms``
    (default ``(-500, 0)`` ms relative to tone onset).
2.  ``jaw_baseline_sd`` — population SD (``np.nanstd``) over the same window.
3.  ``jaw_peak_pos_deflection`` — max of ``(y_final - baseline_mean)``
    inside ``detect_win_ms`` (default ``(0, 5000)`` ms).
4.  ``jaw_peak_neg_deflection`` — min of same (signed).
5.  ``jaw_peak_abs_deflection`` — max of ``|y_final - baseline_mean|``.
6.  ``jaw_peak_selected_deflection`` — signed value of ``y_final -
    baseline_mean`` at the ``argmax(|.|)`` index inside ``detect_win_ms``
    (legacy ``direction_mode="above_or_below"`` convention; cohort default).
7.  ``jaw_thresh_abs`` — ``max(sd_mult * baseline_sd, min_px)``, the
    applied threshold (kickoff §4 redefinition: collapses legacy's dual-
    float ``jaw_thresh_abs`` (= 4·sd) + ``jaw_thresh_px_used`` (= max of
    same and floor) into one float carrying the actually-applied value).
8.  ``jaw_thresh_px_used`` — ``"sd_scaled"`` if the SD-scaled term won,
    ``"px_floor"`` if the px-floor won (categorical successor to legacy's
    redundant second float; declared in kickoff §4a 2026-04-30).
9.  ``jaw_n_frames_over_thresh`` — count of frames in ``detect_win_ms``
    where ``|defl| > jaw_thresh_abs``.
10. ``jaw_pass_qc`` — bool: at least one rolling
    ``sustained_window_n_frames``-frame segment of the test-window mask
    has at least ``ceil(sustained_density_threshold *
    sustained_window_n_frames)`` suprathreshold frames (legacy default
    ``5/8``, the ``_count_true_runs_in_window`` predicate from Cell 53).

Trial whose baseline is degenerate (< 2 finite frames in baseline window)
emits NaN for baseline + peaks, ``"none"`` for the threshold-label, NaN
for ``jaw_thresh_abs``, ``0`` for ``n_frames_over_thresh``, and ``False``
for ``jaw_pass_qc``. Same legacy semantics.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_kinematics._writers import _write_endpoints_json_atomic
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    TrialEvent,
    _derive_trial_events_from_spout_behavior,
)
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

# Version stamped into every emitted JSON. Bumping requires a DECISIONS
# entry + 14-session legacy_approximate parity re-run.
JAW_PERTRIAL_VERSION: str = "v7a.5"
# Trace-source version stamps. Selected dynamically based on the
# dlc_kinematics.jaw.use_cleaned_traces flag.
INTERPOLATION_VERSION_V5P3: str = "v5p3"
INTERPOLATION_VERSION_CLEANED: str = "v3.4-cleaned"
# Backward-compat alias (legacy callers reading this constant). Defaults
# to the v5p3 string; cleaned-trace runs stamp "v3.4-cleaned" into the
# JSON metadata directly.
INTERPOLATION_VERSION: str = INTERPOLATION_VERSION_V5P3


# ===========================================================================
# Public dataclass
# ===========================================================================


@dataclass(frozen=True)
class JawPertrialResult:
    """In-memory container for the JSON emit (pre-write).

    ``endpoints`` matches the on-disk JSON top-level shape exactly
    (``schema_version``, ``animal``, ``date``, ``n_trials``,
    ``trial_indices``, ``sides``, ``jaw_pertrial``, ``metadata``).
    ``metadata`` is the same dict embedded under ``endpoints["metadata"]``
    — duplicated at the dataclass level for direct access by callers
    (e.g. the mismatch classifier in Phase 7a.5 Task 5) that want the
    per-session config without round-tripping through the JSON.
    """

    endpoints: dict[str, Any]
    metadata: dict[str, Any]


# ===========================================================================
# Public API
# ===========================================================================


def build_jaw_pertrial(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: Sequence[TrialEvent],
    params: dict[str, Any] | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
    animal_info: AnimalInfo | None = None,
) -> Path | None:
    """Build per-trial jaw scalars for one session and write JSON atomically.

    Returns the emitted JSON path, or ``None`` if ``overwrite="skip"`` AND
    the target file already exists. Mirrors the
    :func:`stroke_orofacial.dlc_kinematics.build_tongue_pertrial` driver
    contract (overwrite semantics, manifest-excluded short-circuit,
    params-default load).
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

    out_path = resolver.jaw_pertrial_endpoints_json(
        manifest.animal, manifest.date,
    )
    if overwrite == "skip" and out_path.exists():
        return out_path

    result = _build_jaw_pertrial_core(
        manifest=manifest,
        resolver=resolver,
        trial_events=trial_events,
        params=params,
    )
    _write_endpoints_json_atomic(out_path, result.endpoints)
    return out_path


def build_jaw_pertrial_by_animal_date(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    trial_events: Sequence[TrialEvent] | None = None,
    **kwargs: Any,
) -> Path | None:
    """Convenience wrapper analogous to
    :func:`stroke_orofacial.dlc_kinematics.build_tongue_pertrial_by_animal_date`.

    Auto-derives ``trial_events`` from upstream spout_behavior products
    via the 7a.3 V3 helper
    :func:`stroke_orofacial.dlc_kinematics.tongue_pertrial._derive_trial_events_from_spout_behavior`
    if not explicitly passed (the same helper 7a.3 V3 / 7a.4 reuse). The
    private cross-module import is acceptable for the 7a.x family per the
    Task 4 kickoff sign-off; promotion to a public helper is deferred to
    a future generalized per-trial-features framework refactor.
    """
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.kinematics.jaw_pertrial",
    )
    if trial_events is None:
        trial_events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
    kwargs.setdefault("animal_info", animal_info)
    return build_jaw_pertrial(
        manifest=manifest,
        resolver=resolver,
        trial_events=trial_events,
        **kwargs,
    )


# ===========================================================================
# Core compute
# ===========================================================================


def _build_jaw_pertrial_core(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: Sequence[TrialEvent],
    params: dict[str, Any],
) -> JawPertrialResult:
    """Pure-compute path (no I/O): load jaw parquet, compute per-trial scalars,
    return a :class:`JawPertrialResult`."""
    jp_params = params["dlc_kinematics"]["jaw_pertrial"]
    detect_win_ms = tuple(jp_params["detect_win_ms"])
    baseline_win_ms = tuple(jp_params["baseline_win_ms"])
    sd_mult = float(jp_params["deflection_threshold_sd_multiplier"])
    min_px = float(jp_params["deflection_threshold_min_px"])
    density_thr = float(jp_params["sustained_density_threshold"])
    window_n = int(jp_params["sustained_window_n_frames"])

    use_cleaned = bool(
        params.get("dlc_kinematics", {})
        .get("jaw", {})
        .get("use_cleaned_traces", True),
    )
    jaw_y, fps, n_frames = _load_jaw_y_final(manifest, resolver, params)

    rows: list[dict[str, Any]] = []
    for ev in trial_events:
        rows.append(_compute_per_trial(
            ev, jaw_y, fps, n_frames,
            detect_win_ms=detect_win_ms,
            baseline_win_ms=baseline_win_ms,
            sd_mult=sd_mult, min_px=min_px,
            density_thr=density_thr, window_n=window_n,
        ))

    metadata = {
        "fps": float(fps),
        "n_frames": int(n_frames),
        "feature_extraction_version": JAW_PERTRIAL_VERSION,
        "interpolation_version": (
            INTERPOLATION_VERSION_CLEANED if use_cleaned
            else INTERPOLATION_VERSION_V5P3
        ),
        "use_cleaned_traces": bool(use_cleaned),
        "detect_win_ms": list(detect_win_ms),
        "baseline_win_ms": list(baseline_win_ms),
        "deflection_threshold_sd_multiplier": sd_mult,
        "deflection_threshold_min_px": min_px,
        "sustained_density_threshold": density_thr,
        "sustained_window_n_frames": window_n,
    }

    endpoints = {
        "schema_version": JAW_PERTRIAL_VERSION,
        "animal": manifest.animal,
        "date": manifest.date.isoformat(),
        "n_trials": len(rows),
        "trial_indices": [int(r["trial_index"]) for r in rows],
        "sides": [str(r["side"]) for r in rows],
        "jaw_pertrial": {
            "jaw_baseline_mean": [r["jaw_baseline_mean"] for r in rows],
            "jaw_baseline_sd": [r["jaw_baseline_sd"] for r in rows],
            "jaw_peak_pos_deflection": [r["jaw_peak_pos_deflection"] for r in rows],
            "jaw_peak_neg_deflection": [r["jaw_peak_neg_deflection"] for r in rows],
            "jaw_peak_abs_deflection": [r["jaw_peak_abs_deflection"] for r in rows],
            "jaw_peak_selected_deflection": [
                r["jaw_peak_selected_deflection"] for r in rows
            ],
            "jaw_thresh_abs": [r["jaw_thresh_abs"] for r in rows],
            "jaw_thresh_px_used": [r["jaw_thresh_px_used"] for r in rows],
            "jaw_n_frames_over_thresh": [
                int(r["jaw_n_frames_over_thresh"]) for r in rows
            ],
            "jaw_pass_qc": [bool(r["jaw_pass_qc"]) for r in rows],
        },
        "metadata": metadata,
    }
    return JawPertrialResult(endpoints=endpoints, metadata=metadata)


# ===========================================================================
# Loaders
# ===========================================================================


def _load_jaw_y_final(
    manifest: SessionManifest, resolver: PathResolver,
    params: dict[str, Any] | None = None,
) -> tuple[np.ndarray, float, int]:
    """Read the jaw trace parquet for this session.

    By default (Phase 7f, ``dlc_kinematics.jaw.use_cleaned_traces=true``)
    reads from ``cleaned_traces/jaw/`` (Phase 7f v3.4 post-clean
    outputs). Set the flag to False to fall back to ``interpolated_traces/jaw/``
    (Phase 7a.2 v5p3 raw) for A/B audits. Schema is identical
    (v5p3-compatible drop-in) so the rest of jaw_pertrial doesn't change.

    Returns ``(y_final, fps, n_frames)``. Only ``y_final`` is needed by
    Cell 53 logic; ``x_final`` is unread (jaw deflection is a Y-axis
    quantity in spout-centered coordinates, not a 2D distance).
    """
    use_cleaned = True
    if params is not None:
        use_cleaned = bool(
            params.get("dlc_kinematics", {})
            .get("jaw", {})
            .get("use_cleaned_traces", True),
        )

    if use_cleaned:
        path = resolver.cleaned_trace(
            bodypart="jaw", animal=manifest.animal, date=manifest.date,
        )
        if not path.exists():
            raise FileNotFoundError(
                f"Phase 7f cleaned_traces/jaw parquet missing for "
                f"{manifest.animal}/{manifest.date.isoformat()}: expected at {path}. "
                f"Either run the Phase 7f Step 1 re-emit, or set "
                f"dlc_kinematics.jaw.use_cleaned_traces=false to fall back to v5p3.",
            )
    else:
        path = resolver.interpolated_trace(
            bodypart="jaw", animal=manifest.animal, date=manifest.date,
        )
        if not path.exists():
            raise FileNotFoundError(
                f"7a.2 jaw interpolated_traces parquet missing for "
                f"{manifest.animal}/{manifest.date.isoformat()}: expected at {path}. "
                f"Run build_interpolated_trace first.",
            )
    df = pd.read_parquet(path, columns=["y_final"])
    schema = pq.read_schema(path)
    raw_meta = schema.metadata or {}
    fps_meta = raw_meta.get(b"fps")
    n_frames_meta = raw_meta.get(b"n_frames")
    if fps_meta is None or n_frames_meta is None:
        raise ValueError(
            f"jaw parquet at {path} missing required 'fps' / 'n_frames' "
            f"metadata keys (expected per the 7a.2 schema lock).",
        )
    fps = float(fps_meta.decode("utf-8"))
    n_frames = int(n_frames_meta.decode("utf-8"))
    y_final = df["y_final"].to_numpy(dtype=np.float64, copy=False)
    if len(y_final) != n_frames:
        raise ValueError(
            f"jaw parquet at {path}: column length {len(y_final)} != "
            f"n_frames metadata {n_frames}.",
        )
    return y_final, fps, n_frames


# ===========================================================================
# Per-trial compute
# ===========================================================================


def _compute_per_trial(
    ev: TrialEvent,
    jaw_y: np.ndarray,
    fps: float,
    n_frames: int,
    *,
    detect_win_ms: tuple[float, float],
    baseline_win_ms: tuple[float, float],
    sd_mult: float,
    min_px: float,
    density_thr: float,
    window_n: int,
) -> dict[str, Any]:
    """Compute the 10 per-trial scalars for one ``TrialEvent``.

    Returns a flat dict (keys = the 8 jaw scalars + ``trial_index`` + ``side``).
    """
    # Snippet window: union of baseline + detect windows, with a 1-frame pad
    # on each side to keep window_mask comparisons inclusive at the edges.
    snippet_lo_ms = min(baseline_win_ms[0], detect_win_ms[0])
    snippet_hi_ms = max(baseline_win_ms[1], detect_win_ms[1])
    pre_f = abs(_ms_to_frames(snippet_lo_ms, fps))
    post_f = abs(_ms_to_frames(snippet_hi_ms, fps))
    t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))

    jaw_yw = _snippet(jaw_y, ev.tone_frame_idx, pre_f, post_f, n_frames)

    base_mean, base_sd = _compute_jaw_baseline(
        jaw_yw, t_ms, baseline_win_ms=baseline_win_ms,
    )

    # Threshold computation. For degenerate baseline (sd is NaN/0), the
    # SD-scaled term is non-finite/zero so the floor wins; legacy emits
    # NaN+False in that case, which we mirror by short-circuiting the
    # downstream test-window math.
    thresh_abs, thresh_label = _compute_jaw_threshold(
        base_sd, sd_mult=sd_mult, min_px=min_px,
    )

    if not np.isfinite(base_mean) or not np.isfinite(base_sd) or base_sd <= 0:
        # Legacy semantics: degenerate baseline → all peaks NaN, threshold
        # NaN, count 0, QC fail. (Matches Cell 53's
        # ``if jaw_baseline_sd > 0: ... else: jaw_pass_qc = False`` branch.)
        return dict(
            trial_index=int(ev.trial_index),
            side=str(ev.side),
            jaw_baseline_mean=_to_jsonable_float(base_mean),
            jaw_baseline_sd=_to_jsonable_float(base_sd),
            jaw_peak_pos_deflection=None,
            jaw_peak_neg_deflection=None,
            jaw_peak_abs_deflection=None,
            jaw_peak_selected_deflection=None,
            jaw_thresh_abs=None,
            jaw_thresh_px_used="none",
            jaw_n_frames_over_thresh=0,
            jaw_pass_qc=False,
        )

    peaks = _compute_jaw_deflections(
        jaw_yw, t_ms, base_mean, detect_win_ms=detect_win_ms,
    )
    pass_qc, n_over = _check_sustained_density(
        jaw_yw, t_ms, base_mean, thresh_abs,
        detect_win_ms=detect_win_ms,
        window_n=window_n,
        density_thr=density_thr,
    )

    return dict(
        trial_index=int(ev.trial_index),
        side=str(ev.side),
        jaw_baseline_mean=float(base_mean),
        jaw_baseline_sd=float(base_sd),
        jaw_peak_pos_deflection=_to_jsonable_float(peaks["pos"]),
        jaw_peak_neg_deflection=_to_jsonable_float(peaks["neg"]),
        jaw_peak_abs_deflection=_to_jsonable_float(peaks["abs"]),
        jaw_peak_selected_deflection=_to_jsonable_float(peaks["selected"]),
        jaw_thresh_abs=float(thresh_abs),
        jaw_thresh_px_used=str(thresh_label),
        jaw_n_frames_over_thresh=int(n_over),
        jaw_pass_qc=bool(pass_qc),
    )


# ===========================================================================
# Numeric helpers
# ===========================================================================


def _ms_to_frames(ms: float, fps: float) -> int:
    return int(np.round((ms / 1000.0) * fps))


def _snippet(
    arr: np.ndarray, center_fr: int, pre_f: int, post_f: int, n_frames: int,
) -> np.ndarray:
    """Per-trial slice with NaN padding when tone is near a session edge.

    Mirrors Cell 53's ``_snippet`` helper byte-for-byte (vendored at
    ``docs/legacy_snippets/tongue_jaw_mismatch.py`` Cell 53 lines 189-199).
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


def _window_mask(t_ms: np.ndarray, win_ms: tuple[float, float]) -> np.ndarray:
    """Inclusive time-window mask. Mirrors Cell 53's ``_window_mask``."""
    lo, hi = float(win_ms[0]), float(win_ms[1])
    t = np.asarray(t_ms, float)
    return np.isfinite(t) & (t >= lo) & (t <= hi)


def _compute_jaw_baseline(
    jaw_y: np.ndarray, t_ms: np.ndarray,
    *, baseline_win_ms: tuple[float, float],
) -> tuple[float, float]:
    """Mean + population SD of finite ``jaw_y`` over ``baseline_win_ms``.

    Returns ``(NaN, NaN)`` if fewer than 2 finite frames in the window
    (legacy Cell 53 ``if jaw_base.size >= 2`` guard).
    """
    base_mask = _window_mask(t_ms, baseline_win_ms)
    base_vals = np.asarray(jaw_y, float)[base_mask]
    base_vals = base_vals[np.isfinite(base_vals)]
    if base_vals.size < 2:
        return float("nan"), float("nan")
    return float(np.nanmean(base_vals)), float(np.nanstd(base_vals))


def _compute_jaw_deflections(
    jaw_y: np.ndarray, t_ms: np.ndarray, baseline_mean: float,
    *, detect_win_ms: tuple[float, float],
) -> dict[str, float]:
    """Peak deflections inside ``detect_win_ms``.

    Mirrors Cell 53's ``direction_mode="above_or_below"`` branch verbatim:
    ``selected = jaw_test_vals[np.nanargmax(np.abs(jaw_test_vals))]`` (the
    signed value at the max-magnitude index — the larger of |pos| vs |neg|
    with sign preserved).
    """
    test_mask = _window_mask(t_ms, detect_win_ms)
    test_vals = np.asarray(jaw_y, float)[test_mask] - baseline_mean
    test_vals = test_vals[np.isfinite(test_vals)]
    if test_vals.size == 0:
        return dict(
            pos=float("nan"), neg=float("nan"),
            abs=float("nan"), selected=float("nan"),
        )
    pos = float(np.nanmax(test_vals))
    neg = float(np.nanmin(test_vals))
    abs_ = float(np.nanmax(np.abs(test_vals)))
    idx_sel = int(np.nanargmax(np.abs(test_vals)))
    selected = float(test_vals[idx_sel])
    return dict(pos=pos, neg=neg, abs=abs_, selected=selected)


def _compute_jaw_threshold(
    baseline_sd: float, *, sd_mult: float, min_px: float,
) -> tuple[float, str]:
    """Resolve the applied threshold + label which path won.

    ``threshold_value = max(sd_mult * baseline_sd, min_px)``.
    Label is ``"sd_scaled"`` when the SD-scaled term is the larger of the
    two, else ``"px_floor"``. Ties (numerically equal) are recorded as
    ``"px_floor"`` (deterministic floor-preferred tiebreak; same convention
    as Python's ``max`` would pick the first equal element).

    Edge cases: ``baseline_sd`` may be NaN (degenerate baseline) — the
    caller short-circuits before reaching this helper, but as a defensive
    guard, NaN ``sd_mult * baseline_sd`` collapses to the px floor (NaN <
    any finite ``min_px``? actually NaN comparisons return False, so
    ``np.maximum`` with NaN propagates; we explicitly guard against NaN by
    returning ``(min_px, "px_floor")`` in that case).
    """
    sd_term = sd_mult * baseline_sd
    if not np.isfinite(sd_term):
        return float(min_px), "px_floor"
    if sd_term > min_px:
        return float(sd_term), "sd_scaled"
    return float(min_px), "px_floor"


def _check_sustained_density(
    jaw_y: np.ndarray, t_ms: np.ndarray, baseline_mean: float, threshold: float,
    *, detect_win_ms: tuple[float, float],
    window_n: int, density_thr: float,
) -> tuple[bool, int]:
    """Rolling-window density check inside ``detect_win_ms``.

    Returns ``(pass_qc, n_frames_over_thresh)``:

    - ``n_frames_over_thresh``: total count of frames inside
      ``detect_win_ms`` with ``|jaw_y - baseline_mean| > threshold``.
    - ``pass_qc``: True if any contiguous ``window_n``-frame slice of the
      test-window mask contains at least
      ``ceil(density_thr * window_n)`` suprathreshold frames.

    Matches Cell 53's ``_count_true_runs_in_window(supra[test_mask],
    min_true=jaw_min_frames_over, run_window=jaw_frame_window)`` predicate
    with ``min_true = ceil(density_thr * window_n)`` (legacy default
    ``5 = ceil(0.625 * 8)``).
    """
    test_mask = _window_mask(t_ms, detect_win_ms)
    defl = np.asarray(jaw_y, float) - baseline_mean
    supra_full = np.isfinite(defl) & test_mask & (np.abs(defl) > threshold)
    n_over = int(np.sum(supra_full))

    supra_test = supra_full[test_mask].astype(int)
    W = max(1, int(window_n))
    K = max(1, int(np.ceil(density_thr * W)))
    if supra_test.size == 0:
        return False, n_over
    if supra_test.size < W:
        return bool(supra_test.sum() >= K), n_over
    counts = np.convolve(supra_test, np.ones(W, dtype=int), mode="valid")
    return bool(np.any(counts >= K)), n_over


def _to_jsonable_float(x: float) -> float | None:
    """JSON has no NaN literal — emit ``null`` for non-finite floats so
    downstream JSON parsers don't choke on ``NaN`` non-tokens."""
    xf = float(x)
    if not np.isfinite(xf):
        return None
    return xf
