"""Phase 8a.10 Task 0.75 — capture legacy SVG baselines for the
sub-deliverable A parity gate.

Source (read-only): legacy ``basic_behavior_analysis3/<mouse>/*.svg``
per-mouse aggregate plots. These were rendered by Priya's prior
production runs of ``batch_process_behavior_report_20260116PS.ipynb``
(mtimes 2025-06-13 for PS46-50, 2025-06-26 for PS51/54/55). Per the
Task 0.5 extension audit, these are the canonical legacy parity
reference for sub-deliverable A.

Destination (durable, version-controlled):
  ``tests/scripts/_baselines/phase_8a_10/legacy_svgs/<mouse>/<plot_family>.svg``

Also writes a manifest at
``tests/scripts/_baselines/phase_8a_10/manifest.json`` recording per-SVG
metadata (source path, dest path, SHA256, source mtime, size). The
manifest provides durable provenance — if the source SVGs are later
modified or re-rendered on MICROSCOPE, the SHA256s here mark the
parity-baseline state at capture time.

**Path resolution.** Source dir lives under the ``local_processed_spout``
logical root (per ``configs/paths.yaml``); concretely:
``{local_processed_spout}/basic_behavior_analysis3/<mouse>/``. A
dedicated PathResolver helper isn't added in this PR — for a one-off
chore script the inline path construction is clear; if sub-deliverable A
needs cohort-summary plot lookups later, a helper can land then.

**CLAUDE.md compliance.** Read-only on the legacy source data; never
writes to ``basic_behavior_analysis3/``. All writes land under
``tests/scripts/_baselines/phase_8a_10/`` (a new subtree) + the
manifest JSON next to it.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from stroke_orofacial.paths import PathResolver


# Cohort A animals (per Task 0.5 extension audit; kickoff Cohort scope
# section). PS52/PS53 have legacy outputs too but are out of Phase 8a.10
# scope.
COHORT_A_ANIMALS: tuple[str, ...] = (
    "PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55",
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINES_ROOT = REPO_ROOT / "tests" / "scripts" / "_baselines" / "phase_8a_10"
LEGACY_SVGS_DEST = BASELINES_ROOT / "legacy_svgs"
MANIFEST_PATH = BASELINES_ROOT / "manifest.json"

SCRIPT_RELPATH_FROM_REPO_ROOT = (
    "scripts/phase_8a_10/capture_legacy_svg_baselines.py"
)


def _git_rev_parse_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _capture_svg(
    src: Path, animal: str, dest_root: Path, repo_root: Path,
) -> dict:
    """Copy one SVG to the durable baselines tree + return its metadata."""
    plot_family = src.stem
    dest_dir = dest_root / animal
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)  # preserves mtime
    sha = _sha256_of_file(src)
    src_stat = src.stat()
    src_mtime_iso = datetime.datetime.fromtimestamp(
        src_stat.st_mtime, tz=datetime.timezone.utc,
    ).isoformat()
    # dest_path as repo-relative POSIX string for the manifest
    dest_rel = dest.relative_to(repo_root).as_posix()
    return {
        "animal": animal,
        "plot_family": plot_family,
        "source_path": str(src),
        "dest_path": dest_rel,
        "sha256": sha,
        "source_mtime_iso": src_mtime_iso,
        "size_bytes": src_stat.st_size,
    }


def main() -> int:
    git_sha = _git_rev_parse_head()
    captured_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    resolver = PathResolver()
    source_root = resolver.root("local_processed_spout") / "basic_behavior_analysis3"

    print("=" * 72)
    print("Phase 8a.10 Task 0.75 — legacy SVG baseline capture")
    print(f"  git HEAD             : {git_sha}")
    print(f"  source (read-only)   : {source_root}")
    print(f"  dest (version-ctrl)  : {LEGACY_SVGS_DEST}")
    print(f"  manifest             : {MANIFEST_PATH}")
    print(f"  cohort animals       : {COHORT_A_ANIMALS}")
    print("=" * 72)

    if not source_root.exists():
        print(f"ERROR: source root not found: {source_root}", file=sys.stderr)
        return 1

    LEGACY_SVGS_DEST.mkdir(parents=True, exist_ok=True)

    svgs_meta: list[dict] = []
    per_animal_counts: dict[str, int] = {}

    for animal in COHORT_A_ANIMALS:
        animal_src = source_root / animal
        if not animal_src.exists():
            print(f"  WARNING: {animal} source dir missing: {animal_src}")
            per_animal_counts[animal] = 0
            continue
        svgs = sorted(animal_src.glob("*.svg"))
        per_animal_counts[animal] = len(svgs)
        for src in svgs:
            entry = _capture_svg(
                src, animal, LEGACY_SVGS_DEST, REPO_ROOT,
            )
            svgs_meta.append(entry)
        print(
            f"  {animal}: copied {len(svgs)} SVGs "
            f"(total bytes = {sum(s.stat().st_size for s in svgs):,})"
        )

    manifest = {
        "metadata": {
            "captured_at_iso": captured_at_iso,
            "captured_against_git_sha": git_sha,
            "script_path": SCRIPT_RELPATH_FROM_REPO_ROOT,
            "source_directory_microscope": str(source_root),
            "animals": list(COHORT_A_ANIMALS),
            "total_svgs_captured": len(svgs_meta),
            "per_animal_counts": per_animal_counts,
        },
        # Sort by (animal, plot_family) for stable, diff-able output
        "svgs": sorted(
            svgs_meta,
            key=lambda d: (d["animal"], d["plot_family"]),
        ),
    }

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write("\n")

    print("=" * 72)
    print(f"DONE. wrote {MANIFEST_PATH}")
    print(f"  total SVGs captured: {len(svgs_meta)}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
