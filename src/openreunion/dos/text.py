"""DOS cipher (2EC34..2EC8D) and the three recovered plain Pascal tables."""
import hashlib
from pathlib import Path

from ..core import GameError
from .descriptions import FORMATS,decode_descriptions

RAW_NAMES=tuple(FORMATS)+('SZ_FAJ.RAW',)


def decode_line(data):
    if not isinstance(data, bytes) or len(data) > 255:
        raise GameError("Encrypted DOS lines must be bytes of length 0..255.")
    return bytes(((value+22400-79*i) % 224-32) & 255
                 for i, value in enumerate(data, 1))


def decode_text(data):
    if len(data) > 1024*1024:
        raise GameError("Text exceeds the 1 MiB limit.")
    # Preserve blank records, trailing newline, control bytes and vertical bars.
    # splitlines() is incorrect here: cipher bytes can be interpreted as controls.
    lines = data.split(b"\r\n")
    if any(b"\r" in line or b"\n" in line for line in lines):
        raise GameError("Expected DOS CRLF text records.")
    return [decode_line(line).decode("cp437") for line in lines]


def read_text(path):
    with Path(path).open("rb") as stream:
        data=stream.read(1024*1024+1)
    return decode_file(Path(path).name.upper(),data)


def decode_file(name,data):
    if name=='SZ_FAJ.RAW':
        from .race_info import decode_profiles
        return decode_profiles(data)
    if name in FORMATS:return decode_descriptions(name,data)
    return decode_text(data)


def audit_text(root):
    root = Path(root).resolve()
    report = {"decoded": [], "unsupported": [], "malformed": []}
    for path in sorted((root / "TEXT").iterdir()):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            continue
        data = path.read_bytes()
        record = {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(data).hexdigest()}
        if path.name.upper() not in RAW_NAMES and path.suffix.upper() not in (".TXT", ".SP", ".AT", ".LOC"):
            report["unsupported"].append(record)
            continue
        try:
            lines=decode_file(path.name.upper(),data)
            record.update(line_count=len(lines), lines=lines)
            report["decoded"].append(record)
        except GameError as exc:
            record["error"] = str(exc)
            report["malformed"].append(record)
    return report
