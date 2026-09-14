"""Original battle-result backgrounds, opaque 6x8 font and loss overlays."""
from ..core import GameError,integer
from .assets import Picture
from .catalog import DATA_FILE_OFFSET
from .result_display import load_result_palette,fade_result_palette

# 27555..27581: reserved DAC entries 249..251 survive picture loading.
FONT_DAC=bytes([0,0,0,45,42,0,32,29,0])


def result_palette(background,fade_step=5):
    logical=bytearray(768);logical[249*3:252*3]=FONT_DAC
    logical=load_result_palette(background.palette,logical)
    logical=fade_result_palette(logical,bytes(768),fade_step)
    # The standalone crop uses unshifted indices. Full display envelopes retain
    # all logical/device colors separately instead of fabricating the remainder.
    rotated=logical[64*3:]+logical[:64*3]
    return bytes(v*255//63 for v in rotated)


def validate_characters(characters):
    if not isinstance(characters,str) or len(characters)!=78 or len(set(characters))!=78 or not characters.isascii() or any(ord(c)<32 for c in characters):
        raise GameError('Invalid original character map.')


def read_characters(data):
    start=DATA_FILE_OFFSET+0x5BEE
    if data[start]!=78:raise GameError('Unsupported original character map.')
    try:characters=data[start+1:start+79].decode('ascii')
    except UnicodeError as exc:raise GameError('Invalid original character map.') from exc
    validate_characters(characters);return characters


def draw_text(pixels,width,height,font,characters,text,x,y,columns,offset):
    """36126: fixed columns, opaque six-by-eight cells, wrapping color offset.

    Coordinates are bounded in the port instead of wrapping the DOS buffer.
    The font PIC starts after the original resource's 128-byte prefix.
    """
    validate_characters(characters)
    if (font.width,font.height)!=(320,32):raise GameError('Unsupported character atlas.')
    if not isinstance(text,str) or not text.isascii() or len(text)>255:raise GameError('Invalid original text.')
    integer(columns,'Text columns',maximum=255);integer(x,'Text x');integer(y,'Text y')
    if len(pixels)!=width*height or x+6*columns>width or y+8>height:raise GameError('Text exceeds its picture.')
    for column,char in enumerate(text.ljust(columns)[:columns]):
        index=characters.find(char)
        if index<0:index=78 # Original scans one byte beyond its 78-character map.
        source=(index//20)*8*320+(index%20)*16
        for row in range(8):
            target=(y+row)*width+x+column*6
            pixels[target:target+6]=bytes((v+offset)&255 for v in font.pixels[source+row*320:source+row*320+6])


def loss_labels(losses,*,original_columns=False):
    if not isinstance(losses,dict) or set(losses)!={'friendly','hostile'}:raise GameError('Invalid battle losses.')
    labels=[]
    for side,top in (('friendly',39),('hostile',94)):
        values=losses[side]
        if not isinstance(values,(list,tuple)) or len(values)!=4:raise GameError('Expected four casualty totals.')
        for index,value in enumerate(values):
            integer(value,'Battle casualties',maximum=2**63-1)
            text=str(value).rjust(4)
            labels.append({'text':text,'x':87,'y':top+9*index,'columns':4 if original_columns else len(text)})
    return labels


def compose_result(background,font,characters,losses,*,animation=None,frame=1,original_columns=False,fade_step=5):
    if (background.width,background.height)!=(320,151):raise GameError('Unsupported battle-result background.')
    pixels=bytearray(background.pixels)
    if animation is not None:
        if (animation.width,animation.height)!=(152,68):raise GameError('Unsupported ground-result animation.')
        integer(frame,'Defeat animation frame',minimum=1,maximum=3)
        for row in range(61):
            start=(row+1)*320+235;source=row*152+(frame-1)*51
            pixels[start:start+50]=animation.pixels[source:source+50]
    # Background load adds 64; the raw font adds -7. In the supplied result
    # palette these opaque font pixels therefore use indices 185..187.
    for label in loss_labels(losses,original_columns=original_columns):
        draw_text(pixels,320,151,font,characters,offset=-71,**label)
    return Picture(320,151,bytes(pixels),result_palette(background,fade_step))


def advance_ground_result(frame,counter,enabled=True):
    """D1B9: one sprite update per thirteen original main-loop calls."""
    integer(frame,'Defeat animation frame',minimum=1,maximum=3)
    integer(counter,'Defeat animation counter',maximum=13)
    if type(enabled) is not bool:raise GameError('Invalid defeat animation state.')
    if not enabled:return frame,counter,None
    counter=counter%13+1
    return (frame%3+1,counter,frame) if counter==1 else (frame,counter,None)


class BattleResultPictures:
    def __init__(self,content):
        if 'character_set' not in content.catalog:raise GameError('Character metadata is missing; re-extract the content bundle.')
        self.content=content;self.characters=content.catalog['character_set'];validate_characters(self.characters)
        self.font=content.indexed_picture('GRAFIKA/CHARSET1.PIC');self.assets={};self.cache={}

    def picture(self,family,won,losses,*,frame=1,fade_step=5):
        if family not in ('space','ground') or type(won) is not bool:raise GameError('Invalid battle-result kind.')
        integer(fade_step,'Result fade step',maximum=5)
        labels=loss_labels(losses);key=(family,won,tuple(row['text'] for row in labels),frame,fade_step)
        if key not in self.cache:
            name=('SP' if family=='space' else 'GR')+('VICT' if won else 'LOST')
            for asset in (name,'GRANIM') if family=='ground' and not won else (name,):
                if asset not in self.assets:self.assets[asset]=self.content.indexed_picture('WAR/'+asset+'.PIC')
            picture=compose_result(self.assets[name],self.font,self.characters,losses,
                animation=self.assets['GRANIM'] if family=='ground' and not won else None,frame=frame,fade_step=fade_step)
            if len(self.cache)>=12:self.cache.clear()
            self.cache[key]=picture
        return self.cache[key]
