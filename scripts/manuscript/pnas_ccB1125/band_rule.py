"""Data-area top and kept y ticks for the PNAS star-band panels (CC-B 2026-11-25).

v28 (PROMPT_CC_B_pnas_panels item 1, as CC-A's c2 v28): data area ends 1 % of the range above the highest drawn point;
    only ticks inside it are kept (the top tick could be dropped, so the axis line could end below some data).
v29 (PROMPT_CC_B_layout_inputs item 1, Priya "the axis line needs to extend high enough to cover the data"; the rule of
    CC-A's vls_style_spine_cover_ccA1125): the left spine ends at the FIRST major tick at or above the highest drawn
    data point (points, error bars, lines; not marks) and that tick keeps its label; the data area is raised to that
    tick when needed and the star band stays above it. Major ticks = the panel's live tick grid (same step / anchor).
v30 (PROMPT_CC_B_ticks_stars_fig3D_v2 item 1, Priya "yes"; CC-A's c2_scalar_compact_v29 rule): the tick step is chosen
    from 1, 2, 2.5, 4, 5 x 10^k with 4 to 8 ticks over the data area, the step whose first tick at or above the highest
    drawn point is closest to it; the data area and the spine end at that tick. The grid starts at the first step
    multiple at or above the lower limit. Falls back to v29 if no step gives 4-8 ticks.
All: when the lower limit is below 0, the dashed zero line stays inside the data area with a 5 % margin.
Band rows (v30, item 2): rows 3.0 pt below the band top, 4.0 pt apart, 1.5 pt below the last row, and only the rows
the panel uses (band_pt()).
Lower limit (v30, item 2b): cover_low() gives the lowest mean marker / interval bar / connecting line (session dots are
not counted), so the caller can extend the lower limit below it.
"""
import numpy as np

ROW_TOP_PT_V30, ROW_STEP_PT_V30, BELOW_PT_V30 = 3.0, 4.0, 1.5


def tick_step_v30(top, y0):
    """-> (step, first tick >= y0, first tick >= top) or None."""
    rng = top - y0
    best = None
    for k in range(-4, 6):
        for m in (1, 2, 2.5, 4, 5):
            st = m * 10.0 ** k
            lo_t = np.floor(y0 / st + 1e-9) * st
            if lo_t < y0 - 1e-9: lo_t += st
            tp = st * np.ceil(top / st - 1e-9)
            n = int(round((tp - lo_t) / st)) + 1
            if 4 <= n <= 8:
                gap = (tp - top) / rng
                if best is None or gap < best[0] - 1e-9: best = (gap, st, lo_t, tp)
    return None if best is None else best[1:]


def data_top(top, y0, live_ticks, mode):
    """-> (yd1 = data-area top, ticks to keep, spine-top tick or None)."""
    lt = np.asarray(sorted(live_ticks), float)
    if mode == "v28":
        yd1 = top + 0.01 * (top - y0)
        if y0 < 0:
            yd1 = max(yd1, 0.0 + 0.05 * (max(yd1, 0.0) - y0))
        return yd1, [t for t in lt if y0 <= t <= yd1 + 1e-12], None
    if mode == "v30":
        best = tick_step_v30(top, y0)
        if best is not None:
            step, lo_t, tick = best
            tick = round(float(tick), 10)
            yd1 = max(tick, top + 0.01 * (top - y0))
            if y0 < 0:
                yd1 = max(yd1, 0.0 + 0.05 * (max(yd1, 0.0) - y0))
            grid = [round(float(v), 10) for v in np.arange(lo_t, tick + step / 2, step)]
            return yd1, [t for t in grid if y0 - 1e-9 <= t <= tick + 1e-9], tick
    step = float(np.median(np.diff(lt)))
    k = np.ceil((top - lt[0]) / step - 1e-9)
    tick = float(lt[0] + k * step)
    tick = round(tick, 10)
    yd1 = max(tick, top + 0.01 * (top - y0))
    if y0 < 0:
        yd1 = max(yd1, 0.0 + 0.05 * (max(yd1, 0.0) - y0))
    n = int(np.floor((tick - lt[0]) / step + 1e-9))
    grid = [round(float(lt[0] + i * step), 10) for i in range(n + 1)]
    return yd1, [t for t in grid if y0 <= t <= tick + 1e-12], tick


def band_pt(used_rows, extra_pt=0.0):
    """v30 band height (pt) for the rows in use (0-based row indices); 0 when the panel has no marks."""
    if not used_rows: return extra_pt
    return extra_pt + ROW_TOP_PT_V30 + max(used_rows) * ROW_STEP_PT_V30 + BELOW_PT_V30


def row_y(row, ah_pt, extra_pt=0.0):
    """v30: axes-fraction y of mark row `row` (0 = top) for an axes ah_pt tall."""
    return 1.0 - (extra_pt + ROW_TOP_PT_V30 + row * ROW_STEP_PT_V30) / ah_pt


def cover_low(ax):
    """Lowest y of every interval bar (LineCollection segment) and every drawn line (mean markers, connecting
    lines; a Line2D with a visible line style), ignoring the dashed zero line and marker-only lines (session dots)."""
    from matplotlib.collections import LineCollection
    ys = []
    for c in ax.collections:
        if isinstance(c, LineCollection):
            for s in c.get_segments():
                ys.extend(np.asarray(s, float)[:, 1])
    for ln in ax.lines:
        yd = np.asarray(ln.get_ydata(), float)
        if not yd.size or ln.get_linestyle() in ('None', 'none', '', ' '):
            continue
        if np.allclose(yd, 0) and ln.get_linestyle() in ('--', 'dashed'):
            continue
        ys.extend(yd)
    ys = np.asarray(ys, float); ys = ys[np.isfinite(ys)]
    return float(ys.min()) if ys.size else np.nan
