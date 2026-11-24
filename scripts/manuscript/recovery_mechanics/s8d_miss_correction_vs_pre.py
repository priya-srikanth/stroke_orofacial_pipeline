"""S8D alternative (CC-B, Priya 11-23): correction after a MISS, post-stroke vs pre-stroke, with a hit control.

The two-tone (mice #1-#8) mirror of the six-position S12D alternative (widefield worktree wf_ccb_caprev1123,
scripts/caption_review_1123/s12d_miss_correction_vs_pre.py, commit 12e055c3), so S8D and S12D use one analysis.

Input: the live S8 data, <r2>/data/cued_licks_scored.pkl of c1_recovery_mechanics_2026-11-21_r2 (S8D's source).
Pairs (PRIMARY = the S8D set, c1_recovery_mechanics_summary.across_lick): consecutive cued licks k -> k+1 of a trial,
peak-to-peak <= PAIR_MAX_MS (300 ms), e_E of lick k and theta_E of lick k+1 finite. Hit / miss = S8D's (spout contact
on the cued spout within the lick's frames). Angle error e_k = S8D's e_E (endpoint angle minus the animal's pre-stroke
HIT mean for that cue), signed + = contralesional for reporting (gains do not depend on the sign).
SENSITIVITY pair set (the six-position rule): peak-to-peak <= 350 ms AND lick k has a previous lick with a finite e_E.

Per session x cue side (each >= MIN_N licks k of the class):
  gain_miss   OLS dang = a + g (-e_k) over misses; g = fraction of lick k's error corrected by lick k+1
  gain_hit    the same over hits (control: regression to the mean / lick variability)
  gain_diff   gain_miss - gain_hit (same session)
  binned      sign(-e_k) dang after misses in 5-deg |e_k| bins, minus the same animal's pre-stroke misses (same cue
              side, the session itself left out) in the same bin; miss-weighted mean over bins (>= 2 / >= 5 licks)
  ac1_hit     lag-1 correlation of the angle error within trials (e_k vs e_k+1) over hit-k pairs
Robustness: misses with reach >= REACH_CUT px (full-reach misses; cut justified from the pre-stroke miss angle error by
reach bin), and the LATERAL error in px (reach sin(theta_E) minus the animal's pre-stroke hit mean for the cue).
Stats: c1_stats.run_family (change from each animal's own pre-stroke sessions; session MWU + nested animal -> session
bootstrap, 4,000 draws; BH within a family; ** = q < 0.05 AND CI excludes 0); grades mild / moderate / severe and
mild+moderate (and all, descriptive); single-animal cells get the within-animal bootstrap and a dagger
(SECTION_dagger_single_animal.md rule: q < 0.05 AND within-animal CI excludes 0).

    python s8d_miss_correction_vs_pre.py <r2 dir> <out dir> [reach_cut_px]
Writes <out>/data_px/. Refuses to overwrite. The figure: s8d_miss_correction_plot.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'engagement_movement'))

import c1_recovery_mechanics_summary as SM  # noqa: E402

EPOCHS = SM.EPOCHS
GRADES = SM.GRADES
FIG_LABEL = SM.FIG_LABEL
MIN_N, BIN, MIN_CELL, MIN_REF = 10, 5.0, 2, 5
RBIN = 20.0
DAGGER = '†'
# BH families (Priya 11-23 via lead: the LATERAL (px) version is the main S8D panel, as the six-position S12D uses mm;
# the angle and full-reach versions are robustness families)
PX = ['gain_miss_lat', 'gain_hit_lat', 'gain_diff_lat', 'binned_lat', 'ac1_hit']
ANGLE = ['gain_miss', 'gain_hit', 'gain_diff', 'binned']
REACH = ['gain_miss_reach', 'gain_hit_reach', 'gain_diff_reach', 'binned_reach']
FAMILIES = [(PX, 's8d_alt_px'), (ANGLE, 's8d_alt_angle'), (REACH, 's8d_alt_fullreach')]
N_BOOT, SEED = 4000, 0


def pairs(L: pd.DataFrame, max_ms: float, need_prev: bool) -> pd.DataFrame:
    L = L.sort_values(['label', 'trial', 't_ms'])
    rows = []
    cols = ['t_ms', 'theta_E', 'e_E', 'hit', 'reach']
    for (lab, tr), g in L.groupby(['label', 'trial'], sort=False):
        if len(g) < 2:
            continue
        v = g[cols].to_numpy(float)
        for i in range(len(g) - 1):
            a, b = v[i], v[i + 1]
            if b[0] - a[0] > max_ms or not (np.isfinite(a[2]) and np.isfinite(b[1])):
                continue
            if need_prev and (i == 0 or not np.isfinite(v[i - 1][2])):
                continue
            rows.append((lab, tr, a[1], b[1], a[2], b[2], bool(a[3]), a[4], b[4], b[0] - a[0]))
    P = pd.DataFrame(rows, columns=['label', 'trial', 'th', 'th1', 'e', 'e1', 'hit', 'reach', 'reach1', 'dt'])
    meta = L.groupby(['label', 'trial'])[['animal', 'grade', 'epoch', 'rel_day', 'side', 'cue']].first().reset_index()
    return P.merge(meta, on=['label', 'trial'])


def prep(P: pd.DataFrame, L: pd.DataFrame) -> pd.DataFrame:
    pre = L[(L.epoch == 'pre') & L.hit]
    ref = pre.groupby(['animal', 'side']).theta_E.mean().unstack()
    sgn = np.sign(ref['contra'] - ref['ipsi']).rename('sgnC')             # + = contralesional, per animal
    P = P.join(sgn, on='animal')
    P['dang'] = P.th1 - P.th
    P['toward'] = np.sign(-P.e) * P.dang
    P['bin'] = np.floor(P.e.abs() / BIN).astype(int)
    P['e_c'] = P.e * P.sgnC
    P['lat'] = P.reach * np.sin(np.radians(P.th))
    P['lat1'] = P.reach1 * np.sin(np.radians(P.th1))
    Lh = pre.assign(lat=pre.reach * np.sin(np.radians(pre.theta_E)))
    P = P.join(Lh.groupby(['animal', 'cue']).lat.mean().rename('tgt_lat'), on=['animal', 'cue'])
    P['e_lat'] = P.lat - P.tgt_lat
    P['dlat'] = P.lat1 - P.lat
    P['toward_lat'] = np.sign(-P.e_lat) * P.dlat
    P['e_lat_c'] = P.e_lat * P.sgnC
    P['bin_lat'] = np.floor(P.e_lat.abs() / 10.0).astype(int)          # 10 px bins
    P['rbin'] = (np.floor(P.reach / RBIN) * RBIN).astype(int)
    return P


def gain(g: pd.DataFrame, e: str = 'e', d: str = 'dang') -> float:
    if len(g) < MIN_N:
        return np.nan
    x = -g[e].to_numpy(float)
    y = g[d].to_numpy(float)
    b, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(g)), x]), y, rcond=None)
    return float(b[1])


def binned(g: pd.DataFrame, ref: pd.DataFrame, tw: str = 'toward', bcol: str = 'bin') -> float:
    if len(g) < MIN_N:
        return np.nan
    gm = g.groupby(bcol)[tw].agg(['mean', 'size'])
    rm = ref.groupby(bcol)[tw].agg(['mean', 'size'])
    j = gm.join(rm, rsuffix='_ref', how='inner')
    j = j[(j['size'] >= MIN_CELL) & (j['size_ref'] >= MIN_REF)]
    return float(np.average(j['mean'] - j['mean_ref'], weights=j['size'])) if len(j) else np.nan


def ac1(g: pd.DataFrame) -> float:
    return float(np.corrcoef(g.e, g.e1)[0, 1]) if len(g) >= MIN_N else np.nan


def sessions(P: pd.DataFrame, rc: float) -> pd.DataFrame:
    rows = []
    M, H = P[~P.hit], P[P.hit]
    Mr, Hr = M[M.reach >= rc], H[H.reach >= rc]
    keys = ['label', 'animal', 'grade', 'epoch', 'rel_day', 'side']
    gM = dict(list(M.groupby(keys)))
    gH = dict(list(H.groupby(keys)))
    for k in sorted(set(gM) | set(gH)):
        lab, an, gr, ep, day, sd = k
        g = gM.get(k, M.iloc[:0])
        h = gH.get(k, H.iloc[:0])
        gr_ = g[g.reach >= rc]
        hr_ = h[h.reach >= rc]
        refm = M[(M.animal == an) & (M.side == sd) & (M.epoch == 'pre') & (M.label != lab)]
        refr = Mr[(Mr.animal == an) & (Mr.side == sd) & (Mr.epoch == 'pre') & (Mr.label != lab)]
        r = dict(zip(keys, k))
        r.update({'n_miss': len(g), 'n_hit': len(h), 'n_miss_reach': len(gr_), 'n_hit_reach': len(hr_),
                  'gain_miss': gain(g), 'gain_hit': gain(h), 'binned': binned(g, refm), 'ac1_hit': ac1(h),
                  'gain_miss_reach': gain(gr_), 'gain_hit_reach': gain(hr_), 'binned_reach': binned(gr_, refr),
                  'gain_miss_lat': gain(g, 'e_lat', 'dlat'), 'gain_hit_lat': gain(h, 'e_lat', 'dlat'),
                  'binned_lat': binned(g, refm, 'toward_lat', 'bin_lat'),
                  'reach_miss_med': g.reach.median() if len(g) else np.nan,
                  'share_miss_full': float((g.reach >= rc).mean()) if len(g) else np.nan})
        for s in ('', '_reach', '_lat'):
            r[f'gain_diff{s}'] = r[f'gain_miss{s}'] - r[f'gain_hit{s}']
        rows.append(r)
    del Hr
    return pd.DataFrame(rows)


def wa1(pre: np.ndarray, post: np.ndarray):
    rng = np.random.default_rng(SEED)
    d = np.empty(N_BOOT)
    for i in range(N_BOOT):
        qa = post[rng.integers(0, post.size, post.size)].mean()
        pa = pre[rng.integers(0, pre.size, pre.size)].mean()
        d[i] = qa - pa
    lo, hi = np.percentile(d, (2.5, 97.5))
    return float(post.mean() - pre.mean()), float(lo), float(hi)


def stats(S: pd.DataFrame, measures, family: str) -> pd.DataFrame:
    import c1_stats as CS
    long = SM.to_long(S, measures)
    R = CS.run_family(long, family)                                  # grades separately, BH over the family
    mm = long[long.grade.isin(['mild', 'moderate'])].assign(grade='mild+moderate')
    R2 = CS.run_family(pd.concat([mm, long.assign(grade='all')]), family + '_pooled',
                       grades=('mild+moderate', 'all'))
    R = pd.concat([R, R2], ignore_index=True)
    d = CS.deltas(pd.concat([long, mm]))
    # single-animal cells: within-animal bootstrap + dagger; per-animal changes for every cell
    extra = []
    for _, r in R.iterrows():
        gg = d[(d.measure == r.measure) & (d.side == r.side)]
        gg = gg if r.grade == 'all' else gg[gg.grade == r.grade]
        if r.grade == 'all':
            gg = gg[gg.grade != 'mild+moderate']
        pa = gg.groupby(['animal', 'epoch']).value_norm.mean().unstack()
        post_an = sorted(gg[gg.epoch == r.post_epoch].animal.unique())
        x = {'per_animal': '; '.join(f'#{FIG_LABEL[a]} {pa.loc[a, r.post_epoch]:+.3f}' for a in
                                     sorted(post_an, key=FIG_LABEL.get) if a in pa.index and r.post_epoch in pa)}
        x['single_animal'] = len(post_an) == 1
        if len(post_an) == 1:
            a = post_an[0]
            pre = gg[(gg.animal == a) & (gg.epoch == 'pre')].value_norm.to_numpy(float)
            post = gg[(gg.animal == a) & (gg.epoch == r.post_epoch)].value_norm.to_numpy(float)
            x['sole_animal'] = f'#{FIG_LABEL[a]}'
            x['wa1_effect'], x['wa1_ci_lo'], x['wa1_ci_hi'] = wa1(pre, post)
        extra.append(x)
    R = pd.concat([R.reset_index(drop=True), pd.DataFrame(extra)], axis=1)
    ex = (R.wa1_ci_lo > 0) | (R.wa1_ci_hi < 0)
    R['dagger'] = R.single_animal & (R.q_bh < 0.05) & ex
    R['mark'] = np.where(R.star, '**', np.where(R.dagger, DAGGER, ''))
    return R


def describe(P: pd.DataFrame, rc: float, out: Path):
    P = P.assign(outcome=np.where(P.hit, 'hit', 'miss'))
    pre = P[P.epoch == 'pre']
    db = pre.groupby(['rbin', 'outcome']).agg(n=('e', 'size'), angle_err_med=('e_c', 'median'),
                                              abs_angle_err_med=('e', lambda x: x.abs().median()),
                                              lat_err_med_px=('e_lat_c', 'median')).unstack('outcome')
    da = pre.groupby(['side', 'outcome']).agg(n=('e', 'size'), angle_err_med=('e_c', 'median'),
                                              abs_angle_err_med=('e', lambda x: x.abs().median()),
                                              lat_err_med_px=('e_lat_c', 'median'), reach_med=('reach', 'median'))
    dd = P.groupby(['epoch', 'side', 'outcome']).agg(
        n=('e', 'size'), reach_med=('reach', 'median'), abs_angle_err_med=('e', lambda x: x.abs().median()),
        share_reach_ge_cut=('reach', lambda x: float((x >= rc).mean())))
    pd.set_option('display.width', 250)
    for nm, D in (('pre_by_reach', db), ('pre_by_side', da), ('by_epoch', dd)):
        D.to_csv(out / f's8d_alt_desc_{nm}.csv', float_format='%.4g')
        print(f'\n== {nm}\n', D.round(2).to_string(), flush=True)


def main(r2: str, out: str, reach_cut: str = '150'):
    rc = float(reach_cut)
    out = Path(out)
    data = out / 'data_px'
    if data.exists() and any(data.iterdir()):
        sys.exit(f'refusing to overwrite {data}')
    data.mkdir(parents=True, exist_ok=True)
    L = pd.read_pickle(Path(r2) / 'data/cued_licks_scored.pkl')
    for tag, mx, prev in (('primary', SM.PAIR_MAX_MS, False), ('sens350prev', 350.0, True)):
        P = prep(pairs(L, mx, prev), L)
        print(f'\n######## {tag}: {len(P)} pairs, {P.label.nunique()} sessions', flush=True)
        if tag == 'primary':
            P.to_parquet(data / 's8d_alt_pairs_primary.parquet')
            describe(P, rc, data)
        S = sessions(P, rc)
        S.to_csv(data / f's8d_alt_sessions_{tag}.csv', index=False, float_format='%.5g')
        fams = FAMILIES if tag == 'primary' else FAMILIES[:2]
        R = pd.concat([stats(S, m, f) for m, f in fams], ignore_index=True)
        pre_lvl = {m: S[S.epoch == 'pre'].groupby(['side', 'animal'])[m].mean().groupby('side').mean()
                   for m in PX + ANGLE + REACH}
        R['pre_level_animal_mean'] = [pre_lvl[r.measure].get(r.side, np.nan) for r in R.itertuples()]
        R.to_csv(data / f's8d_alt_stats_{tag}.csv', index=False, encoding='utf-8', float_format='%.5g')
        show = R[['family', 'measure', 'side', 'grade', 'post_epoch', 'nb_effect', 'nb_ci_lo', 'nb_ci_hi', 'q_bh',
                  'mark', 'nb_n_animals', 'per_animal']]
        print(show.round(3).to_string(index=False), flush=True)


if __name__ == '__main__':
    main(*sys.argv[1:4])
