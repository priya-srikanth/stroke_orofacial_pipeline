"""Phase 7c.2 Task 5 — Compute-on-demand spatial heatmap driver (Addendum #9 Q12.B).

Renders individual_session + binned_sessions heatmaps for the four
non-whisker families across the 8-animal cohort, both tone-aligned
and whole-session scopes. Whiskers composite + proportion_differences
+ unbalanced_ot deferred to legacy-port steps 3-5 (STOP-and-asks
post-Step-6 driver).

Output paths per Q12.B (resolved via PathResolver helpers landed in
732e2b9):

  pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/
    <family_entry>/individual_session/<YYYYMMDD>.svg
    <family_entry>/binned_sessions/<rel_day_bin_label>.svg

  pipeline_outputs/dlc_kinematics/whole_session_heatmaps/<animal>/
    <family_entry>/individual_session/<YYYYMMDD>.svg
    <family_entry>/binned_sessions/<rel_day_bin_label>.svg

Tone-aligned plot SVGs are 1×3 panels (all, L, R) using the single
(0, 8000)ms window. Whole-session plot SVGs are 1×1 (all only).

Cohort scope (4 non-whisker families × 248 sessions × 2 scopes =
1,984 individual_session SVGs + ~32 binned_sessions SVGs per animal
× 8 animals = ~256 binned_sessions SVGs). Total ≈ 2,240 SVGs;
whisker family adds ~280 more once the composite port lands.

Per-animal manifest schema mirrors Task 3/4:
.scratch_phase_7c2/cohort_heatmaps_manifest.csv. Resumability via
skip-if-status-OK on the prior manifest.

Wall-time projection: ~1-1.5 hr cohort total (per-animal ~7-10 min
small / ~15-20 min big animals).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import re
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
from stroke_orofacial.dlc_kinematics._day_binned import _compute_rel_day_bin_label
from stroke_orofacial.dlc_spatial.render_on_demand import (
    render_binned_sessions_heatmap,
    render_individual_session_heatmap,
    render_proportion_difference_heatmap,
    render_unbalanced_ot_displacement_field,
)
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

# All 5 family entries iterate (whiskers dispatches to the composite
# overlay renderer per Addendum #10 Q1 / commit-to-follow).
ALL_FAMILIES = tuple(EXPECTED_TONE_ALIGNED_FAMILIES.keys())

SCOPES = ("tone_aligned", "whole_session")

# Proportion-diff bin sizes per Addendum #11 Q2.B: render one SVG per
# bin_size; current cohort-wide config is the union of small-animal (2d)
# + big-animal (7d) bin sizes. Each animal produces 2 proportion_diff
# SVGs per (family, scope).
PROPORTION_DIFF_BIN_SIZES: tuple[int, ...] = (2, 7)

# Task 3/4 cohort enumeration constants.
CANON_BP_CM = "tongue_spout_midpoint"
CANON_WIN = "trials-all_-100to1000ms"

MANIFEST_PATH = Path(".scratch_phase_7c2/cohort_heatmaps_manifest.csv")
MANIFEST_HEADER = [
    "animal",
    "runtime_seconds_total",
    "n_individual_session_svgs",
    "n_binned_sessions_svgs",
    "n_proportion_differences_svgs",
    "n_unbalanced_ot_svgs",
    "n_errors",
    "status",
    "anomaly_notes",
]


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c2.render_heatmaps")


def _enumerate_yaml_filtered_dates(animal: str, resolver: PathResolver) -> list[dt.date]:
    """Walk legacy spatial tree + YAML range filter + Pattern A. Mirrors
    Task 3/4 enumeration; see Addendum #5 + #4 for context."""
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


def _bin_dates_by_rel_day(
    dates: list[dt.date], stroke_date: dt.date, bin_days: int,
) -> dict[str, list[dt.date]]:
    """Group session dates by rel_day_bin_label per the canonical
    licking_dynamics/day_binned convention."""
    bins: dict[str, list[dt.date]] = {}
    for d in dates:
        label = _compute_rel_day_bin_label(
            session_date=d, d0=stroke_date, bin_days=bin_days,
        )
        bins.setdefault(label, []).append(d)
    for label in bins:
        bins[label].sort()
    return bins


def _individual_session_out_path(
    resolver: PathResolver, scope: str, animal: str,
    family_entry: str, date: dt.date,
) -> Path:
    if scope == "tone_aligned":
        return resolver.tone_aligned_heatmap_individual_session_path(
            animal, family_entry, date,
        )
    return resolver.whole_session_heatmap_individual_session_path(
        animal, family_entry, date,
    )


def _binned_sessions_out_path(
    resolver: PathResolver, scope: str, animal: str,
    family_entry: str, rel_day_bin_label: str,
) -> Path:
    if scope == "tone_aligned":
        return resolver.tone_aligned_heatmap_binned_sessions_path(
            animal, family_entry, rel_day_bin_label,
        )
    return resolver.whole_session_heatmap_binned_sessions_path(
        animal, family_entry, rel_day_bin_label,
    )


def _proportion_diff_out_path(
    resolver: PathResolver, scope: str, animal: str, family_entry: str,
    bin_size_days: int,
) -> Path:
    if scope == "tone_aligned":
        return resolver.tone_aligned_heatmap_proportion_differences_path(
            animal, family_entry, bin_size_days,
        )
    return resolver.whole_session_heatmap_proportion_differences_path(
        animal, family_entry, bin_size_days,
    )


def _unbalanced_ot_out_path(
    resolver: PathResolver, scope: str, animal: str, family_entry: str,
) -> Path:
    if scope == "tone_aligned":
        return resolver.tone_aligned_heatmap_unbalanced_ot_path(
            animal, family_entry,
        )
    return resolver.whole_session_heatmap_unbalanced_ot_path(
        animal, family_entry,
    )


def _load_manifest_so_far() -> dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[str, str] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            out[row["animal"]] = row["status"]
    return out


def _append_manifest(row: dict) -> None:
    is_new = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if is_new:
            w.writeheader()
        w.writerow(row)


def _process_animal(animal: str, resolver: PathResolver, defaults: dict) -> dict:
    """Render individual_session + binned_sessions × 2 scopes × 4 non-whisker
    families for one animal. Returns manifest row dict."""
    log.info(f"=== animal={animal}: render_heatmaps Task 5 ===")
    animal_t0 = time.perf_counter()
    animal_info = get_animal(animal)
    dates = _enumerate_yaml_filtered_dates(animal, resolver)
    log.info(f"  {len(dates)} in-YAML-range dates")
    bins = _bin_dates_by_rel_day(dates, animal_info.stroke_date, animal_info.bin_days)
    log.info(f"  {len(bins)} rel_day_bins: {sorted(bins.keys())}")

    n_is = 0
    n_bs = 0
    n_pd = 0
    n_ot = 0
    n_err = 0
    anomalies: list[str] = []
    for family_entry in ALL_FAMILIES:
        for scope in SCOPES:
            for date in dates:
                try:
                    fig = render_individual_session_heatmap(
                        animal=animal, family_entry=family_entry,
                        date=date, scope=scope, resolver=resolver,
                        defaults=defaults, animal_info=animal_info,
                    )
                    out = _individual_session_out_path(
                        resolver, scope, animal, family_entry, date,
                    )
                    fig.savefig(out, format="svg")
                    plt.close(fig)
                    n_is += 1
                except Exception as ex:
                    n_err += 1
                    msg = (
                        f"is/{family_entry}/{scope}/{date.isoformat()}: {ex!r}"
                    )
                    anomalies.append(msg)
                    log.error(f"    ERR {msg}")
            for bin_label, bin_dates in sorted(bins.items()):
                try:
                    fig = render_binned_sessions_heatmap(
                        animal=animal, family_entry=family_entry,
                        rel_day_bin_label=bin_label,
                        dates_in_bin=bin_dates,
                        scope=scope, resolver=resolver,
                        defaults=defaults, animal_info=animal_info,
                    )
                    out = _binned_sessions_out_path(
                        resolver, scope, animal, family_entry, bin_label,
                    )
                    fig.savefig(out, format="svg")
                    plt.close(fig)
                    n_bs += 1
                except Exception as ex:
                    n_err += 1
                    msg = (
                        f"bs/{family_entry}/{scope}/{bin_label}: {ex!r}"
                    )
                    anomalies.append(msg)
                    log.error(f"    ERR {msg}")
            # ----- proportion_differences (Addendum #11 Q2.B: 1 SVG per
            # family × scope × bin_size) -----
            for bin_size_days in PROPORTION_DIFF_BIN_SIZES:
                try:
                    fig = render_proportion_difference_heatmap(
                        animal=animal, family_entry=family_entry,
                        scope=scope, resolver=resolver,
                        bin_size_days=bin_size_days,
                        dates=dates,
                        defaults=defaults, animal_info=animal_info,
                    )
                    out = _proportion_diff_out_path(
                        resolver, scope, animal, family_entry, bin_size_days,
                    )
                    fig.savefig(out, format="svg")
                    plt.close(fig)
                    n_pd += 1
                except Exception as ex:
                    n_err += 1
                    msg = f"pd/{family_entry}/{scope}/bin{bin_size_days}d: {ex!r}"
                    anomalies.append(msg)
                    log.error(f"    ERR {msg}")

            # ----- unbalanced_ot displacement field (1 SVG per family × scope) -----
            try:
                fig = render_unbalanced_ot_displacement_field(
                    animal=animal, family_entry=family_entry,
                    scope=scope, resolver=resolver,
                    dates=dates,
                    defaults=defaults, animal_info=animal_info,
                )
                out = _unbalanced_ot_out_path(
                    resolver, scope, animal, family_entry,
                )
                fig.savefig(out, format="svg")
                plt.close(fig)
                n_ot += 1
            except Exception as ex:
                n_err += 1
                msg = f"ot/{family_entry}/{scope}: {ex!r}"
                anomalies.append(msg)
                log.error(f"    ERR {msg}")
        log.info(
            f"  family={family_entry} done; "
            f"n_is={n_is} n_bs={n_bs} n_pd={n_pd} n_ot={n_ot} n_err={n_err}"
        )

    rt = time.perf_counter() - animal_t0
    n_total = n_is + n_bs + n_pd + n_ot
    status = "OK" if n_err == 0 else ("PARTIAL" if n_total > 0 else "ERR")
    log.info(
        f"=== animal={animal}: complete — is={n_is} bs={n_bs} pd={n_pd} "
        f"ot={n_ot} err={n_err} runtime {rt:.1f}s ({rt/60:.1f} min) "
        f"status={status} ==="
    )
    return {
        "animal": animal,
        "runtime_seconds_total": f"{rt:.3f}",
        "n_individual_session_svgs": str(n_is),
        "n_binned_sessions_svgs": str(n_bs),
        "n_proportion_differences_svgs": str(n_pd),
        "n_unbalanced_ot_svgs": str(n_ot),
        "n_errors": str(n_err),
        "status": status,
        "anomaly_notes": "; ".join(anomalies[:5]),  # cap to keep CSV cell readable
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--animal",
        choices=COHORT_ORDER,
        help="Process a single animal. Default: iterate the full Cohort A order.",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    defaults = load_defaults()
    log.info(
        f"output root: {resolver.pipeline_outputs('dlc_kinematics')}/"
        f"{{tone_aligned,whole_session}}_heatmaps/"
    )
    log.info(f"manifest: {MANIFEST_PATH.resolve()}")

    animals = [args.animal] if args.animal else list(COHORT_ORDER)
    prior = _load_manifest_so_far()

    for animal in animals:
        prior_status = prior.get(animal)
        if prior_status == "OK":
            log.info(f"  [skip] {animal} already OK in prior manifest")
            continue
        row = _process_animal(animal, resolver, defaults)
        _append_manifest(row)

    return 0


if __name__ == "__main__":
    sys.exit(main())
