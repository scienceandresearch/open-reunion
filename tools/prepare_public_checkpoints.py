#!/usr/bin/env python3
"""Prepare the public campaign checkpoint collection from its archived source."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_NAME = "MANIFEST.json"
GUIDE_NAME = "START-HERE.md"
SAVE_NAME = re.compile(r"\d{2} - .+\.json\Z")
SAVE_COUNT = 23
SESSION_PRESENTATION_FIELDS = ("audio", "effects", "result_animation", "hero")
SAVE_MODIFICATION = (
    "Only each checkpoint's top-level event log was cleared for public "
    "distribution; all other saved gameplay fields and the unassisted status "
    "are unchanged."
)
GUIDE_INSERT_AFTER = (
    "Choose a point in the campaign without replacing your own saves. These are "
    "optional; New Game still starts normally.\n"
)
GUIDE_INSERT = (
    "\nThe source repository keeps this public collection in `tester-saves`. "
    "Release packaging copies it to **Optional Saves**; importing your game "
    "assets does not restore the removed checkpoint logs.\n"
    "\nFor public distribution, each checkpoint's top-level event log was "
    "cleared. Gameplay state, earned resources, decisions, casualties, timers "
    "and unassisted status are unchanged.\n"
)
GUIDE_NEW_PROVENANCE = (
    "Each public checkpoint was derived from the verified archived checkpoint "
    "by clearing only its top-level event log. Gameplay state fields—including "
    "resources, battle results, campaign flags and unassisted status—are "
    "unchanged. `MANIFEST.json` records current hashes plus the original file "
    "and state hashes."
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def state_hash(state: Any) -> str:
    """Match tools/verify_campaign_journey.py's saved-state hash."""

    packed = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    return sha256(packed)


def gameplay_state(saved_payload: dict[str, Any]) -> dict[str, Any]:
    """Return the state object that RecoveredSession.load exposes for schema 23."""

    state = dict(saved_payload)
    for field in SESSION_PRESENTATION_FIELDS:
        state.pop(field, None)
    return state


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_relative_path(value: Any) -> PurePosixPath:
    require(isinstance(value, str) and value != "", "empty or non-string path")
    require("\\" not in value, f"path must use forward slashes: {value!r}")
    relative = PurePosixPath(value)
    require(not relative.is_absolute(), f"absolute path is not allowed: {value!r}")
    require(
        all(part not in ("", ".", "..") for part in relative.parts),
        f"unsafe relative path: {value!r}",
    )
    return relative


def child_path(root: Path, relative: PurePosixPath) -> Path:
    child = root.joinpath(*relative.parts)
    require(child.resolve().is_relative_to(root), f"path escapes collection: {relative}")
    require(not child.is_symlink(), f"symbolic links are not allowed: {relative}")
    return child


def file_snapshot(root: Path) -> dict[str, tuple[int, str]]:
    snapshot: dict[str, tuple[int, str]] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symbolic links are not allowed: {path.relative_to(root)}")
        if path.is_file():
            data = path.read_bytes()
            snapshot[path.relative_to(root).as_posix()] = (len(data), sha256(data))
    return snapshot


def transform_guide(data: bytes) -> bytes:
    text = data.decode("utf-8").replace("\r\n", "\n")
    require("\r" not in text, "guide contains an unexpected carriage return")
    require(text.count(GUIDE_INSERT_AFTER) == 1, "guide introduction is unexpected")
    text = text.replace(GUIDE_INSERT_AFTER, GUIDE_INSERT_AFTER + GUIDE_INSERT, 1)
    lines = text.splitlines()
    provenance_rows = [
        index
        for index, line in enumerate(lines)
        if line.endswith("MANIFEST.json records source paths and hashes.")
    ]
    require(len(provenance_rows) == 1, "guide provenance is unexpected")
    lines[provenance_rows[0]] = GUIDE_NEW_PROVENANCE
    text = "\n".join(lines)
    return (text.rstrip("\n") + "\n").encode("utf-8")


def prepare(source: Path, output: Path) -> dict[str, Any]:
    source = source.resolve()
    output = output.resolve()
    require(source.is_dir(), f"source collection does not exist: {source}")
    require(not output.exists(), f"output must be a fresh path: {output}")
    require(not output.is_relative_to(source), "output cannot be inside the source")
    require(not source.is_relative_to(output), "output cannot contain the source")

    before = file_snapshot(source)
    manifest_data = (source / MANIFEST_NAME).read_bytes()
    manifest = json.loads(manifest_data)
    require(isinstance(manifest, dict), "manifest must be a JSON object")
    require(manifest.get("unassisted") is True, "source pack must be unassisted")
    require(
        manifest.get("save_bytes_modified") is False,
        "source pack must be the unmodified archived collection",
    )

    file_rows = manifest.get("files")
    save_rows = manifest.get("saves")
    require(isinstance(file_rows, list), "manifest files must be a list")
    require(isinstance(save_rows, list), "manifest saves must be a list")
    require(len(save_rows) == SAVE_COUNT, f"expected {SAVE_COUNT} checkpoint rows")

    listed: dict[str, dict[str, Any]] = {}
    for row in file_rows:
        require(isinstance(row, dict), "manifest file row must be an object")
        relative = safe_relative_path(row.get("path"))
        name = relative.as_posix()
        require(name not in listed, f"duplicate manifest file row: {name}")
        listed[name] = row

    require(MANIFEST_NAME not in listed, "manifest cannot list itself")
    expected = set(listed) | {MANIFEST_NAME}
    actual = set(before)
    require(actual == expected, f"collection membership differs: {sorted(actual ^ expected)}")
    require(GUIDE_NAME in listed, f"manifest does not list {GUIDE_NAME}")

    for name, row in listed.items():
        size, digest = before[name]
        require(row.get("bytes") == size, f"byte count mismatch: {name}")
        require(row.get("sha256") == digest, f"SHA-256 mismatch: {name}")

    save_names: list[str] = []
    for row in save_rows:
        require(isinstance(row, dict), "manifest save row must be an object")
        name = row.get("file")
        require(isinstance(name, str) and SAVE_NAME.fullmatch(name), f"bad save name: {name!r}")
        require(name in listed, f"save is not listed as a file: {name}")
        require(name not in save_names, f"duplicate save row: {name}")
        require(row.get("sha256") == listed[name].get("sha256"), f"save SHA mismatch: {name}")
        require(row.get("bytes") == listed[name].get("bytes"), f"save byte mismatch: {name}")
        save_names.append(name)
    require(len(save_names) == SAVE_COUNT, f"expected {SAVE_COUNT} unique saves")
    require(
        {name for name in listed if name.endswith(".json")} == set(save_names),
        "manifest contains an unexpected JSON file or omits a checkpoint",
    )

    transformed: dict[str, bytes] = {}
    audit_saves: list[dict[str, Any]] = []
    save_rows_by_name = {row["file"]: row for row in save_rows}
    for name in save_names:
        row = save_rows_by_name[name]
        original_data = child_path(source, PurePosixPath(name)).read_bytes()
        original_state = json.loads(original_data)
        require(isinstance(original_state, dict), f"save must be an object: {name}")
        require("log" in original_state, f"save has no top-level log: {name}")
        require(isinstance(original_state["log"], list), f"save log must be a list: {name}")
        require(
            original_state.get("schema") == "recovered-strategy-v23",
            f"wrong schema version: {name}",
        )
        require(original_state.get("assisted") is False, f"save is assisted: {name}")
        original_state_digest = state_hash(gameplay_state(original_state))
        require(
            original_state_digest == row.get("state_sha256"),
            f"source state hash mismatch: {name}",
        )

        public_state = copy.deepcopy(original_state)
        original_log_entries = len(public_state["log"])
        public_state["log"] = []
        for key in original_state:
            if key != "log":
                require(public_state[key] == original_state[key], f"changed field {key}: {name}")
        require(set(public_state) == set(original_state), f"top-level fields changed: {name}")

        public_data = json_bytes(public_state)
        public_state_digest = state_hash(gameplay_state(public_state))
        transformed[name] = public_data
        row["original_sha256"] = row["sha256"]
        row["original_state_sha256"] = row["state_sha256"]
        row["sha256"] = sha256(public_data)
        row["bytes"] = len(public_data)
        row["state_sha256"] = public_state_digest
        listed[name]["sha256"] = row["sha256"]
        listed[name]["bytes"] = row["bytes"]
        audit_saves.append(
            {
                "file": name,
                "original_log_entries": original_log_entries,
                "fields_equal_except_log": True,
                "original_sha256": row["original_sha256"],
                "sha256": row["sha256"],
                "original_state_sha256": row["original_state_sha256"],
                "state_sha256": row["state_sha256"],
            }
        )

    guide_data = transform_guide(child_path(source, PurePosixPath(GUIDE_NAME)).read_bytes())
    transformed[GUIDE_NAME] = guide_data
    listed[GUIDE_NAME]["bytes"] = len(guide_data)
    listed[GUIDE_NAME]["sha256"] = sha256(guide_data)
    manifest["save_bytes_modified"] = True
    ordered_manifest: dict[str, Any] = {}
    for key, value in manifest.items():
        ordered_manifest[key] = value
        if key == "save_bytes_modified":
            ordered_manifest["save_modification"] = SAVE_MODIFICATION
    manifest = ordered_manifest
    require(manifest.get("unassisted") is True, "unassisted flag changed")
    output_manifest_data = json_bytes(manifest)

    after_read = file_snapshot(source)
    require(after_read == before, "source collection changed while it was read")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".public-checkpoints-", dir=output.parent))
    try:
        for name in listed:
            destination = child_path(temporary, safe_relative_path(name))
            destination.parent.mkdir(parents=True, exist_ok=True)
            if name in transformed:
                destination.write_bytes(transformed[name])
            else:
                destination.write_bytes(child_path(source, PurePosixPath(name)).read_bytes())
        (temporary / MANIFEST_NAME).write_bytes(output_manifest_data)
        require(set(file_snapshot(temporary)) == expected, "generated membership differs")
        temporary.rename(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    require(file_snapshot(source) == before, "source collection was mutated")
    return {
        "schema": "public-checkpoint-preparation-audit-v1",
        "source": str(source),
        "output": str(output),
        "source_file_count": len(before),
        "checkpoint_count": len(save_names),
        "source_manifest_sha256": sha256(manifest_data),
        "output_manifest_sha256": sha256(output_manifest_data),
        "source_unchanged": True,
        "save_bytes_modified": True,
        "unassisted": True,
        "modification": SAVE_MODIFICATION,
        "guide": {
            "path": GUIDE_NAME,
            "bytes": len(guide_data),
            "sha256": sha256(guide_data),
        },
        "saves": audit_saves,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="archived original collection")
    parser.add_argument("output", type=Path, help="fresh output directory")
    parser.add_argument(
        "--audit-report",
        type=Path,
        help="optional fresh JSON path for a transformation audit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = prepare(args.source, args.output)
    if args.audit_report is not None:
        audit_path = args.audit_report.resolve()
        require(not audit_path.exists(), f"audit report already exists: {audit_path}")
        require(
            not audit_path.is_relative_to(Path(report["source"])),
            "audit report cannot be inside the source collection",
        )
        require(
            not audit_path.is_relative_to(Path(report["output"])),
            "audit report cannot be inside the output collection",
        )
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_bytes(json_bytes(report))
    print(
        f"Prepared {report['checkpoint_count']} checkpoints in {report['output']}; "
        "source unchanged."
    )
    if args.audit_report is not None:
        print(f"Audit report: {args.audit_report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
