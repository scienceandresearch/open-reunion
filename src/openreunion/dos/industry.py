"""Original construction progress and hourly extraction arithmetic."""
import struct

from .campaign import random_bounded
from .colony import i32,trunc_div
from .rules import i16


def construction_step(remaining,industrial_output,builder_level,builder_rank,chance_limit,seed):
    """0x12610..0x126FC, after resolving the affected world correctly."""
    # DOS adds the base capacity in a signed word, turning sufficient industry
    # into negative progress. Wide arithmetic keeps extra capacity beneficial.
    progress=(industrial_output+4000+builder_level*100)//1500
    if builder_rank==1:
        progress=trunc_div(progress,2)
    if builder_rank==3:
        progress*=2
    seed,roll=random_bounded(seed,chance_limit)
    left=remaining
    if roll<10:
        left=(remaining-progress)&255 if remaining>progress else 0
    refresh=left==0 or left<40<=remaining or left<80<=remaining
    return left,seed,refresh


def derrick_step(stock,capacity,abundance,seed):
    """0x1289C..0x12927, using the building's world and stock destination."""
    if i32(stock)<capacity:
        seed,roll=random_bounded(seed,100)
        if roll<35:
            stock+=abundance//10
    return stock,seed


def mine_step(raw,stocks,capacity,seed):
    """0x12A6E..0x12BB2; five non-Detoxin ores, after world resolution."""
    stocks=list(stocks)
    if raw[0]!=1 or not (raw[6] or raw[10]):
        return stocks,seed
    for index in range(1,6):
        if i32(stocks[index])>=capacity:
            continue
        if not raw[6]:
            seed,roll=random_bounded(seed,100)
            if roll>=30:
                continue
        stocks[index]+=trunc_div(i16(raw[59+index]*raw[10]),10)
    return stocks,seed


def world_stocks(raw):
    return list(struct.unpack_from("<6I",bytes(raw),27))


def set_world_stocks(raw,stocks):
    # Struct's bounded write rejects overflow instead of wrapping saved ores.
    raw[27:51]=struct.pack("<6I",*stocks)
