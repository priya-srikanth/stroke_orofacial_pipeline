"""Chore whisker-nose — phenotype-pooled spatial emit for whisker + nose +
spout + eye (raw DLC, path A).

Extends Q-lock 12's phenotype-pooled spatial methodology to four reference
points, reusing the recipe-driven compute (Stage 1) + the canonical
line+jitter W-2 renderer (unification chore). Emits, per ``<scope>`` in
{4_tier, 3_tier}:

  - proportion_diff heatmaps under
    ``stats/figures/phenotype_pooled/proportion_diff_heatmaps/<scope>/v2/``
      * whisker / spout / eye: single combined ``both`` grid.
      * nose: ONE figure with ipsi + contra side-by-side sub-grids
        (Addendum #4 Option B — multi-side renderer).
  - W-2 recovery (line + per-session jittered dots, mean ± SEM) under
    ``stats/figures/phenotype_pooled/wasserstein_recovery/<scope>/v2/``
      * whisker / nose: 2-panel ipsi/contra.
      * spout / eye: single ``both`` panel.

Design locks: kickoff + Addenda #1-4. spout/eye pool both bilateral
landmarks (surfacing landmark drift despite midpoint centering); whisker
heatmap pools all 6 landmarks (``both``) while W-2 stats split L/R; nose
splits by ipsi/contra cue trials. Ipsi/contra is a pure relabel on the
all-L cohort (no spatial sign-flip fires).

Total = 16 SVGs (4 bodyparts × [1 heatmap + 1 W-2] × 2 scopes) + stats CSVs.

GR7: this script is STOP-and-ask before any cohort emit. Pilot on PS46
first (Stage 4), then fan out after Priya approval.

Usage::

    python -m scripts.chore_whisker_nose_spatial.emit_cohort \\
        --animals PS46 --bodyparts all --cohort-scope both --overwrite force
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import re
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.cohort_enumeration import (  # noqa: E402
    yaml_driven_session_dates,
)
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_spatial.render_on_demand import (  # noqa: E402
    _split_pre_post_dates,
)
from stroke_orofacial.figures.palette import PHENOTYPE_ORDER  # noqa: E402
from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (  # noqa: E402
    compute_cohort_shared_vmax,
    render_phenotype_pooled_proportion_diff_figure,
    render_phenotype_pooled_proportion_diff_multiside_figure,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    aggregate_phenotype_pooled_mean_sem,
    aggregate_phenotype_pooled_spatial_diff,
)
from stroke_orofacial.stats.spatial_proportion_diff import (  # noqa: E402
    POST_EPOCHS,
    compute_per_animal_per_epoch_diff,
    compute_per_animal_pre_pool,
    compute_per_animal_pre_self_diff,
    get_spatial_recipe,
    split_post_dates_by_epoch,
)
from stroke_orofacial.stats.normalization import ratio_to_baseline  # noqa: E402
from stroke_orofacial.stats.spatial_wasserstein import (  # noqa: E402
    compute_per_animal_per_session_w2_long,
)

# Reuse the 3-tier remap from the Q12 driver.
from scripts.phase_9_1_q12.emit_cohort import (  # noqa: E402
    PHENOTYPE_ORDER_3TIER,
    PHENOTYPE_REMAP_3TIER,
)

logger = logging.getLogger("chore.whisker_nose_emit")

COHORT_8 = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
ALL_BODYPARTS = ("whisker", "nose", "spout", "eye")
# Per-session OT create/destroy/move decomposition (G) is EXPENSIVE (an
# unbalanced sinkhorn per session × bodypart × side × epoch). Off by default so
# the normalized-W2 emit stays fast; flip to True (or wire a CLI flag) for the
# OT pass.
WITH_OT_DECOMPOSITION = False

HEATMAP_SUBDIR = "stats/figures/phenotype_pooled/proportion_diff_heatmaps"
W2_SUBDIR = "stats/figures/phenotype_pooled/wasserstein_recovery"

# Heatmap output sides (the combined/split sides used for the spatial map) vs
# W-2 output sides (per-anatomical-side stats). Whisker diverges: combined
# ``both`` heatmap but per-side L/R W-2 (Addendum #2/#4).
HEATMAP_SIDES: dict[str, tuple[str, ...]] = {
    "whisker": ("both",),
    "nose": ("L", "R"),
    "spout": ("both",),
    "eye": ("both",),
}
W2_SIDES: dict[str, tuple[str, ...]] = {
    "whisker": ("L", "R"),
    "nose": ("L", "R"),
    "spout": ("both",),
    "eye": ("both",),
}

# Ipsi/contra is a pure relabel on the all-L cohort: L -> ipsi, R -> contra
# (no spatial x-bin sign-flip fires; Addendum #1 cohort note). "both" passes
# through unchanged (the no-split pooled sides).
_SIDE_RELABEL = {"L": "ipsi", "R": "contra"}
SIDE_DISPLAY = {
    "L": "Ipsi (mouse-L)", "R": "Contra (mouse-R)",
    "ipsi": "Ipsi (mouse-L)", "contra": "Contra (mouse-R)",
    "both": "Both sides (pooled)",
}

HEATMAP_SUBTITLE = (
    "Source: raw DLC tracking (UNFILTERED) + ipsi/contra coding "
    "(chore whisker-nose-spatial-pooled)"
)
W2_PROVENANCE = (
    "Source: raw DLC spatial W-2 (UNFILTERED) + ipsi/contra coding "
    "(chore whisker-nose-spatial-pooled)"
)
W2_AGG_SUBTITLE = (
    "Mean ± SEM session-pooled (n = animals per phenotype; per-session W-2 "
    "shown as faded dots). Raw DLC; spout/eye pool both bilateral landmarks."
)
W2_DISPLAY_NAMES = {
    "whisker": "W-2 distance from pre-stroke (px) — whisker (all landmarks)",
    "nose": "W-2 distance from pre-stroke (px) — nose",
    "spout": "W-2 distance from pre-stroke (px) — spout (both landmarks)",
    "eye": "W-2 distance from pre-stroke (px) — eye (both landmarks)",
}
PROVENANCE = "v2_raw_dlc_ipsi_contra_whisker_nose"


def parse_animals(raw: str) -> list[str]:
    out = [t.strip() for t in raw.split(",") if t.strip()]
    for t in out:
        if not re.fullmatch(r"PS\d{2}", t):
            raise argparse.ArgumentTypeError(f"bad animal id {t!r}")
    if not out:
        raise argparse.ArgumentTypeError("no animals")
    return out


def parse_bodyparts(raw: str) -> list[str]:
    if raw.strip() == "all":
        return list(ALL_BODYPARTS)
    out = [t.strip() for t in raw.split(",") if t.strip()]
    for t in out:
        if t not in ALL_BODYPARTS:
            raise argparse.ArgumentTypeError(
                f"unknown bodypart {t!r}; expected from {ALL_BODYPARTS} or 'all'")
    return out


def _d_record(animal, side, bodypart, post_epoch, rec, *, pre_trials_key):
    """Shape one D record for aggregate_phenotype_pooled_spatial_diff."""
    return {
        "animal": animal, "side": side, "bodypart": bodypart,
        "post_epoch": post_epoch,
        "D": rec["D"], "extent": rec["extent"],
        "n_pre_trials": int(rec.get("n_pre_trials", rec.get(pre_trials_key, 0))),
        "n_post_trials": int(rec.get("n_post_trials",
                                     rec.get(pre_trials_key, 0))),
    }


def compute_animal(
    animal: str, *, resolver: PathResolver, defaults: dict, animal_info,
    bodyparts: list[str],
) -> tuple[list[dict], list[dict]]:
    """Compute heatmap D records + per-session W-2 rows for one animal.

    Returns ``(records, w2_rows)``. ``records`` feed
    :func:`aggregate_phenotype_pooled_spatial_diff` (keyed by side); ``w2_rows``
    are long-form per-session W-2 (side L/R/both, recovery_phenotype attached).
    """
    all_dates = yaml_driven_session_dates(
        animal, animal_info=animal_info, analysis_context="dlc.spatial")
    pre_dates, post_dates = _split_pre_post_dates(all_dates, animal_info)
    by_epoch = split_post_dates_by_epoch(animal_info, post_dates)
    logger.info(
        "[%s] dates: pre=%d acute=%d sub_acute=%d chronic=%d",
        animal, len(pre_dates), len(by_epoch["acute"]),
        len(by_epoch["sub_acute"]), len(by_epoch["chronic"]))

    records: list[dict] = []
    w2_rows: list[dict] = []
    for bodypart in bodyparts:
        get_spatial_recipe(bodypart)  # validates the bodypart early

        # --- Heatmap D records (HEATMAP_SIDES) ---
        for side in HEATMAP_SIDES[bodypart]:
            pre_pool = compute_per_animal_pre_pool(
                animal=animal, bodypart=bodypart, side=side, resolver=resolver,
                defaults=defaults, animal_info=animal_info, pre_dates=pre_dates)
            if pre_pool is None:
                logger.warning("[%s/%s/%s] empty pre-pool; skipping heatmap.",
                               animal, bodypart, side)
                continue
            pre_self = compute_per_animal_pre_self_diff(
                animal=animal, bodypart=bodypart, side=side, pre_pool=pre_pool,
                resolver=resolver, pre_dates=pre_dates, defaults=defaults,
                animal_info=animal_info)
            if pre_self is not None:
                records.append(_d_record(
                    animal, side, bodypart, "pre", pre_self,
                    pre_trials_key="n_pre_trials"))
            for epoch in POST_EPOCHS:
                rec = compute_per_animal_per_epoch_diff(
                    animal=animal, bodypart=bodypart, side=side,
                    post_epoch=epoch, pre_pool=pre_pool, resolver=resolver,
                    defaults=defaults, animal_info=animal_info,
                    post_dates_by_epoch=by_epoch)
                if rec is not None:
                    records.append(_d_record(
                        animal, side, bodypart, epoch, rec,
                        pre_trials_key="n_pre_trials"))

        # --- Per-session W-2 rows (W2_SIDES) ---
        for side in W2_SIDES[bodypart]:
            pre_pool = compute_per_animal_pre_pool(
                animal=animal, bodypart=bodypart, side=side, resolver=resolver,
                defaults=defaults, animal_info=animal_info, pre_dates=pre_dates)
            if pre_pool is None:
                continue
            for epoch_label, dates in (
                ("pre", pre_dates), ("acute", by_epoch["acute"]),
                ("sub_acute", by_epoch["sub_acute"]),
                ("chronic", by_epoch["chronic"]),
            ):
                rows = compute_per_animal_per_session_w2_long(
                    animal=animal, pre_pool=pre_pool, post_dates=dates,
                    side=side, bodypart=bodypart, resolver=resolver,
                    defaults=defaults, animal_info=animal_info,
                    epoch_label=epoch_label,
                    with_ot_decomposition=WITH_OT_DECOMPOSITION)
                for row in rows:
                    row["recovery_phenotype"] = animal_info.recovery_phenotype
                w2_rows.extend(rows)
    return records, w2_rows


def _relabel_side(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["side"] = out["side"].map(lambda s: _SIDE_RELABEL.get(s, s))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animals", type=parse_animals, default=list(COHORT_8))
    parser.add_argument("--bodyparts", type=parse_bodyparts, default="all")
    parser.add_argument("--cohort-scope", choices=("4_tier", "3_tier", "both"),
                        default="both")
    parser.add_argument("--overwrite", choices=("skip", "force"),
                        default="force")
    parser.add_argument("--log-level",
                        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
                        default="INFO")
    args = parser.parse_args(argv)
    if isinstance(args.bodyparts, str):  # default "all" not run through type
        args.bodyparts = parse_bodyparts(args.bodyparts)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    resolver = PathResolver()
    defaults = load_defaults()
    animals = args.animals
    animals_map_full = {a: i for a, i in load_animals().items() if a in animals}
    bodyparts = args.bodyparts

    logger.info("=" * 72)
    logger.info("Whisker-nose v2 emit — animals=%s bodyparts=%s scope=%s",
                ",".join(animals), ",".join(bodyparts), args.cohort_scope)
    logger.info("=" * 72)

    all_records: list[dict] = []
    all_w2_rows: list[dict] = []
    for animal in animals:
        recs, w2 = compute_animal(
            animal, resolver=resolver, defaults=defaults,
            animal_info=animals_map_full[animal], bodyparts=bodyparts)
        all_records.extend(recs)
        all_w2_rows.extend(w2)
    logger.info("Compute: %d D-records, %d per-session W-2 rows",
                len(all_records), len(all_w2_rows))
    if not all_records:
        logger.error("No spatial records; aborting.")
        return 1

    w2_df = _relabel_side(pd.DataFrame(all_w2_rows)).rename(
        columns={"bodypart": "endpoint"})

    scopes: list[tuple[str, tuple[str, ...], dict]] = []
    if args.cohort_scope in ("4_tier", "both"):
        scopes.append(("4_tier", PHENOTYPE_ORDER, animals_map_full))
    if args.cohort_scope in ("3_tier", "both"):
        remapped = {
            a: dataclasses.replace(
                info,
                recovery_phenotype=PHENOTYPE_REMAP_3TIER.get(
                    info.recovery_phenotype, info.recovery_phenotype))
            for a, info in animals_map_full.items()
        }
        scopes.append(("3_tier", PHENOTYPE_ORDER_3TIER, remapped))

    manifest_rows: list[dict] = []
    for scope, phenotype_order, amap in scopes:
        pooled = aggregate_phenotype_pooled_spatial_diff(all_records, amap)
        hm_dir = resolver.pipeline_outputs(subdir=HEATMAP_SUBDIR) / scope / "v2"
        hm_dir.mkdir(parents=True, exist_ok=True)

        for bodypart in bodyparts:
            # Per-bodypart shared_vmax (the 4 reference points live on very
            # different spatial scales; a cohort-wide vmax would wash out the
            # tight-band spout/eye maps).
            bp_pooled = {k: v for k, v in pooled.items() if k[2] == bodypart}
            if not bp_pooled:
                logger.warning("[%s] no pooled records for %s; skip heatmap.",
                               scope, bodypart)
                continue
            vmax = compute_cohort_shared_vmax(bp_pooled)
            target = hm_dir / f"{bodypart}_proportion_diff_v2.svg"
            try:
                if bodypart == "nose":
                    fig = render_phenotype_pooled_proportion_diff_multiside_figure(
                        bodypart="nose", sides=("L", "R"),
                        pooled_records=bp_pooled, shared_vmax=vmax,
                        phenotype_order=phenotype_order, defaults=defaults,
                        subtitle_override=HEATMAP_SUBTITLE,
                        side_display=SIDE_DISPLAY)
                else:
                    side = HEATMAP_SIDES[bodypart][0]  # "both"
                    fig = render_phenotype_pooled_proportion_diff_figure(
                        bodypart=bodypart, side=side, pooled_records=bp_pooled,
                        shared_vmax=vmax, phenotype_order=phenotype_order,
                        defaults=defaults, subtitle_override=HEATMAP_SUBTITLE,
                        side_display=SIDE_DISPLAY)
                if target.exists() and args.overwrite == "skip":
                    manifest_rows.append({"scope": scope, "bodypart": bodypart,
                                          "family": "heatmap", "status": "SKIP",
                                          "path": str(target)})
                else:
                    import matplotlib.pyplot as plt
                    fig.savefig(target, format="svg", bbox_inches="tight")
                    plt.close(fig)
                    manifest_rows.append({"scope": scope, "bodypart": bodypart,
                                          "family": "heatmap", "status": "OK",
                                          "path": str(target)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("[%s/%s] heatmap FAILED", scope, bodypart)
                manifest_rows.append({"scope": scope, "bodypart": bodypart,
                                      "family": "heatmap", "status": "FAIL",
                                      "path": repr(exc)})
        logger.info("[%s] heatmaps -> %s", scope, hm_dir)

        # --- W-2 recovery (line+jitter, mean±SEM) ---
        w2_scoped = w2_df.copy()
        w2_scoped["recovery_phenotype"] = w2_scoped["animal"].map(
            lambda a: amap[a].recovery_phenotype if a in amap else None)
        w2_scoped = w2_scoped.dropna(subset=["recovery_phenotype"])
        pooled_w2 = aggregate_phenotype_pooled_mean_sem(
            w2_scoped, value_col="w2", by_side=True)
        w2_dir = resolver.pipeline_outputs(subdir=W2_SUBDIR) / scope / "v2"
        w2_dir.mkdir(parents=True, exist_ok=True)
        for bodypart in bodyparts:
            w2_side_keys = tuple(
                _SIDE_RELABEL.get(s, s) for s in W2_SIDES[bodypart])
            target = w2_dir / f"{bodypart}_wasserstein_recovery_v2.svg"
            if target.exists() and args.overwrite == "skip":
                manifest_rows.append({"scope": scope, "bodypart": bodypart,
                                      "family": "w2", "status": "SKIP",
                                      "path": str(target)})
                continue
            try:
                from scripts.chore_dlc_pooled_phenotype.q13b_v2_emit import (
                    render_endpoint_v2_figure,
                )
                render_endpoint_v2_figure(
                    per_session_df=w2_scoped, pooled_df=pooled_w2,
                    endpoint=bodypart, phenotype_order=phenotype_order,
                    output_path=target, sides=w2_side_keys, value_col="w2",
                    display_names=W2_DISPLAY_NAMES,
                    aggregation_subtitle=W2_AGG_SUBTITLE,
                    provenance_subtitle=W2_PROVENANCE, is_delta=False)
                manifest_rows.append({"scope": scope, "bodypart": bodypart,
                                      "family": "w2", "status": "OK",
                                      "path": str(target)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("[%s/%s] W-2 FAILED", scope, bodypart)
                manifest_rows.append({"scope": scope, "bodypart": bodypart,
                                      "family": "w2", "status": "FAIL",
                                      "path": repr(exc)})

        # Stats CSV (W-2 pooled mean+SEM) under the results tree.
        res_dir = resolver.pipeline_outputs(
            subdir=W2_SUBDIR.replace("figures", "results")) / scope / "v2"
        res_dir.mkdir(parents=True, exist_ok=True)
        pooled_w2.assign(provenance=PROVENANCE).to_csv(
            res_dir / "wasserstein_recovery_mean_sem.csv", index=False)
        # Persist per-session W-2 (+ OT create/destroy/move) for reuse.
        # Namespaced under ``whisker_nose/`` so the consolidated-stats loader's
        # recursive ``**`` glob reads this file AND the q12 tongue/jaw sibling
        # without either clobbering the other (both formerly wrote the same
        # un-namespaced ``<scope>/v2/wasserstein_recovery_per_session.csv``).
        ps_dir = res_dir / "whisker_nose"
        ps_dir.mkdir(parents=True, exist_ok=True)
        w2_scoped.assign(provenance=PROVENANCE).to_csv(
            ps_dir / "wasserstein_recovery_per_session.csv", index=False)
        logger.info("[%s] W-2 line+jitter -> %s", scope, w2_dir)

        # --- Normalized W-2 recovery (per-animal pre-stroke baseline, per side)
        # parallel to the q12 tongue/jaw build (D). ---
        w2_for_norm = w2_scoped.copy()
        if "is_sentinel" not in w2_for_norm.columns:
            w2_for_norm["is_sentinel"] = False
        w2_norm = ratio_to_baseline(
            w2_for_norm, group_cols=("animal", "side"),
            value_col="w2", baseline_label="pre",
        ).dropna(subset=["value_norm"])
        pooled_w2_norm = aggregate_phenotype_pooled_mean_sem(
            w2_norm, value_col="value_norm", by_side=True)
        norm_dir = resolver.pipeline_outputs(
            subdir="stats/figures/phenotype_pooled/normalized_wasserstein_recovery",
        ) / scope / "v2"
        norm_dir.mkdir(parents=True, exist_ok=True)
        norm_names = {
            bp: f"Normalized W-2 (x pre-stroke baseline) -- {bp}"
            for bp in bodyparts
        }
        for bodypart in bodyparts:
            w2_side_keys = tuple(
                _SIDE_RELABEL.get(s, s) for s in W2_SIDES[bodypart])
            ntarget = norm_dir / f"{bodypart}_normalized_wasserstein_recovery_v2.svg"
            try:
                from scripts.chore_dlc_pooled_phenotype.q13b_v2_emit import (
                    render_endpoint_v2_figure,
                )
                render_endpoint_v2_figure(
                    per_session_df=w2_norm, pooled_df=pooled_w2_norm,
                    endpoint=bodypart, phenotype_order=phenotype_order,
                    output_path=ntarget, sides=w2_side_keys,
                    value_col="value_norm", display_names=norm_names,
                    aggregation_subtitle=W2_AGG_SUBTITLE,
                    provenance_subtitle=W2_PROVENANCE, is_delta=False)
                manifest_rows.append({"scope": scope, "bodypart": bodypart,
                                      "family": "w2_norm", "status": "OK",
                                      "path": str(ntarget)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("[%s/%s] norm W-2 FAILED", scope, bodypart)
                manifest_rows.append({"scope": scope, "bodypart": bodypart,
                                      "family": "w2_norm", "status": "FAIL",
                                      "path": repr(exc)})
        nres_dir = resolver.pipeline_outputs(
            subdir="stats/results/phenotype_pooled/normalized_wasserstein_recovery",
        ) / scope / "v2"
        nres_dir.mkdir(parents=True, exist_ok=True)
        pooled_w2_norm.assign(provenance=PROVENANCE).to_csv(
            nres_dir / "normalized_wasserstein_recovery_mean_sem.csv", index=False)
        # Per-session normalized W-2 (mirrors q12): write ``value_norm`` into a
        # ``w2`` column under a ``whisker_nose/`` subdir so the consolidated-
        # stats loader picks up the normalized family for these bodyparts too
        # (it formerly loaded empty — only mean+SEM was persisted).
        nps_dir = nres_dir / "whisker_nose"
        nps_dir.mkdir(parents=True, exist_ok=True)
        _norm_cols = ["animal", "date", "side", "endpoint", "epoch_label"]
        w2_norm.assign(w2=w2_norm["value_norm"], provenance=PROVENANCE)[
            _norm_cols + ["w2", "provenance"]
        ].to_csv(nps_dir / "wasserstein_recovery_per_session.csv", index=False)
        logger.info("[%s] normalized W-2 -> %s", scope, norm_dir)

    manifest_dir = resolver.pipeline_outputs(
        subdir="stats/sensitivity")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_csv = manifest_dir / "whisker_nose_spatial_emit_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_csv, index=False)
    n_ok = sum(1 for r in manifest_rows if r["status"] == "OK")
    n_fail = sum(1 for r in manifest_rows if r["status"] == "FAIL")
    logger.info("Emit complete: %d OK, %d FAIL. Manifest -> %s",
                n_ok, n_fail, manifest_csv)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
