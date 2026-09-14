"""Versioned JSON saves with validation before replace and same-directory writes."""
import json
import os
from pathlib import Path
import tempfile

from .core import GameError, from_dict, validate

MAX_SAVE_BYTES = 4 * 1024 * 1024


def default_save_directory():
    project = Path(__file__).resolve().parents[2]
    # Portable checkout keeps all data inside itself; installed packages use cwd.
    if (project / "run.py").is_file() and (project / "pyproject.toml").is_file():
        return project / "saves"
    return Path.cwd() / "saves"


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_game(state, path):
    validate(state)
    content = (json.dumps(state.to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    if len(content) > MAX_SAVE_BYTES:
        raise GameError("Save exceeds size limit.")
    atomic_write(path, content)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GameError(f"Duplicate save field: {key}.")
        result[key] = value
    return result


def load_game(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_SAVE_BYTES + 1)
    if len(raw) > MAX_SAVE_BYTES:
        raise GameError("Save exceeds size limit.")
    try:
        return from_dict(json.loads(raw, object_pairs_hook=_unique_object))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise GameError(f"Cannot load save: {exc}") from exc
