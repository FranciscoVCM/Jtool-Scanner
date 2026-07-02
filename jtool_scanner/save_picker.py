"""Save-selection and start-position rules."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

from .constants import OBJ_PLAYER_START, OBJ_SAVE, ROOM_HEIGHT, ROOM_WIDTH
from .jmap import JMap, JMapObject


@dataclass(frozen=True, slots=True)
class SaveChoice:
    save: JMapObject
    policy: str
    reason: str


def choose_save(jmap: JMap, policy: str = "auto") -> SaveChoice | None:
    saves = _ordered_saves(jmap.objects_of_type(OBJ_SAVE))
    if not saves or policy == "none":
        return None

    normalized = policy.strip().lower()
    if normalized == "auto":
        return _choose_auto(saves)
    if normalized == "bottom-left":
        return SaveChoice(_nearest(saves, 0, ROOM_HEIGHT), policy, "nearest bottom-left corner")
    if normalized == "left":
        return SaveChoice(min(saves, key=lambda obj: (obj.x, -obj.y)), policy, "leftmost save")
    if normalized == "bottom":
        return SaveChoice(max(saves, key=lambda obj: (obj.y, -obj.x)), policy, "lowest save")
    if normalized.startswith("index:"):
        index = int(normalized.split(":", 1)[1])
        if index < 0 or index >= len(saves):
            raise ValueError(f"save index {index} is out of range for {len(saves)} saves")
        return SaveChoice(saves[index], policy, f"save index {index}")
    if normalized.startswith("nearest:"):
        match = re.fullmatch(r"nearest:(-?\d+),(-?\d+)", normalized)
        if not match:
            raise ValueError("nearest policy must look like nearest:X,Y")
        x = int(match.group(1))
        y = int(match.group(2))
        return SaveChoice(_nearest(saves, x, y), policy, f"nearest ({x},{y})")

    raise ValueError(f"unknown save policy {policy!r}")


def move_start_to_save(jmap: JMap, policy: str = "auto") -> SaveChoice | None:
    choice = choose_save(jmap, policy)
    if choice is None:
        return None
    jmap.replace_player_start(choice.save.x, choice.save.y)
    return choice


def _choose_auto(saves: list[JMapObject]) -> SaveChoice:
    left_cutoff = ROOM_WIDTH * 0.5
    bottom_cutoff = ROOM_HEIGHT * 0.5

    bottom_left = [save for save in saves if save.x <= left_cutoff and save.y >= bottom_cutoff]
    if bottom_left:
        return SaveChoice(
            min(bottom_left, key=lambda obj: (obj.x, -obj.y)),
            "auto",
            "save in the bottom-left half",
        )

    left_side = [save for save in saves if save.x <= left_cutoff]
    if left_side:
        return SaveChoice(
            min(left_side, key=lambda obj: (obj.x, -obj.y)),
            "auto",
            "left-side fallback",
        )

    bottom_side = [save for save in saves if save.y >= bottom_cutoff]
    if bottom_side:
        return SaveChoice(
            max(bottom_side, key=lambda obj: (obj.y, -obj.x)),
            "auto",
            "bottom-side fallback",
        )

    return SaveChoice(_nearest(saves, 0, ROOM_HEIGHT), "auto", "nearest bottom-left fallback")


def _nearest(saves: list[JMapObject], x: int, y: int) -> JMapObject:
    return min(saves, key=lambda obj: (math.hypot(obj.x - x, obj.y - y), obj.x, -obj.y))


def _ordered_saves(saves: list[JMapObject]) -> list[JMapObject]:
    return sorted(saves, key=lambda obj: (obj.y, obj.x))

