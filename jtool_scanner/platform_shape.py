"""Conservative palette-independent recognition of the default platform sprite.

This supplements, not replaces, the unknown-skin geometry routes.  Local
zero-mean correlation keeps brightness and palette out of the comparison;
it does not imply recognition of arbitrary new sprite silhouettes.
"""

from functools import lru_cache
from math import sqrt
from pathlib import Path

from .constants import ROOM_HEIGHT, ROOM_WIDTH
from .geometry import Box
from .image import RGBImage, load_png


@lru_cache(maxsize=1)
def _reference() -> tuple[float, ...]:
    sprite = load_png(
        Path(__file__).parent
        / "assets/jtool-pat-default/detection/platform-default-frame.png"
    )
    values = [
        sum(c * w for c, w in zip(sprite.pixel(x, y), (0.30, 0.59, 0.11)))
        for y in range(2, 14)
        for x in range(2, 30)
    ]
    mean = sum(values) / len(values)
    norm = sqrt(sum((v - mean) ** 2 for v in values))
    return tuple((v - mean) / norm for v in values)


def default_platform_shape_score(image: RGBImage, room: Box, x: int, y: int) -> float:
    """Match inner frame/posts without sampling unavailable below-room context.

    A two-pixel vertical capture phase is tolerated without moving the JMap
    origin. The outer border is excluded because resampling mixes background
    into it. Flat patches and contrast-inverted patterns are not matches.
    """
    if not (0 <= x <= ROOM_WIDTH - 32 and 0 <= y <= ROOM_HEIGHT - 16):
        return 0.0
    reference = _reference()
    sx, sy = room.width / ROOM_WIDTH, room.height / ROOM_HEIGHT
    xs = [int(room.x + (x + dx + 0.5) * sx) for dx in range(2, 30)]
    best = 0.0
    for phase in (-2, -1, 0, 1, 2):
        values = []
        for dy in range(2, 14):
            py = int(room.y + (y + dy + phase + 0.5) * sy)
            for px in xs:
                r, g, b = image.pixel(px, py)
                values.append(r * 0.30 + g * 0.59 + b * 0.11)
        mean = sum(values) / len(values)
        norm = sqrt(sum((v - mean) ** 2 for v in values))
        if norm < 3 * sqrt(len(values)):
            continue
        score = sum((v - mean) * t for v, t in zip(values, reference)) / norm
        best = max(best, score)
    return best
