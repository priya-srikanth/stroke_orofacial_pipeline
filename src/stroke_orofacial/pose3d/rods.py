"""Rod (spout) tips in the median video4 frame (cam1 orientation = raw vertical flip, FULL 800-px width).

Rods are ~30-px straight bars entering from the top. For each rod: find its two edges in the top rows (20-150,
where nothing else is there), fit a straight line to each edge, then walk down the FITTED centerline (no tracking, so
the walk cannot wander onto the side of the snout -- PS46 03-24). The rod is opaque: its gray fades smoothly down
its length, and the tip is where the centerline gray jumps up onto the face."""

import cv2
import numpy as np

TOP = (20, 150)


def _edge_line(ag, c_lo, c_hi):
    ys = np.arange(*TOP)
    xs = np.array([c_lo + int(np.argmax(ag[y, c_lo:c_hi])) for y in ys])
    return np.polyfit(ys, xs, 1)  # x = a*y + b


def rod_tips(m):
    ag = np.abs(cv2.Sobel(m.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3))
    prof = ag[TOP[0] : TOP[1]].mean(0)
    cols = np.where(prof > 0.3 * prof.max())[0]
    groups = np.split(cols, np.where(np.diff(cols) > 60)[0] + 1)
    groups = sorted([g for g in groups if g.max() - g.min() > 15], key=lambda g: -prof[g].sum())[:2]
    if len(groups) != 2:
        raise RuntimeError(f"found {len(groups)} rods")
    tips = []
    for g in sorted(groups, key=lambda g: g.min()):
        mid = (g.min() + g.max()) // 2
        lines = [_edge_line(ag, g.min() - 4, mid), _edge_line(ag, mid, g.max() + 5)]

        def center_gray(y, lines=lines):
            x = round((np.polyval(lines[0], y) + np.polyval(lines[1], y)) / 2)
            return m[y, max(0, x - 3) : x + 4].mean()

        cen = np.array([center_gray(y) for y in range(m.shape[0])])
        # the rod's own gray fades smoothly down its length (105 -> 50); just past the tip the centerline lands
        # on the face and jumps by > 30 above the rod's darkest value in the preceding 20 rows, for 5 rows
        tip = next(
            y
            for y in range(150, m.shape[0] - 5)
            if cen[y : y + 5].min() > cen[y - 20 : y].min() + 30
        )
        # x at the tip: the fitted edge lines diverge a little by the tip, so read x from the image instead.
        # Just above the tip the rod (dark) lies over the bright face: its left edge is the strongest
        # bright->dark step and its right edge the strongest dark->bright step within +-30 px of the predicted
        # center; x = their midpoint, median over 6 rows.
        xs, ws = [], []
        for y in range(tip - 10, tip - 4):
            xc = round((np.polyval(lines[0], y) + np.polyval(lines[1], y)) / 2)
            d = np.diff(m[y, xc - 30 : xc + 31].astype(np.float32))
            il = int(np.argmin(d[:31]))
            ir = 30 + int(np.argmax(d[30:]))
            xs.append(xc - 30 + (il + ir + 1) / 2.0)
            ws.append(ir - il)
        tips.append((float(np.median(xs)), float(tip), float(np.median(ws))))
    return tips
