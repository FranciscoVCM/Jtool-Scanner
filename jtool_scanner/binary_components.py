"""Exact binary stroke components without a per-pixel flood traversal."""

from PIL import Image, ImageFilter


def dilated_ink_components(
    foreground: bytes | bytearray,
    width: int,
    height: int,
    minimum: int = 1,
) -> list[tuple[int, int, int, int, int]]:
    """Return (x, y, width, height, original ink) in first-pixel order.

    The input must contain only zero/one bytes. Apply radius-one square
    dilation, then eight-connectivity, clipped to the input bounds. Count only
    original ink belonging to each component, never disconnected ink enclosed
    by its bounding box. Adjacent-row runs can touch diagonally. Keeping the
    earliest run as root preserves the ordering of a row-major flood traversal.
    """
    if width < 1 or height < 1 or len(foreground) != width * height:
        raise ValueError("Binary mask dimensions do not match its data")
    if minimum < 0:
        raise ValueError("Minimum original ink must be nonnegative")
    mask = bytes(foreground)
    if mask.count(0) + mask.count(1) != len(mask):
        raise ValueError("Binary mask must contain only zero and one")
    expanded = Image.frombytes("L", (width, height), mask).filter(
        ImageFilter.MaxFilter(3)
    ).tobytes()
    parents: list[int] = []
    bounds: list[list[int]] = []

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        first, second = root(first), root(second)
        if first == second:
            return
        if second < first:
            first, second = second, first
        parents[second] = first
        left, top, right, bottom, ink = bounds[second]
        old = bounds[first]
        bounds[first] = [
            min(old[0], left), min(old[1], top),
            max(old[2], right), max(old[3], bottom), old[4] + ink,
        ]

    previous: list[tuple[int, int, int]] = []
    for y in range(height):
        row = expanded[y * width:(y + 1) * width]
        original = mask[y * width:(y + 1) * width]
        current: list[tuple[int, int, int]] = []
        cursor = prior = 0
        while cursor < width:
            start = row.find(b"\x01", cursor)
            if start < 0:
                break
            end = row.find(b"\x00", start)
            if end < 0:
                end = width
            identifier = len(parents)
            parents.append(identifier)
            bounds.append([start, y, end, y + 1, original[start:end].count(1)])
            current.append((start, end, identifier))
            while prior < len(previous) and previous[prior][1] < start:
                prior += 1
            index = prior
            # Endpoints are exclusive: equality still permits a diagonal link.
            while index < len(previous) and previous[index][0] <= end:
                union(identifier, previous[index][2])
                index += 1
            cursor = end
        previous = current
    return [
        (left, top, right - left, bottom - top, ink)
        for index, (left, top, right, bottom, ink) in enumerate(bounds)
        if parents[index] == index and ink >= minimum
    ]
