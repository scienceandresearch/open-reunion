"""Original building information card, live statistics and six-line prose."""
import struct
from ..core import GameError,integer
from .colony import building_rules
from .descriptions import paragraphs

TEXT_NAME='SZ_FELSZ.TXT'
# DS183E, indexed by building category: production, workers, energy rows.
ROWS=((-1,-1,-1),(1,2,-1),(1,-1,2),(-1,1,2),(-1,-1,1),
      (-1,-1,1),(-1,1,2),(-1,-1,1),(1,2,-1),(1,-1,-1))
# Source offsets within DESIGNER's (94,5,123,77) scratch image, destination
# framebuffer offset, width, height. Original 24CAF..24E18.
BORDERS=((0,18146,2,68),(3,18234,2,68),(12,17506,90,2),(381,39906,90,2),
         (6,41374,2,65),(9,41594,2,65),(750,40734,111,2),(1119,40845,111,2),
         (1488,62174,111,2),(1857,62285,111,2))


def building_lines(lines,identity):
    integer(identity,'Building description',minimum=1,maximum=25)
    if (not isinstance(lines,list) or not 150<=len(lines)<=156
            or any(not isinstance(line,str) or len(line)>255 for line in lines)
            or any(line.strip() for line in lines[150:])):
        raise GameError('Invalid building descriptions; extract the original content again.')
    return lines[(identity-1)*6:identity*6]


def building_description(lines,identity):
    record=building_lines(lines,identity)
    return {'title':record[0].strip(),'description':paragraphs(record[1:])}


def statistics(definition,raw,row=None):
    """2449D..24B1D: blueprint costs versus live production/staffing/power."""
    rule=building_rules(definition);category=rule['category']
    if not 0<=category<len(ROWS):raise GameError('Unknown building information category.')
    production,workers,energy=ROWS[category]
    result={0:f"Cost       : {definition['price']}" if row is None else
              'Status     : '+('Active' if row[8] else 'Passive')}
    if production>0:
        if row is None:
            value='mine' if category in (2,9) else f"{rule['output']} kwh"
        elif not row[8]:value='NONE'
        elif category==2:value=f'{raw[59]//10} t/ptp' if raw[59]>=10 else 'NONE'
        else:value=f"{(rule['output']*row[7]//100)*row[13]//100} kwh"
        result[production]='Production : '+value
    if workers>0:
        if row is None:value=str(rule['workers'])
        else:value=f"{struct.unpack_from('<H',bytes(row),9)[0] if row[8] else 0}/{rule['workers']}"
        result[workers]='Workers    : '+value
    if energy>0:
        value=rule['power'] if row is None else struct.unpack_from('<H',bytes(row),11)[0] if row[8] else 0
        result[energy]=f'Energy     : {value} kwh'
    if row is not None:result[max(0,*ROWS[category])+1]=f'Working    : {row[13] if row[8] else 0}%'
    return sorted(result.items())


def draw(renderer,target,state,view,definition):
    raw=state['worlds'][view.world_id]['raw']
    row=state['buildings'][view.inspected] if view.inspected is not None else None
    target.fill((93,53,224,144),(0,0,0))
    for source,destination,width,height in BORDERS:
        target.blit(renderer.asset('DESIGNER'),destination%320,destination//320,
                    source=(94+source%123,5+source//123,width,height))
    target.blit(renderer.path_asset(f"EPULET/EPULET{definition['id']}.PIC"),228,56,source=(2,2,86,68))
    renderer.text(target,definition['name'],117,59,columns=18)
    for slot,line in statistics(definition,raw,row):
        # Preserve complete values if imported staffing exceeds the narrow DOS
        # field: shorten padding/labels before the renderer applies its bound.
        if len(line)>21:
            label,value=line.split(': ',1)
            label={'Production':'Output','Workers':'Workers','Energy':'Power'}.get(label.strip(),label.strip())
            line=f'{label}: {value}'
        renderer.text(target,line,98,70+slot*9,columns=21)
    if row is not None and row[6]:renderer.text(target,f'Build time: {row[6]} h',98,115,columns=21)
    record=building_lines(renderer.content.text(TEXT_NAME),definition['id'])
    for i,line in enumerate(record):
        renderer.text(target,line,100,134 if i==0 else 139+i*9,columns=35)
