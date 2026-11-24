"""v29dag: the v29-style two-tone epoch panels with a dagger on single-animal cells (Priya 2026-11-23).

Same renders as c1_bridge_v29style.py (dotted faint bridge, same tables, same sizes), plus:
  - the mark in the top band is read from the sheet's `mark` column written by c1_dagger_single_animal.py:
    '**' (q < 0.05 and nested bootstrap CI excludes 0, unchanged) or a dagger (one animal: q < 0.05 and
    within-animal bootstrap CI excludes 0); drawn at the star's place, font and colour;
  - S8 reads the dagger versions of its test tables and its severity key gets a dagger entry.
The manuscript renderers are not edited: as in c1_bridge_v29style.load_patched, each is loaded with exact source
substitutions whose counts are asserted.

Fig 1 E-I are not re-rendered: no single-animal cell there (DAQ measures, both moderate animals at acute).

Usage: python scripts/manuscript/c1_dagger_render.py <out_dir>    (refuses an existing out_dir's files)
"""
import os
import sys
import types
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c1_bridge_v29style import MC, PAT, bridge_plot  # noqa: E402

DAGGER = "\u2020"
STATS = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
FINAL_DAG = "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_dagger"
V = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper")
TABLES = V / "ccB_caption_review_2026-11-23/twotone_rerun/v29dag/tables"
SFX = "_v29dag"
DAG_SCALE = 0.75   # the dagger spans ascender to descender; at 0.75 x the star size it fills the same band height


def mark_for(sheet, fam, ep, ph, side, epoch):
    """c1_panels.stars_for, returning the sheet's mark ('**', dagger or '') instead of a bool."""
    sd = {'L': 'L', 'R': 'R', 'global': 'both'}[side]
    m = sheet[(sheet.endpoint == ep) & (sheet.recovery_phenotype == ph) & (sheet.side == sd) & (sheet.post_epoch == epoch)]
    if fam:
        m = m[m.family == fam]
    if m.empty:
        return ''
    mk = m.iloc[0]['mark']
    return mk if isinstance(mk, str) else ''


def load_subst(path, name, subs):
    """Load a renderer with the v29 bridge substitution plus `subs` [(old, new, count)], counts asserted."""
    src = Path(path).read_text(encoding="utf-8")
    src, n = PAT.subn(r"_bridge_plot(ax, \1, \2, gap, color=\3, lw=\4)", src)
    assert n == 1, f"{path}: bridge statement count {n}"
    for old, new, cnt in subs:
        k = src.count(old)
        assert k == cnt, f"{path}: {old!r} found {k}x, expected {cnt}"
        src = src.replace(old, new)
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    mod._bridge_plot = bridge_plot
    mod._mark_for = mark_for
    mod.DAG_SCALE = DAG_SCALE
    sys.modules[name] = mod
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


STAR_TXT = "'**', color=S.SEV[ph], ha='center', va='center',"
C_SUBS = [("if stars_for(sheet, fam, ep, ph, side, e):", "if (_mk := _mark_for(sheet, fam, ep, ph, side, e)):", 1),
          (STAR_TXT, STAR_TXT.replace("'**'", "_mk"), 1),
          ("fontsize=8, fontweight='bold')", "fontsize=8 * (1 if _mk == '**' else DAG_SCALE), fontweight='bold')", 1)]
S6_SUBS = [("if C.stars_for(sheet, fam, ep, ph, side, e):", "if (_mk := _mark_for(sheet, fam, ep, ph, side, e)):", 1),
           (STAR_TXT, STAR_TXT.replace("'**'", "_mk"), 1),
           ("fontsize=FSTAR, fontweight='bold')", "fontsize=FSTAR * (1 if _mk == '**' else DAG_SCALE), fontweight='bold')", 1)]
S8_KEY_OLD = "label='q < 0.05 & CI'))\n    return h"
S8_KEY_NEW = ("label='q < 0.05 & CI'))\n"
              "    h.append(plt.Line2D([], [], color='0.2', marker='$\u2020$', ls='none', ms=6, "
              "label='one animal: q < 0.05 & within-animal CI'))\n    return h")
S8_SUBS = [("& R.star]", "& (R.star | R.dagger)]", 1),
           ("ax.annotate('**', (i, 1.0)", "ax.annotate(r.mark, (i, 1.0)", 1),
           ("fontsize=T['star'], fontweight='bold')", "fontsize=T['star'] * (1 if r.mark == '**' else DAG_SCALE), fontweight='bold')", 1),
           (S8_KEY_OLD, S8_KEY_NEW, 1)]


def main():
    import matplotlib
    matplotlib.use("Agg")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob(f"*{SFX}.*")):
        sys.exit(f"refusing to overwrite *{SFX}.* in {out}")
    repo = Path(__file__).resolve().parents[2]
    os.environ["PIPELINE_REPO"] = str(repo)
    sys.path[:0] = [str(MC), str(MC / "recovery_mechanics")]
    C = load_subst(MC / "c1_panels.py", "c1_panels", C_SUBS)
    import c1_panels_c2aligned as A
    sheet = pd.read_csv(STATS / f"results/phenotype_pooled/3_tier/{FINAL_DAG}.csv", encoding="utf-8")
    relab = A.epoch_relabeller()

    def sm(slug):
        d = pd.read_csv(STATS / "inputs/sessmean_licks" / f"{slug}_per_session.csv")
        return d[d.passes_min_licks][["animal", "date", "side", "value", "epoch_label"]]

    matplotlib.rcParams["axes.labelpad"] = 1.5
    for name in ("F2_first_lick_time", "F2_angle_first", "F2_angle_all"):
        src, ep, fam, ylab, sign = C.PANELS[name]
        s = C.per_session_scalar(STATS, ep) if src == "scalar" else C.per_session_phase(STATS, fam, ep)
        C.render(C.baseline(relab(s), sign), sheet, fam, ep, ylab, str(out / f"{name}_lp_ps47d5{SFX}"))
    C.render(C.baseline(sm("tongue_sessmean_xy_peak"), 1), sheet, "scalar", "tongue_sessmean_xy_peak",
             "Δ peak protrusion, xy,\nall licks (px)", str(out / f"S_xy_all_lp_ps47d5_sessmean{SFX}"))
    C.render(C.baseline(sm("tongue_alllicks_onsetpeak_sessmean_vxy_peak"), 1), sheet, "scalar",
             "tongue_alllicks_onsetpeak_sessmean_vxy_peak", "Δ peak speed,\nall licks (px/s)",
             str(out / f"F2_speed_all_lp_ps47d5_alllicks_onsetpeak_sessmean{SFX}"))
    C.render(C.baseline(sm("tongue_lick1_onsetpeak_vxy_peak"), 1), sheet, "scalar", "tongue_lick1_onsetpeak_vxy_peak",
             "Δ first-lick peak\nspeed (px/s)", str(out / f"F2_speed_first_lp_ps47d5_onsetpeak_final{SFX}"))
    # severity key with the dagger entry (C1_severity_key layout)
    import matplotlib.pyplot as plt
    import vls_style as S
    fig, ax = plt.subplots(figsize=(5.6, 0.3)); ax.axis('off')
    h = [plt.Line2D([], [], color=S.SEV[p], marker=S.SEV_MK[p], mec='k', mew=0.35, ms=4, lw=1,
                    label=f'{p} (n = {S.SEV_N[p]})') for p in C.PHENOS]
    h.append(plt.Line2D([], [], color='0.2', marker='$**$', ls='none', ms=7, label='q < 0.05 & CI'))
    h.append(plt.Line2D([], [], color='0.2', marker='$\u2020$', ls='none', ms=6, label='one animal: q < 0.05 & CI'))
    ax.legend(handles=h, ncol=5, loc='center', fontsize=6.6, columnspacing=0.8, handlelength=1.4)
    S.save(fig, str(out / f"C1_severity_key{SFX}"))
    print("scalar panels done", flush=True)
    S6 = load_subst(MC / "s6_onepage_v28.py", "s6_onepage_v28", S6_SUBS)
    S6.TRAJ.update(lm=S6.SCAL["lm"], aw=41.0)
    pg, H = S6.build(STATS, STATS / "results/trajectory_sessions", "_ps47d5_inmouth0", repo, FINAL_DAG, FINAL_DAG)
    stem = out / f"S6_two_tone_kinematics_v28_onepage_ps47d5_inmouth0{SFX}"
    pg.fig.savefig(f"{stem}.pdf", bbox_inches=None)
    pg.fig.savefig(f"{stem}.png", dpi=300, bbox_inches=None)
    print("S6 done", flush=True)
    S8 = load_subst(MC / "recovery_mechanics/s8_compact_v28.py", "s8_compact_v28", S8_SUBS)
    D = S8.load_rm(V / "review/c1_recovery_mechanics_2026-11-21_r2/tables")
    D["R1"] = pd.read_csv(TABLES / "tests_within_lick_dagger.csv", encoding="utf-8")
    D["R3"] = pd.read_csv(TABLES / "tests_across_lick_dagger.csv", encoding="utf-8")
    for k in ("R1", "R3"):
        D[k]["mark"] = D[k]["mark"].fillna("")
    S8.compact(D, V / "manuscript_code/data/c1_aim_acc_sessions.csv", V / "manuscript_code/data/c1_aim_acc_stats.csv",
               out, f"S8_aim_recovery_v28_compact_4in{SFX}", **S8.LAYOUT_4IN)
    print("S8 done", flush=True)


if __name__ == "__main__":
    main()
