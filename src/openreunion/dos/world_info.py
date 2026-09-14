"""Survey-gated planet information from original display code 2ABF4..2AF96."""
import struct
from .catalog import ORE_KEYS

TERRAINS=('No data','Earth-like','Gaseous','Icy','Watery','Tropical','Desert',
          'Swampy','Rocky','Too hot','No atmosphere')


def survey_information(raw,catalog):
    survey=raw[12] if raw[12]<128 else raw[12]-256
    terrain=raw[21]
    rules=catalog['surface_rules']
    habitable=bool(raw[2] and 1<=terrain<=len(rules['groups'])
                   and rules['editable'][rules['groups'][terrain-1]-1])
    owner=raw[0]
    # The original portrait conceals alien identity below survey 40, using
    # an unidentified-alien portrait at 30. Do not leak the raw owner ID.
    visible_owner=(owner if owner==1 or survey>=40 else
                   13 if owner>=2 and survey>=30 else 0 if owner==0 and survey>=30 else None)
    return {'survey':survey,'owner':visible_owner,
            'population':struct.unpack_from('<I',bytes(raw),13)[0] if owner<2 or survey>=40 else None,
            'terrain':(TERRAINS[terrain] if terrain<len(TERRAINS) else 'Unclassified terrain') if survey>5 else None,
            'diameter_km':struct.unpack_from('<H',bytes(raw),23)[0] if survey>=3 else None,
            'temperature_k':struct.unpack_from('<h',bytes(raw),25)[0] if survey>=5 else None,
            'habitable':habitable if survey>=20 else None,
            'ore_presence':{key:bool(raw[3] and raw[59+i]>=10) for i,key in enumerate(ORE_KEYS)} if survey>=10 else None,
            # Numeric abundance is a modern convenience at the original ore
            # reveal gate. The original display only says YES/NO.
            'ore_abundance':dict(zip(ORE_KEYS,raw[59:65])) if survey>=10 and raw[3] else
                            dict.fromkeys(ORE_KEYS,0) if survey>=10 else None}


def owner_label(report,catalog):
    owner=report['owner']
    if owner is None:return 'Unknown'
    if owner==0:return 'Unclaimed'
    if owner==1:return 'Player'
    if owner==13:return 'Unidentified aliens'
    names=catalog['alien_names']
    return names[owner-2] if 2<=owner<len(names)+2 else 'Unknown'


def environment_summary(report):
    terrain=report['terrain'] or 'unknown (survey 6)'
    temperature=(f"{report['temperature_k']} K" if report['temperature_k'] is not None else 'unknown (survey 5)')
    return f'Terrain: {terrain} | Temperature: {temperature}'
