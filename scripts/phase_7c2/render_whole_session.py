"""Phase 7c.2 Task 5 — Whole-session spatial heatmap driver (Addendum #3
Q4.B / retired Phase 7c.3).

Renders whole-session (non-tone-aligned) heatmap SVGs per the locked
Q10.A 5-family / 10-bodypart allowlist. Each SVG aggregates frames
across all in-YAML-range sessions for one (animal × bodypart ×
center_mode) cell, with no tone-window filtering — so the heatmap
captures the full session's spatial distribution of the bodypart.

Output layout:

  1. Per-animal full-panel SVGs at
     ``pipeline_outputs/dlc_analysis/spatial_whole_session_visual_gate/<animal>/<family>/<bodypart>.svg``
     — one SVG per (animal × bodypart) cell; content is cohort-
     aggregated whole-session heatmap.

  2. Cohort tile-grid SVGs at
     ``pipeline_outputs/dlc_analysis/spatial_whole_session_visual_gate/cohort/<family>/<bodypart>.svg``
     — 8 subplots (one per animal) of cell-level whole-session
     aggregates.

Cohort scope: 10 bodyparts (across 5 families) × 8 animals = 80
per-animal SVGs + 10 cohort tile-grids = 90 SVGs total. No trial_group
or window fanout under whole-session.

Same in-memory caching as render_visual_gate.py: per-cell (H_counts,
extent, n_sessions) computed once + reused for per-animal panel +
cohort tile-grid subplot.

Replaces Phase 7c.3's standalone whole-session emission per
Addendum #3 (Phase 7c.3 retired into Phase 7c.2 Task 5).
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

CANON_BP_CM = "tongue_spout_midpoint"
CANON_WIN = "trials-all_-100to1000ms"


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c2.render_whole_session")


def _enumerate_yaml_filtered_dates(animal: str, resolver: PathResolver) -> list[dt.date]:
    """Walk legacy spatial tree + filter by YAML range + add Pattern A
    dates. Same enumeration as Task 3/4 + render_visual_gate.py."""
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
    """(family, bodypart, center_mode) for every allowlist bodypart."""
    cells: list[tuple[str, str, str]] = []
    for family_name, fam in EXPECTED_TONE_ALIGNED_FAMILIES.items():
        cm = fam["center_mode"]
        for bp in fam["bodyparts"]:
            cells.append((family_name, bp, cm))
    return cells


def _per_animal_svg_path(
    root: Path, animal: str, family: str, bodypart: str,
) -> Path:
    return root / animal / family / f"{bodypart}.svg"


def _cohort_tile_svg_path(
    root: Path, family: str, bodypart: str,
) -> Path:
    return root / "cohort" / family / f"{bodypart}.svg"


def _render_cohort_tile_grid(
    cache: dict[str, tuple],
    family: str,
    bodypart: str,
    center_mode: str,
    out_path: Path,
    *,
    defaults: dict,
) -> None:
    """8-subplot cohort tile-grid (4 cols × 2 rows)."""
    ncols = 4
    nrows = math.ceil(len(COHORT_ORDER) / ncols)
    fig, axes = plt.subplots(
        nrows=nrows, ncols=ncols, figsize=(ncols * 4.0, nrows * 3.5),
        constrained_layout=True,
    )
    axes_flat = axes.flat if hasattr(axes, "flat") else [axes]
    for animal, ax in zip(COHORT_ORDER, axes_flat, strict=False):
        key = f"{animal}|{bodypart}|{center_mode}"
        cached = cache.get(key)
        if cached is None:
            ax.text(0.5, 0.5, animal + "\n(not cached)",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue
        H, ext, n_sess, _ = cached
        title = f"{animal} n_sess={n_sess}"
        render_h_counts_panel(
            H, ext, bodypart, center_mode,
            title=title, defaults=defaults, ax=ax,
        )
    for ax in list(axes_flat)[len(COHORT_ORDER):]:
        ax.set_axis_off()
    fig.suptitle(f"COHORT WHOLE-SESSION  {family}/{bodypart}", fontsize=12)
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
    """Render all 10 per-animal whole-session SVGs for one animal.

    Returns (n_svgs_written, runtime_seconds).
    """
    t0 = time.perf_counter()
    log.info(f"=== animal={animal}: rendering whole-session visual gate ===")
    dates = _enumerate_yaml_filtered_dates(animal, resolver)
    log.info(f"  {len(dates)} in-YAML-range dates")
    if not dates:
        log.warning(f"  animal={animal} has 0 dates; skipping.")
        return 0, time.perf_counter() - t0
    animal_info = get_animal(animal)

    n_svgs = 0
    for family_name, bodypart, center_mode in _iter_allowlist_cells():
        H, ext, n_sess, _ = compute_animal_aggregated_histogram(
            animal, dates, bodypart, center_mode, resolver,
            trial_group=None, window_ms=None,
            defaults=defaults, animal_info=animal_info,
        )
        key = f"{animal}|{bodypart}|{center_mode}"
        cache[key] = (H, ext, n_sess, 0)
        title = (
            f"{animal}  {bodypart}/{center_mode}  WHOLE SESSION pooled  "
            f"n_sessions={n_sess}"
        )
        fig = render_h_counts_panel(
            H, ext, bodypart, center_mode,
            title=title, defaults=defaults,
        )
        out = _per_animal_svg_path(root, animal, family_name, bodypart)
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
    """10 cohort tile-grid SVGs from cached per-animal histograms."""
    log.info("=== rendering cohort tile-grids ===")
    n_svgs = 0
    for family_name, bodypart, center_mode in _iter_allowlist_cells():
        out = _cohort_tile_svg_path(root, family_name, bodypart)
        _render_cohort_tile_grid(
            cache, family_name, bodypart, center_mode, out, defaults=defaults,
        )
        n_svgs += 1
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
        help="Render per-animal SVGs only; skip cohort tile-grids.",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    defaults = load_defaults()
    root = resolver.pipeline_outputs("dlc_analysis") / "spatial_whole_session_visual_gate"
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
        f"=== WHOLE-SESSION SUMMARY: per-animal SVGs={total_per_animal}, "
        f"cohort tile-grids={cohort_n}, total runtime={total_rt:.1f}s "
        f"({total_rt/60:.1f} min) ==="
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
