"""Parser and writer for JTool `.jmap` files."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import re

from .codec import base32_to_float, base32_to_int, float_to_base32, int_to_base32, pad_left
from .constants import (
    MAX_COORD,
    MIN_COORD,
    OBJ_PLAYER_START,
    OFFICIAL_SAVE_IDS,
    OBJECT_NAMES,
)


@dataclass(slots=True, order=True)
class JMapObject:
    x: int
    y: int
    type_id: int

    @property
    def name(self) -> str:
        return OBJECT_NAMES.get(self.type_id, f"unknown_{self.type_id}")


@dataclass(slots=True)
class JMap:
    version: str = "1.3.5"
    infinite_jump: int = 0
    dot_kid: int = 0
    save_type: int = 1
    border_type: int = 0
    player_save_x: float = 0.0
    player_save_y: float = 0.0
    player_xscale: float = 1.0
    player_gravity: int = 1
    objects: list[JMapObject] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> "JMap":
        return cls.from_text(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_text(cls, text: str) -> "JMap":
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        header = lines[0].strip()
        sections = header.split("|")
        if len(sections) < 2 or sections[0] != "jtool":
            raise ValueError("not a valid JTool map")

        jmap = cls(version=sections[1])
        compact_objects = ""

        for section in sections[2:]:
            if not section:
                continue
            prefix, _, suffix = section.partition(":")
            if prefix == "inf":
                jmap.infinite_jump = int(float(suffix))
            elif prefix == "dot":
                jmap.dot_kid = int(float(suffix))
            elif prefix == "sav":
                jmap.save_type = int(float(suffix))
            elif prefix == "bor":
                jmap.border_type = int(float(suffix))
            elif prefix == "px":
                jmap.player_save_x = base32_to_float(suffix)
            elif prefix == "py":
                jmap.player_save_y = base32_to_float(suffix)
            elif prefix == "ps":
                jmap.player_xscale = float(suffix)
            elif prefix == "pg":
                jmap.player_gravity = int(float(suffix))
            elif prefix == "objects":
                compact_objects = suffix

        expanded = _parse_expanded_objects(lines)
        jmap.objects = expanded if expanded else _parse_compact_objects(compact_objects)
        return jmap

    def to_file(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_text(), encoding="utf-8", newline="\n")

    def to_text(self) -> str:
        compact = _build_compact_objects(self.objects)
        header = "|".join(
            [
                "jtool",
                self.version,
                f"inf:{self.infinite_jump}",
                f"dot:{self.dot_kid}",
                f"sav:{self.save_type}",
                f"bor:{self.border_type}",
                f"px:{float_to_base32(self.player_save_x)}",
                f"py:{float_to_base32(self.player_save_y)}",
                f"ps:{_format_number(self.player_xscale)}",
                f"pg:{self.player_gravity}",
                f"objects:{compact}",
            ]
        )

        expanded_parts: list[str] = []
        for obj in self.objects:
            expanded_parts.append(f"{obj.x} {obj.y} {obj.type_id}")

        detail_lines = [
            header,
            "",
            "data repeated below for easy parsing by other tools",
            "objects: (x, y, type)",
            " ".join(expanded_parts) + (" " if expanded_parts else ""),
            f"version:{self.version}",
            f"infinitejump:{self.infinite_jump}",
            f"dotkid:{self.dot_kid}",
            f"savetype:{self.save_type}",
            f"bordertype:{self.border_type}",
            f"playersavex:{_format_float(self.player_save_x)}",
            f"playersavey:{_format_float(self.player_save_y)}",
            f"playersavexscale:{_format_number(self.player_xscale)}",
        ]
        return "\n".join(detail_lines) + "\n"

    def copy(self) -> "JMap":
        return JMap(
            version=self.version,
            infinite_jump=self.infinite_jump,
            dot_kid=self.dot_kid,
            save_type=self.save_type,
            border_type=self.border_type,
            player_save_x=self.player_save_x,
            player_save_y=self.player_save_y,
            player_xscale=self.player_xscale,
            player_gravity=self.player_gravity,
            objects=[JMapObject(obj.x, obj.y, obj.type_id) for obj in self.objects],
        )

    def objects_of_type(self, type_id: int) -> list[JMapObject]:
        return [obj for obj in self.objects if obj.type_id == type_id]

    def without_type(self, type_id: int) -> "JMap":
        clone = self.copy()
        clone.objects = [obj for obj in clone.objects if obj.type_id != type_id]
        return clone

    def object_counts(self) -> Counter[int]:
        return Counter(obj.type_id for obj in self.objects)

    def replace_player_start(self, x: int, y: int, xscale: float | None = None) -> None:
        self.objects = [obj for obj in self.objects if obj.type_id != OBJ_PLAYER_START]
        self.objects.append(JMapObject(x, y, OBJ_PLAYER_START))
        self.player_save_x = x + 17
        self.player_save_y = y + 23
        if xscale is not None:
            self.player_xscale = xscale


def _parse_expanded_objects(lines: list[str]) -> list[JMapObject]:
    for index, line in enumerate(lines):
        if line.strip() == "objects: (x, y, type)" and index + 1 < len(lines):
            numbers = [int(match.group(0)) for match in re.finditer(r"-?\d+", lines[index + 1])]
            if len(numbers) % 3 != 0:
                raise ValueError("expanded object list does not contain x/y/type triples")
            return [
                JMapObject(numbers[i], numbers[i + 1], numbers[i + 2])
                for i in range(0, len(numbers), 3)
            ]
    return []


def _parse_compact_objects(compact: str) -> list[JMapObject]:
    objects: list[JMapObject] = []
    index = 0
    current_y: int | None = None
    while index < len(compact):
        char = compact[index]
        if char == "-":
            current_y = base32_to_int(compact[index + 1 : index + 3]) - 128
            index += 3
            continue
        if current_y is None:
            raise ValueError("compact object appeared before a y group")
        type_id = base32_to_int(char)
        x = base32_to_int(compact[index + 1 : index + 3]) - 128
        objects.append(JMapObject(x, current_y, type_id))
        index += 3
    return objects


def _build_compact_objects(objects: list[JMapObject]) -> str:
    by_y: dict[int, list[JMapObject]] = {}
    for obj in objects:
        if obj.type_id not in OFFICIAL_SAVE_IDS:
            raise ValueError(f"cannot save unsupported object type {obj.type_id}")
        if obj.x < MIN_COORD or obj.y < MIN_COORD or obj.x >= MAX_COORD or obj.y >= MAX_COORD:
            raise ValueError(
                f"object out of JTool save range: x={obj.x}, y={obj.y}, type={obj.type_id}"
            )
        by_y.setdefault(obj.y, []).append(obj)

    parts: list[str] = []
    for y in sorted(by_y):
        parts.append("-" + pad_left(int_to_base32(y + 128), 2, "0"))
        for obj in sorted(by_y[y], key=lambda item: (item.x, item.type_id)):
            parts.append(
                int_to_base32(obj.type_id) + pad_left(int_to_base32(obj.x + 128), 2, "0")
            )
    return "".join(parts)


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _format_float(value: float) -> str:
    return f"{value:.16f}"

