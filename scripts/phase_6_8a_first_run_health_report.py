"""First-run health report for Phase 6.8a tone-aligned heatmap NPZs.

**Phase 7c.1 disposition (Open Q §5.1):** this script reads the
LEGACY `spatial_reward_aligned/` on-disk tree (NPZ schema key
``n_rewards``, output subdir ``spatial_reward_aligned/``). Phase 7c.1
renamed the source-side emission to ``spatial_tone_aligned/`` + NPZ
key ``n_tones`` for new emits; legacy NPZs at the old paths still
carry the old key. This script remains pointed at the legacy tree
to continue serving its purpose for legacy-tree audits. The script
retires alongside the legacy tree in **Phase 7c.2 Task 5** (legacy-
path cleanup, post cohort-wide re-emit verification).

After Priya executes notebook 12 under the mouse-frame convention, this
script walks the emitted heatmap NPZ tree and confirms the outputs are
internally consistent. Phase 6 has no legacy array-level reference (cell
16 was never run to save outputs on MICROSCOPE pre-consolidation), so
this script is the sanity gate that stands in for parity testing.

Checks performed per (animal, date, bodypart, center_mode, window,
trial_group) NPZ:

1. **Stamp presence.** Every NPZ has both ``wavesurfer_sides_match_mouse_sides``
   and ``side_convention_version`` — missing stamp means a writer
   regression (someone bypassed ``save_tone_aligned_npz``).
2. **Stamp matches ``configs/animals.yaml``.** The NPZ's
   ``wavesurfer_sides_match_mouse_sides`` equals
   ``AnimalInfo.wavesurfer_sides_match_mouse_sides``. A mismatch means
   the yaml was edited after the NPZ was emitted and a re-emit is
   required (runbook §4).
3. **Stamp version matches code.** NPZ's ``side_convention_version``
   equals :data:`SIDE_CONVENTION_VERSION`.
4. **L + R counts = all counts.** For each (animal, date, bodypart,
   center_mode, window_ms), ``n_rewards`` satisfies
   ``n_rewards[all] == n_rewards[L] + n_rewards[R]`` (the wavesurfer
   frame this inequality already held under task #17's Phase 2 re-emit;
   verify it survived the Phase 6 trial_group translation).
5. **H_counts sanity.** ``H_counts.sum() > 0`` for non-empty sessions,
   and ``H_proportion.sum()`` is close to 1.0 (the normalization
   invariant).
6. **Consistent metadata within a (bodypart, center_mode, window).**
   ``bodypart`` / ``center_mode`` / ``window_ms`` / ``nbins`` / axis
   limits are invariant across the L/R/all siblings. (Drift here
   signals the notebook was patched mid-batch.)

Usage::

    python scripts/phase_6_8a_first_run_health_report.py
    python scripts/phase_6_8a_first_run_health_report.py --animals PS46
    python scripts/phase_6_8a_first_run_health_report.py --verbose

Exit codes:
    0 — all checks pass
    1 — at least one check failed (details on stdout)
    2 — no NPZs found (output tree empty; did you run notebook 12?)
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from stroke_orofacial.animals import load_animals
from stroke_orofacial.lr_convention import (
    SIDE_CONVENTION_MATCH_KEY,
    SIDE_CONVENTION_VERSION,
    SIDE_CONVENTION_VERSION_KEY,
)
from stroke_orofacial.paths import PathResolver


def _iter_heatmap_npzs(root: Path):
    """Yield every heatmap NPZ under the Phase 6 output tree along with
    the parsed (animal, date, bodypart, center_mode, window_slug,
    trial_slug) tuple from its path."""
    if not root.exists():
        return
    # Layout: {root}/{bodypart}_{center_mode}/trials-{group}_{win_tag}/
    #           {animal}/heatmap_{YYYYMMDD}.npz
    for bp_mode_dir in sorted(root.iterdir()):
        if not bp_mode_dir.is_dir() or "_" not in bp_mode_dir.name:
            continue
        # Split bodypart_centermode — center_mode can be multi-token
        # (e.g. "spout_midpoint") so split on first "_" once.
        bodypart, _, center_mode = bp_mode_dir.name.partition("_")
        for trials_dir in sorted(bp_mode_dir.iterdir()):
            if not trials_dir.is_dir() or not trials_dir.name.startswith("trials-"):
                continue
            # trials-{group}_{win_tag} e.g. trials-L_-500to5000ms
            stripped = trials_dir.name[len("trials-"):]
            group, _, win_slug = stripped.partition("_")
            for animal_dir in sorted(trials_dir.iterdir()):
                if not animal_dir.is_dir():
                    continue
                animal = animal_dir.name
                for npz in sorted(animal_dir.glob("heatmap_*.npz")):
                    date_str = npz.stem.removeprefix("heatmap_")
                    yield {
                        "path": npz,
                        "animal": animal,
                        "date_str": date_str,
                        "bodypart": bodypart,
                        "center_mode": center_mode,
                        "window_slug": win_slug,
                        "trial_group": group,
                    }


def _check_one_npz(
    info: dict[str, Any],
    expected_match_flag: bool | None,
) -> list[str]:
    """Run the per-NPZ checks. Returns a list of human-readable failure
    strings (empty = all pass)."""
    fails: list[str] = []
    path = info["path"]
    try:
        data = np.load(path, allow_pickle=True)
    except Exception as e:  # noqa: BLE001 — want broad catch for the diagnostic
        return [f"{path}: could not load ({e!r})"]

    # 1. Stamp presence
    if SIDE_CONVENTION_VERSION_KEY not in data.files:
        fails.append(f"{path}: missing {SIDE_CONVENTION_VERSION_KEY}")
        return fails  # no point checking further if unstamped
    if SIDE_CONVENTION_MATCH_KEY not in data.files:
        fails.append(f"{path}: missing {SIDE_CONVENTION_MATCH_KEY}")
        return fails

    # 3. Version matches code
    stamped_version = int(data[SIDE_CONVENTION_VERSION_KEY])
    if stamped_version != SIDE_CONVENTION_VERSION:
        fails.append(
            f"{path}: side_convention_version={stamped_version} "
            f"but code expects {SIDE_CONVENTION_VERSION}"
        )

    # 2. Stamp matches AnimalInfo
    stamped_match = bool(data[SIDE_CONVENTION_MATCH_KEY])
    if expected_match_flag is not None and stamped_match != expected_match_flag:
        fails.append(
            f"{path}: stamp {SIDE_CONVENTION_MATCH_KEY}={stamped_match} "
            f"disagrees with animals.yaml={expected_match_flag}. Re-emit "
            f"required (runbook §4)."
        )

    # 5. H_counts sanity
    if "H_counts" not in data.files:
        fails.append(f"{path}: missing H_counts")
    else:
        h = data["H_counts"]
        if h.sum() == 0:
            # Not necessarily a failure — a session with no tone events
            # or all frames masked out would produce zero counts. Emit an
            # info note, not a fail.
            pass
        else:
            prop_sum = float(data["H_proportion"].sum())
            if not (0.99 < prop_sum < 1.01):
                fails.append(
                    f"{path}: H_proportion.sum()={prop_sum:.6f} "
                    f"(expected ~1.0; bad normalization)"
                )

    return fails


def _check_lr_all_consistency(
    npzs_by_group: dict[str, dict[str, Any]],
    key_label: str,
) -> list[str]:
    """For a single (animal, date, bodypart, center_mode, window),
    confirm n_rewards['all'] == n_rewards['L'] + n_rewards['R']."""
    fails: list[str] = []
    have = set(npzs_by_group.keys())
    if not {"all", "L", "R"}.issubset(have):
        missing = sorted({"all", "L", "R"} - have)
        fails.append(
            f"{key_label}: missing trial_group NPZ(s): {missing}"
        )
        return fails
    try:
        n_all = int(np.load(npzs_by_group["all"]["path"])["n_rewards"])
        n_L = int(np.load(npzs_by_group["L"]["path"])["n_rewards"])
        n_R = int(np.load(npzs_by_group["R"]["path"])["n_rewards"])
    except Exception as e:  # noqa: BLE001
        return [f"{key_label}: could not read n_rewards ({e!r})"]
    if n_all != n_L + n_R:
        fails.append(
            f"{key_label}: n_rewards[all]={n_all} but L+R={n_L + n_R} "
            f"(L={n_L}, R={n_R})"
        )
    return fails


def _check_metadata_consistency(
    npzs_by_group: dict[str, dict[str, Any]],
    key_label: str,
) -> list[str]:
    """Ensure bodypart / center_mode / window_ms / nbins / axis limits
    agree across the L/R/all siblings of one (animal, date, bodypart,
    center_mode, window_slug) bundle. Drift here would mean the
    notebook's USER INPUTS were edited mid-loop."""
    fails: list[str] = []
    scalars = ("bodypart", "center_mode", "nbins")
    arrays = ("window_ms", "x_limits", "y_limits")
    ref = None
    for group, info in npzs_by_group.items():
        try:
            data = np.load(info["path"], allow_pickle=True)
        except Exception as e:  # noqa: BLE001
            fails.append(f"{key_label}/{group}: could not reload ({e!r})")
            continue
        snapshot = {
            **{k: str(data[k]) if k in data.files else None for k in scalars},
            **{
                k: tuple(data[k].tolist()) if k in data.files else None
                for k in arrays
            },
        }
        if ref is None:
            ref = snapshot
            ref_group = group
            continue
        for k, v in snapshot.items():
            if ref[k] != v:
                fails.append(
                    f"{key_label}: metadata[{k}] differs between "
                    f"group={ref_group} ({ref[k]!r}) and group={group} "
                    f"({v!r})"
                )
    return fails


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--animals",
        nargs="*",
        default=None,
        help="Animal IDs to check. Default: every animal in animals.yaml "
             "with outputs under the Phase 6 tree.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print per-NPZ pass lines in addition to failures.",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    animals = load_animals()
    spatial_root = resolver.pipeline_outputs("dlc_analysis") / "spatial_reward_aligned"

    if not spatial_root.exists():
        print(f"ERROR: output tree does not exist: {spatial_root}")
        print("       Run notebook 12 first.")
        return 2

    all_infos = list(_iter_heatmap_npzs(spatial_root))
    if args.animals is not None:
        all_infos = [i for i in all_infos if i["animal"] in set(args.animals)]

    if not all_infos:
        print(f"ERROR: no heatmap NPZs found under {spatial_root}")
        return 2

    total_npzs = len(all_infos)
    total_fails: list[str] = []

    # Per-NPZ checks (stamp presence + metadata sanity).
    n_pass = 0
    for info in all_infos:
        expected = None
        if info["animal"] in animals:
            expected = animals[info["animal"]].wavesurfer_sides_match_mouse_sides
        fails = _check_one_npz(info, expected)
        if fails:
            total_fails.extend(fails)
        else:
            n_pass += 1
            if args.verbose:
                print(f"  OK {info['path']}")

    # Bundle-level checks (L+R=all and metadata consistency within
    # (animal, date, bodypart, center_mode, window_slug)).
    bundles: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for info in all_infos:
        key = (
            info["animal"], info["date_str"],
            info["bodypart"], info["center_mode"], info["window_slug"],
        )
        bundles[key][info["trial_group"]] = info

    n_bundles_checked = 0
    n_bundles_pass = 0
    for key, by_group in bundles.items():
        key_label = (
            f"{key[0]}/{key[1]}/{key[2]}/{key[3]}/{key[4]}"
        )
        fails = []
        fails.extend(_check_lr_all_consistency(by_group, key_label))
        fails.extend(_check_metadata_consistency(by_group, key_label))
        n_bundles_checked += 1
        if fails:
            total_fails.extend(fails)
        else:
            n_bundles_pass += 1

    print("\n=== Phase 6.8a first-run health report ===")
    print(f"NPZ files checked:  {total_npzs}")
    print(f"  per-NPZ pass:     {n_pass}/{total_npzs}")
    print(f"Bundles checked:    {n_bundles_checked}")
    print(f"  bundle pass:      {n_bundles_pass}/{n_bundles_checked}")
    print(f"Total failures:     {len(total_fails)}")
    if total_fails:
        print("\nFailures:")
        for f in total_fails:
            print(f"  {f}")
        return 1
    print("\nALL CHECKS PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
