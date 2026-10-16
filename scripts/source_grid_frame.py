"""Original-source coverage for an existing, explicitly supplied grid view.

Research API, not an application binding. Reuse the scanner's rounded working
normalization; never infer a second crop/grid or treat its padding as evidence.
"""
from math import floor

from PIL import Image

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_sampling import SourceFrame


class GridResizeSourceFrame(SourceFrame):
    """Coverage of PIL's bilinear resize, including widened downsample taps.

    The base class's supplied-view constructor assumes a direct bilinear
    transform. A PIL-resized padded raster has a wider downsampling footprint.
    All contributing taps, not only two center taps, must be original-covered.
    """

    def __init__(self, image, room, *, extent, canonical):
        super().__init__(image, room, extent=extent, canonical=canonical)

        def coverage(origin, length, count, low, high):
            radius = max(1., length / count)
            result = []
            for index in range(count):
                center = origin + (index + .5) * length / count - .5
                if radius > 1:
                    valid = low <= center - radius + 1 and center + radius < high
                else:
                    first = floor(center)
                    valid = low <= first < high and (center == first or low <= first + 1 < high)
                result.append(valid)
            return tuple(result)

        object.__setattr__(self, '_covered_x', coverage(extent.x, extent.width, 800, room.x, room.right))
        object.__setattr__(self, '_covered_y', coverage(extent.y, extent.height, 608, room.y, room.bottom))
        object.__setattr__(self, '_resize_filter', True)

    def geometry_box(self, x, y, size):
        """Round in working coordinates BEFORE applying integer translation.

        Putting an odd translation inside round changes half-even ties. Native
        object origins are unchanged; this maps only their physical review boxes.
        """
        return Box(self.extent.x + int(round(x * self.extent.width / 800)),
                   self.extent.y + int(round(y * self.extent.height / 608)),
                   max(1, int(round(size * self.extent.width / 800))),
                   max(1, int(round(size * self.extent.height / 608))))


def frame_from_existing_grid(image, room, grid, normalization):
    """Validate and wrap EXISTING grid normalization, without re-inferring it.

    This API explicitly performs one RGB resize to create the canonical feature
    view. It is not a scan or a claim of free/shared resampling. Runtime adoption
    still needs sharing/cost qualification. Every unpadded working row must match
    its original physical source bytes before any source evidence can be used.
    """
    if not isinstance(grid, (tuple, list)) or len(grid) != 2 or any(
            not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in grid):
        raise ValueError('Source grid needs two positive integers')
    if not isinstance(image.data, bytes) or len(image.data) != image.width * image.height * 3:
        raise ValueError('Complete immutable original RGB required')
    if (room.width <= 0 or room.height <= 0 or room.x < 0 or room.y < 0
            or room.right > image.width or room.bottom > image.height):
        raise ValueError('Physical source crop must be inside the original image')
    columns, rows = grid
    tile_width, tile_height = room.width / columns, room.height / rows
    top = max(0, int(round((rows - 19) * tile_height)))
    width = min(room.width, int(round(25 * tile_width)))
    height = min(room.height - top, int(round(19 * tile_height)))
    missing_x, missing_y = max(0, 25 - columns), max(0, 19 - rows)
    left = int(round((missing_x // 2) * tile_width))
    right = int(round((missing_x - missing_x // 2) * tile_width))
    top_rows = (missing_y + 1) // 2
    pad_top = int(round(top_rows * tile_height))
    bottom = int(round((missing_y - top_rows) * tile_height))
    view = normalization.image
    expected = (-left, top - pad_top, width + left + right, height + pad_top + bottom)
    actual = (normalization.source_offset_x, normalization.source_offset_y, view.width, view.height)
    if actual != expected:
        raise ValueError('Existing grid normalization metadata does not match this source/grid')
    if not isinstance(view.data, bytes) or len(view.data) != view.width * view.height * 3:
        raise ValueError('Complete immutable working RGB required')
    source, working = memoryview(image.data), memoryview(view.data)
    for y in range(height):
        source_start = ((room.y + top + y) * image.width + room.x) * 3
        view_start = ((pad_top + y) * view.width + left) * 3
        if source[source_start:source_start + width * 3] != working[view_start:view_start + width * 3]:
            raise ValueError('Existing working view does not contain the original source pixels')
    extent = Box(room.x + normalization.source_offset_x, room.y + normalization.source_offset_y,
                 view.width, view.height)
    raster = Image.frombytes('RGB', (view.width, view.height), view.data).resize(
        (800, 608), Image.Resampling.BILINEAR)
    return GridResizeSourceFrame(image, room, extent=extent, canonical=RGBImage(800, 608, raster.tobytes()))
