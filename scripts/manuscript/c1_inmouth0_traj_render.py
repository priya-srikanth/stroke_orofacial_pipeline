"""Two-tone trajectory panels re-rendered with the in-mouth = 0 substrate (CC-B, 2026-11-23, caption review item 1).

Same renderers as manuscript_code/figures/traj_sessions_render.py (kin_v37.c1_rows, kin_v37.c1_path2d,
c1_traj.fig_for; mean +/- SEM across sessions, bins with >= 3 sessions), cohort 1 only, reading:
  session tables  <tables>/c1_traj_sessions_<S>.csv, c1_traj_xy_sessions_<S>.csv   (run_trajectory_session_tables.py)
  cluster tables  v3[/_all_licks]/trajectory_cluster_permutation_c2aligned_bh_fdr_<S>.csv (first / all licks) and
                  v3_xy_dist/trajectory_cluster_permutation_c2aligned_bh_fdr_<XYS>.csv
Delta clusters mark the raw panels too (as make_reader / render_r11). axes.labelpad as the live renders.
Usage: python scripts/manuscript/c1_inmouth0_traj_render.py <tables_dir> <out_dir> [S] [XYS]
  (defaults S = ps47d5_inmouth0, XYS = ps47d5: the xy substrate is unchanged by the rule, see SECTION note)
"""
import sys
from pathlib import Path

import pandas as pd

MC = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/manuscript_code/figures")
sys.path.insert(0, str(MC))
import c1_traj as T  # noqa: E402
import kin_v37 as K  # noqa: E402

PP = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats/results/phenotype_pooled")
V3 = str(PP / "phase_aligned_trajectories/3_tier/v3")
V3ALL = str(PP / "phase_aligned_trajectories_all_licks/3_tier/v3")
V3XY = str(PP / "phase_aligned_trajectories/3_tier/v3_xy_dist")


def main():
    tables, out = Path(sys.argv[1]), Path(sys.argv[2])
    sfx = sys.argv[3] if len(sys.argv) > 3 else "ps47d5_inmouth0"
    xysfx = sys.argv[4] if len(sys.argv) > 4 else "ps47d5"
    if out.exists():
        sys.exit(f"refusing to overwrite: {out} exists")
    out.mkdir(parents=True)
    _read = pd.read_csv
    SES = _read(tables / f"c1_traj_sessions_{sfx}.csv")
    XYS = _read(tables / f"c1_traj_xy_sessions_{sfx}.csv")
    cl = {"first": _read(Path(V3) / f"trajectory_cluster_permutation_c2aligned_bh_fdr_{sfx}.csv"),
          "all": _read(Path(V3ALL) / f"trajectory_cluster_permutation_c2aligned_bh_fdr_{sfx}.csv"),
          "xy": _read(Path(V3XY) / f"trajectory_cluster_permutation_c2aligned_bh_fdr_{xysfx}.csv")}

    def rd(path, *a, **k):
        p = Path(str(path))
        ls = "all" if "all_licks" in str(p) else "first"
        if p.name == "phenotype_pooled_phase_bin_mean_sem.csv":
            src = XYS if "xy_dist" in str(p.parent) else SES
            return src[src.lick_set == ls].drop(columns="lick_set").copy()
        if p.name == "trajectory_cluster_permutation_bh_fdr.csv":
            c = cl["xy"] if "xy_dist" in str(p.parent) else cl[ls]
            return pd.concat([c, c.assign(variant="raw")], ignore_index=True)
        return _read(path, *a, **k)

    pd.read_csv = rd
    K.pd.read_csv = rd
    T.pd.read_csv = rd
    import matplotlib
    matplotlib.rcParams["axes.labelpad"] = 1.5
    q = SES[(SES.lick_set == "first") & (SES.variant == "raw") & SES.signal.isin(["x_centered", "y_centered"])]
    sem = q.pivot_table(index=["recovery_phenotype", "epoch_label", "side", "phase_bin"], columns="signal",
                        values="sem").reset_index()
    sem = sem.rename(columns={"x_centered": "x_centered_sem_sessions", "y_centered": "y_centered_sem_sessions"})
    semcsv = out / "_c1_path_sem_from_sessions.csv"
    sem.to_csv(semcsv, index=False)
    K.c1_path2d(V3, out, sem_csv=str(semcsv))
    sg = K.S.ANGLE_SIGN_C1
    K.c1_rows(V3, "angle_deg", "raw", sg, "angle (deg)", "First-lick tongue angle (+ = contralesional)", str(out / "C1_traj_angle_raw"))
    K.c1_rows(V3, "x_centered", "raw", sg, "lateral (px)", "First-lick lateral position (+ = contralesional)", str(out / "C1_traj_lateral_raw"))
    K.c1_rows(V3, "x_centered", "delta", sg, "Δ lateral (px)", "First-lick lateral position, change from pre-stroke", str(out / "C1_traj_lateral_delta"))
    K.c1_rows(V3ALL, "angle_deg", "raw", sg, "angle (deg)", "All-lick tongue angle (+ = contralesional)", str(out / "C1_traj_angle_all_raw"))
    K.c1_rows(V3ALL, "angle_deg", "delta", sg, "Δ angle (deg)", "All-lick tongue angle, change from pre-stroke", str(out / "C1_traj_angle_all_delta"))
    K.c1_rows(V3XY, "xy_dist", "raw", 1, "xy (px)", "First-lick protrusion, xy distance from the mouth", str(out / "C1_traj_xy_raw"))
    K.c1_rows(V3XY, "xy_dist", "delta", 1, "Δ xy (px)", "First-lick protrusion (xy), change from pre-stroke", str(out / "C1_traj_xy_delta"))
    T.fig_for(V3, "First-lick", str(out / "F2_traj_first_overlaid"))
    T.fig_for(V3ALL, "All-lick", str(out / "F2_traj_all_overlaid"))
    for f in out.glob("*.*"):
        if f.suffix in (".pdf", ".png", ".svg") and "_inmouth0" not in f.stem:
            f.rename(f.with_name(f"{f.stem}_inmouth0{f.suffix}"))


if __name__ == "__main__":
    main()
