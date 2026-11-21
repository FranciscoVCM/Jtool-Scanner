"""Render a JMap with a JTool skin into a synthetic 800x608 room screenshot.

Offline evaluation tooling only: the scanner never imports this module, and
skin images are private local data (keep them under ignored paths such as
``.artifacts/skins``). A synthetic render has exact ground truth but lacks
real-game effects (decorations, lighting, capture scaling), so it measures and
ranks errors; real screenshots remain the adoption gate.

    python scripts/skin_render.py map.jmap SKIN_DIR out.png
"""
from __future__ import annotations

import configparser
import sys
import zipfile
from functools import lru_cache
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jtool_scanner.constants import (  # noqa: E402
    OBJ_APPLE, OBJ_BLOCK, OBJ_BULLET_BLOCKER, OBJ_GRAVITY_DOWN, OBJ_GRAVITY_UP,
    OBJ_JUMP_REFRESHER, OBJ_KILLER_BLOCK, OBJ_MINI_BLOCK, OBJ_MINI_KILLER_BLOCK,
    OBJ_MINI_SPIKE_DOWN, OBJ_MINI_SPIKE_LEFT, OBJ_MINI_SPIKE_RIGHT, OBJ_MINI_SPIKE_UP,
    OBJ_PLATFORM, OBJ_PLAYER_START, OBJ_SAVE, OBJ_SAVE_FLIP, OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT, OBJ_SPIKE_RIGHT, OBJ_SPIKE_UP, OBJ_WALLJUMP_LEFT,
    OBJ_WALLJUMP_RIGHT, OBJ_WARP, OBJ_WATER, OBJ_WATER_2, OBJ_WATER_3,
    ROOM_HEIGHT, ROOM_WIDTH,
)
from jtool_scanner.jmap import JMap  # noqa: E402

DEFAULT_SKIN = ROOT / "jtool_scanner" / "assets" / "jtool-pat-default"
SKIN_ZIP = ROOT / "local_corpus" / "skin-reference-20261108" / "skins.zip"
SKIN_CACHE = ROOT / ".artifacts" / "skins"

# type -> (skin filenames in preference order, default filename, size, origin offset)
SPRITES = {
    OBJ_BLOCK: (("block.png",), "block.png", (32, 32), (0, 0)),
    OBJ_MINI_BLOCK: (("miniblock.png",), "miniblock.png", (16, 16), (0, 0)),
    OBJ_SPIKE_UP: (("spikeup.png",), "spikeup.png", (32, 32), (0, 0)),
    OBJ_SPIKE_RIGHT: (("spikeright.png",), "spikeright.png", (32, 32), (0, 0)),
    OBJ_SPIKE_LEFT: (("spikeleft.png",), "spikeleft.png", (32, 32), (0, 0)),
    OBJ_SPIKE_DOWN: (("spikedown.png",), "spikedown.png", (32, 32), (0, 0)),
    OBJ_MINI_SPIKE_UP: (("miniup.png",), "miniup.png", (16, 16), (0, 0)),
    OBJ_MINI_SPIKE_RIGHT: (("miniright.png",), "miniright.png", (16, 16), (0, 0)),
    OBJ_MINI_SPIKE_LEFT: (("minileft.png",), "minileft.png", (16, 16), (0, 0)),
    OBJ_MINI_SPIKE_DOWN: (("minidown.png",), "minidown.png", (16, 16), (0, 0)),
    OBJ_APPLE: (("apple.png",), "apple-frame0.png", None, (-10, -12)),
    OBJ_SAVE: (("save.png", "save_strip2.png"), "save-frame0.png", (32, 32), (0, 0)),
    OBJ_SAVE_FLIP: ((), "save-flip.png", (32, 32), (0, 0)),
    OBJ_PLATFORM: (("platform.png",), "platform.png", (32, 16), (0, 0)),
    OBJ_WATER: (("water1.png",), "water1.png", (32, 32), (0, 0)),
    OBJ_WATER_2: (("water2.png",), "water2.png", (32, 32), (0, 0)),
    OBJ_WATER_3: (("water3.png",), "water3.png", (32, 32), (0, 0)),
    OBJ_WALLJUMP_LEFT: (("walljumpL.png",), "walljumpL.png", (32, 32), (0, 0)),
    OBJ_WALLJUMP_RIGHT: (("walljumpR.png",), "walljumpR.png", (32, 32), (0, 0)),
    OBJ_KILLER_BLOCK: (("killerblock.png",), "killerblock.png", (32, 32), (0, 0)),
    OBJ_MINI_KILLER_BLOCK: (("minikillerblock.png",), None, (16, 16), (0, 0)),
    OBJ_BULLET_BLOCKER: (("bulletblocker.png",), "bulletblocker.png", (32, 32), (0, 0)),
    OBJ_PLAYER_START: (("playerstart.png",), "playerstart.png", (32, 32), (0, 0)),
    OBJ_WARP: (("warp.png",), "warp.png", (32, 32), (0, 0)),
    OBJ_JUMP_REFRESHER: (("jumprefresher.png",), "jumprefresher.png", None, (-15, -15)),
    OBJ_GRAVITY_UP: (("gravityarrowup.png",), "gravity-up.png", (32, 32), (0, 0)),
    OBJ_GRAVITY_DOWN: (("gravityarrowdown.png",), "gravity-down.png", (32, 32), (0, 0)),
}


def _layer(type_id: int, terrain_over_spikes: bool = True) -> int:
    # Water, then spikes and terrain, then other objects, then markers. Fangame
    # screenshots usually draw terrain over spikes (a spike half inside a wall
    # is half hidden); the JTool editor/render_svg draws spikes on top.
    if type_id in (OBJ_WATER, OBJ_WATER_2, OBJ_WATER_3):
        return 0
    terrain = type_id in (OBJ_BLOCK, OBJ_MINI_BLOCK, OBJ_PLATFORM, OBJ_KILLER_BLOCK, OBJ_MINI_KILLER_BLOCK)
    spike = OBJ_SPIKE_UP <= type_id <= OBJ_MINI_SPIKE_DOWN
    if terrain or spike:
        return 2 if terrain == terrain_over_spikes else 1
    if type_id in (OBJ_SAVE, OBJ_SAVE_FLIP, OBJ_PLAYER_START, OBJ_WARP):
        return 4
    return 3


def extract_skins(zip_path: Path = SKIN_ZIP, cache: Path = SKIN_CACHE) -> list[Path]:
    """Extract the private skin archive once; return sorted skin directories."""
    marker = cache / ".extracted"
    if not marker.exists():
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(cache)
        marker.write_text(str(zip_path), encoding="utf8")
    return sorted(p for p in cache.glob("*/*") if p.is_dir() and (p / "block.png").exists())


@lru_cache(maxsize=4096)
def _sprite(path: str, size: tuple[int, int] | None) -> Image.Image:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    if size is not None and image.size != size:
        w, h = size
        if image.width >= w * 2 and image.height == h:
            image = image.crop((0, 0, w, h))  # animation strip: first frame
        else:
            image = image.resize(size, Image.Resampling.NEAREST)
    return image


def _sprite_for(skin: Path, type_id: int) -> tuple[Image.Image, tuple[int, int]] | None:
    entry = SPRITES.get(type_id)
    if entry is None:
        return None
    names, default, size, offset = entry
    for name in names:
        if (skin / name).exists():
            return _sprite(str(skin / name), size), offset
    if default is not None and (DEFAULT_SKIN / default).exists():
        return _sprite(str(DEFAULT_SKIN / default), size), offset
    return None


def _background(skin: Path) -> Image.Image:
    canvas = Image.new("RGB", (ROOM_WIDTH, ROOM_HEIGHT), (211, 211, 211))
    bg = skin / "bg.png"
    if not bg.exists():
        return canvas
    config = configparser.ConfigParser(strict=False)
    try:
        config.read(skin / "skin_config.ini", encoding="utf8")
    except (configparser.Error, UnicodeDecodeError):
        pass
    mode = config.get("bg", "type", fallback="stretch").strip().lower()
    with Image.open(bg) as opened:
        tile = opened.convert("RGB")
    if mode == "tile":
        for y in range(0, ROOM_HEIGHT, tile.height):
            for x in range(0, ROOM_WIDTH, tile.width):
                canvas.paste(tile, (x, y))
        return canvas
    return tile.resize((ROOM_WIDTH, ROOM_HEIGHT), Image.Resampling.BILINEAR)


def render(jmap: JMap, skin: Path, *, terrain_over_spikes: bool = True) -> Image.Image:
    """Composite the map's objects over the skin background in layer order."""
    canvas = _background(Path(skin)).convert("RGBA")
    for obj in sorted(jmap.objects, key=lambda o: _layer(o.type_id, terrain_over_spikes)):
        if obj.type_id == OBJ_PLAYER_START:
            continue  # an editor-only marker; game screenshots never show it
        found = _sprite_for(Path(skin), obj.type_id)
        if found is None:
            continue
        sprite, (dx, dy) = found
        canvas.alpha_composite(sprite, (obj.x + dx, obj.y + dy)) if (
            0 <= obj.x + dx and 0 <= obj.y + dy
            and obj.x + dx + sprite.width <= ROOM_WIDTH and obj.y + dy + sprite.height <= ROOM_HEIGHT
        ) else _paste_clipped(canvas, sprite, obj.x + dx, obj.y + dy)
    return canvas.convert("RGB")


def visible_objects(jmap: JMap) -> list:
    """Objects whose sprite overlaps the 800x608 room (others cannot be scanned)."""
    kept = []
    for obj in jmap.objects:
        entry = SPRITES.get(obj.type_id)
        if entry is None:
            kept.append(obj)
            continue
        size = entry[2] or (32, 32)
        x, y = obj.x + entry[3][0], obj.y + entry[3][1]
        if x < ROOM_WIDTH and y < ROOM_HEIGHT and x + size[0] > 0 and y + size[1] > 0:
            kept.append(obj)
    return kept


def _paste_clipped(canvas: Image.Image, sprite: Image.Image, x: int, y: int) -> None:
    left, top = max(0, -x), max(0, -y)
    right = min(sprite.width, ROOM_WIDTH - x)
    bottom = min(sprite.height, ROOM_HEIGHT - y)
    if right > left and bottom > top:
        canvas.alpha_composite(sprite.crop((left, top, right, bottom)), (x + left, y + top))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    render(JMap.from_file(sys.argv[1]), Path(sys.argv[2])).save(sys.argv[3])
    print(sys.argv[3])
