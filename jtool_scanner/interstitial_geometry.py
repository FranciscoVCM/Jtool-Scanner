"""Source evidence for false triangle gaps between adjacent real triangles.

Unsigned slopes also describe the empty space between two hazards. Only a
complete local configuration with opposite RGB material polarity and no
independent visible base can establish that the middle hypothesis is a gap.
Weak, clipped, occluded and competing material evidence deliberately abstains.
"""

from math import hypot, sqrt
from statistics import median

from .geometry import Box
from .image import RGBImage
from .spike_color_evidence import QuantizedColorSlopeField
from .spike_shape import SpikeShapeField, VERTICES


def _norm(vector: tuple[float, ...]) -> float:
    return sqrt(sum(channel * channel for channel in vector))


def _cosine(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(first, second)) / max(
        1e-9, _norm(first) * _norm(second),
    )


def interstitial_triangle_aliases(
    image: RGBImage,
    room: Box,
    spikes: list[tuple[int, int, int]],
    solids: list[tuple[int, int, int, int]],
) -> set[tuple[int, int, int]]:
    """Return unsupported full/mini gap hypotheses, never new detections.

    Existing triangles merely locate a test; original source slopes, signed
    RGB transitions and the complete base supply its evidence. New decisions
    do not become witnesses. Features are lazy and cached within this call.
    """
    present = set(spikes)
    rgb = None
    fields: dict[int, SpikeShapeField] = {}
    cache: dict[tuple[int, int, int, int], tuple] = {}
    rejected: set[tuple[int, int, int]] = set()

    def metrics(direction: int, x: int, y: int, size: int):
        key = direction, x, y, size
        if key in cache:
            return cache[key]
        vertices = tuple((a * size / 32, b * size / 32)
                         for a, b in VERTICES[direction])
        tip, *ends = vertices
        center_x = sum(a for a, _ in vertices) / 3
        center_y = sum(b for _, b in vertices) / 3
        vectors = []
        side_vectors = []
        for end in ends:
            tangent_x, tangent_y = end[0] - tip[0], end[1] - tip[1]
            normal_x, normal_y = -tangent_y, tangent_x
            if (normal_x * (center_x - (tip[0] + end[0]) / 2)
                    + normal_y * (center_y - (tip[1] + end[1]) / 2) > 0):
                normal_x, normal_y = -normal_x, -normal_y
            length = hypot(normal_x, normal_y)
            normal_x /= length
            normal_y /= length
            side = []
            for index in range(12):
                fraction = .2 + .6 * index / 11
                px = x + tip[0] + fraction * tangent_x
                py = y + tip[1] + fraction * tangent_y
                outside = rgb.pixel(round(px + size / 8 * normal_x),
                                    round(py + size / 8 * normal_y))
                inside = rgb.pixel(round(px - size / 8 * normal_x),
                                   round(py - size / 8 * normal_y))
                side.append(tuple(outside[k] - inside[k] for k in range(3)))
            side_vectors.append(tuple(median(v[k] for v in side) for k in range(3)))
            vectors.extend(side)
        vector = tuple(median(v[k] for v in vectors) for k in range(3))
        first, second = ends
        tangent_x, tangent_y = second[0] - first[0], second[1] - first[1]
        normal_x, normal_y = -tangent_y, tangent_x
        length = hypot(normal_x, normal_y)
        normal_x /= length
        normal_y /= length
        bases = []
        masked = False
        for index in range(12):
            fraction = .2 + .6 * index / 11
            px = x + first[0] + fraction * tangent_x
            py = y + first[1] + fraction * tangent_y
            coordinates = [(round(px + offset * normal_x),
                            round(py + offset * normal_y))
                           for offset in (-size / 8, 0, size / 8)]
            if any(bx <= sx < bx + width and by <= sy < by + height
                   for sx, sy in coordinates for bx, by, width, height in solids):
                masked = True
            samples = [rgb.pixel(*point) for point in coordinates]
            # A real base can be an outline between equal fills, not just a
            # color step. Retain either form of independently visible edge.
            bases.append(max(_norm(tuple(a[k] - b[k] for k in range(3)))
                             for a, b in ((samples[0], samples[1]),
                                          (samples[1], samples[2]),
                                          (samples[0], samples[2]))))
        cache[key] = vector, side_vectors, bases, masked
        return cache[key]

    opposite = {3: 6, 6: 3, 4: 5, 5: 4}
    for original, x, y in sorted(present):
        size = 16 if original > 6 else 32
        direction = original - 4 if size == 16 else original
        other = opposite[direction] + (4 if size == 16 else 0)
        dx, dy = (size // 2, 0) if direction in (3, 6) else (0, size // 2)
        peers = [(other, x - dx, y - dy), (other, x + dx, y + dy)]
        if not all(peer in present for peer in peers):
            continue
        # Complete sampling margins: a clipped or offscreen base is unknown.
        if any(px < 4 or py < 4 or px + size > 796 or py + size > 604
               for _, px, py in [(original, x, y), *peers]):
            continue
        if rgb is None:
            rgb = QuantizedColorSlopeField(image, room)
        if size not in fields:
            fields[size] = SpikeShapeField(image, room, native_size=size)
        field = fields[size]
        if any(field.localized_score(px, py, d - 4 if size == 16 else d) < 11 / 12
               for d, px, py in [(original, x, y), *peers]):
            continue
        vector, sides, base, masked = metrics(direction, x, y, size)
        peer_metrics = [metrics(d - 4 if size == 16 else d, px, py, size)
                        for d, px, py in peers]
        strength = min(_norm(peer[0]) for peer in peer_metrics)
        # Peers normally have backing at their bases; only the candidate's
        # hidden base makes this negative evidence unavailable.
        if masked or strength < 12 or _norm(vector) < .5 * strength:
            continue
        if _cosine(peer_metrics[0][0], peer_metrics[1][0]) < .9:
            continue
        if any(_cosine(vector, peer[0]) > -.9 for peer in peer_metrics):
            continue
        if any(_cosine(side, vector) < .9 for side in sides):
            continue
        if sum(value > .4 * strength for value in base) > 3:
            continue
        rejected.add((original, x, y))
    return rejected
