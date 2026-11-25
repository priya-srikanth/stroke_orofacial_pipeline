"""Marks check between two matplotlib SVGs (svg.fonttype none): every '*', '**' and dagger text, with its fill colour and
x position (pt), must be the same in both files (y may differ: the band moved). Prints counts and any difference.

Usage: python marks_check.py <live.svg> <new.svg>[+<new2.svg>...] [...pairs]   (+ = marks of several crops pooled)
"""
import re
import sys
from collections import Counter

TXT = re.compile(r'<text\b([^>]*)>([^<]*)</text>', re.S)
FILL = re.compile(r'fill:\s*(#[0-9a-fA-F]{6})')
XY = re.compile(r'translate\(([-\d.e]+)[ ,]+([-\d.e]+)\)')
MARKS = {'*', '**', '†', '&#8224;', '&#x2020;'}


def marks(path):
    s = open(path, encoding='utf-8').read()
    out = []
    for attrs, body in TXT.findall(s):
        t = body.strip()
        if t not in MARKS:
            continue
        t = '†' if t.startswith('&') else t
        f = FILL.search(attrs); m = XY.search(attrs)
        x = float(re.search(r'\bx="([-\d.e]+)"', attrs).group(1)) if m is None else float(m.group(1))
        out.append((t, f.group(1).lower() if f else '?', round(x, 1)))
    return Counter(out)


if __name__ == '__main__':
    a = sys.argv[1:]
    bad = 0
    for live, new in zip(a[::2], a[1::2]):
        A = marks(live); B = sum((marks(n) for n in new.split('+')), Counter())
        n = {k: sum(v for (t, *_), v in A.items() if t == k) for k in ('*', '**', '†')}
        ok = A == B
        bad += not ok
        print(f"{new.replace(chr(92), '/').split('/')[-1]}: live {dict(n)} | {'IDENTICAL marks (text, colour, x)' if ok else 'DIFFER'}")
        if not ok:
            print('   only live:', sorted((A - B).elements())); print('   only new :', sorted((B - A).elements()))
    sys.exit(bad)
