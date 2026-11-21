"""Within-animal cluster permutation for the v3 phase-aligned trajectories.

Rebuilds the same trial x bin substrate as
``scripts/chore_dlc_pooled_phenotype/q13_traj_v2_emit.py`` (v3 = v7-cleaned
trace + filtered_v1 DLC trial/session filters, 3-tier phenotypes), caches it
as parquet, and runs
``stroke_orofacial.stats.trajectory_within_animal_cluster``. Writes NEW files
only; the existing pooled-shuffle CSVs are untouched.

Outputs (under stats/results/phenotype_pooled/<family>/3_tier/v3/):
  trial_bin_substrate.parquet                           (cache; reused with --use-cache)
  trajectory_cluster_permutation_within_animal_bh_fdr.csv

Usage (from the repo root, pipeline env active; ~30-60 min per lick set
without cache):
  python -m scripts.manuscript.run_within_animal_cluster_perm --lick-set both
  python -m scripts.manuscript.run_within_animal_cluster_perm --lick-set first_lick --use-cache

--out-suffix S (2026-11-19, PS47 epoch rerun): writes <name>_S.csv and caches the substrate as
trial_bin_substrate_S.parquet, so a rerun with changed epoch labels never touches the current files
(default: no suffix, unchanged behaviour). --refuse-existing is checked before any computation.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.figures.phase_aligned_trajectories import RESULTS_SUBDIR  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    apply_phase_bin_baseline_delta,
    compute_per_animal_phase_bin_baseline,
    densify_phase_rows_via_interp,
)
from stroke_orofacial.stats.trajectory_within_animal_cluster import (  # noqa: E402
    compute_trajectory_cluster_permutation_c2_aligned,
    compute_trajectory_cluster_permutation_within_animal,
)
from scripts.chore_dlc_pooled_phenotype.q13_traj_v2_emit import (  # noqa: E402
    COHORT_8,
    filter_phase_rows,
)
from scripts.phase_9_1_q13.emit_cohort import (  # noqa: E402
    PHENOTYPE_ORDER_3TIER,
    attach_metadata,
    remap_animals_to_3tier,
    walk_cohort,
)

logger = logging.getLogger("manuscript.within_animal_cluster")
OUT_CSV = "trajectory_cluster_permutation_within_animal_bh_fdr.csv"
# --test c2_aligned (2026-11-19): the six-position cohort's cluster test, BH per signal.
OUT_CSV_C2 = "trajectory_cluster_permutation_c2aligned_bh_fdr.csv"
CACHE = "trial_bin_substrate.parquet"


def build_substrate(lick_set: str, resolver: PathResolver) -> pd.DataFrame:
    from stroke_orofacial.config_loader import load_defaults
    animals = list(COHORT_8)
    amap = remap_animals_to_3tier(
        {a: i for a, i in load_animals().items() if a in animals})
    cohort, _ = walk_cohort(animals=animals, resolver=resolver,
                            logger=logger, lick_set=lick_set)
    cohort, report = filter_phase_rows(cohort, animals=animals,
                                       resolver=resolver,
                                       defaults=load_defaults())
    logger.info("filter report: %s", report)
    cohort = attach_metadata(cohort, amap)
    dense = densify_phase_rows_via_interp(cohort)
    baseline = compute_per_animal_phase_bin_baseline(dense)
    return apply_phase_bin_baseline_delta(dense, baseline)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lick-set", choices=("first_lick", "all_multi", "both"),
                    default="both")
    ap.add_argument("--use-cache", action="store_true",
                    help="reuse trial_bin_substrate.parquet if present")
    ap.add_argument("--n-permutations", type=int, default=5000)
    ap.add_argument("--t-threshold", type=float, default=2.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test", choices=("within_animal", "c2_aligned"),
                    default="within_animal",
                    help="within_animal (default, Sept 2026 sensitivity test) or "
                         "c2_aligned (cohort-2 cluster test: Welch t, two-sided "
                         "p < .05 bin threshold, within-animal shuffle, BH per "
                         "signal; delta variant). --t-threshold is ignored for "
                         "c2_aligned.")
    ap.add_argument("--refuse-existing", action="store_true",
                    help="abort a lick set whose output CSV already exists")
    ap.add_argument("--out-suffix", default="",
                    help="suffix for the output CSV and the substrate cache "
                         "(e.g. ps47d5 -> *_bh_fdr_ps47d5.csv, trial_bin_substrate_ps47d5.parquet)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")
    resolver = PathResolver()
    sets = ["first_lick", "all_multi"] if args.lick_set == "both" else [args.lick_set]
    tag = f"_{args.out_suffix}" if args.out_suffix else ""

    def _paths(ls):
        suffix = "_all_licks" if ls == "all_multi" else ""
        res_dir = resolver.pipeline_outputs(subdir=RESULTS_SUBDIR + suffix) / "3_tier" / "v3"
        name = OUT_CSV_C2 if args.test == "c2_aligned" else OUT_CSV
        return res_dir, res_dir / CACHE.replace(".parquet", f"{tag}.parquet"), res_dir / name.replace(".csv", f"{tag}.csv")

    if args.refuse_existing:   # before any (30-60 min) computation
        clash = [str(o) for o in (_paths(ls)[2] for ls in sets) if o.exists()]
        if clash:
            logger.error("refusing to overwrite %s", ", ".join(clash))
            return 2
    for ls in sets:
        res_dir, cache, out = _paths(ls)
        res_dir.mkdir(parents=True, exist_ok=True)
        if args.use_cache and cache.exists():
            logger.info("[%s] loading cached substrate %s", ls, cache)
            dense = pd.read_parquet(cache)
        else:
            logger.info("[%s] rebuilding substrate (slow)...", ls)
            dense = build_substrate(ls, resolver)
            dense.to_parquet(cache, index=False)
            logger.info("[%s] cached %d rows -> %s", ls, len(dense), cache)
        if args.refuse_existing and out.exists():
            logger.error("[%s] refusing to overwrite %s", ls, out)
            return 2
        if args.test == "c2_aligned":
            res = compute_trajectory_cluster_permutation_c2_aligned(
                dense, phenotype_order=PHENOTYPE_ORDER_3TIER,
                n_permutations=args.n_permutations, rng_seed=args.seed)
        else:
            res = compute_trajectory_cluster_permutation_within_animal(
                dense, phenotype_order=PHENOTYPE_ORDER_3TIER,
                n_permutations=args.n_permutations,
                t_threshold=args.t_threshold, rng_seed=args.seed)
        res.to_csv(out, index=False)
        logger.info("[%s] wrote %s (%d rows, %d significant clusters)",
                    ls, out, len(res), int(res["reject"].fillna(False).sum()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
