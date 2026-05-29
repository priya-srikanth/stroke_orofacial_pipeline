"""Phase 9.1 session/trial filter sensitivity probe (READ-ONLY).

Intelligence-gathering for the upcoming ``chore/dlc-session-and-trial-filtering``
chore-PR. This script does **not** write any pipeline output other than three
sensitivity CSVs under ``pipeline_outputs/stats/sensitivity/``. It reads the
Phase 7a.3 per-trial tongue endpoints JSON and reports how many sessions /
trials / phenotype-pool cells survive a grid of candidate session-level and
trial-level lick-count thresholds, so the threshold lock can be made on
evidence rather than guesswork.

Composition (the four layers the chore-PR filters will compose, modelled here):

    Stage A (SessionFilter)   drop a (session, side) where
                              ``n_trials_with_detected_lick < min_trials`` (10).
    Stage B (TrialFilter)     drop an individual trial where
                              ``n_licks_per_trial < min_licks_per_trial``.
    Stage C (per-session agg) each surviving (session, side) is one unit of
                              observation; a session retaining 0 trials after
                              Stage B cannot produce a per-session statistic and
                              is therefore NOT counted as kept.
    Stage D (phenotype pool)  POOL ALL SURVIVING SESSIONS across every animal in
                              a (phenotype, epoch, side) cell. Session is the
                              unit of observation. Sentinel ONLY when
                              ``n_sessions_kept == 0``.

Lick-count provenance (interpretation note, recorded in the PR):

    "v7-kept lick" here is the DLC **tongue-kinematics** detected lick, read from
    ``tongue.n_licks_family.n_licks[i]`` (the per-trial count of detected tongue
    protrusions in that trial's tone-aligned window;
    ``n_licks == n_left + n_right + n_other``). This is deliberately distinct
    from ``cohort_filters.SessionFilter``'s NPZ **spout-lick** definition — that
    filter informs the W-2 histogram pooling, whereas this probe informs a
    DLC-kinematics-specific filter (first-N-lick velocity, first-lick /
    phase-aligned metrics). A trial's *side* is the tone side
    (``json["sides"][i]``), not the lick direction.

Run (hermetic, from the probe worktree)::

    PYTHONPATH=<worktree>/src python scripts/phase_9_1_filter_sensitivity_probe/probe.py
"""
from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from stroke_orofacial.animals import get_animal
from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label

logger = logging.getLogger("filter_sensitivity_probe")

# --- Cohort + threshold grid ------------------------------------------------

# 8-animal Q-lock 13b cohort.
COHORT: tuple[str, ...] = (
    "PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55",
)

# Stage A proposed SessionFilter default: drop a (session, side) whose count of
# trials with >= 1 detected lick is below this.
SESSION_MIN_TRIALS_WITH_LICK = 10

# Stage B per-trial drop thresholds explored.
SIDES: tuple[str, ...] = ("L", "R")

# Display order for epochs in the stdout summary.
EPOCH_ORDER: tuple[str, ...] = ("pre", "acute", "sub_acute", "chronic")

# filter_variant -> (session_min_trials_with_lick, trial_min_licks)
#   session_min_trials_with_lick = None  -> Stage A passthrough
#   trial_min_licks              = None  -> Stage B passthrough
FILTER_VARIANTS: dict[str, tuple[int | None, int | None]] = {
    "session_only_lt10": (10, None),
    "trial_only_lt5": (None, 5),
    "trial_only_lt3": (None, 3),
    "session_lt10_AND_trial_lt5": (10, 5),
    "session_lt10_AND_trial_lt3": (10, 3),
    "session_lt10_AND_trial_lt1": (10, 1),
}


def collapse_3tier(phenotype_4tier: str | None) -> str | None:
    """Collapse the 4-tier phenotype to the Q-lock 12 Addendum #4 3-tier scheme.

    ``moderate-severe`` merges into ``moderate``; ``mild`` and ``severe`` are
    unchanged. ``None`` (unstamped) passes through.
    """
    if phenotype_4tier == "moderate-severe":
        return "moderate"
    return phenotype_4tier


# --- Per-(animal, date, side) extraction ------------------------------------


@dataclass
class SessionSideRecord:
    """One (animal, date, side) session-side unit and its per-trial licks."""

    animal: str
    date: str  # YYYY-MM-DD
    side: str
    epoch_label: str | None
    phenotype_4tier: str | None
    phenotype_3tier: str | None
    # n_licks_per_trial for every trial of this tone side, in trial order.
    per_trial_licks: list[tuple[int, int]]  # (trial_index, n_licks)

    @property
    def n_trials_of_side(self) -> int:
        return len(self.per_trial_licks)

    @property
    def n_kept_licks(self) -> int:
        return sum(n for _, n in self.per_trial_licks)

    @property
    def n_trials_with_detected_lick(self) -> int:
        return sum(1 for _, n in self.per_trial_licks if n >= 1)

    def n_trials_ge(self, min_licks: int) -> int:
        """Trials whose per-trial lick count is >= ``min_licks``."""
        return sum(1 for _, n in self.per_trial_licks if n >= min_licks)


def load_session_side_records(
    animal: str,
    resolver: PathResolver,
) -> tuple[list[SessionSideRecord], int, int]:
    """Build per-(date, side) records for one animal.

    Returns ``(records, n_dates_enumerated, n_json_missing)``.
    """
    animal_info = get_animal(animal)
    pheno4 = animal_info.recovery_phenotype
    pheno3 = collapse_3tier(pheno4)

    dates = yaml_driven_session_dates(animal, animal_info=animal_info)
    records: list[SessionSideRecord] = []
    n_missing = 0
    for d in dates:
        json_path = resolver.tongue_pertrial_endpoints_json(animal, d)
        if not Path(json_path).exists():
            n_missing += 1
            continue
        with open(json_path) as fh:
            j = json.load(fh)
        sides = j["sides"]
        trial_indices = j["trial_indices"]
        n_licks = j["tongue"]["n_licks_family"]["n_licks"]
        rel_day = animal_info.day_relative_to_stroke(d)
        epoch = assign_epoch_label(rel_day, animal_info)
        per_side: dict[str, list[tuple[int, int]]] = {s: [] for s in SIDES}
        for ti, side, nl in zip(trial_indices, sides, n_licks):
            if side not in per_side:
                per_side[side] = []
            per_side[side].append((int(ti), int(nl)))
        for side in SIDES:
            records.append(
                SessionSideRecord(
                    animal=animal,
                    date=d.isoformat(),
                    side=side,
                    epoch_label=epoch,
                    phenotype_4tier=pheno4,
                    phenotype_3tier=pheno3,
                    per_trial_licks=per_side[side],
                )
            )
    return records, len(dates), n_missing


# --- CSV emission -----------------------------------------------------------


def write_session_filter_probe(records: list[SessionSideRecord], path: Path) -> None:
    """one row per (animal, date, side)."""
    cols = [
        "animal", "date", "side", "epoch_label",
        "phenotype_4tier", "phenotype_3tier",
        "n_kept_licks", "n_trials_with_detected_lick",
        "included_under_trials_lt10", "included_under_licks_lt20",
        "included_under_AND_combine", "included_under_OR_combine",
    ]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in records:
            # Two candidate session-level criteria, plus their AND / OR combine.
            inc_trials_lt10 = r.n_trials_with_detected_lick >= 10
            inc_licks_lt20 = r.n_kept_licks >= 20
            w.writerow([
                r.animal, r.date, r.side, r.epoch_label,
                r.phenotype_4tier, r.phenotype_3tier,
                r.n_kept_licks, r.n_trials_with_detected_lick,
                inc_trials_lt10, inc_licks_lt20,
                inc_trials_lt10 and inc_licks_lt20,
                inc_trials_lt10 or inc_licks_lt20,
            ])


def write_trial_filter_probe(records: list[SessionSideRecord], path: Path) -> None:
    """one row per (animal, date, side, trial_index)."""
    cols = [
        "animal", "date", "side", "trial_index", "epoch_label",
        "phenotype_4tier", "phenotype_3tier", "n_licks_per_trial",
        "included_under_lt1", "included_under_lt3",
        "included_under_lt5", "included_under_lt10",
    ]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in records:
            for trial_index, n in r.per_trial_licks:
                w.writerow([
                    r.animal, r.date, r.side, trial_index, r.epoch_label,
                    r.phenotype_4tier, r.phenotype_3tier, n,
                    n >= 1, n >= 3, n >= 5, n >= 10,
                ])


@dataclass
class CellAccum:
    """Phenotype-pool cell accumulator for one filter variant."""

    n_sessions_total_pre_filter: int = 0
    n_sessions_kept: int = 0
    animals_contributing: set = None  # type: ignore[assignment]
    n_trials_total_pre_filter: int = 0
    n_trials_kept: int = 0

    def __post_init__(self) -> None:
        if self.animals_contributing is None:
            self.animals_contributing = set()


def _session_kept_and_trials(
    r: SessionSideRecord,
    session_min_trials: int | None,
    trial_min_licks: int | None,
) -> tuple[bool, int]:
    """Apply one variant to one (session, side).

    Returns ``(session_kept, n_trials_kept_this_session)``.

    Stage A: if ``session_min_trials`` is set, the (session, side) is dropped
    when ``n_trials_with_detected_lick < session_min_trials``.
    Stage B: if ``trial_min_licks`` is set, only trials with
    ``n_licks >= trial_min_licks`` survive; otherwise all trials survive.
    Stage C: a session retaining 0 trials is NOT kept (cannot form a per-session
    statistic).
    """
    # Stage A.
    if session_min_trials is not None and r.n_trials_with_detected_lick < session_min_trials:
        return False, 0
    # Stage B.
    if trial_min_licks is None:
        n_trials_kept = r.n_trials_of_side
    else:
        n_trials_kept = r.n_trials_ge(trial_min_licks)
    # Stage C.
    if n_trials_kept == 0:
        return False, 0
    return True, n_trials_kept


def build_combined_summary(records: list[SessionSideRecord]) -> dict:
    """Return ``{(pheno4, pheno3, epoch, side, variant): CellAccum}``."""
    summary: dict[tuple, CellAccum] = defaultdict(CellAccum)
    for r in records:
        # An (animal,date,side) row with 0 trials of that side still exists as a
        # pre-filter session-slot, but contributes 0 trials to the denominator.
        for variant, (smin, tmin) in FILTER_VARIANTS.items():
            key = (
                r.phenotype_4tier, r.phenotype_3tier,
                r.epoch_label, r.side, variant,
            )
            cell = summary[key]
            cell.n_sessions_total_pre_filter += 1
            cell.n_trials_total_pre_filter += r.n_trials_of_side
            kept, n_trials_kept = _session_kept_and_trials(r, smin, tmin)
            if kept:
                cell.n_sessions_kept += 1
                cell.animals_contributing.add(r.animal)
                cell.n_trials_kept += n_trials_kept
    return summary


def write_combined_summary(summary: dict, path: Path) -> None:
    cols = [
        "phenotype_4tier", "phenotype_3tier", "epoch_label", "side",
        "filter_variant",
        "n_sessions_total_pre_filter", "n_sessions_kept",
        "n_unique_animals_contributing",
        "n_trials_total_pre_filter", "n_trials_kept",
        "triggers_phenotype_pool_sentinel",
    ]

    def sort_key(item):
        (p4, p3, epoch, side, variant), _ = item
        epoch_rank = EPOCH_ORDER.index(epoch) if epoch in EPOCH_ORDER else len(EPOCH_ORDER)
        variant_rank = list(FILTER_VARIANTS).index(variant)
        return (str(p4), str(epoch_rank), side, variant_rank)

    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for (p4, p3, epoch, side, variant), cell in sorted(summary.items(), key=sort_key):
            w.writerow([
                p4, p3, epoch, side, variant,
                cell.n_sessions_total_pre_filter, cell.n_sessions_kept,
                len(cell.animals_contributing),
                cell.n_trials_total_pre_filter, cell.n_trials_kept,
                cell.n_sessions_kept == 0,
            ])


# --- stdout summary ---------------------------------------------------------


def _ordered_cells(summary: dict, variant: str):
    """Yield ((p4, epoch, side), cell) for one variant, in display order."""
    rows = [
        ((p4, p3, epoch, side), cell)
        for (p4, p3, epoch, side, v), cell in summary.items()
        if v == variant
    ]

    def k(item):
        (p4, p3, epoch, side), _ = item
        epoch_rank = EPOCH_ORDER.index(epoch) if epoch in EPOCH_ORDER else len(EPOCH_ORDER)
        return (str(p4), epoch_rank, side)

    return sorted(rows, key=k)


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 78)
    print("FILTER SENSITIVITY PROBE — phenotype-pool (session-pooled) summary")
    print("=" * 78)

    print("\n--- session_only_lt10  (proposed SessionFilter default) ---")
    print("  phenotype_4tier / epoch / side : n_sessions_kept (n_unique_animals)")
    sentinels: list[str] = []
    for (p4, p3, epoch, side), cell in _ordered_cells(summary, "session_only_lt10"):
        flag = "  <-- SENTINEL (0 sessions)" if cell.n_sessions_kept == 0 else ""
        print(
            f"  {str(p4):16s} {str(epoch):10s} {side} : "
            f"{cell.n_sessions_kept:3d} sessions "
            f"({len(cell.animals_contributing)} animals){flag}"
        )
        if cell.n_sessions_kept == 0:
            sentinels.append(f"{p4}/{epoch}/{side}")
    print(f"\n  SENTINEL cells under session_only_lt10: "
          f"{', '.join(sentinels) if sentinels else 'NONE'}")

    for variant, label in [
        ("session_lt10_AND_trial_lt5",
         "composed filter for first-5-lick velocity metrics"),
        ("session_lt10_AND_trial_lt1",
         "composed filter for first-lick / phase-aligned metrics"),
    ]:
        print(f"\n--- {variant}  ({label}) ---")
        print("  phenotype_4tier / epoch / side : n_trials_kept "
              "(n_sessions_kept, n_unique_animals)")
        v_sentinels: list[str] = []
        for (p4, p3, epoch, side), cell in _ordered_cells(summary, variant):
            flag = "  <-- SENTINEL (0 sessions)" if cell.n_sessions_kept == 0 else ""
            print(
                f"  {str(p4):16s} {str(epoch):10s} {side} : "
                f"{cell.n_trials_kept:5d} trials "
                f"({cell.n_sessions_kept} sessions, "
                f"{len(cell.animals_contributing)} animals){flag}"
            )
            if cell.n_sessions_kept == 0:
                v_sentinels.append(f"{p4}/{epoch}/{side}")
        print(f"\n  SENTINEL cells under {variant}: "
              f"{', '.join(v_sentinels) if v_sentinels else 'NONE'}")


# --- main -------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    resolver = PathResolver()
    out_dir = resolver.pipeline_outputs(subdir="stats") / "sensitivity"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_records: list[SessionSideRecord] = []
    for animal in COHORT:
        recs, n_dates, n_missing = load_session_side_records(animal, resolver)
        n_sessions = len({r.date for r in recs})
        logger.info(
            "%s: %d dates enumerated, %d session JSONs loaded, %d missing",
            animal, n_dates, n_sessions, n_missing,
        )
        all_records.extend(recs)

    logger.info("\nTotal (animal,date,side) session-slots: %d", len(all_records))

    session_csv = out_dir / "session_filter_probe.csv"
    trial_csv = out_dir / "trial_filter_probe.csv"
    summary_csv = out_dir / "combined_filter_summary.csv"

    write_session_filter_probe(all_records, session_csv)
    write_trial_filter_probe(all_records, trial_csv)
    summary = build_combined_summary(all_records)
    write_combined_summary(summary, summary_csv)

    logger.info("Wrote:\n  %s\n  %s\n  %s", session_csv, trial_csv, summary_csv)

    print_summary(summary)


if __name__ == "__main__":
    main()
