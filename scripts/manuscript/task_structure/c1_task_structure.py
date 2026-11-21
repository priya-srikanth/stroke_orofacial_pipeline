"""Two-tone (cohort 1) task-session structure from the cue times of every pre-stroke session (manuscript
Supplementary Figure S2; Priya comment C244, 2026-11-21: "supplemental with diagram of task, including session time
and L vs R cues, showing the structure of cue blocks and quiet blocks").

Design being checked (legacy generate_reward_traces.ipynb, identical in facerhythm_stroke_biomarker_exp and _Priya):
a 60-min schedule alternating baseline epochs (no cue, no reward; U(120, 300) s) and reward epochs (U(20, 240) s),
first and last epochs baseline; up to 100 rewards placed at random inside reward epochs, at least 8 s apart and not in
the last 8 s of an epoch, L and R alternating in the sampling order (so each session is 50/50 but temporally random);
a 200-ms tone of the reward side starts with the reward. The generator stops early when no placeable time remains,
so some schedules hold fewer than 100 rewards.

Cue-reward blocks are runs of cues separated by < GAP_S: in pre-stroke sessions within-block intervals are <= 65 s and
between-block gaps >= 130 s, with none between, and the design's baseline epochs are >= 120 s.
Sham-day sessions are kept as pre-stroke sessions (Priya 2026-11-21).

Usage: PYTHONPATH=src python c1_task_structure.py <trials.parquet> <out_dir>
Writes (refuses to overwrite) <out_dir>/: sessions_structure.csv (one row per pre-stroke session), blocks.csv (one row
per cue-reward block), cue_intervals.csv (every consecutive-cue interval, labelled within / between), example_session.csv
(cues of the session closest to the cohort medians, used for the figure's timeline), summary.json (percentiles).
The manuscript figure is drawn by the paper code (manuscript_code/figures/task_structure/c1_task_structure_plot.py),
which only reads these tables.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

GAP_S = 100.0          # s; block split. Pre-stroke cue gaps are bimodal with nothing between ~65 and ~130 s.
OUT_FILES = ('sessions_structure.csv', 'blocks.csv', 'cue_intervals.csv', 'example_session.csv', 'summary.json')


def split_blocks(t: np.ndarray) -> list[np.ndarray]:
    """Indices that split a sorted cue-time vector into cue-reward blocks (consecutive cues < GAP_S apart)."""
    cut = np.where(np.diff(t) >= GAP_S)[0]
    return np.split(np.arange(len(t)), cut + 1)


def pct(x) -> list[float]:
    """0, 5, 25, 50, 75, 95, 100th percentiles, rounded to 0.1 (the summary format quoted in the legend)."""
    return np.round(np.percentile(np.asarray(x, float), [0, 5, 25, 50, 75, 95, 100]), 1).tolist()


def structure(T: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per-session, per-block and per-interval tables for the pre-stroke sessions of a trials table."""
    P = T[T.epoch == 'pre'].sort_values(['label', 'cue_s'])
    sess, blk, itv = [], [], []
    for lab, g in P.groupby('label'):
        t = g.cue_s.to_numpy(float)
        s = g.side.to_numpy()
        B = split_blocks(t)
        for k, b in enumerate(B):
            blk.append(dict(label=lab, animal=g.animal.iloc[0], block=k, n_trials=len(b), first_cue=t[b[0]],
                            last_cue=t[b[-1]], span_s=t[b[-1]] - t[b[0]]))
        d = np.diff(t)
        itv += [dict(label=lab, interval_s=x, kind='within' if x < GAP_S else 'between') for x in d]
        sess.append(dict(label=lab, animal=g.animal.iloc[0], n=len(t), first_cue=t[0], last_cue=t[-1], n_blocks=len(B),
                         frac_L=(s == 'L').mean(), switch=np.mean(s[1:] != s[:-1])))
    return {'sessions': pd.DataFrame(sess), 'blocks': pd.DataFrame(blk), 'intervals': pd.DataFrame(itv), 'pre': P}


def summarize(tab: dict[str, pd.DataFrame]) -> dict:
    """Percentile summary across all pre-stroke sessions (single-trial blocks have no span and are left out of it)."""
    S, B, iv = tab['sessions'], tab['blocks'], tab['intervals']
    return {'sessions': int(len(S)), 'animals': int(S.animal.nunique()), 'trials_per_session': pct(S.n),
            'first_cue_s': pct(S.first_cue), 'last_cue_min': pct(S.last_cue / 60), 'blocks_per_session': pct(S.n_blocks),
            'trials_per_block': pct(B.n_trials), 'block_duration_s': pct(B.span_s[B.n_trials > 1]),
            'within_block_interval_s': pct(iv.interval_s[iv.kind == 'within']),
            'between_block_gap_s': pct(iv.interval_s[iv.kind == 'between']), 'frac_L': pct(S.frac_L),
            'side_switch_rate': pct(S.switch)}


def example_session(tab: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Cues of the pre-stroke session whose trial and block counts are jointly closest to the cohort medians."""
    S = tab['sessions']
    mn, mb = np.median(S.n), np.median(S.n_blocks)
    lab = S.assign(d=(S.n - mn).abs() / mn + (S.n_blocks - mb).abs() / mb).sort_values('d').iloc[0].label
    g = tab['pre'][tab['pre'].label == lab].copy()
    blocks = split_blocks(g.cue_s.to_numpy(float))
    g['block'] = np.concatenate([[k] * len(b) for k, b in enumerate(blocks)])
    return g[['label', 'animal', 'trial', 'side', 'cue_s', 'block']]


def main(argv=None):
    """CLI: compute the tables from a trials table and write them to a new folder."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('trials', type=Path, help='trials.parquet (label, animal, epoch, trial, side, cue_s)')
    ap.add_argument('out_dir', type=Path)
    a = ap.parse_args(argv)
    if any((a.out_dir / f).exists() for f in OUT_FILES):
        sys.exit(f'refusing to overwrite outputs in {a.out_dir}')
    a.out_dir.mkdir(parents=True, exist_ok=True)
    T = pd.read_parquet(a.trials, columns=['label', 'animal', 'epoch', 'trial', 'side', 'cue_s'])
    tab = structure(T)
    tab['sessions'].to_csv(a.out_dir / 'sessions_structure.csv', index=False)
    tab['blocks'].to_csv(a.out_dir / 'blocks.csv', index=False)
    tab['intervals'].to_csv(a.out_dir / 'cue_intervals.csv', index=False)
    example_session(tab).to_csv(a.out_dir / 'example_session.csv', index=False)
    summ = summarize(tab)
    with open(a.out_dir / 'summary.json', 'w') as fh:
        json.dump(summ, fh, indent=1)
    for k, v in summ.items():
        print(k, v)


if __name__ == '__main__':
    main()
