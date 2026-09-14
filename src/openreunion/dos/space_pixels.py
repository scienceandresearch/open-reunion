"""Original radar sprites, background and scanline compositor, without Tk."""
from ..core import GameError
from .space_presentation import validate_space_presentation


class SpacePixels:
    width, height = 320, 151

    def __init__(self, content, presentation):
        self.content=content;self.cinema_cache={};self.results=None
        validate_space_presentation(presentation);self.spans = presentation["radar_spans"]
        self.atlases = {name: content.indexed_picture("WAR/"+file+".PIC") for name, file in (
            ("panel", "SPWAR"), ("radar", "SPHATTER"), ("sprites", "SPANTS"),
            ("victory", "SPVICT"), ("defeat", "SPLOST"))}
        for name, size in (("panel", (320, 151)), ("radar", (160, 151)), ("sprites", (80, 48)),
                           ("victory", (320, 151)), ("defeat", (320, 151))):
            p = self.atlases[name]
            if (p.width, p.height) != size:raise GameError("Unsupported space "+name+" picture size.")
        self.rgb = {key: p.rgb() for key, p in self.atlases.items()}
        self.cache = {}

    def sprite(self, call):
        """0x16612..0x1671D: opaque ship shapes; transparent 7x7 explosions."""
        key = (call["kind"], call["hull"], call.get("side"), call.get("step"))
        if key not in self.cache:
            hull = call["hull"];rows = [];picture = self.atlases["sprites"]
            if call["kind"] == "explosion":
                sx = 1+8*(call["step"]-1);sy = 1+8*(hull+1)
                rows = [(1, y, sx, sy+y, 7) for y in range(7)]
            else:
                bank = 8 if call["side"] == "hostile" else 0
                rows = {1: [(0, 0, 1, 1+bank, 1)], 2: [(0, 0, 9, 1+bank, 2)],
                    3: [(1, 0, 18, 1+bank, 2), (0, 1, 17, 2+bank, 4), (1, 2, 18, 3+bank, 2)],
                    4: [(1, 0, 26, 1+bank, 4), (0, 1, 25, 2+bank, 6), (1, 2, 26, 3+bank, 4)]}[hull]
            pixels = []
            for dx, dy, sx, sy, width in rows:
                if sx < 0 or sy < 0 or sx+width > 80 or sy >= 48:raise GameError("Space sprite exceeds its atlas.")
                for x in range(width):
                    value = picture.pixels[sy*80+sx+x]
                    # The shared DOS palette maps the asset's transparent index
                    # zero to 0x40. Preserve native index identity, not RGB equality.
                    if call["kind"] != "explosion" or value != 0:
                        pixels.append((dx+x, dy, picture.palette[value*3:value*3+3]))
            if len(self.cache) >= 128:self.cache.clear()
            self.cache[key] = pixels
        return self.cache[key]

    def radar(self, calls):
        result = bytearray(self.rgb["radar"])
        for call in calls:
            for dx, dy, color in self.sprite(call):
                x, y = call["x"]+dx, call["y"]+dy
                # Avoid DOS's row wrapping and out-of-buffer writes.
                if 0 <= x < 160 and 0 <= y < 151:
                    at = (y*160+x)*3;result[at:at+3] = color
        return bytes(result)

    def render(self, calls, *, result=None, cinema=None,losses=None,fade_step=5):
        if result is not None:
            if losses is not None:
                if self.results is None:
                    from .battle_results import BattleResultPictures
                    self.results=BattleResultPictures(self.content)
                return self.results.picture('space',result,losses,fade_step=fade_step).rgb()
            return self.rgb["victory" if result else "defeat"]
        radar = self.radar(calls);frame = bytearray(self.rgb["panel"])
        for source, destination, count in self.spans:
            frame[destination*3:(destination+count)*3] = radar[source*3:(source+count)*3]
        if cinema is not None:
            def clear(rect):
                x,y,width,height=rect
                left,right=max(160,x),min(320,x+width)
                for row in range(max(49,y),min(200,y+height)):
                    start=((row-49)*320+left)*3;frame[start:start+max(0,right-left)*3]=bytes(max(0,right-left)*3)
            if cinema["black"]:clear([160,49,160,151])
            if cinema["picture"] is not None:
                asset,index=cinema["picture"];key=(asset,index)
                if key not in self.cinema_cache:
                    picture=self.content.space_animation(asset,index)
                    if len(self.cinema_cache)>=12:self.cinema_cache.clear()
                    self.cinema_cache[key]=picture.rgb()
                _,width,height,x,y=self.content.catalog["space_cinema"]["assets"][asset-1]
                pixels=self.cinema_cache[key]
                for row in range(height):
                    start=((y-49+row)*320+x)*3
                    frame[start:start+width*3]=pixels[row*width*3:(row+1)*width*3]
            for rect in cinema["clears"]:clear(rect)
        return bytes(frame)

    def ppm(self, calls, *, result=None, cinema=None,losses=None,fade_step=5):
        return b"P6\n320 151\n255\n"+self.render(calls, result=result, cinema=cinema,losses=losses,fade_step=fade_step)
