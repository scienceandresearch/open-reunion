"""Save-independent startup from executable defaults and the original INIT asset."""
import hashlib
import struct

from ..core import GameError, integer
from ..legacy import LegacySave
from .campaign import random_bounded
from .catalog import DATA_FILE_OFFSET, SUPPORTED_HASHES
from .savefile import LAYOUT, SaveBlocks

PROFILE = 'reunion-startup-v1'
INIT_SHA256 = 'a643823bf57c28de54a211079b9e0e6dc5725e9469e57439977ee579fcc8f069'
STATIC_BLOCKS = tuple(b for b in LAYOUT['blocks'] if b['kind'] == 'ds')


def extract_startup(executable, init):
    """Extract only original startup data; never open a numbered player save."""
    digest = hashlib.sha256(executable).hexdigest()
    if digest not in SUPPORTED_HASHES:
        raise GameError('Unsupported executable for new-game initialization.')
    if len(init) != 14002 or hashlib.sha256(init).hexdigest() != INIT_SHA256:
        raise GameError('Unsupported or modified SAVE/INIT startup asset.')
    rows = []
    for block in STATIC_BLOCKS:
        start = DATA_FILE_OFFSET + block['address']
        rows.append(executable[start:start+block['length']].ljust(block['length'], b'\0').hex())
    return {'profile': PROFILE, 'executable_sha256': digest,
            'static_blocks': rows, 'init': init.hex()}


def startup_bytes(definition, catalog, seed):
    """Construct an in-memory serialization for the shared state decoder.

    This buffer is generated afresh; it is not a saved player session. The
    serialized format is only an internal bridge to the verified field readers.
    """
    integer(seed, 'New-game seed', maximum=2**32-1)
    if not isinstance(definition, dict) or set(definition) != {'profile', 'executable_sha256', 'static_blocks', 'init'}:
        raise GameError('Invalid new-game startup data.')
    if definition['profile'] != PROFILE or definition['executable_sha256'] != catalog['sha256']:
        raise GameError('New-game startup data uses a different executable profile.')
    rows = definition['static_blocks']
    if not isinstance(rows, list) or len(rows) != len(STATIC_BLOCKS):
        raise GameError('Incomplete new-game startup data.')
    data = bytearray(41670)
    data[:9] = b'\x08New game'
    try:
        for row, block in zip(rows, STATIC_BLOCKS):
            if not isinstance(row, str) or len(row) != 2*block['length']:
                raise ValueError('Invalid startup block size')
            raw = bytes.fromhex(row)
            if len(raw) != block['length']:
                raise ValueError('Invalid startup block encoding')
            at = block['save_offset']
            data[at:at+len(raw)] = raw
        if not isinstance(definition['init'], str) or len(definition['init']) != 28004:
            raise ValueError('Invalid startup building asset size')
        init = bytes.fromhex(definition['init'])
        if len(init) != 14002 or hashlib.sha256(init).hexdigest() != INIT_SHA256:
            raise ValueError('Unrecognized startup building asset')
    except ValueError as exc:
        raise GameError(str(exc)) from exc
    blocks = SaveBlocks(bytes(data))
    def write(address, value, fmt='H'):
        raw = struct.pack('<'+fmt, value)
        at = blocks.offset(address, len(raw))
        data[at:at+len(raw)] = raw
    # File 4DB1..5043: game defaults, inactive research timers, and the first
    # timed discovery. Presentation-only registers are not part of this state.
    for address in (0x7AE2, 0x95A2, 0xA21A, 0xA2C2, 0xA2C4, 0xA2C8,
                    0xA2CA, 0xA2CC, 0xA2CE, 0x5D9C, 0x5D9E, 0x5DA0):
        write(address, 0)
    for address in range(0x7AE6, 0x7B06, 2):
        write(address, 0)
    for address in range(0x95A4, 0x95BE, 2):
        write(address, 0)
    for address in (*range(0x773E, 0x774A), 0xA2D4, *range(0xA2D6, 0xA2DA)):
        write(address, 0, 'B')
    for address in range(0x91A0, 0x91E6, 2):
        write(address, -1, 'h')
    for address, value in ((0x7AE4, 1), (0x91EA, 1), (0x95B4, 10),
                           (0x95DE, 2927), (0x95E0, 8), (0x95E2, 13), (0x95E4, 23),
                           (0xA2C6, 1), (0xA2C0, struct.unpack_from('<H', init)[0])):
        write(address, value)
    write(0x95BE, 120000, 'I')
    for address in range(0x95C6, 0x95DE, 4):
        write(address, 0, 'I')
    next_seed, roll = random_bounded(seed, 400)
    write(0x5D58, 6000+roll)
    # File 220B9..2211F creates no moving fleets and one empty local defense.
    # Its shared record initializer uses this catalog-derived default name.
    from .equipment import rename_fleet
    local = rename_fleet([0]*161, catalog['fleet_rules'][4]['default_name'])
    local[0] = 5
    local[19:23] = [1, 5, 0, 7]
    pointers = {0xA2BC: init[2:], 0xA2D0: bytes(5152)+bytes(local)+bytes(5152-161),
                0x7ADE: bytes(795)}
    for block in LAYOUT['blocks']:
        if block['kind'] == 'pointer':
            at = block['save_offset']
            data[at:at+block['length']] = pointers[block['address']]
    return bytes(data), next_seed


def new_session(definition, catalog, *, seed=1994,hero=2):
    from .session import RecoveredSession, NOTICE
    from .hero import validate_hero
    validate_hero(hero)
    data, next_seed = startup_bytes(definition, catalog, seed)
    session = RecoveredSession._from_legacy(catalog, LegacySave(data),hero=hero)
    session.state['campaign']['rng'] = next_seed
    session.state['log'] = ['New game initialized from original executable defaults and startup buildings.',
                            NOTICE, f'New-game random seed: {seed}.']
    return session
