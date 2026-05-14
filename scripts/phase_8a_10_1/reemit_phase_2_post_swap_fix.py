"""Phase 8a.10.1 Task 2 — cohort-wide Phase 2 re-emit driver.

Re-emits Phase 2 for every (animal, date) in the Q4.B-locked cohort scope:
Cohort A (255 bare + Pattern A multi-half PS48/20250314) + Cohort B
(14 secondary-spout b-halves; bare halves already covered by Cohort A
iter). All emits land in-place under the production
``pipeline_outputs/spout_behavior/`` tree (Option α locked 2026-05-14).

Per (animal, date) the driver:

1. sha256s the existing on-disk ``licks_and_rewards/<animal>/<date>.npz``
   (and the b-half + Pattern A per-half nested NPZs where applicable)
   BEFORE the re-emit.
2. Calls :func:`process_session_by_animal_date` — which handles Pattern A
   multi-half-merge internally and emits both halves for Pattern B
   sessions.
3. sha256s the same paths post-emit.
4. Records one manifest row per emitted NPZ.

Manifest output: ``scripts/phase_8a_10_1/reemit_manifest.csv`` (CSV
for grep-able post-hoc spot-checking).

Per-session error handling: a single-session failure logs the traceback
to that row's ``status`` field and continues with the next session.
End-of-cohort summary prints OK / errored counts + per-animal breakdown.

Production write boundary: writes to canonical PathResolver default
output_root (``stroke_orofacial_pipeline_outputs/`` on the MICROSCOPE
mount). The Commit A swap fix is in effect: every re-emit produces
post-fix on-disk NPZs (``Reward_*`` keys hold actual reward-delivery
indices; ``Tone_*`` keys hold tone-onset indices).

Run::

    conda activate stroke_orofacial
    python scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_session_overrides
from stroke_orofacial.manifest import SessionManifest
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.session_processing import (
    process_session,
    process_session_by_animal_date,
)
from stroke_orofacial.spout_behavior.visual_gate import iter_cohort_a_sessions

COHORT_A_ANIMALS = ["PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55"]

# Sessions whose WS dir contains 2 .h5 files; ``build_manifest`` /
# ``find_wavesurfer_file`` raises on the ambiguity. The hack mirrors
# the Phase 8a.10 precedent (``scripts/phase_8a_10/cohort_reemit_phase_2.py::
# DUAL_H5_HACK_SESSIONS``): directly construct a SessionManifest with
# ``wavesurfer_file`` pre-set to the chosen .h5 and call process_session()
# directly. PS55/2025-06-06 is the only known case today; the canonical
# fix (a ``wavesurfer_file_overrides:`` block in session_overrides.yaml +
# loader plumbing in manifest.py) is forward-pointer scope.
DUAL_H5_HACK_SESSIONS: dict[tuple[str, datetime.date], str] = {
    ("PS55", datetime.date(2025, 6, 6)): "stroke_0002.h5",
}

MANIFEST_PATH = Path(__file__).parent / "reemit_manifest.csv"

MANIFEST_FIELDS = (
    "animal",
    "date",
    "half_suffix",
    "npz_path",
    "pre_fix_sha256",
    "post_fix_sha256",
    "pre_fix_size_bytes",
    "post_fix_size_bytes",
    "emit_wall_time_sec",
    "status",
    "error_msg",
)


def _yyyymmdd_to_date(s: str) -> datetime.date:
    return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


def _sha256_file(path: Path) -> tuple[str | None, int | None]:
    """Return (hex digest, file size) or (None, None) if file missing."""
    if not path.exists():
        return None, None
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _resolve_pattern_a_per_half_npzs(
    overrides_config: dict,
    animal: str,
    date_str: str,
    licks_root: Path,
) -> list[tuple[str, Path]]:
    """For a Pattern A multi-half session, return [(half_id, npz_path)] pairs
    for the per-half NPZs at ``licks_and_rewards/<animal>/<date><concat>/<date><half>.npz``.
    Returns empty list when the session isn't Pattern A multi-half.
    """
    multi_half = overrides_config.get("multi_half_sessions", {}) or {}
    entry = multi_half.get(animal, {}).get(date_str)
    if entry is None:
        return []
    halves = entry.get("halves") or [{"id": "a"}, {"id": "b"}]
    half_ids = [h["id"] for h in halves]
    concat_label = "".join(half_ids)
    nested_dir = licks_root / animal / f"{date_str}{concat_label}"
    return [
        (hid, nested_dir / f"{date_str}{hid}.npz")
        for hid in half_ids
    ]


def _bare_path(licks_root: Path, animal: str, date_str: str) -> Path:
    return licks_root / animal / f"{date_str}.npz"


def _b_half_path(licks_root: Path, animal: str, date_str: str) -> Path:
    return licks_root / animal / f"{date_str}b.npz"


def _enumerate_calls(resolver: PathResolver) -> list[tuple[str, datetime.date]]:
    """Return Q4.B-scoped (animal, date) list. One call per unique (animal,
    date) pair; ``process_session_by_animal_date`` handles Pattern A merge +
    Pattern B per-half iteration internally.
    """
    calls: list[tuple[str, datetime.date]] = []
    for animal in COHORT_A_ANIMALS:
        for date_str in iter_cohort_a_sessions(
            animal, resolver, include_b_half=False,
        ):
            calls.append((animal, _yyyymmdd_to_date(date_str)))
    return calls


def main() -> None:
    resolver = PathResolver()  # production output_root
    licks_root = resolver.pipeline_outputs("spout_behavior") / "licks_and_rewards"
    overrides = load_session_overrides()
    calls = _enumerate_calls(resolver)
    print(f"Q4.B re-emit scope: {len(calls)} (animal, date) calls")
    print(f"Production licks_root: {licks_root}\n")

    rows: list[dict] = []
    n_ok = 0
    n_err = 0
    t_start = time.time()

    # Write header upfront so partial runs leave a parseable manifest.
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=MANIFEST_FIELDS).writeheader()

    def _flush() -> None:
        with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
            w.writeheader()
            w.writerows(rows)

    for i, (animal, date) in enumerate(calls):
        date_str = date.strftime("%Y%m%d")

        # Pre-emit hashes for every path this session might emit to:
        #   - bare-half: <licks_root>/<animal>/<date>.npz
        #   - b-half (Pattern B only): <licks_root>/<animal>/<date>b.npz
        #   - Pattern A per-halves (PS48/20250314 only):
        #     <licks_root>/<animal>/<date><concat>/<date><half>.npz
        bare_path = _bare_path(licks_root, animal, date_str)
        b_path = _b_half_path(licks_root, animal, date_str)
        pattern_a_halves = _resolve_pattern_a_per_half_npzs(
            overrides, animal, date_str, licks_root,
        )

        pre_bare_sha, pre_bare_size = _sha256_file(bare_path)
        pre_b_sha, pre_b_size = _sha256_file(b_path)
        pre_pa = {hid: _sha256_file(p) for hid, p in pattern_a_halves}

        # Re-emit. Use the dual-h5 hack for known-ambiguous WS dirs
        # (build_manifest's find_wavesurfer_file raises ValueError on
        # multiple .h5 matches without a wavesurfer_file_overrides:
        # registry entry).
        t0 = time.time()
        emit_error: Exception | None = None
        emitted: dict | None = None
        try:
            dual_h5 = DUAL_H5_HACK_SESSIONS.get((animal, date))
            if dual_h5 is not None:
                ws_path = resolver.wavesurfer_dir(date, animal) / dual_h5
                if not ws_path.exists():
                    raise FileNotFoundError(
                        f"Dual-h5 hack target missing: {ws_path}"
                    )
                animal_info = get_animal(animal)
                manifest = SessionManifest(
                    session_id=f"{animal}_{date.strftime('%Y%m%d')}",
                    animal=animal, date=date,
                    day_relative_to_stroke=animal_info.day_relative_to_stroke(date),
                    phase=animal_info.phase(date),
                    wavesurfer_file=ws_path,
                    wavesurfer_sides_match_mouse_sides=(
                        animal_info.wavesurfer_sides_match_mouse_sides
                    ),
                )
                paths_dict = process_session(
                    manifest, resolver,
                    overwrite="force",
                    overrides_config=overrides,
                )
                emitted = {None: paths_dict}
            else:
                emitted = process_session_by_animal_date(
                    animal, date, resolver, overwrite="force",
                    overrides_config=overrides,
                )
        except Exception as exc:
            emit_error = exc
        elapsed = time.time() - t0

        if emit_error is not None:
            tb = traceback.format_exc()
            rows.append({
                "animal": animal, "date": date_str, "half_suffix": "",
                "npz_path": str(bare_path),
                "pre_fix_sha256": pre_bare_sha, "post_fix_sha256": None,
                "pre_fix_size_bytes": pre_bare_size, "post_fix_size_bytes": None,
                "emit_wall_time_sec": round(elapsed, 3),
                "status": f"ERROR_{type(emit_error).__name__}",
                "error_msg": str(emit_error).replace("\n", " | ")[:500],
            })
            n_err += 1
            print(
                f"[{i+1}/{len(calls)}] {animal}/{date_str} ERROR: "
                f"{type(emit_error).__name__}: {emit_error}"
            )
            # Save the full traceback to a side file for debugging.
            with open(MANIFEST_PATH.with_suffix(".errors.txt"), "a", encoding="utf-8") as ef:
                ef.write(f"\n=== {animal}/{date_str} ===\n{tb}\n")
            if (i + 1) % 5 == 0:
                _flush()
            continue

        # Post-emit hashes (same paths as pre-emit).
        post_bare_sha, post_bare_size = _sha256_file(bare_path)
        bare_status = "OK" if post_bare_sha else "ERROR_no_post_fix_file"
        rows.append({
            "animal": animal, "date": date_str, "half_suffix": "",
            "npz_path": str(bare_path),
            "pre_fix_sha256": pre_bare_sha, "post_fix_sha256": post_bare_sha,
            "pre_fix_size_bytes": pre_bare_size, "post_fix_size_bytes": post_bare_size,
            "emit_wall_time_sec": round(elapsed, 3),
            "status": bare_status, "error_msg": "",
        })
        if bare_status == "OK":
            n_ok += 1
        else:
            n_err += 1

        # Pattern B b-half row (only when "b" suffix is in the emitted dict).
        if emitted and "b" in emitted:
            post_b_sha, post_b_size = _sha256_file(b_path)
            b_status = "OK" if post_b_sha else "ERROR_no_post_fix_file"
            rows.append({
                "animal": animal, "date": date_str, "half_suffix": "b",
                "npz_path": str(b_path),
                "pre_fix_sha256": pre_b_sha, "post_fix_sha256": post_b_sha,
                "pre_fix_size_bytes": pre_b_size, "post_fix_size_bytes": post_b_size,
                "emit_wall_time_sec": 0.0,  # part of the parent call's elapsed
                "status": b_status, "error_msg": "",
            })
            if b_status == "OK":
                n_ok += 1
            else:
                n_err += 1

        # Pattern A per-half rows.
        for hid, p in pattern_a_halves:
            pre_sha, pre_size = pre_pa.get(hid, (None, None))
            post_sha, post_size = _sha256_file(p)
            pa_status = "OK" if post_sha else "ERROR_no_post_fix_file"
            rows.append({
                "animal": animal, "date": date_str, "half_suffix": hid,
                "npz_path": str(p),
                "pre_fix_sha256": pre_sha, "post_fix_sha256": post_sha,
                "pre_fix_size_bytes": pre_size, "post_fix_size_bytes": post_size,
                "emit_wall_time_sec": 0.0,
                "status": pa_status, "error_msg": "",
            })
            if pa_status == "OK":
                n_ok += 1
            else:
                n_err += 1

        if (i + 1) % 10 == 0:
            total = time.time() - t_start
            rate = (i + 1) / total if total > 0 else 0
            eta = (len(calls) - i - 1) / rate if rate > 0 else 0
            print(
                f"[{i+1}/{len(calls)}] {animal}/{date_str} "
                f"({elapsed:.1f}s) — total {total:.0f}s, ETA {eta:.0f}s, "
                f"{len(rows)} rows ({n_ok} OK, {n_err} err)"
            )
            _flush()

    _flush()

    total = time.time() - t_start
    print(
        f"\nDone. {len(rows)} manifest rows. {n_ok} OK, {n_err} errored. "
        f"Total wall time: {total:.0f}s "
        f"({total/60:.1f} min).\n"
        f"Manifest: {MANIFEST_PATH}"
    )

    # End-of-run per-animal breakdown.
    by_animal: dict[str, dict[str, int]] = {}
    for r in rows:
        a = r["animal"]
        if a not in by_animal:
            by_animal[a] = {"ok": 0, "err": 0}
        if r["status"] == "OK":
            by_animal[a]["ok"] += 1
        else:
            by_animal[a]["err"] += 1
    print("\nPer-animal breakdown (OK / err):")
    for a in sorted(by_animal):
        s = by_animal[a]
        print(f"  {a}: {s['ok']} OK, {s['err']} err")


if __name__ == "__main__":
    main()
