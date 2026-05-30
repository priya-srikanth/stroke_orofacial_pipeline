"""Focused diagnostic: interpolated (detector-input) vs cleaned (figure)
tongue-y at the suspect mod-severe acute contra peaks (PS51, side R).

Answers two questions:
  (1) Did these pass the v7 rise/fall detector criteria legitimately, or
      should the baseline-fill-excluded / rising-falling logic have rejected
      them?
  (2) Show the actual traces.

For each suspect first-lick peak it overlays, in a +-window around the peak:
  - interpolated y_final (the DETECTOR INPUT, pre-v7-clean) — blue
  - cleaned y_final (the FIGURE substrate, baseline-filled) — red
  - is_baseline_fill frames (cleaned) — gray ticks along the baseline
  - likelihood_raw (right axis) — dotted
  - v7-kept peak frame — star
  - detector rise/fall thresholds annotated

READ-ONLY. Writes only PNG/SVG under stats/sensitivity/trajectory_qc/.
"""
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
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.manifest import build_manifest

ANIMAL = "PS51"
DATE = dt.date(2025, 5, 4)
SIDE = "R"
SUSPECT_TRIALS = [1, 10, 25, 30, 31, 44, 50, 60, 66, 77, 92, 95]
WIN_MS = 120.0           # plot window +- around each peak
FPS = 250.0
RISE_MIN_MS = 16.0       # detector rise_min_ms
FALL_MIN_MS = 16.0


def main() -> None:
    r = PathResolver()
    out = r.pipeline_outputs().parent / "stats" / "sensitivity" / "trajectory_qc"
    out.mkdir(parents=True, exist_ok=True)

    interp = pd.read_parquet(r.interpolated_trace("tongue", ANIMAL, DATE))
    cleaned = pd.read_parquet(r.cleaned_trace("tongue", ANIMAL, DATE))
    print("interp cols:", list(interp.columns))
    print("cleaned cols:", list(cleaned.columns))
    interp = interp.set_index("frame_idx").sort_index()
    cleaned = cleaned.set_index("frame_idx").sort_index()

    bundle = build_tongue_visual_bundle_by_animal_date(ANIMAL, DATE, r)
    info = get_animal(ANIMAL)
    manifest = build_manifest(
        ANIMAL, DATE, r, info, analysis_context="dlc.kinematics.tongue_pertrial",
    )
    events = _derive_trial_events_from_spout_behavior(
        animal=ANIMAL, date=DATE, resolver=r, manifest=manifest,
    )
    tone_by_trial = {(e.trial_index, e.side): e.tone_frame_idx for e in events}

    win_f = int(round(WIN_MS / 1000.0 * FPS))
    rise_f = int(round(RISE_MIN_MS / 1000.0 * FPS))
    fall_f = int(round(FALL_MIN_MS / 1000.0 * FPS))

    fig, axes = plt.subplots(4, 3, figsize=(15, 12))
    axes = axes.ravel()
    for k, trial in enumerate(SUSPECT_TRIALS):
        ax = axes[k]
        pk = bundle.df_bouts[
            (bundle.df_bouts.trial_index == trial)
            & (bundle.df_bouts.side == SIDE)
            & (bundle.df_bouts.peak_t_ms.notna())
        ]
        peaks = sorted(float(v) for v in pk.peak_t_ms.to_numpy())
        tone = tone_by_trial.get((trial, SIDE))
        if tone is None or not peaks:
            ax.set_title(f"t{trial}: no tone/peak")
            continue
        first_pt = peaks[0]
        peak_frame = int(tone + round(first_pt / 1000.0 * FPS))
        lo, hi = peak_frame - win_f, peak_frame + win_f + 1
        idx = np.arange(lo, hi)
        valid = (idx >= interp.index.min()) & (idx <= interp.index.max())
        idx = idx[valid]
        rel_ms = (idx - peak_frame) / FPS * 1000.0
        iy = interp.reindex(idx)["y_final"].to_numpy()
        cy = cleaned.reindex(idx)["y_final"].to_numpy()
        bfill = cleaned.reindex(idx)["is_baseline_fill"].to_numpy().astype(bool)
        lik = interp.reindex(idx)["likelihood_raw"].to_numpy()

        ax.plot(rel_ms, iy, color="tab:blue", lw=1.1,
                label="interp y (detector input)")
        ax.plot(rel_ms, cy, color="tab:red", lw=1.1, ls="-",
                label="cleaned y (figure)")
        # baseline-fill frames of the cleaned trace.
        if bfill.any():
            ax.plot(rel_ms[bfill], np.full(bfill.sum(), -5.0), "|",
                    color="0.5", ms=8, label="cleaned baseline-fill")
        ax.axvline(0, color="k", lw=0.6, ls=":")
        ax.axhline(20, color="green", lw=0.5, ls="--")  # min_peak_y_abs
        # rise/fall windows the detector inspects.
        ax.axvspan(-rise_f / FPS * 1000, 0, color="tab:cyan", alpha=0.12)
        ax.axvspan(0, fall_f / FPS * 1000, color="tab:orange", alpha=0.12)
        ax2 = ax.twinx()
        ax2.plot(rel_ms, lik, color="0.6", lw=0.7, ls=":")
        ax2.set_ylim(0, 1.05)
        ax2.set_ylabel("lik", fontsize=6, color="0.5")
        ax2.tick_params(labelsize=5)
        # peak markers
        for p in peaks:
            pf = int(tone + round(p / 1000.0 * FPS))
            if lo <= pf < hi:
                rm = (pf - peak_frame) / FPS * 1000.0
                yv = interp.reindex([pf])["y_final"].to_numpy()[0]
                ax.plot(rm, yv, "*", color="darkred", ms=11, zorder=6)
        ax.set_title(f"PS51 {DATE} t{trial} R  (npk={len(peaks)})", fontsize=8)
        ax.set_xlabel("ms rel. first peak", fontsize=6)
        ax.set_ylabel("y (px)", fontsize=6)
        ax.tick_params(labelsize=5)
        if k == 0:
            ax.legend(fontsize=5, loc="upper left")
    fig.suptitle(
        "PS51 mod-severe acute contra — interpolated (detector input, blue) "
        "vs cleaned (figure, red) tongue-y at suspect peaks\n"
        "cyan = rise window (need >=4 rising frames), orange = fall window "
        "(>=4 falling OR immediate baseline retraction); green dash = "
        "min_peak_y_abs=20px",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out / "diag_interp_vs_cleaned_mod_severe.png", dpi=110)
    fig.savefig(out / "diag_interp_vs_cleaned_mod_severe.svg")
    plt.close(fig)
    print("WROTE:", out / "diag_interp_vs_cleaned_mod_severe.png")


if __name__ == "__main__":
    main()
