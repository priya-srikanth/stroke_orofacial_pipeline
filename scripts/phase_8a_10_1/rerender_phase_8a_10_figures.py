"""Phase 8a.10.1 Task 4 — figure re-render on post-fix Phase 2 NPZs.

Per kickoff Q2.A lock 2026-05-14: re-render Phase 8a.10's sub-deliverable A
(8 animals × 11 plot families, each with align_to_stroke ∈ {True, False})
+ cohort tile-grids (10 plot families × 2 alignment modes) + sub-deliverable
B (3 Cohort B animals × 2 renderers).

Per Task 3 finding: tone-anchored compute is invariant under the swap
fix on bilateral-reward sessions (Δ=0 metric). Post-fix figures are
expected to be bit-identical to pre-fix on bilateral sessions; differ
ONLY on withhold-side metrics in PS51/PS54/PS55 early-May 2025 sessions
(76/276 sessions touch withhold semantics per the Task 3 Check 4
diagnostic).

Outputs land at the production paths (Q2.A in-place overwrite):
- Sub-A: ``pipeline_outputs/spout_behavior/spout_behavior_figures/<animal>/
  <family>_{relStroke|absDate}.{svg,png}``
- Sub-A cohort tiles: ``.../spout_behavior_figures/summary/
  summary_<animals>__<family>_{relStroke|absDate}.{svg,png}``
- Sub-B: ``.../spout_close_vs_std/cohort/<animal>_{summary,per_trial}.{svg,png}``

Each rendered output is sha256 + size captured to
``scripts/phase_8a_10_1/rerender_manifest.csv``.

Run::

    conda activate stroke_orofacial
    python scripts/phase_8a_10_1/rerender_phase_8a_10_figures.py
"""
from __future__ import annotations

import csv
import hashlib
import sys
import time
import traceback
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.cohort_summary import make_summary_figures
from stroke_orofacial.spout_behavior.spout_close_vs_std import (
    list_cohort_b_animals,
    render_animal_per_trial_spout_close_vs_std,
    render_animal_summary_spout_close_vs_std,
)
from stroke_orofacial.spout_behavior.visual_gate import (
    _compute_per_session_stats,
    load_behavior_report_params,
    load_visual_gate_config,
    render_accuracy_firstCorrectLick,
    render_accuracy_firstCorrectLickAll,
    render_criteria_performance,
    render_latency_bySession,
    render_lick_raster,
    render_lickRate_bySession,
    render_lickiness_bySession,
    render_numLicks_bySession_all,
    render_numLicks_bySession_correct,
    render_numLicks_bySession_correct_and_incorrect,
    render_switchiness_bySession,
)

COHORT_A_ANIMALS = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

# Sub-A plot families. The first 8 share the cached-stats kwarg
# (consume `_PerSessionStats` directly). The 3 in NO_STATS_RENDERERS
# compute their own per-session aggregates internally and don't
# accept a `stats=` kwarg.
STATS_RENDERERS = [
    ("criteria_performance", render_criteria_performance),
    ("accuracy_firstCorrectLick", render_accuracy_firstCorrectLick),
    ("accuracy_firstCorrectLickAll", render_accuracy_firstCorrectLickAll),
    ("lickRate_bySession", render_lickRate_bySession),
    ("latency_bySession", render_latency_bySession),
    ("numLicks_bySession_correct", render_numLicks_bySession_correct),
    ("numLicks_bySession_all", render_numLicks_bySession_all),
    ("numLicks_bySession_correct_and_incorrect", render_numLicks_bySession_correct_and_incorrect),
]
NO_STATS_RENDERERS = [
    ("lick_raster", render_lick_raster),
    ("lickiness_bySession", render_lickiness_bySession),
    ("switchiness_bySession", render_switchiness_bySession),
]

MANIFEST_PATH = Path("scripts/phase_8a_10_1/rerender_manifest.csv")
MANIFEST_FIELDS = (
    "deliverable", "animal", "family", "align_mode", "ext",
    "path", "post_fix_sha256", "post_fix_size_bytes",
    "render_wall_time_sec", "status", "error_msg",
)


def _sha256_size(path):
    if not path.exists():
        return None, None
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _record(rows, **kwargs):
    """Append a row to the manifest, sha256-ing the path."""
    row = {k: "" for k in MANIFEST_FIELDS}
    row.update(kwargs)
    path = row["path"]
    if path and Path(path).exists():
        sha, size = _sha256_size(Path(path))
        row["post_fix_sha256"] = sha
        row["post_fix_size_bytes"] = size
    rows.append(row)


def _flush(rows):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)


def render_sub_a(resolver, defaults, rows):
    """Sub-deliverable A: 11 plot families × 8 animals × 2 align modes."""
    config = load_visual_gate_config()
    behavior_params = load_behavior_report_params()
    print(f"\n=== Sub-A: {len(COHORT_A_ANIMALS)} animals × 11 families × 2 align modes ===\n")
    for animal in COHORT_A_ANIMALS:
        print(f"--- {animal}: compute per-session stats (cached across 10 stats renderers) ---")
        t_stats = time.time()
        stats = _compute_per_session_stats(animal, resolver, behavior_params)
        print(f"  stats ready in {time.time() - t_stats:.1f}s ({len(stats.dates)} dates)")
        for align in (True, False):
            align_mode = "relStroke" if align else "absDate"
            for family, fn in STATS_RENDERERS:
                t0 = time.time()
                try:
                    svg_path, png_path = fn(
                        animal, resolver,
                        align_to_stroke=align,
                        config=config,
                        behavior_params=behavior_params,
                        overwrite="force",
                        stats=stats,
                    )
                    elapsed = time.time() - t0
                    for ext, p in (("svg", svg_path), ("png", png_path)):
                        _record(
                            rows,
                            deliverable="A",
                            animal=animal, family=family,
                            align_mode=align_mode, ext=ext,
                            path=str(p),
                            render_wall_time_sec=round(elapsed, 3),
                            status="OK",
                        )
                except Exception as exc:
                    tb = traceback.format_exc()
                    _record(
                        rows,
                        deliverable="A",
                        animal=animal, family=family,
                        align_mode=align_mode, ext="",
                        render_wall_time_sec=round(time.time() - t0, 3),
                        status=f"ERROR_{type(exc).__name__}",
                        error_msg=str(exc).replace("\n", " | ")[:500],
                    )
                    print(f"  ERROR {family} ({align_mode}): {exc}")
            # No-stats renderers (each computes its own per-session
            # aggregate internally — don't pass stats=).
            for family, fn in NO_STATS_RENDERERS:
                t0 = time.time()
                try:
                    svg_path, png_path = fn(
                        animal, resolver,
                        align_to_stroke=align,
                        config=config,
                        behavior_params=behavior_params,
                        overwrite="force",
                    )
                    elapsed = time.time() - t0
                    for ext, p in (("svg", svg_path), ("png", png_path)):
                        _record(
                            rows,
                            deliverable="A",
                            animal=animal, family=family,
                            align_mode=align_mode, ext=ext,
                            path=str(p),
                            render_wall_time_sec=round(elapsed, 3),
                            status="OK",
                        )
                except Exception as exc:
                    tb = traceback.format_exc()
                    _record(
                        rows,
                        deliverable="A",
                        animal=animal, family=family,
                        align_mode=align_mode, ext="",
                        render_wall_time_sec=round(time.time() - t0, 3),
                        status=f"ERROR_{type(exc).__name__}",
                        error_msg=str(exc).replace("\n", " | ")[:500],
                    )
                    print(f"  ERROR {family} ({align_mode}): {exc}")
        _flush(rows)
        print(f"  {animal} done.")


def render_cohort_tiles(resolver, defaults, rows):
    """10 plot families × 2 align modes — tiled summary grids."""
    print(f"\n=== Cohort tile-grids: {len(COHORT_A_ANIMALS)} animals × 10 families × 2 align modes ===\n")
    config = load_visual_gate_config()
    for align in (True, False):
        align_mode = "relStroke" if align else "absDate"
        t0 = time.time()
        try:
            out_dir = make_summary_figures(
                animals=list(COHORT_A_ANIMALS),
                resolver=resolver,
                align_to_stroke=align,
                config=config,
                overwrite="force",
            )
            elapsed = time.time() - t0
            # Walk the output dir for tiles produced this run.
            tiles_dir = Path(out_dir)
            stem_prefix = "summary_" + "_".join(COHORT_A_ANIMALS)
            for tile in sorted(tiles_dir.glob(f"{stem_prefix}__*_{align_mode}.*")):
                _record(
                    rows,
                    deliverable="A_cohort_tile",
                    animal="cohort",
                    family=tile.stem.replace(f"{stem_prefix}__", "").replace(f"_{align_mode}", ""),
                    align_mode=align_mode, ext=tile.suffix.lstrip("."),
                    path=str(tile),
                    render_wall_time_sec=round(elapsed, 3),
                    status="OK",
                )
            print(f"  align_to_stroke={align}: tiled in {elapsed:.1f}s")
        except Exception as exc:
            tb = traceback.format_exc()
            _record(
                rows,
                deliverable="A_cohort_tile",
                animal="cohort", family="(all)",
                align_mode=align_mode, ext="",
                render_wall_time_sec=round(time.time() - t0, 3),
                status=f"ERROR_{type(exc).__name__}",
                error_msg=str(exc).replace("\n", " | ")[:500],
            )
            print(f"  ERROR cohort tile-grids ({align_mode}): {exc}")
    _flush(rows)


def render_sub_b(resolver, defaults, rows):
    """Sub-deliverable B: 3 Cohort B animals × 2 renderers."""
    print(f"\n=== Sub-B: Cohort B animals × 2 renderers ===\n")
    config = load_visual_gate_config()
    behavior_params = load_behavior_report_params()
    cohort_b_animals = list_cohort_b_animals()
    print(f"  Cohort B animals: {cohort_b_animals}")
    for animal in cohort_b_animals:
        print(f"--- {animal} ---")
        for renderer_name, fn in (
            ("cohort_summary", render_animal_summary_spout_close_vs_std),
            ("cohort_per_trial", render_animal_per_trial_spout_close_vs_std),
        ):
            t0 = time.time()
            try:
                svg_path, png_path = fn(
                    animal,
                    resolver=resolver,
                    config=config,
                    behavior_params=behavior_params,
                    overwrite="force",
                )
                elapsed = time.time() - t0
                for ext, p in (("svg", svg_path), ("png", png_path)):
                    _record(
                        rows,
                        deliverable="B",
                        animal=animal, family=renderer_name,
                        align_mode="", ext=ext,
                        path=str(p),
                        render_wall_time_sec=round(elapsed, 3),
                        status="OK",
                    )
                print(f"  {renderer_name}: {elapsed:.1f}s")
            except Exception as exc:
                tb = traceback.format_exc()
                _record(
                    rows,
                    deliverable="B",
                    animal=animal, family=renderer_name,
                    align_mode="", ext="",
                    render_wall_time_sec=round(time.time() - t0, 3),
                    status=f"ERROR_{type(exc).__name__}",
                    error_msg=str(exc).replace("\n", " | ")[:500],
                )
                print(f"  ERROR {renderer_name}: {exc}")
        _flush(rows)


def main():
    resolver = PathResolver()
    defaults = load_defaults()
    rows: list[dict] = []

    # Write empty manifest header upfront.
    _flush(rows)

    t_start = time.time()
    render_sub_a(resolver, defaults, rows)
    render_cohort_tiles(resolver, defaults, rows)
    render_sub_b(resolver, defaults, rows)
    total = time.time() - t_start

    n_ok = sum(1 for r in rows if r["status"] == "OK")
    n_err = sum(1 for r in rows if r["status"].startswith("ERROR"))
    print(f"\n{'=' * 60}")
    print(f"Total: {len(rows)} manifest rows. {n_ok} OK, {n_err} errored.")
    print(f"Wall time: {total:.0f}s ({total/60:.1f} min)")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
