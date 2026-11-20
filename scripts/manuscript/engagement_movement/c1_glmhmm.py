"""GLM-HMM engagement states for the two-tone cohort (#1-#8), same model class as the six-position cohort.

Model = widefield_pipeline `wfield_local.glm_hmm.GLMHMM` imported UNCHANGED (input-output HMM over trials, per-output
state-specific multinomial logistic emissions, sticky Dirichlet prior 10, L2 prior 1, 5 restarts, EM), design v2
(animal offsets SHARED across states, then a state intercept + task dummies; no previous-outcome input), K = 5, ONE
pooled model over all animals and all epochs (`run_pooled` analog), each session one sequence, ALL trials.
Roles = `behavior_states.glmhmm_roles` rule: engaged = state response rate >= 0.90; disengaged = the highest
no-response rate of the rest; partial = the others. (The six-position 0+1 merge is data-specific and not applied:
roles already pool states.)

Two-tone OUTPUTS per trial cycle (six-position definitions where they apply):
  outcome       0 = response (any spout lick, DAQ, cue + 70 ms .. cue + 8 s), 1 = no response
                (six-position "3" coding merges contact + incomplete into ATTEMPT: side / accuracy are NOT used, so the
                states do not encode the lateralized aim deficit);
  latency       first-lick latency of responded trials, 3 levels by the POOLED PRE-STROKE quantiles (< P50, P50-P90,
                >= P90); unobserved on no-response trials;
  precue_lick   any lick -2..0 s;  iti_lick  any lick in the ITI (previous cue + 8 s .. cue - 2 s);
  run_precue / run_iti   fraction of the window in running bouts: 0 / (0, 0.5) / >= 0.5 (six-position RUN_LEVELS).
INPUTS X: [animal offsets (all but the first animal; shared)] + [state intercept, contralesional-cue dummy,
  cue side switched since the previous trial] (the analog of the six-position spout dummies + "spout moved").

Variants (--variant):
  primary   as above.
  ipsi_only outcome + latency observed ONLY on ipsilesional-cue trials (unobserved = likelihood 1 on contralesional
            ones; their state comes from the chain + the non-spout outputs): engagement a contralesional motor deficit
            cannot drive (prompt item 10a).
  jaw3      (Priya 2026-11-20) outcome = attempt (spout lick) / JAW-ONLY (no lick, jaw opened: pipeline jaw_pass_qc,
            data/jaw_trials.parquet) / no response (neither) = the six-position production OUTCOME coding.
  init      (Priya 2026-11-20) outcome = response INITIATION (lick OR jaw opening) vs none = the six-position 'init'
            refit (s3_glmhmm_refit.py); engaged role = initiation rate >= 0.9.
            Jaw variants: no-lick trials of the 8 sessions without a jaw classifier file are unobserved.
  no_cue    outcome + latency dropped entirely (lick-free of the cue response): engagement from pre-cue / ITI licking
            and running only (sensitivity).

Usage: python c1_glmhmm.py <c1_dir> [--variant primary] [--k 5] [--select-k]
Writes <c1_dir>/glmhmm/<variant>_K<k>_states.csv.gz, _params.json, _profile.csv; select_k_<variant>.csv.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ENGAGED_ATTEMPT = 0.9
RUN_LEVELS = (0.0, 0.5)
OUTPUTS = ('outcome', 'latency', 'precue_lick', 'iti_lick', 'run_precue', 'run_iti')
NCLS = [2, 3, 2, 2, 3, 3]


def run_level(f):
    f = np.asarray(f, float)
    out = np.where(f <= RUN_LEVELS[0], 0, np.where(f < RUN_LEVELS[1], 1, 2))
    return np.where(np.isfinite(f), out, -1).astype(int)


def build(T: pd.DataFrame, variant: str):
    animals = sorted(T.animal.unique())
    pre = T[(T.epoch == 'pre') & T.responded]
    q50, q90 = np.nanpercentile(pre.lat_any, [50, 90])
    data = {}
    for lab, S in T.sort_values(['label', 'trial']).groupby('label', sort=True):
        S = S.reset_index(drop=True)
        out = np.where(S.responded, 0, 1)
        lat = np.where(~S.responded, -1, np.where(S.lat_any < q50, 0, np.where(S.lat_any < q90, 1, 2)))
        if variant == 'ipsi_only':
            contra = (S.side == 'R').to_numpy()
            out = np.where(contra, -1, out); lat = np.where(contra, -1, lat)
        if variant == 'no_cue':
            out = np.full(len(S), -1); lat = np.full(len(S), -1)
        if variant in ('jaw3', 'init'):
            jaw = S.jaw_open.to_numpy(float)
            resp = S.responded.to_numpy(bool)
            if variant == 'jaw3':     # six-position OUTCOME "3": attempt / jaw-only / no response
                out = np.where(resp, 0, np.where(jaw == 1, 1, np.where(jaw == 0, 2, -1)))
            else:                     # six-position 'init': any response initiation (lick OR jaw opening) vs none
                out = np.where(resp | (jaw == 1), 0, np.where(jaw == 0, 1, -1))
        Y = np.column_stack([out, lat, S.precue_lick.astype(int), S.iti_lick.astype(int),
                             run_level(S.run_frac_precue), run_level(S.run_frac_iti)]).astype(int)
        an = S.animal.iloc[0]
        A = np.array([[1.0 if an == a else 0.0 for a in animals[1:]]] * len(S))
        contra = (S.side == 'R').to_numpy(float)
        sw = np.r_[0.0, (S.side.to_numpy()[1:] != S.side.to_numpy()[:-1]).astype(float)]
        X = np.hstack([A, np.ones((len(S), 1)), contra[:, None], sw[:, None]])
        keep = ['label', 'animal', 'date', 'epoch', 'grade', 'trial', 'side', 't_min', 'responded']
        data[lab] = (X, Y, S[keep + (['jaw_open'] if 'jaw_open' in S else [])])
    return data, len(animals) - 1, {'lat_q50': float(q50), 'lat_q90': float(q90)}


def profile(Tab, K, variant='primary'):
    """Per state: posterior-weighted rates. 'response' = the ATTEMPT rate that sets the engaged role (spout lick;
    for 'init' lick OR jaw opening); 'no_response' = neither lick nor (where known) jaw opening for the jaw variants,
    no lick otherwise; jaw_only = no lick but jaw opened (trials with jaw data)."""
    rows = []
    lick = Tab.responded.astype(float).to_numpy()
    jaw = Tab.jaw_open.to_numpy(float) if 'jaw_open' in Tab else np.full(len(Tab), np.nan)
    jo = np.where(np.isfinite(jaw), (lick == 0) & (jaw == 1), np.nan).astype(float)
    none = np.where(np.isfinite(jaw), (lick == 0) & (jaw == 0), np.nan).astype(float)
    att = np.where(np.isfinite(jaw), ((lick == 1) | (jaw == 1)).astype(float), np.where(lick == 1, 1.0, np.nan))

    def wavg(x, w):
        ok = np.isfinite(x)
        return float(np.average(x[ok], weights=w[ok])) if ok.any() and w[ok].sum() > 0 else np.nan
    for k in range(K):
        w = Tab[f'p_state{k}'].to_numpy(float)
        jaw_v = variant in ('jaw3', 'init')
        rows.append({'state': k, 'response': wavg(att, w) if variant == 'init' else wavg(lick, w),
                     'no_response': wavg(none, w) if jaw_v else wavg(1 - lick, w),
                     'lick_rate': wavg(lick, w), 'jaw_only_rate': wavg(jo, w), 'neither_rate': wavg(none, w),
                     'occupancy': w.mean()})
    P = pd.DataFrame(rows).set_index('state')
    eng = P.index[P.response >= ENGAGED_ATTEMPT].tolist()
    rest = P.drop(index=eng)
    dis = [int(rest.no_response.idxmax())] if len(rest) else []
    P['role'] = ['engaged' if k in eng else 'disengaged' if k in dis else 'partial' for k in P.index]
    return P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('c1', type=Path)
    ap.add_argument('--variant', default='primary', choices=('primary', 'ipsi_only', 'no_cue', 'jaw3', 'init'))
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--select-k', action='store_true')
    ap.add_argument('--wf', default='C:/Users/SabatiniLab/Github/widefield_pipeline_c2stats')
    a = ap.parse_args()
    sys.path.insert(0, a.wf)
    from wfield_local import glm_hmm as G
    od = a.c1 / 'glmhmm'; od.mkdir(exist_ok=True)
    T = pd.read_parquet(a.c1 / 'data' / 'trials.parquet')
    if a.variant in ('jaw3', 'init'):              # c1_jaw_trials.py output (pipeline jaw_pass_qc per trial)
        T = T.merge(pd.read_parquet(a.c1 / 'data' / 'jaw_trials.parquet')[['label', 'trial', 'jaw_open']],
                    on=['label', 'trial'], how='left')
    data, ns, meta = build(T, a.variant)
    labs = sorted(data)
    ncls = [3] + NCLS[1:] if a.variant == 'jaw3' else NCLS
    print(f'{a.variant}: {len(labs)} sessions, {sum(len(v[1]) for v in data.values())} trials, X width '
          f'{data[labs[0]][0].shape[1]} (shared {ns}); latency cut points {meta}', flush=True)
    if a.select_k:
        f = od / f'select_k_{a.variant}.csv'
        if f.exists():
            sys.exit(f'refusing to overwrite {f}')
        # folds interleaved by session within animal (glm_hmm.select_k with labels=), K 1..6
        G.N_SHARED = ns
        _orig = G.n_classes
        G.n_classes = lambda: ncls
        G.OUTPUTS = OUTPUTS
        R = G.select_k({k: v[:2] + (None,) for k, v in data.items()}, ks=(1, 2, 3, 4, 5, 6), labels=labs)
        G.n_classes = _orig
        R.to_csv(f, index=False)
        print(R.groupby('K')[['bits_per_cycle_vs_K1', 'pR2_total']].mean().round(4), flush=True)
        return
    stem = od / f'{a.variant}_K{a.k}'
    if Path(f'{stem}_states.csv.gz').exists():
        sys.exit(f'refusing to overwrite {stem}_states.csv.gz')
    m = G.GLMHMM(a.k, n_cls=ncls, seed=0, n_shared=ns).fit([data[l][:2] for l in labs])
    Xm = np.vstack([data[l][0] for l in labs]).mean(0)
    order = m.engagement_order(Xm) if a.variant != 'no_cue' else np.arange(a.k)
    post = m.posteriors([data[l][:2] for l in labs])
    rows = []
    for l, g in zip(labs, post):
        g = g[:, order]
        S = data[l][2].copy()
        for k in range(a.k):
            S[f'p_state{k}'] = g[:, k]
        S['state'] = g.argmax(1)
        S['state_p08'] = np.where(g.max(1) > 0.8, g.argmax(1), -1)
        rows.append(S)
    Tab = pd.concat(rows, ignore_index=True)
    P = profile(Tab, a.k, a.variant)
    if a.variant == 'no_cue':      # no response output: order + roles by the response rate the states imply
        order2 = P.response.sort_values(ascending=False).index.to_numpy()
        ren = {f'p_state{o}': f'p_state{i}' for i, o in enumerate(order2)}
        Tab = Tab.rename(columns=ren)
        inv = {int(o): i for i, o in enumerate(order2)}
        Tab['state'] = Tab.state.map(inv); Tab['state_p08'] = Tab.state_p08.map(lambda s: inv.get(s, -1))
        P = profile(Tab, a.k, a.variant); order = order[order2]
    roles = P.role.to_dict()
    Tab['role'] = Tab.state.map(roles)
    for r in ('engaged', 'partial', 'disengaged'):
        Tab[f'p_{r}'] = Tab[[f'p_state{k}' for k in range(a.k) if roles[k] == r]].sum(1)
    Tab.to_csv(f'{stem}_states.csv.gz', index=False)
    P.to_csv(f'{stem}_profile.csv')
    params = {'K': a.k, 'variant': a.variant, 'outputs': list(OUTPUTS), 'n_classes': ncls, 'n_shared': ns,
              'inputs': 'animal offsets (shared, all but first animal) + intercept + contra-cue dummy + side switched',
              'W': [w[order].tolist() for w in m.W], 'B': [b.tolist() for b in m.B] if m.B is not None else None,
              'A': m.A[np.ix_(order, order)].tolist(), 'pi': m.pi[order].tolist(), 'll': m.ll,
              'roles': {int(k): v for k, v in roles.items()}, **meta,
              'sticky': G.STICKY, 'l2_prior': G.L2_PRIOR, 'n_restarts': G.N_RESTARTS}
    Path(f'{stem}_params.json').write_text(json.dumps(params, indent=1))
    print(P.round(3).to_string(), flush=True)
    print('A diag', np.round(np.diag(np.array(params['A'])), 3), 'll', round(m.ll, 1), flush=True)


if __name__ == '__main__':
    main()
