"""Stage 1.5 — path normalization for phenotype-pooled outputs.

Chore ``vChore-dlc-pooled-phenotype-unification``. Pure file-move operation
(NO re-rendering): migrates the existing ``stats/figures/phenotype_pooled/``
and ``stats/results/phenotype_pooled/`` trees to the locked symmetric
``<family>/<scope>/{no_filter,}/<files>`` convention.

Target convention (locked 2026-05-29 + Stage 0 classification answers):

  * **Scope subdirs** ``4_tier`` / ``3_tier`` replace the implicit-4-tier
    root level + the legacy ``3_phenotype/`` subdir. After normalization
    **zero** ``3_phenotype/`` directories remain anywhere in the tree.
  * **``no_filter/`` layer** is added ONLY for DLC-*filterable* families —
    i.e. metrics that have a ``stats/inputs/filtered_v1/<slug>/`` input and
    will therefore get a ``v2/`` filtered re-emit in Stages 2-4. Concretely:
    the 4 figure families (proportion_diff_heatmaps, wasserstein_recovery,
    phase_aligned_trajectories, phase_aligned_endpoints) and the 23
    ``tongue_*`` scalar metrics.
  * **Flat scope** (``<scope>/<files>``, no ``no_filter/``) for everything
    with no filtered counterpart: the 6 ``jaw_*`` scalars,
    ``mismatch_candidate_no_lick_with_jaw_move`` (DLC-derived but never
    lick-filtered — Priya 2026-05-29), and the 12 spout-behavior scalars.

Classification rule (data-driven): a **scalar** metric gets ``no_filter/``
iff it has a ``filtered_v1`` input dir. This is read live from disk, so if
jaw filtering is ever added the slug auto-promotes. For the current cohort
this is exactly the 23 ``tongue_*`` slugs (verified Stage 0).

Move layout
-----------
For a **filterable** family/scalar ``F``::

    F/<root files + nested subdirs e.g. null_calibration/, sd_band/>
        → F/4_tier/no_filter/<...>
    F/3_phenotype/<...>                  → F/3_tier/no_filter/<...>
    <pp>/3_phenotype/F/<...>  (scalars)  → <pp>/F/3_tier/no_filter/<...>

For a **flat** scalar ``S``::

    S/<root files>                       → S/4_tier/<...>
    <pp>/3_phenotype/S/<...>             → S/3_tier/<...>

Only ``.svg`` / ``.png`` / ``.csv`` files are moved. Windows ``Thumbs.db``
(and any other non-output file) is left in place and reported — it is not a
pipeline output, and deleting it would be a destructive op requiring its own
GR7 approval. (Its presence means the emptied ``3_phenotype/`` dirs may not
be ``rmdir``-able; the dry-run reports exactly which dirs that affects.)

A migration manifest is written to
``stats/sensitivity/dlc_pooled_phenotype_path_normalization_manifest.csv``
(one row per planned/executed move) ONLY in ``--execute`` mode.

Idempotent: files already living under a ``4_tier/`` or ``3_tier/`` segment
are skipped, so re-running after a successful (or partial) move is a no-op.

Usage::

    python -m scripts.chore_dlc_pooled_phenotype.path_normalization            # dry-run (default)
    python -m scripts.chore_dlc_pooled_phenotype.path_normalization --execute  # actually move

**GR7: ``--execute`` is a destructive op on the share — requires Priya's
per-invocation approval. Default is dry-run.**
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path
from typing import NamedTuple

from stroke_orofacial.paths import PathResolver

# ---------------------------------------------------------------------------
# Convention constants
# ---------------------------------------------------------------------------

SCOPE_4TIER = "4_tier"
SCOPE_3TIER = "3_tier"
NO_FILTER = "no_filter"
LEGACY_3TIER_DIRNAME = "3_phenotype"

#: Scope-marker dir names — files already nested under one are pre-migrated.
_SCOPE_MARKERS: frozenset[str] = frozenset({SCOPE_4TIER, SCOPE_3TIER})

#: The 4 figure families and their manifest ``metric_family_type``. All are
#: DLC-filterable (Stages 2-4 emit their ``v2/`` from filtered_v1), so all
#: get the ``no_filter/`` layer.
FAMILY_TYPES: dict[str, str] = {
    "proportion_diff_heatmaps": "heatmap",
    "wasserstein_recovery": "w2",
    "phase_aligned_trajectories": "trajectory",
    "phase_aligned_endpoints": "endpoint_stats",
}

#: Only these extensions are pipeline outputs we migrate.
MOVABLE_EXTS: frozenset[str] = frozenset({".svg", ".png", ".csv"})

MANIFEST_RELPATH = (
    "sensitivity/dlc_pooled_phenotype_path_normalization_manifest.csv"
)


class Move(NamedTuple):
    """A single planned file move."""

    src: Path
    dst: Path
    metric_family_type: str  # dlc | spout | heatmap | trajectory | endpoint_stats | w2
    scope_tier: str          # 4_tier | 3_tier
    scope_layout: str        # no_filter | flat
    size_bytes: int


class SkippedFile(NamedTuple):
    """A non-output file left in place (e.g. Thumbs.db)."""

    path: Path
    reason: str


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_scalar(slug: str, filtered_slugs: frozenset[str]) -> tuple[str, str]:
    """Return ``(metric_family_type, scope_layout)`` for a scalar metric.

    A scalar is DLC-filterable (→ ``no_filter`` layout, ``dlc`` type) iff it
    has a ``filtered_v1`` input; otherwise it is flat (→ ``spout`` type).
    """
    if slug in filtered_slugs:
        return "dlc", NO_FILTER
    return "spout", "flat"


def _layout_segment(scope_layout: str) -> tuple[str, ...]:
    """Path segments contributed by the layout (``no_filter`` adds a dir)."""
    return (NO_FILTER,) if scope_layout == NO_FILTER else ()


# ---------------------------------------------------------------------------
# Planning (pure: reads the filesystem, mutates nothing)
# ---------------------------------------------------------------------------

def _is_movable(f: Path) -> bool:
    return f.is_file() and f.suffix.lower() in MOVABLE_EXTS


def _already_migrated(rel_parts: tuple[str, ...]) -> bool:
    """True if any path component is a scope marker (idempotency guard)."""
    return any(part in _SCOPE_MARKERS for part in rel_parts)


def plan_tree(
    base: Path,
    filtered_slugs: frozenset[str],
) -> tuple[list[Move], list[SkippedFile]]:
    """Plan all moves for one ``phenotype_pooled`` base (figures or results).

    Returns ``(moves, skipped)``. The full file list is snapshotted here
    before any move executes, so creating destination dirs later cannot
    perturb the plan.
    """
    moves: list[Move] = []
    skipped: list[SkippedFile] = []
    if not base.exists():
        return moves, skipped

    for child in sorted(base.iterdir()):
        if not child.is_dir():
            skipped.append(SkippedFile(child, "loose-file-at-base-root"))
            continue

        if child.name == LEGACY_3TIER_DIRNAME:
            # Top-level 3_phenotype/ — 3-tier mirror of the scalar metrics.
            _plan_top_level_3phenotype(child, base, filtered_slugs, moves, skipped)
        elif child.name in FAMILY_TYPES:
            _plan_family(child, FAMILY_TYPES[child.name], moves, skipped)
        else:
            _plan_scalar_root(child, filtered_slugs, moves, skipped)

    return moves, skipped


def _plan_top_level_3phenotype(
    threephen: Path,
    base: Path,
    filtered_slugs: frozenset[str],
    moves: list[Move],
    skipped: list[SkippedFile],
) -> None:
    """``<pp>/3_phenotype/<slug>/...`` → ``<pp>/<slug>/3_tier/[no_filter/]...``."""
    for f in sorted(threephen.rglob("*")):
        if not f.is_file():
            continue
        if not _is_movable(f):
            skipped.append(SkippedFile(f, "non-output-ext"))
            continue
        rel = f.relative_to(threephen)
        if not rel.parts:  # pragma: no cover - defensive
            continue
        slug = rel.parts[0]
        rel_under_slug = Path(*rel.parts[1:])
        family_type, layout = classify_scalar(slug, filtered_slugs)
        dst = base.joinpath(
            slug, SCOPE_3TIER, *_layout_segment(layout), rel_under_slug,
        )
        moves.append(Move(f, dst, family_type, SCOPE_3TIER, layout, f.stat().st_size))


def _plan_family(
    family_dir: Path,
    family_type: str,
    moves: list[Move],
    skipped: list[SkippedFile],
) -> None:
    """A figure family (always ``no_filter``): split its own ``3_phenotype/``
    (→ 3_tier) from everything else (→ 4_tier), preserving nested subdirs."""
    for f in sorted(family_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(family_dir)
        if _already_migrated(rel.parts):
            continue
        if not _is_movable(f):
            skipped.append(SkippedFile(f, "non-output-ext"))
            continue
        if rel.parts and rel.parts[0] == LEGACY_3TIER_DIRNAME:
            rel_after = Path(*rel.parts[1:])
            dst = family_dir.joinpath(SCOPE_3TIER, NO_FILTER, rel_after)
            tier = SCOPE_3TIER
        else:
            dst = family_dir.joinpath(SCOPE_4TIER, NO_FILTER, rel)
            tier = SCOPE_4TIER
        moves.append(Move(f, dst, family_type, tier, NO_FILTER, f.stat().st_size))


def _plan_scalar_root(
    slug_dir: Path,
    filtered_slugs: frozenset[str],
    moves: list[Move],
    skipped: list[SkippedFile],
) -> None:
    """A scalar metric dir at root (4-tier) → ``<slug>/4_tier/[no_filter/]...``."""
    family_type, layout = classify_scalar(slug_dir.name, filtered_slugs)
    for f in sorted(slug_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(slug_dir)
        if _already_migrated(rel.parts):
            continue
        if not _is_movable(f):
            skipped.append(SkippedFile(f, "non-output-ext"))
            continue
        dst = slug_dir.joinpath(SCOPE_4TIER, *_layout_segment(layout), rel)
        moves.append(Move(f, dst, family_type, SCOPE_4TIER, layout, f.stat().st_size))


def remaining_3phenotype_dirs(bases: list[Path]) -> list[Path]:
    """Return every ``3_phenotype`` directory still present under any base.

    The post-move spot-check target is an empty list.
    """
    found: list[Path] = []
    for base in bases:
        if not base.exists():
            continue
        for d in base.rglob(LEGACY_3TIER_DIRNAME):
            if d.is_dir():
                found.append(d)
    return found


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def execute_move(move: Move) -> bool:
    """Move one file; return ``size_check_passed``. Idempotent-ish: if the
    destination already exists with the same size, the source is removed."""
    move.dst.parent.mkdir(parents=True, exist_ok=True)
    if move.dst.exists():
        same = move.dst.stat().st_size == move.size_bytes
        if same and move.src.exists():
            move.src.unlink()
        return same
    shutil.move(str(move.src), str(move.dst))
    return move.dst.exists() and move.dst.stat().st_size == move.size_bytes


def _rmtree_empty(p: Path) -> None:
    """Best-effort recursive removal of now-empty dirs rooted at ``p``."""
    if not p.exists() or not p.is_dir():
        return
    for child in list(p.iterdir()):
        if child.is_dir():
            _rmtree_empty(child)
    if p.exists() and p.is_dir() and not any(p.iterdir()):
        try:
            p.rmdir()
        except OSError:
            pass


def write_manifest(manifest_path: Path, rows: list[dict[str, object]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "src", "dst", "metric_family_type", "scope_tier",
        "scope_layout", "size_bytes", "size_check_passed",
    ]
    with manifest_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_OUTPUTS_TOKEN = "stroke_orofacial_pipeline_outputs"


def _disp(path_str: str) -> str:
    """Trim the long share/outputs-root prefix for a readable report."""
    idx = path_str.find(_OUTPUTS_TOKEN)
    if idx == -1:
        return path_str
    return "<outputs>" + path_str[idx + len(_OUTPUTS_TOKEN):]


_BUCKET_HEADER = {
    "families": "[DLC FAMILIES - get no_filter/ + v2/ structure]",
    "dlc": "[DLC SCALAR METRICS - get no_filter/ + v2/ structure]",
    "spout": "[FLAT-SCOPE METRICS (spout + jaw + mismatch) - scope subdirs only]",
}
_FAMILY_TYPE_SET = frozenset(FAMILY_TYPES.values())


def _bucket(move: Move) -> str:
    if move.metric_family_type in _FAMILY_TYPE_SET:
        return "families"
    if move.metric_family_type == "dlc":
        return "dlc"
    return "spout"


def print_dry_run_report(
    figures_moves: list[Move],
    results_moves: list[Move],
    skipped: list[SkippedFile],
    bases: list[Path],
) -> None:
    """Print the Priya-format dry-run report (no files moved)."""
    all_moves = figures_moves + results_moves
    print("\nDRY RUN - Stage 1.5 proposed moves (no files moved):")

    # Group by bucket, then by source directory (the move's src parent chain
    # up to the metric/family dir) for a compact per-dir summary.
    for bucket in ("families", "dlc", "spout"):
        print(f"\n{_BUCKET_HEADER[bucket]}")
        bmoves = [m for m in all_moves if _bucket(m) == bucket]
        if not bmoves:
            print("  (none)")
            continue
        # Summarize per (src_dir → dst_dir) pair.
        by_pair: dict[tuple[str, str], list[Move]] = {}
        for m in bmoves:
            by_pair.setdefault((str(m.src.parent), str(m.dst.parent)), []).append(m)
        for (src_dir, dst_dir) in sorted(by_pair):
            group = by_pair[(src_dir, dst_dir)]
            ext_counts: dict[str, int] = {}
            for mv in group:
                e = mv.src.suffix.lstrip(".").upper()
                ext_counts[e] = ext_counts.get(e, 0) + 1
            ext_str = ", ".join(f"{ext_counts[e]} {e}" for e in sorted(ext_counts))
            print(f"  {_disp(src_dir)}/  ({len(group)} files: {ext_str})")
            print(f"      -> {_disp(dst_dir)}/")

    # Totals.
    total_moves = len(all_moves)
    total_bytes = sum(m.size_bytes for m in all_moves)
    print("\n" + "-" * 60)
    print(f"  figures-tree moves: {len(figures_moves)}")
    print(f"  results-tree moves: {len(results_moves)}")
    print(f"Total moves planned: {total_moves}")
    print(f"Total bytes: {total_bytes:,}")

    # Skipped non-output files (Thumbs.db etc.).
    if skipped:
        reasons: dict[str, int] = {}
        for s in skipped:
            reasons[s.reason] = reasons.get(s.reason, 0) + 1
        print(f"Skipped non-output files: {len(skipped)}  {reasons}")

    # Spot-check: would any 3_phenotype/ survive? In dry-run we predict TRUE
    # (none remain) iff every movable file under a 3_phenotype is planned AND
    # no non-output file (Thumbs.db) would strand the dir.
    existing_3p = remaining_3phenotype_dirs(bases)
    stranding = [
        s.path for s in skipped
        if LEGACY_3TIER_DIRNAME in s.path.parts
    ]
    would_be_clean = len(stranding) == 0
    print(
        f"Spot-check: no 3_phenotype/ directories remain post-move: "
        f"{str(would_be_clean).upper()}"
    )
    print(f"  ({len(existing_3p)} 3_phenotype dirs exist pre-move; "
          f"{len(stranding)} non-output files would strand them)")
    if stranding:
        print("  Stranding files (need separate GR7 approval to purge):")
        for p in stranding[:10]:
            print(f"    {_disp(str(p))}")
        if len(stranding) > 10:
            print(f"    ... +{len(stranding) - 10} more")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_bases(resolver: PathResolver) -> tuple[Path, Path, Path, Path]:
    stats = resolver.pipeline_outputs(subdir="stats")
    figures_base = stats / "figures" / "phenotype_pooled"
    results_base = stats / "results" / "phenotype_pooled"
    filtered_v1 = stats / "inputs" / "filtered_v1"
    manifest = stats / MANIFEST_RELPATH
    return figures_base, results_base, filtered_v1, manifest


def _load_filtered_slugs(filtered_v1: Path) -> frozenset[str]:
    if not filtered_v1.exists():
        return frozenset()
    return frozenset(
        d.name for d in filtered_v1.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually run the moves + write the manifest. Default is "
             "dry-run. GR7: requires per-invocation Priya approval.",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    figures_base, results_base, filtered_v1, manifest = _resolve_bases(resolver)
    filtered_slugs = _load_filtered_slugs(filtered_v1)

    print(f"figures base: {figures_base}", flush=True)
    print(f"results base: {results_base}", flush=True)
    print(f"filtered_v1 : {filtered_v1}  ({len(filtered_slugs)} slugs)", flush=True)
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}", flush=True)

    figures_moves, fig_skipped = plan_tree(figures_base, filtered_slugs)
    results_moves, res_skipped = plan_tree(results_base, filtered_slugs)
    skipped = fig_skipped + res_skipped
    bases = [figures_base, results_base]

    if not args.execute:
        print_dry_run_report(figures_moves, results_moves, skipped, bases)
        print("\n(DRY-RUN — nothing moved, no manifest written.)", flush=True)
        return 0

    # EXECUTE.
    rows: list[dict[str, object]] = []
    all_moves = figures_moves + results_moves
    for m in all_moves:
        passed = execute_move(m)
        rows.append({
            "src": str(m.src), "dst": str(m.dst),
            "metric_family_type": m.metric_family_type,
            "scope_tier": m.scope_tier, "scope_layout": m.scope_layout,
            "size_bytes": m.size_bytes, "size_check_passed": passed,
        })
    # Clean up now-empty legacy dirs.
    for d in remaining_3phenotype_dirs(bases):
        _rmtree_empty(d)
    write_manifest(manifest, rows)
    n_pass = sum(1 for r in rows if r["size_check_passed"])
    print(f"\nMoved {len(rows)} files ({n_pass} size-checks passed).", flush=True)
    print(f"Manifest: {manifest}", flush=True)
    leftover = remaining_3phenotype_dirs(bases)
    print(f"3_phenotype dirs remaining: {len(leftover)}", flush=True)
    for d in leftover:
        print(f"  (non-empty, likely Thumbs.db): {d}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
