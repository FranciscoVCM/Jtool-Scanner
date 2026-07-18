"""Editable scan projects used between detection and JTool export."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from html import escape
import json
from pathlib import Path
import re
from typing import Any

from .constants import (
    OBJ_MINI_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_PLAYER_START,
    OBJ_SAVE,
    OBJ_SAVE_FLIP,
    OFFICIAL_SAVE_IDS,
    OBJECT_NAMES,
)
from .geometry import Box
from .jmap import JMap, JMapObject
from .render_svg import render_svg
from .save_picker import move_start_to_save


PROJECT_FORMAT = "jtool-scanner-correction"
PROJECT_VERSION = 1
_TYPE_IDS_BY_NAME = {name: type_id for type_id, name in OBJECT_NAMES.items()}
_TYPE_ALIASES = {
    "water_1": "water",
    "miniblock": "mini_block",
    "minispike_up": "mini_spike_up",
    "minispike_right": "mini_spike_right",
    "minispike_left": "mini_spike_left",
    "minispike_down": "mini_spike_down",
    "vine_left": "walljump_left",
    "vine_right": "walljump_right",
}


@dataclass(slots=True)
class CorrectionObject:
    """One scanner candidate or manually-added JTool object."""

    object_id: str
    x: int
    y: int
    type_id: int
    enabled: bool = True
    source: str = "scanner"
    detection_kind: str | None = None
    score: float | None = None
    image_box: Box | None = None
    original: dict[str, int] | None = None

    @property
    def type_name(self) -> str:
        return OBJECT_NAMES.get(self.type_id, f"unknown_{self.type_id}")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.object_id,
            "x": self.x,
            "y": self.y,
            "type_id": self.type_id,
            "type_name": self.type_name,
            "enabled": self.enabled,
            "source": self.source,
        }
        if self.detection_kind is not None:
            result["detection_kind"] = self.detection_kind
        if self.score is not None:
            result["score"] = self.score
        if self.image_box is not None:
            result["image_box"] = _box_to_dict(self.image_box)
        if self.original is not None:
            result["original"] = dict(self.original)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CorrectionObject":
        image_box = data.get("image_box")
        return cls(
            object_id=str(data["id"]),
            x=int(data["x"]),
            y=int(data["y"]),
            type_id=int(data["type_id"]),
            enabled=bool(data.get("enabled", True)),
            source=str(data.get("source", "scanner")),
            detection_kind=data.get("detection_kind"),
            score=float(data["score"]) if data.get("score") is not None else None,
            image_box=_box_from_dict(image_box) if image_box is not None else None,
            original=dict(data["original"]) if data.get("original") is not None else None,
        )


@dataclass(slots=True)
class CorrectionProject:
    """Versioned, UI-neutral representation of an editable scan."""

    source_image: str | None = None
    image_width: int = 800
    image_height: int = 608
    room_box: Box = field(default_factory=lambda: Box(0, 0, 800, 608))
    grid_step: int = 8
    include_color_objects: bool = True
    include_geometry: bool = True
    start_policy: str = "auto"
    start_save_id: str | None = None
    start_position: tuple[int, int] | None = None
    jmap_version: str = "1.3.5"
    infinite_jump: int = 0
    dot_kid: int = 0
    save_type: int = 1
    border_type: int = 0
    player_xscale: float = 1.0
    player_gravity: int = 1
    objects: list[CorrectionObject] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_scan(
        cls,
        result: Any,
        source_image: str | Path | None = None,
        *,
        grid_step: int = 8,
        include_color_objects: bool = True,
        include_geometry: bool = True,
        start_policy: str = "auto",
    ) -> "CorrectionProject":
        detections = sorted(
            result.detections,
            key=lambda item: (
                item.y,
                item.x,
                item.type_id,
                item.kind,
                -item.score,
                item.image_box.x,
                item.image_box.y,
            ),
        )
        objects = [
            CorrectionObject(
                object_id=f"obj-{index:04d}",
                x=detection.x,
                y=detection.y,
                type_id=detection.type_id,
                source="scanner",
                detection_kind=detection.kind,
                score=round(float(detection.score), 6),
                image_box=detection.image_box,
                original={
                    "x": detection.x,
                    "y": detection.y,
                    "type_id": detection.type_id,
                },
            )
            for index, detection in enumerate(detections, start=1)
        ]
        return cls(
            source_image=str(source_image) if source_image is not None else None,
            image_width=result.image_width,
            image_height=result.image_height,
            room_box=result.room_box,
            grid_step=grid_step,
            include_color_objects=include_color_objects,
            include_geometry=include_geometry,
            start_policy=start_policy,
            objects=objects,
            history=[{"operation": "create_from_scan", "detections": len(objects)}],
        )

    @classmethod
    def from_jmap(cls, jmap: JMap, source_jmap: str | Path | None = None) -> "CorrectionProject":
        editable = [obj for obj in jmap.objects if obj.type_id != OBJ_PLAYER_START]
        objects = [
            CorrectionObject(
                object_id=f"obj-{index:04d}",
                x=obj.x,
                y=obj.y,
                type_id=obj.type_id,
                source="jmap",
                original={"x": obj.x, "y": obj.y, "type_id": obj.type_id},
            )
            for index, obj in enumerate(editable, start=1)
        ]
        starts = jmap.objects_of_type(OBJ_PLAYER_START)
        start_position = (starts[0].x, starts[0].y) if starts else None
        start_save_id = None
        if start_position is not None:
            for obj in objects:
                if obj.type_id in (OBJ_SAVE, OBJ_SAVE_FLIP) and (obj.x, obj.y) == start_position:
                    start_save_id = obj.object_id
                    start_position = None
                    break
        return cls(
            source_image=None,
            start_policy="none",
            start_save_id=start_save_id,
            start_position=start_position,
            jmap_version=jmap.version,
            infinite_jump=jmap.infinite_jump,
            dot_kid=jmap.dot_kid,
            save_type=jmap.save_type,
            border_type=jmap.border_type,
            player_xscale=jmap.player_xscale,
            player_gravity=jmap.player_gravity,
            objects=objects,
            history=[
                {
                    "operation": "import_jmap",
                    "source": str(source_jmap) if source_jmap is not None else None,
                    "objects": len(objects),
                }
            ],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "CorrectionProject":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CorrectionProject":
        if data.get("format") != PROJECT_FORMAT:
            raise ValueError("not a JTool Scanner correction project")
        if int(data.get("version", 0)) != PROJECT_VERSION:
            raise ValueError(f"unsupported correction project version {data.get('version')}")
        source = data.get("source", {})
        scanner = data.get("scanner", {})
        start = data.get("start", {})
        settings = data.get("jmap", {})
        position = start.get("position")
        project = cls(
            source_image=source.get("image"),
            image_width=int(source.get("image_width", 800)),
            image_height=int(source.get("image_height", 608)),
            room_box=_box_from_dict(source.get("room_box", {"x": 0, "y": 0, "width": 800, "height": 608})),
            grid_step=int(scanner.get("grid_step", 8)),
            include_color_objects=bool(scanner.get("include_color_objects", True)),
            include_geometry=bool(scanner.get("include_geometry", True)),
            start_policy=str(start.get("policy", "auto")),
            start_save_id=start.get("save_id"),
            start_position=(int(position[0]), int(position[1])) if position is not None else None,
            jmap_version=str(settings.get("version", "1.3.5")),
            infinite_jump=int(settings.get("infinite_jump", 0)),
            dot_kid=int(settings.get("dot_kid", 0)),
            save_type=int(settings.get("save_type", 1)),
            border_type=int(settings.get("border_type", 0)),
            player_xscale=float(settings.get("player_xscale", 1.0)),
            player_gravity=int(settings.get("player_gravity", 1)),
            objects=[CorrectionObject.from_dict(item) for item in data.get("objects", [])],
            history=list(data.get("history", [])),
        )
        project.validate()
        return project

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": PROJECT_FORMAT,
            "version": PROJECT_VERSION,
            "source": {
                "image": self.source_image,
                "image_width": self.image_width,
                "image_height": self.image_height,
                "room_box": _box_to_dict(self.room_box),
            },
            "scanner": {
                "grid_step": self.grid_step,
                "include_color_objects": self.include_color_objects,
                "include_geometry": self.include_geometry,
            },
            "start": {
                "policy": self.start_policy,
                "save_id": self.start_save_id,
                "position": list(self.start_position) if self.start_position is not None else None,
            },
            "jmap": {
                "version": self.jmap_version,
                "infinite_jump": self.infinite_jump,
                "dot_kid": self.dot_kid,
                "save_type": self.save_type,
                "border_type": self.border_type,
                "player_xscale": self.player_xscale,
                "player_gravity": self.player_gravity,
            },
            "objects": [obj.to_dict() for obj in self.objects],
            "history": list(self.history),
        }

    def to_file(self, path: str | Path) -> None:
        self.validate()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    def to_jmap(self) -> JMap:
        self.validate()
        jmap = JMap(
            version=self.jmap_version,
            infinite_jump=self.infinite_jump,
            dot_kid=self.dot_kid,
            save_type=self.save_type,
            border_type=self.border_type,
            player_xscale=self.player_xscale,
            player_gravity=self.player_gravity,
            objects=[
                JMapObject(obj.x, obj.y, obj.type_id)
                for obj in self.objects
                if obj.enabled and obj.type_id != OBJ_PLAYER_START
            ],
        )
        if self.start_save_id is not None:
            selected = self.get_object(self.start_save_id)
            if not selected.enabled or selected.type_id not in (OBJ_SAVE, OBJ_SAVE_FLIP):
                raise ValueError("selected start object must be an enabled save")
            jmap.replace_player_start(selected.x, selected.y)
        elif self.start_position is not None:
            jmap.replace_player_start(*self.start_position)
        else:
            move_start_to_save(jmap, self.start_policy)
        return jmap

    def validate(self) -> None:
        ids = [obj.object_id for obj in self.objects]
        if len(ids) != len(set(ids)):
            raise ValueError("correction project contains duplicate object IDs")
        for obj in self.objects:
            if obj.type_id not in OFFICIAL_SAVE_IDS:
                raise ValueError(f"unsupported JTool object type {obj.type_id} on {obj.object_id}")
        if self.start_save_id is not None and self.start_save_id not in set(ids):
            raise ValueError(f"unknown start save ID {self.start_save_id!r}")
        if self.start_save_id is not None:
            selected = self.get_object(self.start_save_id)
            if not selected.enabled or selected.type_id not in (OBJ_SAVE, OBJ_SAVE_FLIP):
                raise ValueError("selected start object must be an enabled save")

    def get_object(self, object_id: str) -> CorrectionObject:
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        raise ValueError(f"unknown correction object {object_id!r}")

    def add_object(self, x: int, y: int, type_id: int) -> CorrectionObject:
        _require_official_type(type_id)
        obj = CorrectionObject(
            object_id=self._next_object_id(),
            x=int(x),
            y=int(y),
            type_id=type_id,
            source="manual",
        )
        self.objects.append(obj)
        self.history.append({"operation": "add", "id": obj.object_id, "x": obj.x, "y": obj.y, "type_id": type_id})
        return obj

    def set_enabled(self, object_id: str, enabled: bool) -> None:
        obj = self.get_object(object_id)
        obj.enabled = enabled
        self.history.append({"operation": "enable" if enabled else "disable", "id": object_id})

    def move_object(self, object_id: str, x: int, y: int) -> None:
        obj = self.get_object(object_id)
        before = [obj.x, obj.y]
        obj.x = int(x)
        obj.y = int(y)
        self.history.append({"operation": "move", "id": object_id, "from": before, "to": [obj.x, obj.y]})

    def set_object_type(self, object_id: str, type_id: int) -> None:
        _require_official_type(type_id)
        obj = self.get_object(object_id)
        before = obj.type_id
        obj.type_id = type_id
        self.history.append({"operation": "set_type", "id": object_id, "from": before, "to": type_id})

    def replace_type(self, old_type_id: int, new_type_id: int) -> int:
        _require_official_type(old_type_id)
        _require_official_type(new_type_id)
        changed = 0
        for obj in self.objects:
            if obj.enabled and obj.type_id == old_type_id:
                obj.type_id = new_type_id
                changed += 1
        self.history.append({"operation": "replace_type", "from": old_type_id, "to": new_type_id, "count": changed})
        return changed

    def choose_start_save(self, object_id: str | None) -> None:
        if object_id is not None:
            obj = self.get_object(object_id)
            if not obj.enabled or obj.type_id not in (OBJ_SAVE, OBJ_SAVE_FLIP):
                raise ValueError("start save must be an enabled save object")
        self.start_save_id = object_id
        self.start_position = None
        self.history.append({"operation": "set_start_save", "id": object_id})

    def choose_start_position(self, x: int, y: int) -> None:
        self.start_save_id = None
        self.start_position = (int(x), int(y))
        self.history.append({"operation": "set_start_position", "position": [int(x), int(y)]})

    def choose_start_policy(self, policy: str) -> None:
        self.start_save_id = None
        self.start_position = None
        self.start_policy = policy
        self.history.append({"operation": "set_start_policy", "policy": policy})

    def object_counts(self, enabled: bool | None = True) -> Counter[int]:
        return Counter(
            obj.type_id
            for obj in self.objects
            if enabled is None or obj.enabled == enabled
        )

    def _next_object_id(self) -> str:
        highest = 0
        for obj in self.objects:
            match = re.fullmatch(r"obj-(\d+)", obj.object_id)
            if match:
                highest = max(highest, int(match.group(1)))
        return f"obj-{highest + 1:04d}"


def parse_object_type(value: str | int) -> int:
    """Accept either an official numeric ID or a readable object name."""

    if isinstance(value, int) or str(value).strip().lstrip("-").isdigit():
        type_id = int(value)
    else:
        name = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        name = _TYPE_ALIASES.get(name, name)
        if name not in _TYPE_IDS_BY_NAME:
            raise ValueError(f"unknown JTool object type {value!r}")
        type_id = _TYPE_IDS_BY_NAME[name]
    _require_official_type(type_id)
    return type_id


def render_correction_svg(
    project: CorrectionProject,
    title: str = "JTool correction preview",
    *,
    show_ids: bool = False,
    show_disabled: bool = False,
) -> str:
    """Render the exact export plus optional correction IDs and disabled candidates."""

    svg = render_svg(project.to_jmap(), title).rstrip()
    overlays: list[str] = []
    if show_disabled:
        for obj in project.objects:
            if obj.enabled:
                continue
            width, height = _object_size(obj.type_id)
            overlays.append(
                f'<rect x="{obj.x}" y="{obj.y}" width="{width}" height="{height}" '
                'fill="none" stroke="#d03030" stroke-width="2" stroke-dasharray="4 3" opacity="0.9"/>'
            )
    if show_ids:
        for obj in project.objects:
            if not obj.enabled and not show_disabled:
                continue
            color = "#8b1d1d" if not obj.enabled else "#111"
            label = escape(obj.object_id.removeprefix("obj-"))
            overlays.append(
                f'<text x="{obj.x + 2}" y="{obj.y + 10}" font-family="monospace" '
                f'font-size="8" fill="{color}" stroke="#fff" stroke-width="2" '
                f'paint-order="stroke">{label}</text>'
            )
    if overlays:
        svg = svg.removesuffix("</svg>") + "\n<g id=\"correction-overlay\">\n" + "\n".join(overlays) + "\n</g>\n</svg>"
    return svg + "\n"


def _require_official_type(type_id: int) -> None:
    if type_id not in OFFICIAL_SAVE_IDS:
        raise ValueError(f"unsupported JTool object type {type_id}")


def _object_size(type_id: int) -> tuple[int, int]:
    if type_id in {
        OBJ_MINI_BLOCK,
        OBJ_MINI_SPIKE_UP,
        OBJ_MINI_SPIKE_RIGHT,
        OBJ_MINI_SPIKE_LEFT,
        OBJ_MINI_SPIKE_DOWN,
    }:
        return (16, 16)
    return (32, 32)


def _box_to_dict(box: Box) -> dict[str, int]:
    return {"x": box.x, "y": box.y, "width": box.width, "height": box.height}


def _box_from_dict(data: dict[str, Any]) -> Box:
    return Box(int(data["x"]), int(data["y"]), int(data["width"]), int(data["height"]))
