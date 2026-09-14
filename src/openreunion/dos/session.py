"""Transactional recovered strategy state and independently timed battle commands.

DOS input is read-only. Its unrecovered state is never written back after ticking.
This schema intentionally cannot be mistaken for a complete game save.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shlex
import struct

from ..core import GameError, integer
from ..legacy import LegacySave, RESOURCE_OFFSETS
from ..persistence import MAX_SAVE_BYTES, _unique_object, atomic_write
from .catalog import ORE_KEYS, PRODUCT_SAVE_OFFSET, SUBJECTS, read_products
from .rules import calendar_tick, production_tick, research_tick
from .campaign import (discovery_tick, imported_campaign,
                       random_bounded, research_completed, schedule_idea, survey_step)
from .savefile import SaveBlocks
from .worlds import read_world_state,world_message_label
from .colony import allocate_colony, colony_day, industrial_output
from .fleets import read_fleets,validate_fleets,storage_limit,update_capacity,local_record,payload_count,consume_payload,roster_layout
from .orbital import can_deploy_station,can_deploy_solar,establish_station
from .equipment import new_fleet,equipment_step,rename_fleet,EquipmentTransferLimit
from .cargo import cargo_capacity,cargo_used,transfer_ore,transfer_item,ore_transfer_limit,item_transfer_limit
from .navigation import depart,advance_fleet,orbit_toggle,ship_count,interstellar_capable
from .commanders import ROLES,COURSES,commander_hour,training_available,training_quote,training_purchase
from .industry import construction_step,derrick_step,mine_step,world_stocks,set_world_stocks
from .surface import building_available,new_building,occupancy,placement_fits,place_unpositioned
from .settlement import (read_deployments,validate_deployments,can_settle,start_settlement,
                         activate_bundle,settlement_population,deployment_step)
from .strategy import relations,navigation_view,commit_navigation,campaign_work,commit_campaign_work

SCHEMA = "recovered-strategy-v23"
PRODUCT_FIELDS = ("research_state", "research_remaining", "stock", "queued", "work_remaining")
NOTICE = "Story, bar conversations and missions, economy, colonies, travel, training and battles are active. Full campaign verification and original presentation remain unfinished. Older modern saves may need DOS reimport for missing bar records."


def validate(state, catalog):
    expected = {"schema", "executable_sha256", "source_save_sha256", "date", "resources", "products",
                "levels", "ranks", "skills", "workforce", "research_paused", "assisted", "log",
                "campaign","worlds","buildings","known_systems","events","fleets","deployments",
                "ground_encounter","space_encounter","campaign_phase","presentation_requests","battle_requests","active_dialog","active_scene"}
    if not isinstance(state, dict) or set(state) != expected or state["schema"] != SCHEMA:
        raise GameError("Unsupported recovered-session schema. Earlier sessions omit complete civilization and story records; reimport the DOS save with this version.")
    if state["executable_sha256"] != catalog["sha256"]:
        raise GameError("This session uses a different executable catalog.")
    digest = state["source_save_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise GameError("Invalid source-save hash.")
    date = state["date"]
    if not isinstance(date, list) or len(date) != 4:
        raise GameError("Invalid DOS calendar.")
    for name, value, minimum, maximum in zip(("year","month","day","hour"),date,(1,1,1,0),(65535,12,30,23)):
        integer(value,name,minimum=minimum,maximum=maximum)
    for field, keys, maximum in (("resources",RESOURCE_OFFSETS,2**32-1),("levels",ROLES,90),
                                  ("ranks",ROLES,3),("skills",SUBJECTS,255)):
        if not isinstance(state[field],dict) or set(state[field]) != set(keys):
            raise GameError(f"Invalid {field} fields.")
        for key,value in state[field].items():
            integer(value,key,maximum=maximum)
    integer(state["workforce"],"Workforce",minimum=1,maximum=32767)
    if type(state["research_paused"]) is not bool or type(state["assisted"]) is not bool:
        raise GameError("Invalid session flags.")
    rows = state["products"]
    if not isinstance(rows,list) or len(rows) != 35:
        raise GameError("Exactly 35 products are required.")
    active = 0
    for row,definition in zip(rows,catalog["products"]):
        if not isinstance(row,dict) or set(row) != set(PRODUCT_FIELDS):
            raise GameError("Invalid product state fields.")
        for key,value in row.items():
            integer(value,key,maximum=5 if key=="research_state" else 10000 if key=="research_remaining" else 32767)
        active += row["research_state"] in (2,4)
        if row["stock"]+row["queued"] > 32767:
            raise GameError("Stock plus pending production would overflow the DOS inventory field.")
        if row["research_state"] in (2,4) and definition["research_duration"] <= 0:
            raise GameError("Active research must have a positive duration.")
    if active > 1:
        raise GameError("The original research selector allows one active project.")
    if not isinstance(state["log"],list) or len(state["log"]) > 500 or any(not isinstance(s,str) or len(s)>500 for s in state["log"]):
        raise GameError("Invalid session log.")
    from .campaign import validate_campaign
    validate_campaign(state["campaign"])
    bar=state["campaign"]["bar"]
    if bar is not None and bar["conversation"] is not None:
        from .bar_dialogs import validate_conversation
        if "bar_dialogs" not in catalog:raise GameError("Bar dialogue content is missing; re-extract the data.")
        validate_conversation(bar["conversation"],campaign_work(state),catalog["bar_dialogs"])
        if state["active_dialog"] is not None or state['active_scene'] is not None or state["campaign_phase"]!="starmap" or any(
            isinstance(state[key],dict) and state[key].get("phase")!="closed" for key in ("ground_encounter","space_encounter")):
            raise GameError("Bar conversation conflicts with the active campaign encounter.")
    if state["campaign_phase"] not in ("starmap","defeat","victory"):
        raise GameError("Invalid campaign phase.")
    if not isinstance(state["presentation_requests"],list) or len(state["presentation_requests"])>500:
        raise GameError("Invalid presentation request queue.")
    for request in state["presentation_requests"]:
        if not isinstance(request,dict) or set(request) not in ({"kind","id"},{"kind","id","report"}) or request["kind"] not in ("message","scene","civilization_destroyed","dialog","report"):
            raise GameError("Invalid campaign presentation request.")
        integer(request["id"],"Presentation ID",minimum=2 if request["kind"] in ("civilization_destroyed","dialog") else 1,
                maximum={"message":49,"scene":10,"civilization_destroyed":12,"dialog":10,"report":10}[request["kind"]])
        from .mission_messages import validate_report
        validate_report(request)
    if state['active_scene'] is not None:
        from .scene_playback import validate_scene
        from .scene_dispatch import scene_notice
        scene=state['active_scene']
        if not isinstance(scene,dict) or set(scene)!={'playback','notice','dialog'}:raise GameError('Invalid active cinematic.')
        validate_scene(scene['playback'],catalog.get('story_cinema'))
        playback=scene['playback']
        if playback['controller']['rng']!=state['campaign']['rng']:raise GameError('Cinematic RNG disagrees with the campaign.')
        if scene['dialog'] is not None:
            integer(scene['dialog'],'Deferred conversation',minimum=6,maximum=6)
            if playback['scene']!=10 or state['campaign_phase']!='starmap' or '6' not in catalog.get('dialogs',{}):
                raise GameError('Invalid cinematic conversation continuation.')
        if scene['notice'] is not None:
            integer(scene['notice'],'Scene notice',minimum=1,maximum=49)
            if scene['notice']!=scene_notice(playback['scene']) or playback['ticks']!=0:
                raise GameError('Invalid pending cinematic notice.')
        if state['active_dialog'] is not None or any((state[k] or {}).get('phase','closed')!='closed' for k in ('space_encounter','ground_encounter')):
            raise GameError('A cinematic conflicts with another encounter.')
    if state["active_dialog"] is not None:
        from .dialogs import validate_dialog_state
        current=state["active_dialog"]
        if not isinstance(current,dict):raise GameError("Invalid active conversation.")
        definition=catalog.get("dialogs",{}).get(str(current.get("script")))
        if definition is None:raise GameError("Conversation text is missing; re-extract the content.")
        validate_dialog_state(definition,current)
        if state["campaign_phase"]!="starmap":raise GameError("A terminal campaign has an active conversation.")
        if any(isinstance(state[k],dict) and state[k].get("phase")!="closed" for k in ("space_encounter","ground_encounter")):
            raise GameError("A conversation and battle cannot run simultaneously.")
    active=state["campaign"]["training_role"]
    training=state["campaign"]["training"]
    if active and (not state["ranks"][ROLES[active-1]] or (active==4 and not training["course"])):
        raise GameError("Active training needs a hired commander and a valid developer course.")
    if training["quote"] is not None and (active or state["ranks"][training["quote"]["role"]]!=training["quote"]["rank"]):
        raise GameError("Training quote no longer matches the hired commander or university availability.")
    if not isinstance(state["worlds"],dict) or set(state["worlds"])!={w["id"] for w in catalog.get("worlds",[])}:
        raise GameError("Incomplete world state.")
    for record in state["worlds"].values():
        if not isinstance(record,dict) or set(record)!={"raw"} or not isinstance(record["raw"],list) or len(record["raw"])!=65:
            raise GameError("Invalid world record.")
        for byte in record["raw"]:
            integer(byte,"World byte",maximum=255)
    if not isinstance(state["buildings"],list) or len(state["buildings"])>1000:
        raise GameError("Invalid building collection.")
    for record in state["buildings"]:
        if not isinstance(record,list) or len(record)!=14:
            raise GameError("Invalid saved building.")
        for byte in record:
            integer(byte,"Building byte",maximum=255)
    validate_fleets(state["fleets"],local_limit=32+len(state["worlds"]))
    validate_deployments(state["deployments"])
    for key in ("space_encounter","ground_encounter"):
        if state[key] is not None and not isinstance(state[key],dict):raise GameError("Invalid campaign encounter.")
    from .battle_queue import validate_battle_requests
    validate_battle_requests(state)
    from .space_validation import validate_space_encounter
    validate_space_encounter(state["space_encounter"],state,(catalog.get("battle_rules") or {}).get("space"),catalog.get("space_cinema"))
    from .ground_validation import validate_ground_encounter
    validate_ground_encounter(state["ground_encounter"],state["worlds"],catalog.get("battle_rules"),state["campaign"]["rng"])
    encounter=state["ground_encounter"]
    if encounter is not None and encounter["phase"]!="closed" and state["campaign_phase"]!="starmap":
        raise GameError("A terminal campaign cannot have an active ground battle.")
    if encounter is not None and encounter["phase"] in ("setup","fighting"):
        from .ground_setup import build_ground_setup
        original=build_ground_setup(state["fleets"],state["campaign"]["civilizations"],state["worlds"],encounter["destination"],catalog["battle_rules"]["ground_setup"])
        for side in ("friendly","hostile"):
            for field in ("totals","primary","secondary"):
                key=side+"_"+field
                if encounter["battle"][key]!=original[key]:raise GameError("Battle force pools disagree with campaign records.")
    if encounter is not None and encounter["battle"].get("instant_kill",False) and not state["assisted"]:
        raise GameError("An instant battle victory requires an assisted campaign.")
    identities={tuple(w[key] for key in ("system","planet","moon")) for w in catalog.get("worlds",[])}
    if any(tuple(row[1:4]) not in identities for row in state["deployments"]):
        raise GameError("A colony deployment refers to an unknown world.")
    if not isinstance(state["known_systems"],list) or len(state["known_systems"])!=8:
        raise GameError("Invalid system discovery state.")
    for byte in state["known_systems"]:
        integer(byte,"System discovery byte",maximum=255)
    if not isinstance(state["events"],list) or len(state["events"])>500:
        raise GameError("Invalid campaign event log.")
    for event in state["events"]:
        if not isinstance(event,dict) or set(event) not in ({"kind","id","date"},{"kind","id","date","report"}) or event["kind"] not in ("message","idea","report"):
            raise GameError("Invalid campaign event.")
        integer(event["id"],"Event ID",minimum=1,maximum={"message":49,"idea":35,"report":10}[event["kind"]])
        from .mission_messages import validate_report
        validate_report(event)
        if not isinstance(event["date"],list) or len(event["date"])!=4:
            raise GameError("Invalid event date.")
        for value,minimum,maximum in zip(event["date"],(1,1,1,0),(65535,12,30,23)):
            integer(value,"Event date",minimum=minimum,maximum=maximum)
    from .mission_messages import report_size,REPORT_BUDGET
    if any(report_size(state[key])>REPORT_BUDGET for key in ('events','presentation_requests')):
        raise GameError('Mission report history exceeds its size limit.')


class RecoveredSession:
    def __init__(self,catalog,state,*,admin_enabled=False,hero=2):
        from .hero import validate_hero
        validate_hero(hero)
        self.hero=hero
        self.catalog = deepcopy(catalog)
        validate(state,self.catalog)
        self.state = deepcopy(state)
        self.admin_enabled = admin_enabled
        # Runtime UI invalidation only; never saved or included in gameplay RNG.
        self.fleet_revision = 0
        # Presentation has its own sample clock and is excluded from gameplay
        # transactions/RNG. It is stored in the same atomic JSON save.
        self.audio = None
        self.effects = None
        from .result_animation import initial_animation
        self.result_animation=initial_animation(state)
        self.effect_revision = 0
        # Runtime notification for consecutive conversations on the same
        # screen. Loading restores the saved audio directly, so this is not
        # campaign data or an additional persisted clock.
        self.dialog_revision = 0
        self.scene_revision = 0

    @classmethod
    def from_dos(cls,catalog,path):
        return cls._from_legacy(catalog,LegacySave.read(path))

    @classmethod
    def _from_legacy(cls,catalog,saved,*,hero=None):
        products = read_products(saved.data,PRODUCT_SAVE_OFFSET)
        # Static rule changes in a save cannot silently inherit executable rules.
        for product,definition in zip(products,catalog["products"]):
            observed = product.to_dict()
            if product.id == 35 and observed["name"] == "Energy Ihield":
                # Observed in supplied saves 5..7; recover only the known label,
                # using the intact executable record. No original bytes change.
                observed["name"] = "Energy shield"
            if any(observed[key] != definition[key] for key in observed if key not in PRODUCT_FIELDS):
                raise GameError(f"Save changes static fields for {product.name}; this variant needs a separate profile.")
        words = lambda offset: struct.unpack_from("<4H",saved.data,offset)
        worlds,buildings=read_world_state(saved.data,catalog)
        state = {"schema":SCHEMA,"executable_sha256":catalog["sha256"],
                 "source_save_sha256":hashlib.sha256(saved.data).hexdigest(),
                 "date":list(words(0x38A8)),"resources":saved.resources(),
                 "products":[{key:p.to_dict()[key] for key in PRODUCT_FIELDS} for p in products],
                 "levels":dict(zip(ROLES,words(0x3872))),"skills":dict(zip(SUBJECTS,words(0x387A))),
                 "ranks":dict(zip(ROLES,words(0x3884))),
                 "workforce":struct.unpack_from("<H",saved.data,0x3882)[0],
                 "research_paused":False,"assisted":False,"log":[f"Imported recovered state from {saved.name}.",NOTICE,
                    "The original save omits its random seed; this import starts reproducibly at seed 1994."],
                 "campaign":imported_campaign(saved.data),"worlds":worlds,"buildings":buildings,
                 "known_systems":list(SaveBlocks(saved.data).read(0x4816,8)),"events":[],"fleets":read_fleets(saved.data),
                 "deployments":read_deployments(saved.data),"ground_encounter":None,"space_encounter":None,
                 "campaign_phase":"starmap","presentation_requests":[],"battle_requests":[],"active_dialog":None,"active_scene":None}
        if products[-1].name == "Energy Ihield":
            state["log"].append("Restored the damaged Energy shield display label from the executable catalog; original save unchanged.")
        return cls(catalog,state,hero=SaveBlocks(saved.data).number(0x9276) if hero is None else hero)

    def apply(self,action,**arguments):
        handlers = {"advance":self._advance,"research":self._research,"order":self._order,
                    "hire":self._hire,"pause_research":self._pause_research,"admin":self._admin,
                    "launch_satellite":self._launch_satellite,"assign_droid":self._assign_droid,"set_tax":self._set_tax,
                    "build":self._build,"demolish":self._demolish,"colonize":self._colonize,"prepare_surface":self._prepare_surface,
                    "deploy_station":self._deploy_station,"deploy_solar_satellite":self._deploy_solar_satellite,
                    "deploy_survey_satellite":self._deploy_survey_satellite,
                    "deploy_spy_satellite":self._deploy_spy_satellite,"deploy_spy_ship":self._deploy_spy_ship,
                    "create_fleet":self._create_fleet,"equip_fleet":self._equip_fleet,"transfer_cargo":self._transfer_cargo,
                    "rename_fleet":self._rename_fleet,"disband_fleet":self._disband_fleet,
                    "travel":self._travel,"orbit":self._orbit,"attack":self._attack,
                    "quote_training":self._quote_training,"train":self._train,
                    "consult_commander":self._consult_commander,
                    "ground_edit":self._ground_edit,"ground_start":self._ground_start,"ground_cancel":self._ground_cancel,
                    "ground_command":self._ground_command,"ground_tick":self._ground_tick,
                    "space_tick":self._space_tick,"space_retreat":self._space_retreat,"space_acknowledge":self._space_acknowledge,
                    "ground_acknowledge":self._ground_acknowledge,"dismiss_presentation":self._dismiss_presentation,
                    "dialog_answer":self._dialog_answer,"dialog_acknowledge":self._dialog_acknowledge,
                    "scene_tick":self._scene_tick,"scene_acknowledge":self._scene_acknowledge,"start_presentation":self._start_pending_dialog,
                    "bar_talk":self._bar_talk,"bar_answer":self._bar_answer,"bar_acknowledge":self._bar_acknowledge,"bar_leave":self._bar_leave}
        if action not in handlers:
            raise GameError("Unknown recovered-system action.")
        if self.state['presentation_requests'] and self.state['active_dialog'] is None and self.state['active_scene'] is None and not any(
                (self.state[k] or {}).get('phase','closed')!='closed' for k in ('space_encounter','ground_encounter')) and action not in (
                'start_presentation','dismiss_presentation','advance','admin'):
            raise GameError('Acknowledge the pending presentation before changing the campaign.')
        if self.state['active_scene'] is not None and action not in ('scene_tick','scene_acknowledge','admin'):
            raise GameError('Finish the active cinematic before changing the campaign.')
        if self.state["active_dialog"] is not None and action not in ("dialog_answer","dialog_acknowledge","admin"):
            raise GameError("Finish the active conversation before changing the campaign.")
        if (self.state["campaign"]["bar"] or {}).get("conversation") is not None and action not in ("bar_answer","bar_acknowledge","bar_leave","admin"):
            raise GameError("Finish or leave the bar conversation before changing the campaign.")
        active=(self.state["ground_encounter"] or {}).get("phase","closed")!="closed"
        if active and not action.startswith("ground_") and action!="admin":
            raise GameError("Finish the active ground battle before changing the campaign.")
        active=(self.state["space_encounter"] or {}).get("phase","closed")!="closed"
        if active and not action.startswith("space_") and action!="admin":
            raise GameError("Finish the active space battle before changing the campaign.")
        if (self.defeated() or self.state["campaign_phase"]=="victory") and action not in ("admin","dismiss_presentation","scene_tick","scene_acknowledge","start_presentation"):
            raise GameError("The campaign has ended. Import or load an ongoing campaign to continue.")
        candidate = deepcopy(self.state)
        events=handlers[action](candidate,**arguments)
        candidate["log"] = candidate["log"][-500:]
        candidate["events"] = candidate["events"][-500:]
        from .mission_messages import report_size,REPORT_BUDGET
        while report_size(candidate['events'])>REPORT_BUDGET:candidate['events'].pop(0)
        validate(candidate,self.catalog)
        from .effect_control import scene_effects
        from .battle_samples import battle_effect_requests
        effect_events=(events or []) if action=='scene_tick' else battle_effect_requests(action,events or [])
        effects,requests=scene_effects(self.effects,effect_events)
        from .result_animation import stage_animation
        animation=stage_animation(self.result_animation,self.state,candidate)
        previous_scene=self.state['active_scene']
        if candidate['active_scene'] is not None and (previous_scene is None or
                action=='scene_acknowledge' and previous_scene['notice'] is None and previous_scene['playback']['phase']=='done'):
            self.scene_revision+=1
        if roster_layout(self.state["fleets"]) != roster_layout(candidate["fleets"]):
            self.fleet_revision += 1
        self.state = candidate
        self.result_animation=animation
        self.effects=effects;self.effect_revision+=requests
        if action=="dialog_acknowledge":self.dialog_revision+=1
        return events or []

    def defeated(self,state=None):
        state=self.state if state is None else state
        home=state["worlds"].get("1:5:0")
        return state["campaign_phase"]=="defeat" or home is not None and (home["raw"][0]!=1 or not home["raw"][6])

    def _product(self,state,product_id):
        integer(product_id,"Product ID",minimum=1,maximum=35)
        return state["products"][product_id-1],self.catalog["products"][product_id-1]

    def begin_ground_battle(self,destination,*,player_attacking,conquering_owner=None,search_ruins=False):
        """Battle-request dispatcher entry; combat eligibility belongs to the caller.

        This does not expose a player command that bypasses a space encounter.
        The UI request dispatcher will call it after accepting a ground request.
        """
        from .ground_encounter import open_ground_encounter
        if self.defeated() or self.state["campaign_phase"]=="victory":raise GameError("The campaign has ended.")
        if (self.state["space_encounter"] or {}).get("phase","closed")!="closed":
            raise GameError("Finish the active space battle first.")
        rules=self._battle_rules();candidate=deepcopy(self.state)
        work=open_ground_encounter(campaign_work(candidate),destination,rules["ground_setup"],
            player_attacking=player_attacking,conquering_owner=conquering_owner,search_ruins=search_ruins)
        commit_campaign_work(candidate,work);validate(candidate,self.catalog)
        from .result_animation import stage_animation
        animation=stage_animation(self.result_animation,self.state,candidate)
        self.state=candidate;self.result_animation=animation

    def begin_space_battle(self,destination,*,player_attacking,ground_requested=False,
                           conquering_owner=None,search_ruins=False):
        """Dispatcher entry after strategic eligibility has been established."""
        from .space_encounter import open_space_encounter
        from .space_validation import validate_space_rules
        if self.defeated() or self.state["campaign_phase"]=="victory":raise GameError("The campaign has ended.")
        rules=self._battle_rules()["space"];validate_space_rules(rules)
        candidate=deepcopy(self.state)
        work=open_space_encounter(campaign_work(candidate),destination,candidate["levels"]["fighter"],rules,
            player_attacking=player_attacking,ground_requested=ground_requested,
            conquering_owner=conquering_owner,search_ruins=search_ruins,cinema_rules=self.catalog.get("space_cinema"))
        commit_campaign_work(candidate,work);validate(candidate,self.catalog)
        from .result_animation import stage_animation
        animation=stage_animation(self.result_animation,self.state,candidate)
        self.state=candidate;self.result_animation=animation

    def _attack(self,state,fleet_index,target_race=None,target_slot=None):
        from .battle_dispatch import player_attack_request
        from .space_encounter import open_space_encounter
        request=player_attack_request(state,fleet_index,target_race=target_race,target_slot=target_slot)
        work=campaign_work(state)
        work["civilizations"][request["hostile_race"]-2][27]=2
        work=open_space_encounter(work,request["destination"],state["levels"]["fighter"],self._battle_rules()["space"],
            player_attacking=True,ground_requested=request["ground_requested"],cinema_rules=self.catalog.get("space_cinema"))
        commit_campaign_work(state,work)
        state["log"].append("Attack ordered at "+":".join(map(str,request["destination"]))+".")
        return [{"kind":"space_battle_requested"}]

    def _space_tick(self,state,frames=1,render=False):
        from .space_encounter import tick_space_encounter
        integer(frames,"Battle frames",minimum=1,maximum=120)
        if type(render) is not bool:raise GameError("Invalid space rendering request.")
        work=campaign_work(state);events=[]
        for _ in range(frames):
            calls=[] if render else None
            work,requested=tick_space_encounter(work,self._battle_rules()["space"],render_calls=calls,cinema_rules=self.catalog.get("space_cinema"))
            if render and work["space_encounter"]["battle"]["frame"]==1:
                events.append({"kind":"space_frame","calls":calls})
            events.extend(requested)
            if work["space_encounter"]["phase"]=="result":break
        commit_campaign_work(state,work);return events

    def _space_retreat(self,state):
        from .space_encounter import retreat_space_encounter
        work,events=retreat_space_encounter(campaign_work(state))
        commit_campaign_work(state,work);return events

    def _space_acknowledge(self,state):
        from .space_encounter import acknowledge_space_result
        work,phase,events=acknowledge_space_result(campaign_work(state),self._battle_rules()["ground_setup"])
        commit_campaign_work(state,work)
        for kind,event_id in events:
            if kind=="message":self._event(state,kind,event_id)
            state["presentation_requests"].append({"kind":kind,"id":event_id})
        self._dispatch_battles(state)
        return events

    def _battle_rules(self):
        rules=self.catalog.get("battle_rules")
        if rules is None:raise GameError("Battle tables are missing; re-extract the original content.")
        return rules

    def _ground_edit(self,state,operation,selection,amount=1):
        from .ground_encounter import edit_ground_encounter
        work=edit_ground_encounter(campaign_work(state),self._battle_rules()["ground_setup"],operation,selection,amount=amount)
        commit_campaign_work(state,work)

    def _ground_start(self,state):
        from .ground_encounter import start_ground_encounter
        commit_campaign_work(state,start_ground_encounter(campaign_work(state),self._battle_rules()["ground_motion"]))

    def _ground_cancel(self,state):
        from .ground_encounter import cancel_ground_encounter
        commit_campaign_work(state,cancel_ground_encounter(campaign_work(state)))
        state['campaign_phase']='starmap'
        self._dispatch_battles(state)

    def _ground_command(self,state,command,x=None,y=None):
        from .ground_encounter import command_ground_encounter
        rules=self._battle_rules()
        work,events=command_ground_encounter(campaign_work(state),rules["ground_motion"],rules["ground_controls"],command,x=x,y=y)
        commit_campaign_work(state,work);return events

    def _ground_tick(self,state,frames=1):
        from .ground_encounter import tick_ground_encounter
        integer(frames,"Battle frames",minimum=1,maximum=120)
        rules=self._battle_rules();work=campaign_work(state);events=[]
        for _ in range(frames):
            work,requested=tick_ground_encounter(work,rules["ground_motion"],rules["ground_attacks"],rules["ground_movement"])
            events.extend(requested)
            if work["ground_encounter"]["phase"]=="result":break
        commit_campaign_work(state,work);return events

    def _ground_acknowledge(self,state):
        from .ground_encounter import acknowledge_ground_result
        work,phase,events=acknowledge_ground_result(campaign_work(state),self.catalog,self._battle_rules()["aliens"])
        commit_campaign_work(state,work);state["campaign_phase"]=phase
        for kind,event_id in events:
            if kind=="message":self._event(state,kind,event_id)
            state["presentation_requests"].append({"kind":kind,"id":event_id})
        self._dispatch_battles(state)
        return events

    def _dismiss_presentation(self,state):
        if not state["presentation_requests"]:raise GameError("No presentation request is pending.")
        if state["presentation_requests"][0]["kind"] in ('dialog','scene'):raise GameError("Play the pending presentation before continuing.")
        state["presentation_requests"].pop(0)
        self._start_pending_dialog(state);self._dispatch_battles(state)

    def _start_pending_dialog(self,state):
        # Retain request order; DOS's shared request globals could overwrite
        # earlier scenes. A queued notice must be acknowledged before passing it.
        if state['active_dialog'] is not None or state['active_scene'] is not None:return
        if (state['campaign']['bar'] or {}).get('conversation') is not None:return
        if any((state[k] or {}).get('phase','closed')!='closed' for k in ('space_encounter','ground_encounter')):return
        if not state['presentation_requests']:return
        request=state['presentation_requests'][0]
        if request['kind']=='scene':
            self._begin_scene(state,request['id']);state['presentation_requests'].pop(0)
        elif request['kind']=='dialog':
            from .scene_dispatch import dialog_scene
            if state['campaign_phase']!='starmap':return
            if str(request['id']) not in self.catalog.get('dialogs',{}):raise GameError('Conversation text is missing; re-extract the content.')
            intro=dialog_scene(request['id'])
            if intro is not None:self._begin_scene(state,intro,dialog=request['id'])
            else:self._begin_dialog(state,request['id'])
            state['presentation_requests'].pop(0)

    def _begin_dialog(self,state,script):
        from .dialogs import start_conversation
        state['active_dialog']=start_conversation(self.catalog['dialogs'][str(script)])

    def _begin_scene(self,state,scene,*,dialog=None):
        from .scene_playback import begin_scene
        from .scene_dispatch import scene_notice
        notice=scene_notice(scene)
        playback=begin_scene(scene,self.catalog.get('story_cinema'),state['campaign']['rng'])
        state['active_scene']={'playback':playback,'notice':notice,'dialog':dialog}
        if notice is not None:self._event(state,'message',notice)

    def _scene_tick(self,state,mouse=False,key=False):
        from .scene_playback import tick_scene
        current=state['active_scene']
        if current is None:raise GameError('No cinematic is active.')
        if current['notice'] is not None:raise GameError('Acknowledge the scene message before playback.')
        current['playback'],events=tick_scene(current['playback'],self.catalog['story_cinema'],mouse=mouse,key=key)
        state['campaign']['rng']=current['playback']['controller']['rng']
        return events

    def _scene_acknowledge(self,state):
        current=state['active_scene']
        if current is None:raise GameError('No cinematic is active.')
        if current['notice'] is not None:current['notice']=None;return
        if current['playback']['phase']!='done':raise GameError('The cinematic has not finished.')
        state['active_scene']=None
        if current['dialog'] is not None:self._begin_dialog(state,current['dialog'])
        else:self._start_pending_dialog(state)
        self._dispatch_battles(state)

    def _dialog_answer(self,state,question):
        from .dialogs import respond
        current=state["active_dialog"]
        if current is None:raise GameError("No conversation is active.")
        definition=self.catalog["dialogs"][str(current["script"])]
        updated,work,_=respond(definition,current,campaign_work(state),question)
        commit_campaign_work(state,work);state["active_dialog"]=updated

    def _dialog_acknowledge(self,state):
        from .dialogs import closing_messages
        current=state["active_dialog"]
        if current is None or not current["closed"]:raise GameError("Finish the conversation before continuing.")
        for message in closing_messages(current["script"],campaign_work(state)["flags"]):
            self._event(state,"message",message);state["presentation_requests"].append({"kind":"message","id":message})
        state["active_dialog"]=None;self._start_pending_dialog(state);self._dispatch_battles(state)

    def _story_hour(self,state):
        from .story import story_hour
        work,events=story_hour(campaign_work(state),(self.catalog.get("battle_rules") or {}).get("aliens"))
        commit_campaign_work(state,work)
        for kind,number in events:
            if kind=="message":self._event(state,kind,number)
            state["presentation_requests"].append({"kind":kind,"id":number})

    def _advance(self,state,hours):
        integer(hours,"Hours",minimum=1,maximum=240)
        if state['presentation_requests']:
            self._start_pending_dialog(state)
            return
        for _ in range(hours):
            state["date"] = calendar_tick(state["date"])
            campaign=state["campaign"]
            discovered,messages=discovery_tick(campaign,state["products"],state["levels"]["developer"])
            for product_id in discovered:
                self._event(state,"idea",product_id)
            for message in messages:
                self._event(state,"message",message)
            self._story_hour(state);campaign=state["campaign"]
            for row,definition in zip(state["products"],self.catalog["products"]):
                result = research_tick(row["research_state"],row["research_remaining"],definition["research_duration"],
                                       [definition["requirements"][key] for key in SUBJECTS],
                                       [state["skills"][key] for key in SUBJECTS],state["levels"]["developer"],
                                       blocked=state["research_paused"] or campaign["research_block_remaining"]!=0 or campaign["training_role"]==4)
                row["research_state"],row["research_remaining"] = result.state,result.remaining
                if result.completed:
                    state["log"].append(f"Research complete: {definition['name']}.")
                    for message in research_completed(campaign,state["products"],definition["id"]):
                        self._event(state,"message",message)
            for row,definition in zip(state["products"],self.catalog["products"]):
                result = production_tick(row["stock"],row["queued"],definition["base_work"],row["work_remaining"],state["workforce"])
                row.update(stock=result.stock,queued=result.queued,work_remaining=result.work_remaining)
                if result.completed:
                    state["log"].append(f"Manufactured: {definition['name']}.")
            if state["date"][3]==0:
                self._survey_day(state)
            completed=commander_hour(state["levels"],state["ranks"],state["skills"],campaign,self.catalog["training_rules"])
            if completed:
                state["log"].append(self.catalog["training_rules"]["completion_text"].strip("| ")+f" ({completed}).")
            self._industry_hour(state)
            self._fleet_hour(state)
            if self.defeated(state):
                state["log"].append("Campaign ended: New Earth has been lost.")
                break
            self._alien_hour(state)
            self._bar_hour(state)
            self._start_pending_dialog(state)
            self._dispatch_battles(state)
            if state["active_dialog"] is not None or state['active_scene'] is not None or state['presentation_requests'] or (state["space_encounter"] or {}).get("phase","closed")!="closed":
                state["log"].append("Hour advancement stopped for a presentation or alien attack.")
                break

    def _alien_hour(self,state):
        from .alien_movement import alien_hour
        work,events=alien_hour(campaign_work(state));commit_campaign_work(state,work)
        for kind,detail in events:
            if kind=="battle":state["battle_requests"].append(detail)
            elif kind in ("message","scene","dialog"):self._navigation_events(state,[(kind,detail)])
            else:
                name=self.catalog.get("alien_names",["Civilization"]*11)[detail["race"]-2]
                label=":".join(map(str,detail["world"]))
                state["log"].append(("First contact: " if kind=="contact" else "Hostile fleet arrival: ")+name+" at "+label+".")

    def _bar_hour(self,state):
        from .bar import bar_hour
        from .mission_messages import mission_text
        work,events=bar_hour(campaign_work(state));commit_campaign_work(state,work)
        message=None;request=None
        for kind,detail in events:
            if kind=="message":
                self._event(state,kind,detail);state["presentation_requests"].append({"kind":kind,"id":detail})
                message=state['events'][-1];request=state['presentation_requests'][-1]
            else:
                lines=mission_text(self.catalog,kind,detail)
                if kind=='pirate_announcement':
                    self._event(state,'report',detail)
                    state['presentation_requests'].append({'kind':'report','id':detail})
                    message=state['events'][-1];request=state['presentation_requests'][-1]
                    state['log'].append(' '.join(lines))
                else:state['log'].extend(lines)
                if message is None:raise GameError('A mission result lacks its completion message.')
                message.setdefault('report',[]).extend(lines)
                request.setdefault('report',[]).extend(lines)

    def _bar_rules(self):
        rules=self.catalog.get("bar_dialogs")
        if rules is None:raise GameError("Bar dialogue content is missing; re-extract the data.")
        return rules

    def _bar_talk(self,state,agent):
        from .bar_dialogs import open_conversation
        self._bar_rules();work=campaign_work(state)
        current=open_conversation(work,agent)
        state["campaign"]["bar"]["conversation"]=current

    def _bar_answer(self,state,question):
        from .bar_dialogs import choose
        work=campaign_work(state);current=(work["bar"] or {}).get("conversation")
        if current is None:raise GameError("No bar conversation is active.")
        work,current=choose(work,current,question,self._bar_rules())
        work["bar"]["conversation"]=current;commit_campaign_work(state,work)

    def _bar_acknowledge(self,state):
        from .bar_dialogs import acknowledge
        work=campaign_work(state);current=(work["bar"] or {}).get("conversation")
        if current is None:raise GameError("No bar answer is pending.")
        state["campaign"]["bar"]["conversation"]=acknowledge(work,current)

    def _bar_leave(self,state):
        if (state["campaign"]["bar"] or {}).get("conversation") is None:raise GameError("No bar conversation is active.")
        state["campaign"]["bar"]["conversation"]=None

    def _dispatch_battles(self,state):
        from .battle_queue import current_battle_request
        from .space_encounter import open_space_encounter
        self._start_pending_dialog(state)
        if self.defeated(state) or state["campaign_phase"]=="victory":
            state["battle_requests"]=[];return
        if state["active_dialog"] is not None or state['active_scene'] is not None or state['presentation_requests']:return
        if any((state[key] or {}).get("phase","closed")!="closed" for key in ("space_encounter","ground_encounter")):return
        while state["battle_requests"]:
            original=state["battle_requests"].pop(0)
            request=current_battle_request(state,original)
            if request is None:
                state["log"].append("Pending alien attack no longer has an attacker or a player target.")
                continue
            work=open_space_encounter(campaign_work(state),request["world"],state["levels"]["fighter"],self._battle_rules()["space"],
                player_attacking=False,ground_requested=request["ground"],conquering_owner=request["race"],
                cinema_rules=self.catalog.get("space_cinema"))
            commit_campaign_work(state,work)
            from .battle_identity import civilization_name,world_name
            state["log"].append(f"Under attack: {civilization_name(self.catalog,request['race'])} "
                                f"fleet {request['slot']} at {world_name(self.catalog,request['world'])}.")
            return

    @staticmethod
    def _event(state,kind,event_id):
        state["events"].append({"kind":kind,"id":event_id,"date":list(state["date"])})

    def _navigation_events(self,state,events):
        for kind,event_id in events:
            if kind=="message":self._event(state,kind,event_id)
            elif kind=="dialog":state["presentation_requests"].append({"kind":kind,"id":event_id})
            else:
                state["presentation_requests"].append({"kind":"scene","id":event_id})
                state["log"].append(f"Original scene {event_id} requested; scene presentation is pending.")

    def _fleet_hour(self,state):
        for row in state["fleets"]["moving"]:
            before=row[22];previous_contacts=relations(state["campaign"])
            view=navigation_view(state["campaign"])
            row[:],events=advance_fleet(row,view,state["products"],state["known_systems"],state["worlds"],state["levels"]["pilot"])
            commit_navigation(state["campaign"],view)
            self._navigation_events(state,events)
            if before in (4,5,6) and row[22]==2:
                label=bytes(row[2:2+min(row[1],17)]).decode("cp437")
                world=next((w for w in self.catalog["worlds"] if w["id"]==":".join(map(str,row[19:22]))),None)
                state["log"].append(f"{label} arrived in orbit at {world['name'] if world else 'the destination system'}.")
                for i,(old,new) in enumerate(zip(previous_contacts,relations(state["campaign"]))):
                    if old!=new:
                        name=self.catalog.get("alien_names",["Unknown civilization"]*11)[i]
                        state["log"].append(f"First contact: {name}.")

    def _travel(self,state,fleet_index,destination):
        integer(fleet_index,"Fleet index",maximum=len(state["fleets"]["moving"])-1)
        if not isinstance(destination,(list,tuple)) or len(destination)!=3:raise GameError("Select a destination.")
        for v,label,minimum in zip(destination,("System","Planet","Moon"),(1,0,0)):
            integer(v,label,minimum=minimum,maximum=8)
        row=state["fleets"]["moving"][fleet_index];system,planet,moon=destination
        if row[0] not in (1,2,3,4) or row[22] not in (2,4,5,6):raise GameError("Launch into orbit before selecting a route.")
        if ship_count(row,self.catalog)==0:raise GameError("Equip the fleet with ships first.")
        if state["levels"]["pilot"]==0 and row[0]!=4:raise GameError("Hire a pilot before traveling.")
        if state["known_systems"][system-1]>=128:raise GameError("This system is not available for navigation.")
        if planet==0:
            if moon:raise GameError("A system destination cannot have a moon.")
        elif (state["known_systems"][system-1]!=1 or f"{system}:{planet}:{moon}" not in state["worlds"]
              or state["campaign"]["navigation"]["planet_visibility"][8*(system-1)+planet-1]>=128):
            raise GameError("This world is not available for navigation.")
        if system!=row[19] and not interstellar_capable(row,state["products"],state["ranks"]["pilot"],system):
            raise GameError("This interstellar route needs suitable ships and a qualified pilot.")
        row[:],state["campaign"]["rng"]=depart(row,destination,state["campaign"]["rng"])
        state["log"].append("Fleet route selected: "+":".join(map(str,destination))+".")

    def _orbit(self,state,fleet_index):
        integer(fleet_index,"Fleet index",maximum=len(state["fleets"]["moving"])-1)
        row=state["fleets"]["moving"][fleet_index]
        if row[0] not in (1,2,3,4) or row[22] not in (1,2):raise GameError("The fleet must be landed or in orbit.")
        world,raw,identity=self._orbital_world(state,":".join(map(str,row[19:22])))
        if raw[21]==2:raise GameError("Ships cannot land on this terrain.")
        if row[0]==4 and identity!=(1,5,0):raise GameError("Satellite carriers can land only at New Earth.")
        if ship_count(row,self.catalog)==0:raise GameError("Equip the fleet with ships first.")
        row[:],updated,events=orbit_toggle(row,raw,state["campaign"],state["products"])
        raw[:]=updated;self._navigation_events(state,events)
        state["log"].append(f"{'Landed at' if row[22]==1 else 'Launched into orbit at'} {world['name']}.")

    def _survey_day(self,state):
        from .exploration import discover_planet
        campaign=state["campaign"]
        earned_tax=0;discovered_today=False
        for definition in sorted(self.catalog.get("worlds",[]),key=lambda w:(w["system"],w["planet"],w["moon"])):
            if state["known_systems"][definition["system"]-1]!=1:
                continue
            row=state["worlds"][definition["id"]]
            before=row["raw"]
            owner=before[0]
            if owner==1 and before[6]:
                identity=tuple(definition[key] for key in ("system","planet","moon"))
                result=colony_day(before,state["buildings"],identity,campaign,state["products"])
                earned_tax+=result["tax"]
                messages=self.catalog.get("colony_messages",{})
                for offset in result["notices"]:
                    prefix=messages.get(str(offset),f"Colony event {offset:#x}: ")
                    suffix=messages.get(str(0xA0D if offset==0x9E9 else 0x8E6),".")
                    state["log"].append(f"{state['date']} — {prefix}{world_message_label(self.catalog,definition)}{suffix}")
                owner=before[0]
                if result["lost"]:
                    state["fleets"]["local"][:]=[fleet for fleet in state["fleets"]["local"] if fleet[19:22]!=list(identity)]
                if owner==1 and before[6]:
                    self._allocate(state,before,identity)
            diplomatic_status=relations(campaign)[owner-2] if 2<=owner<=12 else 0
            raw,campaign["rng"],increment=survey_step(before,campaign["rng"],diplomatic_status)
            row["raw"]=raw
            if raw[12]-increment<10<=raw[12] and owner<2 and raw[3]!=0:
                if state["products"][4]["research_state"]==0 and campaign["idea_timers"][4]==-1:
                    schedule_idea(campaign,state["products"],5,20,40)
                    self._event(state,"message",2)
            self._settlement_day(state,definition)
            system=definition['system'];index=8*(system-1)+definition['planet']-1
            visibility=campaign['navigation']['planet_visibility']
            visibility[index],campaign['rng'],discovered_today,method=discover_planet(
                visibility[index],state['known_systems'][system-1],system,definition['moon'],
                campaign['system_observatories'][system-1],state['products'][33]['research_state'],
                state['fleets']['moving'],campaign['rng'],discovered_today)
            if method is not None:
                state['log'].append(f"{state['date']} — {definition['name']} discovered by {method}; fleet navigation is now available.")
        state["resources"]["credits"]+=earned_tax

    def _allocate(self,state,raw,identity):
        result=allocate_colony(raw,state["buildings"],self.catalog["buildings"],identity)
        update_capacity(state["fleets"],identity,result["defense_capacity"])

    def _industry_hour(self,state):
        from .story import count_observatories
        state["campaign"]["system_observatories"]=count_observatories(state["buildings"])
        worlds={tuple(w[key] for key in ("system","planet","moon")):w for w in self.catalog.get("worlds",[])}
        buildings={b["id"]:b for b in self.catalog["buildings"]}
        industry={}
        campaign=state["campaign"]
        def stocks_at(identity,raw):
            return [state["resources"][key] for key in ORE_KEYS] if identity==(1,5,0) else world_stocks(raw)
        def store_at(identity,raw,stocks):
            for value in stocks:
                integer(value,"Ore stock",maximum=2**32-1)
            if identity==(1,5,0):
                state["resources"].update(zip(ORE_KEYS,stocks))
            else:
                set_world_stocks(raw,stocks)
        for row in state["buildings"]:
            identity=tuple(row[1:4])
            if identity not in worlds:
                raise GameError("A building refers to an unknown world.")
            raw=state["worlds"][worlds[identity]["id"]]["raw"]
            if row[6]:
                definition=buildings.get(row[0])
                if definition is None:
                    raise GameError("A construction record refers to an unknown building type.")
                previous=row[6]
                if identity not in industry:
                    industry[identity]=industrial_output(state['buildings'],self.catalog['buildings'],identity)
                row[6],campaign["rng"],refresh=construction_step(row[6],industry[identity],state["levels"]["builder"],
                    state["ranks"]["builder"],definition["unclassified_43_44"][1],campaign["rng"])
                if refresh:
                    self._allocate(state,raw,identity)
                    industry.pop(identity,None)
                if previous and not row[6]:
                    state["log"].append(f"Construction complete: {definition['name']} on {worlds[identity]['name']}.")
            if row[6]==0 and row[8] and row[0]==5:
                stocks=stocks_at(identity,raw)
                stocks[0],campaign["rng"]=derrick_step(stocks[0],storage_limit(state["fleets"],identity,state["buildings"]),raw[59],campaign["rng"])
                store_at(identity,raw,stocks)
        self._deployment_hour(state)
        for identity,definition in sorted(worlds.items()):
            if state["known_systems"][identity[0]-1]!=1:
                continue
            raw=state["worlds"][definition["id"]]["raw"]
            stocks,campaign["rng"]=mine_step(raw,stocks_at(identity,raw),storage_limit(state["fleets"],identity,state["buildings"]),campaign["rng"])
            store_at(identity,raw,stocks)

    def _launch_satellite(self,state,world_id):
        definition=next((w for w in self.catalog.get("worlds",[]) if w["id"]==world_id),None)
        if definition is None or state["known_systems"][definition["system"]-1]!=1:
            raise GameError("This world is not in a discovered system.")
        raw=state["worlds"][world_id]["raw"]
        home_orbit=definition["system"]==1 and definition["planet"]==5
        if state["campaign"]["carrier_failure_reported"] and not home_orbit:
            raise GameError("Remote launches require a satellite carrier after the failed direct launch.")
        if raw[8]!=0 or (raw[6]!=0 or raw[10]!=0) and raw[0]<2:
            raise GameError("This world already has survey support or a satellite in transit.")
        satellite=state["products"][2]
        if satellite["stock"]<=0:
            raise GameError("Manufacture a Satellite first.")
        satellite["stock"]-=1
        raw[8]=1 if home_orbit else 226
        if not home_orbit:
            campaign=state["campaign"]
            campaign["rng"],roll=random_bounded(campaign["rng"],10)
            campaign["carrier_failure_remaining"]=5+roll
        state["log"].append(f"Satellite launched toward {definition['name']}.")

    def _orbital_world(self,state,world_id):
        world=next((w for w in self.catalog["worlds"] if w["id"]==world_id),None)
        if world is None or state["known_systems"][world["system"]-1]!=1:
            raise GameError("Select a world in a discovered system.")
        return world,state["worlds"][world_id]["raw"],tuple(world[k] for k in ("system","planet","moon"))

    def _set_tax(self,state,world_id,level):
        from .colony import set_tax_level,TAX_LABELS
        world,raw,identity=self._orbital_world(state,world_id)
        if state['campaign']['navigation']['planet_visibility'][8*(identity[0]-1)+identity[1]-1]>=128:
            raise GameError('Select a discovered colony.')
        raw[:]=set_tax_level(raw,level)
        state['log'].append(f"Taxes at {world['name']}: {level} ({TAX_LABELS[level]}).")

    def _deployment_world(self,state,world_id):
        world,raw,identity=self._orbital_world(state,world_id)
        if state['campaign']['navigation']['planet_visibility'][8*(world['system']-1)+world['planet']-1]>=128:
            raise GameError("Discover this planet before deploying orbital support.")
        return world,raw,identity

    def _create_fleet(self,state,fleet_type,name=None):
        integer(fleet_type,"Fleet type",minimum=1,maximum=4)
        capabilities=state["campaign"]["capabilities"]
        key=("hunter","transfer","pirate","carrier")[fleet_type-1]
        if not capabilities["transport"] or not capabilities[key]:
            raise GameError("This fleet type is not yet available.")
        if len(state["fleets"]["moving"])>=32:
            raise GameError("The moving-fleet limit is 32.")
        definition=self.catalog["fleet_rules"][fleet_type-1]
        row=new_fleet(fleet_type,definition["default_name"] if name is None else name)
        state["fleets"]["moving"].append(row)
        state["log"].append(f"Created {bytes(row[2:2+row[1]]).decode('ascii')} at New Earth.")

    def _rename_fleet(self,state,fleet_index,name,bank="moving"):
        if bank not in ("moving","local"):raise GameError("Unknown fleet bank.")
        integer(fleet_index,"Fleet index",maximum=len(state["fleets"][bank])-1)
        row=state["fleets"][bank][fleet_index]
        previous=bytes(row[2:2+min(17,row[1])]).decode("cp437")
        row[:]=rename_fleet(row,name)
        state["log"].append(f"Renamed {previous} to {name}.")

    def _disband_fleet(self,state,fleet_index,bank='moving'):
        from .disband import disband_fleet
        row=disband_fleet(state,fleet_index,bank)
        name=bytes(row[2:2+min(17,row[1])]).decode('cp437')
        state['log'].append(f'Disbanded {name}.')

    def _equip_fleet(self,state,fleet_index,category,hull,component=0,quantity=1,bank="moving",maximum=False,bounded=False):
        if bank not in ("moving","local"):
            raise GameError("Unknown fleet bank.")
        integer(fleet_index,"Fleet index",maximum=len(state["fleets"][bank])-1)
        integer(quantity,"Transfer quantity",minimum=-1000,maximum=1000)
        if type(maximum) is not bool or type(bounded) is not bool or maximum and quantity not in (-1,1):
            raise GameError("Maximum transfer needs direction 1 (load) or -1 (unload).")
        if quantity==0:
            raise GameError("Choose a nonzero transfer quantity.")
        row=state["fleets"][bank][fleet_index]
        identity=tuple(row[19:22])
        world_id=":".join(map(str,identity))
        world,raw,_=self._orbital_world(state,world_id)
        if raw[0]!=1 or not raw[6] or row[22] not in (1,7):
            raise GameError("Equipment transfers require a landed fleet at an owned colony.")
        rule=next((r for r in self.catalog["fleet_rules"] if r["id"]==row[0]),None)
        integer(category,"Fleet category",minimum=1,maximum=4)
        cat=next((c for c in rule["categories"] if c["id"]==category),None) if rule else None
        if cat is None:
            raise GameError("This fleet does not have that equipment category.")
        integer(hull,"Hull type",minimum=1,maximum=len(cat["hulls"]))
        integer(component,"Equipment slot",maximum=len(cat["components"]))
        entries=[cat["hulls"][hull-1],*cat["components"]]
        item=entries[component]
        if state["products"][item["product"]-1]["research_state"]==0:
            raise GameError("This equipment has not been discovered.")
        local=None if identity==(1,5,0) else local_record(state["fleets"],identity)
        if identity!=(1,5,0) and (local is None or item["local_slot"]==0):
            raise GameError("This equipment is only supplied by New Earth's depot.")
        stocks={entry["product"]:(state["products"][entry["product"]-1]["stock"] if identity==(1,5,0)
                else struct.unpack_from("<h",bytes(local),131+2*entry["local_slot"])[0] if entry["local_slot"] else 0) for entry in entries}
        if local is not None:
            # Some original product descriptors alias the same local word.
            # Use storage slots as keys so sequential returns accumulate there.
            stocks={entry["local_slot"]:stocks[entry["product"]] for entry in entries}
            cat=deepcopy(cat)
            for entry in cat["hulls"]+cat["components"]:
                entry["product"]=entry["local_slot"]
        updated=list(row)
        transferred=0
        cargo_guard=quantity<0 and component==0 and row[0] in (2,3) and "cargo_rules" in self.catalog
        used=cargo_used(row,self.catalog["cargo_rules"]) if cargo_guard else 0
        old_capacity=cargo_capacity(row,self.catalog) if cargo_guard else 0
        for _ in range(32767 if maximum else abs(quantity)):
            try:
                candidate,next_stocks,changed=equipment_step(updated,cat,hull,component,quantity>0,stocks)
                if not changed:
                    entry=cat['hulls'][hull-1] if component==0 else cat['components'][component-1]
                    notice=('Nothing to unload' if quantity<0 else
                            'No stock available' if stocks[entry['product']]<=0 else 'Equipment bay full')
                    raise EquipmentTransferLimit(notice)
                if identity==(1,5,0) and any(stock+state["products"][product-1]["queued"]>32767
                                             for product,stock in next_stocks.items()):
                    raise EquipmentTransferLimit("Depot full")
                if cargo_guard:
                    capacity=cargo_capacity(candidate,self.catalog)
                    if capacity<used and capacity<old_capacity:
                        if not (maximum or bounded):
                            raise GameError("Unload the excess cargo before removing transport hulls.")
                        raise EquipmentTransferLimit("Unload cargo first")
            except EquipmentTransferLimit:
                if transferred and (maximum or bounded):break
                raise
            updated,stocks=candidate,next_stocks
            transferred+=1
        row[:]=updated
        for entry in entries:
            if identity==(1,5,0):
                state["products"][entry["product"]-1]["stock"]=stocks[entry["product"]]
            elif entry["local_slot"]:
                local[131+2*entry["local_slot"]:133+2*entry["local_slot"]]=struct.pack("<h",stocks[entry["local_slot"]])
        state["log"].append(f"{'Loaded' if quantity>0 else 'Unloaded'} {transferred} {item['name']} at {world['name']}.")

    def _transfer_cargo(self,state,fleet_index,quantity,ore=None,slot=None,maximum=False):
        integer(fleet_index,"Fleet index",maximum=len(state["fleets"]["moving"])-1)
        integer(quantity,"Cargo quantity",minimum=-(2**31-1),maximum=2**31-1)
        if type(maximum) is not bool or maximum and quantity not in (-1,1):
            raise GameError("Maximum transfer needs direction 1 (load) or -1 (unload).")
        if quantity==0 or (ore is None)==(slot is None):
            raise GameError("Select one ore or stored item and a nonzero transfer quantity.")
        row=state["fleets"]["moving"][fleet_index]
        identity=tuple(row[19:22])
        _,raw,_=self._orbital_world(state,":".join(map(str,identity)))
        if row[0] not in (2,3) or row[22]!=1 or raw[0]!=1 or not (raw[6] or raw[10]):
            raise GameError("Cargo requires a landed Trade/Pirate fleet at an owned colony or mining outpost.")
        capacity=cargo_capacity(row,self.catalog)
        used=cargo_used(row,self.catalog["cargo_rules"])
        home=identity==(1,5,0)
        if ore is not None:
            if ore not in ORE_KEYS:raise GameError("Unknown ore.")
            depot=[state["resources"][k] for k in ORE_KEYS] if home else world_stocks(raw)
            storage=storage_limit(state["fleets"],identity,state["buildings"])
            if maximum:
                carried=struct.unpack_from("<I",bytes(row),109+4*ORE_KEYS.index(ore))[0]
                quantity*=ore_transfer_limit(carried,depot[ORE_KEYS.index(ore)],capacity,used,storage,quantity>0)
            updated,depot=transfer_ore(row,depot,ORE_KEYS.index(ore),quantity,capacity,used,storage)
            row[:]=updated
            if home:state["resources"].update(zip(ORE_KEYS,depot))
            else:set_world_stocks(raw,depot)
            label=ore
        else:
            integer(slot,"Cargo slot",minimum=1,maximum=13)
            item=self.catalog["cargo_rules"]["items"][slot-1]
            product=item["product"]
            if product is None or state["products"][product-1]["research_state"]!=5:
                raise GameError("This stored item is not available for cargo transfer.")
            if not any(b[0]==12 and b[1:4]==list(identity) and b[6]==0 for b in state["buildings"]):
                raise GameError("Stored items require a completed Space Port at this world.")
            local=None if home else local_record(state["fleets"],identity)
            if not home and local is None:raise GameError("No local item depot is available.")
            stock=state["products"][product-1]["stock"] if home else struct.unpack_from("<h",bytes(local),131+2*slot)[0]
            if maximum:
                carried=struct.unpack_from("<h",bytes(row),131+2*slot)[0]
                queued=state["products"][product-1]["queued"] if home else 0
                quantity*=item_transfer_limit(carried,stock,item["weight"],capacity,used,quantity>0,queued)
            updated,stock=transfer_item(row,slot,stock,quantity,item["weight"],capacity,used)
            row[:]=updated
            if home:state["products"][product-1]["stock"]=stock
            else:local[131+2*slot:133+2*slot]=struct.pack("<h",stock)
            label=self.catalog["products"][product-1]["name"]
        state["log"].append(f"{'Loaded' if quantity>0 else 'Unloaded'} {abs(quantity)} {label}.")

    def _deploy_station(self,state,world_id,fleet_index=None):
        world,raw,identity=self._deployment_world(state,world_id)
        if not can_deploy_station(raw,payload_count(state["fleets"],identity,"miner_station")):
            raise GameError("A Miner station needs an unclaimed ore-bearing world with survey at least 10, no existing outpost, and station cargo at this planet.")
        definition=next(b for b in self.catalog["buildings"] if b["id"]==25)
        if len(state["buildings"])>=1000:
            raise GameError("Building limit reached; station cargo was retained.")
        if not 1<=raw[21]<=11 or bytes.fromhex(definition["unclassified_fields_hex"])[raw[21]+4]==0:
            raise GameError("A Miner station cannot be deployed on this terrain.")
        consume_payload(state["fleets"],identity,"miner_station",preferred=fleet_index)
        raw,messages=establish_station(raw,state["campaign"],state["products"],self.catalog["surface_rules"])
        state["worlds"][world_id]["raw"]=raw
        for message in messages:
            self._event(state,"message",message)
        self._spawn_deployed(state,identity,25)

    def _deploy_survey_satellite(self,state,world_id,fleet_index=None):
        from .orbital import can_deploy_survey,survey_landing
        world,raw,identity=self._deployment_world(state,world_id)
        if not can_deploy_survey(raw,payload_count(state['fleets'],identity,'survey_satellite')):
            raise GameError('A survey satellite needs a stationary loaded carrier at this planet, with no existing satellite, transit or player survey support.')
        consume_payload(state['fleets'],identity,'survey_satellite',preferred=fleet_index)
        updated,landed,events=survey_landing(raw,identity,state['campaign'],state['products'])
        raw[:]=updated;self._navigation_events(state,events)
        state['log'].append(f"Survey satellite {'deployed at' if landed else 'lost at alien-controlled'} {world['name']}.")

    def _deploy_spy_satellite(self,state,world_id,fleet_index=None):
        self._deploy_spy(state,world_id,fleet_index,ship=False)

    def _deploy_spy_ship(self,state,world_id,fleet_index=None):
        self._deploy_spy(state,world_id,fleet_index,ship=True)

    def _deploy_spy(self,state,world_id,fleet_index,*,ship):
        from .orbital import can_deploy_survey,can_deploy_spy_ship,spy_landing
        world,raw,identity=self._deployment_world(state,world_id)
        kind='spy_ship' if ship else 'spy_satellite'
        gate=can_deploy_spy_ship if ship else can_deploy_survey
        if not gate(raw,payload_count(state['fleets'],identity,kind)):
            raise GameError('A spy ship needs an alien world with survey at least 30, no existing spy ship, and a stationary loaded carrier at this planet.' if ship else
                'A spy satellite needs a stationary loaded carrier at this planet, no existing satellite or transit, and no player colony or mining support.')
        consume_payload(state['fleets'],identity,kind,preferred=fleet_index)
        updated,events=spy_landing(raw,identity,state['campaign'],state['products'],ship=ship)
        raw[:]=updated;self._navigation_events(state,events)
        state['log'].append(f"Deployed {'spy ship' if ship else 'spy satellite'} at {world['name']}.")

    def _deploy_solar_satellite(self,state,world_id,fleet_index=None):
        world,raw,identity=self._deployment_world(state,world_id)
        if not can_deploy_solar(raw,payload_count(state["fleets"],identity,"solar_satellite")):
            raise GameError("An owned colony needs solar-satellite cargo at this planet and fewer than five solar satellites.")
        consume_payload(state["fleets"],identity,"solar_satellite",preferred=fleet_index)
        raw[11]+=1
        state["log"].append(f"Deployed a solar satellite at {world['name']} ({raw[11]}/5).")

    def _assign_droid(self,state,world_id):
        definition=next((w for w in self.catalog.get("worlds",[]) if w["id"]==world_id),None)
        if definition is None or state["known_systems"][definition["system"]-1]!=1:
            raise GameError("Select a world in a discovered system.")
        identity=tuple(definition[key] for key in ("system","planet","moon"))
        raw=state["worlds"][world_id]["raw"]
        mines=sum(row[1:4]==list(identity) and row[6]==0 and row[0] in (4,25) for row in state["buildings"])
        if raw[0]!=1 or not raw[6] or raw[10]>=min(9,mines):
            raise GameError("An owned colony needs a completed unassigned mine; at most nine droids can work there.")
        if identity==(1,5,0):
            stock=state["products"][1]["stock"]
        else:
            fleet=local_record(state["fleets"],identity)
            stock=struct.unpack_from("<h",bytes(fleet),157)[0] if fleet is not None else 0
        if stock<=0:
            raise GameError("No Miner droid is stored at this colony.")
        if identity==(1,5,0):
            state["products"][1]["stock"]-=1
        else:
            fleet[157:159]=struct.pack("<h",stock-1)
        raw[10]+=1
        state["log"].append(f"Assigned a Miner droid on {definition['name']}.")

    def _surface_colony(self,state,world_id):
        world=next((w for w in self.catalog.get("worlds",[]) if w["id"]==world_id),None)
        if world is None or state["known_systems"][world["system"]-1]!=1:
            raise GameError("Select a colony in a discovered system.")
        raw=state["worlds"][world_id]["raw"]
        rules=self.catalog.get("surface_rules")
        if raw[0]!=1 or not raw[6] or rules is None or not 1<=raw[21]<=11 or not rules["editable"][rules["groups"][raw[21]-1]-1]:
            raise GameError("This world does not have an accessible owned colony surface.")
        return world,raw,tuple(world[key] for key in ("system","planet","moon"))

    def _prepare_surface(self,state,world_id):
        from .world_lists import world_visible
        from .surface import surface_editable,surface_revealed
        world=next((w for w in self.catalog.get('worlds',[]) if w['id']==world_id),None)
        if world is None or not world_visible(state,world):
            raise GameError('Select a world in a discovered system.')
        raw=state['worlds'][world_id]['raw']
        # Unscanned views do not position hidden structures. Construction and
        # demolition retain their separate owned-colony guard.
        if surface_revealed(raw):
            identity=tuple(world[key] for key in ('system','planet','moon'))
            place_unpositioned(self.catalog,raw,state['buildings'],identity,
                               require_all=surface_editable(self.catalog,raw))

    def _spawn_deployed(self,state,identity,kind):
        world=next((w for w in self.catalog["worlds"] if tuple(w[k] for k in ("system","planet","moon"))==tuple(identity)),None)
        if world is None:
            raise GameError("A colony deployment refers to an unknown world.")
        raw=state["worlds"][world["id"]]["raw"]
        definition=next(b for b in self.catalog["buildings"] if b["id"]==kind)
        if len(state["buildings"])>=1000:
            state["log"].append(f"Could not deploy {definition['name']} on {world['name']}: building limit reached.")
            return
        if not 1<=raw[21]<=11 or bytes.fromhex(definition["unclassified_fields_hex"])[raw[21]+4]==0:
            state["log"].append(f"Could not deploy {definition['name']} on {world['name']}: incompatible terrain.")
            return
        row,state["campaign"]["rng"]=new_building(definition,identity,255,255,raw[21],state["campaign"]["rng"])
        state["buildings"].append(row)
        if "surface_maps" in self.catalog:
            place_unpositioned(self.catalog,raw,state["buildings"],identity,require_all=False)
        self._allocate(state,raw,identity)
        state["log"].append(f"Deployed {definition['name']} on {world['name']}; construction has started.")

    def _colonize(self,state,world_id,options=None):
        world=next((w for w in self.catalog["worlds"] if w["id"]==world_id),None)
        if world is None or state["known_systems"][world["system"]-1]!=1:
            raise GameError("Select a world in a discovered system.")
        raw=state["worlds"][world_id]["raw"]
        if not can_settle(raw,self.catalog["surface_rules"],state["products"][6]["research_state"]==5,len(state["deployments"])):
            raise GameError("Colonization requires Control Centre research, a suitable world surveyed to 30, and no existing colony or deployment; at most ten deployments may be pending.")
        rank=state["ranks"]["builder"]
        if not (rank==3 or rank==2 and world["system"]<=2):
            raise GameError("Colonization requires builder rank 2 in systems 1–2, or rank 3 elsewhere.")
        if len(state["fleets"]["local"])>=32:
            raise GameError("No local defense fleet slot is available.")
        options=[] if options is None else options
        allowed=self.catalog["settlement_options"]
        if not isinstance(options,list) or len(options)>6 or any(type(kind) is not int or kind not in allowed for kind in options) or len(set(options))!=len(options):
            raise GameError("Choose each colony bundle option at most once.")
        cost=100000
        definitions={b["id"]:b for b in self.catalog["buildings"]}
        for kind in options:
            definition=definitions[kind]
            fields=bytes.fromhex(definition["unclassified_fields_hex"])
            if not ((fields[0]==0 and state["levels"]["builder"]>=fields[1]) or (fields[0]>0 and state["products"][fields[0]-1]["research_state"]==5)) or fields[raw[21]+4]==0:
                raise GameError(f"{definition['name']} is unavailable for this colony bundle.")
            cost+=definition["price"]
        if state["resources"]["credits"]<cost:
            raise GameError(f"This colony bundle costs {cost:,} credits.")
        identity=tuple(world[k] for k in ("system","planet","moon"))
        record=[0,*identity]+[0]*12
        for index,kind in enumerate(allowed):
            record[4+2*index]=int(kind in options)
        state["deployments"].append(record)
        state["campaign"]["rng"]=start_settlement(raw,state["campaign"]["rng"])
        fleet=[0]*161
        name=(world["name"]+" forces").encode("ascii")[:17]
        fleet[0],fleet[1]=5,len(name)
        fleet[2:2+len(name)]=name
        fleet[19:23]=[*identity,7]
        state["fleets"]["local"].append(fleet)
        state["resources"]["credits"]-=cost
        if identity==(1,7,0) and state["products"][11]["research_state"]==0:
            self._event(state,"message",13)
            state["products"][11]["research_state"]=3
        state["log"].append(f"Colonization started on {world['name']}; bundle cost {cost:,} credits.")

    def _settlement_day(self,state,world):
        raw=state["worlds"][world["id"]]["raw"]
        if raw[6] or not 0<raw[7]<128:
            return
        raw[7]-=1
        if raw[7]:
            return
        identity=tuple(world[k] for k in ("system","planet","moon"))
        for row in state["deployments"]:
            if row[1:4]==list(identity):
                state["campaign"]["rng"]=activate_bundle(row,state["campaign"]["rng"])
                self._spawn_deployed(state,identity,1)
        state["campaign"]["rng"]=settlement_population(raw,state["campaign"]["rng"])
        state["log"].append(f"Colony established on {world['name']}.")

    def _deployment_hour(self,state):
        remaining=[]
        for row in state["deployments"]:
            due,done=deployment_step(row,self.catalog.get("settlement_options",[]))
            for kind in due:
                self._spawn_deployed(state,tuple(row[1:4]),kind)
            if not done:
                remaining.append(row)
        state["deployments"]=remaining

    def _build(self,state,world_id,building_id,x,y):
        integer(building_id,"Building type",minimum=1,maximum=25)
        integer(x,"Column",minimum=1,maximum=90)
        integer(y,"Row",minimum=1,maximum=60)
        world,raw,identity=self._surface_colony(state,world_id)
        definition=next((b for b in self.catalog["buildings"] if b["id"]==building_id),None)
        if definition is None or not building_available(definition,raw,state["products"],state["levels"]["builder"]):
            raise GameError("This structure is unavailable: check research, terrain and mineral survey.")
        if building_id in (1,25):
            raise GameError("Command centres and Miner stations require their deployment process.")
        fields=bytes.fromhex(definition["unclassified_fields_hex"])
        if state["levels"]["builder"]==0 or state["ranks"]["builder"]<fields[1]:
            raise GameError("Hire a builder of sufficient rank first.")
        for flag,kind,name in ((fields[3],22,"Builder Plant"),(fields[4],23,"Vehicle Plant")):
            if flag and not any(b[0]==kind and b[1:4]==list(identity) and b[6]==0 and b[8] for b in state["buildings"]):
                raise GameError(f"An operating {name} is required on this colony.")
        if len(state["buildings"])>=1000:
            raise GameError("The campaign's 1,000-building limit has been reached.")
        if state["resources"]["credits"]<definition["price"]:
            raise GameError("Not enough credits to construct this building.")
        place_unpositioned(self.catalog,raw,state["buildings"],identity)
        width,height,blocked=occupancy(self.catalog,raw,state["buildings"],identity)
        if not placement_fits(definition,x,y,width,height,blocked):
            raise GameError("The building footprint overlaps terrain, another structure or the map edge.")
        row,state["campaign"]["rng"]=new_building(definition,identity,x,y,raw[21],state["campaign"]["rng"])
        state["buildings"].append(row)
        self._allocate(state,raw,identity)
        state["resources"]["credits"]-=definition["price"]
        if building_id==7:
            state["campaign"]["rng"],settlers=random_bounded(state["campaign"]["rng"],500)
            population=struct.unpack_from("<I",bytes(raw),13)[0]+800+settlers
            integer(population,"Population",maximum=2**32-1)
            raw[13:17]=struct.pack("<I",population)
        state["log"].append(f"Started {definition['name']} on {world['name']} at {x}, {y}; cost {definition['price']:,} credits.")

    def _demolish(self,state,world_id,building_index):
        world,raw,identity=self._surface_colony(state,world_id)
        integer(building_index,"Building index",maximum=len(state["buildings"])-1)
        row=state["buildings"][building_index]
        if row[1:4]!=list(identity):
            raise GameError("The selected building belongs to another world.")
        if row[0]==1 or row[6]:
            raise GameError("The Command centre and unfinished buildings cannot be demolished.")
        if state["resources"]["credits"]<2000:
            raise GameError("Demolition costs 2,000 credits.")
        del state["buildings"][building_index]
        self._allocate(state,raw,identity)
        state["resources"]["credits"]-=2000
        state["log"].append(f"Demolished a building on {world['name']}; cost 2,000 credits.")

    def _research(self,state,product_id):
        row,definition = self._product(state,product_id)
        if product_id == 14 and not state["campaign"]["hyperspace_allowed"]:
            raise GameError("The hyperspace-drive story discovery is still required.")
        status = row["research_state"]
        if status not in (1,2,3,4):
            raise GameError("This project is locked or already researched.")
        if status in (2,4):
            row["research_state"] -= 1
        else:
            for other in state["products"]:
                if other["research_state"] in (2,4):
                    other["research_state"] -= 1
            row["research_state"] += 1
        state["log"].append(f"Research selection: {definition['name']}, state {row['research_state']}.")

    def _order(self,state,product_id,quantity):
        """Set pending quantity; recovered refund/rebuy behavior, retaining work.

        Zero-quantity cancellation is a deliberate modern improvement over the
        observed positive-quantity confirmation branch. It retains partial work.
        """
        integer(quantity,"Pending quantity",maximum=32767)
        row,definition = self._product(state,product_id)
        if row["research_state"] != 5 or not (definition["manufacturable"] or
                definition["special_ship"] and state["products"][23]["research_state"]==5):
            raise GameError("This product cannot currently be manufactured.")
        difference = quantity-row["queued"]
        # Original purchase clamp 27CF1..27D36: each pending capital ship
        # requires an existing space station. Old queues may still be reduced
        # or cancelled, including imports exceeding current station capacity.
        if definition['special_ship'] and difference > 0 and quantity > state['products'][23]['stock']:
            raise GameError('Each pending capital ship requires an existing Space station.')
        costs = {"credits":definition["price"],**definition["ore_costs"]}
        for key,cost in costs.items():
            state["resources"][key] -= difference*cost
            if state["resources"][key] < 0:
                raise GameError(f"Insufficient {key}.")
        if row["work_remaining"] == 0 and quantity:
            row["work_remaining"] = definition["base_work"]
        row["queued"] = quantity
        state["log"].append(f"Pending production: {quantity} {definition['name']}.")

    def _training_check(self,state,role,course):
        if role not in ROLES:raise GameError("Select a commander role.")
        integer(course,"Course",minimum=1 if role=="developer" else 0,maximum=4 if role=="developer" else 0)
        if not state["ranks"][role]:raise GameError("Hire this commander before requesting training.")
        if state["campaign"]["training_role"]:raise GameError("Another commander is already at university.")
        if not training_available(self.catalog["training_rules"],state["levels"],state["ranks"],state["skills"],
                                  state["campaign"]["training"]["phase"],role,course):
            raise GameError("This commander has reached the current limits for that course.")

    def _quote_training(self,state,role,course=0):
        self._training_check(state,role,course)
        campaign=state["campaign"]
        cost,campaign["rng"]=training_quote(state["levels"][role],campaign["rng"])
        campaign["training"]["quote"]={"role":role,"rank":state["ranks"][role],"course":course,"cost":cost}
        state["log"].append(f"University quote for {role}: {cost:,} credits, 50-69 hours.")

    def _consult_commander(self,state,role,question):
        from .advice import unavailable,consult
        reason=unavailable(state,role)
        if reason:raise GameError(reason)
        rules=self.catalog.get('commander_advice')
        if rules is None:raise GameError('Commander advice is missing; extract the original content again.')
        response,state['campaign']['rng']=consult(rules,state['products'],self.catalog['products'],role,question,state['campaign']['rng'])
        commander=next(c for c in self.catalog['commanders'] if c['role']==role and c['rank']==state['ranks'][role])
        state['log'].append(f"{commander['name']} — {response['question']} {response['answer']}")
        return [response]

    def _train(self,state):
        campaign=state["campaign"];training=campaign["training"];quote=training["quote"]
        if quote is None:raise GameError("Request a university quote first.")
        self._training_check(state,quote["role"],quote["course"])
        state["resources"]["credits"],campaign["training_remaining"],campaign["rng"]=training_purchase(
            state["resources"]["credits"],quote["cost"],campaign["rng"])
        campaign["training_role"]=ROLES.index(quote["role"])+1
        if quote["role"]=="developer":training["course"]=quote["course"]
        training["quote"]=None
        course=COURSES[quote["course"]-1] if quote["course"] else "General training"
        state["log"].append(f"{quote['role'].title()} started {course}: {quote['cost']:,} credits; {campaign['training_remaining']} hours.")

    def _hire(self,state,role,rank):
        if role not in ROLES:
            raise GameError("Unknown commander role.")
        integer(rank,"Rank",minimum=1,maximum=3)
        if rank <= state["ranks"][role]:
            raise GameError("The DOS hiring screen only accepts a higher rank.")
        definition = next(c for c in self.catalog["commanders"] if c["role"]==role and c["rank"]==rank)
        if state["resources"]["credits"] < definition["hire_price"]:
            raise GameError("Insufficient credits to hire this commander.")
        state["resources"]["credits"] -= definition["hire_price"]
        state["levels"][role],state["ranks"][role] = state["campaign"]["commander_levels"][ROLES.index(role)*3+rank-1],rank
        if role == "developer":
            state["skills"] = dict(zip(SUBJECTS,state["campaign"]["developer_skill_choices"][4*(rank-1):4*rank]))
        campaign=state["campaign"]
        if campaign["training_role"]==ROLES.index(role)+1:
            campaign["training_role"]=0
            state["log"].append("The replaced commander's course ended without a refund.")
        if campaign["training"]["quote"] is not None and campaign["training"]["quote"]["role"]==role:
            campaign["training"]["quote"]=None
        state["log"].append(f"Hired {definition['name']} as {role}.")

    def _pause_research(self,state,paused):
        state["research_paused"] = paused

    def _admin(self,state,command):
        if not self.admin_enabled:
            raise GameError("Enable admin changes for this session first.")
        words = shlex.split(command)
        if len(words)==3 and words[0] in ("give","set") and words[1] in RESOURCE_OFFSETS:
            amount = int(words[2])
            integer(amount,"Amount",maximum=2**32-1)
            state["resources"][words[1]] = amount+(state["resources"][words[1]] if words[0]=="give" else 0)
        elif len(words)==3 and words[0]=="stock":
            row,_ = self._product(state,int(words[1]))
            row["stock"] = int(words[2])
        else:
            raise GameError("Commands: give RESOURCE AMOUNT; set RESOURCE AMOUNT; stock PRODUCT_ID AMOUNT.")
        state["assisted"] = True
        state["log"].append("Admin: "+command)

    def save(self,path):
        validate(self.state,self.catalog)
        from .music_control import validate_audio
        validate_audio(self.audio)
        from .effect_control import validate_effects
        validate_effects(self.effects)
        from .result_animation import validate_animation
        validate_animation(self.result_animation,self.state)
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise GameError("Recovered sessions must use .json; DOS saves cannot be overwritten.")
        from .hero import validate_hero
        validate_hero(self.hero)
        payload=dict(self.state,audio=self.audio,effects=self.effects,result_animation=self.result_animation,hero=self.hero)
        content=(json.dumps(payload,indent=2,allow_nan=False)+"\n").encode('utf-8')
        if len(content)>MAX_SAVE_BYTES:
            # An accepted compact UTF-8 save must not become unreadable merely
            # because indentation and ASCII escapes expand it when re-saved.
            # Escape lone surrogates while retaining ordinary Unicode as UTF-8.
            content=(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False)+"\n").encode('utf-8',errors='backslashreplace')
        if len(content)>MAX_SAVE_BYTES:
            raise GameError('Session exceeds save-size limit; existing save was not replaced.')
        atomic_write(path,content)

    @classmethod
    def load(cls,catalog,path):
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_SAVE_BYTES+1)
        if len(data)>MAX_SAVE_BYTES:
            raise GameError("Session exceeds save-size limit.")
        try:
            state = json.loads(data,object_pairs_hook=_unique_object)
        except (ValueError,RecursionError) as exc:
            raise GameError(f"Invalid recovered-session JSON: {exc}") from exc
        hero=2
        if isinstance(state,dict):
            if state.get('schema')==SCHEMA:
                from .hero import validate_hero
                hero=state.pop('hero',None);validate_hero(hero)
            elif 'hero' in state:
                raise GameError('Unexpected hero identity in an older save.')
        audio=None
        effects=None
        animation=None;animation_supplied=False
        if isinstance(state,dict) and state.get('schema') in {'recovered-strategy-v'+str(v) for v in range(8,22)}:
            for key in ('events','presentation_requests'):
                records=state.get(key,[])
                if isinstance(records,list) and any(isinstance(row,dict) and ('report' in row or row.get('kind')=='report') for row in records):
                    raise GameError('Unexpected mission report in an older save.')
        if isinstance(state,dict) and state.get('schema') in ('recovered-strategy-v21','recovered-strategy-v22'):state['schema']=SCHEMA
        if isinstance(state,dict) and state.get('schema')==SCHEMA:
            animation_supplied='result_animation' in state;animation=state.pop('result_animation',None)
        if isinstance(state,dict) and state.get('schema') in (SCHEMA,'recovered-strategy-v20','recovered-strategy-v19','recovered-strategy-v18'):
            effects=state.pop('effects',None)
            from .effect_control import validate_effects
            validate_effects(effects,battle=state['schema']!='recovered-strategy-v18',lifecycle=state['schema'] in (SCHEMA,'recovered-strategy-v20'))
        if isinstance(state,dict) and state.get('schema') in (SCHEMA,'recovered-strategy-v20','recovered-strategy-v19','recovered-strategy-v18','recovered-strategy-v17','recovered-strategy-v16'):
            audio=state.pop('audio',None)
            from .music_control import validate_audio
            validate_audio(audio)
        if isinstance(state,dict) and state.get('schema') in {'recovered-strategy-v'+str(v) for v in range(8,17)}:
            if 'active_scene' in state:raise GameError('Unexpected cinematic in an older save.')
            state['active_scene']=None
        if isinstance(state,dict) and state.get('schema')=='recovered-strategy-v16':state['schema']=SCHEMA
        if isinstance(state,dict) and state.get('schema')=='recovered-strategy-v17':state['schema']=SCHEMA
        if isinstance(state,dict) and state.get('schema')=='recovered-strategy-v18':state['schema']=SCHEMA
        if isinstance(state,dict) and state.get('schema')=='recovered-strategy-v19':state['schema']=SCHEMA
        if isinstance(state,dict) and state.get('schema')=='recovered-strategy-v20':state['schema']=SCHEMA
        if isinstance(state,dict) and state.get('schema')=='recovered-strategy-v15':
            state['schema']=SCHEMA
        if isinstance(state,dict) and state.get("schema")=="recovered-strategy-v14":
            campaign=state.get("campaign")
            if not isinstance(campaign,dict):raise GameError("Invalid older campaign.")
            bar=campaign.get("bar")
            if bar is not None:
                if not isinstance(bar,dict) or "social" in bar or "conversation" in bar:raise GameError("Unexpected bar dialogue state in an older save.")
                bar.update(social=None,conversation=None)
            state["schema"]=SCHEMA
        if isinstance(state,dict) and state.get("schema") in {"recovered-strategy-v"+str(v) for v in range(8,14)}:
            campaign=state.get("campaign")
            if not isinstance(campaign,dict) or "bar" in campaign:raise GameError("Unexpected bar records in an older save.")
            campaign["bar"]=None
        if isinstance(state,dict) and state.get("schema") in {"recovered-strategy-v"+str(v) for v in range(8,13)}:
            if "active_dialog" in state:raise GameError("Unexpected conversation in an older save.")
            state["active_dialog"]=None
            campaign=state.get("campaign")
            if not isinstance(campaign,dict) or "system_observatories" in campaign:raise GameError("Unexpected observatory cache in an older save.")
            from .story import count_observatories
            try:campaign["system_observatories"]=count_observatories(state["buildings"])
            except (KeyError,TypeError,IndexError):raise GameError("Invalid buildings in an older save.") from None
        if isinstance(state,dict) and state.get("schema") in {"recovered-strategy-v"+str(v) for v in range(8,12)}:
            if "battle_requests" in state:raise GameError("Unexpected battle queue in an older save.")
            state["battle_requests"]=[]
        # v8 already retains complete campaign/ground state and could never
        # start space combat. Adding an empty encounter is lossless.
        if isinstance(state,dict) and state.get("schema")=="recovered-strategy-v8" and "space_encounter" not in state:
            state["schema"]="recovered-strategy-v9";state["space_encounter"]=None
        if isinstance(state,dict) and state.get("schema")=="recovered-strategy-v9":
            # Validate the old numerical snapshot before deriving its initial
            # view. The first placeholder is never committed or shown.
            previous=state.get("space_encounter")
            if isinstance(previous,dict) and ("radar" in previous or "cinema" in previous):raise GameError("Unexpected presentation state in a v9 save.")
            state["schema"]=SCHEMA
            if isinstance(previous,dict):previous["radar"]=[]
            if isinstance(previous,dict):previous["cinema"]=None
            validate(state,catalog)
            if previous is not None:
                from .space_presentation import space_snapshot_plan
                previous["radar"]=space_snapshot_plan(previous["battle"],catalog["battle_rules"]["space"])
        if isinstance(state,dict) and state.get("schema")=="recovered-strategy-v10":
            previous=state.get("space_encounter")
            if isinstance(previous,dict) and "cinema" in previous:raise GameError("Unexpected cinematic state in a v10 save.")
            if isinstance(previous,dict):previous["cinema"]=None
            state["schema"]=SCHEMA
        if isinstance(state,dict) and state.get("schema")=="recovered-strategy-v11":state["schema"]=SCHEMA
        if isinstance(state,dict) and state.get("schema")=="recovered-strategy-v12":state["schema"]=SCHEMA
        if isinstance(state,dict) and state.get("schema")=="recovered-strategy-v13":state["schema"]=SCHEMA
        result=cls(catalog,state,hero=hero);result.audio=deepcopy(audio);result.effects=deepcopy(effects)
        if animation_supplied:
            from .result_animation import validate_animation
            validate_animation(animation,state)
            result.result_animation=deepcopy(animation)
        if result.result_animation is not None:result.result_animation['paused']=True
        return result

    def tick_result_animation(self):
        from .result_animation import tick_animation
        self.result_animation,changed=tick_animation(self.result_animation,self.state)
        return changed

    def pause_result_animation(self,paused=True):
        from .result_animation import validate_animation
        if type(paused) is not bool:raise GameError('Invalid result-animation pause state.')
        if self.result_animation is None:return
        candidate=dict(self.result_animation,paused=paused)
        validate_animation(candidate,self.state);self.result_animation=candidate
