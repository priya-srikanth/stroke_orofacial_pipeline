#!/usr/bin/env python
"""Fig 1K and Fig 3F with the behavioral pre-stroke baseline (caption review item 33, CC-B 2026-11-23).

Draws exactly as the live panels, only the data frame (baseline days, pct) and the stars change:
  Fig 1K as F1_weights_epoch_r2_unified.pdf (manuscript_code/figures/weights_epoch_unified_render.py, 2.25 x 1.62 in),
         animal-days from c1_weight_days_behavbase_ps47d5.csv, stars from c1_weight_epoch_behavbase_ps47d5.csv;
  Fig 3F as C2_fig3_weight_epoch_v28.pdf (manuscript_code/figures/fig3_def_row_v28.py panel_f, 128 x 128 bp, defaults),
         animal-days from c2_weight_days_behavbase.csv, stars from c2_weight_epoch_behavbase.csv.
Usage: weights_behavbase_render.py <manuscript_code/figures> <tables_dir> <out_dir>
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

FIG, TAB, OUT = (Path(x) for x in sys.argv[1:4])
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(FIG))
import matplotlib.pyplot as plt  # noqa: E402
import vls_style as S  # noqa: E402
import weights_by_epoch as WBE  # noqa: E402

for stem in ("F1_weights_epoch_r2_behavbase", "C2_fig3_weight_epoch_v28_behavbase"):
    for ext in ("pdf", "png", "svg"):
        if (OUT / f"{stem}.{ext}").exists():
            sys.exit(f"refusing to overwrite {OUT / stem}.{ext}")

c1 = pd.read_csv(TAB / "c1_weight_days_behavbase_ps47d5.csv")
t1 = pd.read_csv(TAB / "c1_weight_epoch_behavbase_ps47d5.csv", keep_default_na=False)
c2 = pd.read_csv(TAB / "c2_weight_days_behavbase.csv", dtype={"date": str}).assign(group="all")
t2 = pd.read_csv(TAB / "c2_weight_epoch_behavbase.csv", keep_default_na=False)

# Fig 1K (as weights_epoch_unified_render.py)
WBE.stars = lambda s: s if isinstance(s, str) else ''
s1 = t1[["group", "epoch", "star"]].rename(columns={"star": "q"})
G1 = ["mild", "moderate", "severe"]
fig, ax = plt.subplots(figsize=(2.25, 1.62))
WBE.panel(ax, c1, G1, S.SEV, S.SEV_MK, {"mild": -0.24, "moderate": 0.0, "severe": 0.24}, s1,
          star_dy={"mild": 0.0, "moderate": 0.09, "severe": 0.18})
for g in G1:
    ax.plot([], [], S.SEV_MK[g], color=S.SEV[g], mec="k", ms=4, label=f"{g} (n = {S.SEV_N[g]})")
ax.set_ylim(75, ax.get_ylim()[1])
ax.legend(loc="lower right", bbox_to_anchor=(1.03, -0.03), fontsize=7.5, handletextpad=0.3, borderaxespad=0.0,
          labelspacing=0.25, markerfirst=False, alignment="right")
fig.subplots_adjust(left=0.25, right=0.98, bottom=0.15, top=0.76)
S.save(fig, OUT / "F1_weights_epoch_r2_behavbase")

# Fig 3F (as fig3_def_row_v28.panel_f with its defaults)
import fig3_def_row_v28 as F3  # noqa: E402

WBE.cohort2 = lambda _path: c2
t2[["epoch", "star"]].to_csv(OUT / "_c2_stars_tmp.csv", index=False)
a = argparse.Namespace(weights="unused", wstars=OUT / "_c2_stars_tmp.csv", out=str(OUT), suffix="_v28_behavbase",
                       h=128.0, bottom=21.0, axh=74.0, xpad=3.5, wf=128.0, leftf=32.5, f_one_line=False)
sm, _ = F3.panel_f(a, a, OUT)
(OUT / "_c2_stars_tmp.csv").unlink()
print(sm.round(2))
print("wrote", OUT)
