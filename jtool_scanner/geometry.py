"""Small geometry primitives used by image scanning and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.right and self.y <= y < self.bottom

    def inset(self, amount: int) -> "Box":
        return Box(
            self.x + amount,
            self.y + amount,
            max(0, self.width - amount * 2),
            max(0, self.height - amount * 2),
        )

    @classmethod
    def from_text(cls, value: str) -> "Box":
        parts = [int(part.strip()) for part in value.split(",")]
        if len(parts) != 4:
            raise ValueError("box must look like x,y,width,height")
        return cls(*parts)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def round_to_step(value: float, step: int) -> int:
    return int(round(value / step) * step)

