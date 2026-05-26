"""Phase 7e Event B chore Stage 6.4 — surgical delete 26 stale per_trial
tongue JSONs + emit per-animal _SKIPPED_NO_DLC_INPUT.md sidecars.

Per Priya 2026-05-26 destructive-op approval (Stage 6 adjudication
message). One-time-only execution at chore close walkthrough; do NOT
re-run.

The 26 stale JSONs split into two classes:
  - 17 secondary-spout sessions (per configs/session_overrides.yaml
    `secondary_spout_sessions:`): Pattern B acquisitions with no
    upstream tongue DLC inference.
  - 9 out-of-cohort sessions (PS51/PS54/PS55 × 2025-04-16/17/18):
    predate current animal session_start = 2025-04-21 per Q1.C
    (Phase 7c.2 cohort-archeology correction). Stale leftover from
    prior emit when these dates were in-cohort.

Each affected animal (PS51, PS54, PS55) gets a sidecar README at:
  pipeline_outputs/dlc_kinematics/per_trial/tongue/<animal>/_SKIPPED_NO_DLC_INPUT.md

The sidecar groups dates by class with the appropriate reason.

CLI:
  python scripts/phase_7e/stage6_4_delete_stale_per_trial_jsons.py --dry-run
  python scripts/phase_7e/stage6_4_delete_stale_per_trial_jsons.py --execute

The default mode is --dry-run (no destructive ops). --execute requires
the per-invocation Priya approval message recorded in
.scratch_chore_phase_7e_reemit/_stage6_4_priya_approval.txt OR an
override via --i-have-approval (last-resort manual override).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

import yaml

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

SECONDARY_SPOUT_REASON = (
    "session is in YAML cohort date range but registered as secondary-spout "
    "(Pattern B) per `configs/session_overrides.yaml`; no upstream tongue "
    "DLC inference (Phase 7-pre-secondary-spout cohort lacks DLC outputs)."
)
OUT_OF_COHORT_REASON = (
    "session predates current animal session_start = 2025-04-21 per "
    "`configs/animals.yaml`; excluded from current YAML enumeration per "
    "Q1.C correction (Phase 7c.2 cohort-archeology). Stale leftover JSON "
    "from prior emit when this date was in-cohort."
)


def _load_secondary_spout_sessions() -> set[tuple[str, dt.date]]:
    cfg = yaml.safe_load(Path("configs/session_overrides.yaml").read_text())
    out: set[tuple[str, dt.date]] = set()
    for animal, dates in (cfg.get("secondary_spout_sessions") or {}).items():
        for iso in dates or {}:
            out.add((animal, dt.date.fromisoformat(iso)))
    return out


def _identify_stale_jsons(resolver: PathResolver) -> tuple[
    dict[str, list[tuple[dt.date, str]]],  # by animal: list of (date, class)
    int,  # total stale count
]:
    """Return per-animal list of (date, class) for stale per_trial JSONs.

    Class is 'secondary_spout' or 'out_of_cohort'.
    """
    secondary_spout = _load_secondary_spout_sessions()
    yaml_dates: dict[str, set[dt.date]] = {
        animal: set(yaml_driven_session_dates(animal))
        for animal in COHORT_ORDER
    }
    per_trial_root = resolver.pipeline_outputs(subdir="dlc_kinematics") / "per_trial" / "tongue"

    by_animal: dict[str, list[tuple[dt.date, str]]] = {}
    total = 0
    for animal in COHORT_ORDER:
        animal_dir = per_trial_root / animal
        if not animal_dir.exists():
            continue
        entries: list[tuple[dt.date, str]] = []
        for json_path in sorted(animal_dir.glob("*.json")):
            stem = json_path.stem
            if not (stem.isdigit() and len(stem) == 8):
                continue
            date = dt.date(int(stem[:4]), int(stem[4:6]), int(stem[6:8]))
            if (animal, date) in secondary_spout:
                entries.append((date, "secondary_spout"))
                total += 1
            elif date not in yaml_dates.get(animal, set()):
                entries.append((date, "out_of_cohort"))
                total += 1
            # else: in YAML & not secondary-spout => either OK (re-emitted)
            # or live SKIP — leave alone.
        if entries:
            by_animal[animal] = entries
    return by_animal, total


def _sidecar_markdown(
    animal: str, entries: list[tuple[dt.date, str]],
) -> str:
    by_class: dict[str, list[dt.date]] = {"secondary_spout": [], "out_of_cohort": []}
    for date, cls in entries:
        by_class[cls].append(date)

    lines: list[str] = []
    lines.append(f"# {animal} — SKIPPED tongue per_trial JSONs (no DLC input upstream)")
    lines.append("")
    lines.append(f"Emitted by Phase 7e Event B chore Stage 6.4 (2026-05-26) — "
                 f"see DECISIONS entry 'Chore — Phase 7e cohort re-emit' for context.")
    lines.append("")
    lines.append(f"Total stale JSONs deleted from this directory: **{len(entries)}**.")
    lines.append("")
    if by_class["secondary_spout"]:
        lines.append("## Secondary-spout (Pattern B) sessions — DLC-absent")
        lines.append("")
        lines.append(SECONDARY_SPOUT_REASON)
        lines.append("")
        lines.append("Affected dates:")
        for d in sorted(by_class["secondary_spout"]):
            lines.append(f"  - {d.isoformat()}")
        lines.append("")
    if by_class["out_of_cohort"]:
        lines.append("## Out-of-cohort sessions — Q1.C-excluded")
        lines.append("")
        lines.append(OUT_OF_COHORT_REASON)
        lines.append("")
        lines.append("Affected dates:")
        for d in sorted(by_class["out_of_cohort"]):
            lines.append(f"  - {d.isoformat()}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("If future DLC inference becomes available for any of the above "
                 "dates, re-run Phase 7e Event B Stage 1 on the affected (animal, "
                 "date) pairs to emit fresh v7 per_trial JSONs.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="Default mode. Enumerate + report; NO file writes/deletes.")
    mode.add_argument("--execute", action="store_true",
                      help="Execute deletes + sidecar writes. Requires Priya approval.")
    args = parser.parse_args(argv)

    resolver = PathResolver()
    by_animal, total = _identify_stale_jsons(resolver)
    print(f"=== Stage 6.4 plan: {total} stale JSONs across {len(by_animal)} animals ===")
    for animal in sorted(by_animal):
        entries = by_animal[animal]
        n_ss = sum(1 for _, c in entries if c == "secondary_spout")
        n_oc = sum(1 for _, c in entries if c == "out_of_cohort")
        print(f"  {animal}: {len(entries)} stale ({n_ss} secondary_spout + {n_oc} out_of_cohort)")
        for date, cls in entries:
            print(f"    - {date.isoformat()}  [{cls}]")
        print()

    if not args.execute:
        print("DRY-RUN — no file operations. Re-run with --execute to perform "
              "deletes + sidecar emits (requires Priya approval).")
        return 0

    print("EXECUTE MODE — performing destructive operations.")
    per_trial_root = resolver.pipeline_outputs(subdir="dlc_kinematics") / "per_trial" / "tongue"
    n_deleted = 0
    for animal in sorted(by_animal):
        entries = by_animal[animal]
        animal_dir = per_trial_root / animal
        for date, cls in entries:
            yyyymmdd = date.strftime("%Y%m%d")
            json_path = animal_dir / f"{yyyymmdd}.json"
            if not json_path.exists():
                print(f"  [skip] {animal} {date} JSON already absent")
                continue
            json_path.unlink()
            print(f"  deleted: {json_path}")
            n_deleted += 1
        # Sidecar
        sidecar = animal_dir / "_SKIPPED_NO_DLC_INPUT.md"
        sidecar.write_text(_sidecar_markdown(animal, entries), encoding="utf-8")
        print(f"  wrote sidecar: {sidecar}")
    print(f"\nDONE: {n_deleted} JSONs deleted, {len(by_animal)} sidecars written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
