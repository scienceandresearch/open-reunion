"""Check an extracted bundle against source adapters without changing originals."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/"src"))
from openreunion.dos.content import ContentSource
from openreunion.dos.session import RecoveredSession


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("bundle",type=Path)
    parser.add_argument("--wheel",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--no-saves",action='store_true',help='Verify a complete asset import without personal saves')
    args = parser.parse_args()
    original,bundle = ContentSource(args.source),ContentSource(args.bundle)
    assert not original.bundled and bundle.bundled
    assert original.catalog == bundle.catalog
    assert len(bundle.catalog["surface_maps"])==47
    control_icons=0;control_panels=0;control_slides=0;control_wipes=0
    if 'control_buttons' in bundle.catalog:
        from openreunion.dos.control_panel import ControlPictures
        assert original.control_icons()==bundle.control_icons()
        first,second=ControlPictures(original),ControlPictures(bundle)
        for icon in range(68):assert first.button(icon)==second.button(icon)
        control_icons=68
        from openreunion.dos.control_layouts import select_layout
        for number in range(1,39):
            slots=select_layout(bundle.catalog['control_layouts'],number)['buttons']
            for page in range(2 if slots[6] else 1):
                assert first.panel(original.catalog['control_buttons'],slots,page)==second.panel(bundle.catalog['control_buttons'],slots,page)
                from openreunion.dos.control_wipe import wipe_pictures
                previous=bytes((i*31+17)%256 for i in range(10240))
                assert wipe_pictures(first.panel(original.catalog['control_buttons'],slots,page),previous)==wipe_pictures(second.panel(bundle.catalog['control_buttons'],slots,page),previous)
                control_wipes+=32
                control_panels+=1
            if slots[6]:
                for page in (0,1):
                    frames=first.slide(original.catalog['control_buttons'],slots,original.catalog['control_slide'],page)
                    assert frames==second.slide(bundle.catalog['control_buttons'],slots,bundle.catalog['control_slide'],page)
                    control_slides+=len(frames)
    battle_results=0;result_fades=0
    if 'character_set' in bundle.catalog:
        from openreunion.dos.battle_results import BattleResultPictures
        first,second=BattleResultPictures(original),BattleResultPictures(bundle)
        losses={'friendly':[0,1,12345,4294967295],'hostile':[12,123,9999,10000]}
        for family in ('space','ground'):
            for won in (False,True):
                for frame in range(1,4) if family=='ground' and not won else (1,):
                    for fade_step in range(6):
                        assert first.picture(family,won,losses,frame=frame,fade_step=fade_step)==second.picture(family,won,losses,frame=frame,fade_step=fade_step)
                        result_fades+=1
                    battle_results+=1
    samples=0
    if (args.bundle/'samples.json').is_file():
        from openreunion.dos.samples import audit_samples,SampleRenderer
        audit=json.loads((args.bundle/'samples.json').read_text())
        assert audit==audit_samples(args.source)
        expected=set()
        for record in audit['samples']:
            path=Path(record['path']);expected.add(path.with_suffix('.ors').as_posix())
            first=original.sample(path.stem,path.parent.name);second=bundle.sample(path.stem,path.parent.name)
            assert first==second
            for position in (0,first.frames()//2,max(0,first.frames()-100)):
                assert SampleRenderer(first,position=position).render(256)==SampleRenderer(second,position=position).render(256)
            samples+=1
        assert expected=={p.relative_to(args.bundle/'samples').as_posix() for p in (args.bundle/'samples').rglob('*.ors')}
    fm_tracks=0
    if (args.bundle/'music.json').is_file():
        from openreunion.dos.fm_music import audit_music,FmPlayer
        music_report=json.loads((args.bundle/'music.json').read_text())
        assert music_report==audit_music(args.source)
        names=[Path(record['path']).stem for record in music_report['decoded']]
        assert sorted(path.stem for path in (args.bundle/'music/fm').glob('*.ofm'))==sorted(names)
        for name in names:
            a,b=original.fm_music(name),bundle.fm_music(name)
            assert a==b,name
            first,second=FmPlayer(a),FmPlayer(b)
            assert first.initial_writes==second.initial_writes
            for _ in range(256):assert first.tick()==second.tick(),name
            fm_tracks+=1
    pictures = bundle.pictures()
    for name in pictures:
        if name == 'CREDITS/HIGHRES.PIC':
            assert original.credits_picture('HIGHRES') == bundle.credits_picture('HIGHRES')
            continue
        assert original.picture(name) == bundle.picture(name),name
        assert original.indexed_picture(name) == bundle.indexed_picture(name),name
    texts = bundle.texts()
    assert texts == sorted(original.texts())
    for name in texts:
        assert original.text(name) == bundle.text(name),name
    animation_frames=0
    if "space_cinema" in original.catalog:
        for asset,metadata in enumerate(original.catalog["space_cinema"]["assets"],1):
            for frame in range(1,metadata[0]+1):
                assert original.space_animation(asset,frame)==bundle.space_animation(asset,frame),(asset,frame)
                animation_frames+=1
    saves = [] if args.no_saves else sorted((args.source/"SAVE").glob("SPIDYSAV.[1-7]"))
    story_frames=0
    if 'story_cinema' in original.catalog:
        from openreunion.dos.story_cinema import STORY_ASSETS,audit_animations
        assert json.loads((args.bundle/'story-cinema.json').read_text())==audit_animations(args.source,original.catalog['story_cinema'])
        for asset in STORY_ASSETS:
            for frame in range(1,original.catalog['story_cinema'][asset-1]['frames']+1):
                assert original.story_animation(asset,frame)==bundle.story_animation(asset,frame),(asset,frame)
                story_frames+=1
    if args.no_saves:
        assert not (args.bundle/'sessions').exists()
    else:
        assert len(saves)==7
    for path in saves:
        first = RecoveredSession.from_dos(original.catalog,path)
        second = RecoveredSession.load(bundle.catalog,args.bundle/"sessions"/(path.name+".json"))
        assert first.state == second.state,path.name
        first.apply("advance",hours=24)
        second.apply("advance",hours=24)
        assert first.state == second.state,path.name
    picture_report = json.loads((args.bundle/"pictures.json").read_text())
    text_report = json.loads((args.bundle/"text.json").read_text())
    result = {"passed":True,"executable_sha256":original.catalog["sha256"],"products":35,"buildings":25,"commanders":12,"worlds":len(original.catalog["worlds"]),
              "identical_picture_conversions":len(pictures),"identical_text_files":len(texts),"identical_surface_maps":47,
              "identical_control_icons_and_buttons":control_icons,
              "identical_control_panel_pages":control_panels,
              "identical_control_slide_frames":control_slides,
              "identical_control_wipe_operations":control_wipes,
              "identical_battle_result_compositions":battle_results,
              "identical_battle_result_fade_levels":result_fades,
              "identical_indexed_picture_decodes":len(pictures),
              "identical_space_animation_frames":animation_frames,
              "identical_story_animation_frames":story_frames,
              "identical_pcm_samples_and_continuations":samples,
              "identical_fm_music_tracks_and_256_tick_continuations":fm_tracks,
              "text_records":sum(len(bundle.text(name)) for name in texts),"identical_session_imports_and_continuations":len(saves),
              "unsupported_pictures":picture_report["unsupported"],"quarantined_pictures":picture_report["malformed"],
              "unsupported_text":text_report["unsupported"],"bundle_has_no_executable":not list(args.bundle.rglob("*.PRG")),
              "scope":"Bundle equality and 24-hour recovered-system continuation, including campaign timers and world surveys; no full campaign or independent rendering oracle."}
    assert result["bundle_has_no_executable"]
    if args.wheel:
        with zipfile.ZipFile(args.wheel) as archive:
            names = archive.namelist()
            assert "openreunion/dos/session.py" in names
            assert "openreunion/data/prototype.json" in names
            assert "openreunion/data/save-layout.json" in names
            assert not any(name.lower().endswith((".prg",".pic",".png",".asm",".smp",".mod")) or "/local/" in name for name in names)
        result["wheel"] = {"name":args.wheel.name,"sha256":hashlib.sha256(args.wheel.read_bytes()).hexdigest(),
                           "files":len(names),"original_assets_embedded":False}
    if args.output:
        if not args.output.resolve().is_relative_to(PROJECT):
            parser.error("Report must remain under opensource")
        args.output.write_text(json.dumps(result,indent=2)+"\n")
    checked = "catalog and wheel checks" if args.wheel else "catalog checks"
    print(f"Bundle verified: {len(pictures)} identical PNG conversions, {len(texts)} text files, {len(saves)} session imports/continuations; {checked} passed.")


if __name__ == "__main__":
    main()
