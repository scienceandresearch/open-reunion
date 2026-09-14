"""Recovered orbital survey, intelligence and colony-support deployment rules."""
from .campaign import schedule_idea


def can_deploy_survey(raw,available):
    """1DE9D..1DF0C: the carrier offer uses the same survey-support gate."""
    owner=raw[0] if raw[0]<128 else raw[0]-256
    return raw[8]==0 and (raw[6]==0 and raw[10]==0 or owner>=2) and available>0


def survey_landing(raw,identity,campaign,products):
    """1D8C7..1D93C: satellite loss on alien worlds, otherwise survey/finds."""
    from .navigation import surface_discoveries
    raw=list(raw);owner=raw[0] if raw[0]<128 else raw[0]-256
    if owner>1:return raw,False,[]
    raw[8]=1
    return raw,True,surface_discoveries(identity,campaign,products)


def can_deploy_spy_ship(raw,available):
    """1DF70..1DFCA: owner and survey progress use signed-byte comparisons."""
    owner=raw[0] if raw[0]<128 else raw[0]-256
    progress=raw[12] if raw[12]<128 else raw[12]-256
    return raw[9]==0 and owner>=2 and progress>=30 and available>0


def spy_landing(raw,identity,campaign,products,*,ship=False):
    """1D93D..1D9CF: spy support survives alien ownership; both run site finds."""
    from .navigation import surface_discoveries
    raw=list(raw);raw[9 if ship else 8]=1 if ship else 2
    return raw,surface_discoveries(identity,campaign,products)


def can_deploy_station(raw,available):
    """World-menu branch 0x1E024..0x1E094; survey is a signed byte."""
    return (raw[0]==0 and raw[6]==0 and raw[7]==0 and raw[10]==0
            and 10<=raw[12]<128 and available>0 and raw[3]!=0)


def can_deploy_solar(raw,available):
    """World-menu branch 0x1DFCA..0x1E024."""
    return raw[0]==1 and raw[6]!=0 and raw[11]<5 and available>0


def establish_station(raw,campaign,products,surface_rules):
    """0x1DA04: world changes and the conditional Control centre idea.

    Payload consumption and creation of structure 25 are caller operations.
    The second survey increment is deliberately not clamped in the original.
    """
    raw=list(raw)
    progress=(raw[12]+10)&255
    raw[12]=60 if 60<progress<128 else progress
    raw[0]=raw[10]=1
    terrain=raw[21]
    if (products[6]["research_state"]==0 and campaign["idea_timers"][6]==-1 and raw[2]!=0
            and 1<=terrain<=11 and surface_rules["editable"][surface_rules["groups"][terrain-1]-1]):
        schedule_idea(campaign,products,7,20,40)
        raw[12]=(raw[12]+10)&255
        return raw,[4]
    return raw,[]
