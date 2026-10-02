"""Deterministic local-background source scenes for test/evaluation tooling.

Authored source geometry and evaluation truth stay separate from recognition
inputs. This is a renderer, not a detector or a current-scanner recall claim.
The default lattice has 24 true-mini scenes and 24 empty-gap controls.
"""
from math import isfinite
from random import Random

from PIL import Image, ImageDraw, ImageOps

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage

LOCAL_MATERIAL_VARIATIONS = (
    "checker3px_delta60", "seeded_noise_delta60", "smooth_x_gradient_delta60",
)
LOCAL_MATERIAL_WIDTHS = ((2, 1), (3, 2))
LOCAL_MATERIAL_SCALES = (1, 1.25)
LOCAL_MATERIAL_POLARITIES = ("identity", "invert")


def create_local_material_scene(
    variation, *, full_outline_width=2, mini_outline_width=1, scale=1,
    polarity="identity", include_mini=True, mean_shift=0,
):
    """Return source, room, authored truth, coarse hypotheses, solids, options.

    Paint localized background nuisance before the objects, leaving their
    actual pixels intact. Same scene has two known full triangles, a separately
    optional native16 triangle, and an intentional coarse alias. An empty-gap
    control omits only the known mini. Source truth is not a recognition input.
    """
    if variation not in LOCAL_MATERIAL_VARIATIONS:
        raise ValueError("unsupported localized material variation")
    for width in (full_outline_width, mini_outline_width):
        if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 4:
            raise ValueError("outline width must be an integer from 1 to 4")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not isfinite(scale) or scale <= 0:
        raise ValueError("scale must be finite and positive")
    if polarity not in LOCAL_MATERIAL_POLARITIES:
        raise ValueError("unsupported palette polarity")
    if not isinstance(include_mini, bool):
        raise ValueError("include_mini must be boolean")
    if isinstance(mean_shift, bool) or not isinstance(mean_shift, int) or not -60 <= mean_shift <= 60:
        raise ValueError("mean shift must be an integer from -60 to 60")

    raster = Image.new("RGB", (800, 608), (140, 165, 163))
    ImageDraw.Draw(raster).rectangle((304, 352, 415, 383), fill=(83, 49, 47))
    rng = Random(107)
    for y in range(330, 352):
        for x in range(348, 376):
            if variation == "checker3px_delta60":
                delta = 60 if (x // 3 + y // 3) % 2 else -60
            elif variation == "seeded_noise_delta60":
                delta = rng.randint(-60, 60)
            else:
                delta = round(-60 + 120 * (x - 348) / 27)
            raster.putpixel((x, y), tuple(max(0, min(255, level + delta + mean_shift))
                                         for level in (140, 165, 163)))

    truth = [(3, 320, 320), (3, 368, 320)] + ([(7, 352, 336)] if include_mini else [])
    # These are authored synthetic up-triangle vertices, not a production
    # coordinate/name/palette filter. Only pixels/room/coarse/solids feed helpers.
    for type_id, x, y in truth:
        size = 16 if type_id > 6 else 32
        vertices = [(x + a * size / 32, y + b * size / 32)
                    for a, b in ((16, 0), (0, 32), (32, 32))]
        mask = Image.new("L", (800, 608), 0)
        ImageDraw.Draw(mask).polygon(vertices, fill=255)
        shade = Image.new("RGB", (800, 608), (215, 217, 221))
        ImageDraw.Draw(shade).rectangle((x, y, x + size / 2, y + size), fill=(132, 137, 144))
        raster.paste(shade, (0, 0), mask)
        ImageDraw.Draw(raster).line(vertices + [vertices[0]], fill=(45, 48, 53),
                                   width=mini_outline_width if size == 16 else full_outline_width)
    if polarity == "invert":
        raster = ImageOps.invert(raster)
    raster = raster.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
    image = RGBImage(raster.width, raster.height, raster.tobytes())
    room = Box(0, 0, image.width, image.height)
    coarse = [(3, 320, 320), (3, 368, 320), (3, 336, 320)]
    solids = [(304, 352, 112, 32)]
    options = dict(variation=variation, full_outline_width=full_outline_width,
                   mini_outline_width=mini_outline_width, scale=scale,
                   polarity=polarity, include_mini=include_mini, mean_shift=mean_shift,
                   background_patch_native_box=(348, 330, 28, 22), seed=107)
    return image, room, truth, coarse, solids, options


def local_material_specs(*, mean_shifts=(0,)):
    """Complete deterministic lattice; do not select rows using helper results."""
    return [dict(variation=variation, full_outline_width=widths[0],
                 mini_outline_width=widths[1], scale=scale, polarity=polarity,
                 include_mini=include_mini, mean_shift=mean_shift)
            for mean_shift in mean_shifts for variation in LOCAL_MATERIAL_VARIATIONS
            for widths in LOCAL_MATERIAL_WIDTHS for scale in LOCAL_MATERIAL_SCALES
            for polarity in LOCAL_MATERIAL_POLARITIES for include_mini in (True, False)]
