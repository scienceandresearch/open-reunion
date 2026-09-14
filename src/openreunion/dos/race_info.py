"""Original fixed Pascal race profiles and survey-gated access."""
from ..core import GameError

TEXT_NAME='SZ_FAJ.RAW'
RACES=12
LINES=12
STRIDE=36


def decode_profiles(data):
    """Loader 35063..350C2 reads 5184 bytes, with no text cipher."""
    if not isinstance(data,bytes) or len(data)!=RACES*LINES*STRIDE:
        raise GameError('Race profiles must contain 12 records of 432 bytes.')
    lines=[]
    for offset in range(0,len(data),STRIDE):
        length=data[offset]
        if length>=STRIDE:
            raise GameError('Race profile line exceeds its 35-byte Pascal capacity.')
        lines.append(data[offset+1:offset+1+length].decode('cp437'))
    return lines


def profile(lines,owner):
    if type(owner) is not int or not 1<=owner<=RACES:
        raise GameError('Unknown race profile.')
    if (not isinstance(lines,list) or len(lines)!=RACES*LINES
            or any(not isinstance(line,str) or len(line)>=STRIDE for line in lines)):
        raise GameError('Invalid race profiles; extract the original content again.')
    record=lines[(owner-1)*LINES:owner*LINES]
    # Reflow the original narrow screen's lines, retaining paragraph breaks.
    paragraphs=[];words=[]
    for line in record[1:]:
        if line.strip():words.append(line.strip())
        elif words:paragraphs.append(' '.join(words));words=[]
    if words:paragraphs.append(' '.join(words))
    return {'title':record[0].strip(),'description':'\n\n'.join(paragraphs)}


def revealed_race(raw):
    """Original click gate 8D2E..8D49; signed byte comparison at survey 40."""
    return raw[0] if 2<=raw[0]<=RACES and 40<=raw[12]<128 else None
