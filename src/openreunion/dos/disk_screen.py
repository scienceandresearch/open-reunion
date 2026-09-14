"""Original Disk Operations sound buttons and status indicator sprites."""
from ..core import integer

BUTTONS=((273,155,16,13),(290,155,16,13),(273,169,34,13),(273,183,34,13))
LABELS=('Music 1','Music 2','Stop music','Effects on/off')
INDICATORS=((181,63,30,10),(180,74,33,10),(252,64,47,6),
            (252,75,32,6),(288,75,3,6),(294,75,5,6))
PRESS_RECTS=((0,0,18,15),(18,0,18,15),(0,15,36,14),(0,29,36,14))


def targets():
    return [(rect,label,('disk_audio',index)) for index,(rect,label) in enumerate(zip(BUTTONS,LABELS),1)]


def select_audio(slot,main,effects,*,backend=1,effects_supported=True):
    """F008..F0B7; original effects modes 1=off, 2=on, 0=unavailable."""
    integer(main,'Main music',maximum=2);integer(effects,'Effects mode',maximum=2)
    if backend>0 and slot in (21,22,23):main={21:1,22:2,23:0}[slot]
    elif slot==24 and effects_supported and effects>0:effects=3-effects
    return main,effects


def indicator_copies(main,effects,*,backend=1):
    active=(backend>0 and main>0,backend>0 and main==0,effects==2,
            backend>0,backend>0 and main==1,backend>0 and main==2)
    return tuple(('DISKBR' if enabled else 'DISK',
                  (x-137,y-39,w,h) if enabled else (x,y,w,h),(x,y+49))
                 for (x,y,w,h),enabled in zip(INDICATORS,active))


def pressed_copy(button):
    integer(button,'Disk audio button',minimum=1,maximum=4)
    x,y,w,h=PRESS_RECTS[button-1]
    return 'DISKBR',(x,y+21,w,h),(272+x,154+y)


def draw(renderer,state,audio,effects,caption,pressed=0):
    target=renderer.frame(state,'DISK',12,0,caption)
    main=audio['main'] if audio else 1
    for name,source,(x,y) in indicator_copies(main,2 if effects is None or effects['enabled'] else 1):
        target.blit(renderer.asset(name),x,y,source=source)
    if pressed:
        name,source,(x,y)=pressed_copy(pressed);target.blit(renderer.asset(name),x,y,source=source)
    return target
