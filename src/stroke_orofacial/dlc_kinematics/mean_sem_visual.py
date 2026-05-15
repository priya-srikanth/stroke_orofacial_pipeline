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
import logging  # noqa: E402
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

_logger = logging.getLogger(__name__)

MEAN_SEM_VISUAL_VERSION = "v7a.6"

# Family identifiers handled across the Phase 7a.6 C4.x commits.
PLOT_FAMILIES_C4_1: tuple[str, ...] = (
    "individual_sessions",
    "trial_overlays",
    "session_overlays",
    "binned_overlays",
)
PLOT_FAMILIES_C4_2: tuple[str, ...] = ("mean_trace",)
PLOT_FAMILIES_C4_3: tuple[str, ...] = ("mean_video",)
PLOT_FAMILIES_ALL: tuple[str, ...] = (
    *PLOT_FAMILIES_C4_1,
    *PLOT_FAMILIES_C4_2,
    *PLOT_FAMILIES_C4_3,
)
_PER_SESSION_FAMILIES: frozenset[str] = frozenset(
    {"individual_sessions", "trial_overlays"}
)
_COHORT_FAMILIES: frozenset[str] = frozenset(
    {"session_overlays", "binned_overlays", "mean_trace", "mean_video"}
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
        align_path = resolver.alignment_template_legacy_read(animal, date, cam="cam2")
    if not align_path.exists():
        raise FileNotFoundError(
            f"{animal}/{date_str}: cam2 alignment template missing at "
            f"{align_path}. Run scripts/make_alignment_templates.py.",
        )

    from stroke_orofacial.alignment.templates import load_alignment_template
    from stroke_orofacial.dlc_spatial.tone_aligned import (
        load_tone_events,
        ws_samples_to_frame_indices,
    )

    aln = load_alignment_template(align_path)
    sig_camIdx__idx_ws = aln["sig_camIdx__idx_ws"]

    # X1-β: function rename to load_tone_events. Local-variable +
    # docstring cleanup deferred to Phase 7b per Q3.B.
    centers: dict[str, list[int]] = {"L": [], "R": []}
    for side in ("L", "R"):
        ws_idx = load_tone_events(
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
    tone_pre_ms: int,
    tone_post_ms: int,
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
                pre_ms=tone_pre_ms, post_ms=tone_post_ms,
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
    win_tag = f"{int(tone_pre_ms)}pre-{int(tone_post_ms)}post"
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
        pre_ms=float(tone_pre_ms),
        post_ms=float(tone_post_ms),
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
    *,
    y_lim_override: tuple[float, float] | None = None,
    x_lim_override: tuple[float, float] | None = None,
) -> None:
    """Per-session 4-panel mean+SEM (Y/X × L/R). Direct port of legacy
    ``plot_session_2x2`` (lines 370-408 of vendored cell 31).

    ``y_lim_override`` / ``x_lim_override`` (C7.1 Issue 3): when set,
    use these bounds instead of ``cohort.y_lim`` / ``cohort.x_lim``.
    Defaults to the cohort bounds (current behavior preserved).
    """
    side_colors = params_block.get(
        "side_colors", {"L": "dodgerblue", "R": "mediumvioletred"},
    )
    linewidth = float(params_block.get("linewidth", 1))
    sem_alpha = float(params_block.get("sem_alpha", 0.18))
    plot_sem = bool(params_block.get("plot_sem", True))
    dpi = int(params_block.get("dpi", 200))

    y_lim = y_lim_override if y_lim_override is not None else cohort.y_lim
    x_lim = x_lim_override if x_lim_override is not None else cohort.x_lim

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

    # C7.2 Issue B: R trials on figure LEFT (axs[*, 0]), L on RIGHT
    # (axs[*, 1]). Cam-view convention — camera mirror-images the mouse
    # so mouse-left renders on the right of the cam image. Deliberate
    # deviation from legacy master cell (which has L-LEFT, R-RIGHT)
    # documented in DECISIONS at Task 9 per Priya 2026-05-02.
    one(
        axs[0, 0], sess.myr, sess.syr, "R",
        f"Mouse RIGHT rewards | Y | n={sess.n_R} ({sess.interp_version})",
        f"{label_token} Y (px)", y_lim,
    )
    one(
        axs[0, 1], sess.myl, sess.syl, "L",
        f"Mouse LEFT rewards | Y | n={sess.n_L} ({sess.interp_version})",
        f"{label_token} Y (px)", y_lim,
    )
    one(
        axs[1, 0], sess.mxr, sess.sxr, "R",
        f"Mouse RIGHT rewards | X | n={sess.n_R} ({sess.interp_version})",
        f"{label_token} X (px)", x_lim,
    )
    one(
        axs[1, 1], sess.mxl, sess.sxl, "L",
        f"Mouse LEFT rewards | X | n={sess.n_L} ({sess.interp_version})",
        f"{label_token} X (px)", x_lim,
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
    *,
    y_lim_override: tuple[float, float] | None = None,
    x_lim_override: tuple[float, float] | None = None,
) -> None:
    """Per-session 4-panel mean+SEM with all individual trials underlayed.
    Direct port of legacy ``plot_trial_overlays_2x2`` (lines 410-451).

    ``y_lim_override`` / ``x_lim_override`` (C7.1 Issue 3): when set,
    use these bounds instead of ``cohort.trial_y_lim`` /
    ``cohort.trial_x_lim``.
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

    y_lim = (
        y_lim_override if y_lim_override is not None else cohort.trial_y_lim
    )
    x_lim = (
        x_lim_override if x_lim_override is not None else cohort.trial_x_lim
    )

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

    # C7.2 Issue B: cam-view (R-LEFT, L-RIGHT). See _plot_session_2x2 for
    # full rationale + DECISIONS deviation note.
    one(
        axs[0, 0], sess.Ayr, sess.myr, sess.syr, "R",
        f"Mouse RIGHT rewards | Y | n={sess.n_R} ({sess.interp_version})",
        f"{label_token} Y (px)", y_lim,
    )
    one(
        axs[0, 1], sess.Ayl, sess.myl, sess.syl, "L",
        f"Mouse LEFT rewards | Y | n={sess.n_L} ({sess.interp_version})",
        f"{label_token} Y (px)", y_lim,
    )
    one(
        axs[1, 0], sess.Axr, sess.mxr, sess.sxr, "R",
        f"Mouse RIGHT rewards | X | n={sess.n_R} ({sess.interp_version})",
        f"{label_token} X (px)", x_lim,
    )
    one(
        axs[1, 1], sess.Axl, sess.mxl, sess.sxl, "L",
        f"Mouse LEFT rewards | X | n={sess.n_L} ({sess.interp_version})",
        f"{label_token} X (px)", x_lim,
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
    tone_pre_ms: int, tone_post_ms: int,
) -> str:
    """Match legacy line 400 / 443:
    ``{mouse}_{date}_{win_tag}_{cam}_{interp_version}_meanSEM_2x2[_trials][_legend].png``
    """
    win_tag = f"{int(tone_pre_ms)}pre-{int(tone_post_ms)}post"
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
    tone_pre_ms: int,
    tone_post_ms: int,
    params: dict[str, Any] | None = None,
    cohort: CohortAggregates | None = None,
    animal_y_bounds: tuple[float, float] | None = None,
    animal_x_bounds: tuple[float, float] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> Path | None:
    """Render the per-session 2x2 mean+SEM figure for one (animal, date, window).

    Per-session axis limits are taken from the cohort by default (so all
    per-session plots in the same animal × window share a uniform axis).
    When ``cohort`` is ``None``, the cohort is loaded internally —
    repeated calls in a tight loop should pass an explicit pre-built
    cohort (or use :func:`build_individual_sessions_animal`) to avoid
    re-loading.

    Parameters
    ----------
    bodypart : {"tongue", "jaw"}
    animal, date, resolver
        Standard 7a.x signature.
    tone_pre_ms, tone_post_ms
        Tone-aligned window endpoints in milliseconds. Must match a
        window present in the cohort if one is supplied.
    params
        Loaded :func:`load_defaults` block. ``None`` → loads the repo
        default. Reads ``dlc_kinematics.mean_sem_visual.*``.
    cohort
        Optional pre-built CohortAggregates. Pass to avoid re-loading
        when iterating over multiple dates for the same window.
    animal_y_bounds, animal_x_bounds : tuple[float, float] | None
        C7.1 Issue 3 (added 2026-05-02). When provided, override the
        cohort's auto-scaled ``y_lim`` / ``x_lim`` so per-session figures
        share a uniform axis across an animal-wide span (e.g., across
        windows). ``None`` (default) preserves the original cohort-scoped
        auto-scale behavior. The two-pass driver
        :func:`build_individual_sessions_animal` uses this kwarg to
        emit per-session PNGs with animal-wide bounds in one call.
    overwrite
        ``"skip"`` returns the existing path if the PNG is already on
        disk. ``"force"`` always rewrites.

    Returns
    -------
    Path or None
        The emitted PNG path. ``None`` if ``params_block.plot_individual_sessions``
        is False or the cohort is empty.

    Examples
    --------
    Override a single knob via the params dict:

        defaults = load_defaults()
        params = {**defaults, "dlc_kinematics": {**defaults["dlc_kinematics"], ...}}
        # ... or, cleaner, mutate a deep copy of defaults["dlc_kinematics"][
        # "mean_sem_visual"] directly before calling.
        build_individual_sessions("tongue", animal, date, resolver, params=...)
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
            tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
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
        tone_pre_ms=tone_pre_ms,
        tone_post_ms=tone_post_ms,
        plot_family="individual_sessions",
        animal=animal,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = _per_session_filename(
        "individual_sessions", sess, cohort.cam,
        tone_pre_ms, tone_post_ms,
    )
    out_path = out_dir / fname

    if overwrite == "skip" and out_path.exists():
        return out_path

    _plot_session_2x2(
        bodypart, cohort.cam, sess, cohort, params_block, out_path,
        y_lim_override=animal_y_bounds,
        x_lim_override=animal_x_bounds,
    )
    return out_path


def build_trial_overlays(
    bodypart: str,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    tone_pre_ms: int,
    tone_post_ms: int,
    params: dict[str, Any] | None = None,
    cohort: CohortAggregates | None = None,
    animal_y_bounds: tuple[float, float] | None = None,
    animal_x_bounds: tuple[float, float] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> Path | None:
    """Render the per-session 2x2 trial-overlay figure (mean+SEM with all
    individual trials underlayed). Same shape as
    :func:`build_individual_sessions` but uses the cohort's percentile-
    based ``trial_y_lim`` / ``trial_x_lim`` for axis limits.

    ``animal_y_bounds`` / ``animal_x_bounds`` (C7.1 Issue 3): same
    semantics as :func:`build_individual_sessions` — when provided,
    override the cohort's percentile-based trial axis limits with
    explicit animal-wide bounds.

    Examples
    --------
    Override the trial-overlay alpha:

        params = load_defaults()
        params["dlc_kinematics"]["mean_sem_visual"]["trial_alpha"] = 0.05
        build_trial_overlays("tongue", animal, date, resolver, params=params)
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
            tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
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
        tone_pre_ms=tone_pre_ms,
        tone_post_ms=tone_post_ms,
        plot_family="trial_overlays",
        animal=animal,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = _per_session_filename(
        "trial_overlays", sess, cohort.cam,
        tone_pre_ms, tone_post_ms,
    )
    out_path = out_dir / fname

    if overwrite == "skip" and out_path.exists():
        return out_path

    _plot_trial_overlays_2x2(
        bodypart, cohort.cam, sess, cohort, params_block, out_path,
        y_lim_override=animal_y_bounds,
        x_lim_override=animal_x_bounds,
    )
    return out_path


def build_individual_sessions_animal(
    bodypart: str,
    animal: str,
    dates: Sequence[datetime.date],
    resolver: PathResolver,
    *,
    tone_pre_ms: int,
    tone_post_ms: int,
    params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> list[Path]:
    """C7.1 Issue 3 — two-pass driver that renders ``individual_sessions``
    PNGs for many dates with **animal-wide** Y/X bounds.

    Pass 1: build the cohort once for the (animal, bodypart, window).
    Cohort-wide ``y_lim`` / ``x_lim`` are union of mean+SEM extents
    across every eligible session for this animal — this IS the animal-
    wide auto-scale, so the existing default-mode behavior is already
    animal-wide for the standard call shape (cohort= passed in).

    Pass 2: emit one PNG per ``date``, calling
    :func:`build_individual_sessions` with ``animal_y_bounds`` /
    ``animal_x_bounds`` set to the cohort bounds explicitly. This makes
    the two-pass intent visible in the public API and guarantees
    uniform bounds even when callers might otherwise pass mismatched
    cohorts.

    Returns the list of emitted PNG paths (any ``None`` returns from the
    inner call are filtered out).

    Examples
    --------
    Render uniform-bound PNGs for all in-scope sessions of one animal:

        from datetime import date
        dates = [date(2025, 3, 7), date(2025, 3, 10), date(2025, 3, 13)]
        build_individual_sessions_animal(
            "tongue", "PS46", dates, resolver,
            tone_pre_ms=100, tone_post_ms=1000,
        )
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )

    cohort = build_cohort_aggregates(
        bodypart, animal, resolver,
        tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
        params=params, animal_info=animal_info,
    )
    if cohort is None:
        return []

    out: list[Path] = []
    for date in dates:
        path = build_individual_sessions(
            bodypart, animal, date, resolver,
            tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
            params=params, cohort=cohort,
            animal_y_bounds=cohort.y_lim,
            animal_x_bounds=cohort.x_lim,
            overwrite=overwrite,
        )
        if path is not None:
            out.append(path)
    return out


def build_trial_overlays_animal(
    bodypart: str,
    animal: str,
    dates: Sequence[datetime.date],
    resolver: PathResolver,
    *,
    tone_pre_ms: int,
    tone_post_ms: int,
    params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> list[Path]:
    """C7.1 Issue 3 — two-pass driver for ``trial_overlays``.

    Same shape as :func:`build_individual_sessions_animal` but emits
    the trial-overlay variant with animal-wide ``trial_y_lim`` /
    ``trial_x_lim`` (percentile-based by default).
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )

    cohort = build_cohort_aggregates(
        bodypart, animal, resolver,
        tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
        params=params, animal_info=animal_info,
    )
    if cohort is None:
        return []

    out: list[Path] = []
    for date in dates:
        path = build_trial_overlays(
            bodypart, animal, date, resolver,
            tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
            params=params, cohort=cohort,
            animal_y_bounds=cohort.trial_y_lim,
            animal_x_bounds=cohort.trial_x_lim,
            overwrite=overwrite,
        )
        if path is not None:
            out.append(path)
    return out


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
        ("myl", "syl", "Mouse LEFT tones",
         f"{label} Y (px)", "overlay_Y_mouseLtones"),
        ("myr", "syr", "Mouse RIGHT tones",
         f"{label} Y (px)", "overlay_Y_mouseRtones"),
        ("mxl", "sxl", "Mouse LEFT tones",
         f"{label} X (px)", "overlay_X_mouseLtones"),
        ("mxr", "sxr", "Mouse RIGHT tones",
         f"{label} X (px)", "overlay_X_mouseRtones"),
    )


def _cohort_binned_specs(
    bodypart: str,
) -> tuple[tuple[str, str, str, str, str], ...]:
    label = _AXIS_LABEL[bodypart]
    return (
        ("myl", "syl", "Mouse LEFT tones",
         f"{label} Y (px)", "binnedOverlay_Y_mouseLtones"),
        ("myr", "syr", "Mouse RIGHT tones",
         f"{label} Y (px)", "binnedOverlay_Y_mouseRtones"),
        ("mxl", "sxl", "Mouse LEFT tones",
         f"{label} X (px)", "binnedOverlay_X_mouseLtones"),
        ("mxr", "sxr", "Mouse RIGHT tones",
         f"{label} X (px)", "binnedOverlay_X_mouseRtones"),
    )


def build_session_overlays(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    *,
    tone_pre_ms: int,
    tone_post_ms: int,
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
            tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
            params=params,
        )
    if cohort is None:
        return []

    center_mode = _resolve_center_mode(bodypart, params)
    out_dir = resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=center_mode,
        tone_pre_ms=tone_pre_ms,
        tone_post_ms=tone_post_ms,
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
    tone_pre_ms: int,
    tone_post_ms: int,
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
            tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
            params=params,
        )
    if cohort is None or not cohort.binned:
        return []

    center_mode = _resolve_center_mode(bodypart, params)
    out_dir = resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=center_mode,
        tone_pre_ms=tone_pre_ms,
        tone_post_ms=tone_post_ms,
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


# ===========================================================================
# Phase 7a.6 C4.2 — Mean trace (cells 45 / 32)
# ===========================================================================
#
# Cohort cross-session mean XY trajectory overlays. Per-(animal, window,
# bin_size_days), emits ONE PNG with two side-by-side panels (R left,
# L right per legacy convention; y-axis inverted so 0 sits at the top).
# Optionally aggregates session-mean trajectories into rel_day bins.
#
# Departures from cell 31/30 master-cell inputs:
#
# - X-range filter ON by default (legacy ``DO_X_RANGE_FILTER``): clips
#   x-values outside ±``xlim_pm_px`` to NaN before snippet extraction.
#   tongue uses 150 px, jaw uses 75 px (per-bodypart override block).
# - Time-domain moving-average smoothing on the per-(date, side) mean
#   trajectory (legacy ``TIME_SMOOTH_MOVAVG_MS = 40 ms``).
# - Per-(date, side) mean across trials (vs the master cell's per-side
#   mean+SEM stack).
#
# Q4 lock 2026-05-01: jaw cell 32's per-mouse multi-bin (``bin_sizes_days``
# list) is ported back to tongue. The public ``build_mean_trace`` accepts
# a ``bin_sizes_days`` int OR list[int]; one PNG is emitted per entry.


@dataclass(frozen=True)
class MeanTraceRow:
    """Per-(date, side) mean XY trajectory for one session.

    Returned in the ``rows`` list of :class:`MeanTraceCohort`. ``mx`` /
    ``my`` are the column means across trials (after the optional
    moving-average time smoothing). ``sx`` / ``sy`` are SEMs (also
    smoothed). ``rel_day`` is NaN if no ``stroke_date`` is configured for
    the animal.
    """

    date: datetime.date
    side: str
    rel_day: float
    n_trials: int
    fps: float
    pre_ms: float
    post_ms: float
    t_ms: np.ndarray = field(repr=False)
    mx: np.ndarray = field(repr=False)
    my: np.ndarray = field(repr=False)
    sx: np.ndarray = field(repr=False)
    sy: np.ndarray = field(repr=False)


@dataclass(frozen=True)
class BinnedTraceRow:
    """Cross-session aggregated mean XY trajectory within one rel_day bin.

    ``mx`` / ``my`` are means across the per-session ``mx`` / ``my``
    arrays in the bin (i.e., second-level mean: trials → session →
    cross-session). ``sx`` / ``sy`` are cross-session SEMs.
    """

    side: str
    rel_day_bin_label: str
    rel_day_bin_lo: int
    rel_day_bin_hi: int
    rel_day_bin_center: float
    n_sessions: int
    t_ms: np.ndarray = field(repr=False)
    mx: np.ndarray = field(repr=False)
    my: np.ndarray = field(repr=False)
    sx: np.ndarray = field(repr=False)
    sy: np.ndarray = field(repr=False)


@dataclass(frozen=True)
class MeanTraceCohort:
    """Cross-session aggregates for one ``(animal, bodypart, window, bin_size_days)``.

    Returned by :func:`build_mean_trace_cohort`. Consumed by
    :func:`build_mean_trace`. ``binned`` is empty when no ``stroke_date``
    is available or no bins could be constructed.
    """

    bodypart: str
    animal: str
    pre_ms: float
    post_ms: float
    bin_size_days: int
    fps: float
    cam: str
    interp_version: str
    rows: list[MeanTraceRow] = field(repr=False)
    binned: list[BinnedTraceRow] = field(repr=False)
    y_max: float
    suffix: str


# ----- additional helpers ported verbatim from cells 45/32 -----


def _moving_average_nan(y: np.ndarray, w: int) -> np.ndarray:
    """NaN-aware moving average. Direct port of legacy
    ``_moving_average_nan`` (lines 1002-1014 of vendored cell 45)."""
    y = np.asarray(y, float)
    if w <= 1:
        return y.copy()
    finite = np.isfinite(y)
    y0 = np.where(finite, y, 0.0)
    kernel = np.ones(int(w), dtype=float)
    num = np.convolve(y0, kernel, mode="same")
    den = np.convolve(finite.astype(float), kernel, mode="same")
    out = np.full_like(y, np.nan, dtype=float)
    good = den > 0
    out[good] = num[good] / den[good]
    return out


def _smooth_movavg_ms(
    arr: np.ndarray, win_ms: float, fps: float, stride: int = 1,
) -> np.ndarray:
    """Moving-average smoothing with the kernel width specified in ms.

    Direct port of legacy ``_smooth_movavg_ms`` (lines 1016-1022). Useful
    for time-axis smoothing of per-session mean trajectories (cells
    45/32 ``TIME_SMOOTH_MOVAVG_MS = 40 ms`` default).
    """
    if (win_ms is None) or (win_ms <= 0):
        return np.asarray(arr, float)
    dt_ms = (1000.0 / float(fps)) * float(stride)
    w = int(np.round(float(win_ms) / dt_ms))
    w = max(1, w)
    return _moving_average_nan(np.asarray(arr, float), w)


def _color_for_rel_day_continuous(
    rel_day: float, post_max: float | None,
    cmap_name: str = "plasma", pre_color: str = "0.6",
) -> Any:
    """Continuous (per-rel-day) version of :func:`_color_for_bin`.

    Cell 45's ``_color_for_rel_day``: rel_day <= 0 → pre_color (grey);
    rel_day >= 1 → linearly mapped onto cmap from 0..1 over [1, post_max].
    """
    if (
        rel_day is None
        or (not np.isfinite(rel_day))
        or rel_day <= 0
    ):
        return pre_color
    cmap = plt.get_cmap(cmap_name)
    if (
        post_max is None
        or (not np.isfinite(post_max))
        or post_max <= 1
    ):
        return cmap(0.85)
    u = (float(rel_day) - 1.0) / max(1.0, float(post_max) - 1.0)
    u = float(np.clip(u, 0.0, 1.0))
    return cmap(u)


def _abs_max_finite(arrays: Sequence[np.ndarray]) -> float:
    """Max absolute finite value across a sequence of arrays. Returns 1.0
    if no array contains finite values (defensive — shouldn't happen on
    real cohort data; protects animations against div-by-zero).
    """
    vals = []
    for a in arrays:
        if a is None:
            continue
        v = np.asarray(a, float).ravel()
        v = v[np.isfinite(v)]
        if v.size:
            vals.append(float(np.nanmax(np.abs(v))))
    return float(max(vals)) if vals else 1.0


def _union_symmetric_x_max(
    *,
    mx_per_side: dict[str, list[np.ndarray]],
    pad_frac: float = 0.05,
) -> float:
    """C7.2 Issue A — compute union-symmetric ``x_abs_max`` for a 2-panel
    L/R XY overlay plot.

    Takes max abs value across BOTH the L and R subplot data; the result
    is suitable for ``set_xlim(-x_abs_max, +x_abs_max)`` applied to both
    subplots so the X axis is centered on 0 (spout) and shared L+R.

    X-only (renamed from C7.2's ``_union_symmetric_xy_bounds``). Y axis
    has different semantics (legacy inverts via reversed set_ylim arg
    order); see :func:`_union_y_range_for_inversion`.
    """
    all_x: list[np.ndarray] = []
    for arrs in mx_per_side.values():
        all_x.extend(arrs)
    return _abs_max_finite(all_x) * (1.0 + pad_frac)


def _union_y_range_for_inversion(
    *,
    my_per_side: dict[str, list[np.ndarray]],
    pad_frac: float = 0.05,
    clip_y_lo_at_zero: bool = False,
) -> tuple[float, float]:
    """C7.3 — Y-range computation for legacy's inverted-Y convention.

    Returns ``(y_lo_padded, y_hi_padded)`` where the caller applies
    ``ax.set_ylim(y_hi_padded, y_lo_padded)`` (reversed args to invert
    the axis — legacy idiom; matches jaw cell 32 + jaw cell 34 + tongue
    cells 45/47/48). Pad fraction matches legacy: 5% on tongue cell 45 +
    mean_video; 10% on jaw cell 32 (latter wins per the
    consolidate-on-newer pattern, but we expose ``pad_frac`` so callers
    can override).

    ``clip_y_lo_at_zero`` (default False, matches jaw 32/34 newer
    convention): set True to reproduce tongue cell 45/47/48 older
    behavior of forcing ``y_lo = 0`` regardless of actual min. Default
    False allows the data range to extend below 0 (e.g., jaw can have
    occasional negative excursion below baseline).
    """
    all_y: list[np.ndarray] = []
    for arrs in my_per_side.values():
        all_y.extend(arrs)

    finite_vals: list[float] = []
    for a in all_y:
        if a is None:
            continue
        v = np.asarray(a, float).ravel()
        v = v[np.isfinite(v)]
        if v.size:
            finite_vals.append(float(np.nanmin(v)))
            finite_vals.append(float(np.nanmax(v)))
    if not finite_vals:
        return -1.0, 1.0
    y_lo = min(finite_vals)
    y_hi = max(finite_vals)
    if clip_y_lo_at_zero:
        y_lo = min(y_lo, 0.0)  # never push y_lo above 0 in clip mode
        y_lo = 0.0  # tongue cell 45 forces y_top = 0.0 explicitly
    rng = max(1e-6, y_hi - y_lo)
    pad = pad_frac * rng
    return y_lo - pad, y_hi + pad


def _plot_xy_mean(
    ax: Any, mx: np.ndarray, my: np.ndarray,
    sx: np.ndarray | None, sy: np.ndarray | None,
    color: Any, label: str | None = None,
    lw: float = 1.0, alpha: float = 0.4,
    show_tube: bool = False, tube_alpha: float = 0.16,
) -> None:
    """Plot a single XY trajectory + optional ±SEM tube. Direct port of
    legacy ``_plot_xy_mean`` (lines 1086-1096 of vendored cell 45).
    """
    ax.plot(mx, my, color=color, lw=lw, alpha=alpha, label=label)
    if not show_tube:
        return
    ok = np.isfinite(mx) & np.isfinite(my)
    if (sx is not None) and np.any(ok) and np.any(np.isfinite(sx)):
        ax.plot(mx + sx, my, color=color, lw=1.0, alpha=tube_alpha)
        ax.plot(mx - sx, my, color=color, lw=1.0, alpha=tube_alpha)
    if (sy is not None) and np.any(ok) and np.any(np.isfinite(sy)):
        ax.plot(mx, my + sy, color=color, lw=1.0, alpha=tube_alpha)
        ax.plot(mx, my - sy, color=color, lw=1.0, alpha=tube_alpha)


def _normalize_bin_sizes(
    bin_sizes_days: int | Sequence[int] | None,
    animal_info: AnimalInfo | None,
) -> list[int]:
    """Resolve a ``bin_sizes_days`` argument into a list of ints.

    ``None`` → singleton list of ``animal_info.bin_days`` (Q4 default).
    int → singleton list. Sequence → list (deduped, sorted ascending).
    Empty sequence → empty list (caller should treat as "no binning").
    """
    if bin_sizes_days is None:
        if animal_info is None:
            return [2]  # conservative fallback; 2 = audit majority
        return [int(animal_info.bin_days)]
    if isinstance(bin_sizes_days, int):
        return [int(bin_sizes_days)]
    out = sorted({int(b) for b in bin_sizes_days if int(b) > 0})
    return out


# ===========================================================================
# Mean-trace cohort builder
# ===========================================================================


def _load_session_xy_filtered(
    bodypart: str,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    do_x_range_filter: bool,
    xlim_pm_px: float,
) -> tuple[np.ndarray, np.ndarray, float, int, str]:
    """Read the 7a.2 parquet's ``x_final`` / ``y_final`` arrays + metadata,
    optionally clipping the x-range (legacy mean_trace ``DO_X_RANGE_FILTER``).
    """
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
    x = df["x_final"].to_numpy(dtype=float)
    y = df["y_final"].to_numpy(dtype=float)
    if do_x_range_filter:
        bad = (~np.isfinite(x)) | (np.abs(x) > float(xlim_pm_px))
        if np.any(bad):
            x = x.copy()
            y = y.copy()
            x[bad] = np.nan
            y[bad] = np.nan
    return x, y, fps, n_frames, interp_version


def _per_session_mean_xy(
    x: np.ndarray, y: np.ndarray,
    centers: np.ndarray, pre_f: int, post_f: int,
    *, fps: float, stride: int, do_smooth: bool, smooth_ms: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """Stack per-trial XY snippets, take column mean+SEM across trials,
    optionally apply moving-average time smoothing.

    Returns ``(mx, my, sx, sy, n_trials)``. SEM uses ``ddof=0`` (matches
    legacy ``_mean_sem_trials``).
    """
    if len(centers) == 0:
        T = pre_f + post_f + 1
        if stride > 1:
            T = len(np.arange(-pre_f, post_f + 1)[::stride])
        nan = np.full(T, np.nan, float)
        return nan, nan.copy(), nan.copy(), nan.copy(), 0

    xs_list = [_snippet(x, int(c), pre_f, post_f) for c in centers]
    ys_list = [_snippet(y, int(c), pre_f, post_f) for c in centers]
    if stride > 1:
        xs_list = [s[::stride] for s in xs_list]
        ys_list = [s[::stride] for s in ys_list]
    xs = np.vstack(xs_list)
    ys = np.vstack(ys_list)

    mx = np.nanmean(xs, axis=0)
    my = np.nanmean(ys, axis=0)
    n_eff_x = np.sum(np.isfinite(xs), axis=0)
    n_eff_y = np.sum(np.isfinite(ys), axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        sx = np.nanstd(xs, axis=0) / np.sqrt(np.maximum(1, n_eff_x))
        sy = np.nanstd(ys, axis=0) / np.sqrt(np.maximum(1, n_eff_y))
    if do_smooth and smooth_ms > 0:
        mx = _smooth_movavg_ms(mx, smooth_ms, fps=fps, stride=stride)
        my = _smooth_movavg_ms(my, smooth_ms, fps=fps, stride=stride)
        sx = _smooth_movavg_ms(sx, smooth_ms, fps=fps, stride=stride)
        sy = _smooth_movavg_ms(sy, smooth_ms, fps=fps, stride=stride)
    return mx, my, sx, sy, len(centers)


def build_mean_trace_cohort(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    *,
    tone_pre_ms: int,
    tone_post_ms: int,
    bin_size_days: int | None = None,
    params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> MeanTraceCohort | None:
    """Load + aggregate cross-session mean XY trajectories.

    For one ``(animal, bodypart, window, bin_size_days)`` combination,
    emits a :class:`MeanTraceCohort` with one :class:`MeanTraceRow` per
    eligible (date, side) and (when binning is requested + ``stroke_date``
    is set) one :class:`BinnedTraceRow` per (rel_day_bin, side). Returns
    ``None`` when no eligible sessions remain.

    ``bin_size_days`` defaults to ``animal_info.bin_days`` (Q4 lock).
    Pass an explicit int to override (e.g. iterating multiple sizes).
    """
    if bodypart not in _KNOWN_BODYPARTS:
        raise ValueError(
            f"bodypart must be one of {_KNOWN_BODYPARTS}; got {bodypart!r}",
        )

    if params is None:
        params = load_defaults()
    msv_block = (
        params.get("dlc_kinematics", {}).get("mean_sem_visual", {})
    )
    mt_block = msv_block.get("mean_trace", {})
    bp_block = msv_block.get(bodypart, {})
    bp_mt_block = bp_block.get("mean_trace", {})

    if animal_info is None:
        try:
            animal_info = get_animal(animal)
        except (KeyError, FileNotFoundError):
            animal_info = None

    bin_size_days_resolved = (
        int(bin_size_days) if bin_size_days is not None
        else (
            int(animal_info.bin_days) if animal_info is not None
            else int(msv_block.get("default_bin_size_days", 2))
        )
    )

    # Knobs (with per-bodypart override merge).
    do_x_range_filter = bool(mt_block.get("do_x_range_filter", True))
    xlim_pm_px = float(
        bp_mt_block.get("xlim_pm_px", mt_block.get("xlim_pm_px", 150.0)),
    )
    do_time_smooth = bool(mt_block.get("do_time_smooth", True))
    smooth_ms = float(mt_block.get("time_smooth_movavg_ms", 40.0))
    stride = int(mt_block.get("stride", 1))
    do_rel_day_bin = bool(mt_block.get("do_rel_day_bin", True))
    cam = str(msv_block.get("cam", "cam2"))
    prepost_mode = str(msv_block.get("prepost_mode", "both"))
    rel_day_range_cfg = msv_block.get("rel_day_range", None)
    rel_day_range: tuple[int, int] | None = None
    if rel_day_range_cfg is not None:
        rel_day_range = (
            int(rel_day_range_cfg[0]), int(rel_day_range_cfg[1]),
        )

    dates = _eligible_dates(
        animal, bodypart, resolver,
        animal_info=animal_info,
        prepost_mode=prepost_mode,
        rel_day_range=rel_day_range,
    )
    if not dates:
        return None

    rows: list[MeanTraceRow] = []
    fps0: float | None = None
    interp_version: str = "unknown"
    for d in dates:
        try:
            x, y, fps, _n_frames, iv = _load_session_xy_filtered(
                bodypart, animal, d, resolver,
                do_x_range_filter=do_x_range_filter,
                xlim_pm_px=xlim_pm_px,
            )
        except FileNotFoundError:
            continue

        if fps0 is None:
            fps0 = fps
            interp_version = iv
        elif abs(fps - fps0) > 1e-6:
            raise ValueError(
                f"{animal}: fps mismatch across sessions: "
                f"{d.isoformat()} has {fps}, expected {fps0}",
            )

        manifest = build_manifest(
            animal, d, resolver, animal_info,
            analysis_context=f"dlc.kinematics.{bodypart}.mean_trace",
        )
        try:
            centers_L, centers_R, _ = _derive_reward_events_for_bodypart(
                bodypart, animal, d, resolver, manifest,
            )
        except FileNotFoundError:
            continue

        pre_f = max(0, int(round((float(tone_pre_ms) / 1000.0) * fps)))
        post_f = max(0, int(round((float(tone_post_ms) / 1000.0) * fps)))
        t_ms_full = np.arange(-pre_f, post_f + 1) * (1000.0 / fps)
        t_ms = t_ms_full[::stride] if stride > 1 else t_ms_full

        rel_day = (
            float(animal_info.day_relative_to_stroke(d))
            if (animal_info is not None and animal_info.stroke_date is not None)
            else float("nan")
        )

        for side, centers in (("L", centers_L), ("R", centers_R)):
            if len(centers) == 0:
                continue
            mx, my, sx, sy, n_trials = _per_session_mean_xy(
                x, y, centers, pre_f, post_f,
                fps=fps, stride=stride,
                do_smooth=do_time_smooth, smooth_ms=smooth_ms,
            )
            rows.append(MeanTraceRow(
                date=d, side=side, rel_day=rel_day,
                n_trials=n_trials, fps=fps,
                pre_ms=float(tone_pre_ms),
                post_ms=float(tone_post_ms),
                t_ms=t_ms, mx=mx, my=my, sx=sx, sy=sy,
            ))

    if not rows or fps0 is None:
        return None

    binned: list[BinnedTraceRow] = []
    if (
        do_rel_day_bin
        and animal_info is not None
        and animal_info.stroke_date is not None
    ):
        rel_days = np.array(
            [r.rel_day for r in rows if np.isfinite(r.rel_day)], float,
        )
        bin_edges = _make_rel_day_bins(rel_days, bin_size=bin_size_days_resolved)
        if bin_edges:
            # Aggregate per (side, bin).
            t_ms_ref = rows[0].t_ms
            for side in ("L", "R"):
                for lo, hi in bin_edges:
                    grp = [
                        r for r in rows
                        if (
                            r.side == side
                            and np.isfinite(r.rel_day)
                            and lo <= int(r.rel_day) <= hi
                        )
                    ]
                    if not grp:
                        continue
                    mxM = np.vstack([r.mx for r in grp])
                    myM = np.vstack([r.my for r in grp])
                    mx = np.nanmean(mxM, axis=0)
                    my = np.nanmean(myM, axis=0)
                    n = max(1, mxM.shape[0])
                    sx = np.nanstd(mxM, axis=0) / np.sqrt(n)
                    sy = np.nanstd(myM, axis=0) / np.sqrt(n)
                    binned.append(BinnedTraceRow(
                        side=side,
                        rel_day_bin_label=_bin_label(int(lo), int(hi)),
                        rel_day_bin_lo=int(lo),
                        rel_day_bin_hi=int(hi),
                        rel_day_bin_center=float(_bin_center(int(lo), int(hi))),
                        n_sessions=len(grp),
                        t_ms=t_ms_ref, mx=mx, my=my, sx=sx, sy=sy,
                    ))

    # y_max: data-driven from binned aggregates if present, else per-session.
    y_lim_mode = str(mt_block.get("y_lim_mode", "robust"))
    y_robust_pct = tuple(mt_block.get("y_robust_pct", (1.0, 99.9)))
    y_pad_frac = float(mt_block.get("y_pad_frac", 0.1))
    arrs_for_y: list[np.ndarray] = []
    if binned:
        arrs_for_y = [b.my for b in binned]
    else:
        arrs_for_y = [r.my for r in rows]
    if y_lim_mode == "robust":
        _, y_hi_raw = _finite_percentile_range(
            arrs_for_y,
            pct_lo=float(y_robust_pct[0]),
            pct_hi=float(y_robust_pct[1]),
        )
    else:  # "minmax"
        _, y_hi_raw = _finite_minmax(arrs_for_y)
    if not np.isfinite(y_hi_raw) or y_hi_raw <= 0:
        y_hi_raw = 1.0
    y_max = float(y_hi_raw * (1.0 + y_pad_frac))

    # Suffix per legacy: encodes window + bin + smoothing + xlim + stroke.
    win_tag = f"{int(tone_pre_ms)}pre-{int(tone_post_ms)}post"
    suffix_parts = [win_tag]
    if do_rel_day_bin:
        suffix_parts.append(f"relDayBin{bin_size_days_resolved}d")
    if do_time_smooth:
        suffix_parts.append(f"timeSmooth{int(smooth_ms)}ms")
    if do_x_range_filter:
        suffix_parts.append(
            f"xlim-{int(xlim_pm_px)}to{int(xlim_pm_px)}",
        )
    if animal_info is not None and animal_info.stroke_date is not None:
        suffix_parts.append(
            f"d0_{animal_info.stroke_date.strftime('%Y%m%d')}_{prepost_mode}",
        )
    suffix = "_".join(suffix_parts)

    return MeanTraceCohort(
        bodypart=bodypart,
        animal=animal,
        pre_ms=float(tone_pre_ms),
        post_ms=float(tone_post_ms),
        bin_size_days=bin_size_days_resolved,
        fps=fps0,
        cam=cam,
        interp_version=interp_version,
        rows=rows,
        binned=binned,
        y_max=y_max,
        suffix=suffix,
    )


# ===========================================================================
# Phase 7a.6 C4.3 — Mean video (cells 47+48 / 34, Q5 consolidated)
# ===========================================================================
#
# Cohort binned-mean session XY trajectory ANIMATIONS. Q5 lock 2026-05-01:
# tongue's split (Cell 47 basic + Cell 48 with-frame-timestamps) is
# consolidated into one entry point with ``with_frame_timestamps: bool``
# kwarg defaulting to True (matches jaw Cell 34 + tongue Cell 48 behavior).
#
# Output filename pattern (matches legacy):
#   {animal}_{cam}_sessionMeanXY_BINNED_VIDEO_interp-{ver}_
#   win{-pre}to{post}ms_relDayBin{N}d_timeSmooth{T}ms_xlim-{lo}to{hi}_
#   mode-{cumulative|dot}_fps{F}_speed{S}[_tail{T}ms].{mp4|gif}
#
# Writer fallback (deviation from legacy verbatim, since the consolidated
# env may not have ffmpeg):
#   - ``video_format="mp4"`` and ffmpeg present → :class:`FFMpegWriter`.
#   - ``video_format="mp4"`` and ffmpeg missing → fall back to GIF via
#     :class:`PillowWriter` (always available), log the deviation, and
#     change the output filename suffix to ``.gif``. Caller can detect via
#     return ``Path.suffix``.
#   - ``video_format="gif"`` → :class:`PillowWriter`.
# Legacy cell 34 swallows the ffmpeg ImportError and prints a warning;
# the consolidated module is more explicit about the fallback so the
# parity harness can detect it.


def _resolve_animation_writer(
    video_format: str, anim_fps: int,
    *, allow_gif_fallback: bool = False,
) -> tuple[Any, str]:
    """Pick a matplotlib animation writer + final filename extension.

    Returns ``(writer, ext)``.

    Default behavior (``allow_gif_fallback=False``, C7.5): when
    ``video_format='mp4'`` is requested but ffmpeg is unavailable, raise
    ``RuntimeError`` rather than silently downgrading to GIF. The
    motivation is that GIF output (PillowWriter) produces ~10× larger
    files with posterized colors and no QuickTime playback on Mac, and
    we discovered (C7.5 review) that the previous silent fallback had
    leaked GIFs into cohort outputs unnoticed. Fail-loud surfaces the
    missing-dependency state at the production-rendering boundary.

    Opt-in fallback (``allow_gif_fallback=True``): emit a logging.WARNING
    and return PillowWriter with ``ext='gif'``. Reserved for dev/CI
    environments where ffmpeg cannot be installed; callers must pass the
    flag explicitly so the deviation is auditable.

    When ``video_format='gif'`` is requested explicitly, PillowWriter is
    always returned — no flag is needed.
    """
    import matplotlib.animation as mpl_anim

    fmt = str(video_format).lower()
    if fmt == "mp4":
        if mpl_anim.FFMpegWriter.isAvailable():
            return (mpl_anim.FFMpegWriter(fps=anim_fps, bitrate=12000), "mp4")
        if not allow_gif_fallback:
            raise RuntimeError(
                "ffmpeg is not available on PATH but video_format='mp4' "
                "was requested. Install ffmpeg in the env (it is bundled "
                "with environment.yml as of Phase 7a.6) or, to allow a "
                "GIF fallback for dev/CI environments, pass "
                "allow_gif_fallback=True (parity harness: "
                "--allow-gif-fallback).",
            )
        # Opt-in fallback to GIF (PillowWriter is always available).
        _logger.warning(
            "ffmpeg not found; falling back to GIF via PillowWriter "
            "(requested video_format='mp4', allow_gif_fallback=True). "
            "Output will have a .gif extension. Install ffmpeg in the "
            "env to emit MP4.",
        )
        return (mpl_anim.PillowWriter(fps=anim_fps), "gif")
    if fmt == "gif":
        return (mpl_anim.PillowWriter(fps=anim_fps), "gif")
    raise ValueError(
        f"video_format must be 'mp4' or 'gif'; got {video_format!r}",
    )


def _build_mean_video_animation(
    bodypart: str,
    cohort: MeanTraceCohort,
    msv_block: dict[str, Any],
    *,
    anim_mode: str,
    with_frame_timestamps: bool,
) -> tuple[Any, Any]:
    """Build a 2-panel (R-left, L-right) animation over the binned mean
    trajectories. Returns ``(fig, ani)`` matching the legacy
    :func:`make_animation` shape (jaw cell 34 lines 2081-2216).
    """
    import matplotlib.animation as mpl_anim

    if not cohort.binned:
        raise ValueError(
            f"{cohort.animal}: mean_video requires binned aggregates; "
            f"cohort has none (no stroke_date or no eligible bins).",
        )

    mt_block = msv_block.get("mean_trace", {})
    mv_block = msv_block.get("mean_video", {})
    bp_mt_block = (msv_block.get(bodypart, {}) or {}).get("mean_trace", {})

    pre_color = str(mt_block.get("pre_color", "0.6"))
    post_cmap = str(mt_block.get("post_cmap", "plasma"))
    bin_lw = 2.8           # legacy BIN_LW
    bin_alpha = 0.60       # legacy BIN_ALPHA
    show_tube = bool(mv_block.get("show_sem_tube", False))
    tube_alpha = float(mv_block.get("tube_alpha", 0.14))
    fig_w = float(
        bp_mt_block.get(
            "figure_width_inches", mt_block.get("figure_width_inches", 13.0),
        ),
    )
    fig_h = float(mt_block.get("figure_height_inches", 6.2))
    anim_fps = int(mv_block.get("anim_fps", 60))
    anim_speed = float(mv_block.get("anim_speed", 0.125))
    tail_ms = float(mv_block.get("tail_ms", 100.0))

    if anim_mode not in ("cumulative", "dot"):
        raise ValueError(
            f"anim_mode must be 'cumulative' or 'dot'; got {anim_mode!r}",
        )

    # Compute post_max for color mapping (mirrors legacy).
    post_centers = np.array(
        [b.rel_day_bin_center for b in cohort.binned if b.rel_day_bin_center >= 1],
        float,
    )
    post_max = float(np.nanmax(post_centers)) if post_centers.size else 1.0

    # C7.2 Issue A — drop sharey kwarg; explicit symmetric (-x, +x) /
    # (-y, +y) bounds applied below supersede share* anyway. Also avoids
    # the share* + set_aspect("equal", "box") + explicit set_ylim
    # interaction which sometimes produced subtle visual asymmetries.
    fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h))
    # C7.8: wspace=0.35 matches the C7.6 static-PNG fix
    # (mean_trace.panel_wspace in defaults.yaml). The mean_video
    # animation has its own subplots_adjust call distinct from
    # _plot_mean_trace_overlays — C7.6 missed this code path. The L
    # subplot's Y-axis tick labels overlap the R subplot's data on the
    # PS46 jaw mean_video at the older wspace=0.06 in the same way the
    # static PNG did at 0.10. right=0.78 unchanged (no legend on the
    # video frame; reserves space for the inset rel_day color bar).
    fig.subplots_adjust(right=0.78, wspace=0.35)
    # C7.2 Issue B: R trials on figure LEFT (cam-view; matches all 3
    # legacy mean_video cells 47/48/34). Already cam-view in C7.1; kept
    # explicit here for the C7.2 commit's documentation.
    ax_left, ax_right = axes[0], axes[1]
    side_to_ax = {"R": ax_left, "L": ax_right}

    # C7.2 Issue A — union-symmetric XY bounds across L+R subplot data.
    binned_by_side: dict[str, list[BinnedTraceRow]] = {"L": [], "R": []}
    for b in cohort.binned:
        binned_by_side[b.side].append(b)
    mx_per_side = {
        side: [b.mx for b in binned_by_side[side]]
        for side in ("L", "R")
    }
    my_per_side = {
        side: [b.my for b in binned_by_side[side]]
        for side in ("L", "R")
    }
    if not (mx_per_side["L"] or mx_per_side["R"]):
        raise ValueError(
            f"{cohort.animal}: no finite XY data in binned traces; cannot "
            f"compute animation axis limits.",
        )
    # C7.2 (X symmetric) + C7.3 (Y inverted, legacy idiom). Padding
    # 5% mirrors mean_video cell 34. See _plot_mean_trace_overlays for
    # full rationale on the X-symmetric / Y-inverted split.
    x_abs_max = _union_symmetric_x_max(
        mx_per_side=mx_per_side,
        pad_frac=0.05,
    )
    y_lo_padded, y_hi_padded = _union_y_range_for_inversion(
        my_per_side=my_per_side,
        pad_frac=0.05,
    )

    label_token = _AXIS_LABEL[bodypart]
    # ax_left = R trials (cam-view); ax_right = L trials.
    ax_left.set_title(f"{label_token} XY location, R trials")
    ax_right.set_title(f"{label_token} XY location, L trials")
    for ax in (ax_left, ax_right):
        ax.set_xlabel("x (px)")
        ax.set_ylabel("y (px)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.2)
        ax.set_xlim(-x_abs_max, +x_abs_max)
        # Y inverted via reversed set_ylim arg order — legacy idiom.
        ax.set_ylim(y_hi_padded, y_lo_padded)

    # Optional frame-time text labels (Q5 consolidate).
    time_text: dict[str, Any] = {}
    if with_frame_timestamps:
        for side in ("R", "L"):
            ax = side_to_ax[side]
            time_text[side] = ax.text(
                0.02, 0.98, "",
                transform=ax.transAxes,
                ha="left", va="top",
                fontsize=11,
                alpha=0.9,
            )

    # Legend (one shared rel_day-bin legend, anchored OUTSIDE the right
    # subplot via ax-level legend with axis-coord bbox). C7.4 fix mirrors
    # the _plot_mean_trace_overlays change — see that function's
    # comment for full rationale.
    from matplotlib.lines import Line2D
    uniq_bins = sorted(
        {(b.rel_day_bin_label, b.rel_day_bin_center) for b in cohort.binned},
        key=lambda kv: kv[1],
    )
    handles, labels = [], []
    for lab, cen in uniq_bins:
        n_sessions = sum(
            b.n_sessions for b in cohort.binned
            if b.rel_day_bin_label == lab
        )
        col = _color_for_rel_day_continuous(
            cen, post_max, cmap_name=post_cmap, pre_color=pre_color,
        )
        handles.append(Line2D([0], [0], color=col, lw=3.0))
        labels.append(f"{lab} (n={n_sessions})")
    ax_right.legend(
        handles, labels,
        title="rel_day bins",
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        frameon=False,
        ncol=1,
        handlelength=2.2,
        handletextpad=0.6,
        labelspacing=0.4,
    )

    title = (
        f"{cohort.animal} {cohort.cam} | interp={cohort.interp_version} | "
        f"window=-{int(cohort.pre_ms)}..{int(cohort.post_ms)} ms"
    )
    fig.suptitle(title, y=0.995)

    # Crop traces to a common length T.
    T = int(min(len(b.mx) for b in cohort.binned))
    if T < 2:
        plt.close(fig)
        raise ValueError(
            f"{cohort.animal}: not enough points in binned trajectories "
            f"to animate (T={T}).",
        )

    # Per-trace metadata (color, side, color-mapped to rel_day_bin_center).
    trace_data = []
    for b in cohort.binned:
        col = _color_for_rel_day_continuous(
            b.rel_day_bin_center, post_max,
            cmap_name=post_cmap, pre_color=pre_color,
        )
        trace_data.append({
            "side": b.side,
            "color": col,
            "lw": bin_lw,
            "alpha": bin_alpha,
            "x": np.asarray(b.mx[:T], float),
            "y": np.asarray(b.my[:T], float),
            "sx": np.asarray(b.sx[:T], float),
            "sy": np.asarray(b.sy[:T], float),
            "t_ms": np.asarray(cohort.binned[0].t_ms[:T], float),
        })

    tms0 = np.asarray(cohort.binned[0].t_ms[:T], float)
    if len(tms0) >= 2:
        dt_ms = float(np.nanmedian(np.diff(tms0)))
    else:
        dt_ms = 1000.0 / max(1.0, cohort.fps)
    tail_frames = max(1, int(np.round(tail_ms / max(1e-6, dt_ms))))

    # Set up artists per trace + anim_mode.
    artists: list[tuple[str, Any, dict[str, Any]]] = []
    for tr in trace_data:
        ax = side_to_ax.get(tr["side"], None)
        if ax is None:
            continue
        if anim_mode == "cumulative":
            (ln,) = ax.plot(
                [], [], color=tr["color"], lw=tr["lw"], alpha=tr["alpha"],
            )
            artists.append(("line", ln, tr))
        else:  # "dot"
            (tail_ln,) = ax.plot(
                [], [], color=tr["color"], lw=tr["lw"], alpha=tr["alpha"],
            )
            (dot_artist,) = ax.plot(
                [], [], marker="o", markersize=4.0, linestyle="None",
                color=tr["color"], alpha=min(1.0, tr["alpha"] + 0.25),
            )
            artists.append(("tail", tail_ln, tr))
            artists.append(("dot", dot_artist, tr))

    # Optional static SEM tubes (off by default per legacy mean_video block).
    if show_tube:
        for tr in trace_data:
            ax = side_to_ax.get(tr["side"], None)
            if ax is None:
                continue
            _plot_xy_mean(
                ax, tr["x"], tr["y"], tr["sx"], tr["sy"],
                color=tr["color"], lw=0.8, alpha=0.0,
                show_tube=True, tube_alpha=tube_alpha,
            )

    def _init() -> list[Any]:
        for _kind, artist, _tr in artists:
            artist.set_data([], [])
        if with_frame_timestamps:
            for side in ("R", "L"):
                if side in time_text:
                    time_text[side].set_text("")
        all_artists: list[Any] = [a[1] for a in artists]
        if with_frame_timestamps:
            all_artists.extend(time_text[s] for s in time_text)
        return all_artists

    def _update(frame_idx: int) -> list[Any]:
        k = int(np.clip(np.round(frame_idx * anim_speed), 0, T - 1))
        if with_frame_timestamps:
            t_here_ms = float(tms0[k]) if k < len(tms0) else (k * dt_ms)
            for side in time_text:
                time_text[side].set_text(f"t = {t_here_ms:,.0f} ms")
        for kind, artist, tr in artists:
            x = tr["x"]
            y = tr["y"]
            if anim_mode == "cumulative":
                if kind == "line":
                    artist.set_data(x[: k + 1], y[: k + 1])
            else:  # "dot"
                if kind == "tail":
                    lo = max(0, k - tail_frames)
                    artist.set_data(x[lo : k + 1], y[lo : k + 1])
                elif kind == "dot":
                    artist.set_data([x[k]], [y[k]])
        all_artists: list[Any] = [a[1] for a in artists]
        if with_frame_timestamps:
            all_artists.extend(time_text[s] for s in time_text)
        return all_artists

    n_frames = int(np.ceil((T - 1) / max(1e-6, anim_speed))) + 1
    ani = mpl_anim.FuncAnimation(
        fig,
        _update,
        frames=n_frames,
        init_func=_init,
        blit=False,
        interval=1000.0 / float(anim_fps),
    )
    return fig, ani


def _mean_video_filename(
    cohort: MeanTraceCohort,
    msv_block: dict[str, Any],
    bodypart: str,
    *,
    anim_mode: str,
    ext: str,
    animal_info: AnimalInfo | None,
) -> str:
    """Match legacy filename pattern (jaw cell 34 ``_build_outname``)."""
    mt_block = msv_block.get("mean_trace", {})
    mv_block = msv_block.get("mean_video", {})
    bp_mt = (msv_block.get(bodypart, {}) or {}).get("mean_trace", {})
    do_x_range_filter = bool(mt_block.get("do_x_range_filter", True))
    do_time_smooth = bool(mt_block.get("do_time_smooth", True))
    smooth_ms = float(mt_block.get("time_smooth_movavg_ms", 40.0))
    xlim_pm_px = int(
        bp_mt.get("xlim_pm_px", mt_block.get("xlim_pm_px", 150)),
    )
    anim_fps = int(mv_block.get("anim_fps", 60))
    anim_speed = float(mv_block.get("anim_speed", 0.125))
    tail_ms = float(mv_block.get("tail_ms", 100.0))

    parts = [
        cohort.animal,
        cohort.cam,
        "sessionMeanXY_BINNED_VIDEO",
        f"interp-{cohort.interp_version}",
        f"win-{int(cohort.pre_ms)}to{int(cohort.post_ms)}ms",
    ]
    if cohort.binned:
        parts.append(f"relDayBin{cohort.bin_size_days}d")
    if do_time_smooth:
        parts.append(f"timeSmooth{int(smooth_ms)}ms")
    if do_x_range_filter:
        parts.append(f"xlim-{xlim_pm_px}to{xlim_pm_px}")
    if animal_info is not None and animal_info.stroke_date is not None:
        prepost_mode = str(msv_block.get("prepost_mode", "both"))
        parts.append(
            f"d0_{animal_info.stroke_date.strftime('%Y%m%d')}_{prepost_mode}",
        )
    parts.append(f"mode-{anim_mode}")
    parts.append(f"fps{anim_fps}")
    parts.append(f"speed{anim_speed}")
    if anim_mode == "dot":
        parts.append(f"tail{int(tail_ms)}ms")
    return "_".join(parts) + f".{ext}"


def build_mean_video(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    *,
    tone_pre_ms: int,
    tone_post_ms: int,
    bin_sizes_days: int | Sequence[int] | None = None,
    modes: Sequence[str] | None = None,
    video_format: str | None = None,
    with_frame_timestamps: bool | None = None,
    params: dict[str, Any] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
    animal_info: AnimalInfo | None = None,
    allow_gif_fallback: bool = False,
) -> list[Path]:
    """Render the mean-video cohort animations.

    Q5 lock 2026-05-01: tongue cells 47 (basic) + 48 (with frame
    timestamps) consolidate to this single entry point with the
    ``with_frame_timestamps`` knob (defaulting to True from the
    ``mean_video`` config block — matches jaw cell 34 + tongue cell 48).

    For each ``(bin_size, mode)`` combination, emits one video file. The
    writer is chosen by :func:`_resolve_animation_writer`: MP4 via
    ffmpeg if available, GIF via PillowWriter as a fallback.

    Parameters
    ----------
    bodypart : {"tongue", "jaw"}
    animal, resolver
        Standard 7a.x signature.
    tone_pre_ms, tone_post_ms
        Tone-aligned window endpoints in milliseconds.
    bin_sizes_days : int | Sequence[int] | None
        Same semantics as :func:`build_mean_trace`. Default uses
        ``animal_info.bin_days``.
    modes : Sequence["cumulative" | "dot"] | None
        Animation modes to render. ``None`` reads ``save_both_modes``
        from the config block (default: both).
    video_format : "mp4" | "gif" | None
        Default reads from config (``mp4``). When ffmpeg is unavailable
        and ``video_format='mp4'`` is in effect, the call raises
        ``RuntimeError`` unless ``allow_gif_fallback=True`` (C7.5).
    allow_gif_fallback : bool
        When True, allow MP4→GIF fallback for environments without
        ffmpeg. Default False — fail-loud at the resolver. Reserved for
        dev/CI use; production cohort runs should leave this False so
        missing ffmpeg surfaces immediately.
    with_frame_timestamps : bool | None
        Q5 toggle. ``None`` reads config default (``True``, matches jaw
        cell 34 + tongue cell 48).

    Returns
    -------
    list[Path]
        Paths of the emitted video files. Empty list when the cohort has
        no binned aggregates (e.g., no ``stroke_date`` configured).
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )

    if params is None:
        params = load_defaults()
    msv_block = (
        params.get("dlc_kinematics", {}).get("mean_sem_visual", {})
    )
    mv_block = msv_block.get("mean_video", {})

    if animal_info is None:
        try:
            animal_info = get_animal(animal)
        except (KeyError, FileNotFoundError):
            animal_info = None

    if video_format is None:
        video_format = str(mv_block.get("video_format", "mp4"))
    if with_frame_timestamps is None:
        with_frame_timestamps = bool(
            mv_block.get("with_frame_timestamps", True),
        )
    if modes is None:
        modes = (
            ("cumulative", "dot") if bool(mv_block.get("save_both_modes", True))
            else (str(mv_block.get("animation_mode", "dot")),)
        )

    sizes = _normalize_bin_sizes(bin_sizes_days, animal_info)
    if not sizes:
        return []

    center_mode = _resolve_center_mode(bodypart, params)
    out_dir = resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=center_mode,
        tone_pre_ms=tone_pre_ms,
        tone_post_ms=tone_post_ms,
        plot_family="mean_xy_overlays",
        animal=animal,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    anim_fps = int(mv_block.get("anim_fps", 60))
    video_dpi = int(mv_block.get("video_dpi", 200))

    paths: list[Path] = []
    for size in sizes:
        cohort = build_mean_trace_cohort(
            bodypart, animal, resolver,
            tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
            bin_size_days=size,
            params=params, animal_info=animal_info,
        )
        if cohort is None or not cohort.binned:
            continue
        for mode in modes:
            writer, ext = _resolve_animation_writer(
                video_format, anim_fps,
                allow_gif_fallback=allow_gif_fallback,
            )
            fname = _mean_video_filename(
                cohort, msv_block, bodypart,
                anim_mode=mode, ext=ext,
                animal_info=animal_info,
            )
            out_path = out_dir / fname
            if overwrite == "skip" and out_path.exists():
                paths.append(out_path)
                continue
            fig, ani = _build_mean_video_animation(
                bodypart, cohort, msv_block,
                anim_mode=mode,
                with_frame_timestamps=with_frame_timestamps,
            )
            try:
                ani.save(str(out_path), writer=writer, dpi=video_dpi)
            finally:
                plt.close(fig)
            paths.append(out_path)
    return paths


def _plot_mean_trace_overlays(
    bodypart: str,
    cohort: MeanTraceCohort,
    msv_block: dict[str, Any],
    out_path: Path,
) -> None:
    """Two-panel mean XY trajectory figure (R left, L right; y-axis
    inverted so 0 sits at the top). Direct port of legacy
    ``plot overlays`` block in cell 45 (lines 1330-1450).
    """
    mt_block = msv_block.get("mean_trace", {})
    bp_mt_block = (msv_block.get(bodypart, {}) or {}).get("mean_trace", {})

    pre_color = str(mt_block.get("pre_color", "0.6"))
    post_cmap = str(mt_block.get("post_cmap", "plasma"))
    line_alpha = float(mt_block.get("line_alpha", 0.2))
    line_lw = float(mt_block.get("line_lw", 0.8))
    show_tube = bool(mt_block.get("show_sem_tube", True))
    tube_alpha = float(mt_block.get("tube_alpha", 0.15))
    plot_individual_when_binned = bool(
        mt_block.get("plot_individual_sessions_when_binned", True),
    )
    fig_h = float(mt_block.get("figure_height_inches", 6.2))
    fig_w = float(
        bp_mt_block.get(
            "figure_width_inches", mt_block.get("figure_width_inches", 13.0),
        ),
    )
    dpi = int(msv_block.get("dpi", 200))

    # C7.1 Issue 2 (legend layout). Adopt jaw cell 32's newer right-margin
    # legend placement (LEGEND_RIGHT=0.80, anchor at (0.75, 0.50)) instead
    # of tongue cell 45's older center-overlap placement (right=0.98 +
    # wspace=0.04 + bbox_to_anchor=(0.51, 0.52) which squeezed the legend
    # into the gap between subplots).
    legend_right = float(mt_block.get("legend_right_fraction", 0.80))
    legend_anchor_x = float(mt_block.get("legend_anchor_x", 0.75))
    legend_anchor_y = float(mt_block.get("legend_anchor_y", 0.50))
    panel_wspace = float(mt_block.get("panel_wspace", 0.10))
    symmetric_pad_frac = float(mt_block.get("symmetric_pad_frac", 0.05))

    rel_days = np.array(
        [r.rel_day for r in cohort.rows], float,
    )
    post_days = rel_days[np.isfinite(rel_days) & (rel_days >= 1)]
    post_max = float(np.max(post_days)) if post_days.size else 1.0

    # C7.2 Issue B: cam-view convention (R trials on figure LEFT,
    # L trials on figure RIGHT). The camera mirror-images the mouse, so
    # mouse-left appears on the right of the cam image and vice-versa.
    #
    # Deliberate departure from legacy: tongue cell 45 (older) already
    # uses cam-view; jaw cell 32 (newer) uses the OPPOSITE order
    # (L-LEFT, R-RIGHT — case 2 per the C7.2 review). C7.1 had adopted
    # jaw's order via the newer-jaw-wins pattern; that's reverted here
    # per Priya 2026-05-02 to match cam-view consistently across all
    # 2-panel L/R XY plots in the consolidated module. Documented as a
    # deliberate deviation in DECISIONS at Task 9.
    #
    # C7.2 Issue A: drop sharex/sharey kwargs because we set explicit
    # symmetric (-x, +x) / (-y, +y) bounds below — sharey + explicit
    # set_ylim + set_aspect("equal", adjustable="box") interaction was
    # confusing and could produce subtle visual asymmetries.
    fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h))
    fig.subplots_adjust(right=legend_right, wspace=panel_wspace)
    ax_left, ax_right = axes[0], axes[1]
    side_to_ax = {"R": ax_left, "L": ax_right}

    binned_by_side: dict[str, list[BinnedTraceRow]] = {"L": [], "R": []}
    for b in cohort.binned:
        binned_by_side[b.side].append(b)

    rows_by_side: dict[str, list[MeanTraceRow]] = {"L": [], "R": []}
    for r in cohort.rows:
        rows_by_side[r.side].append(r)

    # C7.2 Issue A (X) + C7.3 (Y) — shared L+R bounds, with legacy's
    # mixed convention preserved:
    #   - X axis: union-symmetric (-x_abs_max, +x_abs_max). Spout sits
    #     at x=0 in baseline-subtracted coords; centering on 0 makes
    #     L vs R cohort comparisons read directly off the figure.
    #   - Y axis: union-of-actual-range with INVERTED set_ylim (legacy
    #     convention). Mouse licks DOWN in cam coords (y INCREASES
    #     downward); legacy renders this with y=0 at the TOP of the
    #     plot and y=y_max at the BOTTOM via reversed ``set_ylim`` arg
    #     order. C7.2's symmetric ``(-y_abs_max, +y_abs_max)``
    #     accidentally dropped this inversion — Priya 2026-05-03 flagged
    #     the regression. This commit restores legacy idiom (jaw cell
    #     32 newer convention: y_lo allowed to go below 0 if the data
    #     warrants; pad_frac configurable; default 5%).
    #
    # Take bounds from binned aggregates if present (they're the
    # rendered-on-top layer the user sees); fall back to per-session
    # rows otherwise.
    if cohort.binned:
        mx_per_side = {
            side: [b.mx for b in binned_by_side[side]]
            for side in ("L", "R")
        }
        my_per_side = {
            side: [b.my for b in binned_by_side[side]]
            for side in ("L", "R")
        }
    else:
        mx_per_side = {
            side: [r.mx for r in rows_by_side[side]]
            for side in ("L", "R")
        }
        my_per_side = {
            side: [r.my for r in rows_by_side[side]]
            for side in ("L", "R")
        }
    x_abs_max = _union_symmetric_x_max(
        mx_per_side=mx_per_side,
        pad_frac=symmetric_pad_frac,
    )
    y_lo_padded, y_hi_padded = _union_y_range_for_inversion(
        my_per_side=my_per_side,
        pad_frac=symmetric_pad_frac,
    )

    # Per-axis styling. ax_left = R trials (cam-view). ax_right = L trials.
    for ax in (ax_left, ax_right):
        ax.set_xlabel("x (px, baseline-subtracted)")
        ax.set_ylabel("y (px, baseline-subtracted)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.2)
    ax_left.set_title("R trials | session mean XY overlays")
    ax_right.set_title("L trials | session mean XY overlays")
    # Apply identical bounds to both subplots. Y is inverted via
    # reversed ``set_ylim`` arg order (legacy idiom).
    for ax in (ax_left, ax_right):
        ax.set_xlim(-x_abs_max, +x_abs_max)
        ax.set_ylim(y_hi_padded, y_lo_padded)

    # Data plotting per side (uses side_to_ax + per-side rows + binned).
    for side in ("L", "R"):
        ax = side_to_ax[side]
        if cohort.binned:
            if plot_individual_when_binned:
                for r in rows_by_side[side]:
                    col = _color_for_rel_day_continuous(
                        r.rel_day, post_max,
                        cmap_name=post_cmap, pre_color=pre_color,
                    )
                    _plot_xy_mean(
                        ax, r.mx, r.my, None, None,
                        color=col, lw=1, alpha=0.1, show_tube=False,
                    )
            for b in binned_by_side[side]:
                col = _color_for_rel_day_continuous(
                    b.rel_day_bin_center, post_max,
                    cmap_name=post_cmap, pre_color=pre_color,
                )
                _plot_xy_mean(
                    ax, b.mx, b.my, b.sx, b.sy,
                    color=col, lw=2.5, alpha=0.6,
                    show_tube=show_tube, tube_alpha=tube_alpha,
                )
        else:
            for r in rows_by_side[side]:
                col = _color_for_rel_day_continuous(
                    r.rel_day, post_max,
                    cmap_name=post_cmap, pre_color=pre_color,
                )
                _plot_xy_mean(
                    ax, r.mx, r.my, r.sx, r.sy,
                    color=col, lw=line_lw, alpha=line_alpha,
                    show_tube=show_tube, tube_alpha=tube_alpha,
                )

    # Legend (binned mode only): rel_day bin entries anchored OUTSIDE
    # the right subplot's right edge. C7.4 fix (Priya 2026-05-03):
    # switch from figure-level legend to ax-level legend on ax_right,
    # with bbox in AXIS coords so the legend sits cleanly outside the
    # data area regardless of subplot extent. legend_anchor_x/y are now
    # axis-coord (was figure-coord pre-C7.4); see defaults.yaml comment.
    # Anchoring on ax_right (the L-trials subplot under cam-view) is
    # deliberate: the legend appears just to the right of the rightmost
    # subplot, with subplots_adjust(right=legend_right_fraction) above
    # reserving figure width for it.
    if cohort.binned:
        from matplotlib.lines import Line2D
        uniq = sorted(
            {(b.rel_day_bin_label, b.rel_day_bin_center) for b in cohort.binned},
            key=lambda kv: kv[1],
        )
        handles, labels = [], []
        for lab, cen in uniq:
            n_sessions = sum(
                b.n_sessions for b in cohort.binned
                if b.rel_day_bin_label == lab
            )
            col = _color_for_rel_day_continuous(
                cen, post_max,
                cmap_name=post_cmap, pre_color=pre_color,
            )
            handles.append(Line2D([0], [0], color=col, lw=3.0))
            labels.append(f"{lab} (n={n_sessions})")
        ax_right.legend(
            handles, labels,
            title="rel_day bins",
            loc="upper left",
            bbox_to_anchor=(legend_anchor_x, legend_anchor_y),
            borderaxespad=0.0,
            frameon=False,
            ncol=1,
            handlelength=2.2,
            handletextpad=0.6,
            labelspacing=0.4,
        )

    title = (
        f"{cohort.animal} {cohort.cam} | mean XY lick trajectory overlays "
        f"| interp={cohort.interp_version} | "
        f"window=-{int(cohort.pre_ms)}..{int(cohort.post_ms)} ms"
    )
    if cohort.binned:
        title += f" | rel_day bin={cohort.bin_size_days}d"
    fig.suptitle(title, y=0.995)
    # Skip tight_layout — it would override our subplots_adjust right
    # margin reservation and squeeze the legend back into the plot area
    # (regression of the very Issue 2 fix this commit makes). Save with
    # bbox_inches="tight" still trims excess whitespace at the figure
    # boundary.
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def build_mean_trace(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    *,
    tone_pre_ms: int,
    tone_post_ms: int,
    bin_sizes_days: int | Sequence[int] | None = None,
    params: dict[str, Any] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
    animal_info: AnimalInfo | None = None,
) -> list[Path]:
    """Render the mean-trace cohort overlay (Q5: 1 PNG per ``bin_size_days``).

    For each entry in ``bin_sizes_days``, emits one PNG with R on the
    left subplot and L on the right (legacy convention; y-axis inverted
    so 0 sits at the top of the plot).

    ``bin_sizes_days``:
      - ``None`` → uses ``animal_info.bin_days`` (Q4 default).
      - ``int`` → singleton list.
      - ``Sequence[int]`` → one PNG per entry; useful for multi-bin
        comparison plots (jaw cell 32 newer-only feature, ported back to
        tongue per the consolidated module).

    Filename matches legacy:
    ``{mouse}_{cam}_sessionMeanXY_interp-{ver}_yLim-robust-{lo}to{hi}_
    win-{pre}to{post}ms_relDayBin{N}d_timeSmooth{T}ms_xlim-{lo}to{hi}_
    d0_{stroke}_{prepost}.png``.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}.",
        )

    if params is None:
        params = load_defaults()
    msv_block = (
        params.get("dlc_kinematics", {}).get("mean_sem_visual", {})
    )

    if animal_info is None:
        try:
            animal_info = get_animal(animal)
        except (KeyError, FileNotFoundError):
            animal_info = None

    sizes = _normalize_bin_sizes(bin_sizes_days, animal_info)
    if not sizes:
        return []

    center_mode = _resolve_center_mode(bodypart, params)
    out_dir = resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=center_mode,
        tone_pre_ms=tone_pre_ms,
        tone_post_ms=tone_post_ms,
        plot_family="mean_xy_overlays",
        animal=animal,
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for size in sizes:
        cohort = build_mean_trace_cohort(
            bodypart, animal, resolver,
            tone_pre_ms=tone_pre_ms, tone_post_ms=tone_post_ms,
            bin_size_days=size,
            params=params, animal_info=animal_info,
        )
        if cohort is None:
            continue
        # Legacy filename builder. ``-{pre}to{post}ms`` mirrors cell 45
        # line 1434 (``win{-int(PRE_MS)}to{int(POST_MS)}ms``).
        mt_block = msv_block.get("mean_trace", {})
        do_x_range_filter = bool(mt_block.get("do_x_range_filter", True))
        do_time_smooth = bool(mt_block.get("do_time_smooth", True))
        smooth_ms = float(mt_block.get("time_smooth_movavg_ms", 40.0))
        bp_mt = (msv_block.get(bodypart, {}) or {}).get("mean_trace", {})
        xlim_pm_px = int(
            bp_mt.get("xlim_pm_px", mt_block.get("xlim_pm_px", 150)),
        )
        y_lim_mode = str(mt_block.get("y_lim_mode", "robust"))
        y_robust_pct = mt_block.get("y_robust_pct", (1.0, 99.9))

        parts = [
            cohort.animal,
            cohort.cam,
            "sessionMeanXY",
            f"interp-{cohort.interp_version}",
        ]
        if y_lim_mode == "robust":
            parts.append(
                f"yLim-robust-{y_robust_pct[0]}to{y_robust_pct[1]}",
            )
        parts.append(
            f"win-{int(cohort.pre_ms)}to{int(cohort.post_ms)}ms",
        )
        if cohort.binned:
            parts.append(f"relDayBin{cohort.bin_size_days}d")
        if do_time_smooth:
            parts.append(f"timeSmooth{int(smooth_ms)}ms")
        if do_x_range_filter:
            parts.append(f"xlim-{xlim_pm_px}to{xlim_pm_px}")
        if (
            animal_info is not None
            and animal_info.stroke_date is not None
        ):
            prepost_mode = str(msv_block.get("prepost_mode", "both"))
            parts.append(
                f"d0_{animal_info.stroke_date.strftime('%Y%m%d')}_"
                f"{prepost_mode}",
            )
        fname = "_".join(parts) + ".png"
        out_path = out_dir / fname
        if overwrite == "skip" and out_path.exists():
            paths.append(out_path)
            continue
        _plot_mean_trace_overlays(
            bodypart, cohort, msv_block, out_path,
        )
        paths.append(out_path)
    return paths


# ===========================================================================
# Composite wrappers (orchestration notebooks call these)
# ===========================================================================


def build_mean_sem_by_animal_date(
    bodypart: str,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    time_windows_ms: Sequence[tuple[int, int]] | None = None,
    params: dict[str, Any] | None = None,
    cohort_cache: dict[tuple[int, int], CohortAggregates] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, list[Path]]:
    """Per-(animal, date) composite — runs every per-session family across
    every time window.

    Iterates over ``time_windows_ms`` (``None`` → ``msv.time_windows_ms``
    from defaults) and calls :func:`build_individual_sessions` +
    :func:`build_trial_overlays` for each. Cohort aggregates are
    cached per window so the inner loop loads each cohort once even
    when the orchestration notebook calls this helper for many dates in
    sequence (caller may pre-seed ``cohort_cache``).

    Returns a mapping keyed by family name with the list of emitted
    PNG paths (one per window per family, ordered as the windows
    iterable).
    """
    if params is None:
        params = load_defaults()
    msv_block = (
        params.get("dlc_kinematics", {}).get("mean_sem_visual", {})
    )
    if time_windows_ms is None:
        time_windows_ms = [
            tuple(w) for w in msv_block.get(
                "time_windows_ms", [(100, 1000), (500, 5000)],
            )
        ]
    if cohort_cache is None:
        cohort_cache = {}

    if animal_info is None:
        try:
            animal_info = get_animal(animal)
        except (KeyError, FileNotFoundError):
            animal_info = None

    out: dict[str, list[Path]] = {
        "individual_sessions": [],
        "trial_overlays": [],
    }
    for pre_ms, post_ms in time_windows_ms:
        key = (int(pre_ms), int(post_ms))
        cohort = cohort_cache.get(key)
        if cohort is None:
            cohort = build_cohort_aggregates(
                bodypart, animal, resolver,
                tone_pre_ms=key[0], tone_post_ms=key[1],
                params=params, animal_info=animal_info,
            )
            if cohort is not None:
                cohort_cache[key] = cohort
        if cohort is None:
            continue
        ind_path = build_individual_sessions(
            bodypart, animal, date, resolver,
            tone_pre_ms=key[0], tone_post_ms=key[1],
            params=params, cohort=cohort, overwrite=overwrite,
        )
        if ind_path is not None:
            out["individual_sessions"].append(ind_path)
        trial_path = build_trial_overlays(
            bodypart, animal, date, resolver,
            tone_pre_ms=key[0], tone_post_ms=key[1],
            params=params, cohort=cohort, overwrite=overwrite,
        )
        if trial_path is not None:
            out["trial_overlays"].append(trial_path)
    return out


def build_mean_sem_cohort(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    *,
    time_windows_ms: Sequence[tuple[int, int]] | None = None,
    bin_sizes_days: int | Sequence[int] | None = None,
    include_mean_video: bool = True,
    mean_video_windows: Sequence[tuple[int, int]] | None = None,
    allow_gif_fallback: bool = False,
    params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, list[Path]]:
    """Per-animal composite — runs every cohort family across every time
    window (and every ``bin_sizes_days`` for ``mean_trace`` /
    ``mean_video``).

    Families covered:
      - ``session_overlays``: 4 PNGs per (animal, window).
      - ``binned_overlays``: 4 PNGs per (animal, window).
      - ``mean_trace``: 1 PNG per (animal, window, bin_size_days).
      - ``mean_video``: 1 video per (animal, window, bin_size_days, mode).

    ``include_mean_video`` defaults to ``True``. Set to ``False`` to skip
    the (potentially-slow) animation rendering — useful for fast cohort
    sweeps where only the static plot families are needed.

    ``mean_video_windows`` (C7.7) — when not ``None``, gates mean_video
    per-window emit to only the listed ``(pre_ms, post_ms)`` pairs.
    Other families ignore this allow-list. ``None`` (default) means no
    gating; mean_video emits for every entry in ``time_windows_ms``.

    ``allow_gif_fallback`` (C7.5) forwarded to :func:`build_mean_video`;
    defaults to ``False`` (fail-loud on missing ffmpeg).
    """
    if params is None:
        params = load_defaults()
    msv_block = (
        params.get("dlc_kinematics", {}).get("mean_sem_visual", {})
    )
    if time_windows_ms is None:
        time_windows_ms = [
            tuple(w) for w in msv_block.get(
                "time_windows_ms", [(100, 1000), (500, 5000)],
            )
        ]

    if animal_info is None:
        try:
            animal_info = get_animal(animal)
        except (KeyError, FileNotFoundError):
            animal_info = None

    out: dict[str, list[Path]] = {
        "session_overlays": [],
        "binned_overlays": [],
        "mean_trace": [],
        "mean_video": [],
    }
    for pre_ms, post_ms in time_windows_ms:
        key = (int(pre_ms), int(post_ms))
        cohort = build_cohort_aggregates(
            bodypart, animal, resolver,
            tone_pre_ms=key[0], tone_post_ms=key[1],
            params=params, animal_info=animal_info,
        )
        if cohort is not None:
            out["session_overlays"].extend(
                build_session_overlays(
                    bodypart, animal, resolver,
                    tone_pre_ms=key[0], tone_post_ms=key[1],
                    params=params, cohort=cohort, overwrite=overwrite,
                ),
            )
            out["binned_overlays"].extend(
                build_binned_overlays(
                    bodypart, animal, resolver,
                    tone_pre_ms=key[0], tone_post_ms=key[1],
                    params=params, cohort=cohort, overwrite=overwrite,
                ),
            )
        out["mean_trace"].extend(
            build_mean_trace(
                bodypart, animal, resolver,
                tone_pre_ms=key[0], tone_post_ms=key[1],
                bin_sizes_days=bin_sizes_days,
                params=params, animal_info=animal_info,
                overwrite=overwrite,
            ),
        )
        if include_mean_video:
            mv_allow = (
                mean_video_windows is None
                or (key[0], key[1]) in [
                    (int(a), int(b)) for a, b in mean_video_windows
                ]
            )
            if mv_allow:
                out["mean_video"].extend(
                    build_mean_video(
                        bodypart, animal, resolver,
                        tone_pre_ms=key[0], tone_post_ms=key[1],
                        bin_sizes_days=bin_sizes_days,
                        params=params, animal_info=animal_info,
                        overwrite=overwrite,
                        allow_gif_fallback=allow_gif_fallback,
                    ),
                )
    return out


__all__ = [
    "MEAN_SEM_VISUAL_VERSION",
    "PLOT_FAMILIES_ALL",
    "PLOT_FAMILIES_C4_1",
    "PLOT_FAMILIES_C4_2",
    "PLOT_FAMILIES_C4_3",
    "BinnedTraceRow",
    "CohortAggregates",
    "MeanTraceCohort",
    "MeanTraceRow",
    "SessionAggregates",
    "build_binned_overlays",
    "build_cohort_aggregates",
    "build_individual_sessions",
    "build_individual_sessions_animal",
    "build_mean_sem_by_animal_date",
    "build_mean_sem_cohort",
    "build_mean_trace",
    "build_mean_trace_cohort",
    "build_mean_video",
    "build_session_overlays",
    "build_trial_overlays",
    "build_trial_overlays_animal",
]
