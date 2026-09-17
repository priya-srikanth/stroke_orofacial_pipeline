"""Recover the plotted data out of a matplotlib SVG into a tidy CSV.

Some manuscript panels (Figure 1 body weight and caudoputamen quantification,
the videofluoroscopy panels) were produced outside this repository and their
generating code was not preserved. This tool reads the published SVG, calibrates
the pixel -> data transform from the axis ticks, and writes every plotted point
back out as data, so the panel can be re-rendered from a checked-in table by
``plot_recovered_panels.py``.

It is a recovery path, not a substitute for the original measurements: values are
exact to the precision matplotlib wrote into the path coordinates (about five
decimal places in pixel space, so well under a plotting pixel), but anything the
figure did not draw -- excluded points, raw replicates behind a mean, units that
were converted before plotting -- cannot be recovered. Replace the CSV with the
real source table if it turns up.

Usage::

    python scripts/manuscript/extract_svg_series.py <figure.svg> <out.csv>
    python scripts/manuscript/extract_svg_series.py <dir-of-svgs> <out_dir> --glob "Figure1*.svg"
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


def _color(seg: str) -> str:
    """The artist's stroke (else fill) colour, which usually identifies the series."""
    m = re.search(r"stroke:\s*(#[0-9a-fA-F]{6})", seg)
    if m:
        return m.group(1).lower()
    m = re.search(r"fill:\s*(#[0-9a-fA-F]{6})", seg)
    return m.group(1).lower() if m else ""


def _tick_value(label: str) -> float | None:
    t = label.strip().replace("−", "-").replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _axes_blocks(svg: str) -> list[tuple[str, str]]:
    """(axes_id, inner svg) for each ``<g id="axes_N">`` block."""
    out = []
    for m in re.finditer(r'<g id="(axes_\d+)">', svg):
        start = m.end()
        depth, i = 1, start
        for mm in re.finditer(r"<g\b|</g>", svg[start:]):
            depth += 1 if mm.group(0) != "</g>" else -1
            if depth == 0:
                i = start + mm.start()
                break
        out.append((m.group(1), svg[start:i]))
    return out


def _ticks(block: str, kind: str) -> list[tuple[float, str]]:
    """[(pixel, label)] for each ``xtick``/``ytick`` group that carries a label."""
    pts = []
    for m in re.finditer(rf'<g id="{kind}_\d+">(.*?)(?=<g id="{kind}_\d+">|\Z)',
                         block, re.S):
        seg = m.group(1)
        u = re.search(rf'<use[^>]*\sx="({NUM})"\s+y="({NUM})"', seg)
        lab = re.search(r"<!--\s*(.*?)\s*-->", seg)
        if not u or not lab:
            continue
        pts.append((float(u.group(1) if kind == "xtick" else u.group(2)),
                    lab.group(1).strip()))
    return pts


def _affine(ticks: list[tuple[float, str]]) -> tuple[float, float] | None:
    """(scale, offset) with value = scale * pixel + offset, from the numeric tick
    pair that is farthest apart (most numerically stable). None if the axis is
    categorical (no two numeric ticks)."""
    num = [(p, _tick_value(t)) for p, t in ticks]
    num = sorted((p, v) for p, v in num if v is not None)
    if len(num) < 2:
        return None
    (p0, v0), (p1, v1) = num[0], num[-1]
    if p1 == p0:
        return None
    scale = (v1 - v0) / (p1 - p0)
    return scale, v0 - scale * p0


def _categorical(ticks: list[tuple[float, str]]):
    """Nearest-tick label lookup, for a categorical axis."""
    if not ticks:
        return None
    pts = sorted(ticks)
    def nearest(px: float) -> str:
        return min(pts, key=lambda t: abs(t[0] - px))[1]
    return nearest


def _path_points(d: str) -> list[tuple[float, float]]:
    """Points of an SVG path made only of absolute M/L commands (matplotlib lines)."""
    if re.search(r"[CQSTAcqstahvz]", d):
        return []          # curves / markers drawn as shapes: not a data polyline
    return [(float(a), float(b))
            for a, b in re.findall(rf"[ML]\s*({NUM})\s+({NUM})", d)]


def extract(svg_path: Path) -> pd.DataFrame:
    svg = svg_path.read_text()
    rows = []
    for axes_id, block in _axes_blocks(svg):
        # drop the legend block: its handles are not data
        block = re.sub(r'<g id="legend_\d+">.*', "", block, flags=re.S)
        xt, yt = _ticks(block, "xtick"), _ticks(block, "ytick")
        ax, ay = _affine(xt), _affine(yt)
        if ay is None and ax is None:
            continue                      # no calibrated axis at all
        xcat = _categorical(xt) if ax is None else None
        ycat = _categorical(yt) if ay is None else None

        def to_data(px, py):
            x = ax[0] * px + ax[1] if ax else (xcat(px) if xcat else px)
            y = ay[0] * py + ay[1] if ay else (ycat(py) if ycat else py)
            return x, y

        # lines / polylines
        for m in re.finditer(r'<g id="(line2d_\d+)">(.*?)</g>\s*(?=<g id="|\Z)',
                             block, re.S):
            artist, seg = m.group(1), m.group(2)
            for dm in re.finditer(r'<path d="([^"]+)"', seg):
                pts = _path_points(dm.group(1))
                if len(pts) < 2:
                    continue
                col = _color(dm.group(0) + seg)
                for k, (px, py) in enumerate(pts):
                    x, y = to_data(px, py)
                    rows.append((axes_id, "line", artist, k, x, y, col))
            # markers placed with <use>
            for k, um in enumerate(re.finditer(
                    rf'<use[^>]*\sx="({NUM})"\s+y="({NUM})"', seg)):
                x, y = to_data(float(um.group(1)), float(um.group(2)))
                rows.append((axes_id, "marker", artist, k, x, y, _color(seg)))
        # bars: rectangle patches (skip the axes background, patch_1)
        for m in re.finditer(r'<g id="(patch_\d+)">(.*?)</g>\s*(?=<g id="|\Z)',
                             block, re.S):
            artist, seg = m.group(1), m.group(2)
            dm = re.search(r'<path d="([^"]+)"', seg)
            if not dm or "style=\"fill: none" in seg:
                continue
            pts = [(float(a), float(b)) for a, b in
                   re.findall(rf"[MLmlHV]?\s*({NUM})\s+({NUM})", dm.group(1))]
            if len(pts) < 4:
                continue
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if len(set(round(v, 3) for v in xs)) != 2:
                continue                  # not an axis-aligned rectangle
            x, y = to_data((min(xs) + max(xs)) / 2, min(ys))   # bar top
            _, y0 = to_data(0, max(ys))
            rows.append((axes_id, "bar", artist, 0, x, y, _color(seg)))
            rows.append((axes_id, "bar_base", artist, 0, x, y0, _color(seg)))

        # scatter
        for m in re.finditer(r'<g id="(PathCollection_\d+)">(.*?)</g>\s*(?=<g id="|\Z)',
                             block, re.S):
            artist, seg = m.group(1), m.group(2)
            for k, um in enumerate(re.finditer(
                    rf'<use[^>]*\sx="({NUM})"\s+y="({NUM})"', seg)):
                x, y = to_data(float(um.group(1)), float(um.group(2)))
                rows.append((axes_id, "scatter", artist, k, x, y, _color(seg)))
    d = pd.DataFrame(rows, columns=["axes", "kind", "artist", "i", "x", "y", "color"])
    d.insert(0, "figure", svg_path.stem)
    return d


def labels(svg_path: Path) -> list[str]:
    """Every text string in the SVG, in document order (titles, ticks, legend)."""
    svg = svg_path.read_text()
    seen, out = set(), []
    for m in re.finditer(r"<!--\s*(.*?)\s*-->", svg):
        t = m.group(1).strip()
        if t and t not in seen:
            seen.add(t); out.append(t)
    for m in re.finditer(r">([^<>]{1,120})</text>", svg):
        t = m.group(1).strip()
        if t and t not in seen:
            seen.add(t); out.append(t)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="an .svg, or a directory of them")
    ap.add_argument("dst", type=Path, help="output .csv, or output directory")
    ap.add_argument("--glob", default="*.svg")
    a = ap.parse_args(argv)
    srcs = sorted(a.src.glob(a.glob)) if a.src.is_dir() else [a.src]
    if not srcs:
        raise SystemExit(f"no SVG matched {a.src}/{a.glob}")
    for s in srcs:
        d = extract(s)
        if a.src.is_dir():
            a.dst.mkdir(parents=True, exist_ok=True)
            out = a.dst / f"{s.stem}.csv"
        else:
            out = a.dst
            out.parent.mkdir(parents=True, exist_ok=True)
        d.to_csv(out, index=False)
        print(f"{s.name}: {len(d)} points, {d.artist.nunique()} artists -> {out}")
        print("   labels:", "; ".join(labels(s)[:14]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
