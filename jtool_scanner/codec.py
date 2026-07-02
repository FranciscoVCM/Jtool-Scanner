"""Encoding helpers matching JTool's compact save format."""

from __future__ import annotations

import struct

BASE32_ALPHABET = "0123456789abcdefghijklmnopqrstuv"


def int_to_base32(number: int) -> str:
    if number < 0:
        raise ValueError("JTool base32 only supports non-negative integers")
    if number == 0:
        return ""

    chars: list[str] = []
    while number > 0:
        number, rem = divmod(number, 32)
        chars.append(BASE32_ALPHABET[rem])
    return "".join(reversed(chars))


def base32_to_int(value: str) -> int:
    number = 0
    for char in value:
        try:
            digit = BASE32_ALPHABET.index(char)
        except ValueError as exc:
            raise ValueError(f"invalid JTool base32 character {char!r}") from exc
        number = number * 32 + digit
    return number


def pad_left(value: str, width: int, fill: str = "0") -> str:
    if len(fill) != 1:
        raise ValueError("fill must be one character")
    return value.rjust(width, fill)


def float_to_base32(value: float) -> str:
    bits = int.from_bytes(struct.pack(">d", float(value)), "big")
    return pad_left(int_to_base32(bits), 13, "0")


def base32_to_float(value: str) -> float:
    bits = base32_to_int(value)
    raw = bits.to_bytes(8, "big")
    return struct.unpack(">d", raw)[0]

