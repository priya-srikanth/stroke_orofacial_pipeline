"""Two-tone cohort (#1-#8 = PS46-PS55): recovery mechanics of lick aim, the 2D counterparts of the six-position analyses
in widefield_pipeline (scripts/within_lick_correction.py, learned_compensation.py T1, lick_correction.py; Priya
2026-11-21: "ok to build and do the parallel two-tone analyses"). Decisions: docs/DECISIONS.md 2026-11-21.

  1  WITHIN-LICK CORRECTION + CORRECTIVE SUBMOVEMENTS (CSMs), cued licks 70 ms .. 3 s after the cue (the window of the
     pipeline's v7 lick events), all orders and outcomes, by cue side.
       theta_L  launch direction: Savitzky-Golay(5, 2) displacement from the first out-of-mouth frame to frame 3
                (12 ms), degrees(arcsin(lat / |d|)); needs the run to start within 2 frames of the lick's rise start and
                the extension peak >= 4 frames after it (widefield N_LAUNCH, ONSET_TOL, MIN_PEAK_FR).
       theta_E  endpoint: arcsin(lat / r) of the tongue tip at the extension peak (max distance from the mouth origin).
                Not the pipeline's per-lick peak_angle_deg: that angle is eye-referenced and taken at the v7 peak frame,
                whereas the launch angle needs a mouth-origin reference, so theta_L and theta_E share one origin and
                one frame of reference, as in the widefield 3D analysis (comparison in DECISIONS 2026-11-21).
       lat      lateral tongue position from the mouth origin, + = CONTRALESIONAL: the front camera's x is mouse-left
                positive, so -x is mouse-right positive, recoded to contralesional-positive with the animal's
                stroke_laterality (stroke_orofacial.ipsi_contra_recoding; all eight animals are left-lesioned).
       e_L, e_E angle minus the animal's pre-stroke mean of the same angle on HIT licks (contact on the cued spout) of
                the same cue side (- = ipsilesional of the pre-stroke hit pattern); corr = e_E - e_L (+ = endpoint more
                contralesional than launch; toward the target on contralesional-cue trials).
       CSM      sum over the outward / inward phases (split at the extension peak) of max(0, n speed peaks - 1), peak
                prominence >= theta_s; speed from SG(5, 2) derivative of the 2D track (px/s). theta_s = the smallest
                grid value at which a noise surrogate (SG(9, 3) track + Gaussian noise with the session's residual SD)
                gains a CSM over the smooth surrogate on <= 5 % of pre-stroke licks (widefield calibrate()). Scored on
                fully tracked licks (onset and offset within 2 frames of the lick's rise / fall, >= MIN_CSM_FR frames).
     GATE (before any post-stroke CSM number): pre-stroke real CSM share must exceed the surrogate false rate.
  2  WITHIN- vs BETWEEN-SESSION RECOVERY (T1): contralesional-cue FIRST-lick e_E (primary), e_L, and first-lick accuracy
     in early / middle / late thirds of each session; mixed models (statsmodels MixedLM, animal groups, session
     variance component): within-session y ~ x * post (x = trial position 0..1 in the session), overnight pairs
     (late third of day d vs early third of day d + 1) y ~ second * post; post = acute + subacute sessions.
  3  ACROSS-LICK CORRECTION (lick_correction.py): pairs k -> k + 1 within a trial (both scored, peak-to-peak <= 300 ms),
     e_k = theta_E,k - target (pre hit mean), dang = theta_E,k+1 - theta_E,k; toward = sign(-e_k) * dang; MISS-minus-HIT
     contrast at matched error: mean over 5-deg |e_k| bins of [toward | miss] - [toward | hit] (xcorr), per session.
  4  (SECONDARY) SPONTANEOUS LICKS in the non-reward blocks (inter-cue gaps > 60 s): lick-sensor contacts from
     last cue + B to next cue - 2 s (B chosen from the pre-stroke lick-rate decay after the block's last cue, >= 8 s);
     camera theta_E of the contact lick (max reach within -48 .. +24 ms of the contact); first lick of each bout
     (gap >= 1 s) primary. D = theta_E - the animal's pre-stroke spontaneous mean to the same spout; compared with
     cued HIT first-lick e_E to the same spout.

Cue and contact times map to camera frames with the pipeline's own wavesurfer -> frame lookup
(dlc_spatial.tone_aligned.ws_samples_to_frame_indices: round(sig_camIdx__idx_ws[ws_sample])), the same mapping that
anchors the lick events' rise / fall times, so lick boundaries land on the frames the lick events were measured on.

Statistics: the two-tone rule (c1_stats.run_family: session change from own pre, session MWU + nested bootstrap, BH-FDR
within each family, star = q < .05 AND CI excludes 0), one family per analysis; per-animal sign counts.
Inputs (read-only): <outputs>/dlc_kinematics/{lick_events,cleaned_traces}/tongue, cam2 alignment templates, the
spout_behavior licks (visual_gate.load_session_plot_data), configs/animals.yaml (stroke_laterality), and the review
trials table <c1_dir>/data/trials.parquet (sessions, epochs with PS47 chronic >= day 5, grades, first-lick accuracy).
Usage (PYTHONPATH=src; sibling modules are found via sys.path):
  python c1_recovery_mechanics.py extract <out> <c1_dir> [--jobs 6] [--only LABEL]
  python c1_recovery_mechanics.py summarize <out> <c1_dir>
  python c1_recovery_mechanics.py t1_by_grade <out> <c1_dir>
  python c1_recovery_mechanics.py plot <out> [--daycourse-grid {1x4,2x2}]
  python c1_recovery_mechanics.py daycourse <out> --daycourse-grid 2x2      (day course only, e.g. after plot)
Outputs only under <out>; every writer refuses to overwrite.
"""
from __future__ import annotations

import argparse
import datetime
import sys
import zlib
from functools import partial
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))                               # sibling summary module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'engagement_movement'))  # c1_stats

N_LAUNCH, MIN_PEAK_FR, ONSET_TOL_FR, MIN_CSM_FR = 3, 4, 2, 10
GRID = list(range(200, 4001, 100))         # px/s prominence grid
FALSE_MAX = 0.05
WIN_MS = (70.0, 3000.0)
CONTACT_TOL_FR = 2
BLOCK_GAP_S = 60.0
BOUT_GAP_S = 1.0
EXTRACT_FILES = ('cued_licks.pkl', 'spont_licks.pkl', 'block_decay.npz', 'extract_status.csv')


def frame_dt() -> float:
    """Camera frame interval in s, from configs/defaults.yaml alignment.fps_cam (250 Hz)."""
    from stroke_orofacial.config_loader import load_defaults
    return 1.0 / float(load_defaults()['alignment']['fps_cam'])


def outputs_dir(subdir: str) -> Path:
    """A pipeline-outputs subdirectory via PathResolver (repo rule: no absolute paths in source); resolved at call time,
    so importing this module needs no server mount."""
    from stroke_orofacial.paths import PathResolver
    return Path(PathResolver().pipeline_outputs(subdir=subdir))


def contra_sign(animal: str) -> float:
    """+1 if mouse-right is contralesional for this animal, -1 if mouse-left is (from animals.yaml stroke_laterality)."""
    from stroke_orofacial.animals import load_animals
    from stroke_orofacial.ipsi_contra_recoding import signed_value_to_ipsi_contra
    return signed_value_to_ipsi_contra(1.0, load_animals()[animal].stroke_laterality)


def _runs(mask):
    d = np.diff(np.r_[0, mask.astype(np.int8), 0])
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _peaks(x, k):
    from scipy.signal import find_peaks, peak_prominences
    xp = np.r_[0.0, x, 0.0]
    pk, _ = find_peaks(xp)
    if not len(pk):
        return (), ()
    pr = peak_prominences(xp, pk)[0]
    idx = pk - 1
    return tuple(np.round(pr[idx < k], 1)), tuple(np.round(pr[idx > k], 1))


def csm_count(pre, post, th):
    """Corrective submovements in one lick: extra speed peaks (prominence >= th) beyond one per phase (out / back)."""
    return max(0, sum(p >= th for p in pre) - 1) + max(0, sum(p >= th for p in post) - 1)


def process(label, trials_path: Path):
    """Per-lick launch / endpoint angles, CSM speed-peak prominences (real and noise surrogates), contacts, and the
    session's spontaneous (non-reward block) contact licks and post-block lick-rate decay. Returns a dict with status."""
    from scipy.signal import savgol_filter
    from stroke_orofacial.dlc_spatial.tone_aligned import ws_samples_to_frame_indices
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.spout_behavior.visual_gate import load_session_plot_data
    dt = frame_dt()
    kin = outputs_dir('dlc_kinematics')
    an, d = label.split('_')
    T = pd.read_parquet(trials_path, filters=[('label', '==', label)]).sort_values('trial')
    E_f = kin / 'lick_events/tongue' / an / f'{d}.parquet'
    C_f = kin / 'cleaned_traces/tongue' / an / f'{d}.parquet'
    if not (E_f.exists() and C_f.exists()):
        return {'label': label, 'status': 'missing kinematics'}
    r = PathResolver()
    dd = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:]))
    ap = r.alignment_template_for_reading(an, dd, cam='cam2')
    if not Path(ap).exists():
        return {'label': label, 'status': 'missing template'}
    sd = load_session_plot_data(an, d, r)
    fs = float(sd.sample_rate)
    tz = np.load(ap)
    tf = tz['sig_wsIdx__idx_cam'].astype(float) / fs          # frame -> wavesurfer time (s), for contact windows
    lut = tz['sig_camIdx__idx_ws']                             # wavesurfer sample -> frame (the pipeline's mapping)
    cue_ws = np.sort(np.r_[sd.tones_idx['Tone_L'], sd.tones_idx['Tone_R']]).astype(int)
    cues = cue_ws / fs
    if len(cues) != len(T) or np.abs(cues - T.cue_s.to_numpy()).max() > 0.002:
        return {'label': label, 'status': 'cue mismatch'}
    LLw = np.sort(np.asarray(sd.lick_idx['Lick_L'], int))
    LRw = np.sort(np.asarray(sd.lick_idx['Lick_R'], int))
    LL, LR = LLw / fs, LRw / fs
    C = pd.read_parquet(C_f, columns=['x_final', 'y_final', 'is_baseline_fill'])
    X = C.x_final.to_numpy(float)
    Y = C.y_final.to_numpy(float)
    out_m = ~C.is_baseline_fill.to_numpy(bool) & np.isfinite(X) & np.isfinite(Y)
    n_fr = len(X)
    sgn = contra_sign(an)
    E = pd.read_parquet(E_f, columns=['trial', 'side', 'lick_idx', 't_ms', 'rise_start_ms', 'fall_end_ms'])
    E = E[(E.t_ms >= WIN_MS[0]) & (E.t_ms <= WIN_MS[1]) & (E.trial < len(T))].sort_values(['trial', 't_ms'])
    f0 = ws_samples_to_frame_indices(cue_ws, lut, n_fr)       # -1 = cue outside the video
    rng = np.random.default_rng(zlib.crc32(label.encode()))

    def track(a, b):
        """longest out-of-mouth run inside frames a..b (inclusive) -> (i0, P[n, 2] with lat + = contralesional)."""
        a, b = max(a, 0), min(b, n_fr - 1)
        if b - a < 2:
            return None
        best = max(_runs(out_m[a:b + 1]), key=lambda z: z[1] - z[0], default=None)
        if best is None or best[1] - best[0] < 3:
            return None
        i0, i1 = a + best[0], a + best[1]
        # -x is mouse-right positive (front camera x is mouse-left positive); sgn recodes to contralesional-positive
        return i0, np.c_[-sgn * X[i0:i1], Y[i0:i1]]

    def contact(t0, t1):
        cl = LL[(LL >= t0) & (LL <= t1)]
        cr = LR[(LR >= t0) & (LR <= t1)]
        return len(cl) > 0, len(cr) > 0

    # session noise SD: SG(7, 2) residual on fully tracked cued licks (interior frames)
    items, res = [], []
    for e in E.itertuples():
        base = f0[e.trial]
        if base < 0 or not (np.isfinite(e.rise_start_ms) and np.isfinite(e.fall_end_ms)):
            continue
        fr = base + int(round(e.rise_start_ms / 1000.0 / dt))
        fe = base + int(round(e.fall_end_ms / 1000.0 / dt))
        tr = track(fr - ONSET_TOL_FR, fe + ONSET_TOL_FR)
        if tr is None:
            continue
        i0, P = tr
        items.append((e, fr, fe, i0, P))
        if len(P) >= 9 and i0 - fr <= ONSET_TOL_FR and fe - (i0 + len(P) - 1) <= ONSET_TOL_FR:
            res.append((P - savgol_filter(P, 7, 2, axis=0))[3:-3])
    sdn = np.concatenate(res).std(0) / np.sqrt(1 - 1 / 3) if res else np.full(2, np.nan)
    rows = []
    for e, fr, fe, i0, P in items:
        n = len(P)
        rr = np.linalg.norm(P, axis=1)
        k = int(np.argmax(rr))
        t_lo, t_hi = tf[max(fr - CONTACT_TOL_FR, 0)], tf[min(fe + CONTACT_TOL_FR, n_fr - 1)]
        cL, cR = contact(t_lo, t_hi) if np.isfinite(t_lo) and np.isfinite(t_hi) else (False, False)
        onset_ok = (i0 - fr) <= ONSET_TOL_FR
        full_ok = bool(onset_ok and (fe - (i0 + n - 1)) <= ONSET_TOL_FR and n >= MIN_CSM_FR)
        row = dict(label=label, trial=int(e.trial), cue=e.side, lick_idx=int(e.lick_idx), t_ms=float(e.t_ms),
                   contact_L=cL, contact_R=cR, hit=bool(cL if e.side == 'L' else cR), n_run=n, k=k,
                   onset_ok=bool(onset_ok), full_ok=full_ok, reach=float(rr[k]),
                   theta_E=float(np.degrees(np.arcsin(np.clip(P[k, 0] / rr[k], -1, 1)))) if rr[k] > 0 else np.nan)
        if n >= 5:
            Ps = savgol_filter(P, 5, 2, axis=0)
            V = savgol_filter(P, 5, 2, deriv=1, axis=0) / dt
            sp = np.linalg.norm(V, axis=1)
            row['speed_peak'] = float(sp.max())
            if onset_ok and k >= MIN_PEAK_FR:
                dv = Ps[N_LAUNCH] - Ps[0]
                nd = np.linalg.norm(dv)
                row['theta_L'] = float(np.degrees(np.arcsin(np.clip(dv[0] / nd, -1, 1)))) if nd > 1.0 else np.nan
            if full_ok:
                row['pk_sp'] = _peaks(sp, k)
                if np.isfinite(sdn).all():
                    T9 = savgol_filter(P, 9, 3, axis=0)
                    Tn = T9 + rng.normal(0, 1, T9.shape) * sdn
                    for nm, Z in (('sm', T9), ('nz', Tn)):
                        Vz = savgol_filter(Z, 5, 2, deriv=1, axis=0) / dt
                        row[f'sur_{nm}_sp'] = _peaks(np.linalg.norm(Vz, axis=1), k)
        rows.append(row)
    L = pd.DataFrame(rows)
    # ---- spontaneous licks in the non-reward blocks (item 4): every lick-sensor contact in a block gap
    sp_rows = []
    gaps = np.flatnonzero(np.diff(cues) > BLOCK_GAP_S)
    for side, arr, arr_w in (('L', LL, LLw), ('R', LR, LRw)):
        fcs = ws_samples_to_frame_indices(arr_w, lut, n_fr)
        for gi in gaps:
            a, b = cues[gi], cues[gi + 1]
            for j in np.flatnonzero((arr > a) & (arr < b)):
                fc, tc = int(fcs[j]), float(arr[j])
                if fc < 0:
                    continue
                tr = track(fc - 12, fc + 6)
                if tr is None:
                    continue
                i0, P = tr
                rr = np.linalg.norm(P, axis=1)
                k = int(np.argmax(rr))
                sp_rows.append(dict(label=label, spout=side, t_s=tc, since_cue=float(tc - a),
                                    to_cue=float(b - tc), gap_i=int(gi), reach=float(rr[k]),
                                    theta_E=float(np.degrees(np.arcsin(np.clip(P[k, 0] / rr[k], -1, 1))))
                                    if rr[k] > 0 else np.nan))
    S = pd.DataFrame(sp_rows)
    if len(S):
        allc = np.sort(np.r_[LL, LR])
        S = S.sort_values('t_s')
        prev = np.r_[-np.inf, allc][np.searchsorted(allc, S.t_s.to_numpy(), side='left')]
        S['bout_first'] = (S.t_s.to_numpy() - prev) >= BOUT_GAP_S
    # all-contact rate after each block's last cue (for choosing B): counts in 1-s bins 0..60 s
    rate = np.zeros(60)
    for gi in gaps:
        h, _ = np.histogram(np.r_[LL, LR] - cues[gi], bins=np.arange(0, 61))
        rate += h
    return {'label': label, 'status': 'ok', 'licks': L, 'spont': S, 'decay': rate, 'n_gaps': len(gaps),
            'noise_sd': sdn.tolist()}


def cmd_extract(out: Path, c1_dir: Path, jobs: int, only: str | None):
    """Run process() over every session of the trials table; write data/{cued_licks.pkl, spont_licks.pkl,
    block_decay.npz, extract_status.csv}. With --only, prints one session and writes nothing."""
    od = out / 'data'
    trials = c1_dir / 'data/trials.parquet'
    if only is None:
        existing = [od / f for f in EXTRACT_FILES if (od / f).exists()]
        if existing:
            sys.exit(f'refusing to overwrite {existing}')
    labs = [only] if only else sorted(pd.read_parquet(trials, columns=['label']).label.unique())
    fn = partial(process, trials_path=trials)
    if jobs > 1 and len(labs) > 1:
        with Pool(jobs) as p:
            R = p.map(fn, labs, chunksize=1)
    else:
        R = [fn(x) for x in labs]
    st = pd.DataFrame([{'label': r['label'], 'status': r['status'], 'n_licks': len(r.get('licks', [])),
                        'n_spont': len(r.get('spont', [])), 'n_gaps': r.get('n_gaps', 0),
                        'noise_sd': r.get('noise_sd')} for r in R])
    print(st.status.value_counts().to_dict(), flush=True)
    if only:
        print(st.to_string())
        print(R[0]['licks'].head(20).to_string())
        return
    ok = [r for r in R if r['status'] == 'ok']
    od.mkdir(parents=True, exist_ok=True)
    pd.concat([r['licks'] for r in ok], ignore_index=True).to_pickle(od / 'cued_licks.pkl')
    pd.concat([r['spont'] for r in ok if len(r['spont'])], ignore_index=True).to_pickle(od / 'spont_licks.pkl')
    np.savez(od / 'block_decay.npz', labels=np.array([r['label'] for r in ok]),
             rate=np.vstack([r['decay'] for r in ok]), n_gaps=np.array([r['n_gaps'] for r in ok]))
    st.to_csv(od / 'extract_status.csv', index=False)


def main(argv=None):
    """Command-line entry point (see the module docstring)."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['extract', 'summarize', 't1_by_grade', 'plot', 'daycourse'])
    ap.add_argument('out', type=Path)
    ap.add_argument('c1_dir', type=Path, nargs='?', help='review c1 folder holding data/trials.parquet')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--only', default=None)
    ap.add_argument('--daycourse-grid', choices=['1x4', '2x2'], default='1x4')
    a = ap.parse_args(argv)
    if a.cmd not in ('plot', 'daycourse') and a.c1_dir is None:
        ap.error(f'{a.cmd} needs <c1_dir>')
    if a.cmd == 'extract':
        cmd_extract(a.out, a.c1_dir, a.jobs, a.only)
        return
    import c1_recovery_mechanics_summary as SM
    if a.cmd == 'plot':
        SM.cmd_plot(a.out, daycourse_grid=a.daycourse_grid)
    elif a.cmd == 'daycourse':
        SM.cmd_daycourse(a.out, daycourse_grid=a.daycourse_grid)
    else:
        getattr(SM, f'cmd_{a.cmd}')(a.out, a.c1_dir)


if __name__ == '__main__':
    main()
