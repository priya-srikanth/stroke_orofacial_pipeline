"""Two-tone panels for caption review items 29, 30 and 34 (CC-B, 2026-11-23), drawn with the manuscript renderer
unchanged (manuscript_code/figures/c1_panels.py render + baseline; live size, colors, star rule; axes.labelpad 1.5 pt
as the *_lp files). Session values from stats/inputs/sessmedian_times/, stars from
pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_timesmedian_lpr.csv (headline_and_bootstrap_sig):
  F1_latency_lp_ps47d5_sessmedian       Fig 1G  first-correct-lick latency, session median over trials (s)
  F2_first_lick_time_lp_ps47d5_sessmedian Fig 2C first camera-lick latency, session median over trials (ms)
  F2_ili_lp_ps47d5_sessmedian           S6A     median within-bout ILI (intervals <= 300 ms), 70-3000 ms (ms)
  S6_licks_per_resp_camera_lp_ps47d5    S6 new  camera licks per responded trial (70-5000 ms)
Usage: python scripts/manuscript/c1_times_lpr_panels.py <out_dir>
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
SH = ROOT / "results/phenotype_pooled/3_tier/pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_timesmedian_lpr.csv"
JOBS = [("F1_latency_lp_ps47d5_sessmedian", "latency_to_first_correct_lick_s_sessmedian",
         "Δ latency to first\ncorrect lick (s)"),
        ("F2_first_lick_time_lp_ps47d5_sessmedian", "tongue_first_peak_t_ms_sessmedian",
         "Δ latency to first\ncamera lick (ms)"),
        ("F2_ili_lp_ps47d5_sessmedian", "tongue_sessmedian_within_bout_ili_ms", "Δ within-bout ILI (ms)"),
        ("S6_licks_per_resp_camera_lp_ps47d5", "tongue_n_licks_per_responded_trial",
         "Δ camera licks per\nresponded trial")]


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    sh = pd.read_csv(SH)
    for stem, ep, ylab in JOBS:
        if any((out / f"{stem}.{x}").exists() for x in ("pdf", "png")):
            sys.exit(f"refusing to overwrite {out / stem}")
        s = pd.read_csv(ROOT / "inputs/sessmedian_times" / f"{ep}_per_session.csv")
        C.render(C.baseline(s[["animal", "date", "side", "value", "epoch_label"]], 1), sh, "scalar", ep, ylab,
                 str(out / stem))
        print("wrote", stem)


if __name__ == "__main__":
    main()
