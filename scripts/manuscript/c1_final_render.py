"""FINAL two-tone panels (CC-B, 2026-11-23; suffix _FINAL_ccB1123), drawn with the live manuscript renderers.

Marks from pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123.csv (`mark`: '**' = q < 0.05 and nested
bootstrap CI excludes 0; dagger = one animal, q < 0.05 and within-animal bootstrap CI excludes 0). The renderers are
loaded with the exact, count-checked substitutions of c1_dagger_render (v29dag2: dagger 0.30 epoch right of the star
column, 0.75 x the star size; dotted, semi-transparent severe bridge). Source files are not edited.

Per-session values: the FINAL definitions.
  Fig 1E, 1F, 1H, 1I     unchanged inputs (no_filter), marks from the FINAL family
  Fig 1G, Fig 2C, S6A    session MEDIAN over trials / within-bout intervals (stats/inputs/sessmedian_times)
  Fig 2D, 2E             all licks, per-trial median then session mean (stats/inputs/final_ccB1123)
  S6D, first-lick speed  session median over trials of the first lick (stats/inputs/final_ccB1123)
  Fig 2F, 2G, S6E, S6F   angles / lateral position, session means (unchanged)
Pages: S6 in the live v28 layout (A = ILI, D = first-lick xy; s6_onepage_v28) and in CC-A's v29 layout, which adds the
first-lick peak speed panel (s6_onepage_v29; A = first-lick xy, B = first-lick speed, L = ILI); S8 compact 4-in
(v29dag2 test tables; data unchanged). Trajectories: _ps47d5_inmouth0.
Usage: python scripts/manuscript/c1_final_render.py <FINAL_twotone_dir>
"""
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c1_bridge_v29style import MC  # noqa: E402
from c1_dagger_render import C_SUBS, DAGGER, S6_SUBS, S8_SUBS, load_subst  # noqa: E402

STATS = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
FINAL = "pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123"
V = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper")
DAGT = V / "ccB_caption_review_2026-11-23/twotone_rerun/v29dag/tables"
SFX = "_FINAL_ccB1123"
FILES = {"latency_to_first_correct_lick_s_sessmedian": "sessmedian_times",
         "tongue_first_peak_t_ms_sessmedian": "sessmedian_times",
         "tongue_sessmedian_within_bout_ili_ms": "sessmedian_times",
         "tongue_alllicks_trialmed_xy_peak": "final_ccB1123",
         "tongue_alllicks_onsetpeak_trialmed_vxy_peak": "final_ccB1123",
         "tongue_lick1_sessmedian_xy_peak": "final_ccB1123",
         "tongue_lick1_onsetpeak_sessmedian_vxy_peak": "final_ccB1123"}
# panel stem -> (C.PANELS key or None, endpoint, family, y label, sign)
SINGLE = [("F1_accuracy", "F1_accuracy"), ("F1_correct_licks", "F1_correct_licks"),
          ("F1_latency", ("scalar", "latency_to_first_correct_lick_s_sessmedian", None,
                          "Δ latency to first\ncorrect lick (s)", 1)),
          ("F1_dprime", "F1_dprime"), ("F1_criterion", "F1_criterion"),
          ("F2_first_lick_time", ("scalar", "tongue_first_peak_t_ms_sessmedian", None,
                                  "Δ latency to first\ncamera lick (ms)", 1)),
          ("S_xy_all", ("scalar", "tongue_alllicks_trialmed_xy_peak", None, "Δ peak protrusion, xy,\nall licks (px)", 1)),
          ("F2_speed_all", ("scalar", "tongue_alllicks_onsetpeak_trialmed_vxy_peak", None,
                            "Δ peak speed,\nall licks (px/s)", 1)),
          ("F2_angle_first", "F2_angle_first"), ("F2_angle_all", "F2_angle_all"),
          ("F2_ili", ("scalar", "tongue_sessmedian_within_bout_ili_ms", None, "Δ within-bout ILI (ms)", 1)),
          ("F2_xy_first", ("scalar", "tongue_lick1_sessmedian_xy_peak", None,
                           "Δ first-lick peak\nprotrusion, xy (px)", 1)),
          ("F2_speed_first", ("scalar", "tongue_lick1_onsetpeak_sessmedian_vxy_peak", None,
                              "Δ first-lick peak\nspeed (px/s)", 1))]


def main():
    import matplotlib
    matplotlib.use("Agg")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob(f"*{SFX}.p*")):
        sys.exit(f"refusing to overwrite *{SFX}.* in {out}")
    repo = Path(__file__).resolve().parents[2]
    os.environ["PIPELINE_REPO"] = str(repo)
    sys.path[:0] = [str(MC), str(MC / "recovery_mechanics")]
    C = load_subst(MC / "c1_panels.py", "c1_panels", C_SUBS)
    import c1_panels_c2aligned as A
    sheet = pd.read_csv(STATS / f"results/phenotype_pooled/3_tier/{FINAL}.csv", encoding="utf-8",
                        keep_default_na=False, na_values=[""])
    sheet["mark"] = sheet["mark"].fillna("")
    assert set(sheet["mark"]) <= {"", "**", DAGGER}
    relab = A.epoch_relabeller()

    orig_pss = C.per_session_scalar

    def per_session_final(root, ep):
        """FINAL per-session tables for the changed endpoints; the live inputs otherwise."""
        if ep in FILES:
            d = pd.read_csv(STATS / "inputs" / FILES[ep] / f"{ep}_per_session.csv")
            if "passes_min_licks" in d:
                d = d[d.passes_min_licks.astype(bool)]
            return d[["animal", "date", "side", "value", "epoch_label"]]
        return orig_pss(root, ep)
    C.per_session_scalar = per_session_final           # s6_onepage_* call C.per_session_scalar at run time
    C.PANELS["F2_ili"] = dict(SINGLE)["F2_ili"]
    C.PANELS["F2_xy_first"] = dict(SINGLE)["F2_xy_first"]

    matplotlib.rcParams["axes.labelpad"] = 1.5
    for stem, spec in SINGLE:
        src, ep, fam, ylab, sign = C.PANELS[spec] if isinstance(spec, str) else spec
        ep = A.C2_RENAME.get(ep, ep)
        s = C.per_session_scalar(STATS, ep) if src == "scalar" else C.per_session_phase(STATS, fam, ep)
        C.render(C.baseline(relab(s), sign), sheet, fam, ep, ylab, str(out / f"{stem}_lp_ps47d5{SFX}"))
        print("wrote", stem, flush=True)
    import matplotlib.pyplot as plt
    import vls_style as S
    fig, ax = plt.subplots(figsize=(5.6, 0.3)); ax.axis('off')
    h = [plt.Line2D([], [], color=S.SEV[p], marker=S.SEV_MK[p], mec='k', mew=0.35, ms=4, lw=1,
                    label=f'{p} (n = {S.SEV_N[p]})') for p in C.PHENOS]
    h.append(plt.Line2D([], [], color='0.2', marker='$**$', ls='none', ms=7, label='q < 0.05 & CI'))
    h.append(plt.Line2D([], [], color='0.2', marker='$\u2020$', ls='none', ms=6, label='one animal: q < 0.05 & CI'))
    ax.legend(handles=h, ncol=5, loc='center', fontsize=6.6, columnspacing=0.8, handlelength=1.4)
    S.save(fig, str(out / f"C1_severity_key{SFX}"))
    plt.close("all")

    # S6, live v28 layout (A = ILI median, D = first-lick xy median)
    S6 = load_subst(MC / "s6_onepage_v28.py", "s6_onepage_v28", S6_SUBS)
    S6.TRAJ.update(lm=S6.SCAL["lm"], aw=41.0)
    pg, H = S6.build(STATS, STATS / "results/trajectory_sessions", "_ps47d5_inmouth0", repo, FINAL, FINAL)
    stem = out / f"S6_two_tone_kinematics_v28_onepage_ps47d5{SFX}"
    pg.fig.savefig(f"{stem}.pdf", bbox_inches=None); pg.fig.savefig(f"{stem}.png", dpi=300, bbox_inches=None)
    plt.close("all")
    print("S6 v28 done", flush=True)
    # S6, v29 layout with the first-lick peak speed panel (session median over first licks)
    S6b = load_subst(MC / "s6_onepage_v29.py", "s6_onepage_v29", S6_SUBS + [
        ("ep = 'tongue_lick1_onsetpeak_vxy_peak'", "ep = 'tongue_lick1_onsetpeak_sessmedian_vxy_peak'", 1),
        ("stats / 'inputs/sessmean_licks' / f'{ep}_per_session.csv'",
         "stats / 'inputs/final_ccB1123' / f'{ep}_per_session.csv'", 1)])
    S6b.TRAJ.update(lm=S6b.SCAL["lm"], aw=41.0)
    pg, H = S6b.build(STATS, STATS / "results/trajectory_sessions", "_ps47d5_inmouth0", repo, FINAL, "none")
    stem = out / f"S6_two_tone_kinematics_v29_onepage_ps47d5{SFX}"
    pg.fig.savefig(f"{stem}.pdf", bbox_inches=None); pg.fig.savefig(f"{stem}.png", dpi=300, bbox_inches=None)
    plt.close("all")
    print("S6 v29 done", flush=True)
    # S8 compact 4-in (data and stars unchanged; daggers from the v29dag2 tables)
    S8 = load_subst(MC / "recovery_mechanics/s8_compact_v28.py", "s8_compact_v28", S8_SUBS)
    D = S8.load_rm(V / "review/c1_recovery_mechanics_2026-11-21_r2/tables")
    D["R1"] = pd.read_csv(DAGT / "tests_within_lick_dagger.csv", encoding="utf-8")
    D["R3"] = pd.read_csv(DAGT / "tests_across_lick_dagger.csv", encoding="utf-8")
    for k in ("R1", "R3"):
        D[k]["mark"] = D[k]["mark"].fillna("")
    S8.compact(D, V / "manuscript_code/data/c1_aim_acc_sessions.csv", V / "manuscript_code/data/c1_aim_acc_stats.csv",
               out, f"S8_aim_recovery_v28_compact_4in{SFX}", **S8.LAYOUT_4IN)
    print("S8 done", flush=True)


if __name__ == "__main__":
    main()
