"""Original control labels and 40x24 icons, composed in 48x32 button frames."""
import struct
from ..core import GameError,integer
from .assets import Picture
from .catalog import DATA_FILE_OFFSET

ICON_COUNT=68
ICON_PIXELS=40*24
MAGIC=b'ORIC\x01'


def read_buttons(data):
    buttons=[]
    for index in range(78):
        raw=data[DATA_FILE_OFFSET+0x488A+18*index:DATA_FILE_OFFSET+0x488A+18*(index+1)]
        if len(raw)!=18 or raw[0]>17:raise GameError('Invalid original control label.')
        try:label=raw[1:1+raw[0]].decode('ascii').rstrip()
        except UnicodeError as exc:raise GameError('Invalid original control label.') from exc
        buttons.append({'id':index,'label':label,'icon':data[DATA_FILE_OFFSET+0x4E06+index]})
    validate_buttons(buttons);return buttons


def validate_buttons(buttons):
    if not isinstance(buttons,list) or len(buttons)!=78:raise GameError('Invalid control button table.')
    for index,row in enumerate(buttons):
        if not isinstance(row,dict) or set(row)!={'id','label','icon'} or type(row['id']) is not int or row['id']!=index:
            raise GameError('Invalid control button record.')
        if not isinstance(row['label'],str) or len(row['label'])>17 or not row['label'].isascii() or any(ord(c)<32 for c in row['label']):
            raise GameError('Invalid control label.')
        # Three records absent from the supplied layouts contain out-of-bank bytes.
        # Preserve the evidence; rendering validates against the actual bank.
        integer(row['icon'],'Control icon reference',maximum=255)


def icon_chunks(data):
    if not isinstance(data,bytes) or len(data)>131072:raise GameError('Invalid icon bank size.')
    chunks=[];offset=0
    for _ in range(ICON_COUNT):
        if offset+2>len(data):raise GameError('Truncated icon bank.')
        size=struct.unpack_from('<H',data,offset)[0];offset+=2
        if not 2<=size<=1921 or offset+size>len(data):raise GameError('Invalid icon record size.')
        chunks.append(data[offset:offset+size]);offset+=size
    if offset!=len(data):raise GameError('Trailing icon bank data.')
    return chunks


def decode_icon(data):
    """2F54C..2F56A: RLE plus wrapping palette offset two; 960 pixels."""
    if not isinstance(data,bytes) or len(data)>1921 or not data or data[-1]!=12:
        raise GameError('Invalid icon end marker.')
    pixels=bytearray();offset=0;end=len(data)-1
    while offset<end:
        value=data[offset];offset+=1;count=1
        if value>=192:
            count=value&63
            if not count or offset>=end:raise GameError('Invalid icon run.')
            value=data[offset];offset+=1
        if len(pixels)+count>ICON_PIXELS:raise GameError('Icon run exceeds its buffer.')
        pixels.extend(bytes([(value+2)&255])*count)
    if len(pixels)!=ICON_PIXELS:raise GameError('Truncated icon pixels.')
    return bytes(pixels)


def decode_icons(data):return tuple(decode_icon(chunk) for chunk in icon_chunks(data))


def converted_icons(icons):
    if len(icons)!=ICON_COUNT or any(not isinstance(p,bytes) or len(p)!=ICON_PIXELS for p in icons):
        raise GameError('Invalid converted icon bank.')
    return MAGIC+b''.join(icons)


def decode_converted_icons(data):
    if len(data)!=len(MAGIC)+ICON_COUNT*ICON_PIXELS or not data.startswith(MAGIC):
        raise GameError('Invalid converted icon bank.')
    return tuple(data[len(MAGIC)+i*ICON_PIXELS:len(MAGIC)+(i+1)*ICON_PIXELS] for i in range(ICON_COUNT))


def button_picture(frame,icons,icon):
    integer(icon,'Control icon',maximum=67)
    if (frame.width,frame.height)!=(240,32):raise GameError('Unsupported control frame size.')
    # Index rotation expresses the original +2 decode while preserving the
    # supplied palette's RGB. The 40th source column is not copied by DOS.
    pixels=bytearray((frame.pixels[y*240+x]+2)&255 for y in range(32) for x in range(48))
    if icon:
        for y in range(24):pixels[(y+4)*48+4:(y+4)*48+43]=icons[icon][y*40:y*40+39]
    return Picture(48,32,bytes(pixels),frame.palette[-6:]+frame.palette[:-6])


class ControlPictures:
    def __init__(self,content):
        self.frame=content.indexed_picture('ICON/ICONMAIN.PIC');self.icons=content.control_icons();self.cache={}

    def button(self,icon):
        if icon not in self.cache:self.cache[icon]=button_picture(self.frame,self.icons,icon)
        return self.cache[icon]

    def panel(self,buttons,slots,page=0):
        integer(page,'Control page',maximum=1)
        if page and not slots[6]:raise GameError('This control layout has one page.')
        pixels=panel_pixels(self.frame,self.icons,buttons,slots)
        return panel_picture(self.frame,pixels,page)

    def slide(self,buttons,slots,steps,page=0):
        from .control_slide import slide_rows
        if not slots[6]:raise GameError('This control layout has one page.')
        rows=slide_rows(steps,page);pixels=panel_pixels(self.frame,self.icons,buttons,slots)
        return tuple(panel_window(self.frame,pixels,row) for row in rows)


def panel_picture(frame,pixels,page=0):
    integer(page,'Control page',maximum=1)
    return panel_window(frame,pixels,page*33)


def panel_window(frame,pixels,row):
    integer(row,'Control panel row',maximum=33)
    if len(pixels)!=320*66:raise GameError('Invalid panel backing buffer.')
    # 2F394 presents from buffer + 1, aligning frames at visible x=0 and
    # the page tile at x=288. The linear spill is part of this last tile.
    start=row*320+1
    return Picture(320,32,pixels[start:start+320*32],frame.palette[-6:]+frame.palette[:-6])


def panel_pixels(frame,icons,buttons,slots,background=None):
    """2ED4F: two six-button banks, including the original linear edge spill.

    The caller owns the untouched pixels. Each displayed bank is 320x32;
    bank two starts on row 33 of the backing buffer.
    """
    validate_buttons(buttons)
    if not isinstance(slots,(list,tuple)) or len(slots)!=12:raise GameError('Expected twelve control slots.')
    for action in slots:integer(action,'Control action',maximum=77)
    if background is None:background=bytes(320*66)
    if not isinstance(background,bytes) or len(background)!=320*66:raise GameError('Invalid panel background.')
    pixels=bytearray(background);second=bool(slots[6])
    for index in range(12 if second else 6):
        picture=button_picture(frame,icons,buttons[slots[index]]['icon'])
        start=(index//6)*33*320+1+(index%6)*48
        for y in range(32):pixels[start+y*320:start+y*320+48]=picture.pixels[y*48:(y+1)*48]
    for page,source_x in ((0,80),(1,48)) if second else ((0,112),):
        start=page*33*320+289
        for y in range(32):
            # DOS uses a linear copy: destination column 320 reaches the
            # following row's column zero, including the final spacer row.
            pixels[start+y*320:start+y*320+32]=bytes((v+2)&255 for v in frame.pixels[y*240+source_x:y*240+source_x+32])
    return bytes(pixels)


def pointer_slot(x,y,hotspots=()):
    """3C61C with its actual 3C545 grid helper; signed DOS pointer words.

    Hotspots are (left, top, width, height) in ascending record order.
    Lowest record wins overlaps; panel and status areas take precedence.
    """
    integer(x,'Pointer x',minimum=-32768,maximum=32767)
    integer(y,'Pointer y',minimum=-32768,maximum=32767)
    if 0<=x<=287 and 0<=y<=32:return x//48+1
    if x>=288 and y<33:return 13
    if x>=218 and 33<y<46:return 14
    def signed(value):return (value+32768)%65536-32768
    for index,record in enumerate(hotspots,1):
        if not isinstance(record,(tuple,list)) or len(record)!=4:raise GameError('Invalid control hotspot.')
        left,top,width,height=record
        integer(left,'Hotspot left',minimum=-32768,maximum=32767)
        integer(top,'Hotspot top',maximum=255)
        integer(width,'Hotspot width',maximum=65535)
        integer(height,'Hotspot height',maximum=255)
        if left<=x<=signed(left+width-1) and top<=y<=top+height-1:return index+20
    return 0
