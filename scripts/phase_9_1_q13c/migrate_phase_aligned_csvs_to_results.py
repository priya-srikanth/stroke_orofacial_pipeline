"""Phase 9.1 Q-lock 13c Addendum #2 (Q13c-K) — migrate trajectory CSVs.

Moves all ``*.csv`` files under
``pipeline_outputs/stats/figures/phenotype_pooled/phase_aligned_trajectories/``
to the analog path under ``stats/results/phenotype_pooled/phase_aligned_trajectories/``,
preserving the relative subpath structure (root, ``null_calibration/``,
``3_phenotype/``, ``3_phenotype/null_calibration/``, etc.).

Project-wide convention split (per ``runners.py`` axis tree,
``latency_hist_cdf.py:11``, ``phenotype_pooled_spatial.py:4``):

  - ``stats/figures/`` → SVG/PNG renders
  - ``stats/results/`` → numerical CSV outputs

Q-lock 13 originally emitted both to ``stats/figures/...`` (mixed
tree). Addendum #2 separates them. SVGs stay; CSVs migrate.

Safety guards
-------------
- Refuses to run if any destination file already exists (no
  accidental overwrite of a partial prior migration).
- Writes a manifest CSV at ``<results-tree>/migration_manifest.csv``
  recording every move (src + dst + size_bytes + sha256).
- ``--dry-run`` reports what would move without touching anything.

Per CLAUDE.md GR7: ``shutil.move`` writes to ``pipeline_outputs/`` and
is destructive on the figures-tree CSVs. STOP-and-ask Priya before
running without ``--dry-run``. After approval, run once; manifest +
preserved SHA256s provide an audit trail.

Usage
-----
::

    # Dry run first — reports the move plan with no side effects.
    python scripts/phase_9_1_q13c/migrate_phase_aligned_csvs_to_results.py --dry-run

    # Actual migration (requires Priya approval per GR7).
    python scripts/phase_9_1_q13c/migrate_phase_aligned_csvs_to_results.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import shutil
import sys
from pathlib import Path

from stroke_orofacial.paths import PathResolver

log = logging.getLogger("phase_9_1_q13c.migrate")

# Q-lock 13c Addendum #2 path mapping.
FIGURES_SUBDIR = "stats/figures/phenotype_pooled/phase_aligned_trajectories"
RESULTS_SUBDIR = "stats/results/phenotype_pooled/phase_aligned_trajectories"

MANIFEST_HEADER = ["src", "dst", "size_bytes", "sha256"]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _enumerate_csvs(figures_root: Path) -> list[Path]:
    """All CSVs under ``figures_root`` (recursive)."""
    if not figures_root.exists():
        return []
    return sorted(figures_root.rglob("*.csv"))


def _planned_moves(
    figures_root: Path, results_root: Path,
) -> list[tuple[Path, Path]]:
    """Return [(src, dst), ...] for every CSV under figures_root."""
    pairs: list[tuple[Path, Path]] = []
    for src in _enumerate_csvs(figures_root):
        rel = src.relative_to(figures_root)
        dst = results_root / rel
        pairs.append((src, dst))
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Report planned moves without touching anything. Always run "
            "this first to sanity-check the migration scope."
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    resolver = PathResolver()
    figures_root = resolver.pipeline_outputs(subdir=FIGURES_SUBDIR)
    results_root = resolver.pipeline_outputs(subdir=RESULTS_SUBDIR)

    log.info("Figures (source) root: %s", figures_root)
    log.info("Results (destination) root: %s", results_root)

    pairs = _planned_moves(figures_root, results_root)
    log.info("Found %d CSVs under figures tree.", len(pairs))
    if not pairs:
        log.info("Nothing to migrate. Exiting cleanly.")
        return 0

    # Safety guard: destinations must not already exist.
    existing_dsts = [dst for _, dst in pairs if dst.exists()]
    if existing_dsts:
        log.error(
            "ABORT: %d destination paths already exist; refusing to overwrite.",
            len(existing_dsts),
        )
        for d in existing_dsts[:5]:
            log.error("  existing: %s", d)
        if len(existing_dsts) > 5:
            log.error("  ... and %d more.", len(existing_dsts) - 5)
        return 2

    # Print full plan.
    log.info("Planned moves:")
    for src, dst in pairs:
        rel = src.relative_to(figures_root)
        log.info("  %s\n    → %s", rel, dst)

    if args.dry_run:
        log.info("--dry-run: no changes applied. Re-run without --dry-run "
                 "to perform the migration.")
        return 0

    # Live migration. Compute SHA256 of each source BEFORE moving so the
    # manifest captures the source fingerprint as an audit trail.
    manifest_rows: list[dict[str, object]] = []
    moved = 0
    for src, dst in pairs:
        size = src.stat().st_size
        digest = _sha256(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved += 1
        manifest_rows.append({
            "src": str(src),
            "dst": str(dst),
            "size_bytes": size,
            "sha256": digest,
        })
        log.info(
            "MOVED [%d/%d] %s -> %s (%d bytes)",
            moved, len(pairs),
            src.relative_to(figures_root), dst, size,
        )

    # Write manifest at results-tree root.
    results_root.mkdir(parents=True, exist_ok=True)
    manifest_path = results_root / "migration_manifest.csv"
    write_header = not manifest_path.exists()
    mode = "a" if manifest_path.exists() else "w"
    with manifest_path.open(mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerows(manifest_rows)
    log.info("Wrote migration manifest: %s (%d rows)",
             manifest_path, len(manifest_rows))
    log.info("Migration complete: %d/%d CSVs moved.", moved, len(pairs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
