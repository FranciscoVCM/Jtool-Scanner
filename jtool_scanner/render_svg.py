"""Simple SVG renderer for JTool maps."""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

from .constants import (
    GRID_SIZE,
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_BULLET_BLOCKER,
    OBJ_GRAVITY_DOWN,
    OBJ_GRAVITY_UP,
    OBJ_JUMP_REFRESHER,
    OBJ_KILLER_BLOCK,
    OBJ_MINI_BLOCK,
    OBJ_MINI_KILLER_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_PLATFORM,
    OBJ_PLAYER_START,
    OBJ_SAVE,
    OBJ_SAVE_FLIP,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
    OBJ_WALLJUMP_LEFT,
    OBJ_WALLJUMP_RIGHT,
    OBJ_WARP,
    OBJ_WATER,
    OBJ_WATER_2,
    OBJ_WATER_3,
    ROOM_HEIGHT,
    ROOM_WIDTH,
)
from .jmap import JMap, JMapObject


_JTOOL_SPRITES: dict[int, tuple[str, int, int, int, int, bool]] = {
    OBJ_BLOCK: ("block.png", 32, 32, 0, 0, False),
    OBJ_MINI_BLOCK: ("miniblock.png", 16, 16, 0, 0, False),
    OBJ_SPIKE_UP: ("spikeup.png", 32, 32, 0, 0, True),
    OBJ_SPIKE_RIGHT: ("spikeright.png", 32, 32, 0, 0, True),
    OBJ_SPIKE_LEFT: ("spikeleft.png", 32, 32, 0, 0, True),
    OBJ_SPIKE_DOWN: ("spikedown.png", 32, 32, 0, 0, True),
    OBJ_MINI_SPIKE_UP: ("miniup.png", 16, 16, 0, 0, True),
    OBJ_MINI_SPIKE_RIGHT: ("miniright.png", 16, 16, 0, 0, True),
    OBJ_MINI_SPIKE_LEFT: ("minileft.png", 16, 16, 0, 0, True),
    OBJ_MINI_SPIKE_DOWN: ("minidown.png", 16, 16, 0, 0, True),
    # Apple and jump-refresher JMap coordinates are sprite origins rather
    # than top-left corners.  These offsets mirror the upstream GameMaker
    # origins (10,12) and (15,15), respectively.
    OBJ_APPLE: ("apple-frame0.png", 21, 24, -10, -12, True),
    OBJ_SAVE: ("save-frame0.png", 32, 32, 0, 0, False),
    OBJ_PLATFORM: ("platform.png", 32, 16, 0, 0, False),
    OBJ_WATER: ("water1.png", 32, 32, 0, 0, False),
    OBJ_WATER_2: ("water2.png", 32, 32, 0, 0, False),
    # Upstream names describe the facing wall, while the app's names describe
    # the visible half of the grid cell.
    OBJ_WALLJUMP_LEFT: ("walljumpR.png", 32, 32, 0, 0, False),
    OBJ_WALLJUMP_RIGHT: ("walljumpL.png", 32, 32, 0, 0, False),
    OBJ_KILLER_BLOCK: ("killerblock.png", 32, 32, 0, 0, True),
    OBJ_BULLET_BLOCKER: ("bulletblocker.png", 32, 32, 0, 0, False),
    OBJ_PLAYER_START: ("playerstart.png", 32, 32, 0, 0, False),
    OBJ_WARP: ("warp.png", 32, 32, 0, 0, False),
    OBJ_JUMP_REFRESHER: ("jumprefresher.png", 32, 32, -15, -15, False),
    OBJ_WATER_3: ("water3.png", 32, 32, 0, 0, False),
    OBJ_GRAVITY_UP: ("gravity-up.png", 32, 32, 0, 0, False),
    OBJ_GRAVITY_DOWN: ("gravity-down.png", 32, 32, 0, 0, False),
    OBJ_SAVE_FLIP: ("save-flip.png", 32, 32, 0, 0, False),
}


def render_svg(jmap: JMap, title: str = "JTool map preview") -> str:
    body: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ROOM_WIDTH}" height="{ROOM_HEIGHT}" '
        f'viewBox="0 0 {ROOM_WIDTH} {ROOM_HEIGHT}" role="img" aria-label="{escape(title)}">',
        "<defs>",
        '<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">',
        '<path d="M 32 0 L 0 0 0 32" fill="none" stroke="#b7b7b7" stroke-width="1"/>',
        "</pattern>",
        # JTool applies the pat_default skin's idle-killer value (175/255) to
        # spike, fruit and killer-block sprites.  Preserve the exact sprite
        # pixels while reproducing that component-wise tint.
        '<filter id="jtool-killer-tint" color-interpolation-filters="sRGB">',
        '<feComponentTransfer>',
        '<feFuncR type="linear" slope="0.68627451"/>',
        '<feFuncG type="linear" slope="0.68627451"/>',
        '<feFuncB type="linear" slope="0.68627451"/>',
        "</feComponentTransfer>",
        "</filter>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#d3d3d3"/>',
        '<rect width="100%" height="100%" fill="url(#grid)"/>',
    ]

    for obj in sorted(jmap.objects, key=lambda item: _render_priority(item.type_id)):
        body.extend(_render_object(obj))

    body.append("</svg>")
    return "\n".join(body) + "\n"


def _render_object(obj: JMapObject) -> list[str]:
    x, y, type_id = obj.x, obj.y, obj.type_id

    sprite = _JTOOL_SPRITES.get(type_id)
    if sprite is not None:
        filename, width, height, offset_x, offset_y, killer_tint = sprite
        return [
            _jtool_sprite(
                filename,
                x + offset_x,
                y + offset_y,
                width,
                height,
                killer_tint=killer_tint,
            )
        ]

    if type_id == OBJ_BLOCK:
        return [_rect(x, y, 32, 32, "#b8b8b8", "#111", 2), _edge(x, y, 32, 32)]
    if type_id == OBJ_MINI_BLOCK:
        return [_rect(x, y, 16, 16, "#b8b8b8", "#111", 1)]
    if type_id in (OBJ_SPIKE_UP, OBJ_SPIKE_RIGHT, OBJ_SPIKE_LEFT, OBJ_SPIKE_DOWN):
        return [_spike(x, y, 32, type_id)]
    if type_id in (OBJ_MINI_SPIKE_UP, OBJ_MINI_SPIKE_RIGHT, OBJ_MINI_SPIKE_LEFT, OBJ_MINI_SPIKE_DOWN):
        return [_mini_spike(x, y, type_id)]
    if type_id in (OBJ_WATER, OBJ_WATER_2, OBJ_WATER_3):
        color = {OBJ_WATER: "#5ba9e8", OBJ_WATER_2: "#7ecfd0", OBJ_WATER_3: "#9fe4e4"}[type_id]
        return [_rect(x, y, 32, 32, color, "none", 0, opacity=0.72)]
    if type_id in (OBJ_WALLJUMP_LEFT, OBJ_WALLJUMP_RIGHT):
        raise AssertionError("walljump sprite mapping is incomplete")
    if type_id == OBJ_SAVE or type_id == OBJ_SAVE_FLIP:
        return _save(x, y, flipped=type_id == OBJ_SAVE_FLIP)
    if type_id == OBJ_PLAYER_START:
        return _start(x, y)
    if type_id == OBJ_WARP:
        return _warp(x, y)
    if type_id == OBJ_PLATFORM:
        return [_rect(x, y + 10, 32, 12, "#9d9d9d", "#111", 1)]
    if type_id in (OBJ_KILLER_BLOCK, OBJ_MINI_KILLER_BLOCK):
        size = 16 if type_id == OBJ_MINI_KILLER_BLOCK else 32
        return [_rect(x, y, size, size, "#555", "#111", 1), _line(x, y, x + size, y + size), _line(x + size, y, x, y + size)]
    if type_id == OBJ_BULLET_BLOCKER:
        return [_rect(x, y, 32, 32, "#d8d8d8", "#111", 1), _rect(x + 8, y + 11, 16, 10, "#a8a8a8", "#555", 1)]
    if type_id == OBJ_APPLE:
        # JTool stores fruit coordinates at the sprite center, unlike terrain
        # objects whose coordinates describe their top-left corner.
        return [f'<circle cx="{x}" cy="{y}" r="11" fill="#c43" stroke="#711" stroke-width="2"/>']
    if type_id == OBJ_JUMP_REFRESHER:
        # JTool's refresher sprite uses a centered origin (15,15), so its
        # stored coordinates are the icon center rather than a cell corner.
        return [f'<circle cx="{x}" cy="{y}" r="12" fill="#d8d8d8" stroke="#777" stroke-width="3"/>']
    if type_id == OBJ_GRAVITY_UP:
        return [_arrow(x, y, up=True)]
    if type_id == OBJ_GRAVITY_DOWN:
        return [_arrow(x, y, up=False)]

    return [_rect(x, y, 32, 32, "#f0a", "#111", 1), f'<text x="{x + 4}" y="{y + 20}" font-size="10">{type_id}</text>']


def _render_priority(type_id: int) -> tuple[int, int]:
    if type_id in (OBJ_WATER, OBJ_WATER_2, OBJ_WATER_3):
        return (0, type_id)
    if type_id in (OBJ_BLOCK, OBJ_MINI_BLOCK, OBJ_PLATFORM):
        return (1, type_id)
    if type_id in (OBJ_SPIKE_UP, OBJ_SPIKE_RIGHT, OBJ_SPIKE_LEFT, OBJ_SPIKE_DOWN):
        return (2, type_id)
    if type_id in (OBJ_MINI_SPIKE_UP, OBJ_MINI_SPIKE_RIGHT, OBJ_MINI_SPIKE_LEFT, OBJ_MINI_SPIKE_DOWN):
        return (2, type_id)
    if type_id in (OBJ_SAVE, OBJ_SAVE_FLIP, OBJ_PLAYER_START, OBJ_WARP):
        return (4, type_id)
    return (3, type_id)


def _rect(x: int, y: int, w: int, h: int, fill: str, stroke: str, stroke_width: int, opacity: float = 1.0) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke != "none" else ""
    opacity_attr = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"{stroke_attr}{opacity_attr}/>'


def _edge(x: int, y: int, w: int, h: int) -> str:
    return f'<path d="M{x + 2} {y + 2} H{x + w - 2} V{y + h - 2}" fill="none" stroke="#d0d0d0" stroke-width="2"/>'


def _line(x1: int, y1: int, x2: int, y2: int) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#111" stroke-width="1"/>'


def _spike(x: int, y: int, size: int, type_id: int) -> str:
    points = {
        OBJ_SPIKE_UP: [(x, y + size), (x + size / 2, y), (x + size, y + size)],
        OBJ_SPIKE_RIGHT: [(x, y), (x + size, y + size / 2), (x, y + size)],
        OBJ_SPIKE_LEFT: [(x + size, y), (x, y + size / 2), (x + size, y + size)],
        OBJ_SPIKE_DOWN: [(x, y), (x + size / 2, y + size), (x + size, y)],
    }[type_id]
    return _polygon(points, "#d8d8d8", "#111")


def _mini_spike(x: int, y: int, type_id: int) -> str:
    points = {
        OBJ_MINI_SPIKE_UP: [(x, y + 16), (x + 8, y), (x + 16, y + 16)],
        OBJ_MINI_SPIKE_RIGHT: [(x, y), (x + 16, y + 8), (x, y + 16)],
        OBJ_MINI_SPIKE_LEFT: [(x + 16, y), (x, y + 8), (x + 16, y + 16)],
        OBJ_MINI_SPIKE_DOWN: [(x, y), (x + 8, y + 16), (x + 16, y)],
    }[type_id]
    return _polygon(points, "#d8d8d8", "#111")


def _polygon(points: list[tuple[float, float]], fill: str, stroke: str) -> str:
    encoded = " ".join(f"{x:g},{y:g}" for x, y in points)
    return f'<polygon points="{encoded}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'


def _save(x: int, y: int, flipped: bool) -> list[str]:
    label_y = y + 8 if not flipped else y + 29
    return [
        _rect(x + 2, y + 2, 28, 28, "#efe44a", "#111", 1),
        f'<circle cx="{x + 16}" cy="{y + 17}" r="9" fill="#b81220" stroke="#610000" stroke-width="2"/>',
        f'<text x="{x + 4}" y="{label_y}" font-family="monospace" font-size="7" fill="#111">SAVE</text>',
    ]


def _start(x: int, y: int) -> list[str]:
    return [
        f'<text x="{x + 1}" y="{y + 8}" font-family="monospace" font-size="8" fill="#111">start</text>',
        f'<circle cx="{x + 17}" cy="{y + 22}" r="7" fill="#4169e1" stroke="#111" stroke-width="1"/>',
        f'<rect x="{x + 13}" y="{y + 20}" width="12" height="10" fill="#333" stroke="#111" stroke-width="1"/>',
    ]


def _warp(x: int, y: int) -> list[str]:
    return [
        f'<circle cx="{x + 16}" cy="{y + 16}" r="13" fill="none" stroke="#7827ff" stroke-width="5" opacity="0.65"/>',
        f'<circle cx="{x + 16}" cy="{y + 16}" r="7" fill="#250071" opacity="0.85"/>',
    ]


@lru_cache(maxsize=None)
def _jtool_sprite_data(filename: str) -> str:
    path = Path(__file__).with_name("assets") / "jtool-pat-default" / filename
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _jtool_sprite(
    filename: str,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    killer_tint: bool = False,
) -> str:
    filter_attr = ' filter="url(#jtool-killer-tint)"' if killer_tint else ""
    return (
        f'<image href="{_jtool_sprite_data(filename)}" x="{x}" y="{y}" '
        f'width="{width}" height="{height}" image-rendering="pixelated"{filter_attr}/>'
    )


def _arrow(x: int, y: int, up: bool) -> str:
    if up:
        return _polygon([(x + 16, y + 4), (x + 29, y + 18), (x + 21, y + 18), (x + 21, y + 30), (x + 11, y + 30), (x + 11, y + 18), (x + 3, y + 18)], "#ff6060", "#111")
    return _polygon([(x + 16, y + 28), (x + 29, y + 14), (x + 21, y + 14), (x + 21, y + 2), (x + 11, y + 2), (x + 11, y + 14), (x + 3, y + 14)], "#4fc3f7", "#111")
