"""Q12 v2 re-emit — proportion-diff heatmaps + W-2 recovery, ipsi/contra.

Chore ``vChore-dlc-pooled-phenotype-unification`` Stage 2 (run last per the
locked Q13b -> Q13/Q13c -> Q12 order).

LOCKED Q12 scope (Priya 2026-05-29 — spatial is NEVER filtered):
- **No DLC filter, no session filter** — the spatial compute reads the
  existing centered parquets UNCHANGED with a *pass-through* filter. "No
  licking" produces meaningful spatial mass (rest position) that the heatmap
  exists to capture; filtering would erase the severe-stroke phenotype.
  (NB: the shipped no_filter Q12 figures were emitted WITH the v1 NPZ
  SessionFilter, so these unfiltered v2 figures genuinely differ.)
- **Ipsi/contra coding** = pure relabel on the all-L cohort (ipsi = mouse-L,
  contra = mouse-R; no spatial x-bin sign-flip fires). Heatmaps stay heatmaps
  (convention unchanged); only the side label + subtitle change.
- **W-2 recovery** box plots -> the Stage-1 line+jitter+dots convention
  (mean +/- SEM session-pooled), 2-panel ipsi/contra per bodypart.

Output: ``stats/figures/phenotype_pooled/{proportion_diff_heatmaps,
wasserstein_recovery}/<scope>/v2/``. ``<scope>`` in {4_tier, 3_tier}.

Forward-caveat: on a future right-stroke cohort, the relabel becomes a true
recode (sign-flip spatial x-bins + W-2 signed metrics, pool on ipsi/contra).

Usage::

    python -m scripts.chore_dlc_pooled_phenotype.q12_v2_emit \\
        --animals PS46 --overwrite force --remap-phenotypes none
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.cohort_filters import PASS_THROUGH_FILTER  # noqa: E402
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.figures.palette import PHENOTYPE_ORDER  # noqa: E402
from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (  # noqa: E402
    compute_cohort_shared_vmax,
    emit_phenotype_pooled_proportion_diff_figures,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    aggregate_phenotype_pooled_mean_sem,
)
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    aggregate_phenotype_pooled_spatial_diff,
)

# Reuse the heavy Q12 spatial compute + the Stage-1 line+jitter renderer.
from scripts.phase_9_1_q12.emit_cohort import (  # noqa: E402
    PHENOTYPE_ORDER_3TIER,
    PHENOTYPE_REMAP_3TIER,
    compute_per_animal_records,
)
from scripts.chore_dlc_pooled_phenotype.q13b_v2_emit import (  # noqa: E402
    render_endpoint_v2_figure,
)
from stroke_orofacial.stats.normalization import ratio_to_baseline  # noqa: E402

logger = logging.getLogger("chore.q12_v2_emit")

COHORT_8 = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

HEATMAP_SUBDIR = "stats/figures/phenotype_pooled/proportion_diff_heatmaps"
W2_SUBDIR = "stats/figures/phenotype_pooled/wasserstein_recovery"

HEATMAP_V2_SUBTITLE = (
    "Source: spatial centered parquets (UNFILTERED — no-licking is signal) "
    "+ ipsi/contra coding (chore vChore-dlc-pooled-phenotype-unification)"
)
W2_V2_PROVENANCE = (
    "Source: spatial W-2 (UNFILTERED) + ipsi/contra coding "
    "(chore vChore-dlc-pooled-phenotype-unification)"
)
W2_AGG_SUBTITLE = (
    "Mean ± SEM session-pooled (n = animals per phenotype; per-cell "
    "n_sessions in stats CSV); per-session W-2 shown as faded dots."
)
SIDE_DISPLAY = {"L": "Ipsi (mouse-L)", "R": "Contra (mouse-R)"}
W2_DISPLAY_NAMES = {
    "tongue": "W-2 distance from pre-stroke (px) — tongue",
    "jaw": "W-2 distance from pre-stroke (px) — jaw",
}
PROVENANCE = "v2_unfiltered_ipsi_contra"

# --- Normalized W-2 recovery (NEW, CC #9): each session's W-2 divided by that
# animal's pre-stroke mean W-2 (per side), via the multiplicative
# stats.normalization.ratio_to_baseline. Expresses recovery as a fold-change of
# the animal's own pre-stroke spatial variability (pre-stroke ~ 1), controlling
# for animal-to-animal absolute-W-2 differences. Unfiltered, same substrate as
# the absolute W-2 figure it normalizes.
NORM_W2_SUBDIR = "stats/figures/phenotype_pooled/normalized_wasserstein_recovery"
NORM_W2_DISPLAY_NAMES = {
    "tongue": "Normalized W-2 (× pre-stroke baseline) — tongue",
    "jaw": "Normalized W-2 (× pre-stroke baseline) — jaw",
}
NORM_W2_PROVENANCE = (
    "Source: spatial W-2 ÷ per-animal pre-stroke baseline (per side; UNFILTERED) "
    "+ ipsi/contra coding (chore vChore-dlc-pooled-phenotype-unification)"
)
NORM_W2_AGG_SUBTITLE = (
    "Mean ± SEM session-pooled; each session's W-2 ÷ that animal's pre-stroke "
    "mean W-2 (per side). Pre-stroke ≈ 1; per-session ratios shown as faded dots."
)
NORM_PROVENANCE = "v2_normalized_unfiltered_ipsi_contra"


def parse_animals(raw: str) -> list[str]:
    import re
    out = [t.strip() for t in raw.split(",") if t.strip()]
    for t in out:
        if not re.fullmatch(r"PS\d{2}", t):
            raise argparse.ArgumentTypeError(f"bad animal id {t!r}")
    if not out:
        raise argparse.ArgumentTypeError("no animals")
    return out


def _relabel_side_ipsi_contra(df: pd.DataFrame) -> pd.DataFrame:
    """All-L relabel: L -> ipsi, R -> contra (no value change)."""
    out = df.copy()
    out["side"] = out["side"].map({"L": "ipsi", "R": "contra"}).fillna(out["side"])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animals", type=parse_animals, default=list(COHORT_8))
    parser.add_argument(
        "--overwrite", choices=("skip", "force"), default="force",
    )
    parser.add_argument(
        "--remap-phenotypes", choices=("none", "3tier", "both"), default="none",
    )
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S",
    )

    resolver = PathResolver()
    defaults = load_defaults()
    animals = args.animals
    animals_map_full = {a: i for a, i in load_animals().items() if a in animals}

    logger.info("=" * 72)
    logger.info("Q12 v2 re-emit (UNFILTERED + ipsi/contra) — animals=%s remap=%s",
                ",".join(animals), args.remap_phenotypes)
    logger.info("=" * 72)

    # Heavy spatial compute, ONCE, with a PASS-THROUGH filter (no filtering).
    all_records: list[dict] = []
    all_w2_rows: list[dict] = []
    for animal in animals:
        records, _w2_records, per_session_w2, _audit = compute_per_animal_records(
            animal=animal, resolver=resolver, defaults=defaults,
            animals_map=animals_map_full, logger=logger,
            filter_spec=PASS_THROUGH_FILTER,
            with_ot_decomposition=True,
        )
        all_records.extend(records)
        all_w2_rows.extend(per_session_w2)
    logger.info("Spatial compute: %d D-records, %d per-session W-2 rows",
                len(all_records), len(all_w2_rows))
    if not all_records:
        logger.error("No spatial records; aborting.")
        return 1

    w2_df = pd.DataFrame(all_w2_rows)
    w2_df = _relabel_side_ipsi_contra(w2_df).rename(columns={"bodypart": "endpoint"})

    scopes: list[tuple[str, tuple[str, ...], dict]] = []
    if args.remap_phenotypes in ("none", "both"):
        scopes.append(("4_tier", PHENOTYPE_ORDER, animals_map_full))
    if args.remap_phenotypes in ("3tier", "both"):
        remapped = {
            a: dataclasses.replace(
                info,
                recovery_phenotype=PHENOTYPE_REMAP_3TIER.get(
                    info.recovery_phenotype, info.recovery_phenotype),
            )
            for a, info in animals_map_full.items()
        }
        scopes.append(("3_tier", PHENOTYPE_ORDER_3TIER, remapped))

    for scope, phenotype_order, amap in scopes:
        # --- Heatmaps (relabel only; no convention change) ---
        pooled = aggregate_phenotype_pooled_spatial_diff(all_records, amap)
        shared_vmax = compute_cohort_shared_vmax(pooled)
        hm_dir = resolver.pipeline_outputs(subdir=HEATMAP_SUBDIR) / scope / "v2"
        emit_phenotype_pooled_proportion_diff_figures(
            pooled, resolver=resolver, output_dir=hm_dir,
            overwrite=args.overwrite, shared_vmax=shared_vmax,
            phenotype_order=phenotype_order, defaults=defaults,
            subtitle_override=HEATMAP_V2_SUBTITLE, side_display=SIDE_DISPLAY,
        )
        logger.info("[%s] heatmaps -> %s (vmax=%.4g)", scope, hm_dir, shared_vmax)

        # --- W-2 recovery (box -> line+jitter, mean+SEM, 2-panel ipsi/contra) ---
        # Attach phenotype per the scope's animals_map (per-session W-2 carries
        # the unremapped tier from compute; re-map here for 3_tier).
        w2_scoped = w2_df.copy()
        w2_scoped["recovery_phenotype"] = w2_scoped["animal"].map(
            lambda a: amap[a].recovery_phenotype if a in amap else None
        )
        w2_scoped = w2_scoped.dropna(subset=["recovery_phenotype"])
        pooled_w2 = aggregate_phenotype_pooled_mean_sem(
            w2_scoped, value_col="w2", by_side=True,
        )
        w2_dir = resolver.pipeline_outputs(subdir=W2_SUBDIR) / scope / "v2"
        w2_dir.mkdir(parents=True, exist_ok=True)
        n_figs = 0
        for bodypart in ("tongue", "jaw"):
            target = w2_dir / f"{bodypart}_wasserstein_recovery_v2.svg"
            render_endpoint_v2_figure(
                per_session_df=w2_scoped, pooled_df=pooled_w2,
                endpoint=bodypart, phenotype_order=phenotype_order,
                output_path=target, sides=("ipsi", "contra"),
                value_col="w2", display_names=W2_DISPLAY_NAMES,
                aggregation_subtitle=W2_AGG_SUBTITLE,
                provenance_subtitle=W2_V2_PROVENANCE, is_delta=False,
            )
            n_figs += 1
        # Provenance-stamped W-2 pooled CSV under the results tree.
        res_dir = resolver.pipeline_outputs(
            subdir=W2_SUBDIR.replace("figures", "results")) / scope / "v2"
        res_dir.mkdir(parents=True, exist_ok=True)
        pooled_w2.assign(provenance=PROVENANCE).to_csv(
            res_dir / "wasserstein_recovery_mean_sem.csv", index=False)
        # Persist the PER-SESSION W-2 (the figure's scatter values) so any
        # future normalization / re-pool never needs another OT recompute.
        w2_scoped.assign(provenance=PROVENANCE).to_csv(
            res_dir / "wasserstein_recovery_per_session.csv", index=False)
        logger.info("[%s] W-2 line+jitter figs=%d -> %s", scope, n_figs, w2_dir)

        # --- Normalized W-2 recovery (NEW): per-session W-2 / per-animal
        # pre-stroke baseline W-2 (per side). Reuses the same per-session pool
        # as the absolute figure, so no extra spatial compute. ---
        w2_for_norm = w2_scoped.copy()
        if "is_sentinel" not in w2_for_norm.columns:
            w2_for_norm["is_sentinel"] = False
        w2_norm = ratio_to_baseline(
            w2_for_norm, group_cols=("animal", "side"),
            value_col="w2", baseline_label="pre",
        ).dropna(subset=["value_norm"])
        pooled_w2_norm = aggregate_phenotype_pooled_mean_sem(
            w2_norm, value_col="value_norm", by_side=True,
        )
        norm_dir = resolver.pipeline_outputs(subdir=NORM_W2_SUBDIR) / scope / "v2"
        norm_dir.mkdir(parents=True, exist_ok=True)
        n_norm = 0
        for bodypart in ("tongue", "jaw"):
            target = norm_dir / f"{bodypart}_normalized_wasserstein_recovery_v2.svg"
            render_endpoint_v2_figure(
                per_session_df=w2_norm, pooled_df=pooled_w2_norm,
                endpoint=bodypart, phenotype_order=phenotype_order,
                output_path=target, sides=("ipsi", "contra"),
                value_col="value_norm", display_names=NORM_W2_DISPLAY_NAMES,
                aggregation_subtitle=NORM_W2_AGG_SUBTITLE,
                provenance_subtitle=NORM_W2_PROVENANCE, is_delta=False,
            )
            n_norm += 1
        res_norm = resolver.pipeline_outputs(
            subdir=NORM_W2_SUBDIR.replace("figures", "results")) / scope / "v2"
        res_norm.mkdir(parents=True, exist_ok=True)
        pooled_w2_norm.assign(provenance=NORM_PROVENANCE).to_csv(
            res_norm / "normalized_wasserstein_recovery_mean_sem.csv", index=False)
        logger.info("[%s] normalized W-2 figs=%d -> %s", scope, n_norm, norm_dir)

    logger.info("Q12 v2 re-emit complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
