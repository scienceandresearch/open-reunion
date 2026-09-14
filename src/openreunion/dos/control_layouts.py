"""Original 25-byte control layouts; layout 30 is the Continue button bank."""
from ..core import GameError,integer
from .catalog import DATA_FILE_OFFSET

TABLE=0x50FB
LAYOUT_COUNT=38


def validate_layouts(layouts):
    if not isinstance(layouts,list) or len(layouts)!=LAYOUT_COUNT:raise GameError('Invalid control layout table.')
    for index,row in enumerate(layouts,1):
        if not isinstance(row,dict) or set(row)!={'id','name','buttons'} or type(row['id']) is not int or row['id']!=index:
            raise GameError('Invalid control layout record.')
        if not isinstance(row['name'],str) or len(row['name'])>9 or not row['name'].isascii() or any(ord(c)<32 for c in row['name']):
            raise GameError('Invalid control layout name.')
        if not isinstance(row['buttons'],list) or len(row['buttons'])>12:raise GameError('Invalid control layout buttons.')
        for button in row['buttons']:integer(button,'Control button',maximum=255)


def read_layouts(data):
    result=[]
    for index in range(1,LAYOUT_COUNT+1):
        raw=data[DATA_FILE_OFFSET+TABLE+25*index:DATA_FILE_OFFSET+TABLE+25*(index+1)]
        if len(raw)!=25 or raw[0]>9 or raw[12]>12:raise GameError('Invalid original control layout.')
        try:name=raw[1:1+raw[0]].decode('ascii')
        except UnicodeError as exc:raise GameError('Invalid original control name.') from exc
        result.append({'id':index,'name':name,'buttons':list(raw[13:13+raw[12]])})
    validate_layouts(result);return result


def select_layout(layouts,number,main_visible=1):
    """2ECA9..2ED4C selects slots, redraws/presents, and clears pending input.

    The argument is a table index, not a duration. The twelve button words are
    stored at 21-byte strides in DOS; unrelated bytes in those records survive.
    """
    validate_layouts(layouts);integer(number,'Control layout',minimum=1,maximum=LAYOUT_COUNT)
    integer(main_visible,'Main control visibility',maximum=255)
    buttons=layouts[number-1]['buttons']
    return {'visible':main_visible if number==1 else 1,'buttons':buttons+[0]*(12-len(buttons)),'input':0}


def result_control_enabled(catalog,phase):
    if phase!='result':return False
    if 'control_layouts' not in catalog:raise GameError('Control layouts are missing; re-extract the local content bundle.')
    return 65 in select_layout(catalog['control_layouts'],30)['buttons']
