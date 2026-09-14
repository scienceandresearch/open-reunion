"""Original commander consultation replies, priority selection and RNG draws."""
import struct
from ..core import GameError,integer
from .catalog import DATA_FILE_OFFSET,pascal
from .commanders import ROLES
from .campaign import random_bounded

PHRASES={'research_none':0xE8AD,'research_first':0xE8CD,'research_second':0xE8E2,
         'production_none':0xE912,'production_first':0xE933,'production_first_end':0xE942,
         'production_second':0xE944,'production_second_end':0xE959}


def read_rules(data,text):
    rules={'priorities':[list(struct.unpack_from('<HH',data,DATA_FILE_OFFSET+0x64F0+4*i)) for i in range(9)],
           'questions':text('KERDES1.SP')[:4],
           'replies':[line[3:] for line in text('VALASZ1.SP')[1:6]],
           'reasons':[line.rstrip() for line in text('AJANLAS.SP')[:9]],
           'phrases':{key:pascal(data,offset,255) for key,offset in PHRASES.items()}}
    validate_rules(rules);return rules


def validate_rules(rules):
    if not isinstance(rules,dict) or set(rules)!={'priorities','questions','replies','reasons','phrases'}:
        raise GameError('Incomplete commander advice; extract the original content again.')
    def strings(values,count):
        if not isinstance(values,list) or len(values)!=count or any(not isinstance(s,str) or not 1<=len(s)<=255 for s in values):
            raise GameError('Invalid commander advice text.')
    for key,count in (('questions',4),('replies',5),('reasons',9)):strings(rules[key],count)
    if not isinstance(rules['phrases'],dict) or set(rules['phrases'])!=set(PHRASES):raise GameError('Invalid advice phrases.')
    strings(list(rules['phrases'].values()),8)
    if not isinstance(rules['priorities'],list) or len(rules['priorities'])!=9:raise GameError('Invalid advice priorities.')
    for row in rules['priorities']:
        if not isinstance(row,list) or len(row)!=2:raise GameError('Invalid advice priority row.')
        integer(row[0],'Commander role',minimum=1,maximum=4);integer(row[1],'Advice product',minimum=1,maximum=35)


def unavailable(state,role):
    if role not in ROLES:return 'Select a commander role.'
    if not state['ranks'][role]:return 'Hire this commander before consulting them.'
    if state['campaign']['training_role']==ROLES.index(role)+1:return 'This commander is at university.'
    if role=='developer' and state['campaign']['research_block_remaining']!=0:return 'The developer is unavailable during the research interruption.'
    return None


def recommendation(rules,products,role,completed):
    """E6B9..E72F: the last matching priority wins, regardless of stock."""
    result=None
    for index,(candidate,product) in enumerate(rules['priorities']):
        status=products[product-1]['research_state']
        if candidate==ROLES.index(role)+1 and (status==5 if completed else status in (1,2,3,4)):result=index
    return result


def consult(rules,products,definitions,role,question,seed):
    if role not in ROLES:raise GameError('Select a commander role.')
    integer(question,'Advice question',minimum=1,maximum=4)
    selected=None
    if question==1:
        seed,roll=random_bounded(seed,2);reply=2+roll
        answer=rules['replies'][reply-2]
    elif question==2:
        selected=recommendation(rules,products,role,False)
        seed,roll=random_bounded(seed,50)
        reply=4 if roll<10 else 5 if selected is not None else 6
        answer=rules['replies'][reply-2];selected=None
    else:
        completed=question==4;reply=8 if completed else 7
        selected=recommendation(rules,products,role,completed)
        kind='production' if completed else 'research';phrases=rules['phrases']
        if selected is None:answer=phrases[kind+'_none']
        else:
            seed,roll=random_bounded(seed,50);variant='first' if roll<25 else 'second'
            product=rules['priorities'][selected][1];name=definitions[product-1]['name']
            answer=phrases[kind+'_'+variant]+' '+name
            if completed:answer+=phrases[kind+'_'+variant+'_end']
            answer+='\n'+rules['reasons'][selected]
    return {'kind':'commander_advice','question':rules['questions'][question-1],
            'answer':answer,'reply_id':reply,
            'product_id':rules['priorities'][selected][1] if selected is not None else None},seed
