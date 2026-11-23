"""Two-tone all-lick peak tongue speed WITHOUT the five-licks-per-trial cap (CC-B, 2026-11-23, Fig 2E all-lick).

The per-trial JSON's peak_velocity_per_lick.vxy_peaks_bylick holds licks 1-5 of each trial only
(tongue_pertrial._extract_peak_velocity_first5, n_lick = 5). This script recomputes the same per-lick peak speed for
EVERY v7-kept lick of the trial in the same [70, 3000] ms window (peak_velocity_detect_win_ms; the window and lick
set of the lick_events parquet behind the Fig 2D xy measure): max over the lick's [rise_start, fall_end] frames of
the 2-D speed hypot(dx, dy) * fps on the v7-cleaned trace with baseline-filled (in-mouth) frames masked, exactly the
production v7 branch, only without the `if j >= 5: break`.

It runs the in-memory pertrial core (build_tongue_visual_bundle_by_animal_date; NO file is written by the pipeline)
with the velocity extractor wrapped so each call also records the uncapped per-lick values. The ILI argument is a
dummy (it only feeds the phase bundle, not the velocity).

Steps (writes NEW files only):
  licks --animal PSxx --stage DIR    per-lick table DIR/speed_alllicks_<animal>.parquet (+ check: licks 1-5 equal the JSON)
  stats [--stage DIR]                session mean over all licks (filtered_v1 trials, >= 5 licks), cells in the merged
                                     502-cell scalar family (replacing the capped speed cells), sheet
                                     pooled_phenotype_stats_c2aligned_v3_ps47d5_alllicks_sessmean.csv
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.dlc_kinematics import tongue_pertrial as TP  # noqa: E402

_REC: list[list[tuple[float, float]]] = []
# --window onsetpeak (2026-11-23 late): max over lick onset (rise start) .. extension peak only, as the six-position
# speed_peak (onset -> 3-D peak). The speed is still differentiated over the whole masked [rise, fall] window (central
# differences at the peak), then the max is taken up to the peak frame (frame of t_ms nearest the lick's peak time).
WINDOW = "risefall"
_orig = TP._extract_peak_velocity_first5


def _uncapped(y_t, x_t, t_ms, fps, *, params, v7_trial_result=None):
    """Production extractor (returned unchanged) + uncapped per-lick record of the v7 branch."""
    out = _orig(y_t, x_t, t_ms, fps, params=params, v7_trial_result=v7_trial_result)
    if v7_trial_result is None:
        raise RuntimeError("expected the v7 pipeline (use_v7_pipeline=True)")
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    lo, hi = tuple(tp["peak_velocity_detect_win_ms"])
    min_finite = int(TP._per_cell_detector(params, "cell36")["min_finite_samples_per_lick"])
    yc, xc, base = v7_trial_result.y_clean, v7_trial_result.x_clean, v7_trial_result.is_baseline_fill_clean
    rec = []
    for kept in v7_trial_result.kept_licks:
        t = float(kept["t_ms"])
        if t < lo or t > hi:
            continue
        rsf, fef = int(kept.get("rise_start_frame", -1)), int(kept.get("fall_end_frame", -1))
        v = np.nan
        if 0 <= rsf <= fef < len(yc):
            yw = np.where(base[rsf:fef + 1], np.nan, yc[rsf:fef + 1].astype(np.float64))
            xw = np.where(base[rsf:fef + 1], np.nan, xc[rsf:fef + 1].astype(np.float64))
            if int(np.count_nonzero(np.isfinite(yw) & np.isfinite(xw))) >= min_finite:
                vxy = np.sqrt((np.gradient(xw) * fps) ** 2 + (np.gradient(yw) * fps) ** 2)
                if WINDOW == "onsetpeak":
                    if len(t_ms) != len(yc):
                        raise RuntimeError("trial t_ms and cleaned trace differ in length")
                    pk = int(np.argmin(np.abs(np.asarray(t_ms, float) - t)))
                    vxy = vxy[: max(0, min(pk, fef) - rsf) + 1]
                if np.isfinite(vxy).any():
                    v = float(np.nanmax(vxy))
        rec.append((t, v))
    _REC.append(rec)
    return out


def licks_one_animal(animal: str, stage: Path) -> None:
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.animals import get_animal
    from stroke_orofacial.manifest import build_manifest
    from scripts.phase_9_1_q13.emit_cohort import enumerate_session_dates

    out = stage / (f"speed_alllicks_{animal}.parquet" if WINDOW == "risefall" else f"speed_onsetpeak_{animal}.parquet")
    if out.exists():
        print("exists", out)
        return
    TP._extract_peak_velocity_first5 = _uncapped
    r = PathResolver()
    info = get_animal(animal)
    rows, checks = [], []
    for d in enumerate_session_dates(animal, r):
        t0 = time.perf_counter()
        man = build_manifest(animal, d, r, info, analysis_context="dlc.kinematics.tongue_pertrial")
        ev = TP._derive_trial_events_from_spout_behavior(animal=animal, date=d, resolver=r, manifest=man)
        _REC.clear()
        try:
            TP.build_tongue_visual_bundle_by_animal_date(animal=animal, date=d, resolver=r, trial_events=ev,
                                                        pre_stroke_median_ili_ms=180.0)
        except Exception as exc:
            print(f"[{animal}/{d}] FAILED {exc!r}", flush=True)
            continue
        if len(_REC) != len(ev):
            print(f"[{animal}/{d}] record count {len(_REC)} != trials {len(ev)}; skipped", flush=True)
            continue
        # check vs the production JSON (licks 1-5)
        jp = r.tongue_pertrial_endpoints_json(animal, d)
        J = json.load(open(jp, encoding="utf-8")) if jp.exists() else None
        jv = {}
        if J is not None:
            jv = {(int(ti), s): v for ti, s, v in zip(J["trial_indices"], J["sides"],
                                                       J["tongue"]["peak_velocity_per_lick"]["vxy_peaks_bylick"])}
        for e, rec in zip(ev, _REC):
            for k, (t, v) in enumerate(rec):
                rows.append((animal, d, int(e.trial_index), e.side, k, t, v))
            if WINDOW == "risefall" and (int(e.trial_index), e.side) in jv:
                a = np.array([v for _, v in rec[:5]] + [np.nan] * (5 - len(rec[:5])), float)
                b = np.array([np.nan if x is None else x for x in jv[(int(e.trial_index), e.side)]], float)
                checks.append(bool(np.allclose(a, b, equal_nan=True, rtol=1e-9, atol=1e-6)))
        print(f"[{animal}/{d}] {len(ev)} trials, {sum(len(x) for x in _REC)} licks, {time.perf_counter() - t0:.1f}s",
              flush=True)
    df = pd.DataFrame(rows, columns=["animal", "date", "trial_idx", "side", "lick_k", "t_ms", "vxy_peak"])
    df.to_parquet(out, index=False)
    print(f"[{animal}] wrote {out}: {len(df)} licks; JSON check (licks 1-5 match) {sum(checks)}/{len(checks)} trials",
          flush=True)


def stats(stage: Path) -> None:
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df
    from scripts.manuscript.c1_sessmean_scalars import MIN_LICKS, kept_trials, run_cells

    r = PathResolver()
    st = r.pipeline_outputs(subdir="stats")
    r3 = st / "results/phenotype_pooled/3_tier"
    tag = "alllicks" if WINDOW == "risefall" else "alllicks_onsetpeak"
    out_csv = r3 / f"pooled_phenotype_stats_c2aligned_v3_ps47d5_{tag}_sessmean.csv"
    sess_csv = st / f"inputs/sessmean_licks/tongue_{tag}_sessmean_vxy_peak_per_session.csv"
    for p in (out_csv, sess_csv):
        if p.exists():
            raise SystemExit(f"refusing to overwrite {p}")
    L = pd.concat([pd.read_parquet(p) for p in sorted(stage.glob(("speed_alllicks" if WINDOW == "risefall" else "speed_onsetpeak") + "_PS*.parquet"))], ignore_index=True)
    L["date"] = pd.to_datetime(L["date"]).dt.date
    t = kept_trials(r, "tongue_median_vxy_peak_per_trial")
    t["date"] = pd.to_datetime(t["date"]).dt.date
    keep = t[["animal", "date", "trial_idx", "side", "epoch_label"]].drop_duplicates()
    L = L.merge(keep, on=["animal", "date", "trial_idx", "side"], how="inner")
    L = L[np.isfinite(L["vxy_peak"])]
    s = L.groupby(["animal", "date", "side"], as_index=False).agg(
        value=("vxy_peak", "mean"), n_licks=("vxy_peak", "size"), n_trials=("trial_idx", "nunique"),
        epoch_label=("epoch_label", "first"))
    s["endpoint"] = f"tongue_{tag}_sessmean_vxy_peak"
    s["passes_min_licks"] = s["n_licks"] >= MIN_LICKS
    s.to_csv(sess_csv, index=False)
    print("sessions", len(s), "excluded", int((~s.passes_min_licks).sum()), "licks", int(s.n_licks.sum()),
          "median/min licks per session x side", s.n_licks.median(), s.n_licks.min())
    cells = run_cells(s[s.passes_min_licks][["animal", "date", "side", "value", "epoch_label", "endpoint"]], "scalar")
    prev = pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_sessmean.csv")
    fam = prev[(prev.family == "scalar") & (prev.endpoint != "tongue_sessmean_vxy_peak")]
    cols = list(cells.columns)
    merged = pd.concat([fam[cols], cells[cols]], ignore_index=True)
    for pcol, adj in (("mwu_session_p", "mwu_session_p_fdr"), ("wa_p", "wa_p_fdr")):
        merged = merged.rename(columns={pcol: "p_value"})
        merged = apply_correction_to_results_df(merged, group_cols=("family",))
        merged = merged.rename(columns={"p_value": pcol, "p_adj": adj}).drop(columns=["reject"])
    merged["headline_test"] = "mwu_session+nested_bootstrap"
    merged["headline_p_fdr"] = merged["mwu_session_p_fdr"]
    merged["headline_sig"] = merged["headline_p_fdr"] < 0.05
    merged["headline_and_bootstrap_sig"] = merged["headline_sig"] & merged["nb_excludes_zero"].astype(bool)
    pd.concat([merged, prev[prev.family != "scalar"]], ignore_index=True).to_csv(out_csv, index=False)
    print("wrote", out_csv, len(merged), "scalar-family cells")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=("licks", "stats"))
    ap.add_argument("--animal")
    ap.add_argument("--stage", type=Path, required=True)
    ap.add_argument("--window", choices=("risefall", "onsetpeak"), default="risefall")
    a = ap.parse_args(argv)
    global WINDOW
    WINDOW = a.window
    a.stage.mkdir(parents=True, exist_ok=True)
    licks_one_animal(a.animal, a.stage) if a.step == "licks" else stats(a.stage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
