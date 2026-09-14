"""Bounded native sprite composition for the recovered ground battlefield."""
from ..core import GameError, integer


def sprite_pixels(picture, x, y, width, height, direction=1):
    """Crop with the original identity/transpose/reverse/antitranspose mapping."""
    for value, label in ((x, "Sprite x"), (y, "Sprite y"), (width, "Sprite width"), (height, "Sprite height")):
        integer(value, label, minimum=1 if label in ("Sprite width", "Sprite height") else 0, maximum=2048)
    integer(direction, "Sprite direction", maximum=4)
    if x+width>picture.width or y+height>picture.height:raise GameError("Sprite exceeds its source atlas.")
    if direction not in (0, 1) and width!=height:raise GameError("Directional sprites must be square.")
    result = bytearray(width*height)
    for sy in range(height):
        for sx in range(width):
            dx, dy = (sx, sy) if direction in (0, 1) else (sy, sx) if direction==2 else (
                (width-1-sx, height-1-sy) if direction==3 else (width-1-sy, height-1-sx))
            result[dy*width+dx] = picture.pixels[(y+sy)*picture.width+x+sx]
    return bytes(result)


class GroundPixels:
    """Cache local source atlases and sprites; produce a 320x151 RGB viewport.

    Uses the recovered atlas palette colors. DOS palette quantization and the
    original text rasterizer are separate presentation work, not hidden here.
    """
    width, height = 320, 151

    def __init__(self, content, terrain):
        integer(terrain, "Battle terrain", minimum=1, maximum=11)
        self.atlases = {key: content.indexed_picture(name) for key, name in (
            ("terrain", f"WAR/GRF{terrain}.PIC"), ("panel", "WAR/GRWAR.PIC"),
            ("units", "WAR/GRICON.PIC"), ("effects", "WAR/GRICON2.PIC"))}
        for key, expected in (("terrain", (320, 200)), ("panel", (64, 200)), ("units", (320, 48)), ("effects", (320, 32))):
            picture = self.atlases[key]
            if (picture.width, picture.height)!=expected:raise GameError("Unsupported ground "+key+" atlas dimensions.")
        self.cache = {}
        background = bytearray(self.width*self.height*3)
        for y in range(self.height):
            for x in range(self.width):
                p = self.atlases["panel" if x<64 else "terrain"]
                index = p.pixels[(y+49)*p.width+x]
                at = (y*self.width+x)*3;background[at:at+3] = p.palette[index*3:index*3+3]
        self.background = bytes(background)

    def render(self, calls):
        result = bytearray(self.background)
        for call in calls:
            atlas = call["atlas"];direction = call.get("direction", 1)
            if direction==0:continue  # The original directional blitter draws nothing.
            if atlas=="terrain":
                source_x, source_y = call["source"];width, height = call["width"], call["height"]
                transparent = call["transparent"]
            elif atlas=="projectiles":
                atlas = "effects";source_x, source_y = 1+11*call["heading"], 16
                width, height = 11, 10;transparent = True
            else:
                source_x, source_y = (call["frame"]-1)*16, (call["bank"]-1)*16
                width = height = 16;transparent = True
            key = (atlas, source_x, source_y, width, height, direction)
            if key not in self.cache:
                if len(self.cache)>=1024:self.cache.clear()
                p = self.atlases[atlas]
                pixels = sprite_pixels(p, source_x, source_y, width, height, direction)
                self.cache[key] = [(value, p.palette[value*3:value*3+3]) for value in pixels]
            for at, (value, rgb) in enumerate(self.cache[key]):
                if transparent and value==0:continue
                x, y = call["x"]+at%width, call["y"]+at//width
                # DOS can address the frame buffer outside its visible viewport.
                # Native drawing clips sprites, preserving neighboring UI state.
                if not 64<=x<self.width or not 0<=y<self.height:continue
                dest = (y*self.width+x)*3;result[dest:dest+3] = rgb
        return bytes(result)

    def ppm(self, calls):
        return b"P6\n320 151\n255\n"+self.render(calls)
