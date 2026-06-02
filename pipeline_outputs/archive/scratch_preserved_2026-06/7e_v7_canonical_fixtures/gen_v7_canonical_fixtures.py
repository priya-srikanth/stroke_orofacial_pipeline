"""Phase 7e Task 8 — generator for tests/fixtures/v7_canonical/.

Populates ``tests/fixtures/v7_canonical/`` with:

1. ``pipeline_outputs/`` subtree containing the **per-session input data**
   the 9 canonical hard trials need (4 unique sessions:
   PS54/2025-06-13, PS54/2025-05-01, PS54/2025-04-28, PS47/2025-03-14).
   Per session, the following files are copied from MICROSCOPE (read
   via the real PathResolver) into the fixture tree (write via a
   fixture-rooted PathResolver):
     - ``dlc_kinematics/interpolated_traces/tongue/<animal>/<date>.parquet``
     - ``spout_behavior/licks_and_rewards/<animal>/<date>.npz``
     - ``dlc_analysis/alignment_templates/cam2/<animal>/<date>.npz``
   Total fixture footprint: ~15-40 MB across 4 sessions.

2. ``expected_outputs.json`` — JSON sidecar of the scratch v7 reference
   outputs for each of the 9 canonical trials. Schema per
   ``tests/test_v7_parity.py:_load_sidecar`` docstring.

USAGE (must be run from a session with MICROSCOPE mounted; the Cowork
Linux sandbox cannot reach MICROSCOPE):

    conda activate stroke_orofacial
    python .scratch_phase_7e/gen_v7_canonical_fixtures.py

After successful run, commit the new ``tests/fixtures/v7_canonical/``
tree (parquets + NPZs + JSON) and confirm
``pytest tests/test_v7_parity.py -v`` reports 9 passing tests (the
``pytestmark.skipif`` will auto-flip from skipped to live once the
sidecar JSON exists).

DESIGN NOTES:

- The generator runs the SCRATCH v7 (``.scratch_phase_9_1/
  inv_p3a_step2j_unified_preclean.py``) to produce the sidecar JSON.
  This makes the sidecar a frozen snapshot of the scratch reference
  at the date of generation — the test then asserts production matches
  the snapshot (with the 3 EXPECTED-PER-ADDENDUM-1 divergences as
  by-design slack). If the scratch reference changes in the future,
  re-run this generator.
- Input fixtures are copied byte-for-byte from MICROSCOPE so the
  test runs against frozen data even if upstream phases re-emit.
- Generator deliberately writes via direct ``shutil.copyfile`` rather
  than through pandas/numpy round-trips to preserve exact bytes
  (matters for parquet schema metadata + NPZ allow_pickle settings).
"""

from __future__ import annotations

import datetime
import json
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO / "tests" / "fixtures" / "v7_canonical"
FIXTURE_OUTPUTS = FIXTURE_ROOT / "pipeline_outputs"
SIDECAR_JSON = FIXTURE_ROOT / "expected_outputs.json"

# Make the scratch v7 reference importable.
sys.path.insert(0, str(REPO / ".scratch_phase_9_1"))

# Scratch reference: SINGLES = the 9 canonical trials.
from inv_p3a_step2j_unified_preclean import (  # noqa: E402
    SINGLES,
    evaluate_trial,
    load_session,
)
from stroke_orofacial.animals import get_animal  # noqa: E402
from stroke_orofacial.manifest import build_manifest  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402


def _unique_sessions() -> list[tuple[str, str]]:
    """Return unique (animal, date_str) pairs across CANONICAL_TRIALS."""
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for animal, date_str, _trial, _side, _label in SINGLES:
        key = (animal, date_str)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _copy_session_inputs(
    animal: str,
    date_str: str,
    prod_resolver: PathResolver,
    fixture_resolver: PathResolver,
) -> dict:
    """Copy the 3 input files for one session from MICROSCOPE to fixture tree.

    Returns a dict of {kind: (src, dst, size_bytes)} for logging.
    """
    date = datetime.date.fromisoformat(date_str)
    copied: dict[str, tuple[Path, Path, int]] = {}

    # 1. interpolated_traces parquet (always present at production output_root).
    src_parq = prod_resolver.interpolated_trace(
        bodypart="tongue", animal=animal, date=date,
    )
    if not src_parq.exists():
        raise FileNotFoundError(
            f"Missing interpolated_trace parquet for {animal}/{date_str}: "
            f"{src_parq}",
        )
    dst_parq = fixture_resolver.interpolated_trace(
        bodypart="tongue", animal=animal, date=date,
    )
    dst_parq.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_parq, dst_parq)
    copied["interpolated_trace"] = (src_parq, dst_parq, dst_parq.stat().st_size)

    # 2. spout_licks_and_rewards NPZ.
    src_npz = prod_resolver.spout_licks_and_rewards_npz(animal, date)
    if not src_npz.exists():
        raise FileNotFoundError(
            f"Missing spout licks NPZ for {animal}/{date_str}: {src_npz}",
        )
    dst_npz = fixture_resolver.spout_licks_and_rewards_npz(animal, date)
    dst_npz.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_npz, dst_npz)
    copied["spout_licks_npz"] = (src_npz, dst_npz, dst_npz.stat().st_size)

    # 3. alignment template (cam2) — use the "for_reading" resolver which
    # honors the prefer-new + fallback-legacy chain.
    src_aln = prod_resolver.alignment_template_for_reading(animal, date, cam="cam2")
    if not src_aln.exists():
        raise FileNotFoundError(
            f"Missing alignment template for {animal}/{date_str}: {src_aln}",
        )
    # Write to the NEW canonical alignment-template location (under
    # pipeline_outputs) so the fixture resolver's prefer-new branch picks
    # it up without needing a legacy-fallback path.
    fixture_outputs_root = FIXTURE_OUTPUTS
    dst_aln = (
        fixture_outputs_root / "dlc_analysis" / "alignment_templates"
        / "cam2" / animal / f"{date_str.replace('-', '')}.npz"
    )
    dst_aln.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_aln, dst_aln)
    copied["alignment_template"] = (src_aln, dst_aln, dst_aln.stat().st_size)

    return copied


def _emit_sidecar_entry(
    animal: str,
    date_str: str,
    trial: int,
    side: str,
) -> dict:
    """Run scratch v7 on one canonical trial; return sidecar JSON entry.

    Schema: {n_kept, licks: [{t_ms, y, x, imputed, source}, ...]}
    """
    date = datetime.date.fromisoformat(date_str)
    sess = load_session(animal, date)
    sess["animal"] = animal
    r = evaluate_trial(sess, trial, side)
    kept_decisions = [d for d in r["decisions"] if d["keep"]]
    kept_decisions.sort(key=lambda d: d["t_ms"])

    # Scratch's decision dict carries t_ms, y, src, imputed; x may or
    # may not be present depending on whether the scratch reference
    # records it for that decision. Try several plausible keys.
    licks = []
    for d in kept_decisions:
        x_val = d.get("x")
        if x_val is None:
            x_val = d.get("peak_x")
        if x_val is None:
            x_val = d.get("new_peak_x")
        licks.append({
            "t_ms": float(d["t_ms"]),
            "y": float(d["y"]),
            "x": float(x_val) if x_val is not None else None,
            "imputed": bool(d.get("imputed", False)),
            "source": str(d["src"]),
        })

    return {"n_kept": len(licks), "licks": licks}


def main() -> int:
    print("=" * 80)
    print("Phase 7e fixture generator — populating tests/fixtures/v7_canonical/")
    print("=" * 80)

    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)

    # Production resolver = real (MICROSCOPE-rooted) PathResolver.
    prod_resolver = PathResolver()
    fixture_resolver = PathResolver(output_root=FIXTURE_OUTPUTS)

    # Step 1: copy per-session input fixtures.
    print("\n[1/2] Copying per-session input fixtures...")
    sessions = _unique_sessions()
    total_bytes = 0
    for animal, date_str in sessions:
        print(f"  {animal}/{date_str}: ", end="")
        try:
            copied = _copy_session_inputs(
                animal, date_str, prod_resolver, fixture_resolver,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL — {exc!r}")
            return 1
        sizes_kb = {k: v[2] / 1024.0 for k, v in copied.items()}
        print(
            f"OK ({sizes_kb['interpolated_trace']:.0f} KB parquet + "
            f"{sizes_kb['spout_licks_npz']:.0f} KB licks NPZ + "
            f"{sizes_kb['alignment_template']:.0f} KB align NPZ)",
        )
        total_bytes += sum(v[2] for v in copied.values())
    print(f"  Total input-fixture footprint: {total_bytes / 1024.0 / 1024.0:.1f} MB")

    # Step 2: run scratch v7 on each canonical trial; build sidecar JSON.
    print("\n[2/2] Running scratch v7 on 9 canonical trials...")
    sidecar: dict[str, dict] = {}
    for animal, date_str, trial, side, label in SINGLES:
        key = f"{animal}_{date_str}_{trial}{side}"
        print(f"  {key} ({label}): ", end="")
        try:
            entry = _emit_sidecar_entry(animal, date_str, trial, side)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL — {exc!r}")
            return 1
        sidecar[key] = entry
        print(f"OK (n_kept={entry['n_kept']})")

    SIDECAR_JSON.write_text(json.dumps(sidecar, indent=2, sort_keys=True))
    print(f"\n  Wrote sidecar JSON: {SIDECAR_JSON} "
          f"({SIDECAR_JSON.stat().st_size / 1024.0:.1f} KB)")

    print("\n" + "=" * 80)
    print("DONE. Next steps:")
    print("  1. `git add tests/fixtures/v7_canonical/`")
    print("  2. `git status` — confirm 4 session-trees + expected_outputs.json")
    print("  3. `pytest tests/test_v7_parity.py -v` — should show 9 passing")
    print("  4. Commit + push (matches the close-PR's CC follow-up plan).")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
