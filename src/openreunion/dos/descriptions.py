"""Original fixed Pascal candidate and completed-product descriptions."""
from ..core import GameError,integer

# record count, lines per record, byte stride per Pascal string
FORMATS={'SZ_FACE.RAW':(12,4,41),'SZ_TALAL.RAW':(35,7,31)}


def decode_descriptions(name,data):
    if name not in FORMATS:raise GameError('Unknown description table.')
    count,lines,stride=FORMATS[name]
    if not isinstance(data,bytes) or len(data)!=count*lines*stride:
        raise GameError(f'{name} must contain {count} records of {lines*stride} bytes.')
    result=[]
    for offset in range(0,len(data),stride):
        length=data[offset]
        if length>=stride:raise GameError('Description exceeds its Pascal string capacity.')
        result.append(data[offset+1:offset+1+length].decode('cp437'))
    return result


def record(name,lines,index):
    count,size,stride=FORMATS[name]
    integer(index,'Description ID',minimum=1,maximum=count)
    if (not isinstance(lines,list) or len(lines)!=count*size
            or any(not isinstance(line,str) or len(line)>=stride for line in lines)):
        raise GameError('Invalid description records; extract the original content again.')
    return lines[(index-1)*size:index*size]


def paragraphs(lines):
    result=[];current=''
    for line in lines:
        line=line.strip()
        if line:current+=('' if not current or current.endswith('-') else ' ')+line
        elif current:result.append(current);current=''
    if current:result.append(current)
    return '\n\n'.join(result)


def product_description(lines,product_id):
    data=record('SZ_TALAL.RAW',lines,product_id)
    return {'title':data[0].strip(),'description':paragraphs(data[1:])}


def candidate_description(lines,candidate_id):
    data=record('SZ_FACE.RAW',lines,candidate_id)
    return {'title':data[0].strip(),'description':paragraphs(data[1:3]),'original_offer':data[3].strip()}


def product_description_available(row):
    # The original description list, 28270..282C5, includes completed research.
    return row['research_state']==5
