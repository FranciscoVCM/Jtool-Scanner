"""Brightness-relative crossed killblock evidence for known native tile cells.

Colour remains semantic evidence; a dim red patch alone is not a killblock.
Require both complete dark diagonals, separated from their local flanks. Thin
strokes need 32px detail rather than the colour pass's 16px sampling lattice.
There are no room identities, learned output templates or coordinate answers.
"""

from statistics import median


def red_cross_shape_supported(colours, detail, *, physical_axes=None) -> bool:
    """Qualify a whole red tile with two source-visible dark diagonal strokes.

    ``colours`` and ``detail`` are existing 16x16 and 32x32 native-tile samples.
    This is an additional positive channel, not permission to remove overlaps or
    identify arbitrary coloured tiles. The caller must establish a complete,
    localized native cell; unknown/padded cells cannot provide object evidence.
    Direct native-or-larger samples have distinct pixel identities. Oversampled
    captures must supply their actual 32 x/y physical indices; repeated pixels
    never supply additional contour support. A None index means unknown coverage.
    """
    if len(colours) != 256 or len(detail) != 1024:
        return False
    if physical_axes is not None and (
        len(physical_axes) != 2 or any(len(axis) != 32 for axis in physical_axes)
    ):
        return False
    relative_red = sum(
        red > green * 1.25 and red > blue * 1.30
        for red, green, blue in colours
    ) / len(colours)
    if relative_red < 0.97:
        return False
    if physical_axes is not None:
        xs, ys = physical_axes
        original_colours = {}
        for y in range(32):
            for x in range(32):
                position = xs[x], ys[y]
                if None in position:
                    continue
                colour = detail[y * 32 + x]
                if position in original_colours and original_colours[position] != colour:
                    # Two values cannot be evidence from the same physical pixel.
                    return False
                original_colours[position] = colour
    values = [sum(value) for value in detail]
    for direction in (1, -1):
        supported = False
        for offset in (-2, -1, 0, 1, 2):
            sites = []
            seen = set()
            for x in range(4, 28):
                y = (x if direction == 1 else 31 - x) + offset
                if not (0 <= y - 4 and y + 4 < 32):
                    continue
                if physical_axes is not None:
                    xs, ys = physical_axes
                    center = xs[x], ys[y]
                    first, last = (xs[x], ys[y - 4]), (xs[x], ys[y + 4])
                    if (None in center + first + last or center in seen
                            or len({first, center, last}) != 3):
                        continue
                    seen.add(center)
                sites.append((values[(y - 4) * 32 + x], values[y * 32 + x],
                              values[(y + 4) * 32 + x]))
            if len(sites) < 20:
                continue
            margin = max(3, 2 * median(abs(a - c) for a, _, c in sites))
            if len(sites) >= 20 and sum(min(a, c) - b > margin for a, b, c in sites) >= 20:
                supported = True
                break
        if not supported:
            return False
    return True
