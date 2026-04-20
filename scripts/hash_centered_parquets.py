"""Baseline hash table for centered DLC parquets (Phase 4.5-lite).

Walks ``{pipeline_outputs}/dlc_analysis/centered_{mode}/{animal}/*.parquet`` for
each animal in ``configs/animals.yaml`` × each of the three centering modes and
records a SHA-256 content hash of each parquet file plus the ``_param_sig``
embedded in the filename.

Emits a markdown table on stdout suitable for pasting into MIGRATION_LOG.

As an exit-gating check, asserts that the Phase 4 parity ``_param_sig`` values
(``c23dc714`` for nose, ``2a6efb6a`` for spout_midpoint, ``b13af51c`` for
eye_midpoint) appear wherever their mode's parquet is present. A mismatch means
the param-sig hash (derived from config) has drifted from the Phase 4 values —
which Phase 4.5-lite is required to preserve.

Usage::

    python scripts/hash_centered_parquets.py

Exits 0 on success, 1 on missing-output or param-sig-drift, 2 on I/O error.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver

# Phase 4 recorded param_sig hashes (MIGRATION_LOG Phase 4 §4d).
EXPECTED_PARAM_SIG = {
    "nose": "c23dc714",
    "spout_midpoint": "2a6efb6a",
    "eye_midpoint": "b13af51c",
}

_PARAM_SIG_RE = re.compile(r"\.intermediate\.([0-9a-f]{8})\.parquet$")


def _content_hash(path: Path, chunk_size: int = 1 << 20) -> str:
    """SHA-256 of file contents, first 12 hex chars."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _extract_param_sig(filename: str) -> str | None:
    m = _PARAM_SIG_RE.search(filename)
    return m.group(1) if m else None


def _extract_date(filename: str) -> str | None:
    m = re.search(r"_(\d{4})-(\d{2})-(\d{2})T", filename)
    if not m:
        return None
    return f"{m.group(1)}{m.group(2)}{m.group(3)}"


def main() -> int:
    resolver = PathResolver()
    animals = load_animals()
    root = resolver.pipeline_outputs("dlc_analysis")

    rows = []
    drift = []
    missing_animal_dirs = []

    for animal_id in sorted(animals.keys()):
        for mode in EXPECTED_PARAM_SIG:
            animal_dir = root / f"centered_{mode}" / animal_id
            if not animal_dir.exists():
                missing_animal_dirs.append(f"{animal_id}/{mode}")
                continue
            parquets = sorted(animal_dir.glob("*.parquet"))
            if not parquets:
                missing_animal_dirs.append(f"{animal_id}/{mode} (empty)")
                continue
            for p in parquets:
                date = _extract_date(p.name) or "<unknown>"
                sig = _extract_param_sig(p.name)
                if sig != EXPECTED_PARAM_SIG[mode]:
                    drift.append((animal_id, date, mode, sig, EXPECTED_PARAM_SIG[mode], p.name))
                content = _content_hash(p)
                size_mb = p.stat().st_size / (1024 * 1024)
                rows.append((animal_id, date, mode, sig or "<missing>", content, f"{size_mb:.1f}"))

    # Emit markdown table.
    print("| Animal | Date | Mode | param_sig | content_sha256[:12] | Size (MB) |")
    print("|--------|------|------|-----------|---------------------|-----------|")
    for row in rows:
        print("| " + " | ".join(row) + " |")
    print()

    if missing_animal_dirs:
        print(f"Animals/modes with no parquets on disk ({len(missing_animal_dirs)}):")
        for m in missing_animal_dirs:
            print(f"  - {m}")
        print()

    if drift:
        print("ERROR: param_sig drift detected (Phase 4.5-lite must preserve Phase 4 values):")
        for animal, date, mode, got, want, fname in drift:
            print(f"  {animal}/{date}/{mode}: got {got}, want {want}  ({fname})")
        return 1

    # Exit-gating assertion: every mode that has ANY parquet on disk must contain
    # the expected Phase 4 param_sig at least once.
    seen_sigs = {mode: set() for mode in EXPECTED_PARAM_SIG}
    for _, _, mode, sig, _, _ in rows:
        seen_sigs[mode].add(sig)
    for mode, expected in EXPECTED_PARAM_SIG.items():
        if seen_sigs[mode] and expected not in seen_sigs[mode]:
            print(f"ERROR: mode {mode!r} on disk but expected param_sig {expected} not found.")
            return 1

    print(f"OK — {len(rows)} parquet(s) hashed; all present param_sigs match Phase 4 baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
