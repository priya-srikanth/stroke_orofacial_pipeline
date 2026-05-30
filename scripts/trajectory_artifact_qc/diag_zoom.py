"""Zoomed 2x2 of representative PS51 suspect peaks — interp vs cleaned y,
high DPI, with raw per-frame y values annotated so the rise/fall structure
that the v7 detector saw is legible. READ-ONLY; writes PNG only."""
from __future__ import annotations

import datetime as dt

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    _derive_trial_events_from_spout_behavior,
    build_tongue_visual_bundle_by_animal_date,
)
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver

ANIMAL, DATE, SIDE = "PS51", dt.date(2025, 5, 4), "R"
TRIALS = [1, 44, 50, 77]   # incl. trial 44 = n_licks==1 (most artifact-prone)
WIN_MS, FPS = 80.0, 250.0


def main() -> None:
    r = PathResolver()
    out = r.pipeline_outputs().parent / "stats" / "sensitivity" / "trajectory_qc"
    interp = pd.read_parquet(r.interpolated_trace("tongue", ANIMAL, DATE)).set_index("frame_idx").sort_index()
    cleaned = pd.read_parquet(r.cleaned_trace("tongue", ANIMAL, DATE)).set_index("frame_idx").sort_index()
    bundle = build_tongue_visual_bundle_by_animal_date(ANIMAL, DATE, r)
    info = get_animal(ANIMAL)
    manifest = build_manifest(ANIMAL, DATE, r, info, analysis_context="dlc.kinematics.tongue_pertrial")
    events = _derive_trial_events_from_spout_behavior(animal=ANIMAL, date=DATE, resolver=r, manifest=manifest)
    tone = {(e.trial_index, e.side): e.tone_frame_idx for e in events}

    win_f = int(round(WIN_MS / 1000.0 * FPS))
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for ax, trial in zip(axes.ravel(), TRIALS):
        pk = bundle.df_bouts[(bundle.df_bouts.trial_index == trial) & (bundle.df_bouts.side == SIDE) & (bundle.df_bouts.peak_t_ms.notna())]
        peaks = sorted(float(v) for v in pk.peak_t_ms.to_numpy())
        t0 = tone[(trial, SIDE)]
        pf = int(t0 + round(peaks[0] / 1000.0 * FPS))
        idx = np.arange(pf - win_f, pf + win_f + 1)
        idx = idx[(idx >= interp.index.min()) & (idx <= interp.index.max())]
        rel = (idx - pf) / FPS * 1000.0
        iy = interp.reindex(idx)["y_final"].to_numpy()
        cy = cleaned.reindex(idx)["y_final"].to_numpy()
        bf = cleaned.reindex(idx)["is_baseline_fill"].to_numpy().astype(bool)
        intp = interp.reindex(idx)["is_interp_fill"].to_numpy().astype(bool)
        lik = interp.reindex(idx)["likelihood_raw"].to_numpy()
        ax.plot(rel, iy, "-o", color="tab:blue", ms=3, lw=1.0, label="interp y (detector input)")
        ax.plot(rel, cy, "-s", color="tab:red", ms=3, lw=1.0, label="cleaned y (figure)")
        if bf.any():
            ax.plot(rel[bf], cy[bf], "s", color="red", mfc="white", ms=7, label="cleaned baseline-fill")
        if intp.any():
            ax.plot(rel[intp], iy[intp], "o", color="blue", mfc="white", ms=7, label="interp is_interp_fill")
        ax.axhline(20, color="green", ls="--", lw=0.7, label="min_peak_y_abs=20")
        ax.axvline(0, color="k", ls=":", lw=0.6)
        ax2 = ax.twinx(); ax2.plot(rel, lik, color="0.6", lw=0.8, ls=":"); ax2.set_ylim(0, 1.05); ax2.set_ylabel("likelihood", color="0.5")
        ax.set_title(f"PS51 {DATE} t{trial} R — npk={len(peaks)}", fontsize=11)
        ax.set_xlabel("ms rel. first peak"); ax.set_ylabel("y (px)")
        ax.legend(fontsize=7, loc="upper left")
    fig.suptitle("PS51 mod-severe acute contra — zoomed interp(blue) vs cleaned(red) tongue-y", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out / "diag_zoom_mod_severe.png", dpi=130)
    plt.close(fig)
    print("WROTE", out / "diag_zoom_mod_severe.png")


if __name__ == "__main__":
    main()
