"""Phase 7a.2 — bodypart-parametric v5p3 interpolation.

Ports ``docs/legacy_snippets/tongue_cell23_interp_v5p3.py`` and
``docs/legacy_snippets/jaw_cell22_interp_v5p3.py`` into one module.
The two legacy cells are algorithmically identical — they differ only
in bodypart-parametric constants (from
``configs/defaults.yaml dlc_kinematics.<bodypart>``) and per-animal
``(X0, Y0)`` baselines (from ``configs/animals.yaml kinematics_baselines``
via :meth:`AnimalInfo.get_kinematics_baseline`).

Public API
----------
:class:`InterpolationResult`
    7-stage arrays + provenance masks + scalar metadata.
:func:`build_interpolated_trace`
    Session-level driver. Writes canonical parquet + optional QC NPZ.
:func:`build_interpolated_trace_by_animal_date`
    ``(animal, date)`` convenience wrapper.

Knob resolutions (DECISIONS 2026-04-22, ``interpolation-strategy.md`` §10):
Knob 1 split emit • Knob 2 PCHIP + linear fallback (not runtime-tunable) •
Knob 3 forced baseline path default, data-driven path preserved •
Knob 4 ``x_range_source="lk"`` for parity • §5 Option A pure-bodypart
parquet (no side labels) • §3.1 per-animal baselines in ``animals.yaml``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.interpolate import PchipInterpolator

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.lr_convention import (
    SIDE_CONVENTION_MATCH_KEY,
    SIDE_CONVENTION_VERSION,
    SIDE_CONVENTION_VERSION_KEY,
)
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

# Version tag stamped into every emitted parquet/NPZ. Bumping requires a
# DECISIONS entry + a full 14-session parity re-run.
INTERPOLATION_VERSION: str = "v5p3"

# fill_method per-frame categorical for the output parquet.
_FILL_METHOD_NONE: int = 0
_FILL_METHOD_PCHIP: int = 1
_FILL_METHOD_LINEAR: int = 2
_FILL_METHOD_BASELINE: int = 3

# Legacy tongue Cell 23 + jaw Cell 22 hardcode FPS = 250.0. Consolidated
# callers read it from ``alignment.fps_cam``; this is the fallback.
_DEFAULT_FPS: float = 250.0

# Post-tone window for the baseline-pool mask. Locked at legacy values;
# not a YAML knob because the cohort's legacy NPZs were computed with
# these exact bounds.
_BASELINE_POST_WIN_MS: tuple[float, float] = (0.0, 5000.0)
_BASELINE_SOURCE_STAGE: str = "drop"  # legacy BASELINE_SOURCE_STAGE
_BASELINE_REQUIRE_FINITE_X: bool = True

# Centering-likelihood threshold used in the Phase 4.5-lite centered
# parquet's filename signature. Must match ``dlc_io.parquet._param_sig``.
_CENTERING_LIKELIHOOD_THRESHOLD: float = 0.7

_KNOWN_BODYPARTS: frozenset[str] = frozenset({"tongue", "jaw"})


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class InterpolationResult:
    """Per-session v5p3 output: 7 stages + final + provenance + metadata.

    Stages map to the legacy pipeline:
    raw → xrange (x-range filter) → thr (lk gate) → drop (isolated-hi-lk
    rejection) → interp (PCHIP short-gap fill) → interp_filled (baseline
    substitution) → final (baseline subtraction).
    """

    # 7-stage arrays (all length n_frames)
    x_raw: np.ndarray
    y_raw: np.ndarray
    lk_raw: np.ndarray
    x_xrange: np.ndarray
    y_xrange: np.ndarray
    x_thr: np.ndarray
    y_thr: np.ndarray
    x_drop: np.ndarray
    y_drop: np.ndarray
    x_interp: np.ndarray
    y_interp: np.ndarray
    x_interp_filled: np.ndarray
    y_interp_filled: np.ndarray
    x_final: np.ndarray
    y_final: np.ndarray
    # Provenance masks.
    is_interp_fill: np.ndarray   # bool: where stage 4 filled a NaN.
    is_baseline_fill: np.ndarray  # bool: where stage 5 substituted (X0, Y0).
    fill_method: np.ndarray       # int8 per-frame (none/pchip/linear/baseline).
    # Baselines.
    X0: float
    Y0: float
    X0_data: float  # data-driven X0 (diagnostic; NOT fed to x_final under force=true)
    Y0_data: float
    # Scalars.
    fps: float
    n_frames: int
    center_mode: str  # long form e.g. "centered_spout_midpoint"
    baseline_stage: str = _BASELINE_SOURCE_STAGE
    interpolation_version: str = INTERPOLATION_VERSION
    bodypart: str = ""
    animal: str = ""
    date: dt.date | None = None
    # Side-convention stamp — copied from ``AnimalInfo.
    # wavesurfer_sides_match_mouse_sides`` so the writer can emit the
    # v6.8 parquet metadata without re-looking-up AnimalInfo.
    wavesurfer_sides_match_mouse_sides: bool = False
    # Cam-frame tone-onset centers used for the baseline pool — kept for
    # the optional QC NPZ sidecar only. Dataclass field name + NPZ key
    # ``reward_centers_cam`` PRESERVED per Phase 7b-light Addendum #1
    # (on-disk contract; Phase 7c-dlc-cohort-reemit will rename in
    # lockstep with cohort regeneration).
    reward_centers_cam: np.ndarray = field(default_factory=lambda: np.array([]))


# ---------------------------------------------------------------------------
# Stage helpers — direct transcriptions of the vendored cells
# ---------------------------------------------------------------------------


def _stage_xrange(
    x_raw: np.ndarray,
    y_raw: np.ndarray,
    lk_raw: np.ndarray,
    *,
    x_range_pm: float,
    x_range_source: str,
    lk_thr: float,
) -> tuple[np.ndarray, np.ndarray]:
    """NaN-out samples outside ``median(x) ± x_range_pm``.

    ``x_range_source="lk"`` computes the median over hi-lk support only
    (Knob 4, locked for legacy parity). ``"finite"`` uses all finite
    points. Falls back to finite support if the lk-gated set is empty,
    matching legacy ``compute_session_x_range`` behavior.
    """
    finite_xy = np.isfinite(x_raw) & np.isfinite(y_raw)
    if x_range_source == "lk":
        m = finite_xy & np.isfinite(lk_raw) & (lk_raw >= lk_thr)
    elif x_range_source == "finite":
        m = finite_xy
    else:
        raise ValueError(
            f"Unknown x_range_source={x_range_source!r}. Expected 'finite' or 'lk'."
        )
    if not np.any(m):
        m = finite_xy
    x_out = x_raw.copy().astype(float)
    y_out = y_raw.copy().astype(float)
    if not np.any(m):
        # All-NaN input — nothing to filter against. Return copies as-is.
        return x_out, y_out
    med_x = float(np.nanmedian(x_raw[m]))
    x_lo = med_x - float(x_range_pm)
    x_hi = med_x + float(x_range_pm)
    bad = (~np.isfinite(x_out)) | (x_out < x_lo) | (x_out > x_hi)
    x_out[bad] = np.nan
    y_out[bad] = np.nan
    return x_out, y_out


def _stage_thr(
    x_xrange: np.ndarray,
    y_xrange: np.ndarray,
    lk_raw: np.ndarray,
    *,
    lk_thr: float,
) -> tuple[np.ndarray, np.ndarray]:
    """NaN-out samples where ``lk < lk_thr`` or x/y are already NaN."""
    hi = (
        np.isfinite(lk_raw) & (lk_raw >= lk_thr)
        & np.isfinite(x_xrange) & np.isfinite(y_xrange)
    )
    x_thr = x_xrange.copy().astype(float)
    y_thr = y_xrange.copy().astype(float)
    x_thr[~hi] = np.nan
    y_thr[~hi] = np.nan
    return x_thr, y_thr


def _stage_drop(
    x_thr: np.ndarray,
    y_thr: np.ndarray,
    *,
    n_neigh: int,
    neighbor_f: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Drop hi-lk samples with fewer than ``n_neigh`` hi-lk neighbors.

    Sliding window of ±``neighbor_f`` frames around each hi-lk point,
    two monotonic pointers over the sorted hi-lk index list. O(n) —
    matches the vendored implementation.
    """
    n = len(x_thr)
    hi_idx = np.flatnonzero(np.isfinite(x_thr) & np.isfinite(y_thr))
    keep_hi = np.zeros(n, dtype=bool)
    j0 = 0
    j1 = 0
    for ii in hi_idx:
        while j0 < hi_idx.size and hi_idx[j0] < ii - neighbor_f:
            j0 += 1
        while j1 < hi_idx.size and hi_idx[j1] <= ii + neighbor_f:
            j1 += 1
        # Subtract 1 because the current sample itself is always in window.
        if (j1 - j0 - 1) >= n_neigh:
            keep_hi[ii] = True
    x_drop = np.full(n, np.nan, dtype=float)
    y_drop = np.full(n, np.nan, dtype=float)
    x_drop[keep_hi] = x_thr[keep_hi]
    y_drop[keep_hi] = y_thr[keep_hi]
    return x_drop, y_drop


def _interp_small_gaps(
    arr: np.ndarray,
    hi_mask: np.ndarray,
    max_gap_f: int,
    *,
    require_bracketed_by_hi: bool,
    method: str,
    n_side: int,
    min_total_context: int,
    fallback: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Fill NaN runs of length ``<= max_gap_f``.

    Transcribed from the vendored ``interp_small_gaps_method``. Returns
    ``(out, fill_codes)`` where ``fill_codes`` is a per-frame int8 in
    ``{0=none, 1=pchip, 2=linear}`` — allows provenance without changing
    ``out`` (parity-neutral).
    """
    out = arr.copy().astype(float)
    fill_codes = np.zeros(len(out), dtype=np.int8)
    n = len(out)

    def collect_context(left_end: int, right_end: int) -> np.ndarray:
        """Gather up to ``n_side`` hi-lk finite indices on each side."""
        lpts: list[int] = []
        i = left_end
        while i >= 0 and len(lpts) < n_side:
            if hi_mask[i] and np.isfinite(out[i]):
                lpts.append(i)
            i -= 1
        lpts = lpts[::-1]
        rpts: list[int] = []
        i = right_end
        while i < n and len(rpts) < n_side:
            if hi_mask[i] and np.isfinite(out[i]):
                rpts.append(i)
            i += 1
        return np.unique(np.array(lpts + rpts, dtype=int))

    def fill_linear(i_: int, j_: int, left_: int, right_: int) -> None:
        out[i_:j_] = np.interp(
            np.arange(i_, j_), [left_, right_], [out[left_], out[right_]]
        )
        fill_codes[i_:j_] = _FILL_METHOD_LINEAR

    i = 0
    while i < n:
        if np.isfinite(out[i]):
            i += 1
            continue

        # Gap [i, j)
        j = i
        while j < n and (not np.isfinite(out[j])):
            j += 1

        run_len = j - i
        left = i - 1
        right = j

        fillable = (
            run_len <= max_gap_f
            and left >= 0 and right < n
            and np.isfinite(out[left]) and np.isfinite(out[right])
        )
        if not fillable:
            i = j
            continue
        if require_bracketed_by_hi and not (hi_mask[left] and hi_mask[right]):
            i = j
            continue

        if method == "linear":
            fill_linear(i, j, left, right)
            i = j
            continue

        if method == "pchip":
            ctx = collect_context(left, right)
            if (left not in ctx) or (right not in ctx):
                ctx = np.unique(np.r_[ctx, [left, right]]).astype(int)
            if ctx.size < min_total_context:
                if fallback == "linear":
                    fill_linear(i, j, left, right)
                i = j
                continue
            x_ctx = ctx.astype(float)
            y_ctx = out[ctx].astype(float)
            good = np.isfinite(y_ctx)
            x_ctx = x_ctx[good]
            y_ctx = y_ctx[good]
            if x_ctx.size < min_total_context or np.unique(x_ctx).size < 2:
                if fallback == "linear":
                    fill_linear(i, j, left, right)
                i = j
                continue
            try:
                f = PchipInterpolator(x_ctx, y_ctx, extrapolate=False)
                out[i:j] = f(np.arange(i, j, dtype=float))
                fill_codes[i:j] = _FILL_METHOD_PCHIP
            except Exception:
                if fallback == "linear":
                    fill_linear(i, j, left, right)
            i = j
            continue

        raise ValueError(f"Unknown interpolation method: {method!r}")

    return out, fill_codes


def _fill_nan_with(arr: np.ndarray, fill_value: float) -> np.ndarray:
    """Return a copy with non-finite entries replaced by ``fill_value``."""
    out = arr.copy().astype(float)
    out[~np.isfinite(out)] = float(fill_value)
    return out


def _build_tone_aligned_pool_mask(
    n_frames: int,
    tone_centers_float: np.ndarray,
    fps: float,
    win_ms: tuple[float, float] = _BASELINE_POST_WIN_MS,
) -> np.ndarray:
    """Boolean mask: frames within ``win_ms`` of any tone-onset center.

    Uses rounded tone-onset frame indices (OR'ed per-tone windows),
    matching the vendored ``_build_reward_aligned_pool_mask`` byte-for-byte
    (legacy vendored helper retains its pre-Case-2 name as a citation).
    """
    w0_ms, w1_ms = float(win_ms[0]), float(win_ms[1])
    if w1_ms < w0_ms:
        raise ValueError(f"win_ms must be (start, end) with end>=start; got {win_ms}")
    w0_f = int(np.floor((w0_ms / 1000.0) * fps))
    w1_f = int(np.ceil((w1_ms / 1000.0) * fps))
    centers_i = np.round(tone_centers_float).astype(int)
    centers_i = centers_i[(centers_i >= 0) & (centers_i < n_frames)]
    mask = np.zeros(n_frames, dtype=bool)
    for c in centers_i:
        lo = max(0, c + w0_f)
        hi = min(n_frames - 1, c + w1_f)
        if hi >= lo:
            mask[lo : hi + 1] = True
    return mask


# ---------------------------------------------------------------------------
# Baseline helpers
# ---------------------------------------------------------------------------


def _compute_baseline_forced(
    animal_info: AnimalInfo, bodypart: str
) -> tuple[float, float]:
    """Read per-animal ``(x0, y0)`` from AnimalInfo.kinematics_baselines.

    Raises ``KeyError`` (via
    :meth:`AnimalInfo.get_kinematics_baseline`) if bodypart is missing.
    """
    b = animal_info.get_kinematics_baseline(bodypart)
    return float(b["x0"]), float(b["y0"])


def _compute_baseline_data_driven(
    x_base_src: np.ndarray,
    y_base_src: np.ndarray,
    lk_raw: np.ndarray,
    pool_mask: np.ndarray,
    *,
    y0_lk_thr: float,
    y0_percentile: float,
    require_finite_x: bool = _BASELINE_REQUIRE_FINITE_X,
) -> tuple[float, float]:
    """Data-driven baseline: Y0 = median(Y of lowest-percentile Y subset),
    X0 = median(X of the SAME subset).

    Simplified relative to the legacy cells (which used separate lk
    thresholds and Y-percentiles for Y0 and X0). ``interpolation-
    strategy.md`` §7 collapses these into one pool — with
    ``baseline.force=true`` (cohort default) this path is informational
    only, populating ``InterpolationResult.{X0_data, Y0_data}``.

    Intentional divergence from the legacy cells under ``force=false``:
    legacy used separate ``(lk_thr, percentile)`` pools for Y0 and X0;
    the consolidated single-pool semantics here match
    ``interpolation-strategy.md`` §7. See the 2026-04-24 Phase 7a.2
    DECISIONS entry (data-driven-baseline pool unification) for
    rationale and the forward commitment to revisit if a future
    session genuinely requires ``force=false``.
    """
    base_finite = np.isfinite(y_base_src)
    if require_finite_x:
        base_finite &= np.isfinite(x_base_src)
    pool = (
        pool_mask & base_finite
        & np.isfinite(lk_raw) & (lk_raw >= float(y0_lk_thr))
    )
    if not np.any(pool):
        return float("nan"), float("nan")
    y_pool = y_base_src[pool]
    y_cut = float(np.nanpercentile(y_pool, float(y0_percentile)))
    lowY = pool & (y_base_src <= y_cut)
    if not np.any(lowY):
        # Degenerate Y distribution — fall back to lowest-K-by-Y.
        k = max(10, int(np.ceil((float(y0_percentile) / 100.0) * y_pool.size)))
        pool_idx = np.flatnonzero(pool)
        lowK_idx = np.argsort(y_pool)[: min(k, y_pool.size)]
        lowY = np.zeros_like(pool)
        lowY[pool_idx[lowK_idx]] = True
    return (
        float(np.nanmedian(x_base_src[lowY])),
        float(np.nanmedian(y_base_src[lowY])),
    )


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def _center_mode_short(center_mode: str) -> str:
    """Strip the legacy ``"centered_"`` prefix.

    Config uses the long form (``"centered_spout_midpoint"``) to match
    legacy NPZ output dirs; Phase 4.5-lite centered parquets live under
    the short form (``"spout_midpoint"``). This normalises between them.
    """
    return center_mode[len("centered_") :] if center_mode.startswith("centered_") else center_mode


def _load_centered_df(
    manifest: SessionManifest,
    bodypart: str,
    center_mode: str,
    resolver: PathResolver,
) -> pd.DataFrame:
    """Load the Phase 4.5-lite centered DLC parquet for this session."""
    from stroke_orofacial.dlc_io.parquet import _param_sig, read_centered_parquet

    if not manifest.dlc_h5_files:
        raise FileNotFoundError(
            f"{manifest.session_id}: manifest.dlc_h5_files is empty. "
            f"Phase 7a.2 requires DLC inference output — run DLC first."
        )
    short = _center_mode_short(center_mode)
    sig = _param_sig(short, _CENTERING_LIKELIHOOD_THRESHOLD)
    parquet_dir = (
        resolver.pipeline_outputs("dlc_analysis")
        / f"centered_{short}"
        / manifest.animal
    )
    parquet_path = (
        parquet_dir
        / f"{manifest.dlc_h5_files[0].name}.intermediate.{sig}.parquet"
    )
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}/{center_mode}: Phase 4 centered parquet "
            f"missing at {parquet_path}. Emit via "
            f"scripts/run_notebook_10_phase_4_centering.py."
        )
    df = read_centered_parquet(parquet_path)
    for col in (f"{bodypart}_x", f"{bodypart}_y", f"{bodypart}_likelihood"):
        if col not in df.columns:
            raise KeyError(
                f"{manifest.session_id}/{center_mode}: centered parquet at "
                f"{parquet_path} missing column {col!r}."
            )
    return df


def _load_tone_centers_cam(
    manifest: SessionManifest,
    resolver: PathResolver,
) -> np.ndarray:
    """Return the cam-frame union of mouse-L+R tone-onset centers.

    Uses the consolidated Phase 2 licks NPZ (post-re-emit, mouse-frame,
    stamped) + cam2 alignment template. Labels are discarded — the
    baseline pool only needs the SET of tone-onset centers, and that
    set is invariant to the wavesurfer↔mouse-frame flip applied to
    labels.
    """
    from stroke_orofacial.dlc_spatial.tone_aligned import load_tone_events

    date_str = manifest.date.strftime("%Y%m%d")
    licks_path = (
        resolver.pipeline_outputs("spout_behavior")
        / "licks_and_rewards"
        / manifest.animal
        / f"{date_str}.npz"
    )
    if not licks_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}: Phase 2 licks NPZ missing at "
            f"{licks_path}. Re-emit Phase 2 (see runbooks/"
            f"reemit-phase-5-6-after-lr-fix.md) before Phase 7a.2."
        )

    # v6.8 boundary-layer invariance: ``trial_group="all"`` returns the
    # union of mouse-L and mouse-R tone-onset WS indices. The legacy
    # cells (pre-v6.8, wavesurfer-frame) concatenate ``Reward_R`` +
    # ``Reward_L`` NPZ keys (the experimenter-labeled sides; legacy
    # NPZ-key citations preserved); the consolidated Phase 2 NPZ
    # (post-v6.8, mouse-frame; post-Phase-8a.10.1 swap-fix carries
    # tone-onset content under ``Tone_<side>`` keys) concatenates
    # mouse-L + mouse-R. The UNION is set-identical across the L/R
    # flip — baseline pool-mask is bit-identical regardless of which
    # side each label sits on.
    tone_ws = load_tone_events(
        licks_path, trial_group="all",
        wavesurfer_sides_match_mouse_sides=manifest.wavesurfer_sides_match_mouse_sides,
    )
    if len(tone_ws) == 0:
        return np.array([], dtype=float)

    align_path = manifest.alignment_template
    if align_path is None or not align_path.exists():
        align_path = resolver.alignment_template_legacy_read(
            manifest.animal, manifest.date, cam="cam2",
        )
    if not align_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}: cam2 alignment template missing at "
            f"{align_path}. Run scripts/make_alignment_templates.py."
        )
    aln = np.load(str(align_path), allow_pickle=False)
    sig_camIdx__idx_ws = aln["sig_camIdx__idx_ws"]

    ws_idx = np.asarray(tone_ws, dtype=np.int64)
    ws_idx = ws_idx[(ws_idx >= 0) & (ws_idx < len(sig_camIdx__idx_ws))]
    fr = sig_camIdx__idx_ws[ws_idx].astype(float)
    return fr[np.isfinite(fr)]


# ---------------------------------------------------------------------------
# Pure-function core
# ---------------------------------------------------------------------------


def _interpolate_bodypart_core(
    df: pd.DataFrame,
    bodypart: str,
    center_mode: str,
    bodypart_params: dict[str, Any],
    reward_centers_cam: np.ndarray,
    *,
    animal_info: AnimalInfo,
    fps: float = _DEFAULT_FPS,
) -> InterpolationResult:
    """Stage-by-stage v5p3 interpolation on one session.

    Pure function — no I/O. Reads ``{bodypart}_x``, ``{bodypart}_y``,
    ``{bodypart}_likelihood`` from ``df`` and applies the 7 stages.
    ``animal_info`` is required even under ``force=false`` (we still
    stamp ``animal_id`` into the result).
    """
    if bodypart not in _KNOWN_BODYPARTS:
        raise ValueError(
            f"Unknown bodypart {bodypart!r}. Expected one of "
            f"{sorted(_KNOWN_BODYPARTS)}."
        )

    interp_cfg = bodypart_params["interpolation"]
    baseline_cfg = bodypart_params["baseline"]

    # Per-bodypart constants (from defaults.yaml dlc_kinematics.<bp>.interpolation).
    x_range_pm = float(interp_cfg["x_range_pm"])
    x_range_source = str(interp_cfg["x_range_source"])
    lk_thr = float(interp_cfg["lk_thr"])
    n_neigh = int(interp_cfg["n_neigh"])
    neighbor_ms = float(interp_cfg["neighbor_ms"])
    max_gap_ms = float(interp_cfg["max_gap_ms"])
    interp_n_side = int(interp_cfg["interp_n_side"])
    require_bracketed_by_hilk = bool(interp_cfg["require_bracketed_by_hilk"])
    # Top-level dlc_kinematics.* inherited via build_interpolated_trace.
    method = str(bodypart_params.get("interpolation_method", "pchip"))
    fallback = str(bodypart_params.get("interpolation_fallback", "linear"))
    # Legacy INTERP_MIN_TOTAL_CONTEXT locked at 6 in both vendored cells.
    interp_min_total_context = int(interp_cfg.get("interp_min_total_context", 6))

    x_raw = df[f"{bodypart}_x"].to_numpy(dtype=float).copy()
    y_raw = df[f"{bodypart}_y"].to_numpy(dtype=float).copy()
    lk_raw = df[f"{bodypart}_likelihood"].to_numpy(dtype=float).copy()
    n_frames = len(df)

    # Stage 1 — X-range filter.
    x_xrange, y_xrange = _stage_xrange(
        x_raw, y_raw, lk_raw,
        x_range_pm=x_range_pm, x_range_source=x_range_source, lk_thr=lk_thr,
    )

    # Stage 2 — likelihood threshold.
    x_thr, y_thr = _stage_thr(x_xrange, y_xrange, lk_raw, lk_thr=lk_thr)

    # Stage 3 — drop isolated hi-lk (neighbor count in ±neighbor_ms window).
    neighbor_f = max(int(round((neighbor_ms / 1000.0) * fps)), 1)
    x_drop, y_drop = _stage_drop(
        x_thr, y_thr, n_neigh=n_neigh, neighbor_f=neighbor_f,
    )

    # Stage 4 — PCHIP-fallback-linear short-gap fill.
    max_gap_f = max(int(round((max_gap_ms / 1000.0) * fps)), 1)
    hi_mask_post = np.isfinite(x_drop) & np.isfinite(y_drop)
    x_interp, x_fill = _interp_small_gaps(
        x_drop, hi_mask_post, max_gap_f,
        require_bracketed_by_hi=require_bracketed_by_hilk,
        method=method, n_side=interp_n_side,
        min_total_context=interp_min_total_context, fallback=fallback,
    )
    y_interp, y_fill = _interp_small_gaps(
        y_drop, hi_mask_post, max_gap_f,
        require_bracketed_by_hi=require_bracketed_by_hilk,
        method=method, n_side=interp_n_side,
        min_total_context=interp_min_total_context, fallback=fallback,
    )

    # Merge fill codes (x and y share the same gap structure via hi_mask_post).
    fill_method = np.where(
        x_fill != _FILL_METHOD_NONE, x_fill, y_fill
    ).astype(np.int8)
    is_interp_fill = fill_method != _FILL_METHOD_NONE

    # Baseline pool (tone-aligned on the "drop" stage).
    pool_mask = _build_tone_aligned_pool_mask(
        n_frames=n_frames, tone_centers_float=reward_centers_cam, fps=fps,
    )
    # Data-driven baseline (informational when force=true; feeds X0/Y0 when false).
    y0_lk_thr = float(baseline_cfg.get("y0_lk_thr", lk_thr))
    y0_percentile = float(baseline_cfg.get("y0_percentile", 5.0))
    X0_data, Y0_data = _compute_baseline_data_driven(
        x_drop, y_drop, lk_raw, pool_mask,
        y0_lk_thr=y0_lk_thr, y0_percentile=y0_percentile,
    )

    force_baseline = bool(baseline_cfg.get("force", True))
    if force_baseline:
        X0, Y0 = _compute_baseline_forced(animal_info, bodypart)
    else:
        if not (np.isfinite(X0_data) and np.isfinite(Y0_data)):
            raise RuntimeError(
                f"{animal_info.animal_id} data-driven baseline for "
                f"bodypart={bodypart!r} is NaN (baseline pool empty). "
                f"Set baseline.force=true + seed animals.yaml "
                f"kinematics_baselines, or re-check the session."
            )
        X0, Y0 = X0_data, Y0_data

    # Stage 5 — fill remaining NaNs with (X0, Y0).
    x_interp_filled = _fill_nan_with(x_interp, X0)
    y_interp_filled = _fill_nan_with(y_interp, Y0)
    is_baseline_fill = ~(np.isfinite(x_interp) & np.isfinite(y_interp))
    # Baseline trumps interp in the fill_method enum.
    fill_method[is_baseline_fill] = _FILL_METHOD_BASELINE

    # Stage 6 — subtract baselines for final zero-centered traces.
    x_final = x_interp_filled - X0
    y_final = y_interp_filled - Y0

    return InterpolationResult(
        x_raw=x_raw, y_raw=y_raw, lk_raw=lk_raw,
        x_xrange=x_xrange, y_xrange=y_xrange,
        x_thr=x_thr, y_thr=y_thr,
        x_drop=x_drop, y_drop=y_drop,
        x_interp=x_interp, y_interp=y_interp,
        x_interp_filled=x_interp_filled, y_interp_filled=y_interp_filled,
        x_final=x_final, y_final=y_final,
        is_interp_fill=is_interp_fill,
        is_baseline_fill=is_baseline_fill,
        fill_method=fill_method,
        X0=float(X0), Y0=float(Y0),
        X0_data=float(X0_data), Y0_data=float(Y0_data),
        fps=float(fps),
        n_frames=int(n_frames),
        center_mode=str(center_mode),
        bodypart=bodypart,
        animal=animal_info.animal_id,
        wavesurfer_sides_match_mouse_sides=bool(
            animal_info.wavesurfer_sides_match_mouse_sides
        ),
        reward_centers_cam=reward_centers_cam,
    )


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def _write_parquet(result: InterpolationResult, path: Path) -> None:
    """Write the canonical per-frame parquet.

    Schema locked by ``interpolation-strategy.md`` §2c:

    - 7 columns: ``frame_idx`` (int64), ``x_final`` / ``y_final`` /
      ``likelihood_raw`` (float64), ``is_interp_fill`` /
      ``is_baseline_fill`` (bool), ``fill_method`` (int8 enum per
      :data:`_FILL_METHOD_NONE`/``_PCHIP``/``_LINEAR``/``_BASELINE``).
    - 9 file-level metadata keys: ``X0``, ``Y0``, ``fps``, ``n_frames``,
      ``center_mode``, ``baseline_stage``, ``interpolation_version``,
      plus the v6.8 side-convention stamp pair
      (``wavesurfer_sides_match_mouse_sides``,
      ``side_convention_version``).

    ``bodypart``, ``animal``, ``date`` are NOT emitted as file metadata
    — they are already encoded in the parquet path
    (``interpolated_traces/<bodypart>/<animal>/<YYYYMMDD>.parquet``);
    duplicating them in metadata is redundant.

    Diagnostic scalars ``X0_data``/``Y0_data`` (data-driven baseline
    estimates computed even under ``baseline.force=true``) live in the
    optional ``.qc.npz`` sidecar per :func:`_write_qc_npz`, not here.

    Read metadata back via
    ``pq.ParquetFile(path).metadata.metadata``.
    """
    df = pd.DataFrame({
        "frame_idx": np.arange(result.n_frames, dtype=np.int64),
        "x_final": result.x_final.astype(np.float64),
        "y_final": result.y_final.astype(np.float64),
        "likelihood_raw": result.lk_raw.astype(np.float64),
        "is_interp_fill": result.is_interp_fill.astype(bool),
        "is_baseline_fill": result.is_baseline_fill.astype(bool),
        "fill_method": result.fill_method.astype(np.int8),
    })
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta_updates = {
        b"X0": repr(result.X0).encode(),
        b"Y0": repr(result.Y0).encode(),
        b"fps": repr(result.fps).encode(),
        b"n_frames": str(result.n_frames).encode(),
        b"center_mode": result.center_mode.encode(),
        b"baseline_stage": result.baseline_stage.encode(),
        b"interpolation_version": result.interpolation_version.encode(),
        SIDE_CONVENTION_MATCH_KEY.encode(): repr(
            result.wavesurfer_sides_match_mouse_sides
        ).encode(),
        SIDE_CONVENTION_VERSION_KEY.encode(): str(SIDE_CONVENTION_VERSION).encode(),
    }
    existing = table.schema.metadata or {}
    merged = {**{bytes(k): bytes(v) for k, v in existing.items()}, **meta_updates}
    table = table.replace_schema_metadata(merged)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, str(path), compression="snappy")


def _write_qc_npz(result: InterpolationResult, path: Path) -> None:
    """Write the optional intermediate-stages QC NPZ sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(path),
        x_raw=result.x_raw, y_raw=result.y_raw, lk_raw=result.lk_raw,
        x_xrange=result.x_xrange, y_xrange=result.y_xrange,
        x_thr=result.x_thr, y_thr=result.y_thr,
        x_drop=result.x_drop, y_drop=result.y_drop,
        x_interp=result.x_interp, y_interp=result.y_interp,
        x_interp_filled=result.x_interp_filled,
        y_interp_filled=result.y_interp_filled,
        x_final=result.x_final, y_final=result.y_final,
        is_interp_fill=result.is_interp_fill,
        is_baseline_fill=result.is_baseline_fill,
        fill_method=result.fill_method,
        X0=np.float64(result.X0), Y0=np.float64(result.Y0),
        X0_data=np.float64(result.X0_data), Y0_data=np.float64(result.Y0_data),
        fps=np.float64(result.fps), n_frames=np.int64(result.n_frames),
        center_mode=np.array(result.center_mode),
        baseline_stage=np.array(result.baseline_stage),
        interpolation_version=np.array(result.interpolation_version),
        bodypart=np.array(result.bodypart),
        animal=np.array(result.animal),
        reward_centers_cam=result.reward_centers_cam.astype(np.float64),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_interpolated_trace(
    manifest: SessionManifest,
    bodypart: Literal["tongue", "jaw"],
    resolver: PathResolver,
    params: dict[str, Any] | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
    emit_qc_bundle: bool = False,
    animal_info: AnimalInfo | None = None,
) -> Path | None:
    """Build per-frame interpolated trace for one bodypart in one session.

    Writes ``<outputs>/dlc_analysis/interpolated_traces/<bodypart>/
    <animal>/<YYYYMMDD>.parquet`` (always) and optionally
    ``...<YYYYMMDD>.qc.npz``. Returns the parquet path, or None if the
    session is excluded for ``dlc.kinematics.<bodypart>``.

    Raises
    ------
    ValueError
        If ``bodypart`` not in ``{"tongue", "jaw"}`` or ``overwrite``
        not in ``{"skip", "force"}``.
    KeyError
        If ``animal_info.kinematics_baselines`` lacks ``bodypart``
        under ``baseline.force=true``.
    FileNotFoundError
        If required upstream artifacts are missing (centered parquet,
        Phase 2 licks NPZ, cam2 alignment template).
    """
    if bodypart not in _KNOWN_BODYPARTS:
        raise ValueError(
            f"Unknown bodypart {bodypart!r}. Expected one of "
            f"{sorted(_KNOWN_BODYPARTS)}."
        )
    if overwrite not in ("skip", "force"):
        raise ValueError(f"overwrite must be 'skip' or 'force'; got {overwrite!r}.")

    # Exclusion check (Phase 7-pre schema). Trust the manifest if it was
    # built with the right context; re-check here as a belt-and-braces.
    if animal_info is None:
        animal_info = get_animal(manifest.animal)
    if manifest.excluded:
        return None
    excluded, _reason = animal_info.is_excluded(
        manifest.date, analysis_context=f"dlc.kinematics.{bodypart}",
    )
    if excluded:
        return None

    # Params.
    if params is None:
        params = load_defaults()
    kinematics_cfg = params.get("dlc_kinematics")
    if kinematics_cfg is None:
        raise KeyError(
            "configs/defaults.yaml missing 'dlc_kinematics:' block "
            "(Phase 7a.2 §7 seed)."
        )
    if bodypart not in kinematics_cfg:
        raise KeyError(
            f"configs/defaults.yaml dlc_kinematics missing {bodypart!r} block."
        )
    bodypart_params = dict(kinematics_cfg[bodypart])
    # Inherit top-level method/fallback for the core helper's one-lookup
    # convenience.
    bodypart_params.setdefault(
        "interpolation_method", kinematics_cfg.get("interpolation_method", "pchip"),
    )
    bodypart_params.setdefault(
        "interpolation_fallback",
        kinematics_cfg.get("interpolation_fallback", "linear"),
    )
    center_mode = str(bodypart_params["center_mode"])

    out_path = resolver.interpolated_trace(
        bodypart=bodypart, animal=manifest.animal, date=manifest.date,
    )
    if overwrite == "skip" and out_path.exists():
        return out_path

    fps = float((params.get("alignment") or {}).get("fps_cam", _DEFAULT_FPS))

    df = _load_centered_df(manifest, bodypart, center_mode, resolver)
    reward_centers_cam = _load_tone_centers_cam(manifest, resolver)

    result = _interpolate_bodypart_core(
        df=df,
        bodypart=bodypart,
        center_mode=center_mode,
        bodypart_params=bodypart_params,
        reward_centers_cam=reward_centers_cam,
        animal_info=animal_info,
        fps=fps,
    )
    result.date = manifest.date

    _write_parquet(result, out_path)
    if emit_qc_bundle:
        qc_path = resolver.interpolated_trace(
            bodypart=bodypart, animal=manifest.animal, date=manifest.date,
            variant="qc_npz",
        )
        _write_qc_npz(result, qc_path)
    return out_path


def build_interpolated_trace_by_animal_date(
    animal: str,
    date: dt.date,
    bodypart: Literal["tongue", "jaw"],
    resolver: PathResolver,
    **kwargs: Any,
) -> Path | None:
    """Build the trace from ``(animal, date)`` — manifests internally.

    Loads ``AnimalInfo`` via :func:`get_animal`, builds a
    ``SessionManifest`` with ``analysis_context="dlc.kinematics.<bp>"``,
    and forwards to :func:`build_interpolated_trace`.
    """
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context=f"dlc.kinematics.{bodypart}",
    )
    kwargs.setdefault("animal_info", animal_info)
    return build_interpolated_trace(manifest, bodypart, resolver, **kwargs)
