"""Two-tone all-lick peak tongue angle PER LICK WITH ITS LICK NUMBER, taken from the source (CC-B, 2026-11-23).

Fig 2G's all-lick angle table (stats/inputs/all_licks_endpoints/peak_angle_deg) is written by
scripts/phase_9_stats/precompute_all_licks_endpoints.py from
``compute_phase_aligned_endpoints_per_trial(build_tongue_visual_bundle_by_animal_date(...), lick_set="all_multi")``,
which returns one row per lick keyed (trial_index, side, peak_t_ms); the persisted table drops trial_index. This script
re-runs that same producer per session and keeps trial_index. Lick number = order of the lick peaks within the trial
(sort by peak_t_ms within trial_index x side; every lick row counts, also those whose angle is not finite), i.e. the
source's own per-trial lick list (same window and lick rules as Fig 2G by construction).

Session set = Fig 2G's own: the filtered_v1 DLC session filter (build_pooled_phenotype_stats._build_dlc_filter
kept_keys, 428 animal x date x side sessions); no trial filter (the angle table has no n_licks_per_trial, as in 2G).
Epoch label = assign_epoch_label (as precompute_all_licks_endpoints).

Checks (printed and written to <out>_checks.csv): per session, values and peak times equal the persisted Fig 2G table
row by row.

    python scripts/manuscript/c1_angle_licks_source.py <out.parquet> [--jobs 8]
"""
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "scripts" / "phase_9_stats")]


def one_session(arg):
    animal, date = arg
    from stroke_orofacial.animals import load_animals
    from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
        build_tongue_visual_bundle_by_animal_date,
    )
    from stroke_orofacial.dlc_kinematics.tongue_phase_aligned_endpoints import (
        compute_phase_aligned_endpoints_per_trial,
    )
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.stats.recovery_epochs import assign_epoch_label
    try:
        b = build_tongue_visual_bundle_by_animal_date(animal=animal, date=date, resolver=PathResolver())
        pl = compute_phase_aligned_endpoints_per_trial(b, lick_set="all_multi")
    except Exception as exc:  # noqa: BLE001
        return animal, date, None, repr(exc)
    if pl.empty:
        return animal, date, None, "empty"
    info = load_animals()[animal]
    pl = pl[["trial_index", "side", "peak_t_ms", "peak_angle_deg"]].copy()
    pl["src_row"] = np.arange(len(pl))          # row order = the persisted table's order within the session
    pl = pl.sort_values(["trial_index", "side", "peak_t_ms"], kind="stable")
    pl["k"] = pl.groupby(["trial_index", "side"]).cumcount()
    pl = pl.sort_values("src_row")
    pl["animal"], pl["date"] = animal, date
    pl["epoch_label"] = assign_epoch_label(int(info.day_relative_to_stroke(date)), info)
    return animal, date, pl, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    if a.out.exists():
        sys.exit(f"refusing to overwrite {a.out}")
    import build_pooled_phenotype_stats as B

    from stroke_orofacial.animals import load_animals
    from stroke_orofacial.paths import PathResolver
    r = PathResolver()
    _, kept = B._build_dlc_filter(sorted(load_animals()), r)
    K = pd.DataFrame(sorted(kept), columns=["animal", "date", "side"])
    K["date"] = pd.to_datetime(K.date).dt.date
    sess = sorted({(x, d) for x, d in zip(K.animal, K.date)})
    print(f"Fig 2G session set: {len(K)} animal x date x side, {len(sess)} animal x date", flush=True)
    out, fails = [], []
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, (animal, date, pl, err) in enumerate(ex.map(one_session, sess)):
            if pl is None:
                fails.append((animal, date, err))
            else:
                out.append(pl)
            if i % 25 == 0:
                print(i, "/", len(sess), flush=True)
    if fails:
        print("FAILED sessions:", fails, flush=True)
    A = pd.concat(out, ignore_index=True)
    # row-by-row check against the persisted Fig 2G table
    root = r.pipeline_outputs(subdir="stats") / "inputs/all_licks_endpoints/peak_angle_deg"
    chk = []
    for animal, g in A.groupby("animal"):
        P = pd.read_parquet(root / f"{animal}.parquet")
        P["date"] = pd.to_datetime(P.date).dt.date
        for date, gd in g.groupby("date"):
            pd_ = P[P.date == date]
            ok = len(pd_) == len(gd) and np.allclose(pd_.value.to_numpy(float), gd.peak_angle_deg.to_numpy(float),
                                                    equal_nan=True) \
                and (pd_.peak_t_ms.to_numpy() == gd.peak_t_ms.to_numpy()).all() \
                and (pd_.side.to_numpy() == gd.side.to_numpy()).all()
            chk.append({"animal": animal, "date": date, "n_src": len(gd), "n_table": len(pd_), "identical": bool(ok)})
    C = pd.DataFrame(chk)
    print(f"sessions identical to the persisted Fig 2G table: {int(C.identical.sum())} / {len(C)}", flush=True)
    C.to_csv(a.out.with_name(a.out.stem + "_checks.csv"), index=False)
    A = A.merge(K, on=["animal", "date", "side"])          # Fig 2G session x side set
    A.drop(columns="src_row").to_parquet(a.out, index=False)
    print("wrote", a.out, len(A), "licks", flush=True)


if __name__ == "__main__":
    main()
