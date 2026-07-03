"""Dependency-free PNG loading and simple RGB image helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib

from .geometry import Box

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(slots=True)
class RGBImage:
    width: int
    height: int
    data: bytes

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            raise IndexError((x, y))
        offset = (y * self.width + x) * 3
        return self.data[offset], self.data[offset + 1], self.data[offset + 2]

    def row(self, y: int) -> memoryview:
        start = y * self.width * 3
        return memoryview(self.data)[start : start + self.width * 3]

    def crop(self, box: Box) -> "RGBImage":
        left = max(0, box.x)
        top = max(0, box.y)
        right = min(self.width, box.right)
        bottom = min(self.height, box.bottom)
        rows = []
        for y in range(top, bottom):
            start = (y * self.width + left) * 3
            end = (y * self.width + right) * 3
            rows.append(self.data[start:end])
        return RGBImage(right - left, bottom - top, b"".join(rows))


def load_png(path: str | Path) -> RGBImage:
    raw = Path(path).read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")

    pos = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    palette: list[tuple[int, int, int]] | None = None
    transparent: bytes | None = None
    compressed = bytearray()

    while pos < len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        chunk_type = raw[pos + 4 : pos + 8]
        chunk = raw[pos + 8 : pos + 8 + length]
        pos += 12 + length

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif chunk_type == b"PLTE":
            palette = [
                (chunk[i], chunk[i + 1], chunk[i + 2])
                for i in range(0, len(chunk), 3)
            ]
        elif chunk_type == b"tRNS":
            transparent = chunk
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or bit_depth is None or color_type is None:
        raise ValueError("PNG is missing IHDR")
    if bit_depth != 8:
        raise ValueError(f"unsupported PNG bit depth {bit_depth}")
    if interlace != 0:
        raise ValueError("interlaced PNGs are not supported yet")

    channels = _channels_for_color_type(color_type)
    decompressed = zlib.decompress(bytes(compressed))
    scanline_len = width * channels
    source = memoryview(decompressed)
    rows: list[bytearray] = []
    cursor = 0
    previous = bytearray(scanline_len)

    for _ in range(height):
        filter_type = source[cursor]
        cursor += 1
        row = bytearray(source[cursor : cursor + scanline_len])
        cursor += scanline_len
        _unfilter(row, previous, filter_type, channels)
        rows.append(row)
        previous = row

    return _rows_to_rgb(rows, width, height, color_type, palette, transparent)


def _channels_for_color_type(color_type: int) -> int:
    if color_type == 0:
        return 1
    if color_type == 2:
        return 3
    if color_type == 3:
        return 1
    if color_type == 4:
        return 2
    if color_type == 6:
        return 4
    raise ValueError(f"unsupported PNG color type {color_type}")


def _unfilter(row: bytearray, previous: bytearray, filter_type: int, bpp: int) -> None:
    if filter_type == 0:
        return
    if filter_type == 1:
        for i in range(len(row)):
            left = row[i - bpp] if i >= bpp else 0
            row[i] = (row[i] + left) & 0xFF
        return
    if filter_type == 2:
        for i in range(len(row)):
            row[i] = (row[i] + previous[i]) & 0xFF
        return
    if filter_type == 3:
        for i in range(len(row)):
            left = row[i - bpp] if i >= bpp else 0
            up = previous[i]
            row[i] = (row[i] + ((left + up) // 2)) & 0xFF
        return
    if filter_type == 4:
        for i in range(len(row)):
            left = row[i - bpp] if i >= bpp else 0
            up = previous[i]
            up_left = previous[i - bpp] if i >= bpp else 0
            row[i] = (row[i] + _paeth(left, up, up_left)) & 0xFF
        return
    raise ValueError(f"unsupported PNG filter type {filter_type}")


def _paeth(left: int, up: int, up_left: int) -> int:
    p = left + up - up_left
    pa = abs(p - left)
    pb = abs(p - up)
    pc = abs(p - up_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return up_left


def _rows_to_rgb(
    rows: list[bytearray],
    width: int,
    height: int,
    color_type: int,
    palette: list[tuple[int, int, int]] | None,
    transparent: bytes | None,
) -> RGBImage:
    out = bytearray(width * height * 3)
    pos = 0
    if color_type == 2:
        return RGBImage(width, height, b"".join(rows))
    for row in rows:
        if color_type == 0:
            for gray in row:
                out[pos : pos + 3] = bytes((gray, gray, gray))
                pos += 3
        elif color_type == 3:
            if palette is None:
                raise ValueError("palette PNG is missing PLTE")
            for index in row:
                out[pos : pos + 3] = bytes(palette[index])
                pos += 3
        elif color_type == 4:
            for i in range(0, len(row), 2):
                gray = row[i]
                out[pos : pos + 3] = bytes((gray, gray, gray))
                pos += 3
        elif color_type == 6:
            for i in range(0, len(row), 4):
                out[pos : pos + 3] = row[i : i + 3]
                pos += 3
        else:
            raise ValueError(f"unsupported PNG color type {color_type}")
    return RGBImage(width, height, bytes(out))

