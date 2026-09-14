"""Complete block addressing, with semantic interpretation added independently."""
import json
from importlib.resources import files
import struct

from ..core import GameError, integer
from ..legacy import LegacySave

LAYOUT = json.loads(files("openreunion").joinpath("data/save-layout.json").read_text())


class SaveBlocks:
    def __init__(self,data):
        self.data = LegacySave(data).data

    def read(self,address,length,*,pointer=False):
        integer(address,"DS address",maximum=65535)
        integer(length,"Block length",minimum=1,maximum=65536)
        kind="pointer" if pointer else "ds"
        for block in LAYOUT["blocks"]:
            if block["kind"]!=kind:
                continue
            start=block["address"]
            delta=0 if pointer and address==start else address-start
            if (not pointer or address==start) and 0<=delta and delta+length<=block["length"]:
                at=block["save_offset"]+delta
                return self.data[at:at+length]
        raise GameError(f"Address {address:#x}, length {length} is not in a serialized {kind} block.")

    def number(self,address,format="H"):
        return struct.unpack("<"+format,self.read(address,struct.calcsize("<"+format)))[0]

    def offset(self,address,length=1):
        integer(address,"DS address",maximum=65535)
        integer(length,"Block length",minimum=1,maximum=65536)
        for block in LAYOUT["blocks"]:
            if block["kind"]=="ds" and block["address"]<=address and address+length<=block["address"]+block["length"]:
                return block["save_offset"]+address-block["address"]
        raise GameError("DS address is not serialized.")
