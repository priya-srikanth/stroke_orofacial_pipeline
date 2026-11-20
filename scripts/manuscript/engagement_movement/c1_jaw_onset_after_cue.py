"""Two-tone cohort jaw-only class with the AFTER-CUE rule (Priya 2026-11-20: "for 2B movement must start after cue").

For every trial of every session in dlc_kinematics/tongue_jaw_mismatch/candidate_trials, re-runs the jaw call on the
same cleaned jaw trace with `jaw_pertrial.jaw_onset_after_cue` (same parameters as the stored jaw_pass_qc; the stored
value is reproduced and checked) and writes one row per trial:

  animal, date, trial_index, side, quiet_tongue_pass, jaw_pass_qc (stored), jaw_pass_qc_recomputed,
  onset_frames, reonset_frames, onset_ms, moved_after_cue (1 / 0 / NaN),
  jaw_only_v1   = the current class (candidate_no_lick_with_jaw_move: no camera lick 70 ms..5 s AND jaw_pass_qc)
  jaw_only_v2   = no camera lick AND the jaw movement STARTS after the cue (onset > 0, or an at-cue deflection that
                  settles and moves again); NaN (unknown) when no camera lick and the jaw passed only through an at-cue
                  deflection that never settled -- the six-position cohort's rule (widefield jaw_kinematics.jaw_onsets)

Output (refuses to overwrite): <outputs>/dlc_kinematics/tongue_jaw_mismatch/jaw_onset_after_cue/c1_jaw_onset_trials.parquet
Usage: python c1_jaw_onset_after_cue.py [--jobs 8] [--out PATH]
"""
from __future__ import annotations

import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/dlc_kinematics")
OUT = ROOT / "tongue_jaw_mismatch/jaw_onset_after_cue/c1_jaw_onset_trials.parquet"


def process(cf: str) -> pd.DataFrame | None:
    from types import SimpleNamespace

    from stroke_orofacial.config_loader import load_defaults
    from stroke_orofacial.dlc_kinematics import jaw_pertrial as JP
    cf = Path(cf)
    animal, d = cf.parent.name, cf.stem
    jf = ROOT / f"cleaned_traces/jaw/{animal}/{d}.parquet"
    if not jf.exists():
        return None
    jp = load_defaults()["dlc_kinematics"]["jaw_pertrial"]
    kw = dict(detect_win_ms=tuple(jp["detect_win_ms"]), baseline_win_ms=tuple(jp["baseline_win_ms"]),
              sd_mult=float(jp["deflection_threshold_sd_multiplier"]), min_px=float(jp["deflection_threshold_min_px"]),
              density_thr=float(jp["sustained_density_threshold"]), window_n=int(jp["sustained_window_n_frames"]))
    jy = pd.read_parquet(jf, columns=["y_final"]).y_final.to_numpy(float)
    C = pd.read_parquet(cf, columns=["trial_index", "side", "tone_frame_idx", "fps", "quiet_tongue_pass", "jaw_pass_qc",
                                     "candidate_no_lick_with_jaw_move"])
    rows = []
    for r in C.itertuples():
        fps, c = float(r.fps), int(r.tone_frame_idx)
        o = JP.jaw_onset_after_cue(jy, fps, c, **kw)
        ref = JP._compute_per_trial(SimpleNamespace(trial_index=r.trial_index, side=r.side, tone_frame_idx=c),
                                    jy, fps, len(jy), **kw)["jaw_pass_qc"]
        quiet = bool(r.quiet_tongue_pass)
        v2 = (float("nan") if quiet and np.isnan(o["moved_after_cue"]) else
              float(quiet and o["moved_after_cue"] == 1.0))
        rows.append(dict(animal=animal, date=d, trial_index=int(r.trial_index), side=r.side, quiet_tongue_pass=quiet,
                         jaw_pass_qc=bool(r.jaw_pass_qc), jaw_pass_qc_recomputed=bool(o["jaw_pass_qc"]),
                         jaw_pass_qc_reference=bool(ref), onset_frames=o["onset_frames"],
                         reonset_frames=o["reonset_frames"], onset_ms=o["onset_ms"],
                         moved_after_cue=o["moved_after_cue"],
                         jaw_only_v1=bool(r.candidate_no_lick_with_jaw_move), jaw_only_v2=v2))
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    if a.out.exists():
        sys.exit(f"refusing to overwrite {a.out}")
    files = sorted(str(p) for p in (ROOT / "tongue_jaw_mismatch/candidate_trials").glob("*/*.parquet"))
    with Pool(a.jobs) as p:
        res = p.map(process, files, chunksize=1)
    B = pd.concat([r for r in res if r is not None], ignore_index=True).sort_values(["animal", "date", "trial_index"])
    agree = (B.jaw_pass_qc == B.jaw_pass_qc_recomputed).mean()
    agree_ref = (B.jaw_pass_qc_reference == B.jaw_pass_qc_recomputed).mean()
    print(f"sessions {B[['animal', 'date']].drop_duplicates().shape[0]}, trials {len(B)}; jaw_pass_qc recomputed == stored "
          f"{agree:.4f}, == _compute_per_trial {agree_ref:.4f}")
    nl = B[B.quiet_tongue_pass]
    print(f"no-lick trials {len(nl)}: jaw_only v1 {int(nl.jaw_only_v1.sum())}, v2 {int((nl.jaw_only_v2 == 1).sum())}, "
          f"v2 unknown {int(nl.jaw_only_v2.isna().sum())}, v1 -> not jaw-only {int((nl.jaw_only_v1 & (nl.jaw_only_v2 == 0)).sum())}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    B.to_parquet(a.out, index=False)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
