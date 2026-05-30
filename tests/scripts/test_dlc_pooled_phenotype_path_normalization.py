"""Tests for Stage 1.5 path-normalization planner.

Chore ``vChore-dlc-pooled-phenotype-unification``. All tests build a fake
tree under ``tmp_path`` — nothing touches the real outputs share.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.chore_dlc_pooled_phenotype import path_normalization as pn

FILTERED = frozenset({"tongue_x"})


def _touch(p: Path, content: bytes = b"x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A miniature phenotype_pooled tree exercising every bucket."""
    base = tmp_path / "phenotype_pooled"
    # Filterable scalar (tongue_x) — 4-tier root + Thumbs.db cruft.
    _touch(base / "tongue_x" / "a.svg")
    _touch(base / "tongue_x" / "a.png")
    _touch(base / "tongue_x" / "Thumbs.db")
    # Flat scalar (jaw_y).
    _touch(base / "jaw_y" / "b.svg")
    # A figure family with nested subdir + its own 3_phenotype mirror.
    _touch(base / "proportion_diff_heatmaps" / "c.svg")
    _touch(base / "proportion_diff_heatmaps" / "null_calibration" / "d.svg")
    _touch(base / "proportion_diff_heatmaps" / "3_phenotype" / "c.svg")
    # Top-level 3_phenotype mirror for scalars + a stranding Thumbs.db.
    _touch(base / "3_phenotype" / "tongue_x" / "e.svg")
    _touch(base / "3_phenotype" / "jaw_y" / "f.svg")
    _touch(base / "3_phenotype" / "Thumbs.db")
    return base


def _move_map(moves: list[pn.Move], base: Path) -> dict[str, str]:
    """Map src→dst as paths relative to base, for readable assertions."""
    return {
        str(m.src.relative_to(base)).replace("\\", "/"):
        str(m.dst.relative_to(base)).replace("\\", "/")
        for m in moves
    }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def test_classify_filterable_scalar() -> None:
    assert pn.classify_scalar("tongue_x", FILTERED) == ("dlc", "no_filter")


def test_classify_flat_scalar() -> None:
    assert pn.classify_scalar("jaw_y", FILTERED) == ("spout", "flat")
    assert pn.classify_scalar("d_prime", FILTERED) == ("spout", "flat")


# ---------------------------------------------------------------------------
# Planning — destinations per bucket
# ---------------------------------------------------------------------------

def test_filterable_scalar_root_to_4tier_no_filter(tree: Path) -> None:
    moves, _ = pn.plan_tree(tree, FILTERED)
    mm = _move_map(moves, tree)
    assert mm["tongue_x/a.svg"] == "tongue_x/4_tier/no_filter/a.svg"
    assert mm["tongue_x/a.png"] == "tongue_x/4_tier/no_filter/a.png"


def test_flat_scalar_root_to_4tier_no_no_filter(tree: Path) -> None:
    moves, _ = pn.plan_tree(tree, FILTERED)
    mm = _move_map(moves, tree)
    assert mm["jaw_y/b.svg"] == "jaw_y/4_tier/b.svg"


def test_family_4tier_and_nested_preserved(tree: Path) -> None:
    moves, _ = pn.plan_tree(tree, FILTERED)
    mm = _move_map(moves, tree)
    assert (
        mm["proportion_diff_heatmaps/c.svg"]
        == "proportion_diff_heatmaps/4_tier/no_filter/c.svg"
    )
    # Nested subdir (null_calibration) preserved recursively under no_filter.
    assert (
        mm["proportion_diff_heatmaps/null_calibration/d.svg"]
        == "proportion_diff_heatmaps/4_tier/no_filter/null_calibration/d.svg"
    )


def test_family_own_3phenotype_to_3tier_no_filter(tree: Path) -> None:
    moves, _ = pn.plan_tree(tree, FILTERED)
    mm = _move_map(moves, tree)
    assert (
        mm["proportion_diff_heatmaps/3_phenotype/c.svg"]
        == "proportion_diff_heatmaps/3_tier/no_filter/c.svg"
    )


def test_toplevel_3phenotype_scalars_split_by_filterability(tree: Path) -> None:
    moves, _ = pn.plan_tree(tree, FILTERED)
    mm = _move_map(moves, tree)
    # Filterable → 3_tier/no_filter; flat → 3_tier (no no_filter).
    assert mm["3_phenotype/tongue_x/e.svg"] == "tongue_x/3_tier/no_filter/e.svg"
    assert mm["3_phenotype/jaw_y/f.svg"] == "jaw_y/3_tier/f.svg"


def test_family_type_tags(tree: Path) -> None:
    moves, _ = pn.plan_tree(tree, FILTERED)
    by_src = {str(m.src.relative_to(tree)).replace("\\", "/"): m for m in moves}
    assert by_src["proportion_diff_heatmaps/c.svg"].metric_family_type == "heatmap"
    assert by_src["tongue_x/a.svg"].metric_family_type == "dlc"
    assert by_src["jaw_y/b.svg"].metric_family_type == "spout"


# ---------------------------------------------------------------------------
# Skipping non-output files
# ---------------------------------------------------------------------------

def test_thumbs_db_skipped_not_moved(tree: Path) -> None:
    moves, skipped = pn.plan_tree(tree, FILTERED)
    moved_names = {m.src.name for m in moves}
    assert "Thumbs.db" not in moved_names
    skipped_names = {s.path.name for s in skipped}
    assert "Thumbs.db" in skipped_names


def test_only_svg_png_csv_planned(tree: Path) -> None:
    moves, _ = pn.plan_tree(tree, FILTERED)
    assert all(m.src.suffix.lower() in pn.MOVABLE_EXTS for m in moves)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_already_migrated_files_not_replanned(tree: Path) -> None:
    # Simulate a prior run: a file already under 4_tier/.
    _touch(tree / "tongue_x" / "4_tier" / "no_filter" / "already.svg")
    moves, _ = pn.plan_tree(tree, FILTERED)
    srcs = {str(m.src.relative_to(tree)).replace("\\", "/") for m in moves}
    assert "tongue_x/4_tier/no_filter/already.svg" not in srcs


# ---------------------------------------------------------------------------
# Execution + cleanup
# ---------------------------------------------------------------------------

def test_execute_moves_files_and_size_checks(tree: Path) -> None:
    moves, _ = pn.plan_tree(tree, FILTERED)
    for m in moves:
        passed, pre_size = pn.execute_move(m)
        assert passed is True
        assert pre_size is None  # no pre-existing dst on a clean move
        assert m.dst.exists()
        assert not m.src.exists()


def test_execute_refuses_divergent_dst_by_default(tmp_path: Path) -> None:
    """Default execute_move won't overwrite a divergent destination."""
    base = tmp_path / "pp"
    _touch(base / "tongue_x" / "a.svg", b"new-content")
    moves, _ = pn.plan_tree(base, FILTERED)
    (m,) = [mv for mv in moves if mv.src.name == "a.svg"]
    m.dst.parent.mkdir(parents=True, exist_ok=True)
    m.dst.write_bytes(b"stale-bigger-content")  # different size at dst
    passed, pre_size = pn.execute_move(m)
    assert passed is False
    assert pre_size is None
    assert m.src.exists()  # source untouched (not clobbered)


def test_replace_existing_overwrites_and_reports_pre_size(tmp_path: Path) -> None:
    """--replace-existing overwrites a divergent dst and reports its size."""
    base = tmp_path / "pp"
    _touch(base / "tongue_x" / "a.svg", b"new")
    moves, _ = pn.plan_tree(base, FILTERED)
    (m,) = [mv for mv in moves if mv.src.name == "a.svg"]
    m.dst.parent.mkdir(parents=True, exist_ok=True)
    m.dst.write_bytes(b"stale-content")  # 13 bytes
    passed, pre_size = pn.execute_move(m, replace_existing=True)
    assert passed is True
    assert pre_size == len(b"stale-content")
    assert m.dst.read_bytes() == b"new"
    assert not m.src.exists()


def test_execute_then_no_3phenotype_dirs_when_no_cruft(tmp_path: Path) -> None:
    # Clean tree (no Thumbs.db) → after execute + cleanup, zero 3_phenotype.
    base = tmp_path / "pp"
    _touch(base / "tongue_x" / "a.svg")
    _touch(base / "3_phenotype" / "tongue_x" / "e.svg")
    moves, _ = pn.plan_tree(base, FILTERED)
    for m in moves:
        pn.execute_move(m)
    for d in pn.remaining_3phenotype_dirs([base]):
        pn._rmtree_empty(d)
    assert pn.remaining_3phenotype_dirs([base]) == []


def test_find_db_files_locates_thumbs_db(tree: Path) -> None:
    """find_db_files locates every Thumbs.db (purge targets)."""
    dbs = pn.find_db_files([tree])
    names = {p.name for p in dbs}
    assert names == {"Thumbs.db"}
    assert len(dbs) == 2  # tongue_x/ + 3_phenotype/


def test_execute_with_purge_clears_3phenotype_despite_db(tree: Path) -> None:
    """Full execute flow: moves + Thumbs.db purge + cleanup → 0 3_phenotype.

    The stranding Thumbs.db under 3_phenotype/ would otherwise keep that dir
    alive; purging it (GR7-approved) lets cleanup remove it.
    """
    moves, _ = pn.plan_tree(tree, FILTERED)
    for m in moves:
        pn.execute_move(m)
    for f in pn.find_db_files([tree]):
        f.unlink()
    for d in pn.remaining_3phenotype_dirs([tree]):
        pn._rmtree_empty(d)
    assert pn.remaining_3phenotype_dirs([tree]) == []


def test_manifest_written(tmp_path: Path) -> None:
    rows = [{
        "src": "a", "dst": "b", "metric_family_type": "dlc",
        "scope_tier": "4_tier", "scope_layout": "no_filter",
        "size_bytes": 10, "size_check_passed": True,
    }]
    manifest = tmp_path / "sub" / "manifest.csv"
    pn.write_manifest(manifest, rows)
    text = manifest.read_text(encoding="utf-8")
    assert "metric_family_type" in text
    assert "dlc" in text
