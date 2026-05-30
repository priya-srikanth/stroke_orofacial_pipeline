"""Step-1-complete pre-vs-post delta report for the tongue substrate-routing
fix (Priya 2026-05-30, answer 2). Run AFTER the cohort endpoints re-emit.

Compares the pre-fix snapshot (prefix_endpoints_snapshot.csv) against the
NOW-on-disk (post-fix) endpoints JSONs and reports:
  - n_licks delta per (phenotype, epoch, side) cell
  - SessionFilter (min_trials_with_detected_lick=10) pass/fail per
    (animal, date, side), pre vs post
  - predicted cell-loss: (phenotype, epoch, side) cells whose passing-session
    count drops to 0 (severe-acute expected — correct scientific outcome)

Reads only; writes report + CSVs to stats/sensitivity/substrate_fix_pilot/.

Usage:
  python scripts/phase_7e/step1_complete_delta.py
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver


def _post_rows(resolver: PathResolver, snap: pd.DataFrame) -> pd.DataFrame:
    """Read the post-fix JSONs for every (animal, date) in the snapshot."""
    rows: list[dict] = []
    for (animal, date_str), _ in snap.groupby(["animal", "date"]):
        date = dt.date.fromisoformat(date_str)
        jp = resolver.tongue_pertrial_endpoints_json(animal, date)
        if not jp.exists():
            continue
        obj = json.load(open(jp))
        t = obj["tongue"]
        ti = obj["trial_indices"]
        sides = obj["sides"]
        nl = t["n_licks_family"]["n_licks"]
        py = t["phase_aligned_endpoints"]["peak_y_px"]
        for i, tr in enumerate(ti):
            rows.append({
                "animal": animal, "date": date_str,
                "trial_index": int(tr), "side": sides[i],
                "n_licks_post": nl[i] if i < len(nl) else None,
                "peak_y_px_post": (py[i] if i < len(py) and py[i] is not None
                                   else np.nan),
            })
    return pd.DataFrame(rows)


def main() -> int:
    resolver = PathResolver()
    out = (resolver.pipeline_outputs().parent / "stats" / "sensitivity"
           / "substrate_fix_pilot")
    snap = pd.read_csv(out / "prefix_endpoints_snapshot.csv")
    post = _post_rows(resolver, snap)

    thr = int(
        load_defaults()["stats"]["dlc_session_filter"]
        ["dlc_tongue_trajectory_metrics"]["min_trials_with_detected_lick"]
    )

    m = snap.merge(post, on=["animal", "date", "trial_index", "side"], how="left")
    m["n_licks_pre"] = m["n_licks_pre"].fillna(0)
    m["n_licks_post"] = m["n_licks_post"].fillna(0)
    m["has_lick_pre"] = m["n_licks_pre"] >= 1
    m["has_lick_post"] = m["n_licks_post"] >= 1

    # --- SessionFilter per (animal, date, side) ---
    sess = m.groupby(["animal", "phenotype", "epoch_label", "date", "side"]).agg(
        n_trials_with_lick_pre=("has_lick_pre", "sum"),
        n_trials_with_lick_post=("has_lick_post", "sum"),
    ).reset_index()
    sess["pass_pre"] = sess["n_trials_with_lick_pre"] >= thr
    sess["pass_post"] = sess["n_trials_with_lick_post"] >= thr
    sess["flipped_pass_to_fail"] = sess["pass_pre"] & ~sess["pass_post"]
    sess.to_csv(out / "step1_sessionfilter_delta.csv", index=False)

    # --- cell roll-up per (phenotype, epoch, side) ---
    cell = sess.groupby(["phenotype", "epoch_label", "side"]).agg(
        n_sessions=("date", "count"),
        n_pass_pre=("pass_pre", "sum"),
        n_pass_post=("pass_post", "sum"),
    ).reset_index()
    cell["cell_lost"] = (cell["n_pass_pre"] > 0) & (cell["n_pass_post"] == 0)
    cell.to_csv(out / "step1_cell_loss.csv", index=False)

    # --- n_licks delta per (phenotype, epoch, side) ---
    nl_cell = m.groupby(["phenotype", "epoch_label", "side"]).agg(
        n_trials=("trial_index", "count"),
        n_licks_pre_sum=("n_licks_pre", "sum"),
        n_licks_post_sum=("n_licks_post", "sum"),
    ).reset_index()
    nl_cell["n_licks_dropped"] = nl_cell["n_licks_pre_sum"] - nl_cell["n_licks_post_sum"]

    # contra = mouse-R for all L-stroke cohort animals.
    flipped = sess[sess["flipped_pass_to_fail"]]
    lost = cell[cell["cell_lost"]]

    lines = []
    lines.append("# Step-1-complete delta — tongue substrate v7-routing fix\n")
    lines.append(f"SessionFilter threshold: min_trials_with_detected_lick = {thr} "
                 f"(per animal/date/side).\n")
    lines.append(f"Trials compared: {len(m)}. Sessions(side): {len(sess)}.\n")

    lines.append("\n## Predicted cell-loss (phenotype × epoch × side)\n")
    lines.append("Cells whose passing-session count drops to 0 (contra = side R):\n")
    if len(lost):
        lines.append("| phenotype | epoch | side | n_sessions | pass_pre | pass_post |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in lost.iterrows():
            lines.append(f"| {r.phenotype} | {r.epoch_label} | {r.side} | "
                         f"{r.n_sessions} | {r.n_pass_pre} | {r.n_pass_post} |")
    else:
        lines.append("_None._")
    lines.append("")

    lines.append("\n## Sessions flipping SessionFilter PASS → FAIL\n")
    lines.append(f"Total: **{len(flipped)}** (animal,date,side) sessions.\n")
    if len(flipped):
        lines.append("| animal | phenotype | epoch | date | side | n_lick_pre | n_lick_post |")
        lines.append("|---|---|---|---|---|---|---|")
        for _, r in flipped.iterrows():
            lines.append(f"| {r.animal} | {r.phenotype} | {r.epoch_label} | {r.date} "
                         f"| {r.side} | {int(r.n_trials_with_lick_pre)} | "
                         f"{int(r.n_trials_with_lick_post)} |")
    lines.append("")

    lines.append("\n## n_licks delta per (phenotype, epoch, side)\n")
    lines.append("| phenotype | epoch | side | n_trials | n_licks_pre | n_licks_post | dropped |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in nl_cell.sort_values(["phenotype", "epoch_label", "side"]).iterrows():
        lines.append(f"| {r.phenotype} | {r.epoch_label} | {r.side} | {int(r.n_trials)} "
                     f"| {int(r.n_licks_pre_sum)} | {int(r.n_licks_post_sum)} "
                     f"| {int(r.n_licks_dropped)} |")
    lines.append("")
    lines.append("CSVs: step1_sessionfilter_delta.csv, step1_cell_loss.csv\n")

    (out / "step1_complete_delta_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("WROTE", out / "step1_complete_delta_report.md")
    print(f"cell-loss cells: {len(lost)}; sessions PASS->FAIL: {len(flipped)}")
    for _, r in lost.iterrows():
        print(f"  CELL-LOST: {r.phenotype} {r.epoch_label} side={r.side} "
              f"(pass {r.n_pass_pre}->{r.n_pass_post} of {r.n_sessions})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
