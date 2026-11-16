"""Experimental original-pixel crease proof for a localized compact red tile.

This standalone evidence helper is not called by the app or scanner. To
test a narrow dark stroke under illumination, interpolate opposing flanks
symmetrically at two scales. Require both diagonals on independent folds.
"""


def crossed_tile_curvature(colours, detail, axes):
    """Return evidence from existing 16/32 native samples and physical axes."""
    if (len(colours) != 256 or len(detail) != 1024 or len(axes) != 2
            or any(x is None for a in axes for x in a)):
        return dict(passed=False, reason='unknown original support')
    if sum(r > 1.25*g and r > 1.30*b for r, g, b in colours) / 256 < .97:
        return dict(passed=False, reason='legacy relative-red isolation')
    xs, ys = axes
    if len(xs) != 32 or len(ys) != 32:
        return dict(passed=False, reason='invalid physical axes')
    raw = {}
    for v, sy in enumerate(ys):
        for u, sx in enumerate(xs):
            k = (sx, sy)
            q = detail[v * 32 + u]
            if k in raw and raw[k] != q:
                return dict(passed=False, reason='inconsistent repeated physical RGB')
            raw[k] = q
    result = []
    for sign in (1, -1):
        phases = []
        for off in range(-2, 3):
            folds = [[0, 0, 0], [0, 0, 0]]
            seen_x = set()
            for x in range(4, 28):
                y = (x if sign == 1 else 31 - x) + off
                if not 4 <= y < 28 or xs[x] in seen_x:
                    continue
                taps = [(xs[x], ys[y+n]) for n in (-4, -2, 0, 2, 4)]
                if len(set(taps)) != 5:
                    continue
                seen_x.add(xs[x])
                fold = folds[x % 2]
                fold[0] += 1
                a, b, c, d, e = map(raw.__getitem__, taps)
                inside = tuple(m+n-2*p for m, n, p in zip(b, d, c))
                outside = tuple(m+n-2*p for m, n, p in zip(a, e, c))
                inner, outer = sum(inside), sum(outside)
                # Curvature of a broad quadratic valley scales with the
                # square of the spacing; narrow ink already dips inside.
                if inner > 6 and outer > 6 and 5*inner >= 3*outer and sum(v > 0 for v in inside) >= 2:
                    fold[1] += 1
                    fold[2] += inner
            phases.append(dict(offset=off, folds=folds))
        best = []
        for p in (0, 1):
            options = sorted(((r['folds'][p][1:], r['offset'])
                               for r in phases if r['folds'][p][1] >= 10), reverse=True)
            best.append(options[0][1] if options and (len(options) == 1 or options[0][0] != options[1][0]) else None)
        result.append(dict(sign=sign, winners=best, passed=best[0] is not None and best[0] == best[1], phases=phases))
    ok = all(r['passed'] for r in result)
    return dict(passed=ok, diagonals=result, reason='two original localized strokes' if ok else 'local stroke proof incomplete')
