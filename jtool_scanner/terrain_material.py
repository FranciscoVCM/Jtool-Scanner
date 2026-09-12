"""Geometry-backed grouping of interleaved, room-local terrain materials.

This fallback is deliberately limited to repeated textured cells. It does not
infer flat terrain, unknown colors or arbitrary object types from a palette.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import combinations
from statistics import median


Point = tuple[int, int]


@dataclass(frozen=True, slots=True)
class ComplementaryTerrain:
    terrain_cells: frozenset[Point]
    full_blocks: frozenset[Point]
    seed_cluster: int
    support_votes: int
    full_coverage: float


def cell_quad(origin: Point) -> frozenset[Point]:
    x, y = origin
    return frozenset(((x, y), (x + 16, y), (x, y + 16), (x + 16, y + 16)))


def distributed_cell_edges(mask: tuple[bool, ...]) -> bool:
    """A weak 16x16 texture must extend beyond one borrowed boundary line.

    Require broad extent in both axes and at least two witnesses away from
    the dominant row/column. One noisy pixel beside a straight edge is not
    sufficient. This supplements, never replaces, neighboring tile evidence.
    """
    points = [(i % 16, i // 16) for i, edge in enumerate(mask) if edge]
    if len(mask) != 256 or len(points) < 8:
        return False
    xs, ys = zip(*points)
    return (
        min(max(xs)-min(xs), max(ys)-min(ys)) >= 8
        and max(max(Counter(xs).values()), max(Counter(ys).values())) <= len(points)-2
    )


def pack_textured_rectangles(
    positions: frozenset[Point] | set[Point],
    scores: Mapping[Point, float] | None = None,
) -> frozenset[Point]:
    """Cover complete 32px rectangles without requiring a global 32px phase.

    Constrained boundary cells precede ambiguous interior placements. Four
    deterministic tie orders reduce packing holes without an unbounded search.
    A final half-block overlap can fill a supported strip, but never a single
    residual 16px corner. Every emitted rectangle remains entirely in the mask.
    This establishes occupancy, not the original hidden object decomposition.
    """
    candidates = {p: cell_quad(p) for p in positions if cell_quad(p) <= positions}
    if not candidates:
        return frozenset()
    scores = scores or {}
    solutions: list[frozenset[Point]] = []
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        remaining = dict(candidates)
        selected: list[Point] = []
        while remaining:
            usage = Counter(cell for cells in remaining.values() for cell in cells)
            origin = min(
                remaining,
                key=lambda p: (
                    min(usage[c] for c in remaining[p]),
                    -sum(1 / usage[c] for c in remaining[p]),
                    -scores.get(p, 0), sy * p[1], sx * p[0],
                ),
            )
            cells = remaining[origin]
            selected.append(origin)
            remaining = {p: q for p, q in remaining.items() if not q & cells}
        solutions.append(frozenset(selected))
    selected_blocks = set(max(
        solutions,
        key=lambda blocks: (
            len(blocks), sum(scores.get(p, 0) for p in blocks), tuple(sorted(blocks)),
        ),
    ))
    covered = {c for p in selected_blocks for c in candidates[p]}
    while True:
        remaining = {p: q for p, q in candidates.items() if len(q - covered) >= 2}
        if not remaining:
            break
        origin = max(
            remaining,
            key=lambda p: (len(remaining[p] - covered), scores.get(p, 0), -p[1], -p[0]),
        )
        selected_blocks.add(origin)
        covered.update(remaining[origin])
    return frozenset(selected_blocks)


def learn_complementary_terrain(
    labels: Mapping[Point, int],
    edges: Mapping[int, float],
    votes: Mapping[int, int],
    score_patch: Callable[[Point], float],
    dense_field: Callable[[frozenset[Point]], bool],
    cell_edge: Callable[[Point], float],
    weak_cell_texture: Callable[[Point], bool] | None = None,
) -> ComplementaryTerrain | None:
    """Join textured halves only when complete rectangles explain their union.

    Color proximity cannot establish a material here: colors can be arbitrarily
    different, while a background can share the same mean. Require independent
    support, interleaving, rectangle coverage and local texture instead. Keep the
    original 85% whole-cluster coverage gate, plus separate coverage of each
    texture-supported member. Already complete materials must not be merged.
    """
    accepted: list[tuple[float, tuple[int, int], ComplementaryTerrain]] = []
    for first, second in combinations(sorted(set(labels.values())), 2):
        pair = first, second
        if min(edges.get(c, 0) for c in pair) < 0.12:
            continue
        positions = frozenset(p for p, c in labels.items() if c in pair)
        if not 48 <= len(positions) <= len(labels) * 0.65:
            continue
        support_votes = sum(votes.get(c, 0) for c in pair)
        support_share = support_votes / max(1, sum(votes.values()))
        if min(votes.get(c, 0) for c in pair) < 2 or support_share < 0.65:
            continue
        # One borrowed border edge in a similarly colored background cell is
        # not the repeated texture observed in that room-local material.
        textured = frozenset(p for p in positions if cell_edge(p) >= edges[labels[p]] * 0.4)
        if weak_cell_texture is not None:
            # A mostly smooth tile quadrant can carry a weak distributed
            # motif. Admit at most one such quadrant per complete rectangle,
            # with three independently strong neighbors. Use the frozen strong
            # set: accepted weak cells cannot bootstrap further expansion.
            weak_supported = set()
            for p in positions-textured:
                if not weak_cell_texture(p):
                    continue
                x, y = p
                for dx, dy in ((0,0), (-16,0), (0,-16), (-16,-16)):
                    cells = cell_quad((x+dx, y+dy))
                    if cells <= positions and cells-{p} <= textured:
                        weak_supported.add(p)
                        break
            textured = textured | weak_supported
        origins = {p for p in textured if cell_quad(p) <= textured}
        scores = {p: score_patch(p) for p in origins}
        blocks = pack_textured_rectangles(textured, scores)
        covered = frozenset(c for p in blocks for c in cell_quad(p))
        coverage = len(covered) / len(positions)
        if coverage < 0.85 or len(blocks) < 12 or dense_field(blocks):
            continue
        mixed = sum(len({labels[c] for c in cell_quad(p)}) == 2 for p in blocks) / len(blocks)
        members = {c: frozenset(p for p, label in labels.items() if label == c) for c in pair}
        member_coverage = [len(covered & members[c]) / max(1, len(textured & members[c])) for c in pair]
        if mixed < 0.8 or min(member_coverage) < 0.8:
            continue
        single_coverage = [
            len({cell for p in pack_textured_rectangles(members[c]) for cell in cell_quad(p)}) / len(members[c])
            for c in pair
        ]
        if max(single_coverage) > 0.65:
            continue
        score = support_votes * (1 + 4 * median(edges[c] for c in pair)) * coverage * mixed
        profile = ComplementaryTerrain(
            terrain_cells=positions, full_blocks=blocks,
            seed_cluster=max(pair, key=lambda c: (votes.get(c, 0), -c)),
            support_votes=support_votes, full_coverage=coverage,
        )
        accepted.append((score, pair, profile))
    accepted.sort(key=lambda row: (row[0], row[1]), reverse=True)
    if len(accepted) > 1 and accepted[0][0] / max(1e-6, accepted[1][0]) < 1.25:
        return None
    return accepted[0][2] if accepted else None
