"""Bounded SpidyGfx decoder. Original assets are optional local inputs."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
import zlib

from ..core import GameError


# The original INFO caller uses 192-byte source rows. This exact shipped file
# declares 191, but every encoded row contains 192 pixels. See PIC-RESEARCH.md.
INFO26_SHA256 = "fc432c0df924a9e1810bcff66baf0fe54d36607ecaf5598345289663a3989bdc"


def picture_correction(data):
    if hashlib.sha256(data).hexdigest() == INFO26_SHA256:
        return {"kind": "incorrect_width_header", "declared_width": 191,
                "corrected_width": 192, "height": 127}
    return None


@dataclass(frozen=True)
class Picture:
    width: int
    height: int
    pixels: bytes
    palette: bytes

    def rgb(self):
        return b"".join(self.palette[i*3:i*3+3] for i in self.pixels)

    def ppm(self):
        return f"P6\n{self.width} {self.height}\n255\n".encode("ascii") + self.rgb()

    def png(self):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data))
        scanlines = b"".join(b"\0" + self.pixels[y*self.width:(y+1)*self.width] for y in range(self.height))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 3, 0, 0, 0))
                + chunk(b"PLTE", self.palette) + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


def decode_picture(data):
    if len(data) < 12+769 or data[:8] != b"SpidyGfx":
        raise GameError("Not a supported SpidyGfx picture.")
    width, height = struct.unpack_from("<HH", data, 8)
    correction = picture_correction(data)
    if correction:
        width = correction["corrected_width"]
    if not 1 <= width <= 2048 or not 1 <= height <= 2048 or width*height > 1048576:
        raise GameError("Picture dimensions exceed supported limits.")
    end = len(data)-769
    if data[end] != 12:
        raise GameError("Missing SpidyGfx palette marker.")
    pixels = bytearray()
    position = 12
    while position < end:
        token = data[position]
        position += 1
        count, value = 1, token
        if token >= 192:
            count = token-192
            if not count or position >= end:
                raise GameError("Invalid or truncated SpidyGfx run.")
            value = data[position]
            position += 1
        if len(pixels)+count > width*height:
            raise GameError(f"SpidyGfx payload exceeds {width}x{height}. Header/row-stride mismatch; asset quarantined.")
        pixels.extend(bytes([value])*count)
    if len(pixels) != width*height:
        raise GameError("Truncated SpidyGfx pixel payload.")
    return Picture(width, height, bytes(pixels), bytes(data[end+1:]))


def read_picture(path):
    with Path(path).open("rb") as stream:
        data = stream.read(3*1024*1024+1)
    if len(data) > 3*1024*1024:
        raise GameError("Picture file exceeds size limit.")
    return decode_picture(data)


def decode_converted_png(data):
    """Read this project's bounded indexed PNG export, retaining palette IDs.

    This intentionally accepts the format written by Picture.png: indexed
    eight-bit pixels, filter zero, no interlacing, one palette and IDAT stream.
    Keeping palette indices distinguishes the transparent sprite index from
    other entries with the same RGB value.
    """
    if not isinstance(data, bytes) or len(data)>3*1024*1024 or data[:8]!=b"\x89PNG\r\n\x1a\n":
        raise GameError("Invalid converted indexed PNG.")
    chunks = [];at = 8
    while at<len(data):
        if at+12>len(data):raise GameError("Truncated converted PNG chunk.")
        size = struct.unpack_from(">I", data, at)[0];kind = data[at+4:at+8]
        if at+size+12>len(data):raise GameError("Truncated converted PNG payload.")
        payload = data[at+8:at+8+size]
        if zlib.crc32(kind+payload)!=struct.unpack_from(">I", data, at+8+size)[0]:
            raise GameError("Converted PNG checksum mismatch.")
        chunks.append((kind, payload));at += size+12
        if len(chunks)>4:raise GameError("Unsupported converted PNG chunk sequence.")
    if [kind for kind, _ in chunks]!=[b"IHDR", b"PLTE", b"IDAT", b"IEND"]:
        raise GameError("Unsupported converted PNG chunk sequence.")
    header, palette, compressed, end = [payload for _, payload in chunks]
    if len(header)!=13 or header[8:]!=bytes([8, 3, 0, 0, 0]) or len(palette)!=768 or end:
        raise GameError("Unsupported converted PNG encoding.")
    width, height = struct.unpack_from(">II", header)
    if not 1<=width<=2048 or not 1<=height<=2048 or width*height>1048576:
        raise GameError("Converted PNG dimensions exceed limits.")
    expected = (width+1)*height
    try:
        inflater = zlib.decompressobj();scanlines = inflater.decompress(compressed, expected+1)
    except zlib.error as exc:raise GameError("Invalid converted PNG compression.") from exc
    if len(scanlines)!=expected or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise GameError("Converted PNG pixel count mismatch.")
    if any(scanlines[y*(width+1)] for y in range(height)):
        raise GameError("Unsupported converted PNG row filter.")
    pixels = b"".join(scanlines[y*(width+1)+1:(y+1)*(width+1)] for y in range(height))
    return Picture(width, height, pixels, palette)


def audit_pictures(root, output=None):
    root = Path(root).resolve()
    output = Path(output).resolve() if output else None
    if output and output.is_relative_to(root) and "opensource" not in output.relative_to(root).parts:
        raise GameError("Decoded assets must not be written into the source installation.")
    report = {"decoded": [], "unsupported": [], "malformed": []}
    # Visit only original top-level asset directories, never generated tool trees.
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.name.startswith(".") or directory.name in ("opensource", "__pycache__") or directory.is_symlink():
            continue
        for path in sorted(directory.glob("*.PIC")):
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                continue
            data = path.read_bytes()
            relative = path.relative_to(root).as_posix()
            record = {"path": relative, "sha256": hashlib.sha256(data).hexdigest()}
            if not data.startswith(b"SpidyGfx"):
                report["unsupported"].append(record)
                continue
            try:
                picture = decode_picture(data)
                record.update(width=picture.width, height=picture.height,
                              pixels_sha256=hashlib.sha256(picture.pixels).hexdigest())
                correction = picture_correction(data)
                if correction:
                    record["correction"] = correction
                report["decoded"].append(record)
                if output:
                    target = output / Path(relative).with_suffix(".png")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(picture.png())
            except GameError as exc:
                record["error"] = str(exc)
                report["malformed"].append(record)
    return report
