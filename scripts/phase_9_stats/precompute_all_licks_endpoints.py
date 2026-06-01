"""Precompute + persist the per-LICK all-licks phase-aligned endpoints.

Structural fix for the I slowness: compute the all-licks endpoints once per
session (build the tongue bundle ONCE) and write them to disk, so both the q13b
all-licks figures and the consolidated stats driver read from disk instead of
rebuilding bundles on-the-fly (twice).

Output: stats/inputs/all_licks_endpoints/<endpoint_slug>/<animal>.parquet
        (one row per (date, trial, lick); columns animal, date, side,
         peak_t_ms, value, epoch_label, is_sentinel) — same schema the stats
         driver's scalar loader consumes.

Usage::
  python scripts/phase_9_stats/precompute_all_licks_endpoints.py
  python scripts/phase_9_stats/precompute_all_licks_endpoints.py --animals PS46
"""
from __future__ import annotations

import argparse
import datetime
import logging
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates  # noqa: E402
from stroke_orofacial.dlc_kinematics.tongue_phase_aligned_endpoints import (  # noqa: E402
    compute_phase_aligned_endpoints_per_trial,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    build_tongue_visual_bundle_by_animal_date,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("precompute_all_licks_endpoints")

ENDPOINTS = (
    "peak_angle_deg",
    "signed_angle_at_max_abs_phase_0_075_deg",
    "signed_x_at_max_abs_phase_0_075_px",
)
COHORT = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--animals", nargs="*", default=list(COHORT))
    args = p.parse_args(argv)
    resolver = PathResolver()
    amap = load_animals()
    out_root = resolver.pipeline_outputs(subdir="stats") / "inputs" / "all_licks_endpoints"

    n_sessions = 0
    for animal in args.animals:
        info = amap.get(animal)
        if info is None:
            log.warning("no AnimalInfo for %s; skipping", animal)
            continue
        rows_by_ep: dict[str, list[dict]] = {ep: [] for ep in ENDPOINTS}
        dates = list(yaml_driven_session_dates(animal))
        log.info("[%s] %d sessions", animal, len(dates))
        for d in dates:
            if isinstance(d, str):
                d = datetime.date.fromisoformat(d)
            try:
                bundle = build_tongue_visual_bundle_by_animal_date(
                    animal=animal, date=d, resolver=resolver)
                per_lick = compute_phase_aligned_endpoints_per_trial(
                    bundle, lick_set="all_multi")
            except Exception as exc:  # noqa: BLE001
                log.warning("  %s/%s build/compute failed: %s", animal, d, exc)
                continue
            if per_lick.empty:
                continue
            rel = int(info.day_relative_to_stroke(d))
            epoch = assign_epoch_label(rel, info)
            for ep in ENDPOINTS:
                if ep not in per_lick.columns:
                    continue
                for _, r in per_lick.iterrows():
                    v = r.get(ep)
                    rows_by_ep[ep].append({
                        "animal": animal, "date": d, "side": str(r["side"]),
                        "peak_t_ms": float(r.get("peak_t_ms", float("nan"))),
                        "value": float(v) if v is not None else float("nan"),
                        "epoch_label": epoch, "is_sentinel": v is None,
                    })
            n_sessions += 1
        for ep, rows in rows_by_ep.items():
            if not rows:
                continue
            d_out = out_root / ep
            d_out.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_parquet(d_out / f"{animal}.parquet", index=False)
        log.info("[%s] wrote %d endpoints", animal,
                 sum(1 for ep in ENDPOINTS if rows_by_ep[ep]))
    log.info("done: %d sessions across %d animals", n_sessions, len(args.animals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
