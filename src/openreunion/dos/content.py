"""Original-file and self-contained extracted-bundle adapters for presentation."""
import json
from pathlib import Path
import struct

from ..core import GameError
from ..persistence import _unique_object
from .assets import read_picture, decode_converted_png
from .catalog import load_catalog, read_catalog
from .session import RecoveredSession
from .text import read_text,RAW_NAMES


class ContentSource:
    def __init__(self,path):
        self.root = Path(path).resolve()
        self.bundled = (self.root/"catalog.json").is_file()
        self.catalog = load_catalog(self.root/"catalog.json") if self.bundled else read_catalog(self.root/"GRWAR/REUNION.PRG")
        if not self.bundled:
            from .surface import read_surface_maps
            self.catalog["surface_maps"]=read_surface_maps(self.root)
            from .space_cinema import read_cinema_rules
            self.catalog["space_cinema"] = read_cinema_rules((self.root/"GRWAR/REUNION.PRG").read_bytes(),
                                                          (self.root/"WAR/ANIM/ANIM.DEF").read_bytes())
            from .dialogs import read_dialog_graphs,conversation,validate_definition
            graphs=read_dialog_graphs((self.root/"GRWAR/REUNION.PRG").read_bytes())
            self.catalog["dialogs"]={str(script):conversation(script,graphs,
                read_text(self.root/f"TEXT/KERDES{script}.AT"),read_text(self.root/f"TEXT/VALASZ{script}.AT")) for script in range(2,11)}
            for definition in self.catalog["dialogs"].values():validate_definition(definition)
            self.catalog["pirate_messages"]=read_text(self.root/"TEXT/PIRATE.TXT")[:10]
            from .bar_dialogs import read_rules
            self.catalog["bar_dialogs"]=read_rules((self.root/"GRWAR/REUNION.PRG").read_bytes(),lambda name:read_text(self.root/"TEXT"/name))
            from .advice import read_rules as read_advice
            self.catalog['commander_advice']=read_advice((self.root/'GRWAR/REUNION.PRG').read_bytes(),lambda name:read_text(self.root/'TEXT'/name))
        self.space_animation_cache = {}
        self.story_animation_cache = {}
        self.bridge_animation_cache = {}
        self.defeat_animation_cache = {}
        self.text_records = {}
        if self.bundled:
            with (self.root/"text.json").open("rb") as stream:
                data = stream.read(2*1024*1024+1)
            if len(data)>2*1024*1024:
                raise GameError("Extracted text exceeds size limit.")
            try:
                content = json.loads(data,object_pairs_hook=_unique_object)
                for record in content["decoded"]:
                    name,lines = record["path"],record["lines"]
                    if not isinstance(name,str) or not name.startswith("TEXT/") or name[5:] in self.text_records:
                        raise GameError("Invalid extracted text name.")
                    if not isinstance(lines,list) or len(lines)>10000 or any(not isinstance(line,str) or len(line)>255 for line in lines):
                        raise GameError("Invalid extracted text records.")
                    self.text_records[name[5:]] = lines
            except (ValueError,TypeError,KeyError,RecursionError) as exc:
                raise GameError(f"Invalid extracted text: {exc}") from exc

    def safe_path(self,path):
        path = (self.root/path).resolve()
        if not path.is_relative_to(self.root):
            raise GameError("Content path escapes its source folder.")
        return path

    def initial_session(self,save=None):
        """Legacy imported-start adapter retained for recorded journey replays."""
        if save is not None and Path(save).suffix.lower()=='.json':return RecoveredSession.load(self.catalog,save)
        if self.bundled:
            return RecoveredSession.load(self.catalog,save or self.root/"sessions/SPIDYSAV.1.json")
        return RecoveredSession.from_dos(self.catalog,save or self.root/"SAVE/SPIDYSAV.1")

    def startup_data(self):
        from .new_game import extract_startup
        if not self.bundled:
            return extract_startup((self.root/'GRWAR/REUNION.PRG').read_bytes(),
                                   (self.root/'SAVE/INIT').read_bytes())
        from ..persistence import _unique_object
        try:
            with self.safe_path('startup.json').open('rb') as stream:
                raw=stream.read(200001)
        except FileNotFoundError as exc:
            raise GameError('This content bundle lacks new-game data. Extract the original content again.') from exc
        if len(raw)>200000:raise GameError('New-game data exceeds size limit.')
        try:return json.loads(raw,object_pairs_hook=_unique_object)
        except (ValueError,RecursionError) as exc:raise GameError('Invalid new-game data.') from exc

    def new_game(self,*,seed=1994,hero=2):
        from .new_game import new_session
        return new_session(self.startup_data(),self.catalog,seed=seed,hero=hero)

    def pictures(self):
        if self.bundled:
            return sorted(p.relative_to(self.root/"pictures").with_suffix(".PIC").as_posix()
                          for p in (self.root/"pictures").glob("*/*.png") if not p.is_symlink())
        paths = []
        for folder in sorted(self.root.iterdir()):
            if folder.is_dir() and not folder.is_symlink() and not folder.name.startswith(".") and folder.name != "opensource":
                paths.extend(p.relative_to(self.root).as_posix() for p in sorted(folder.glob("*.PIC")) if not p.is_symlink())
        return paths

    def picture(self,name):
        if not self.bundled:
            picture = read_picture(self.safe_path(name))
            return picture.png(),picture.width,picture.height
        path = self.safe_path(Path("pictures")/Path(name).with_suffix(".png"))
        with path.open("rb") as stream:
            data = stream.read(3*1024*1024+1)
        if len(data)>3*1024*1024 or len(data)<33 or data[:8]!=b"\x89PNG\r\n\x1a\n" or data[12:16]!=b"IHDR":
            raise GameError("Invalid or oversized converted PNG.")
        width,height = struct.unpack_from(">II",data,16)
        if not 1<=width<=2048 or not 1<=height<=2048 or width*height>1048576:
            raise GameError("Converted PNG dimensions exceed limits.")
        return data,width,height

    def texts(self):
        if self.bundled:
            return sorted(self.text_records)
        return [p.name for p in sorted((self.root/"TEXT").iterdir())
                if (p.suffix.upper() in (".SP",".AT",".LOC",".TXT") or p.name.upper() in RAW_NAMES) and not p.is_symlink()]

    def description(self,kind,identity):
        from .descriptions import product_description,candidate_description
        from .building_information import building_description
        formats={'product':('SZ_TALAL.RAW',product_description),'candidate':('SZ_FACE.RAW',candidate_description),
                 'building':('SZ_FELSZ.TXT',building_description)}
        if kind not in formats:raise GameError('Unknown description type.')
        name,decode=formats[kind]
        if self.bundled and name not in self.text_records:
            raise GameError('Descriptions are missing; extract the original content again.')
        return decode(self.text(name),identity)

    def race_profile(self,owner):
        from .race_info import TEXT_NAME,profile
        if self.bundled and TEXT_NAME not in self.text_records:
            raise GameError('Race profiles are missing; extract the original content again.')
        return profile(self.text(TEXT_NAME),owner)

    def indexed_picture(self,name):
        """Original palette IDs for sprites, in both content-source modes."""
        if not self.bundled:return read_picture(self.safe_path(name))
        return decode_converted_png(self.picture(name)[0])

    def fm_music(self,name):
        from .fm_music import MUSIC_NAMES,MAX_MUSIC_BYTES,CONVERTED_MAGIC,decode_music,decode_converted_music
        if name not in MUSIC_NAMES:raise GameError('Unknown FM music name.')
        path=self.safe_path(Path('music/fm')/(name+'.ofm') if self.bundled else Path('GRWAR')/(name+'.PIC'))
        with path.open('rb') as stream:data=stream.read(MAX_MUSIC_BYTES+len(CONVERTED_MAGIC)+1)
        return decode_converted_music(data) if self.bundled else decode_music(data)

    def product_model_data(self, product_id):
        from ..core import integer
        from .product_models import decode_model
        integer(product_id, 'Product model', minimum=1, maximum=35)
        path = self.safe_path(f'models/V{product_id}.VEC' if self.bundled else f'VECTORS/V{product_id}.VEC')
        try:
            with path.open('rb') as stream:
                data = stream.read(65537)
        except FileNotFoundError as exc:
            raise GameError('Product models are missing; extract the original content again.') from exc
        decode_model(data)
        return data

    def control_icons(self):
        from .control_panel import decode_icons,decode_converted_icons
        path=self.safe_path('controls/icons.ori' if self.bundled else 'ICON/ICON.ALL')
        with path.open('rb') as stream:data=stream.read(131073)
        return decode_converted_icons(data) if self.bundled else decode_icons(data)

    def sample(self,name,folder='SOUND'):
        from .samples import SAMPLE_FOLDERS,MAX_PCM,decode_sample,decode_converted_sample
        if not isinstance(name,str) or not 1<=len(name)<=8 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name.upper()):
            raise GameError('Invalid sound sample name.')
        if folder not in SAMPLE_FOLDERS:raise GameError('Invalid sound sample folder.')
        stem=name.upper()
        path=self.safe_path(f'samples/{folder}/{stem}.ors' if self.bundled else f'{folder}/{stem}.SMP')
        with path.open('rb') as stream:data=stream.read(MAX_PCM+11)
        return decode_converted_sample(data) if self.bundled else decode_sample(data)

    def text(self,name):
        if self.bundled:
            if name not in self.text_records:
                raise GameError("Unknown text record file.")
            return self.text_records[name]
        return read_text(self.safe_path(Path("TEXT")/name))

    def bridge_animation(self,asset,frame):
        """Original MAIN1..6 cumulative idle frames, using the Control Room palette."""
        from ..core import integer
        from .animation import decode_frame
        from .assets import Picture
        from .story_cinema import read_main_animation,draw_frame
        integer(asset,'Bridge animation asset',minimum=1,maximum=6)
        row=self.catalog['story_cinema'][asset-1]
        integer(frame,'Bridge animation frame',minimum=1,maximum=row['frames'])
        if self.bundled:
            with self.safe_path(f'animations/bridge/MAIN{asset}/{frame}.png').open('rb') as stream:
                data=stream.read(3*1024*1024+1)
            picture=decode_converted_png(data)
            if (picture.width,picture.height)!=(row['width'],row['height']):
                raise GameError('Converted bridge animation dimensions disagree.')
            return picture
        if asset not in self.bridge_animation_cache:
            with self.safe_path(f'ANIM/MAIN{asset}.ANI').open('rb') as stream:
                data=stream.read(2*1024*1024+1)
            encoded,tail=read_main_animation(data,row)
            if tail:raise GameError('Unexpected bridge animation tail.')
            if encoded[0] is None:raise GameError('Bridge animation has no complete first frame.')
            previous=decode_frame(encoded[0])[2];frames=[previous]
            for index in range(2,len(encoded)+1):
                previous=draw_frame(encoded,index,previous);frames.append(previous)
            palette=self.indexed_picture('GRAFIKA/MAIN.PIC').palette
            self.bridge_animation_cache[asset]=(tuple(frames),palette)
        frames,palette=self.bridge_animation_cache[asset]
        return Picture(row['width'],row['height'],frames[frame-1],palette)

    def story_animation(self,asset,frame):
        from .story_cinema import STORY_ASSETS,read_main_animation,draw_frame
        from .animation import decode_frame
        from ..core import integer
        if type(asset) is not int or asset not in STORY_ASSETS:raise GameError('Unsupported story animation asset.')
        if 'story_cinema' not in self.catalog:raise GameError('Story animation data is missing; re-extract the content.')
        row=self.catalog['story_cinema'][asset-1]
        integer(frame,'Story animation frame',minimum=1,maximum=row['frames'])
        if self.bundled:
            with self.safe_path(f'animations/story/MAIN{asset}/{frame}.png').open('rb') as stream:data=stream.read(3*1024*1024+1)
            picture=decode_converted_png(data)
            if (picture.width,picture.height)!=(row['width'],row['height']):raise GameError('Converted story animation dimensions disagree.')
            return picture
        if asset not in self.story_animation_cache:
            with self.safe_path(f'ANIM/MAIN{asset}.ANI').open('rb') as stream:data=stream.read(2*1024*1024+1)
            encoded,_=read_main_animation(data,row)
            if encoded[0] is None:raise GameError('Story animation has no complete first frame.')
            previous=decode_frame(encoded[0])[2];frames=[previous]
            for index in range(2,len(encoded)+1):
                previous=draw_frame(encoded,index,previous);frames.append(previous)
            palette=self.indexed_picture(f'PICS/PIC{STORY_ASSETS[asset]}.PIC').palette
            if len(self.story_animation_cache)>=2:self.story_animation_cache.pop(next(iter(self.story_animation_cache)))
            self.story_animation_cache[asset]=(tuple(frames),palette)
        from .assets import Picture
        frames,palette=self.story_animation_cache[asset]
        return Picture(row['width'],row['height'],frames[frame-1],palette)

    def prepare_story_scene(self,scene):
        """Decode original animation data before starting the presentation clock.

        No script operation is executed here. Cached frames/palettes have no
        controller state, requests, input or RNG; the cache holds two assets.
        Converted frames already decode individually with bounded cost.
        """
        from .story_cinema import scene_script
        if not self.bundled:
            for operation in scene_script(scene,self.catalog['story_cinema']):
                if operation[0]=='select':self.story_animation(operation[1],1)

    def victory_picture(self,name):
        from .victory_cinema import PICTURES
        if name not in PICTURES:raise GameError('Unknown victory picture.')
        if not hasattr(self,'victory_picture_cache'):self.victory_picture_cache={}
        if name not in self.victory_picture_cache:
            picture=self.indexed_picture(f'VICTORY/{name}.PIC')
            if (picture.width,picture.height)!=(320,200):raise GameError('Invalid victory picture dimensions.')
            self.victory_picture_cache[name]=picture
        return self.victory_picture_cache[name]

    def victory_animation(self,frame):
        from ..core import integer
        from .victory_cinema import ANIMATION_RULE
        from .story_cinema import read_main_animation,draw_frame
        from .assets import Picture
        integer(frame,'Victory animation frame',minimum=1,maximum=16)
        if self.bundled:
            if not hasattr(self,'victory_converted_frames'):self.victory_converted_frames={}
            if frame in self.victory_converted_frames:return self.victory_converted_frames[frame]
            with self.safe_path(f'animations/victory/ANIM1/{frame}.png').open('rb') as stream:data=stream.read(3*1024*1024+1)
            picture=decode_converted_png(data)
            if (picture.width,picture.height)!=(320,200):raise GameError('Invalid victory animation dimensions.')
            self.victory_converted_frames[frame]=picture
            return picture
        if not hasattr(self,'victory_animation_cache'):
            with self.safe_path('VICTORY/ANIM1.ANI').open('rb') as stream:data=stream.read(2*1024*1024+1)
            encoded,tail=read_main_animation(data,ANIMATION_RULE)
            # The original table plays 16 records; retain the unused tail in
            # research reports without interpreting extra records as gameplay.
            picture=self.victory_picture('PAL1');pixels=picture.pixels;frames=[]
            for index in range(1,17):
                pixels=draw_frame(encoded,index,pixels);frames.append(Picture(320,200,pixels,picture.palette))
            self.victory_animation_cache=frames
        return self.victory_animation_cache[frame-1]

    def module_music(self,name):
        from .module_music import MODULE_NAMES,MAX_MODULE_BYTES,decode_module
        if name not in MODULE_NAMES:raise GameError('Unknown original module music.')
        relative=(f'music/mod/{name}.mod' if self.bundled else 'CREDITS/STEAL2.MOD' if name=='STEAL2'
                  else 'VICTORY/ENDSEQ.MOD' if name=='ENDSEQ' else f'ANIM/{name}.SPD')
        with self.safe_path(relative).open('rb') as stream:data=stream.read(MAX_MODULE_BYTES+1)
        return decode_module(data)

    def intro_music(self,name):
        from .intro_cinema import TRACKS
        from .intro_music import decode_intro_module
        from .module_music import MAX_MODULE_BYTES
        if name not in TRACKS:raise GameError('Unknown intro module music.')
        relative=f'music/intro/{name}.mod' if self.bundled else f'INTRO/{name}.MOD'
        with self.safe_path(relative).open('rb') as stream:data=stream.read(MAX_MODULE_BYTES+1)
        return decode_intro_module(data)

    def intro_picture(self,name):
        from .intro_cinema import LOW_PICTURES
        if name not in LOW_PICTURES:raise GameError('Unknown intro picture.')
        picture=self.indexed_picture(f'INTRO/{name}.PIC')
        expected=(320,256) if name=='PAL14' else (320,200)
        if (picture.width,picture.height)!=expected:raise GameError('Invalid intro picture dimensions.')
        return picture

    def intro_high_resolution(self,prefix):
        from .intro_assets import PICTURE_PREFIXES,assemble_high_resolution,high_resolution_picture
        if prefix not in PICTURE_PREFIXES:raise GameError('Unknown high-resolution intro picture.')
        if not self.bundled:return high_resolution_picture(self.root/'INTROP',prefix)
        return assemble_high_resolution(
            [self.indexed_picture(f'INTROP/{prefix}{index}.PIC') for index in range(1,6)],prefix)

    def intro_animation(self,asset):
        from .intro_assets import FRAME_COUNTS,animation_frames,decode_converted_animation
        if type(asset) is not int or asset not in FRAME_COUNTS:raise GameError('Unknown intro animation.')
        if not hasattr(self,'intro_animation_cache'):self.intro_animation_cache={}
        if asset not in self.intro_animation_cache:
            relative=(f'animations/intro/ANIM{asset}.oria' if self.bundled else f'INTRO/ANIM{asset}.ANI')
            with self.safe_path(relative).open('rb') as stream:data=stream.read(2*1024*1024+8)
            frames=(decode_converted_animation(data,asset) if self.bundled else animation_frames(data,asset)[0])
            self.intro_animation_cache[asset]=frames
        return self.intro_animation_cache[asset]

    def disk_animation(self,frame):
        from ..core import integer
        from .animation import read_animation
        from .assets import Picture
        integer(frame,'CD tray frame',minimum=1,maximum=23)
        if not hasattr(self,'disk_animation_cache'):self.disk_animation_cache={}
        if frame not in self.disk_animation_cache:
            if self.bundled:
                with self.safe_path(f'animations/disk/MAIN17/{frame}.png').open('rb') as stream:data=stream.read(3*1024*1024+1)
                picture=decode_converted_png(data)
                if (picture.width,picture.height)!=(100,49):raise GameError('Invalid CD tray frame dimensions.')
                self.disk_animation_cache[frame]=picture
            else:
                with self.safe_path('ANIM/MAIN17.ANI').open('rb') as stream:data=stream.read(2*1024*1024+1)
                frames=read_animation(data,frames=23,width=100,height=49)
                palette=self.indexed_picture('GRAFIKA/DISK.PIC').palette
                self.disk_animation_cache.update({i:Picture(100,49,pixels,palette) for i,pixels in enumerate(frames,1)})
        return self.disk_animation_cache[frame]

    def credits_picture(self,name):
        from .credits_cinema import PICTURES
        from .credits_assets import high_resolution_picture
        if name not in PICTURES:raise GameError('Unknown Game Credits picture.')
        if name=='HIGHRES' and not self.bundled:return high_resolution_picture(self.root/'CREDITS')
        picture=self.indexed_picture('CREDITS/'+name+'.PIC')
        if (picture.width,picture.height)!=((640,480) if name=='HIGHRES' else (320,200)):
            raise GameError('Invalid Game Credits picture dimensions.')
        return picture

    def credits_animation(self,asset,frame):
        from .credits_assets import displayed_frames,original_frames
        if type(frame) is not int or frame not in displayed_frames(asset):raise GameError('Invalid displayed credits frame.')
        if not hasattr(self,'credits_frame_cache'):self.credits_frame_cache={}
        key=(asset,frame)
        if key not in self.credits_frame_cache:
            if self.bundled:
                with self.safe_path(f'animations/credits/ANIM{asset}/{frame}.png').open('rb') as stream:
                    data=stream.read(3*1024*1024+1)
                picture=decode_converted_png(data)
                if (picture.width,picture.height)!=(320,200):raise GameError('Invalid credits frame dimensions.')
                self.credits_frame_cache[key]=picture
            else:
                self.credits_frame_cache.update({(a,i):p for a,i,p in original_frames(self.root/'CREDITS')})
        return self.credits_frame_cache[key]

    def defeat_animation(self,asset,step):
        from .defeat_cinema import ANIMATIONS,animation_index
        from .story_cinema import read_main_animation,draw_frame
        from .assets import Picture
        if asset not in ANIMATIONS:raise GameError('Unknown defeat animation.')
        row=self.catalog['story_cinema'][asset-1];count=row['frames']
        index=animation_index(asset,step,count)
        if self.bundled:
            path=self.safe_path(f'animations/defeat/MAIN{asset}/{index}.png')
            try:
                with path.open('rb') as stream:data=stream.read(3*1024*1024+1)
            except FileNotFoundError as exc:raise GameError('Defeat animation content is missing; extract the original content again.') from exc
            picture=decode_converted_png(data)
            if (picture.width,picture.height)!=(320,200):raise GameError('Invalid defeat animation dimensions.')
            return picture
        if asset not in self.defeat_animation_cache:
            with self.safe_path(f'ANIM/MAIN{asset}.ANI').open('rb') as stream:data=stream.read(2*1024*1024+1)
            encoded,tail=read_main_animation(data,row)
            if tail:raise GameError('Unexpected defeat animation tail.')
            picture=self.indexed_picture(f'GRAFIKA/{ANIMATIONS[asset][0]}.PIC')
            pixels=picture.pixels[:64000];frames=[]
            for draw in range(1,count*2+1):
                pixels=draw_frame(encoded,draw%count+1,pixels);frames.append(pixels)
            self.defeat_animation_cache[asset]=(frames,picture.palette)
        frames,palette=self.defeat_animation_cache[asset]
        return Picture(320,200,frames[index-1],palette)

    def space_animation(self,asset,frame):
        from ..core import integer
        from .animation import read_animation
        from .assets import Picture
        integer(asset,"Space animation asset",minimum=1,maximum=25)
        rules=self.catalog.get("space_cinema")
        if rules is None:raise GameError("Cinematic tables are missing; re-extract the content.")
        count,width,height,_,_=rules["assets"][asset-1]
        integer(frame,"Space animation frame",minimum=1,maximum=count)
        if self.bundled:
            with self.safe_path(f"animations/space/SA{asset}/{frame}.png").open("rb") as stream:data=stream.read(3*1024*1024+1)
            picture=decode_converted_png(data)
            if (picture.width,picture.height)!=(width,height):raise GameError("Converted animation dimensions disagree.")
            return picture
        if asset not in self.space_animation_cache:
            with self.safe_path(f"WAR/WAR/SA{asset}.ANI").open("rb") as stream:data=stream.read(2*1024*1024+1)
            decoded=read_animation(data,frames=count,width=width,height=height)
            if len(self.space_animation_cache)>=3:self.space_animation_cache.pop(next(iter(self.space_animation_cache)))
            self.space_animation_cache[asset]=decoded
        return Picture(width,height,self.space_animation_cache[asset][frame-1],self.indexed_picture("WAR/SPWAR.PIC").palette)
