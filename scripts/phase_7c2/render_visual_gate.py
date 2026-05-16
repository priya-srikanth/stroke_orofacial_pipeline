"""Phase 7c.2 Task 5 — Compute-on-demand spatial visual-gate driver.

Renders SVG heatmaps per Addendum #3 Q4.B for the locked 5-family /
10-bodypart allowlist (Q10.A). Outputs:

  1. Per-animal full-panel SVGs at
     ``pipeline_outputs/dlc_analysis/spatial_visual_gate/<animal>/<family>/<bodypart>/<trial_group>_<window>.svg``
     — one SVG per (animal × bodypart × trial_group × window) cell;
     content is the cohort-aggregated heatmap (sum of all in-YAML-
     range session histograms for that animal).

  2. Cohort tile-grid SVGs at
     ``pipeline_outputs/dlc_analysis/spatial_visual_gate/cohort/<family>/<bodypart>/<trial_group>_<window>.svg``
     — one SVG per (bodypart × trial_group × window) cell; 8 subplots
     in a 4×2 (or similar) grid, one per animal. Each subplot shows
     that animal's aggregated heatmap for the cell.

Cohort-aggregated histograms are computed ONCE per cell + cached in
memory; both the per-animal SVG and the cohort tile-grid subplot
re-render from the cached (H_counts, extent) without re-reading
parquets.

Allowlist (Q10.A, 10 individual bodyparts across 5 families):

  tongue_spout_midpoint  : tongue / spout_midpoint
  tongue_eye_midpoint    : tongue / eye_midpoint
  jaw_eye_midpoint       : jaw / eye_midpoint
  nose_eye_midpoint      : nose / eye_midpoint
  whiskers_eye_midpoint  : L_whiskers_1/2/3 + R_whiskers_1/2/3 / eye_midpoint

Per (animal × bodypart × trial_group × window): 3 trial_groups
("all", "L", "R") × 2 windows ((-100, 1000), (-500, 5000)) =
6 SVGs/cell. Total per-animal SVGs = 10 bp × 6 = 60. Cohort total:
8 × 60 = 480. Cohort tile-grids: 10 bp × 6 = 60.

Per-animal sub-batching mirrors Task 3/4 (--animal flag); no-flag
invocation iterates the full cohort order.

Output dir layout (paths above) writes directly to MICROSCOPE
production paths under ``pipeline_outputs/dlc_analysis/
spatial_visual_gate/``. Cohort tile-grids land at
``<root>/cohort/<family>/<bodypart>/<tg>_<window>.svg``. The
``spatial_visual_gate/`` root is NEW and replaces the cache-based
``spatial_tone_aligned/`` tree per Addendum #3 Interpretation 1.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import (
    EXPECTED_TONE_ALIGNED_FAMILIES,
    load_defaults,
    load_session_overrides,
)
from stroke_orofacial.dlc_spatial.render_on_demand import (
    compute_animal_aggregated_histogram,
    render_h_counts_panel,
)
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

TRIAL_GROUPS = ("all", "L", "R")
WINDOWS_MS = ((-100.0, 1000.0), (-500.0, 5000.0))

# Reuses Task 3/4's walk-then-filter date enumeration. Same canonical
# config from .scratch_phase_7c2/legacy_state_audit.csv.
CANON_BP_CM = "tongue_spout_midpoint"
CANON_WIN = "trials-all_-100to1000ms"


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c2.render_visual_gate")


def _enumerate_yaml_filtered_dates(animal: str, resolver: PathResolver) -> list[dt.date]:
    """Walk legacy spatial tree + filter by YAML range + add Pattern A
    dates (mirrors Task 3/4 enumeration). Returns dt.date list in
    chronological order. Same behavior as the function in
    reemit_cohort.py / reemit_cohort_aggregates.py.
    """
    import re

    output_root = resolver.pipeline_outputs("dlc_analysis")
    canon_dir = output_root / "spatial_reward_aligned" / CANON_BP_CM / CANON_WIN / animal
    animal_info = get_animal(animal)
    start = animal_info.session_start
    end = animal_info.session_end

    dates: set[dt.date] = set()
    if canon_dir.exists():
        for npz in sorted(canon_dir.glob("heatmap_*.npz")):
            m = re.match(r"heatmap_(\d{8})\.npz", npz.name)
            if not m:
                continue
            ds = m.group(1)
            d = dt.date(int(ds[0:4]), int(ds[4:6]), int(ds[6:8]))
            if start <= d <= end:
                dates.add(d)

    overrides = load_session_overrides()
    mh = overrides.get("multi_half_sessions", {}) or {}
    for ds in (mh.get(animal, {}) or {}).keys():
        d = dt.date(int(ds[0:4]), int(ds[4:6]), int(ds[6:8]))
        if start <= d <= end:
            dates.add(d)

    return sorted(dates)


def _iter_allowlist_cells() -> list[tuple[str, str, str]]:
    """Yield (family_name, bodypart, center_mode) for every allowlist
    bodypart. Whisker family fans out to 6 individual bodyparts; other
    families to 1 bodypart each. Total: 10 cells."""
    cells: list[tuple[str, str, str]] = []
    for family_name, fam in EXPECTED_TONE_ALIGNED_FAMILIES.items():
        cm = fam["center_mode"]
        for bp in fam["bodyparts"]:
            cells.append((family_name, bp, cm))
    return cells


def _window_label(window_ms: tuple[float, float]) -> str:
    return f"{int(window_ms[0])}to{int(window_ms[1])}ms"


def _per_animal_svg_path(
    root: Path, animal: str, family: str, bodypart: str,
    trial_group: str, window_ms: tuple[float, float],
) -> Path:
    return (
        root / animal / family / bodypart
        / f"{trial_group}_{_window_label(window_ms)}.svg"
    )


def _cohort_tile_svg_path(
    root: Path, family: str, bodypart: str,
    trial_group: str, window_ms: tuple[float, float],
) -> Path:
    return (
        root / "cohort" / family / bodypart
        / f"{trial_group}_{_window_label(window_ms)}.svg"
    )


def _render_cohort_tile_grid(
    cache: dict[str, tuple],
    family: str,
    bodypart: str,
    center_mode: str,
    trial_group: str,
    window_ms: tuple[float, float],
    out_path: Path,
    *,
    defaults: dict,
) -> None:
    """Render an 8-subplot cohort tile-grid SVG. Each subplot is one
    animal's cached aggregated heatmap for the (bp, cm, tg, win) cell.
    Layout: 4 cols × 2 rows."""
    ncols = 4
    nrows = math.ceil(len(COHORT_ORDER) / ncols)
    fig, axes = plt.subplots(
        nrows=nrows, ncols=ncols, figsize=(ncols * 4.0, nrows * 3.5),
        constrained_layout=True,
    )
    axes_flat = axes.flat if hasattr(axes, "flat") else [axes]
    for animal, ax in zip(COHORT_ORDER, axes_flat, strict=False):
        key = f"{animal}|{bodypart}|{center_mode}|{trial_group}|{_window_label(window_ms)}"
        cached = cache.get(key)
        if cached is None:
            ax.text(0.5, 0.5, animal + "\n(not cached)",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue
        H, ext, n_sess, n_tones = cached
        title = f"{animal} n_sess={n_sess}"
        if window_ms is not None and trial_group is not None:
            title += f" n_tones={n_tones}"
        render_h_counts_panel(
            H, ext, bodypart, center_mode,
            title=title, defaults=defaults, ax=ax,
        )
    # Hide unused trailing axes if cohort < ncols*nrows.
    for ax in list(axes_flat)[len(COHORT_ORDER):]:
        ax.set_axis_off()
    suptitle = (
        f"COHORT  {family}/{bodypart}  tg={trial_group}  "
        f"win=[{int(window_ms[0])}, {int(window_ms[1])}] ms"
    )
    fig.suptitle(suptitle, fontsize=12)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg")
    plt.close(fig)


def _process_animal(
    animal: str,
    resolver: PathResolver,
    defaults: dict,
    root: Path,
    cache: dict[str, tuple],
) -> tuple[int, float]:
    """Render all 60 per-animal SVGs (10 bp × 6 cells) for one animal.
    Caches (H, extent, n_sess, n_tones) keyed by
    ``{animal}|{bp}|{cm}|{tg}|{win_label}`` for downstream cohort
    tile-grid reuse.

    Returns ``(n_svgs_written, runtime_seconds)``.
    """
    t0 = time.perf_counter()
    log.info(f"=== animal={animal}: rendering per-animal visual gate ===")
    dates = _enumerate_yaml_filtered_dates(animal, resolver)
    log.info(f"  {len(dates)} in-YAML-range dates")
    if not dates:
        log.warning(f"  animal={animal} has 0 dates; skipping.")
        return 0, time.perf_counter() - t0
    animal_info = get_animal(animal)

    n_svgs = 0
    for family_name, bodypart, center_mode in _iter_allowlist_cells():
        for tg in TRIAL_GROUPS:
            for win in WINDOWS_MS:
                H, ext, n_sess, n_tones = compute_animal_aggregated_histogram(
                    animal, dates, bodypart, center_mode, resolver,
                    trial_group=tg, window_ms=win,
                    defaults=defaults, animal_info=animal_info,
                )
                key = f"{animal}|{bodypart}|{center_mode}|{tg}|{_window_label(win)}"
                cache[key] = (H, ext, n_sess, n_tones)
                title = (
                    f"{animal}  {bodypart}/{center_mode}  tg={tg}  "
                    f"win=[{int(win[0])}, {int(win[1])}] ms  "
                    f"n_sess={n_sess} n_tones={n_tones}"
                )
                fig = render_h_counts_panel(
                    H, ext, bodypart, center_mode,
                    title=title, defaults=defaults,
                )
                out = _per_animal_svg_path(root, animal, family_name, bodypart, tg, win)
                out.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(out, format="svg")
                plt.close(fig)
                n_svgs += 1
        log.info(
            f"  family={family_name} bodypart={bodypart} done "
            f"(per-animal SVGs so far: {n_svgs})"
        )
    rt = time.perf_counter() - t0
    log.info(f"=== animal={animal}: complete — {n_svgs} per-animal SVGs in {rt:.1f}s ({rt/60:.1f} min) ===")
    return n_svgs, rt


def _render_all_cohort_tile_grids(
    cache: dict[str, tuple],
    defaults: dict,
    root: Path,
) -> int:
    """Render the 60 cohort tile-grid SVGs from the in-memory cache.
    Returns the number of SVGs written. Skips cells where every animal
    is missing (rare; render_h_counts_panel handles per-cell empties)."""
    log.info("=== rendering cohort tile-grids ===")
    n_svgs = 0
    for family_name, bodypart, center_mode in _iter_allowlist_cells():
        for tg in TRIAL_GROUPS:
            for win in WINDOWS_MS:
                out = _cohort_tile_svg_path(root, family_name, bodypart, tg, win)
                _render_cohort_tile_grid(
                    cache, family_name, bodypart, center_mode, tg, win,
                    out, defaults=defaults,
                )
                n_svgs += 1
        log.info(
            f"  cohort family={family_name} bodypart={bodypart} done "
            f"(cohort tile-grids so far: {n_svgs})"
        )
    log.info(f"=== cohort tile-grids: {n_svgs} SVGs written ===")
    return n_svgs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--animal",
        choices=COHORT_ORDER,
        help="Process a single animal. Default: iterate the full Cohort A order.",
    )
    parser.add_argument(
        "--skip-cohort-tile-grids",
        action="store_true",
        help="Render per-animal SVGs only; skip cohort tile-grids. Useful when "
             "iterating one animal at a time and deferring tile-grid render until "
             "all animals have populated the cache.",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    defaults = load_defaults()
    root = resolver.pipeline_outputs("dlc_analysis") / "spatial_visual_gate"
    log.info(f"output root: {root}")

    animals = [args.animal] if args.animal else list(COHORT_ORDER)
    cache: dict[str, tuple] = {}

    total_per_animal = 0
    total_rt = 0.0
    for animal in animals:
        n_svgs, rt = _process_animal(animal, resolver, defaults, root, cache)
        total_per_animal += n_svgs
        total_rt += rt

    cohort_n = 0
    if not args.skip_cohort_tile_grids and args.animal is None:
        cohort_n = _render_all_cohort_tile_grids(cache, defaults, root)

    log.info(
        f"=== VISUAL-GATE SUMMARY: per-animal SVGs={total_per_animal}, "
        f"cohort tile-grids={cohort_n}, total runtime={total_rt:.1f}s "
        f"({total_rt/60:.1f} min) ==="
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
