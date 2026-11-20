"""Two-tone cohort (#1-#8 = PS46-PS55): per-trial and per-session tables for the engagement / treadmill / running
review (PROMPT_engagement_movement_both_cohorts.md items 8, 10a, 11c (treadmill part), 11d). Review output only.

Reads (read-only), via the stroke_orofacial_pipeline checkout on PYTHONPATH (worktree ps47-chronic-day5):
  * sessions  = `visual_gate.iter_cohort_a_sessions` (the cohort-1 scalar-family session set);
  * licks / tones (mouse frame) = `visual_gate.load_session_plot_data` (the same loader the scalar family uses);
  * epochs = `recovery_epochs.assign_epoch_label` with that checkout's configs/animals.yaml (PS47 chronic >= day 5);
  * treadmill = spout_behavior/treadmill_signals_preprocessed/<animal>/<date>.npz `Treadmill_smoothed`
    (pipeline `process_treadmill_signal`: (V - 1.2588 V) / 0.382 V*s/rot * 29.25 mm/rot, Gaussian sigma 0.15 s,
    1 kHz; + = forward, - = backward; the SAME constants as the six-position rig, widefield configs/defaults.yaml
    segmentation.treadmill). Multi-half sessions (PS48 2025-03-14): halves a + b concatenated, as the merged licks.
  * per-trial first-lick angle = dlc_kinematics/per_trial/tongue/<animal>/<date>.json phase_aligned_endpoints.

Definitions (six-position values, widefield configs/defaults.yaml segmentation + behavior_states, cue at 0):
  push         = backward speed > 0.5 mm/s at any sample in the cue window -0.25..0.75 s; control = -2..-1 s;
                 push_peak = max backward speed in the cue window; push_latency = first supra-threshold sample.
  walk_cue     = fraction of the 2..3.5 s window with forward speed > 3 mm/s (behavior_states: fraction of window time,
                 averaged over trials); walk_control = same in -2..-1 s; walk_cue_any = any sample > 3 mm/s.
  running bouts= forward speed > 3 mm/s, gaps < 0.3 s filled, bouts >= 2 s kept (`bouts.find_running_bouts` with the
                 six-position thresholds; the two-tone pipeline's own running_bouts use 5 mm/s).
  response     = any spout lick (DAQ) in cue + 70 ms .. cue + 8 s (the cohort-1 response window).
  first-lick accuracy / correct licks = the pipeline's own functions (`compute_first_lick_correct`, None -> 0 =
                 first_lick_accuracy_all; correct / incorrect licks in the response window = *_rw).
  ITI          = previous cue + 8 s .. this cue - 2 s (first trial: cue - 10 s .. cue - 2 s).
  lick working period = first .. last trial with a response lick (the two-tone analog of the six-position
                 camera-lick working period; sessions have a fixed 96 trials, so this trims only a quit tail).

Writes <out>/data/trials.parquet, sessions_running.parquet, traces.npz. Refuses to overwrite.
Usage: python c1_extract_sessions.py <out_dir> [--jobs 8] [--only PS46_20250310]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

GRADE = {'PS47': 'mild', 'PS48': 'mild', 'PS49': 'mild', 'PS50': 'mild',
         'PS46': 'moderate', 'PS51': 'moderate', 'PS54': 'severe', 'PS55': 'severe'}
PUSH_THR, CUE_W, CTRL_W = 0.5, (-0.25, 0.75), (-2.0, -1.0)
WALK_THR, WALK_W = 3.0, (2.0, 3.5)
RUN = {'thresh_speed': 3.0, 'max_gap_duration': 0.3, 'min_duration': 2.0}
STILL_THR = 1.0
RESP_W = (0.07, 8.0)
PRECUE_W = (-2.0, 0.0)
TR_W = (-2.0, 4.5)            # stored cue-aligned trace window (s)
TR_DS = 40                    # 1 kHz -> 25 Hz for the stored traces
SPOUT = 'M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/spout_behavior'


def sessions():
    from stroke_orofacial.animals import load_animals
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.spout_behavior.visual_gate import iter_cohort_a_sessions
    r = PathResolver()
    return [(a, d) for a in sorted(GRADE) for d in iter_cohort_a_sessions(a, r)], load_animals()


def load_treadmill(animal, date):
    p = Path(SPOUT) / 'treadmill_signals_preprocessed' / animal
    f = p / f'{date}.npz'
    if f.exists():
        return np.load(f)['Treadmill_smoothed'].astype(float)
    halves = sorted(p.glob(f'{date}*/{date}?.npz'))           # Pattern A multi-half: <date>ab/<date>a.npz, b.npz
    if halves:
        return np.concatenate([np.load(h)['Treadmill_smoothed'].astype(float) for h in halves])
    return None


def bouts(mask):
    """(starts, stops) sample indices of True runs."""
    d = np.diff(np.r_[0, mask.astype(np.int8), 0])
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def angles(animal, date):
    from stroke_orofacial.paths import PathResolver
    p = PathResolver().tongue_pertrial_endpoints_json(animal=animal, date=datetime.date(int(date[:4]), int(date[4:6]),
                                                                                       int(date[6:])))
    if not Path(p).exists():
        return None
    d = json.load(open(p))
    v = (d.get('tongue', {}).get('phase_aligned_endpoints') or {}).get('peak_angle_deg')
    if v is None or len(v) != len(d['trial_indices']):
        return None
    return dict(zip(d['trial_indices'], zip(d['sides'], [np.nan if x is None else float(x) for x in v])))


def process(item):
    animal, date, rel, epoch = item
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.spout_behavior.bouts import find_running_bouts
    from stroke_orofacial.spout_behavior.visual_gate import (compute_first_lick_correct, compute_trial_lick_delays,
                                                             load_session_plot_data)
    r = PathResolver()
    sd = load_session_plot_data(animal, date, r)
    fs = float(sd.sample_rate)
    tL, tR = np.asarray(sd.tones_idx['Tone_L'], int), np.asarray(sd.tones_idx['Tone_R'], int)
    lL, lR = np.sort(np.asarray(sd.lick_idx['Lick_L'], int)), np.sort(np.asarray(sd.lick_idx['Lick_R'], int))
    delays = compute_trial_lick_delays(sd, (1.0, 8.0))           # window_around_tones (defaults.yaml)
    flc = compute_first_lick_correct(delays)
    cue = np.r_[tL, tR]
    side = np.array(['L'] * len(tL) + ['R'] * len(tR))
    k_in_side = np.r_[np.arange(len(tL)), np.arange(len(tR))]
    o = np.argsort(cue, kind='stable')
    cue, side, k_in_side = cue[o], side[o], k_in_side[o]
    cs = cue / fs
    allk = np.sort(np.r_[lL, lR]) / fs
    LL, LR = lL / fs, lR / fs
    v = load_treadmill(animal, date)
    n_tm = 0 if v is None else len(v)
    run_mask = find_running_bouts(v, fs, RUN) if v is not None else None
    rs, rp = bouts(run_mask) if v is not None else (np.array([]), np.array([]))
    ang = angles(animal, date)

    def win(a, b):
        i0, i1 = int(round(a * fs)), int(round(b * fs))
        if v is None or i0 < 0 or i1 > n_tm:
            return None
        return v[i0:i1]

    def run_frac(a, b):
        if v is None or not (np.isfinite(a) and np.isfinite(b)) or b <= a:
            return np.nan
        i0, i1 = max(int(a * fs), 0), min(int(b * fs), n_tm)
        return float(run_mask[i0:i1].mean()) if i1 > i0 else np.nan

    rows, trF, trB = [], [], []
    nb = int(round((TR_W[1] - TR_W[0]) * fs))
    for t in range(len(cs)):
        c, s = cs[t], side[t]
        other = LR if s == 'L' else LL
        own = LL if s == 'L' else LR
        rel_any = allk[(allk >= c + RESP_W[0]) & (allk <= c + RESP_W[1])] - c
        own_rw = own[(own >= c + RESP_W[0]) & (own <= c + RESP_W[1])] - c
        oth_rw = other[(other >= c + RESP_W[0]) & (other <= c + RESP_W[1])] - c
        f = flc[s][int(k_in_side[t])]
        prev_c = cs[t - 1] if t else np.nan
        iti0 = prev_c + RESP_W[1] if t else c - 10.0
        iti1 = c + PRECUE_W[0]
        row = dict(animal=animal, date=date, label=f'{animal}_{date}', rel_day=rel, epoch=epoch,
                   grade=GRADE[animal], trial=t, side=s, cue_s=c, t_min=(c - cs[0]) / 60.0,
                   prev_side=side[t - 1] if t else None,
                   responded=bool(len(rel_any)), lat_any=float(rel_any[0]) if len(rel_any) else np.nan,
                   first_lick_side=(None if not len(rel_any) else
                                    (s if (len(own_rw) and (not len(oth_rw) or own_rw[0] <= oth_rw[0])) else
                                     ('R' if s == 'L' else 'L'))),
                   first_correct=np.nan if f is None else float(f), first_correct_all=0.0 if f is None else float(f),
                   n_correct_rw=len(own_rw), n_incorrect_rw=len(oth_rw),
                   lat_correct=float(own_rw[0]) if len(own_rw) else np.nan,
                   precue_lick=int(np.any((allk >= c + PRECUE_W[0]) & (allk < c))),
                   iti_lick=int(np.any((allk >= iti0) & (allk < iti1))) if iti1 > iti0 else -1,
                   iti_lick_rate=(float(np.sum((allk >= iti0) & (allk < iti1)) / (iti1 - iti0))
                                  if iti1 > iti0 else np.nan),
                   run_frac_precue=run_frac(c + PRECUE_W[0], c), run_frac_iti=run_frac(iti0, iti1))
        if ang is not None and t in ang:
            row['angle_side_json'], row['peak_angle_deg'] = ang[t]
        bc, bk = win(c + CUE_W[0], c + CUE_W[1]), win(c + CTRL_W[0], c + CTRL_W[1])
        fw = win(c + WALK_W[0], c + WALK_W[1])
        if bc is not None and bk is not None and fw is not None:
            back_c, back_k = np.maximum(-bc, 0), np.maximum(-bk, 0)
            above = np.flatnonzero(back_c > PUSH_THR)
            row.update(push=bool(len(above)), push_control=bool((back_k > PUSH_THR).any()),
                       push_peak=float(back_c.max()), push_latency_s=CUE_W[0] + above[0] / fs if len(above) else np.nan,
                       walk_cue=float(np.mean(fw > WALK_THR)), walk_control=float(np.mean(bk > WALK_THR)),
                       walk_cue_any=bool((fw > WALK_THR).any()), walk_control_any=bool((bk > WALK_THR).any()))
        w = win(c + TR_W[0], c + TR_W[1])
        if w is not None and len(w) == nb:
            trF.append(np.maximum(w, 0)[::TR_DS]); trB.append(np.maximum(-w, 0)[::TR_DS])
        else:
            trF.append(np.full(len(range(0, nb, TR_DS)), np.nan)); trB.append(np.full(len(range(0, nb, TR_DS)), np.nan))
        rows.append(row)
    T = pd.DataFrame(rows)
    resp = np.flatnonzero(T.responded.to_numpy())
    T['lick_period'] = False
    if len(resp):
        T.loc[resp[0]:resp[-1], 'lick_period'] = True
    span_min = (cs[-1] - cs[0]) / 60.0
    # ---- session-level running / stillness (whole span from the first cue; ITI-only) at several spans
    S = []
    if v is not None:
        speed_f = np.maximum(v, 0)
        t_end_all = min(cs[-1] + RESP_W[1], n_tm / fs)
        trial_mask = np.zeros(n_tm, bool)
        for c in cs:
            trial_mask[max(int((c + PRECUE_W[0]) * fs), 0):min(int((c + RESP_W[1]) * fs), n_tm)] = True
        for span_name, t_end in (('all', t_end_all),) + tuple((f'first{m}', min(cs[0] + m * 60.0, t_end_all))
                                                             for m in (40, 45, 48)):
            i0, i1 = int(cs[0] * fs), int(t_end * fs)
            for scope in ('session', 'iti'):
                m = np.zeros(n_tm, bool); m[i0:i1] = True
                if scope == 'iti':
                    m &= ~trial_mask
                dur_min = m.sum() / fs / 60.0
                on = rs[(rs >= i0) & (rs < i1)]
                on_iti = on[~trial_mask[on]] if scope == 'iti' else on
                bdur = (rp - rs)[np.isin(rs, on_iti)] / fs
                inb = run_mask & m
                S.append(dict(animal=animal, date=date, label=f'{animal}_{date}', rel_day=rel, epoch=epoch,
                              grade=GRADE[animal], span=span_name, scope=scope, minutes=dur_min,
                              mean_fwd_speed=float(speed_f[m].mean()),
                              mean_speed_in_bouts=float(v[inb].mean()) if inb.any() else np.nan,
                              bouts_per_min=len(on_iti) / dur_min if dur_min > 0 else np.nan,
                              frac_fwd_gt3=float((v[m] > WALK_THR).mean()), frac_in_bouts=float(run_mask[m].mean()),
                              bout_dur_median_s=float(np.median(bdur)) if len(bdur) else np.nan,
                              still_frac=float((np.abs(v[m]) < STILL_THR).mean()),
                              back_frac_gt05=float((v[m] < -PUSH_THR).mean())))
    meta = dict(label=f'{animal}_{date}', n_trials=len(T), span_min=span_min, n_tm=n_tm,
                tm_covers=bool(v is not None and n_tm / fs >= cs[-1] + 4.5),
                n_lick_samples_sd=int(getattr(sd, 'n_samples_session', -1) or -1),
                has_angle=ang is not None)
    return T, pd.DataFrame(S), np.array(trF), np.array(trB), meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    od = a.out / 'data'
    outs = [od / 'trials.parquet', od / 'sessions_running.parquet', od / 'traces.npz', od / 'extract_meta.csv']
    if a.only is None and any(p.exists() for p in outs):
        sys.exit('refusing to overwrite: ' + ', '.join(str(p) for p in outs if p.exists()))
    from stroke_orofacial.stats.recovery_epochs import assign_epoch_label
    ses, amap = sessions()
    items = []
    for an, d in ses:
        dd = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:]))
        rel = int(amap[an].day_relative_to_stroke(dd))
        ep = assign_epoch_label(rel, amap[an])
        if a.only and f'{an}_{d}' != a.only:
            continue
        items.append((an, d, rel, ep))
    print(len(items), 'sessions', flush=True)
    if a.jobs > 1 and len(items) > 1:
        with Pool(a.jobs) as p:
            res = p.map(process, items, chunksize=1)
    else:
        res = [process(i) for i in items]
    T = pd.concat([r[0] for r in res], ignore_index=True)
    S = pd.concat([r[1] for r in res], ignore_index=True)
    M = pd.DataFrame([r[4] for r in res])
    if a.only:
        print(T.head(12).to_string()); print(S.to_string()); print(M.to_string())
        return
    od.mkdir(parents=True, exist_ok=True)
    T.to_parquet(outs[0]); S.to_parquet(outs[1]); M.to_csv(outs[3], index=False)
    labs = np.concatenate([[f'{r[4]["label"]}'] * len(r[0]) for r in res])
    np.savez_compressed(outs[2], fwd=np.vstack([r[2] for r in res]).astype(np.float32),
                        back=np.vstack([r[3] for r in res]).astype(np.float32), label=labs,
                        trial=np.concatenate([r[0].trial.to_numpy() for r in res]),
                        t=TR_W[0] + np.arange(0, int(round((TR_W[1] - TR_W[0]) * 1000)), TR_DS) / 1000.0)
    print('written', od, len(T), 'trials', T.label.nunique(), 'sessions', flush=True)


if __name__ == '__main__':
    main()
