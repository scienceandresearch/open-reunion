"""CLI for the desktop client, modern admin shell, and local compatibility tools."""
import argparse
import json
from pathlib import Path
import sys

from .core import GameError
from .engine import Engine
from .legacy import LegacySave, TerrainMap, audit_installation, export_legacy
from .persistence import atomic_write, load_game, save_game


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open Reunion reconstruction workbench (prototype, not full game parity)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("play", help="Launch desktop prototype")
    recover = commands.add_parser("recover", help="Launch original-data client for recovered DOS economic systems")
    recover.add_argument("source", type=Path, help="Original DOS installation or extracted bundle")
    recover.add_argument("--save", type=Path, help="Load a DOS or modern JSON save instead of starting a new game")
    recover.add_argument("--original-ui", action="store_true", help="Launch the original graphical interface under construction")
    extract = commands.add_parser("recover-data", help="Extract verified catalogs, pictures and decrypted text into a separate local folder")
    extract.add_argument("source", type=Path)
    extract.add_argument("--output", required=True, type=Path)
    extract.add_argument("--no-saves", action="store_true", help="Do not import personal DOS saves")
    asset_import = commands.add_parser("import-assets", help="Import your original game folder, or open the setup window")
    asset_import.add_argument("source", nargs="?", type=Path)
    asset_import.add_argument("--output", type=Path, default=Path("local/recovered"))
    asset_import.add_argument("--play", action="store_true", help="Launch the game after importing")
    music = commands.add_parser("render-music", help="Render recovered FM music to a new stereo WAV file")
    music.add_argument("source",type=Path)
    music.add_argument("track")
    music.add_argument("--output",type=Path,required=True)
    music.add_argument("--seconds",type=int,default=30)
    music.add_argument("--rate",type=int,default=48000)
    sample=commands.add_parser('render-sample',help='Render a recovered sound sample to a new stereo WAV file')
    sample.add_argument('source',type=Path);sample.add_argument('name')
    sample.add_argument('--folder',choices=('SOUND','SOUND2','SOUND3'),default='SOUND')
    sample.add_argument('--output',type=Path,required=True);sample.add_argument('--rate',type=int,default=48000)
    listen=commands.add_parser('play-sample',help='Play one recovered sound effect through the native Windows output')
    listen.add_argument('source',type=Path);listen.add_argument('name')
    listen.add_argument('--folder',choices=('SOUND','SOUND2','SOUND3'),default='SOUND')
    inspect = commands.add_parser("inspect-save", help="Read known DOS resource fields")
    inspect.add_argument("source", type=Path)
    edit = commands.add_parser("edit-save", help="Export a new DOS save; never overwrite the source")
    edit.add_argument("source", type=Path)
    edit.add_argument("destination", type=Path)
    edit.add_argument("changes", nargs="+", metavar="RESOURCE=VALUE")
    terrain = commands.add_parser("inspect-map", help="Inspect a DOS terrain grid")
    terrain.add_argument("source", type=Path)
    audit = commands.add_parser("audit", help="Hash and inspect a local DOS installation")
    audit.add_argument("source", type=Path)
    audit.add_argument("--output", required=True, type=Path)
    console = commands.add_parser("console", help="Modern scenario admin shell")
    console.add_argument("--load", type=Path)
    console.add_argument("--save", type=Path, help="Save on exit")
    console.add_argument("--admin", action="store_true", help="Enable resource changes")
    args = parser.parse_args(argv)
    try:
        if args.command == "play":
            from .ui import play
            play()
        elif args.command == "recover":
            if args.original_ui:
                from .dos.original_ui import play
            else:
                from .dos.ui import play
            play(args.source,args.save)
        elif args.command == "import-assets":
            from .dos.asset_import import import_assets
            if args.source is not None:
                import_assets(args.source, args.output)
                complete = True
            else:
                from .dos.import_ui import choose_and_import
                complete = choose_and_import(args.output)
            if complete and args.play:
                from .dos.original_ui import play
                play(args.output)
        elif args.command == "recover-data":
            from .dos.extraction import recover_data
            recover_data(args.source, args.output, include_saves=not args.no_saves)
        elif args.command == "render-music":
            from .dos.content import ContentSource
            from .dos.fm_audio import render_wave
            content=ContentSource(args.source)
            print(json.dumps(render_wave(content.fm_music(args.track.upper()),args.output,args.seconds,rate=args.rate),indent=2))
        elif args.command=='render-sample':
            from .dos.content import ContentSource
            sample=ContentSource(args.source).sample(args.name,args.folder)
            if args.output.suffix.lower()!='.wav':raise GameError('Sample output must be a new .wav file.')
            data=sample.wav(args.rate);args.output.parent.mkdir(parents=True,exist_ok=True)
            with args.output.open('xb') as stream:stream.write(data)
            print(json.dumps({'path':str(args.output),'rate':args.rate,'frames':sample.frames(args.rate),'source_samples':len(sample.pcm)},indent=2))
        elif args.command=='play-sample':
            import time
            from .dos.content import ContentSource
            from .dos.sample_output import SamplePlayer
            sample=ContentSource(args.source).sample(args.name,args.folder);player=SamplePlayer()
            try:
                player.start(sample)
                while player.playing:time.sleep(.02)
                if player.error:raise GameError(player.error)
                print(json.dumps({'sample':args.name,'completed':player.completed,'consumed_frames':player.position()},indent=2))
            except KeyboardInterrupt:print('Sample stopped.')
            finally:player.stop()
        elif args.command == "inspect-save":
            print(json.dumps(LegacySave.read(args.source).describe(), indent=2))
        elif args.command == "edit-save":
            changes = {}
            for assignment in args.changes:
                key, value = assignment.split("=", 1)
                if key in changes:
                    raise GameError(f"Duplicate resource: {key}")
                changes[key] = int(value)
            export_legacy(args.source, args.destination, changes)
            print(f"Wrote {args.destination}; source unchanged.")
        elif args.command == "inspect-map":
            terrain = TerrainMap.read(args.source)
            print(json.dumps({"width": terrain.width, "height": terrain.height, "tiles": len(terrain.tiles), "distinct_tile_ids": len(set(terrain.tiles))}, indent=2))
        elif args.command == "audit":
            result = audit_installation(args.source)
            # Audit reports may never replace a source artifact.
            if args.output.resolve().is_relative_to(args.source.resolve()) and "opensource" not in args.output.resolve().relative_to(args.source.resolve()).parts:
                raise GameError("Write the report outside the source installation, or under opensource.")
            atomic_write(args.output, (json.dumps(result, indent=2) + "\n").encode())
            print(f"Audited {result['file_count']} files, {len(result['maps'])} maps, {len(result['production_candidates'])} production candidates; {len(result['errors'])} errors.")
        else:
            engine = Engine(load_game(args.load) if args.load else None, admin_enabled=args.admin)
            print("Prototype console. help / status / tick HOURS / quit. Admin " + ("enabled." if args.admin else "disabled."))
            while True:
                try:
                    line = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if line == "quit":
                    break
                try:
                    if line.startswith("tick "):
                        engine.apply("advance", hours=int(line[5:]))
                        print(f"Hour {engine.state.hour}")
                    else:
                        print(engine.console(line))
                except (GameError, ValueError) as exc:
                    print(f"Error: {exc}")
            if args.save:
                save_game(engine.state, args.save)
                print(f"Saved {args.save}")
    except (GameError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
