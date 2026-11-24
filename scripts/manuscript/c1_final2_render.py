"""FINAL2 two-tone renders (CC-B, 2026-11-23; suffix _FINAL2_ccB1123): only what changed vs the FINAL renders.

Marks from pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall2_ccB1123.csv. Against FINAL (_FINALall_ccB1123) no
mark of a kept cell changes (max |dq| 0.008), so Fig 1E-I, Fig 2C-G, S6A/D/first-lick speed and S8 stand as
_FINAL_ccB1123. New here:
  S6_licks_per_resp_camera_lp_ps47d5_FINAL2_ccB1123   item 30 panel (camera licks per responded trial), live
      c1_panels.render; Y RANGE FIX: the live 1-99% quantile range clipped the single-animal moderate acute
      contralesional-cue marker (-15.8); for this endpoint the range is widened to cover every grade x epoch mean +/- SEM
      (_yrange below; every other endpoint keeps the live 1-99% range exactly);
  S6 pages with the item 30 panel added (same y-range rule):
      S6_two_tone_kinematics_v28_onepage_ps47d5_FINAL2_ccB1123  live v28 layout, item 30 panel = L beside K;
      S6_two_tone_kinematics_v29_onepage_ps47d5_FINAL2_ccB1123  CC-A v29 layout, item 30 panel = M (own row).
Master renderers (11-23 19:50: native mark column, dagger 0.30 epoch right, dotted bridge) loaded with count-checked
substitutions: dagger at 0.75 x the star size (as the FINAL set), the y-range rule, the item 30 panel slot.
Usage: python scripts/manuscript/c1_final2_render.py <panels_dir>
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c1_bridge_v29style import MC  # noqa: E402
from c1_dagger_render import DAGGER, load_subst  # noqa: E402
import c1_final_render as FR  # noqa: E402

STATS = FR.STATS
FINAL2 = "pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall2_ccB1123"
SFX = "_FINAL2_ccB1123"
LPR = "tongue_n_licks_per_responded_trial"
LPR_SPEC = ("scalar", LPR, None, "Δ camera licks per\nresponded trial", 1)
EXTEND = {LPR}
RANGE = ("lo, hi = d.delta.quantile(0.01), d.delta.quantile(0.99)", "lo, hi = _yrange(d, ep)", 1)
# the master renderers draw marks natively since 11-23 19:50 (mark column, dagger DAG_DX right); keep the FINAL set's
# dagger size (0.75 x the star, as v29dag2) so FINAL and FINAL2 panels match
C_SUBS = [("fontsize=8, fontweight='bold')", "fontsize=8 * (1 if mk == '**' else DAG_SCALE), fontweight='bold')", 1)]
S6_SUBS = [("fontsize=FSTAR, fontweight='bold')", "fontsize=FSTAR * (1 if mk == '**' else DAG_SCALE), fontweight='bold')", 1)]


def _yrange(d, ep):
    """Live 1-99% quantile range; for EXTEND endpoints widened to every grade x side x epoch mean +/- SEM."""
    lo, hi = d.delta.quantile(0.01), d.delta.quantile(0.99)
    if ep in EXTEND:
        g = d.groupby(["side", "ph", "epoch_label"]).delta
        m, n, sd = g.mean(), g.size(), g.std(ddof=1)
        se = (sd / np.sqrt(n)).where(n > 1, 0.0)
        lo, hi = min(lo, float((m - se).min())), max(hi, float((m + se).max()))
    return lo, hi


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = Path(sys.argv[1])
    if any(out.glob(f"*{SFX}.p*")):
        sys.exit(f"refusing to overwrite *{SFX}.* in {out}")
    repo = Path(__file__).resolve().parents[2]
    os.environ["PIPELINE_REPO"] = str(repo)
    sys.path[:0] = [str(MC), str(MC / "recovery_mechanics")]
    C = load_subst(MC / "c1_panels.py", "c1_panels", C_SUBS + [RANGE])
    C._yrange = _yrange
    import c1_panels_c2aligned as A
    sheet = pd.read_csv(STATS / f"results/phenotype_pooled/3_tier/{FINAL2}.csv", encoding="utf-8",
                        keep_default_na=False, na_values=[""])
    sheet["mark"] = sheet["mark"].fillna("")
    assert set(sheet["mark"]) <= {"", "**", DAGGER}
    relab = A.epoch_relabeller()
    files = dict(FR.FILES, **{LPR: "sessmedian_times"})
    orig = C.per_session_scalar

    def pss(root, ep):
        if ep in files:
            d = pd.read_csv(STATS / "inputs" / files[ep] / f"{ep}_per_session.csv")
            if "passes_min_licks" in d:
                d = d[d.passes_min_licks.astype(bool)]
            return d[["animal", "date", "side", "value", "epoch_label"]]
        return orig(root, ep)
    C.per_session_scalar = pss
    single = dict(FR.SINGLE)
    C.PANELS["F2_ili"], C.PANELS["F2_xy_first"], C.PANELS["S6_lpr"] = single["F2_ili"], single["F2_xy_first"], LPR_SPEC

    matplotlib.rcParams["axes.labelpad"] = 1.5
    d = C.baseline(relab(pss(STATS, LPR)), 1)
    C.render(d, sheet, None, LPR, LPR_SPEC[3], str(out / f"S6_licks_per_resp_camera_lp_ps47d5{SFX}"))
    plt.close("all")
    print("wrote item 30 panel", flush=True)

    loop = ("for name in ('F2_ili', 'F2_xy_first', 'S_lat_first', 'S_lat_all'):",
            "for name in ('F2_ili', 'F2_xy_first', 'S_lat_first', 'S_lat_all', 'S6_lpr'):", 1)
    hts = ("if b else th for _, a, _, _, b, _ in rows]", "if b else (th if a == 'traj' else sh) for _, a, _, _, b, _ in rows]", 1)
    S6 = load_subst(MC / "s6_onepage_v28.py", "s6_onepage_v28", S6_SUBS + [RANGE, loop, (
        "'First-lick tongue angle (+ = contralesional)'), None, None, None)]",
        "'First-lick tongue angle (+ = contralesional)'), 'L', 'scalar', 'S6_lpr')]", 1)])
    S6._yrange = _yrange
    S6.TRAJ.update(lm=S6.SCAL["lm"], aw=41.0)
    pg, H = S6.build(STATS, STATS / "results/trajectory_sessions", "_ps47d5_inmouth0", repo, FINAL2, FINAL2)
    stem = out / f"S6_two_tone_kinematics_v28_onepage_ps47d5{SFX}"
    pg.fig.savefig(f"{stem}.pdf", bbox_inches=None); pg.fig.savefig(f"{stem}.png", dpi=300, bbox_inches=None)
    plt.close("all")
    print("S6 v28 done", flush=True)
    S6b = load_subst(MC / "s6_onepage_v29.py", "s6_onepage_v29", S6_SUBS + [RANGE, loop, hts,
        ("ep = 'tongue_lick1_onsetpeak_vxy_peak'", "ep = 'tongue_lick1_onsetpeak_sessmedian_vxy_peak'", 1),
        ("stats / 'inputs/sessmean_licks' / f'{ep}_per_session.csv'",
         "stats / 'inputs/final_ccB1123' / f'{ep}_per_session.csv'", 1),
        ("'L', 'scalar', 'F2_ili')]", "'L', 'scalar', 'F2_ili'),\n            ('M', 'scalar', 'S6_lpr', None, None, None)]", 1)])
    S6b._yrange = _yrange
    S6b.TRAJ.update(lm=S6b.SCAL["lm"], aw=41.0)
    pg, H = S6b.build(STATS, STATS / "results/trajectory_sessions", "_ps47d5_inmouth0", repo, FINAL2, "none")
    stem = out / f"S6_two_tone_kinematics_v29_onepage_ps47d5{SFX}"
    pg.fig.savefig(f"{stem}.pdf", bbox_inches=None); pg.fig.savefig(f"{stem}.png", dpi=300, bbox_inches=None)
    plt.close("all")
    print("S6 v29 done", flush=True)


if __name__ == "__main__":
    main()
