"""Phase 7a.6 — Mean/SEM visual gate (bodypart-parametric).

Ported from the canonical tongue + jaw notebook master cells, vendored
byte-identically at:

- ``docs/legacy_snippets/tongue_mean_sem_section.py`` cell 31 (722L,
  sha256 ``dbdb19599bd7f2194c20d5ddc507e561de6e0799c6ee19e7b7dd1d38b785aab0``).
- ``docs/legacy_snippets/jaw_mean_sem_section.py`` cell 30 (722L,
  sha256 ``9a45dd48eebcde6b634765ba1193fc7d9d642b6a142dcd5f2182cd5384b641ec``;
  byte-near-identical to tongue cell 31 — only ``CENTER_MODE`` diverges
  between bodyparts; KNOBS audit (.scratch_7a6/_knobs_diff.py output
  2026-05-01) confirms 33 of 34 knobs shared verbatim).

Architecture (Q2 locked 2026-05-01): bodypart-parametric — single module
takes ``bodypart: Literal["tongue", "jaw"]`` and threads it through all
public entry points + filename + axis-label tokens + path resolver. No
per-bodypart sibling modules.

This commit (C4.1) ports the master cell's 4 plot families:

1. ``individual_sessions``  — per-session 2x2 mean+SEM (Y/X × L/R).
2. ``trial_overlays``       — per-session 2x2 with all individual trials
   overlayed faintly under the mean+SEM line.
3. ``session_overlays``     — cohort: per-mouse cross-session overlay
   colored by ``rel_day`` (pre = grey, post = plasma); 4 PNGs (Y/X × L/R)
   per (animal, window).
4. ``binned_overlays``      — cohort: same shape but session means
   aggregated into ``rel_day`` bins from ``animals.yaml`` ``bin_days``.

The ``mean_xy_overlays`` family (cells 45/32 trace + 47+48/34 video) ships
in C4.2.

Each public ``build_*`` follows the 7a.x convention: takes
``(animal, date, resolver)`` (per-session) or ``(animal, resolver)``
(cohort), accepts an optional ``params`` block (loaded from
``configs/defaults.yaml`` ``dlc_kinematics.mean_sem_visual.*``), and
returns the emitted Path(s) or None.

Consumes from prior phases (no algorithmic changes to those modules):

- Phase 7a.2 ``interpolated_trace`` parquet (per-frame ``x_final`` /
  ``y_final`` + ``fps`` / ``n_frames`` metadata).
- ``spout_behavior`` ``licks_and_rewards`` NPZ + cam2 alignment template
  for reward-frame derivation (mirrors the 7a.3 V3 Task 5.0 pattern).
- ``configs/animals.yaml`` per-mouse ``stroke_date`` + ``bin_days``
  (replaces legacy inline ``MOUSE_SPECS`` dict).
- ``configs/defaults.yaml`` ``dlc_kinematics.mean_sem_visual`` block
  (replaces legacy inline KNOBS section).

Phase 7a.6 Q-locks honored (kickoff 2026-05-01):

- Q6: lowercase ``{bodypart}`` only — ``mean_sem_visual_dir`` resolver
  enforces this; legacy ``mouse_Tongue_kinematics`` capital-T bug not
  replicated.
- Q7: per-window ``rewardAligned_{pre}pre-{post}post/`` subdir layout
  uniformly for both bodyparts (resolver-enforced).

Backend: ``matplotlib`` ``Agg`` (headless cohort runs + tests).
"""

from __future__ import annotations

# matplotlib backend MUST be set before any pyplot import. Required for
# headless cohort renders (no display) and to keep test runs deterministic
# across CI vs local.
import matplotlib

matplotlib.use("Agg")

import datetime  # noqa: E402  (ordering after backend setup is intentional)
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Literal, Sequence  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from stroke_orofacial.animals import AnimalInfo, get_animal  # noqa: E402
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.manifest import SessionManifest, build_manifest  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402

MEAN_SEM_VISUAL_VERSION = "v7a.6"

# Family identifiers handled by this commit (C4.1). C4.2 adds
# ``mean_xy_overlays``.
PLOT_FAMILIES_C4_1: tuple[str, ...] = (
    "individual_sessions",
    "trial_overlays",
    "session_overlays",
    "binned_overlays",
)
_PER_SESSION_FAMILIES: frozenset[str] = frozenset(
    {"individual_sessions", "trial_overlays"}
)
_COHORT_FAMILIES: frozenset[str] = frozenset(
    {"session_overlays", "binned_overlays"}
)

# Per-bodypart axis-label tokens. Matches legacy ``Tongue X (px)`` /
# ``Jaw X (px)`` axis labels.
_AXIS_LABEL = {"tongue": "Tongue", "jaw": "Jaw"}

_KNOWN_BODYPARTS = ("tongue", "jaw")


# ===========================================================================
# Public dataclasses
# ===========================================================================


@dataclass(frozen=True)
class SessionAggregates:
    """Per-(animal, date, bodypart, window) aggregated arrays.

    Mirrors the per-session dict the legacy main loop builds (lines 676-691
    of ``tongue_mean_sem_section.py`` cell 31). Frozen to avoid accidental
    mutation when the same aggregates are reused across plot families.

    Conventions:

    - ``Ayl`` / ``Ayr`` / ``Axl`` / ``Axr`` = stacked per-trial reward-
      aligned snippets (rows = trials, columns = time bins). Y vs X is the
      DLC pixel axis; L vs R is the mouse-side reward.
    - ``myl`` / ``syl`` / ... = column mean / SEM across trials. NaN-aware
      via :func:`_mean_sem` (matches legacy ``mean_sem``).
    - ``rel_day = None`` if ``USE_STROKE_ALIGNMENT`` is off OR the animal
      has no ``stroke_date``. Otherwise integer days from the animal's
      stroke_date (last pre-stroke session = day 0).
    - ``legend`` = ``f"d{rel_day:+d}"`` (e.g. ``"d-6"``, ``"d0"``,
      ``"d+5"``) when ``rel_day`` is set, else the date as ``YYYYMMDD``.
    """

    animal: str
    date: datetime.date
    bodypart: str
    fps: float
    n_frames: int
    pre_ms: float
    post_ms: float
    pre_f: int
    post_f: int
    t_ms: np.ndarray            # shape (T,)
    n_L: int
    n_R: int
    Ayl: np.ndarray = field(repr=False)   # (n_L, T)
    Ayr: np.ndarray = field(repr=False)
    Axl: np.ndarray = field(repr=False)
    Axr: np.ndarray = field(repr=False)
    myl: np.ndarray = field(repr=False)
    syl: np.ndarray = field(repr=False)
    myr: np.ndarray = field(repr=False)
    syr: np.ndarray = field(repr=False)
    mxl: np.ndarray = field(repr=False)
    sxl: np.ndarray = field(repr=False)
    mxr: np.ndarray = field(repr=False)
    sxr: np.ndarray = field(repr=False)
    rel_day: int | None
    legend: str
    interp_version: str
    source_path: Path


@dataclass(frozen=True)
class CohortAggregates:
    """Cross-session aggregated arrays for one ``(animal, bodypart, window)``.

    Aggregates the per-session arrays + cohort-level axis limits + day-bin
    layout. Returned by :func:`build_cohort_aggregates` and consumed by
    every plot family in this module:

    - Per-session families read ``y_lim`` / ``x_lim`` (mean+SEM extents)
      and ``trial_y_lim`` / ``trial_x_lim`` (percentile-based, used by
      ``trial_overlays`` only) so per-session figures share a uniform
      axis across the cohort.
    - Cohort families consume the ``sessions`` list directly.
    - ``binned_overlays`` reuses ``bins`` + ``binned`` (precomputed at
      cohort-build time; if no ``stroke_date`` available the binner is
      skipped and these are empty).
    """

    bodypart: str
    animal: str
    pre_ms: float
    post_ms: float
    pre_f: int
    post_f: int
    fps: float
    t_ms: np.ndarray = field(repr=False)
    sessions: list[SessionAggregates] = field(repr=False)
    y_lim: tuple[float, float]
    x_lim: tuple[float, float]
    trial_y_lim: tuple[float, float]
    trial_x_lim: tuple[float, float]
    bin_days: int
    bins: list[tuple[int, int]]
    binned: list[dict[str, Any]] = field(repr=False)
    cam: str
    interp_version: str
    suffix: str    # e.g. "20250307-20250406_100pre-1000post_strokeD0_20250313_both"


# ===========================================================================
# Helpers — direct ports of the master cell helper functions
# ===========================================================================


def _yyyymmdd_to_date(s: str) -> datetime.date:
    return datetime.datetime.strptime(s, "%Y%m%d").date()


def _dlabel(rel_day: int) -> str:
    """Match legacy ``dlabel``: ``"d0"`` for 0, ``"d+5"`` / ``"d-6"`` else."""
    if rel_day == 0:
        return "d0"
    return f"d{rel_day:+d}"


def _mean_sem(A: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Column-wise NaN-aware mean + SEM. Direct port of legacy ``mean_sem``.

    SEM denominator = sqrt(count of finite per column). Columns with zero
    finite samples get NaN both in mean and SEM (legacy behavior).
    """
    A = np.asarray(A, float)
    if A.size == 0:
        T = A.shape[1] if A.ndim == 2 else 0
        return np.full((T,), np.nan), np.full((T,), np.nan)
    m = np.nanmean(A, axis=0)
    denom = np.sqrt(np.sum(np.isfinite(A), axis=0))
    s = np.nanstd(A, axis=0) / np.where(denom == 0, np.nan, denom)
    return m, s


def _snippet(
    arr: np.ndarray, c: int, pre_f: int, post_f: int,
) -> np.ndarray:
    """Extract ``arr[c-pre_f : c+post_f+1]`` with NaN-pad on out-of-range."""
    T = pre_f + post_f + 1
    lo = c - pre_f
    hi = c + post_f
    out = np.full(T, np.nan, dtype=float)
    src_lo = max(lo, 0)
    src_hi = min(hi, len(arr) - 1)
    if src_hi < src_lo:
        return out
    dst_lo = src_lo - lo
    dst_hi = dst_lo + (src_hi - src_lo)
    out[dst_lo : dst_hi + 1] = arr[src_lo : src_hi + 1]
    return out


def _stack_snippets(
    arr: np.ndarray, centers: Sequence[int], pre_f: int, post_f: int,
) -> np.ndarray:
    """Stack :func:`_snippet` calls into a (n_centers, T) array."""
    if len(centers) == 0:
        return np.zeros((0, pre_f + post_f + 1), dtype=float)
    return np.stack(
        [_snippet(arr, int(c), pre_f, post_f) for c in centers], axis=0,
    )


def _finite_minmax(arrs: Sequence[np.ndarray | None]) -> tuple[float, float]:
    """Min/max across the finite values in any of ``arrs``."""
    vals = []
    for a in arrs:
        if a is None:
            continue
        v = np.asarray(a).ravel()
        v = v[np.isfinite(v)]
        if v.size:
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    v = np.concatenate(vals)
    return float(np.min(v)), float(np.max(v))


def _pad_axis_limits(
    lo: float, hi: float, frac: float = 0.05,
) -> tuple[float, float]:
    """Symmetric fractional padding around ``[lo, hi]``. Singleton → ±1."""
    if (not np.isfinite(lo)) or (not np.isfinite(hi)):
        return lo, hi
    if hi == lo:
        return lo - 1.0, hi + 1.0
    d = (hi - lo) * frac
    return lo - d, hi + d


def _finite_percentile_range(
    arrs: Sequence[np.ndarray | None],
    pct_lo: float = 1.0,
    pct_hi: float = 99.0,
) -> tuple[float, float]:
    """Percentile range across finite values. Used by trial-overlay axes."""
    vals = []
    for a in arrs:
        if a is None:
            continue
        v = np.asarray(a).ravel()
        v = v[np.isfinite(v)]
        if v.size:
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    v = np.concatenate(vals)
    return (
        float(np.nanpercentile(v, pct_lo)),
        float(np.nanpercentile(v, pct_hi)),
    )


def _overlay_colors_pre_grey_post_cmap(
    sessions: Sequence[SessionAggregates],
    cmap_name: str = "plasma",
    pre_color: str = "0.3",
) -> list[Any]:
    """Color per session for the cross-session overlay.

    - rel_day == None for any session → fall back to plain colormap sweep
      across all sessions.
    - rel_day <= 0 → ``pre_color`` (default grey).
    - rel_day >= 1 → colormap-sampled value, where post sessions are
      sampled uniformly from 0 to 1 along the colormap.
    """
    cmap = plt.get_cmap(cmap_name)

    if any(s.rel_day is None for s in sessions):
        return [
            cmap(i / max(1, len(sessions) - 1))
            for i in range(len(sessions))
        ]

    post_idx = [
        i for i, s in enumerate(sessions)
        if s.rel_day is not None and s.rel_day >= 1
    ]
    n_post = len(post_idx)

    colors: list[Any] = [None] * len(sessions)
    for i, s in enumerate(sessions):
        if s.rel_day is not None and s.rel_day <= 0:
            colors[i] = pre_color
    for j, i in enumerate(post_idx):
        colors[i] = cmap(j / max(1, n_post - 1))
    return colors


# --- day-binning helpers (legacy lines 274-367) ---


def _make_rel_day_bins(
    rel_days: np.ndarray, bin_size: int,
) -> list[tuple[int, int]]:
    """Same anchor convention as legacy: bins extend from 0 backward / 1 forward.

    Pre-stroke bins are inclusive of 0; post-stroke bins start at 1. Bin
    width = ``bin_size`` (read from ``AnimalInfo.bin_days``).
    """
    rel_days = np.asarray(rel_days, float)
    rel_days = rel_days[np.isfinite(rel_days)]
    if rel_days.size == 0:
        return []

    B = int(max(1, bin_size))
    mn = int(np.floor(rel_days.min()))
    mx = int(np.ceil(rel_days.max()))

    bins: list[tuple[int, int]] = []

    # pre bins (<=0)
    pre_end = 0
    pre_start = pre_end - (B - 1)
    while pre_start > mn:
        pre_end -= B
        pre_start = pre_end - (B - 1)

    lo = pre_start
    hi = lo + (B - 1)
    while hi <= 0:
        bins.append((lo, hi))
        lo += B
        hi += B

    # post bins (>=1)
    lo = 1
    hi = lo + (B - 1)
    while lo <= mx:
        bins.append((lo, hi))
        lo += B
        hi += B

    return bins


def _bin_label(lo: int, hi: int) -> str:
    return f"{lo}..{hi}"


def _bin_center(lo: int, hi: int) -> float:
    return 0.5 * (lo + hi)


def _assign_to_bin(
    rel_day: int, bins: Sequence[tuple[int, int]],
) -> tuple[int, int] | None:
    rd = int(rel_day)
    for lo, hi in bins:
        if lo <= rd <= hi:
            return (lo, hi)
    return None


def _color_for_bin(
    lo: int, hi: int, post_max: float | None,
    cmap_name: str = "plasma", pre_color: str = "0.3",
) -> Any:
    cen = _bin_center(lo, hi)
    if cen <= 0:
        return pre_color
    cmap = plt.get_cmap(cmap_name)
    if (post_max is None) or (not np.isfinite(post_max)) or (post_max <= 1):
        return cmap(0.85)
    u = (float(cen) - 1.0) / max(1.0, float(post_max) - 1.0)
    u = float(np.clip(u, 0.0, 1.0))
    return cmap(u)


def _compute_binned(
    sessions: Sequence[SessionAggregates],
    bins: Sequence[tuple[int, int]],
) -> list[dict[str, Any]]:
    """Aggregate per-session means (column mean across sessions in a bin).

    Returned list is sorted by ``bin_center``. Each entry is a dict with
    ``bin_lo`` / ``bin_hi`` / ``bin_label`` / ``bin_center`` /
    ``n_sessions`` / ``sessions`` (list of date YYYYMMDD strings) plus
    aggregated arrays ``myl`` / ``syl`` / ``myr`` / ``syr`` / ``mxl`` /
    ``sxl`` / ``mxr`` / ``sxr`` (each shape ``(T,)``). The SEM here is
    computed across SESSIONS within the bin (population SD / sqrt(n)),
    matching legacy ``compute_binned``.
    """
    groups: dict[tuple[int, int], list[SessionAggregates]] = {}
    for s in sessions:
        if s.rel_day is None or (not np.isfinite(s.rel_day)):
            continue
        b = _assign_to_bin(int(s.rel_day), bins)
        if b is None:
            continue
        groups.setdefault(b, []).append(s)

    out: list[dict[str, Any]] = []
    for (lo, hi), grp in sorted(
        groups.items(),
        key=lambda kv: _bin_center(kv[0][0], kv[0][1]),
    ):
        for_key: dict[str, np.ndarray] = {}
        # ``getattr`` walks the SessionAggregates fields to keep parity
        # with legacy's dict-keyed aggregator.
        for key_m, key_s in [
            ("myl", "syl"),
            ("myr", "syr"),
            ("mxl", "sxl"),
            ("mxr", "sxr"),
        ]:
            M = np.vstack(
                [np.asarray(getattr(g, key_m), float) for g in grp],
            )
            mu = np.nanmean(M, axis=0)
            sem = np.nanstd(M, axis=0) / np.sqrt(max(1, M.shape[0]))
            for_key[key_m] = mu
            for_key[key_s] = sem

        out.append(
            dict(
                bin_lo=int(lo),
                bin_hi=int(hi),
                bin_label=_bin_label(int(lo), int(hi)),
                bin_center=float(_bin_center(int(lo), int(hi))),
                n_sessions=len(grp),
                sessions=[g.date.strftime("%Y%m%d") for g in grp],
                **for_key,
            ),
        )
    return out


# ===========================================================================
# Reward-events derivation (mirror tongue_pertrial._derive_trial_events_*)
# ===========================================================================


def _derive_reward_events_for_bodypart(
    bodypart: str,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    manifest: SessionManifest,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Return ``(centers_L, centers_R, n_frames)`` for one session.

    Bodypart-parametric mirror of
    :func:`stroke_orofacial.dlc_kinematics.tongue_pertrial._derive_trial_events_from_spout_behavior`,
    but returning per-side cam-frame index arrays directly (matching the
    legacy NPZ ``Z["fr_reward_mouseL"]`` / ``Z["fr_reward_mouseR"]``
    semantics) instead of the trial-event list. ``n_frames`` is read from
    the consolidated parquet's metadata so the WS→cam translator can
    validate every reward index lies in range.

    Parameters
    ----------
    bodypart : {"tongue", "jaw"}
        Which 7a.2 parquet to read for n_frames metadata. Functionally
        the rewards are session-level (not bodypart-specific), but we
        pin to the same bodypart's parquet for invariant validation.
    animal, date, resolver, manifest
        Standard 7a.x signature.

    Returns
    -------
    centers_L : np.ndarray of int
        Cam-frame indices for mouse-LEFT rewards, sorted.
    centers_R : np.ndarray of int
        Cam-frame indices for mouse-RIGHT rewards, sorted.
    n_frames : int
        Cam-frame count for the session (parquet metadata).
    """
    parquet_path = resolver.interpolated_trace(
        bodypart=bodypart, animal=animal, date=date,
    )
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"7a.2 {bodypart} interpolated_traces parquet missing for "
            f"{animal}/{date.isoformat()}: expected at {parquet_path}. "
            f"Run build_interpolated_trace first.",
        )
    schema = pq.read_schema(parquet_path)
    raw_meta = schema.metadata or {}
    n_frames_meta = raw_meta.get(b"n_frames")
    if n_frames_meta is None:
        raise ValueError(
            f"7a.2 {bodypart} parquet at {parquet_path} missing "
            f"'n_frames' metadata key (expected per the 7a.2 schema lock).",
        )
    n_frames = int(n_frames_meta)

    # Spout_behavior licks_and_rewards NPZ path (no dedicated PathResolver
    # helper as of Phase 7a.6; pattern matches 7a.3 V3 Task 5.0).
    date_str = date.strftime("%Y%m%d")
    licks_path = (
        resolver.pipeline_outputs("spout_behavior")
        / "licks_and_rewards"
        / animal
        / f"{date_str}.npz"
    )

    align_path = manifest.alignment_template
    if align_path is None or not align_path.exists():
        align_path = resolver.alignment_template(animal, date, cam="cam2")
    if not align_path.exists():
        raise FileNotFoundError(
            f"{animal}/{date_str}: cam2 alignment template missing at "
            f"{align_path}. Run scripts/make_alignment_templates.py.",
        )

    from stroke_orofacial.alignment.templates import load_alignment_template
    from stroke_orofacial.dlc_spatial.reward_aligned import (
        load_reward_events,
        ws_samples_to_frame_indices,
    )

    aln = load_alignment_template(align_path)
    sig_camIdx__idx_ws = aln["sig_camIdx__idx_ws"]

    centers: dict[str, list[int]] = {"L": [], "R": []}
    for side in ("L", "R"):
        ws_idx = load_reward_events(
            licks_path, trial_group=side,
            wavesurfer_sides_match_mouse_sides=(
                manifest.wavesurfer_sides_match_mouse_sides
            ),
        )
        if len(ws_idx) == 0:
            continue
        cam_frames = ws_samples_to_frame_indices(
            ws_idx, sig_camIdx__idx_ws, n_cam_frames=n_frames,
        )
        for f in cam_frames:
            if f < 0:
                continue  # invalid translation; legacy `centers >= 0` filter
            if f >= n_frames:
                raise ValueError(
                    f"{animal}/{date_str}: reward_frame_idx={f} >= n_frames"
                    f"={n_frames} after WS→cam translation. The alignment "
                    f"LUT may be out of sync with the {bodypart} parquet's "
                    f"n_frames metadata.",
                )
            centers[side].append(int(f))

    return (
        np.array(sorted(centers["L"]), dtype=int),
        np.array(sorted(centers["R"]), dtype=int),
        n_frames,
    )


# ===========================================================================
# Per-session loader
# ===========================================================================


def _load_session_aggregates(
    bodypart: str,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    pre_ms: float,
    post_ms: float,
    animal_info: AnimalInfo | None = None,
) -> SessionAggregates:
    """Build per-session aggregates from 7a.2 parquet + spout_behavior rewards.

    Mirrors lines 646-691 of the legacy main loop (vendored ``cell 31``).

    The 7a.2 parquet supplies ``x_final`` / ``y_final`` arrays + ``fps`` /
    ``n_frames`` metadata. Reward centers per side come from
    spout_behavior via :func:`_derive_reward_events_for_bodypart`. Trial
    snippets are stacked at frame resolution; ``t_ms`` mirrors legacy
    ``np.arange(-pre_f, post_f + 1) * (1000 / fps)`` exactly.

    rel_day / legend default to ``None`` / ``YYYYMMDD`` if no
    ``stroke_date`` is configured for the animal. Otherwise computed from
    :meth:`AnimalInfo.day_relative_to_stroke`.
    """
    if bodypart not in _KNOWN_BODYPARTS:
        raise ValueError(
            f"bodypart must be one of {_KNOWN_BODYPARTS}; got {bodypart!r}",
        )

    if animal_info is None:
        try:
            animal_info = get_animal(animal)
        except (KeyError, FileNotFoundError):
            animal_info = None

    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context=f"dlc.kinematics.{bodypart}",
    )

    parquet_path = resolver.interpolated_trace(
        bodypart=bodypart, animal=animal, date=date,
    )
    table = pq.read_table(parquet_path)
    raw_meta = table.schema.metadata or {}

    fps = float(raw_meta[b"fps"].decode())
    n_frames = int(raw_meta[b"n_frames"].decode())
    interp_version = raw_meta.get(
        b"interpolation_version", b"unknown",
    ).decode()

    df = table.to_pandas()
    x_final = df["x_final"].to_numpy(dtype=float)
    y_final = df["y_final"].to_numpy(dtype=float)

    centers_L, centers_R, _ = _derive_reward_events_for_bodypart(
        bodypart, animal, date, resolver, manifest,
    )

    pre_f = int(round((pre_ms / 1000.0) * fps))
    post_f = int(round((post_ms / 1000.0) * fps))
    t_ms = np.arange(-pre_f, post_f + 1) * (1000.0 / fps)

    Ayl = _stack_snippets(y_final, centers_L, pre_f, post_f)
    Ayr = _stack_snippets(y_final, centers_R, pre_f, post_f)
    Axl = _stack_snippets(x_final, centers_L, pre_f, post_f)
    Axr = _stack_snippets(x_final, centers_R, pre_f, post_f)

    myl, syl = _mean_sem(Ayl)
    myr, syr = _mean_sem(Ayr)
    mxl, sxl = _mean_sem(Axl)
    mxr, sxr = _mean_sem(Axr)

    rel_day: int | None = None
    legend = date.strftime("%Y%m%d")
    if animal_info is not None and animal_info.stroke_date is not None:
        rel_day = int(animal_info.day_relative_to_stroke(date))
        legend = _dlabel(rel_day)

    return SessionAggregates(
        animal=animal,
        date=date,
        bodypart=bodypart,
        fps=fps,
        n_frames=n_frames,
        pre_ms=float(pre_ms),
        post_ms=float(post_ms),
        pre_f=pre_f,
        post_f=post_f,
        t_ms=t_ms,
        n_L=len(centers_L),
        n_R=len(centers_R),
        Ayl=Ayl, Ayr=Ayr, Axl=Axl, Axr=Axr,
        myl=myl, syl=syl, myr=myr, syr=syr,
        mxl=mxl, sxl=sxl, mxr=mxr, sxr=sxr,
        rel_day=rel_day,
        legend=legend,
        interp_version=interp_version,
        source_path=parquet_path,
    )


# ===========================================================================
# Cohort builder
# ===========================================================================


def _eligible_dates(
    animal: str,
    bodypart: str,
    resolver: PathResolver,
    *,
    animal_info: AnimalInfo | None = None,
    prepost_mode: str = "both",
    rel_day_range: tuple[int, int] | None = None,
) -> list[datetime.date]:
    """Filtered chronological list of dates with a 7a.2 parquet + included.

    Mirrors the legacy date-filtering logic (lines 574-618 of vendored
    cell 31): keeps dates with an interpolated_trace parquet on disk,
    drops excluded sessions per ``animal_info.is_excluded``, applies
    ``PREPOST_MODE`` / ``REL_DAY_RANGE`` filtering, and sorts
    chronologically (or by rel_day if a stroke_date is set).
    """
    if animal_info is None:
        try:
            animal_info = get_animal(animal)
        except (KeyError, FileNotFoundError):
            animal_info = None

    if animal_info is not None:
        d0 = animal_info.session_start
        d1 = animal_info.session_end
    else:
        # Fall back to the 7a.2 parquet inventory if no animals.yaml entry.
        d0 = datetime.date(2025, 1, 1)
        d1 = datetime.date(2026, 12, 31)

    parquet_dir = (
        resolver.pipeline_outputs(subdir="dlc_analysis")
        / "interpolated_traces"
        / bodypart
        / animal
    )
    if not parquet_dir.exists():
        return []

    available_dates: set[datetime.date] = set()
    for p in parquet_dir.glob("*.parquet"):
        try:
            d = _yyyymmdd_to_date(p.stem)
        except ValueError:
            continue
        if d0 <= d <= d1:
            available_dates.add(d)

    dates = sorted(available_dates)

    if animal_info is not None:
        # Per-animal exclusions for the analysis context.
        ctx = f"dlc.kinematics.{bodypart}.mean_sem_visual"
        kept: list[datetime.date] = []
        for d in dates:
            excluded, _reason = animal_info.is_excluded(d, analysis_context=ctx)
            if not excluded:
                kept.append(d)
        dates = kept

    stroke_date = (
        animal_info.stroke_date if animal_info is not None else None
    )

    if stroke_date is not None and prepost_mode != "all":
        if prepost_mode == "pre":
            dates = [d for d in dates if (d - stroke_date).days <= 0]
        elif prepost_mode == "post":
            dates = [d for d in dates if (d - stroke_date).days >= 1]
        elif prepost_mode == "both":
            pass  # no filter
        else:
            raise ValueError(
                f"prepost_mode must be one of 'pre','post','both','all'; "
                f"got {prepost_mode!r}",
            )

    if rel_day_range is not None and stroke_date is not None:
        lo, hi = rel_day_range
        dates = [
            d for d in dates
            if lo <= (d - stroke_date).days <= hi
        ]

    if stroke_date is not None:
        dates.sort(key=lambda d: (d - stroke_date).days)
    else:
        dates.sort()

    return dates


def build_cohort_aggregates(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    *,
    reward_pre_ms: int,
    reward_post_ms: int,
    params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> CohortAggregates | None:
    """Load + aggregate every eligible session for one (animal, bodypart, window).

    Returns ``None`` when no eligible sessions remain after filtering
    (matches the legacy ``[warn] mouse: no sessions matched`` skip path).
    """
    if bodypart not in _KNOWN_BODYPARTS:
        raise ValueError(
            f"bodypart must be one of {_KNOWN_BODYPARTS}; got {bodypart!r}",
        )

    if params is None:
        params = load_defaults()
    params_block = (
        params.get("dlc_kinematics", {}).get("mean_sem_visual", {})
    )

    if animal_info is None:
        try:
            animal_info = get_animal(animal)
        except (KeyError, FileNotFoundError):
            animal_info = None

    prepost_mode = params_block.get("prepost_mode", "both")
    rel_day_range_cfg = params_block.get("rel_day_range", None)
    rel_day_range: tuple[int, int] | None = None
    if rel_day_range_cfg is not None:
        rel_day_range = (int(rel_day_range_cfg[0]), int(rel_day_range_cfg[1]))

    dates = _eligible_dates(
        animal, bodypart, resolver,
        animal_info=animal_info,
        prepost_mode=prepost_mode,
        rel_day_range=rel_day_range,
    )
    if not dates:
        return None

    sessions: list[SessionAggregates] = []
    for d in dates:
        try:
            sa = _load_session_aggregates(
                bodypart, animal, d, resolver,
                pre_ms=reward_pre_ms, post_ms=reward_post_ms,
                animal_info=animal_info,
            )
        except FileNotFoundError:
            # Date had a parquet but missing reward inputs (alignment
            # template / licks NPZ). Skip — matches legacy behavior of
            # logging and continuing the inner loop.
            continue
        sessions.append(sa)

    if not sessions:
        return None

    # FPS sanity: legacy raises on cross-session fps mismatch. Mirror.
    fps0 = sessions[0].fps
    for s in sessions[1:]:
        if abs(s.fps - fps0) > 1e-6:
            raise ValueError(
                f"{animal}: fps mismatch across sessions: "
                f"{s.date.isoformat()} has {s.fps}, expected {fps0}",
            )

    pre_f = sessions[0].pre_f
    post_f = sessions[0].post_f
    t_ms = sessions[0].t_ms

    # ----- mean+SEM-extent axis limits (used by individual_sessions,
    # session_overlays, binned_overlays) -----
    plot_sem = bool(params_block.get("plot_sem", True))
    if plot_sem:
        y_lo, y_hi = _finite_minmax([
            *(s.myl - s.syl for s in sessions),
            *(s.myl + s.syl for s in sessions),
            *(s.myr - s.syr for s in sessions),
            *(s.myr + s.syr for s in sessions),
        ])
        x_lo, x_hi = _finite_minmax([
            *(s.mxl - s.sxl for s in sessions),
            *(s.mxl + s.sxl for s in sessions),
            *(s.mxr - s.sxr for s in sessions),
            *(s.mxr + s.sxr for s in sessions),
        ])
    else:
        y_lo, y_hi = _finite_minmax(
            [*(s.myl for s in sessions), *(s.myr for s in sessions)],
        )
        x_lo, x_hi = _finite_minmax(
            [*(s.mxl for s in sessions), *(s.mxr for s in sessions)],
        )
    y_lo, y_hi = _pad_axis_limits(y_lo, y_hi, frac=0.05)
    x_lo, x_hi = _pad_axis_limits(x_lo, x_hi, frac=0.05)
    y_lim = (y_lo, y_hi)
    x_lim = (x_lo, x_hi)

    # ----- trial-overlay percentile-based axis limits -----
    use_separate = bool(
        params_block.get("use_separate_trial_overlay_limits", True),
    )
    pct = tuple(params_block.get("trial_overlay_percentiles", (1.0, 99.0)))
    overlay_pad = float(params_block.get("trial_overlay_pad_frac", 0.05))
    if use_separate:
        ty_lo, ty_hi = _finite_percentile_range(
            [*(s.Ayl for s in sessions), *(s.Ayr for s in sessions)],
            pct_lo=pct[0], pct_hi=pct[1],
        )
        tx_lo, tx_hi = _finite_percentile_range(
            [*(s.Axl for s in sessions), *(s.Axr for s in sessions)],
            pct_lo=pct[0], pct_hi=pct[1],
        )
        ty_lo, ty_hi = _pad_axis_limits(ty_lo, ty_hi, frac=overlay_pad)
        tx_lo, tx_hi = _pad_axis_limits(tx_lo, tx_hi, frac=overlay_pad)
    else:
        ty_lo, ty_hi = y_lo, y_hi
        tx_lo, tx_hi = x_lo, x_hi
    trial_y_lim = (ty_lo, ty_hi)
    trial_x_lim = (tx_lo, tx_hi)

    # ----- day bins (per AnimalInfo.bin_days) -----
    bin_days = (
        int(animal_info.bin_days) if animal_info is not None
        else int(params_block.get("default_bin_size_days", 2))
    )
    if (
        animal_info is not None
        and animal_info.stroke_date is not None
    ):
        rel_days = np.array(
            [s.rel_day for s in sessions if s.rel_day is not None], float,
        )
        bins = _make_rel_day_bins(rel_days, bin_size=bin_days)
        binned = _compute_binned(sessions, bins) if bins else []
    else:
        bins = []
        binned = []

    # Suffix used in cohort filenames (matches legacy line 739):
    # ``date_start-date_end_winTag[_strokeD0_d0_prepost[_relDay[lo,hi]]]``.
    if animal_info is not None:
        date_start = animal_info.session_start.strftime("%Y%m%d")
        date_end = animal_info.session_end.strftime("%Y%m%d")
    else:
        date_start = sessions[0].date.strftime("%Y%m%d")
        date_end = sessions[-1].date.strftime("%Y%m%d")
    win_tag = f"{int(reward_pre_ms)}pre-{int(reward_post_ms)}post"
    suffix_parts = [f"{date_start}-{date_end}_{win_tag}"]
    if animal_info is not None and animal_info.stroke_date is not None:
        suffix_parts.append(
            f"strokeD0_{animal_info.stroke_date.strftime('%Y%m%d')}_"
            f"{prepost_mode}",
        )
    if rel_day_range is not None:
        suffix_parts.append(
            f"relDay[{rel_day_range[0]},{rel_day_range[1]}]",
        )
    suffix = "_".join(suffix_parts)

    return CohortAggregates(
        bodypart=bodypart,
        animal=animal,
        pre_ms=float(reward_pre_ms),
        post_ms=float(reward_post_ms),
        pre_f=pre_f,
        post_f=post_f,
        fps=fps0,
        t_ms=t_ms,
        sessions=sessions,
        y_lim=y_lim,
        x_lim=x_lim,
        trial_y_lim=trial_y_lim,
        trial_x_lim=trial_x_lim,
        bin_days=bin_days,
        bins=bins,
        binned=binned,
        cam=str(params_block.get("cam", "cam2")),
        interp_version=sessions[0].interp_version,
        suffix=suffix,
    )


# ===========================================================================
# Plot helpers (private)
# ===========================================================================


def _resolved_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Pull out the ``mean_sem_visual`` block, loading defaults on demand."""
    if params is None:
        params = load_defaults()
    return params.get("dlc_kinematics", {}).get("mean_sem_visual", {})


def _bodypart_block(
    params: dict[str, Any] | None, bodypart: str,
) -> dict[str, Any]:
    """Pull the per-bodypart override block (carries ``center_mode`` etc.)."""
    block = _resolved_params(params)
    return block.get(bodypart, {})


def _resolve_center_mode(
    bodypart: str, params: dict[str, Any] | None,
) -> str:
    bp_block = _bodypart_block(params, bodypart)
    cm = bp_block.get("center_mode")
    if cm is None:
        # Fall back to the dlc_kinematics.{bodypart}.center_mode used by
        # 7a.2 (kept in defaults.yaml as the source of truth for the
        # bodypart's center). Matches what the consolidated pipeline
        # emits.
        if params is None:
            params = load_defaults()
        cm = (
            params.get("dlc_kinematics", {})
            .get(bodypart, {})
            .get("center_mode")
        )
    if cm is None:
        raise ValueError(
            f"No center_mode resolvable for bodypart={bodypart!r}; "
            f"add it under dlc_kinematics.mean_sem_visual.{bodypart}."
            f"center_mode or dlc_kinematics.{bodypart}.center_mode in "
            f"defaults.yaml",
        )
    return str(cm)


def _plot_session_2x2(
    bodypart: str,
    cam: str,
    sess: SessionAggregates,
    cohort: CohortAggregates,
    params_block: dict[str, Any],
    out_path: Path,
) -> None:
    """Per-session 4-panel mean+SEM (Y/X × L/R). Direct port of legacy
    ``plot_session_2x2`` (lines 370-408 of vendored cell 31).
    """
    side_colors = params_block.get(
        "side_colors", {"L": "dodgerblue", "R": "mediumvioletred"},
    )
    linewidth = float(params_block.get("linewidth", 1))
    sem_alpha = float(params_block.get("sem_alpha", 0.18))
    plot_sem = bool(params_block.get("plot_sem", True))
    dpi = int(params_block.get("dpi", 200))

    label_token = _AXIS_LABEL[bodypart]
    fig, axs = plt.subplots(2, 2, figsize=(12, 7), sharex=True)

    def one(ax, m, s, side, title, ylabel, ylim):
        c = side_colors[side]
        ax.plot(cohort.t_ms, m, lw=linewidth, label="mean", color=c)
        if plot_sem:
            ax.fill_between(
                cohort.t_ms, m - s, m + s, alpha=sem_alpha, lw=0, color=c,
            )
        ax.axvline(0, color="k", lw=1)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel(ylabel)
        if ylim is not None and np.isfinite(ylim[0]) and np.isfinite(ylim[1]):
            ax.set_ylim(*ylim)

    one(
        axs[0, 0], sess.myl, sess.syl, "L",
        f"Mouse LEFT rewards | Y | n={sess.n_L} ({sess.interp_version})",
        f"{label_token} Y (px)", cohort.y_lim,
    )
    one(
        axs[0, 1], sess.myr, sess.syr, "R",
        f"Mouse RIGHT rewards | Y | n={sess.n_R} ({sess.interp_version})",
        f"{label_token} Y (px)", cohort.y_lim,
    )
    one(
        axs[1, 0], sess.mxl, sess.sxl, "L",
        f"Mouse LEFT rewards | X | n={sess.n_L} ({sess.interp_version})",
        f"{label_token} X (px)", cohort.x_lim,
    )
    one(
        axs[1, 1], sess.mxr, sess.sxr, "R",
        f"Mouse RIGHT rewards | X | n={sess.n_R} ({sess.interp_version})",
        f"{label_token} X (px)", cohort.x_lim,
    )

    for ax in axs[1, :]:
        ax.set_xlabel("Time relative to reward (ms)")

    title = f"{sess.animal} {cam} | {sess.date.strftime('%Y%m%d')}"
    if sess.rel_day is not None:
        title += f" ({sess.legend})"
    title += f" | src={sess.source_path.name}"
    fig.suptitle(title, y=1.02, fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _plot_trial_overlays_2x2(
    bodypart: str,
    cam: str,
    sess: SessionAggregates,
    cohort: CohortAggregates,
    params_block: dict[str, Any],
    out_path: Path,
) -> None:
    """Per-session 4-panel mean+SEM with all individual trials underlayed.
    Direct port of legacy ``plot_trial_overlays_2x2`` (lines 410-451).
    """
    side_colors = params_block.get(
        "side_colors", {"L": "dodgerblue", "R": "mediumvioletred"},
    )
    linewidth = float(params_block.get("linewidth", 1))
    sem_alpha = float(params_block.get("sem_alpha", 0.18))
    trial_alpha = float(params_block.get("trial_alpha", 0.08))
    trial_lw = float(params_block.get("trial_linewidth", 0.6))
    plot_sem = bool(params_block.get("plot_sem", True))
    dpi = int(params_block.get("dpi", 200))

    label_token = _AXIS_LABEL[bodypart]
    fig, axs = plt.subplots(2, 2, figsize=(12, 7), sharex=True)

    def one(ax, A, m, s, side, title, ylabel, ylim):
        c = side_colors[side]
        if A is not None and A.size > 0:
            for row in A:
                ax.plot(
                    cohort.t_ms, row, lw=trial_lw, alpha=trial_alpha, color=c,
                )
        ax.plot(cohort.t_ms, m, lw=linewidth, label="mean", color=c)
        if plot_sem:
            ax.fill_between(
                cohort.t_ms, m - s, m + s, alpha=sem_alpha, lw=0, color=c,
            )
        ax.axvline(0, color="k", lw=1)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel(ylabel)
        if ylim is not None and np.isfinite(ylim[0]) and np.isfinite(ylim[1]):
            ax.set_ylim(*ylim)

    one(
        axs[0, 0], sess.Ayl, sess.myl, sess.syl, "L",
        f"Mouse LEFT rewards | Y | n={sess.n_L} ({sess.interp_version})",
        f"{label_token} Y (px)", cohort.trial_y_lim,
    )
    one(
        axs[0, 1], sess.Ayr, sess.myr, sess.syr, "R",
        f"Mouse RIGHT rewards | Y | n={sess.n_R} ({sess.interp_version})",
        f"{label_token} Y (px)", cohort.trial_y_lim,
    )
    one(
        axs[1, 0], sess.Axl, sess.mxl, sess.sxl, "L",
        f"Mouse LEFT rewards | X | n={sess.n_L} ({sess.interp_version})",
        f"{label_token} X (px)", cohort.trial_x_lim,
    )
    one(
        axs[1, 1], sess.Axr, sess.mxr, sess.sxr, "R",
        f"Mouse RIGHT rewards | X | n={sess.n_R} ({sess.interp_version})",
        f"{label_token} X (px)", cohort.trial_x_lim,
    )

    for ax in axs[1, :]:
        ax.set_xlabel("Time relative to reward (ms)")

    title = (
        f"{sess.animal} {cam} | {sess.date.strftime('%Y%m%d')} | "
        f"all trials + mean±SEM"
    )
    if sess.rel_day is not None:
        title += f" ({sess.legend})"
    title += f" | src={sess.source_path.name}"
    fig.suptitle(title, y=1.02, fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _plot_session_overlay(
    bodypart: str,
    cam: str,
    cohort: CohortAggregates,
    params_block: dict[str, Any],
    key_m: str,
    key_s: str,
    side_label: str,
    ylabel: str,
    out_path: Path,
) -> None:
    """Cross-session overlay (one panel: one of {Y,X} × {L,R}). Direct port
    of legacy ``plot_overlay`` (lines 453-500).
    """
    cmap_name = str(params_block.get("cmap_name", "plasma"))
    pre_color = str(params_block.get("pre_color", "0.3"))
    linewidth = float(params_block.get("linewidth", 1))
    line_alpha = float(params_block.get("line_alpha", 0.5))
    sem_alpha = float(params_block.get("sem_alpha", 0.18))
    plot_sem = bool(params_block.get("plot_sem", True))
    dpi = int(params_block.get("dpi", 200))

    sessions = cohort.sessions
    colors = _overlay_colors_pre_grey_post_cmap(
        sessions, cmap_name=cmap_name, pre_color=pre_color,
    )

    fig, ax = plt.subplots(figsize=(12, 4))
    for i, sess in enumerate(sessions):
        m = getattr(sess, key_m)
        s = getattr(sess, key_s)
        c = colors[i]
        ax.plot(
            cohort.t_ms, m, lw=linewidth, color=c, alpha=line_alpha,
            label=sess.legend,
        )
        if plot_sem:
            ax.fill_between(
                cohort.t_ms, m - s, m + s, color=c, alpha=sem_alpha, lw=0,
            )

    ax.axvline(0, color="k", lw=1)
    ax.set_title(
        f"{cohort.animal} {cam} | {side_label} | mean±SEM | "
        f"sessions={len(sessions)} | src={cohort.interp_version}",
    )
    ax.set_xlabel("Time relative to reward (ms)")
    ax.set_ylabel(ylabel)
    if "y" in key_m.lower():
        ylim = cohort.y_lim
    else:
        ylim = cohort.x_lim
    if ylim is not None and np.isfinite(ylim[0]) and np.isfinite(ylim[1]):
        ax.set_ylim(*ylim)

    n = len(sessions)
    if n <= 16:
        ncol, fsize = 2, 9
    elif n <= 36:
        ncol, fsize = 3, 8
    else:
        ncol, fsize = 4, 7.5

    fig.subplots_adjust(right=0.78)
    ax.legend(
        frameon=False,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        borderaxespad=0.0,
        ncol=ncol,
        fontsize=fsize,
        handlelength=1.8,
        handletextpad=0.4,
        columnspacing=1.0,
        labelspacing=0.35,
    )
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _plot_binned_overlay(
    bodypart: str,
    cam: str,
    cohort: CohortAggregates,
    params_block: dict[str, Any],
    key_m: str,
    key_s: str,
    side_label: str,
    ylabel: str,
    out_path: Path,
) -> None:
    """Cross-session day-binned overlay. Direct port of legacy
    ``plot_binned_overlay`` (lines 502-565).
    """
    binned = cohort.binned
    if not binned:
        # Legacy logs `[warn] no binned data to plot.` and returns; same here.
        return

    cmap_name = str(params_block.get("cmap_name", "plasma"))
    pre_color = str(params_block.get("pre_color", "0.3"))
    sem_alpha = float(params_block.get("sem_alpha", 0.18))
    plot_sem = bool(params_block.get("plot_sem", True))
    include_pre = bool(params_block.get("include_pre_bins", True))
    include_post = bool(params_block.get("include_post_bins", True))
    dpi = int(params_block.get("dpi", 200))

    post_centers = np.array(
        [b["bin_center"] for b in binned if b["bin_center"] >= 1], float,
    )
    post_max = float(np.nanmax(post_centers)) if post_centers.size else 1.0

    fig, ax = plt.subplots(figsize=(12, 4))
    for b in binned:
        lo, hi = b["bin_lo"], b["bin_hi"]
        cen = b["bin_center"]
        if cen <= 0 and not include_pre:
            continue
        if cen >= 1 and not include_post:
            continue
        c = _color_for_bin(
            lo, hi, post_max, cmap_name=cmap_name, pre_color=pre_color,
        )
        m = b[key_m]
        s = b[key_s]
        lab = f"{b['bin_label']} (n={b['n_sessions']})"
        ax.plot(cohort.t_ms, m, lw=1.5, color=c, alpha=0.5, label=lab)
        if plot_sem:
            ax.fill_between(
                cohort.t_ms, m - s, m + s, color=c, alpha=sem_alpha, lw=0,
            )

    ax.axvline(0, color="k", lw=1)
    ax.set_title(
        f"{cohort.animal} {cam} | BINNED overlays | bin={cohort.bin_days}d "
        f"| {side_label} | src={cohort.interp_version}",
    )
    ax.set_xlabel("Time relative to reward (ms)")
    ax.set_ylabel(ylabel)
    if "y" in key_m.lower():
        ylim = cohort.y_lim
    else:
        ylim = cohort.x_lim
    if ylim is not None and np.isfinite(ylim[0]) and np.isfinite(ylim[1]):
        ax.set_ylim(*ylim)

    n = len(binned)
    if n <= 16:
        ncol, fsize = 1, 9
    elif n <= 28:
        ncol, fsize = 1, 8
    else:
        ncol, fsize = 2, 7.5

    fig.subplots_adjust(right=0.78)
    ax.legend(
        frameon=False,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        borderaxespad=0.0,
        ncol=ncol,
        fontsize=fsize,
        handlelength=1.8,
        handletextpad=0.4,
        columnspacing=1.0,
        labelspacing=0.35,
    )
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# ===========================================================================
# Filename builders (match legacy)
# ===========================================================================


def _per_session_filename(
    family: str, sess: SessionAggregates, cam: str,
    reward_pre_ms: int, reward_post_ms: int,
) -> str:
    """Match legacy line 400 / 443:
    ``{mouse}_{date}_{win_tag}_{cam}_{interp_version}_meanSEM_2x2[_trials][_legend].png``
    """
    win_tag = f"{int(reward_pre_ms)}pre-{int(reward_post_ms)}post"
    base = (
        f"{sess.animal}_{sess.date.strftime('%Y%m%d')}_{win_tag}_{cam}_"
        f"{sess.interp_version}_meanSEM_2x2"
    )
    if family == "trial_overlays":
        base += "_trials"
    if sess.rel_day is not None:
        base += f"_{sess.legend}"
    return base + ".png"


def _cohort_filename(
    family: str, cohort: CohortAggregates, cam: str, outname: str,
) -> str:
    """Match legacy lines 495 / 560:
    ``{mouse}_{suffix}_{cam}_{outname}_{interp_version}.png`` (overlays)
    or ``{mouse}_{suffix}_{cam}_{outname}_BIN{N}d_{interp_version}.png`` (binned).
    """
    if family == "session_overlays":
        return (
            f"{cohort.animal}_{cohort.suffix}_{cam}_{outname}_"
            f"{cohort.interp_version}.png"
        )
    if family == "binned_overlays":
        return (
            f"{cohort.animal}_{cohort.suffix}_{cam}_{outname}_"
            f"BIN{cohort.bin_days}d_{cohort.interp_version}.png"
        )
    raise ValueError(f"Unknown cohort family {family!r}")


# ===========================================================================
# Public API — per-session
# ===========================================================================


def build_individual_sessions(
    bodypart: str,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    reward_pre_ms: int,
    reward_post_ms: int,
    params: dict[str, Any] | None = None,
    cohort: CohortAggregates | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> Path | None:
    """Render the per-session 2x2 mean+SEM figure for one (animal, date, window).

    Per-session axis limits are taken from the cohort (so all per-session
    plots in the same animal × window share a uniform axis). When
    ``cohort`` is ``None``, the cohort is loaded internally — repeated
    calls in a tight loop should pass an explicit pre-built cohort to
    avoid re-loading.

    Parameters
    ----------
    bodypart : {"tongue", "jaw"}
    animal, date, resolver
        Standard 7a.x signature.
    reward_pre_ms, reward_post_ms
        Reward-aligned window endpoints in milliseconds. Must match a
        window present in the cohort if one is supplied.
    params
        Loaded :func:`load_defaults` block. ``None`` → loads the repo
        default. Reads ``dlc_kinematics.mean_sem_visual.*``.
    cohort
        Optional pre-built CohortAggregates. Pass to avoid re-loading
        when iterating over multiple dates for the same window.
    overwrite
        ``"skip"`` returns the existing path if the PNG is already on
        disk. ``"force"`` always rewrites.

    Returns
    -------
    Path or None
        The emitted PNG path. ``None`` if ``params_block.plot_individual_sessions``
        is False or the cohort is empty.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )

    params_block = _resolved_params(params)
    if not bool(params_block.get("plot_individual_sessions", True)):
        return None

    if cohort is None:
        cohort = build_cohort_aggregates(
            bodypart, animal, resolver,
            reward_pre_ms=reward_pre_ms, reward_post_ms=reward_post_ms,
            params=params,
        )
    if cohort is None:
        return None

    # Find the matching session in the cohort.
    sess: SessionAggregates | None = next(
        (s for s in cohort.sessions if s.date == date), None,
    )
    if sess is None:
        return None

    center_mode = _resolve_center_mode(bodypart, params)
    out_dir = resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=center_mode,
        reward_pre_ms=reward_pre_ms,
        reward_post_ms=reward_post_ms,
        plot_family="individual_sessions",
        animal=animal,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = _per_session_filename(
        "individual_sessions", sess, cohort.cam,
        reward_pre_ms, reward_post_ms,
    )
    out_path = out_dir / fname

    if overwrite == "skip" and out_path.exists():
        return out_path

    _plot_session_2x2(
        bodypart, cohort.cam, sess, cohort, params_block, out_path,
    )
    return out_path


def build_trial_overlays(
    bodypart: str,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    reward_pre_ms: int,
    reward_post_ms: int,
    params: dict[str, Any] | None = None,
    cohort: CohortAggregates | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> Path | None:
    """Render the per-session 2x2 trial-overlay figure (mean+SEM with all
    individual trials underlayed). Same shape as
    :func:`build_individual_sessions` but uses the cohort's percentile-
    based ``trial_y_lim`` / ``trial_x_lim`` for axis limits.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )

    params_block = _resolved_params(params)
    if not bool(params_block.get("plot_trial_overlays", True)):
        return None

    if cohort is None:
        cohort = build_cohort_aggregates(
            bodypart, animal, resolver,
            reward_pre_ms=reward_pre_ms, reward_post_ms=reward_post_ms,
            params=params,
        )
    if cohort is None:
        return None

    sess: SessionAggregates | None = next(
        (s for s in cohort.sessions if s.date == date), None,
    )
    if sess is None:
        return None

    center_mode = _resolve_center_mode(bodypart, params)
    out_dir = resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=center_mode,
        reward_pre_ms=reward_pre_ms,
        reward_post_ms=reward_post_ms,
        plot_family="trial_overlays",
        animal=animal,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = _per_session_filename(
        "trial_overlays", sess, cohort.cam,
        reward_pre_ms, reward_post_ms,
    )
    out_path = out_dir / fname

    if overwrite == "skip" and out_path.exists():
        return out_path

    _plot_trial_overlays_2x2(
        bodypart, cohort.cam, sess, cohort, params_block, out_path,
    )
    return out_path


# ===========================================================================
# Public API — cohort
# ===========================================================================


# Cohort overlay: 4 panels (Y/X × L/R) per (animal, window). The legacy
# loop at line 756 calls plot_overlay 4 times with these (key_m, key_s,
# side_label, ylabel suffix, outname) tuples.
def _cohort_overlay_specs(
    bodypart: str,
) -> tuple[tuple[str, str, str, str, str], ...]:
    label = _AXIS_LABEL[bodypart]
    return (
        ("myl", "syl", "Mouse LEFT rewards",
         f"{label} Y (px)", "overlay_Y_mouseLrewards"),
        ("myr", "syr", "Mouse RIGHT rewards",
         f"{label} Y (px)", "overlay_Y_mouseRrewards"),
        ("mxl", "sxl", "Mouse LEFT rewards",
         f"{label} X (px)", "overlay_X_mouseLrewards"),
        ("mxr", "sxr", "Mouse RIGHT rewards",
         f"{label} X (px)", "overlay_X_mouseRrewards"),
    )


def _cohort_binned_specs(
    bodypart: str,
) -> tuple[tuple[str, str, str, str, str], ...]:
    label = _AXIS_LABEL[bodypart]
    return (
        ("myl", "syl", "Mouse LEFT rewards",
         f"{label} Y (px)", "binnedOverlay_Y_mouseLrewards"),
        ("myr", "syr", "Mouse RIGHT rewards",
         f"{label} Y (px)", "binnedOverlay_Y_mouseRrewards"),
        ("mxl", "sxl", "Mouse LEFT rewards",
         f"{label} X (px)", "binnedOverlay_X_mouseLrewards"),
        ("mxr", "sxr", "Mouse RIGHT rewards",
         f"{label} X (px)", "binnedOverlay_X_mouseRrewards"),
    )


def build_session_overlays(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    *,
    reward_pre_ms: int,
    reward_post_ms: int,
    params: dict[str, Any] | None = None,
    cohort: CohortAggregates | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> list[Path]:
    """Render the cohort cross-session overlay (4 PNGs per animal × window).

    One PNG per (Y/X × L/R) combination.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )

    params_block = _resolved_params(params)
    if not bool(params_block.get("plot_session_overlays", True)):
        return []

    if cohort is None:
        cohort = build_cohort_aggregates(
            bodypart, animal, resolver,
            reward_pre_ms=reward_pre_ms, reward_post_ms=reward_post_ms,
            params=params,
        )
    if cohort is None:
        return []

    center_mode = _resolve_center_mode(bodypart, params)
    out_dir = resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=center_mode,
        reward_pre_ms=reward_pre_ms,
        reward_post_ms=reward_post_ms,
        plot_family="session_overlays",
        animal=animal,
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for key_m, key_s, side_label, ylabel, outname in _cohort_overlay_specs(
        bodypart,
    ):
        fname = _cohort_filename(
            "session_overlays", cohort, cohort.cam, outname,
        )
        out_path = out_dir / fname
        if overwrite == "skip" and out_path.exists():
            paths.append(out_path)
            continue
        _plot_session_overlay(
            bodypart, cohort.cam, cohort, params_block,
            key_m, key_s, side_label, ylabel, out_path,
        )
        paths.append(out_path)
    return paths


def build_binned_overlays(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    *,
    reward_pre_ms: int,
    reward_post_ms: int,
    params: dict[str, Any] | None = None,
    cohort: CohortAggregates | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> list[Path]:
    """Render the cohort day-binned overlay (4 PNGs per animal × window).

    No-op (returns ``[]``) when the animal has no ``stroke_date`` or no
    bins could be constructed.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )

    params_block = _resolved_params(params)
    if not bool(params_block.get("plot_binned_overlays", True)):
        return []

    if cohort is None:
        cohort = build_cohort_aggregates(
            bodypart, animal, resolver,
            reward_pre_ms=reward_pre_ms, reward_post_ms=reward_post_ms,
            params=params,
        )
    if cohort is None or not cohort.binned:
        return []

    center_mode = _resolve_center_mode(bodypart, params)
    out_dir = resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=center_mode,
        reward_pre_ms=reward_pre_ms,
        reward_post_ms=reward_post_ms,
        plot_family="binned_overlays",
        animal=animal,
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for key_m, key_s, side_label, ylabel, outname in _cohort_binned_specs(
        bodypart,
    ):
        fname = _cohort_filename(
            "binned_overlays", cohort, cohort.cam, outname,
        )
        out_path = out_dir / fname
        if overwrite == "skip" and out_path.exists():
            paths.append(out_path)
            continue
        _plot_binned_overlay(
            bodypart, cohort.cam, cohort, params_block,
            key_m, key_s, side_label, ylabel, out_path,
        )
        paths.append(out_path)
    return paths


__all__ = [
    "MEAN_SEM_VISUAL_VERSION",
    "PLOT_FAMILIES_C4_1",
    "CohortAggregates",
    "SessionAggregates",
    "build_binned_overlays",
    "build_cohort_aggregates",
    "build_individual_sessions",
    "build_session_overlays",
    "build_trial_overlays",
]
