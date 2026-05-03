"""Phase 7a.6 — Mean/SEM visual gate parity harness + cohort runner.

Two modes (matching the 7a.2/7a.3/7a.5 precedent shape, adapted to
the artifact landscape this phase actually has):

- ``default``: deterministic re-run check on consolidated arrays. Loads
  each cohort twice through the consolidated module and asserts bit-
  stable per-session arrays across re-runs. Catches accidental
  nondeterminism in the helper pipeline.
- ``legacy_approximate``: numerical parity vs the LEGACY NPZ inputs at
  ``atol=1e-6`` over the 14-session scope. Per the kickoff: "Numerical
  parity is load-bearing — if the consolidated implementation drifts
  from legacy at the data level, the visual gate is a waste".

  Legacy emits ONLY PNGs/MP4s for the 6 mean_sem_visual families (no
  per-family CSVs / NPZs; audit ``.scratch_7a6/output_inventory.md``),
  so traditional artifact-vs-artifact CSV comparison is N/A. Instead,
  the harness compares the two real drift vectors:

  1. Per-frame ``x_final`` / ``y_final`` arrays — legacy NPZ
     (``processed_interpolated_data/{mouse}_{date}_cam2_{bp}_interp_v5p3
     .npz``) vs consolidated 7a.2 parquet
     (``dlc_analysis/interpolated_traces/{bp}/{animal}/{date}.parquet``).
  2. Per-side reward-frame indices — legacy NPZ ``fr_reward_mouseL/R``
     vs consolidated ``_derive_reward_events_for_bodypart()`` output.

  Everything downstream of these two inputs (cohort aggregation, mean+
  SEM, day-binning) is verbatim helper port from the legacy cells (see
  the ``mean_sem_visual.py`` docstring) — so if these match exactly, the
  rest of the cohort math matches by construction.

CLI::

    python tests/scripts/parity_phase7a6_mean_sem.py \\
        --mode {default, legacy_approximate} \\
        --bodyparts tongue,jaw \\
        --windows 100,1000:500,5000 \\
        --animals PS46,PS51,PS54,PS55 \\
        --sessions auto \\
        --emit-root .scratch_7a6/cohort_run \\
        [--skip-mean-video] [--skip-cohort-emit] [--allow-gif-fallback]

The harness DOUBLES as the Task 6 cohort runner: in either ``--mode``,
it emits PNGs (and optionally GIFs) for every covered (animal, bodypart,
window) combination into ``--emit-root`` (skip via ``--skip-cohort-emit``).

Output report at ``{emit_root}/parity_report.md``: per-animal section
with per-(bodypart, window) family file counts + ffmpeg fallback counts
+ deterministic-re-run results + per-(animal, date, bodypart) legacy
NPZ comparison metrics + cohort wall-time.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_phase7a3_tongue_pertrial as h7a3  # type: ignore[import]

from stroke_orofacial.dlc_kinematics import mean_sem_visual as msv
from stroke_orofacial.paths import PathResolver

ATOL_DEFAULT = 1e-6

DEFAULT_ANIMALS: tuple[str, ...] = (
    "PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55",
)
DEFAULT_BODYPARTS: tuple[str, ...] = ("tongue", "jaw")
DEFAULT_WINDOWS_MS: tuple[tuple[int, int], ...] = (
    (100, 1000),
    (500, 5000),
)


@dataclass
class CohortResult:
    """One per (animal, bodypart, window). Aggregated into the report."""

    animal: str
    bodypart: str
    pre_ms: int
    post_ms: int
    cohort_loaded: bool = False
    n_sessions: int = 0
    n_individual_sessions: int = 0
    n_trial_overlays: int = 0
    n_session_overlays: int = 0
    n_binned_overlays: int = 0
    n_mean_trace: int = 0
    n_mean_video: int = 0
    n_mean_video_gif_fallback: int = 0
    deterministic: bool | None = None  # None if not checked
    deterministic_max_abs_delta: float = 0.0
    wall_time_s: float = 0.0
    notes: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class SessionParityResult:
    """One per (animal, date, bodypart). Legacy NPZ comparison metrics.

    Three metric families:
    - ``x_max_abs_delta`` / ``y_max_abs_delta`` — per-frame array diff
      between legacy NPZ and consolidated parquet (NaN-aware, ddof
      irrelevant since these are arrays not summary stats). Both should
      be 0 because 7a.2 already proved per-frame parity.
    - ``reward_L_match`` / ``reward_R_match`` — exact integer-array
      equality between legacy NPZ ``fr_reward_mouseL/R`` and
      consolidated ``_derive_reward_events_for_bodypart()`` output. The
      primary potential drift vector for 7a.6 (legacy reads from NPZ;
      consolidated re-derives via spout_behavior + alignment LUT).
    """

    animal: str
    date: dt.date
    bodypart: str
    legacy_npz_exists: bool = False
    consolidated_parquet_exists: bool = False
    x_n_compared: int = 0
    x_max_abs_delta: float = 0.0
    y_max_abs_delta: float = 0.0
    n_reward_L_legacy: int = 0
    n_reward_L_consolidated: int = 0
    reward_L_match: bool | None = None
    reward_L_diff_idxs: list[int] = field(default_factory=list)
    n_reward_R_legacy: int = 0
    n_reward_R_consolidated: int = 0
    reward_R_match: bool | None = None
    reward_R_diff_idxs: list[int] = field(default_factory=list)
    error: str | None = None


@dataclass
class HarnessConfig:
    mode: str
    bodyparts: list[str]
    windows: list[tuple[int, int]]
    animals: list[str]
    sessions_per_animal: dict[str, list[dt.date]]
    emit_root: Path
    skip_mean_video: bool
    skip_cohort_emit: bool
    atol: float
    allow_gif_fallback: bool = False


# ---------------------------------------------------------------------------
# MICROSCOPE preflight
# ---------------------------------------------------------------------------


_MICROSCOPE_LEGACY_ROOT = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
    r"\DeepLabCut\O2_analysis"
)


def _microscope_preflight(legacy_required: bool) -> tuple[bool, list[str]]:
    """Verify MICROSCOPE access for the consolidated tree (always) plus
    the legacy ``processed_interpolated_data`` tree (legacy_approximate
    mode only).

    Returns ``(ok, messages)``. ``ok=False`` short-circuits the harness
    before the cohort run kicks off — bad to discover halfway through.
    """
    msgs: list[str] = []
    consolidated_outputs = (
        PathResolver().pipeline_outputs("dlc_analysis").parent
    )
    if not consolidated_outputs.exists():
        msgs.append(
            f"FAIL — consolidated outputs root inaccessible: "
            f"{consolidated_outputs}",
        )
        return False, msgs
    msgs.append(f"OK — consolidated outputs: {consolidated_outputs}")

    if legacy_required:
        if not _MICROSCOPE_LEGACY_ROOT.exists():
            msgs.append(
                f"FAIL — legacy NPZ root inaccessible: "
                f"{_MICROSCOPE_LEGACY_ROOT}",
            )
            return False, msgs
        msgs.append(f"OK — legacy NPZ root: {_MICROSCOPE_LEGACY_ROOT}")
    return True, msgs


# ---------------------------------------------------------------------------
# Legacy NPZ comparison (legacy_approximate mode)
# ---------------------------------------------------------------------------


_LEGACY_CENTER_MODE_PER_BODYPART = {
    "tongue": "centered_spout_midpoint",
    "jaw": "centered_eye_midpoint",
}


def _legacy_npz_path(animal: str, date: dt.date, bodypart: str) -> Path:
    """Match the legacy
    ``{animal}_{bodypart}_kinematics/processed_interpolated_data/
    {center_mode}/{animal}_{date}_{cam}_{bodypart}_interp_{ver}.npz``
    pattern (cells 31/45/30/32 ``list_session_npzs_v5_only`` shape).
    """
    cm = _LEGACY_CENTER_MODE_PER_BODYPART[bodypart]
    date_str = date.strftime("%Y%m%d")
    return (
        _MICROSCOPE_LEGACY_ROOT
        / animal
        / f"{animal}_{bodypart}_kinematics"
        / "processed_interpolated_data"
        / cm
        / f"{animal}_{date_str}_cam2_{bodypart}_interp_v5p3.npz"
    )


def _max_abs_delta_arrays(a: np.ndarray, b: np.ndarray) -> float:
    """NaN-aware element-wise max abs delta. Both NaN at a position →
    treat as match (delta 0); otherwise compute |a - b|.
    """
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if a.shape != b.shape:
        return float("inf")
    both_nan = np.isnan(a) & np.isnan(b)
    diff = np.abs(a - b)
    diff[both_nan] = 0.0
    if not diff.size:
        return 0.0
    return float(np.nanmax(diff))


def session_parity_check(
    animal: str, date: dt.date, bodypart: str,
    resolver: PathResolver,
) -> SessionParityResult:
    """Compare consolidated parquet + reward derivation against legacy NPZ.

    Returns an SessionParityResult with per-array diffs + reward-index
    match flags. Errors during loading are captured into ``error``.
    """
    import pyarrow.parquet as pq

    from stroke_orofacial.dlc_kinematics.mean_sem_visual import (
        _derive_reward_events_for_bodypart,
    )
    from stroke_orofacial.manifest import build_manifest
    from stroke_orofacial.animals import get_animal

    res = SessionParityResult(animal=animal, date=date, bodypart=bodypart)

    legacy_path = _legacy_npz_path(animal, date, bodypart)
    res.legacy_npz_exists = legacy_path.exists()
    parquet_path = resolver.interpolated_trace(
        bodypart=bodypart, animal=animal, date=date,
    )
    res.consolidated_parquet_exists = parquet_path.exists()
    if not res.legacy_npz_exists:
        res.error = f"legacy NPZ missing: {legacy_path.name}"
        return res
    if not res.consolidated_parquet_exists:
        res.error = f"consolidated parquet missing: {parquet_path}"
        return res

    try:
        Z = np.load(legacy_path, allow_pickle=True)
        legacy_x = np.asarray(Z["x_final"], float)
        legacy_y = np.asarray(Z["y_final"], float)
        legacy_L = np.asarray(Z["fr_reward_mouseL"], int)
        legacy_R = np.asarray(Z["fr_reward_mouseR"], int)
    except Exception as e:  # noqa: BLE001
        res.error = f"failed to load legacy NPZ: {e}"
        return res

    try:
        df = pq.read_table(parquet_path).to_pandas()
        cons_x = df["x_final"].to_numpy(dtype=float)
        cons_y = df["y_final"].to_numpy(dtype=float)
    except Exception as e:  # noqa: BLE001
        res.error = f"failed to load consolidated parquet: {e}"
        return res

    if cons_x.shape != legacy_x.shape:
        res.error = (
            f"x_final shape mismatch: legacy={legacy_x.shape} "
            f"consolidated={cons_x.shape}"
        )
        return res

    res.x_n_compared = int(cons_x.size)
    res.x_max_abs_delta = _max_abs_delta_arrays(legacy_x, cons_x)
    res.y_max_abs_delta = _max_abs_delta_arrays(legacy_y, cons_y)

    # Reward-frame derivation comparison (the primary 7a.6 drift vector).
    try:
        animal_info = get_animal(animal)
    except (KeyError, FileNotFoundError):
        animal_info = None
    try:
        manifest = build_manifest(
            animal, date, resolver, animal_info,
            analysis_context=f"dlc.kinematics.{bodypart}.mean_sem_visual",
        )
        cons_L, cons_R, _ = _derive_reward_events_for_bodypart(
            bodypart, animal, date, resolver, manifest,
        )
    except Exception as e:  # noqa: BLE001
        res.error = f"reward derivation raised: {e}"
        return res

    legacy_L_sorted = np.sort(legacy_L.astype(int))
    legacy_R_sorted = np.sort(legacy_R.astype(int))
    cons_L_sorted = np.sort(cons_L.astype(int))
    cons_R_sorted = np.sort(cons_R.astype(int))

    res.n_reward_L_legacy = int(legacy_L_sorted.size)
    res.n_reward_L_consolidated = int(cons_L_sorted.size)
    res.n_reward_R_legacy = int(legacy_R_sorted.size)
    res.n_reward_R_consolidated = int(cons_R_sorted.size)

    res.reward_L_match = (
        res.n_reward_L_legacy == res.n_reward_L_consolidated
        and bool(np.array_equal(legacy_L_sorted, cons_L_sorted))
    )
    res.reward_R_match = (
        res.n_reward_R_legacy == res.n_reward_R_consolidated
        and bool(np.array_equal(legacy_R_sorted, cons_R_sorted))
    )

    # Capture diff indices for the report when reward arrays don't match.
    if not res.reward_L_match:
        if res.n_reward_L_legacy == res.n_reward_L_consolidated:
            res.reward_L_diff_idxs = [
                int(i) for i, (a, b) in enumerate(
                    zip(legacy_L_sorted, cons_L_sorted),
                ) if a != b
            ][:8]
    if not res.reward_R_match:
        if res.n_reward_R_legacy == res.n_reward_R_consolidated:
            res.reward_R_diff_idxs = [
                int(i) for i, (a, b) in enumerate(
                    zip(legacy_R_sorted, cons_R_sorted),
                ) if a != b
            ][:8]

    return res


def _parse_windows(spec: str) -> list[tuple[int, int]]:
    """Parse ``--windows 100,1000:500,5000`` → [(100, 1000), (500, 5000)]."""
    out: list[tuple[int, int]] = []
    for chunk in spec.split(":"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [p.strip() for p in chunk.split(",")]
        if len(parts) != 2:
            raise ValueError(
                f"--windows entries must be pre,post pairs separated by ':'; "
                f"got {chunk!r}",
            )
        out.append((int(parts[0]), int(parts[1])))
    return out


def _resolve_sessions(
    args_sessions: str, animals: list[str],
) -> dict[str, list[dt.date]]:
    """Resolve --sessions to a {animal: [dates]} mapping.

    ``auto`` → the canonical 14-session parity scope from 7a.3 (mirrors
    7a.2's interpolation-strategy.md §6).
    ``cohort`` → for each animal, every date that has a 7a.2 parquet on
    disk (per-bodypart will further filter at run time). Convenience for
    full-cohort runs over the consolidated tree.
    """
    out: dict[str, list[dt.date]] = defaultdict(list)
    if args_sessions == "auto":
        for animal, date in h7a3.PARITY_SESSIONS_14:
            if animal in animals:
                out[animal].append(date)
    elif args_sessions == "cohort":
        resolver = PathResolver()
        for animal in animals:
            seen: set[dt.date] = set()
            for bp in ("tongue", "jaw"):
                pq_dir = (
                    resolver.pipeline_outputs("dlc_analysis")
                    / "interpolated_traces" / bp / animal
                )
                if not pq_dir.exists():
                    continue
                for p in pq_dir.glob("*.parquet"):
                    try:
                        d = dt.datetime.strptime(p.stem, "%Y%m%d").date()
                    except ValueError:
                        continue
                    seen.add(d)
            out[animal] = sorted(seen)
    else:
        raise ValueError(
            f"--sessions must be 'auto' or 'cohort'; got {args_sessions!r}",
        )
    return dict(out)


# ---------------------------------------------------------------------------
# Deterministic re-run check
# ---------------------------------------------------------------------------


def _max_abs_delta_session_aggregates(
    a: msv.SessionAggregates, b: msv.SessionAggregates,
) -> float:
    """Compare two SessionAggregates side-by-side; return max |Δ| across
    every numeric field. Used by the default-mode determinism check.
    """
    keys = ("Ayl", "Ayr", "Axl", "Axr",
            "myl", "syl", "myr", "syr",
            "mxl", "sxl", "mxr", "sxr",
            "t_ms")
    max_delta = 0.0
    for k in keys:
        va = np.asarray(getattr(a, k), float)
        vb = np.asarray(getattr(b, k), float)
        if va.shape != vb.shape:
            return float("inf")
        # NaN-aware: if both NaN at a position, treat as equal.
        both_nan = np.isnan(va) & np.isnan(vb)
        diff = np.abs(va - vb)
        diff[both_nan] = 0.0
        max_delta = max(max_delta, float(np.nanmax(diff)) if diff.size else 0.0)
    if not np.isfinite(max_delta):
        return float("inf")
    return max_delta


def _determinism_check(
    bodypart: str,
    animal: str,
    resolver: PathResolver,
    pre_ms: int,
    post_ms: int,
) -> tuple[bool | None, float, str]:
    """Run build_cohort_aggregates twice and compare per-session arrays.

    Returns ``(passed, max_abs_delta, note)``. ``passed=None`` when the
    cohort can't be loaded (no eligible sessions, etc.) — that's not a
    failure, just a skip.
    """
    try:
        cohort_a = msv.build_cohort_aggregates(
            bodypart, animal, resolver,
            reward_pre_ms=pre_ms, reward_post_ms=post_ms,
        )
    except Exception as e:  # noqa: BLE001
        return None, 0.0, f"first build_cohort_aggregates raised: {e}"
    if cohort_a is None:
        return None, 0.0, "cohort empty (no eligible sessions)"
    try:
        cohort_b = msv.build_cohort_aggregates(
            bodypart, animal, resolver,
            reward_pre_ms=pre_ms, reward_post_ms=post_ms,
        )
    except Exception as e:  # noqa: BLE001
        return False, float("inf"), f"second build_cohort_aggregates raised: {e}"
    if cohort_b is None:
        return False, float("inf"), "second build returned None (first didn't)"
    if len(cohort_a.sessions) != len(cohort_b.sessions):
        return False, float("inf"), (
            f"session count mismatch: {len(cohort_a.sessions)} vs "
            f"{len(cohort_b.sessions)}"
        )
    max_delta = 0.0
    for sa, sb in zip(cohort_a.sessions, cohort_b.sessions):
        if sa.date != sb.date:
            return False, float("inf"), (
                f"date order mismatch at index {cohort_a.sessions.index(sa)}: "
                f"{sa.date} vs {sb.date}"
            )
        d = _max_abs_delta_session_aggregates(sa, sb)
        max_delta = max(max_delta, d)
    return (max_delta == 0.0), max_delta, "ok"


# ---------------------------------------------------------------------------
# Per-animal cohort emit
# ---------------------------------------------------------------------------


class _GifFallbackCounter(logging.Handler):
    """Count MP4→GIF fallback warnings per cohort emit."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage().lower()
        if "ffmpeg not found" in msg and "gif" in msg:
            self.count += 1


def cohort_emit_one(
    animal: str,
    bodypart: str,
    pre_ms: int,
    post_ms: int,
    sessions: list[dt.date],
    resolver: PathResolver,
    *,
    skip_mean_video: bool,
    skip_cohort_emit: bool,
    mode: str,
    allow_gif_fallback: bool = False,
) -> CohortResult:
    """Emit every supported family for one (animal, bodypart, window).

    The composite wrappers are used as the entry point so the harness
    matches the orchestration-notebook call shape. Determinism check
    runs in default mode only.
    """
    import time

    result = CohortResult(
        animal=animal, bodypart=bodypart,
        pre_ms=pre_ms, post_ms=post_ms,
    )

    t_start = time.monotonic()
    fallback_counter = _GifFallbackCounter()
    msv_logger = logging.getLogger(
        "stroke_orofacial.dlc_kinematics.mean_sem_visual",
    )
    msv_logger.addHandler(fallback_counter)
    try:
        try:
            cohort = msv.build_cohort_aggregates(
                bodypart, animal, resolver,
                reward_pre_ms=pre_ms, reward_post_ms=post_ms,
            )
        except Exception as e:  # noqa: BLE001
            result.error = f"build_cohort_aggregates raised: {e}"
            return result

        if cohort is None:
            result.notes.append("cohort empty (no eligible sessions)")
            return result

        result.cohort_loaded = True
        result.n_sessions = len(cohort.sessions)

        if not skip_cohort_emit:
            # Per-session families across all dates in this cohort.
            for sess in cohort.sessions:
                ind = msv.build_individual_sessions(
                    bodypart, animal, sess.date, resolver,
                    reward_pre_ms=pre_ms, reward_post_ms=post_ms,
                    cohort=cohort, overwrite="force",
                )
                if ind is not None:
                    result.n_individual_sessions += 1
                tro = msv.build_trial_overlays(
                    bodypart, animal, sess.date, resolver,
                    reward_pre_ms=pre_ms, reward_post_ms=post_ms,
                    cohort=cohort, overwrite="force",
                )
                if tro is not None:
                    result.n_trial_overlays += 1

            # Cohort families.
            result.n_session_overlays = len(msv.build_session_overlays(
                bodypart, animal, resolver,
                reward_pre_ms=pre_ms, reward_post_ms=post_ms,
                cohort=cohort, overwrite="force",
            ))
            result.n_binned_overlays = len(msv.build_binned_overlays(
                bodypart, animal, resolver,
                reward_pre_ms=pre_ms, reward_post_ms=post_ms,
                cohort=cohort, overwrite="force",
            ))
            result.n_mean_trace = len(msv.build_mean_trace(
                bodypart, animal, resolver,
                reward_pre_ms=pre_ms, reward_post_ms=post_ms,
                overwrite="force",
            ))
            if not skip_mean_video:
                video_paths = msv.build_mean_video(
                    bodypart, animal, resolver,
                    reward_pre_ms=pre_ms, reward_post_ms=post_ms,
                    overwrite="force",
                    allow_gif_fallback=allow_gif_fallback,
                )
                result.n_mean_video = len(video_paths)
            else:
                result.notes.append("mean_video skipped per --skip-mean-video")
        else:
            result.notes.append(
                "cohort emit skipped per --skip-cohort-emit (parity-only run)",
            )

        # Determinism check (always — fast).
        ok, max_delta, note = _determinism_check(
            bodypart, animal, resolver, pre_ms, post_ms,
        )
        result.deterministic = ok
        result.deterministic_max_abs_delta = max_delta
        if note != "ok":
            result.notes.append(f"determinism: {note}")

    finally:
        result.n_mean_video_gif_fallback = fallback_counter.count
        msv_logger.removeHandler(fallback_counter)
        result.wall_time_s = time.monotonic() - t_start

    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _format_animal_table(rows: list[CohortResult]) -> list[str]:
    if not rows:
        return ["  (no rows)"]
    out = []
    out.append(
        f"  {'bodypart':10s} {'window':16s} {'sess':5s} "
        f"{'ind':5s} {'tri':5s} {'sov':5s} {'bov':5s} "
        f"{'mtr':5s} {'mvi':5s} {'gif':5s} {'det':5s}",
    )
    out.append("  " + "-" * 100)
    for r in rows:
        det = "—" if r.deterministic is None else ("PASS" if r.deterministic else "FAIL")
        out.append(
            f"  {r.bodypart:10s} {f'{r.pre_ms}-{r.post_ms}ms':16s} "
            f"{r.n_sessions:5d} {r.n_individual_sessions:5d} "
            f"{r.n_trial_overlays:5d} {r.n_session_overlays:5d} "
            f"{r.n_binned_overlays:5d} {r.n_mean_trace:5d} "
            f"{r.n_mean_video:5d} {r.n_mean_video_gif_fallback:5d} {det:5s}",
        )
    return out


def write_report(
    cfg: HarnessConfig,
    results: list[CohortResult],
    parity_results: list[SessionParityResult],
    total_wall_s: float,
    preflight_msgs: list[str],
    report_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# Phase 7a.6 — Mean/SEM visual gate parity report\n")
    lines.append(f"- Mode: ``{cfg.mode}``")
    lines.append(f"- Atol: ``{cfg.atol}``")
    lines.append(f"- Bodyparts: ``{', '.join(cfg.bodyparts)}``")
    win_strs = [f"({a},{b})ms" for a, b in cfg.windows]
    lines.append(f"- Windows: ``{', '.join(win_strs)}``")
    lines.append(f"- Animals: ``{', '.join(cfg.animals)}``")
    n_sess = sum(len(v) for v in cfg.sessions_per_animal.values())
    lines.append(f"- Sessions in scope: ``{n_sess}``")
    lines.append(f"- Skip mean_video: ``{cfg.skip_mean_video}``")
    lines.append(f"- Skip cohort emit: ``{cfg.skip_cohort_emit}``")
    lines.append(f"- Allow GIF fallback: ``{cfg.allow_gif_fallback}``")
    lines.append(f"- Emit root: ``{cfg.emit_root}``")
    lines.append(f"- Total wall time: ``{total_wall_s:.1f} s``")
    lines.append("")

    lines.append("## Preflight\n")
    for m in preflight_msgs:
        lines.append(f"- {m}")
    lines.append("")

    lines.append("## Legacy artifact landscape (kickoff parity-table gap)\n")
    lines.append(
        "Phase 7a.6 master cell (Cell 31/30) + mean-trace cell (45/32) "
        "+ mean-video cell (47+48/34) emit ONLY PNGs / MP4s on "
        "MICROSCOPE — confirmed by Task 1d output inventory "
        "(`.scratch_7a6/output_inventory.md`). There are no per-family "
        "CSV / NPZ artifacts to compare numerically. The kickoff's "
        "Task 6 sketch table (per-session CSV / per-cohort CSV / "
        "per-session NPZ) describes legacy outputs that don't exist "
        "for these cells. Per the kickoff escape valve (\"document the "
        "gap and flag those families as visual-gate-only\"):\n",
    )
    lines.append("| Family | Legacy artifact | Numerical parity | Visual gate |")
    lines.append("|---|---|---|---|")
    lines.append(
        "| individual_sessions | PNG only | "
        "via x/y + reward inputs (this report) | Task 7 |",
    )
    lines.append(
        "| trial_overlays | PNG only | "
        "via x/y + reward inputs (this report) | Task 7 |",
    )
    lines.append(
        "| session_overlays | PNG only | "
        "via x/y + reward inputs (this report) | Task 7 |",
    )
    lines.append(
        "| binned_overlays | PNG only | "
        "via x/y + reward inputs (this report) | Task 7 |",
    )
    lines.append(
        "| mean_trace | PNG only | "
        "via x/y + reward inputs (this report) | Task 7 |",
    )
    lines.append(
        "| mean_video | MP4/GIF only | n/a (animation frames) | Task 7 |",
    )
    lines.append("")
    lines.append(
        "Numerical parity in legacy_approximate mode is asserted at the "
        "two real drift vectors (per-frame x/y arrays + reward-frame "
        "indices); the helper math downstream (`_mean_sem`, `_snippet`, "
        "`_stack_snippets`, `_moving_average_nan`, `_smooth_movavg_ms`, "
        "`_compute_binned`) is verbatim port from the legacy cells, so "
        "matching at the inputs implies matching at every downstream "
        "family by construction.\n",
    )

    if parity_results:
        lines.append("## Legacy NPZ parity (legacy_approximate mode)\n")
        lines.append(
            "Per (animal, date, bodypart): per-frame x_final / y_final "
            "max|Δ| vs legacy NPZ; reward index match between legacy "
            "NPZ ``fr_reward_mouseL/R`` and consolidated "
            "``_derive_reward_events_for_bodypart()`` output.",
        )
        lines.append("")
        lines.append(
            f"  {'animal':6s} {'date':12s} {'bp':6s} {'x_max|Δ|':12s} "
            f"{'y_max|Δ|':12s} {'rL':6s} {'rR':6s} {'note':40s}",
        )
        lines.append("  " + "-" * 100)
        x_overall = 0.0
        y_overall = 0.0
        rL_pass = rL_fail = rR_pass = rR_fail = 0
        n_skip = 0
        for r in parity_results:
            if r.error:
                n_skip += 1
                lines.append(
                    f"  {r.animal:6s} {r.date.isoformat():12s} {r.bodypart:6s} "
                    f"{'':12s} {'':12s} {'':6s} {'':6s} ERROR {r.error[:35]}",
                )
                continue
            x_overall = max(x_overall, r.x_max_abs_delta)
            y_overall = max(y_overall, r.y_max_abs_delta)
            if r.reward_L_match:
                rL_pass += 1
            else:
                rL_fail += 1
            if r.reward_R_match:
                rR_pass += 1
            else:
                rR_fail += 1
            extras = []
            if not r.reward_L_match:
                extras.append(
                    f"L: {r.n_reward_L_legacy}vs{r.n_reward_L_consolidated}",
                )
            if not r.reward_R_match:
                extras.append(
                    f"R: {r.n_reward_R_legacy}vs{r.n_reward_R_consolidated}",
                )
            note = "; ".join(extras)[:40] if extras else "ok"
            lines.append(
                f"  {r.animal:6s} {r.date.isoformat():12s} {r.bodypart:6s} "
                f"{r.x_max_abs_delta:.3e}    {r.y_max_abs_delta:.3e}    "
                f"{'PASS' if r.reward_L_match else 'FAIL':6s} "
                f"{'PASS' if r.reward_R_match else 'FAIL':6s} {note:40s}",
            )
        lines.append("")
        lines.append(
            f"**Overall**: x_max|Δ|={x_overall:.3e}, "
            f"y_max|Δ|={y_overall:.3e}, "
            f"reward_L: {rL_pass} PASS / {rL_fail} FAIL, "
            f"reward_R: {rR_pass} PASS / {rR_fail} FAIL, "
            f"{n_skip} SKIP/ERROR sessions.",
        )
        lines.append("")

    lines.append("## Per-animal cohort emit + determinism check\n")

    by_animal: dict[str, list[CohortResult]] = defaultdict(list)
    for r in results:
        by_animal[r.animal].append(r)

    for animal in cfg.animals:
        rows = by_animal.get(animal, [])
        n_sess_a = len(cfg.sessions_per_animal.get(animal, []))
        lines.append(f"### {animal} ({n_sess_a} sessions in scope)\n")
        if not rows:
            lines.append("- (no rows; not run for this animal)\n")
            continue
        legend = (
            "Columns: sess=loaded sessions, ind=individual_sessions PNGs, "
            "tri=trial_overlays PNGs, sov=session_overlays PNGs, "
            "bov=binned_overlays PNGs, mtr=mean_trace PNGs, "
            "mvi=mean_video files, gif=mp4→gif fallback warnings, "
            "det=determinism check (only in --mode default)."
        )
        lines.append(legend + "\n")
        lines.append("```")
        for line in _format_animal_table(rows):
            lines.append(line)
        lines.append("```\n")

        # Errors and notes per row.
        for r in rows:
            label = f"{r.bodypart} {r.pre_ms}-{r.post_ms}ms"
            if r.error:
                lines.append(f"- **{label} ERROR**: {r.error}")
            for note in r.notes:
                lines.append(f"- {label}: {note}")
            if r.deterministic is False:
                lines.append(
                    f"- **{label} determinism FAILED**: max|Δ|="
                    f"{r.deterministic_max_abs_delta:g}",
                )
        lines.append("")

    # Cohort summary.
    lines.append("## Cohort totals\n")
    counts: Counter[str] = Counter()
    fallbacks_total = 0
    det_pass = det_fail = det_skip = 0
    err_count = 0
    for r in results:
        counts["individual_sessions"] += r.n_individual_sessions
        counts["trial_overlays"] += r.n_trial_overlays
        counts["session_overlays"] += r.n_session_overlays
        counts["binned_overlays"] += r.n_binned_overlays
        counts["mean_trace"] += r.n_mean_trace
        counts["mean_video"] += r.n_mean_video
        fallbacks_total += r.n_mean_video_gif_fallback
        if r.deterministic is True:
            det_pass += 1
        elif r.deterministic is False:
            det_fail += 1
        else:
            det_skip += 1
        if r.error:
            err_count += 1
    lines.append("| Family | Total emitted |")
    lines.append("|---|---|")
    for fam in (
        "individual_sessions", "trial_overlays",
        "session_overlays", "binned_overlays",
        "mean_trace", "mean_video",
    ):
        lines.append(f"| {fam} | {counts[fam]} |")
    lines.append("")
    lines.append(
        f"- mean_video MP4→GIF fallbacks (env without ffmpeg): "
        f"**{fallbacks_total}**"
    )
    if cfg.mode == "default":
        lines.append(
            f"- Determinism check: {det_pass} pass, {det_fail} fail, "
            f"{det_skip} skip (no eligible sessions).",
        )
    if err_count:
        lines.append(f"- Errors: {err_count} cohort × bodypart × window rows.")
    else:
        lines.append("- Errors: none.")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="parity_phase7a6_mean_sem",
        description="Phase 7a.6 mean/SEM visual gate parity + cohort runner.",
    )
    parser.add_argument(
        "--mode", choices=("default", "legacy_approximate"),
        default="default",
        help=(
            "default = deterministic re-run check on consolidated arrays. "
            "legacy_approximate = ADDITIONAL per-(animal, date, bodypart) "
            "comparison vs legacy NPZ inputs (x/y arrays at atol; reward "
            "indices exact int match). Cohort emit runs in both modes."
        ),
    )
    parser.add_argument(
        "--bodyparts", default=",".join(DEFAULT_BODYPARTS),
        help=f"Comma-separated; default {','.join(DEFAULT_BODYPARTS)}",
    )
    parser.add_argument(
        "--windows",
        default=":".join(f"{p},{q}" for p, q in DEFAULT_WINDOWS_MS),
        help=(
            "Colon-separated 'pre_ms,post_ms' pairs. Default: "
            "100,1000:500,5000."
        ),
    )
    parser.add_argument(
        "--animals", default=",".join(DEFAULT_ANIMALS),
        help="Comma-separated; default: full cohort.",
    )
    parser.add_argument(
        "--sessions", default="auto",
        help=(
            "'auto' = canonical 14-session parity scope (h7a3."
            "PARITY_SESSIONS_14). 'cohort' = every (animal, date) in the "
            "consolidated 7a.2 inventory."
        ),
    )
    parser.add_argument(
        "--emit-root", type=Path, default=None,
        help=(
            "Output root for the cohort emit. Default ``None`` writes to the "
            "real MICROSCOPE consolidated outputs tree (matches the "
            "production path of every other 7a.x emit). Pass an explicit "
            "path to redirect to a local sandbox — caveat: the harness "
            "also reads 7a.2 parquets through the same resolver, so the "
            "sandbox path must already host a 7a.2 inventory."
        ),
    )
    parser.add_argument(
        "--report-path", type=Path,
        default=(
            Path(__file__).resolve().parent.parent.parent
            / ".scratch_7a6" / "cohort_run" / "parity_report.md"
        ),
        help=(
            "Where to write the parity report (always a local file even "
            "when --emit-root points to MICROSCOPE)."
        ),
    )
    parser.add_argument(
        "--skip-mean-video", action="store_true",
        help=(
            "Skip animation rendering (PillowWriter is slow). PNG-only "
            "cohort sweeps benefit; visual gate inspection of MP4/GIF "
            "still requires running with this flag off."
        ),
    )
    parser.add_argument(
        "--skip-cohort-emit", action="store_true",
        help=(
            "Skip the cohort PNG/GIF emit; run only the parity checks "
            "(determinism + legacy-NPZ comparison if mode allows)."
        ),
    )
    parser.add_argument(
        "--atol", type=float, default=ATOL_DEFAULT,
        help=(
            "Tolerance reported in the parity table. Used by the "
            "determinism check (max|Δ| should be 0.0 across re-runs) "
            "and by the legacy_approximate per-frame x/y comparison."
        ),
    )
    parser.add_argument(
        "--allow-gif-fallback", action="store_true",
        help=(
            "Allow MP4→GIF fallback in mean_video when ffmpeg is not on "
            "PATH. Default: fail-loud (RuntimeError). Reserved for dev/CI "
            "environments where ffmpeg cannot be installed; production "
            "cohort runs should leave this unset (C7.5)."
        ),
    )
    args = parser.parse_args(argv)

    import time

    bodyparts = [b.strip() for b in args.bodyparts.split(",") if b.strip()]
    windows = _parse_windows(args.windows)
    animals = [a.strip() for a in args.animals.split(",") if a.strip()]
    sessions_per_animal = _resolve_sessions(args.sessions, animals)

    cfg = HarnessConfig(
        mode=args.mode,
        bodyparts=bodyparts,
        windows=windows,
        animals=animals,
        sessions_per_animal=sessions_per_animal,
        emit_root=args.emit_root,
        skip_mean_video=bool(args.skip_mean_video),
        skip_cohort_emit=bool(args.skip_cohort_emit),
        atol=float(args.atol),
        allow_gif_fallback=bool(args.allow_gif_fallback),
    )

    print(f"Phase 7a.6 mean/SEM parity harness — mode={cfg.mode}")
    print(f"  bodyparts: {bodyparts}")
    print(f"  windows: {windows}")
    print(f"  animals: {animals}")
    n_sess = sum(len(v) for v in sessions_per_animal.values())
    print(f"  sessions in scope: {n_sess} (across {len(animals)} animals)")
    print(f"  emit_root: {cfg.emit_root or '<real MICROSCOPE>'}")
    print(f"  report_path: {args.report_path}")
    print(f"  skip_mean_video: {cfg.skip_mean_video}")
    print(f"  skip_cohort_emit: {cfg.skip_cohort_emit}")
    print()

    # Preflight — fail fast before kicking off the cohort run.
    print("Preflight:")
    legacy_required = (cfg.mode == "legacy_approximate")
    ok, preflight_msgs = _microscope_preflight(legacy_required=legacy_required)
    for m in preflight_msgs:
        print(f"  {m}")
    if not ok:
        print()
        print("Preflight FAILED — aborting.")
        return 2
    print()

    t_total_start = time.monotonic()

    if cfg.emit_root is None:
        resolver = PathResolver()  # real MICROSCOPE path
    else:
        resolver = PathResolver(output_root=cfg.emit_root)
    results: list[CohortResult] = []
    parity_results: list[SessionParityResult] = []

    for animal in animals:
        sessions = sessions_per_animal.get(animal, [])
        if not sessions:
            print(f">>> {animal}: 0 sessions in scope; skipping")
            continue
        print(f">>> {animal}: {len(sessions)} sessions in scope")

        # Per-(animal, date, bodypart) legacy NPZ parity (legacy_approximate
        # mode only). Run before the cohort emit so failures surface early.
        if cfg.mode == "legacy_approximate":
            real_resolver = PathResolver()
            for date in sessions:
                for bodypart in bodyparts:
                    pr = session_parity_check(
                        animal, date, bodypart, real_resolver,
                    )
                    parity_results.append(pr)
                    if pr.error:
                        print(
                            f"    [parity {bodypart} {date.isoformat()}] "
                            f"ERROR: {pr.error}",
                        )
                    else:
                        rL = "PASS" if pr.reward_L_match else "FAIL"
                        rR = "PASS" if pr.reward_R_match else "FAIL"
                        print(
                            f"    [parity {bodypart} {date.isoformat()}] "
                            f"x_max|Δ|={pr.x_max_abs_delta:.3e} "
                            f"y_max|Δ|={pr.y_max_abs_delta:.3e} "
                            f"rL={rL} rR={rR}",
                        )

        for bodypart in bodyparts:
            for pre_ms, post_ms in windows:
                print(f"    [{bodypart} | win {pre_ms}-{post_ms}ms]", end=" ", flush=True)
                r = cohort_emit_one(
                    animal, bodypart, pre_ms, post_ms,
                    sessions=sessions,
                    resolver=resolver,
                    skip_mean_video=cfg.skip_mean_video,
                    skip_cohort_emit=cfg.skip_cohort_emit,
                    mode=cfg.mode,
                    allow_gif_fallback=cfg.allow_gif_fallback,
                )
                results.append(r)
                if r.error:
                    print(f"ERROR: {r.error}")
                else:
                    det = (
                        "—" if r.deterministic is None
                        else ("PASS" if r.deterministic else "FAIL")
                    )
                    print(
                        f"sess={r.n_sessions} ind={r.n_individual_sessions} "
                        f"tri={r.n_trial_overlays} sov={r.n_session_overlays} "
                        f"bov={r.n_binned_overlays} mtr={r.n_mean_trace} "
                        f"mvi={r.n_mean_video} gif={r.n_mean_video_gif_fallback} "
                        f"det={det} {r.wall_time_s:.1f}s"
                    )

    total_wall_s = time.monotonic() - t_total_start

    write_report(
        cfg, results, parity_results, total_wall_s, preflight_msgs,
        args.report_path,
    )
    print()
    print(f"Total wall time: {total_wall_s:.1f} s")
    print(f"Report written to {args.report_path}")

    n_err = sum(1 for r in results if r.error)
    n_det_fail = sum(1 for r in results if r.deterministic is False)
    n_parity_fail = sum(
        1 for p in parity_results
        if (p.reward_L_match is False or p.reward_R_match is False
            or p.x_max_abs_delta > cfg.atol or p.y_max_abs_delta > cfg.atol)
    )
    return 1 if (n_err or n_det_fail or n_parity_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
