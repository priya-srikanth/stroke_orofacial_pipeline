"""Does a lower likelihood cutoff recover real below-view (video4) tongue? (Priya 11-19)

The widefield cam1 model, zero-shot on video4, keeps the tongue at p > 0.9 in few frames. For each cutoff, with the
front view's CLEANED tongue as the reference (fill_method 0 = tongue tracked out, 3 = tongue in the mouth):

* recall      = share of front "out" frames where the below-view tongue passes the cutoff
* false_pos   = share of front "in" frames where it passes (a tongue point with no tongue out = wrong)
* (cutoff+gate = p > 0.4 and within 40 px of the rod-tip line: what the clips use)
* r_x         = per-frame correlation of below-view tongue x with front-view tongue x on frames passing the cutoff
                (both are the lateral axis; |r| near the p > 0.9 value = the extra points sit where the tongue is)

Bins (p in [lo, hi)) are reported too, so the quality of the ADDED points is visible on its own.

Run in the dlc env from the work dir's parent (needs only numpy / pandas):
    python scripts/pose3d_2pram/lateral_test/below_tongue_cutoff.py --work <latangle work dir> PS46:20250310 ...
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

CUTS = (0.9, 0.6, 0.4, 0.2, 0.1)
BINS = ((0.9, 1.01), (0.6, 0.9), (0.4, 0.6), (0.2, 0.4), (0.1, 0.2))


def session(work: str, animal: str, date: str) -> list[dict]:
    """Per-cutoff and per-bin rows for one session."""
    Z = np.load(f"{work}/clips/{animal}_{date}_index.npz")
    idx4, trig2, trig4 = Z["idx4"], Z["trig2"], Z["trig4"]
    f2_of_trig = np.full(int(trig2[-1]) + 1, -1)
    f2_of_trig[trig2] = np.arange(len(trig2))
    t = trig4[idx4]
    f2 = np.where(
        (t >= 0) & (t < len(f2_of_trig)), f2_of_trig[np.clip(t, 0, len(f2_of_trig) - 1)], -1
    )
    p = glob.glob(f"{work}/preds/{animal}_{date}_video4_trials_*.csv")[0]
    d = pd.read_csv(p, header=[0, 1, 2], index_col=0)
    d.columns = d.columns.droplevel(0)
    tg = d["tongue"][["x", "y", "likelihood"]].to_numpy(float)
    FC = np.load(f"{work}/clips/{animal}_{date}_front_cleaned.npz")
    ok = f2 >= 0
    fill = np.full(len(f2), -1)
    fill[ok] = FC["tongue_fill"][f2[ok]]
    fx = np.full(len(f2), np.nan)
    fx[ok] = FC["tongue_xy"][f2[ok], 0]
    out_, in_ = fill == 0, fill == 3
    rows = []

    def row(kind, lo, hi, sel):
        both = sel & out_ & np.isfinite(fx)
        r = np.corrcoef(tg[both, 0], fx[both])[0, 1] if both.sum() > 30 else np.nan
        rows.append(
            {
                "animal": animal,
                "date": date,
                "kind": kind,
                "p_lo": lo,
                "p_hi": hi,
                "frames": int(sel.sum()),
                "recall": float((sel & out_).sum() / max(out_.sum(), 1)),
                "false_pos": float((sel & in_).sum() / max(in_.sum(), 1)),
                "share_on_front_out": float(
                    (sel & out_).sum() / max((sel & (out_ | in_)).sum(), 1)
                ),
                "r_x": float(r),
                "n_r": int(both.sum()),
            }
        )

    for c in CUTS:
        row("cutoff", c, 1.0, tg[:, 2] > c)
    # the cutoff used by two_view_clips.py: p > 0.4 and not > 40 px above the rod-tip line (removes nose-tip labels)
    rod_y = np.mean(
        [
            t[1]
            for t in json.loads(Path(f"{work}/clips/{animal}_{date}_tips.json").read_text())["tips"]
        ]
    )
    row("cutoff+gate", 0.4, 1.0, (tg[:, 2] > 0.4) & (tg[:, 1] - rod_y > -40.0))
    for lo, hi in BINS:
        row("bin", lo, hi, (tg[:, 2] >= lo) & (tg[:, 2] < hi))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sessions", nargs="+", help="ANIMAL:YYYYMMDD")
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", default=None, help="csv path (optional)")
    a = ap.parse_args(argv)
    df = pd.DataFrame([r for s in a.sessions for r in session(a.work, *s.split(":"))])
    pd.set_option("display.width", 200)
    print(df.round(3).to_string(index=False))
    if a.out:
        df.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
