"""Shared local conversion pipeline for the CLI and first-run importer."""
import json
from pathlib import Path

from ..core import GameError
from ..persistence import atomic_write


def recover_data(source, output, *, include_saves=True, progress=print):
    from .assets import audit_pictures
    from .catalog import read_catalog
    from .text import audit_text
    from .session import RecoveredSession
    output = Path(output).resolve()
    source = Path(source).resolve()
    if output.is_relative_to(source) and "opensource" not in output.relative_to(source).parts:
        raise GameError("Extract to a separate folder or under opensource, never over original data.")
    from .content import ContentSource
    recovered=ContentSource(source);catalog=recovered.catalog
    progress('Converting pictures and music...')
    pictures = audit_pictures(source,output/"pictures")
    from .fm_music import audit_music
    music = audit_music(source,output/"music/fm")
    from .module_music import MODULE_NAMES
    for name in MODULE_NAMES:
        atomic_write(output/f'music/mod/{name}.mod',recovered.module_music(name).data)
    from .intro_cinema import TRACKS as INTRO_TRACKS
    for name in INTRO_TRACKS:
        atomic_write(output/f'music/intro/{name}.mod',recovered.intro_music(name).data)
    texts = audit_text(source)
    progress('Converting space animations...')
    animation_frames=0
    for asset,metadata in enumerate(catalog["space_cinema"]["assets"],1):
        for frame in range(1,metadata[0]+1):
            atomic_write(output/f"animations/space/SA{asset}/{frame}.png",recovered.space_animation(asset,frame).png())
            animation_frames+=1
    from .story_cinema import STORY_ASSETS,audit_animations
    story_report=audit_animations(source,catalog['story_cinema'])
    progress('Converting story and bridge animations...')
    story_frames=0
    bridge_frames=0
    for asset in range(1,7):
        for frame in range(1,catalog['story_cinema'][asset-1]['frames']+1):
            atomic_write(output/f'animations/bridge/MAIN{asset}/{frame}.png',recovered.bridge_animation(asset,frame).png())
            bridge_frames+=1
    for asset in STORY_ASSETS:
        for frame in range(1,catalog['story_cinema'][asset-1]['frames']+1):
            atomic_write(output/f'animations/story/MAIN{asset}/{frame}.png',recovered.story_animation(asset,frame).png())
            story_frames+=1
    from .samples import audit_samples
    from .defeat_cinema import ANIMATIONS
    progress('Converting defeat and victory animations...')
    defeat_frames=0
    for asset in (15,16):
        # The ruin sequence only draws 61 steps; the female sequence
        # repeats its four-frame cycle after its distinct first pass.
        for step in range(1,min(catalog['story_cinema'][asset-1]['frames']*2,ANIMATIONS[asset][1])+1):
            atomic_write(output/f'animations/defeat/MAIN{asset}/{step}.png',recovered.defeat_animation(asset,step).png())
            defeat_frames+=1
    for frame in range(1,17):
        atomic_write(output/f'animations/victory/ANIM1/{frame}.png',recovered.victory_animation(frame).png())
    progress('Converting opening film...')
    from .intro_assets import FRAME_COUNTS,converted_animation
    for asset in FRAME_COUNTS:
        with recovered.safe_path(f'INTRO/ANIM{asset}.ANI').open('rb') as stream:data=stream.read(2*1024*1024+1)
        atomic_write(output/f'animations/intro/ANIM{asset}.oria',converted_animation(data,asset))
    progress('Converting credits...')
    from .credits_assets import ASSETS,displayed_frames
    for asset in ASSETS:
        for frame in displayed_frames(asset):
            atomic_write(output/f'animations/credits/ANIM{asset}/{frame}.png',recovered.credits_animation(asset,frame).png())
    atomic_write(output/'pictures/CREDITS/HIGHRES.png',recovered.credits_picture('HIGHRES').png())
    for frame in range(1,24):
        atomic_write(output/f'animations/disk/MAIN17/{frame}.png',recovered.disk_animation(frame).png())
    from .control_panel import converted_icons
    atomic_write(output/'controls/icons.ori',converted_icons(recovered.control_icons()))
    for product_id in range(1, 36):
        atomic_write(output/f'models/V{product_id}.VEC', recovered.product_model_data(product_id))
    progress('Converting sound effects and game data...')
    samples=audit_samples(source)
    for record in samples['samples']:
        path=Path(record['path']);sample=recovered.sample(path.stem,path.parent.name)
        atomic_write(output/'samples'/path.with_suffix('.ors'),sample.converted())
    for name,content in (("catalog.json",catalog),("pictures.json",pictures),("text.json",texts),("music.json",music),('story-cinema.json',story_report),('samples.json',samples)):
        atomic_write(output/name,(json.dumps(content,indent=2)+"\n").encode())
    atomic_write(output/'startup.json',(json.dumps(recovered.startup_data(),indent=2)+'\n').encode())
    sessions = 0
    for path in sorted((source/"SAVE").glob("SPIDYSAV.[1-7]")) if include_saves else ():
        RecoveredSession.from_dos(catalog,path).save(output/"sessions"/(path.name+".json"))
        sessions += 1
    progress(f"Recovered {len(catalog['products'])} products, {len(catalog['buildings'])} buildings, {len(catalog['commanders'])} commanders, {len(pictures['decoded'])} pictures, {len(texts['decoded'])} text files.")
    progress(f"Converted {animation_frames} space cinematic frames from 25 animation assets.")
    progress(f"Converted {story_frames} cumulative story frames from five animation assets for the native Story player.")
    progress(f"Converted {defeat_frames} defeat animation frames, including the distinct first female cycle.")
    progress('Converted 16 original victory animation frames.')
    progress(f"Extracted {len(MODULE_NAMES)} original module music tracks, including complete FAILURE and ENDSEQ.")
    progress('Converted 68 original control icons for native battle buttons.')
    progress(f'Converted {bridge_frames} Control Room idle frames for standalone playback.')
    progress(f"Converted {len(samples['samples'])} PCM sound samples; native playback includes cinematic effects, battle-frame sounds and ground-order feedback.")
    progress(f"Converted {len(music['decoded'])} FM music tracks; {len(music['unsupported'])} malformed track recorded in music.json. The Music tab uses the optional native synthesizer.")
    progress(f"Picture exceptions: {len(pictures['unsupported'])} unsupported, {len(pictures['malformed'])} malformed. Text exceptions: {len(texts['unsupported'])} unsupported, {len(texts['malformed'])} malformed. See reports in {output}.")
    progress(f"Extracted {sessions} partial strategy sessions with {len(catalog['worlds'])} worlds each. Run without the original installation: python run.py recover \"{output}\"")
