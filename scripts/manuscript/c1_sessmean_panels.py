"""Fig 2D, Fig 2E and S6D re-rendered for caption review items 19-20 (CC-B, 2026-11-23).

Uses the manuscript renderer unchanged (vls_stroke_paper/manuscript_code/figures/c1_panels.py: render, baseline;
same size, colors, star rule), with axes.labelpad = 1.5 pt as the *_lp files. Inputs:
  S_xy_all_sessmean   Fig 2D  session mean over all kept licks of xy distance (stats/inputs/sessmean_licks/)
  F2_speed_all_sessmean Fig 2E  session mean over licks 1-5 of each trial of peak speed (same folder)
  F2_xy_first_merged  S6D     first-lick xy (unchanged data), stars from the merged scalar family
Stars: pooled_phenotype_stats_c2aligned_v3_ps47d5_sessmean.csv (headline_and_bootstrap_sig).
--control re-renders the CURRENT S_xy_all from the old sheets, to check the renderer reproduces the live panel.
Usage: python scripts/manuscript/c1_sessmean_panels.py <out_dir> [--control]
"""
import sys
from pathlib import Path

import matplotlib
import pandas as pd

MC = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/manuscript_code/figures")
sys.path.insert(0, str(MC))
import c1_panels as C  # noqa: E402

matplotlib.rcParams["axes.labelpad"] = 1.5
ROOT = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
R3 = ROOT / "results/phenotype_pooled/3_tier"


def sess(slug):
    d = pd.read_csv(ROOT / "inputs/sessmean_licks" / f"{slug}_per_session.csv")
    return d[d.passes_min_licks][["animal", "date", "side", "value", "epoch_label"]]


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if "--control" in sys.argv:
        sh = pd.concat([pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv"),
                        pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv")])
        for name, ep in (("S_xy_all", "tongue_median_xy_peak_per_trial"), ("F2_speed_all", "tongue_median_vxy_peak_per_trial"),
                         ("F2_xy_first", "tongue_lick1_xy_peak")):
            C.render(C.baseline(C.per_session_scalar(ROOT, ep), 1), sh, None, ep, C.PANELS[name][3],
                     str(out / f"{name}_lp_ps47d5_CONTROL"))
        return
    if "--firstspeed" in sys.argv:   # item 26: first-lick peak speed (onset to extension peak), final family stars
        sh = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv")
        C.render(C.baseline(sess("tongue_lick1_onsetpeak_vxy_peak"), 1), sh, "scalar",
                 "tongue_lick1_onsetpeak_vxy_peak", "Δ first-lick peak\nspeed (px/s)",
                 str(out / "F2_speed_first_lp_ps47d5_onsetpeak_final"))
        print("wrote F2_speed_first_lp_ps47d5_onsetpeak_final")
        return
    if "--onsetpeak" in sys.argv:   # Fig 2E, all licks, max speed from lick onset to extension peak only
        sh = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_alllicks_onsetpeak_sessmean.csv")
        C.render(C.baseline(sess("tongue_alllicks_onsetpeak_sessmean_vxy_peak"), 1), sh, "scalar",
                 "tongue_alllicks_onsetpeak_sessmean_vxy_peak", "Δ peak speed,\nall licks (px/s)",
                 str(out / "F2_speed_all_lp_ps47d5_alllicks_onsetpeak_sessmean"))
        print("wrote F2_speed_all_lp_ps47d5_alllicks_onsetpeak_sessmean")
        return
    if "--alllicks" in sys.argv:   # Fig 2E without the five-licks-per-trial cap (c1_speed_alllicks.py)
        sh = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_alllicks_sessmean.csv")
        C.render(C.baseline(sess("tongue_alllicks_sessmean_vxy_peak"), 1), sh, "scalar",
                 "tongue_alllicks_sessmean_vxy_peak", "Δ peak speed,\nall licks (px/s)",
                 str(out / "F2_speed_all_lp_ps47d5_alllicks_sessmean"))
        print("wrote F2_speed_all_lp_ps47d5_alllicks_sessmean")
        return
    sh = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_sessmean.csv")
    jobs = [("S_xy_all_lp_ps47d5_sessmean", sess("tongue_sessmean_xy_peak"), "tongue_sessmean_xy_peak",
             "Δ peak protrusion, xy,\nall licks (px)"),
            ("F2_speed_all_lp_ps47d5_sessmean", sess("tongue_sessmean_vxy_peak"), "tongue_sessmean_vxy_peak",
             "Δ peak speed,\nall licks (px/s)"),
            ("F2_xy_first_lp_ps47d5_merged", C.per_session_scalar(ROOT, "tongue_lick1_xy_peak"), "tongue_lick1_xy_peak",
             C.PANELS["F2_xy_first"][3])]
    for stem, s, ep, ylab in jobs:
        C.render(C.baseline(s, 1), sh, "scalar", ep, ylab, str(out / stem))
        print("wrote", stem)


if __name__ == "__main__":
    main()
