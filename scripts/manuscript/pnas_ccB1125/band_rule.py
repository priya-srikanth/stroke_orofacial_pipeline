"""Data-area top and kept y ticks for the PNAS star-band panels (CC-B 2026-11-25).

v28 (PROMPT_CC_B_pnas_panels item 1, as CC-A's c2 v28): data area ends 1 % of the range above the highest drawn point;
    only ticks inside it are kept (the top tick could be dropped, so the axis line could end below some data).
v29 (PROMPT_CC_B_layout_inputs item 1, Priya "the axis line needs to extend high enough to cover the data"; the rule of
    CC-A's vls_style_spine_cover_ccA1125): the left spine ends at the FIRST major tick at or above the highest drawn
    data point (points, error bars, lines; not marks) and that tick keeps its label; the data area is raised to that
    tick when needed and the star band stays above it. Major ticks = the panel's live tick grid (same step / anchor).
Both: when the lower limit is below 0, the dashed zero line stays inside the data area with a 5 % margin.
"""
import numpy as np


def data_top(top, y0, live_ticks, mode):
    """-> (yd1 = data-area top, ticks to keep, spine-top tick or None)."""
    lt = np.asarray(sorted(live_ticks), float)
    if mode == "v28":
        yd1 = top + 0.01 * (top - y0)
        if y0 < 0:
            yd1 = max(yd1, 0.0 + 0.05 * (max(yd1, 0.0) - y0))
        return yd1, [t for t in lt if y0 <= t <= yd1 + 1e-12], None
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
