"""Original planet deployment offers, shared by rendered icons and input."""
from .colony import can_change_tax
from .colony_screen import settlement_offered
from .fleets import payload_count
from .mining_screen import mining_available
from .orbital import can_deploy_survey,can_deploy_spy_ship,can_deploy_solar,can_deploy_station

DEPLOY_ACTIONS={70:'launch_satellite',20:'deploy_survey_satellite',67:'deploy_spy_satellite',
                68:'deploy_spy_ship',69:'deploy_solar_satellite',10:'deploy_station'}


def deployment_buttons(state,catalog,world_id):
    raw=state['worlds'][world_id]['raw'];identity=tuple(map(int,world_id.split(':')))
    buttons=[]
    home=identity[:2]==(1,5)
    if (not state['campaign']['carrier_failure_reported'] or home) and can_deploy_survey(raw,state['products'][2]['stock']):
        buttons.append(70)
    for button,kind,gate in ((20,'survey_satellite',can_deploy_survey),(67,'spy_satellite',can_deploy_survey),
                             (68,'spy_ship',can_deploy_spy_ship),(69,'solar_satellite',can_deploy_solar),
                             (10,'miner_station',can_deploy_station)):
        if button==20 and 70 in buttons:continue
        if gate(raw,payload_count(state['fleets'],identity,kind)):buttons.append(button)
    if settlement_offered(state,catalog,world_id):buttons.append(5)
    return buttons


def planet_buttons(state,catalog,world_id):
    raw=state['worlds'][world_id]['raw']
    buttons=[24,46,41]+([38,39] if can_change_tax(raw) else [])
    if mining_available(state,world_id):buttons.append(8)
    return buttons+deployment_buttons(state,catalog,world_id)


def action_signature(state,world_id):
    """A held icon must not change meaning after inventory or settlement edits."""
    return (world_id,tuple(state['worlds'][world_id]['raw']),
            tuple(tuple(r) for r in state['fleets']['moving']),len(state['fleets']['local']),
            tuple((r['stock'],r['research_state']) for r in state['products']),
            state['resources']['credits'],state['levels']['builder'],state['ranks']['builder'],
            len(state['deployments']),state['campaign']['carrier_failure_reported'])
