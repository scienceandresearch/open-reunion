"""Recovered scene entry notices and conversation-six cinematic lead-in."""
from ..core import integer


def scene_notice(scene):
    integer(scene,'Scene',minimum=1,maximum=10)
    return {4:36,9:1}.get(scene)


def dialog_scene(script):
    integer(script,'Conversation',minimum=2,maximum=10)
    return 10 if script==6 else None
