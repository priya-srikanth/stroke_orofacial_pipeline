"""v29 style for the two-tone epoch panels (Priya 2026-11-23): the line that bridges an epoch with no data (severe:
pre -> subacute, no acute) is DOTTED, semi-transparent and drawn BEHIND every other line and marker.

ONE place: BRIDGE below. The three manuscript renderers that draw the bridge (manuscript_code/figures c1_panels.render,
s6_onepage_v28.scalar_panel, recovery_mechanics/s8_compact_v28.epoch_panel_axes) all draw it with the same statement
    ax.plot(xs[a:a + 2], ms[a:a + 2], '--' if gap else '-', color=..., lw=..., zorder=2)
load_patched() loads such a module with that statement routed to bridge_plot() (the source file is NOT edited; the
replacement count is asserted). The same two-line change can be applied to the master scripts:
    if gap: ax.plot(x, y, **BRIDGE, color=c, lw=lw)  else: ax.plot(x, y, '-', color=c, lw=lw, zorder=2)

Re-render (writes NEW files with suffix _v29style; refuses to overwrite):
  python scripts/manuscript/c1_bridge_v29style.py <out_dir>
"""
import importlib.util
import os
import re
import sys
import types
from pathlib import Path

BRIDGE = dict(ls=(0, (1, 1.6)), alpha=0.4, zorder=0.5)   # dotted, semi-transparent, below scatter (1) / lines (2)
MC = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/manuscript_code/figures")
PAT = re.compile(r"ax\.plot\((xs\[\w+:\w+ \+ 2\]), (ms\[\w+:\w+ \+ 2\]), '--' if gap else '-', color=([^,]+), "
                 r"lw=([\d.]+), zorder=2\)")


def bridge_plot(ax, x, y, gap, color, lw):
    """Solid epoch line (zorder 2), or the v29 bridge (dotted, alpha 0.4, zorder 0.5) across a missing epoch."""
    if gap:
        return ax.plot(x, y, color=color, lw=lw, **BRIDGE)
    return ax.plot(x, y, '-', color=color, lw=lw, zorder=2)


def load_patched(path, name):
    src = Path(path).read_text(encoding="utf-8")
    new, n = PAT.subn(r"_bridge_plot(ax, \1, \2, gap, color=\3, lw=\4)", src)
    assert n == 1, f"{path}: expected one bridge statement, found {n}"
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    mod._bridge_plot = bridge_plot
    sys.modules[name] = mod
    exec(compile(new, str(path), "exec"), mod.__dict__)
    return mod


def main():
    import matplotlib
    matplotlib.use("Agg")
    import pandas as pd
    out = Path(sys.argv[1])
    if out.exists():
        sys.exit(f"refusing to overwrite {out}")
    out.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[2]
    os.environ["PIPELINE_REPO"] = str(repo)                   # animals.yaml with PS47 chronic from day 5
    sys.path[:0] = [str(MC), str(MC / "recovery_mechanics")]
    C = load_patched(MC / "c1_panels.py", "c1_panels")        # c1_panels_c2aligned / s6 import this patched module
    import c1_panels_c2aligned as A
    stats = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
    r3 = stats / "results/phenotype_pooled/3_tier"
    FINAL = "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123"
    sheet = pd.read_csv(r3 / f"{FINAL}.csv")
    relab = A.epoch_relabeller()

    def sm(slug):
        d = pd.read_csv(stats / "inputs/sessmean_licks" / f"{slug}_per_session.csv")
        return d[d.passes_min_licks][["animal", "date", "side", "value", "epoch_label"]]

    # 1) Fig 1 E-I and Fig 2 C-G single panels (live renderer, labelpad 1.5 as the *_lp files)
    matplotlib.rcParams["axes.labelpad"] = 1.5
    for name in ("F1_accuracy", "F1_correct_licks", "F1_latency", "F1_dprime", "F1_criterion", "F2_first_lick_time",
                 "F2_angle_first", "F2_angle_all"):
        src, ep, fam, ylab, sign = C.PANELS[name]
        ep = A.C2_RENAME.get(ep, ep)
        s = C.per_session_scalar(stats, ep) if src == "scalar" else C.per_session_phase(stats, fam, ep)
        C.render(C.baseline(relab(s), sign), sheet, fam, ep, ylab, str(out / f"{name}_lp_ps47d5_v29style"))
    C.render(C.baseline(sm("tongue_sessmean_xy_peak"), 1), sheet, "scalar", "tongue_sessmean_xy_peak",
             "Δ peak protrusion, xy,\nall licks (px)", str(out / "S_xy_all_lp_ps47d5_sessmean_v29style"))
    C.render(C.baseline(sm("tongue_alllicks_onsetpeak_sessmean_vxy_peak"), 1), sheet, "scalar",
             "tongue_alllicks_onsetpeak_sessmean_vxy_peak", "Δ peak speed,\nall licks (px/s)",
             str(out / "F2_speed_all_lp_ps47d5_alllicks_onsetpeak_sessmean_v29style"))
    C.render(C.baseline(sm("tongue_lick1_onsetpeak_vxy_peak"), 1), sheet, "scalar", "tongue_lick1_onsetpeak_vxy_peak",
             "Δ first-lick peak\nspeed (px/s)", str(out / "F2_speed_first_lp_ps47d5_onsetpeak_final_v29style"))
    print("scalar panels done", flush=True)
    # 2) S6 one-page (in-mouth = 0 trajectories, final-family stars, S6D merged), as the live _v2 (--align-axes)
    S6 = load_patched(MC / "s6_onepage_v28.py", "s6_onepage_v28")
    S6.TRAJ.update(lm=S6.SCAL["lm"], aw=41.0)
    pg, H = S6.build(stats, stats / "results/trajectory_sessions", "_ps47d5_inmouth0", repo, FINAL, FINAL)
    stem = out / "S6_two_tone_kinematics_v28_onepage_ps47d5_inmouth0_v29style"
    pg.fig.savefig(f"{stem}.pdf", bbox_inches=None)
    pg.fig.savefig(f"{stem}.png", dpi=300, bbox_inches=None)
    print("S6 done", flush=True)
    # 3) S8 compact 4-in (data unchanged; same inputs as the live file)
    S8 = load_patched(MC / "recovery_mechanics/s8_compact_v28.py", "s8_compact_v28")
    V = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper")
    D = S8.load_rm(V / "review/c1_recovery_mechanics_2026-11-21_r2/tables")
    S8.compact(D, V / "manuscript_code/data/c1_aim_acc_sessions.csv", V / "manuscript_code/data/c1_aim_acc_stats.csv",
               out, "S8_aim_recovery_v28_compact_4in_v29style", **S8.LAYOUT_4IN)
    print("S8 done", flush=True)


if __name__ == "__main__":
    main()
