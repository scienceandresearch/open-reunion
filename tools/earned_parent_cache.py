"""Process-local materialization of an already accepted graphical parent."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile

from openreunion.dos.session import RecoveredSession


class ParentCacheError(ValueError):
    """The accepted-report chain is not safe to cache."""


def _digest_json(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise ParentCacheError('Catalog is not canonically serializable') from exc
    return hashlib.sha256(encoded).hexdigest()


def _session_bytes(session):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'session.json'
        session.save(path)
        return path.read_bytes()


def _load_session(catalog, payload):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'session.json'
        path.write_bytes(payload)
        return RecoveredSession.load(catalog, path)


@dataclass(frozen=True)
class AcceptedChain:
    digest: str
    tip_sha256: str
    paths: tuple
    endpoint_state: dict


def inspect_accepted_chain(project, tip):
    """Validate hash links and dual-adapter invariants from base through tip."""
    project = Path(project).resolve()
    current = Path(tip).resolve()
    seen = set()
    descending = []
    required_digest = None
    while True:
        if not current.is_relative_to(project) or current in seen:
            raise ParentCacheError('Parent report escapes the project or forms a cycle')
        seen.add(current)
        try:
            raw = current.read_bytes()
            report = json.loads(raw)
        except (OSError, ValueError, TypeError) as exc:
            raise ParentCacheError(f'Cannot read accepted report {current}') from exc
        digest = hashlib.sha256(raw).hexdigest()
        if required_digest is not None and digest != required_digest:
            raise ParentCacheError('Child report parent digest does not match')
        if not isinstance(report, dict) or report.get('passed') is not True:
            raise ParentCacheError('Every cached report must be accepted')
        # Legacy graphical reports predate this marker. Their earned status is
        # still established below by replay, endpoint equality and the absence
        # of assisted/admin state. Any explicit value must be exactly false.
        if report.get('prepared_state', False) is not False:
            raise ParentCacheError('Prepared parent reports cannot be cached')
        adapters = report.get('adapters')
        if not isinstance(adapters, list) or len(adapters) != 2:
            raise ParentCacheError('Accepted parent must contain two adapters')
        for row in adapters:
            if not isinstance(row, dict) or row.get('passed') is not True:
                raise ParentCacheError('Both accepted adapters must pass')
            if row.get('prepared_state', False) is not False:
                raise ParentCacheError('Prepared adapter state cannot be cached')
            state = row.get('final_state')
            journal = row.get('journal')
            if not isinstance(state, dict) or state.get('assisted') is not False:
                raise ParentCacheError('Both accepted endpoints must be unassisted')
            if not isinstance(journal, list):
                raise ParentCacheError('Both accepted adapters need complete journals')
            if row.get('admin_used', False) is not False:
                raise ParentCacheError('Admin-marked ancestry cannot be cached')
            for command in journal:
                if (not isinstance(command, dict) or not isinstance(command.get('action'), str)
                        or not isinstance(command.get('arguments'), dict)):
                    raise ParentCacheError('Malformed accepted command journal')
                if command['action'] == 'admin':
                    raise ParentCacheError('Admin ancestry cannot be cached')
        if adapters[0]['journal'] != adapters[1]['journal']:
            raise ParentCacheError('Adapter journals differ; replay them separately')
        if adapters[0]['final_state'] != adapters[1]['final_state']:
            raise ParentCacheError('Adapter endpoint states differ')
        descending.append((current, raw, digest, report))
        if 'parent' not in report:
            break
        try:
            parent = (project/report['parent']).resolve()
        except (TypeError, ValueError) as exc:
            raise ParentCacheError('Child report has an invalid parent path') from exc
        if not parent.is_relative_to(project) or parent in seen:
            raise ParentCacheError('Parent report escapes the project or forms a cycle')
        expected = report.get('parent_sha256')
        if not isinstance(expected, str) or len(expected) != 64:
            raise ParentCacheError('Child report lacks a valid parent digest')
        current = parent
        required_digest = expected.lower()

    ordered = list(reversed(descending))
    chain = hashlib.sha256()
    for path, raw, _, _ in ordered:
        relative = path.relative_to(project).as_posix().encode()
        chain.update(len(relative).to_bytes(4, 'big')); chain.update(relative)
        chain.update(len(raw).to_bytes(8, 'big')); chain.update(raw)
    return AcceptedChain(
        digest=chain.hexdigest(),
        tip_sha256=descending[0][2],
        paths=tuple(path.relative_to(project).as_posix() for path, *_ in ordered),
        endpoint_state=deepcopy(descending[0][3]['adapters'][0]['final_state']),
    )


class EarnedParentCache:
    """Cache complete session bytes only for a validated identical adapter chain."""
    def __init__(self, project):
        self.project = Path(project).resolve()
        self._entries = {}

    def load_or_replay(self, content, parent, adapter, replay):
        if adapter not in (0, 1):
            raise ParentCacheError('Adapter index must be zero or one')
        if not callable(replay):
            raise TypeError('replay must be callable')
        chain = inspect_accepted_chain(self.project, parent)
        catalog_sha256 = _digest_json(content.catalog)
        initial_payload = _session_bytes(content.new_game())
        initial_sha256 = hashlib.sha256(initial_payload).hexdigest()
        key = (chain.digest, catalog_sha256, initial_sha256)
        entry = self._entries.get(key)
        mode = 'cache_verified'
        if entry is None:
            replayed = replay()
            if not isinstance(replayed, RecoveredSession):
                raise ParentCacheError('Replay did not return a recovered session')
            # A long replay leaves time for an accepted report to be replaced.
            # Never bind its endpoint to the bytes inspected before replay.
            after_replay = inspect_accepted_chain(self.project, parent)
            if after_replay != chain:
                raise ParentCacheError('Accepted parent chain changed during replay')
            if (replayed.admin_enabled or replayed.state.get('assisted') is not False
                    or replayed.state != chain.endpoint_state):
                raise ParentCacheError('Replayed endpoint does not match the accepted report')
            payload = _session_bytes(replayed)
            # Public load performs complete state/audio/effect/result validation.
            checked = _load_session(content.catalog, payload)
            if checked.state != chain.endpoint_state or checked.admin_enabled:
                raise ParentCacheError('Serialized replay endpoint did not validate')
            entry = {'payload': payload, 'replay_adapter': adapter}
            self._entries[key] = entry
            mode = 'replayed'
        session = _load_session(content.catalog, entry['payload'])
        if (session.admin_enabled or session.state.get('assisted') is not False
                or session.state != chain.endpoint_state):
            raise ParentCacheError('Cached endpoint failed fresh validation')
        endpoint_sha256 = hashlib.sha256(entry['payload']).hexdigest()
        provenance = {
            'mode': mode,
            'chain_sha256': chain.digest,
            'tip_report_sha256': chain.tip_sha256,
            'reports': list(chain.paths),
            'catalog_sha256': catalog_sha256,
            'new_game_save_sha256': initial_sha256,
            'endpoint_save_sha256': endpoint_sha256,
            'replay_adapter': entry['replay_adapter'],
        }
        return session, provenance
