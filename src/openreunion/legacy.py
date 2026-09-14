"""Bounded, read-only DOS adapters. Exported saves are always new files."""
from collections import Counter
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import string
import struct

from .core import GameError, integer

SAVE_SIZE = 41670
# Name order and serialization traced in the executable; see docs/RESEARCH.md.
RESOURCE_OFFSETS = {"credits": 0x388C, "detoxin": 0x3890, "energon": 0x3894,
                    "kremir": 0x3898, "lepitium": 0x389C,
                    "raenium": 0x38A0, "texon": 0x38A4}
BUILDING_COST_OFFSETS = {
    "command_centre": 0x458A9, "windtrap": 0x45927, "mine": 0x45966,
    "derrick": 0x459A5, "observatory": 0x459E4, "housing": 0x45A23,
    "leisure_centre": 0x45A62, "stadium": 0x45AA1, "church": 0x45AE0,
    "storage_bay": 0x45B1F, "space_port": 0x45B5E, "university": 0x45B9D,
    "park": 0x45BDC, "hospital": 0x45C1B, "farm": 0x45C5A,
}


@dataclass(frozen=True)
class LegacySave:
    data: bytes

    def __post_init__(self):
        if not isinstance(self.data, bytes) or len(self.data) != SAVE_SIZE:
            raise GameError(f"Expected a {SAVE_SIZE:,}-byte DOS save.")
        label = self.data[1:1 + self.data[0]]
        if not label or any(b < 32 or b > 126 for b in label):
            raise GameError("Unsupported or corrupt English DOS save label.")

    @classmethod
    def read(cls, path):
        with Path(path).open("rb") as stream:
            return cls(stream.read(SAVE_SIZE + 1))

    @property
    def name(self):
        return self.data[1:1 + self.data[0]].decode("ascii")

    def resources(self):
        return {key: struct.unpack_from("<I", self.data, offset)[0] for key, offset in RESOURCE_OFFSETS.items()}

    def describe(self):
        return {"name": self.name, "bytes": len(self.data), "sha256": hashlib.sha256(self.data).hexdigest(),
                "resources": self.resources(),
                "notice": "Resource order traced in DOS serialization and ore-name lookup. Partial save interpretation; no full campaign import."}

    def with_resources(self, changes):
        if not changes or not set(changes) <= set(RESOURCE_OFFSETS):
            raise GameError("Editable DOS fields: " + ", ".join(RESOURCE_OFFSETS))
        result = bytearray(self.data)
        for key, value in changes.items():
            integer(value, key, maximum=2**32 - 1)
            struct.pack_into("<I", result, RESOURCE_OFFSETS[key], value)
        return bytes(result)


def export_legacy(source, destination, changes):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise GameError("Choose a new output file; the source save is never overwritten.")
    data = LegacySave.read(source).with_resources(changes)
    # Exclusive creation also rejects existing files and hard links to the source.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class TerrainMap:
    width: int
    height: int
    tiles: bytes

    @classmethod
    def decode(cls, data):
        if len(data) < 2:
            raise GameError("Map header is truncated.")
        width, height = data[:2]
        if not width or not height or len(data) != 2 + width * height:
            raise GameError("Map size does not match its width and height.")
        return cls(width, height, bytes(data[2:]))

    @classmethod
    def read(cls, path):
        with Path(path).open("rb") as stream:
            return cls.decode(stream.read(2 + 255 * 255 + 1))

    def tile(self, x, y):
        integer(x, "X", maximum=self.width-1)
        integer(y, "Y", maximum=self.height-1)
        return self.tiles[y * self.width + x]


def production_candidates(data):
    """Adapted scanner heuristic from reunion_cheat.py; semantics remain unverified."""
    allowed = set((string.ascii_letters + string.digits + " .-").encode("ascii"))
    rows = []
    for offset in range(0x450C0, min(len(data), 0x457E0) - 34):
        size = data[offset]
        if not 5 <= size <= 16:
            continue
        name = data[offset+1:offset+1+size]
        if not set(name) <= allowed:
            continue
        if any(b not in (0, 32) for b in data[offset+1+size:offset+16]):
            continue
        base = struct.unpack_from("<I", data, offset + 0x1F)[0]
        if 0 < base <= 50000:
            rows.append({"name": name.decode("ascii"), "record_offset": f"0x{offset:06X}",
                         "candidate_work_u32": base, "status": "observed bytes; formula unverified"})
    return rows


def audit_installation(root):
    root = Path(root).resolve()
    if not (root / "GRWAR/REUNION.PRG").is_file():
        raise GameError("Not a recognized installation: missing GRWAR/REUNION.PRG.")
    records, map_info, errors = [], [], []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part.lower() in ("opensource", "reunion-private", "__pycache__") for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            continue
        data = path.read_bytes()
        records.append({"path": relative.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        if path.suffix.lower() == ".map":
            try:
                terrain = TerrainMap.decode(data)
                map_info.append({"path": relative.as_posix(), "width": terrain.width,
                                 "height": terrain.height, "distinct_tiles": len(set(terrain.tiles))})
            except GameError as exc:
                errors.append({"path": relative.as_posix(), "error": str(exc)})
    binary = (root / "GRWAR/REUNION.PRG").read_bytes()
    building_costs = {key: {"offset": hex(offset), "observed_u32": struct.unpack_from("<I", binary, offset)[0]}
                      for key, offset in BUILDING_COST_OFFSETS.items() if len(binary) >= offset + 4}
    return {"report_schema": 1, "source": "User-supplied DOS installation; no binaries embedded",
            "files": records, "file_count": len(records), "total_bytes": sum(r["bytes"] for r in records),
            "extensions": dict(sorted(Counter(Path(r["path"]).suffix.lower() for r in records).items())),
            "maps": map_info, "production_candidates": production_candidates(binary),
            "building_cost_candidates": building_costs, "errors": errors}
