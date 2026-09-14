"""Original VECTORS records with a native shaded preview renderer.

324F6..32698 reads size, vertices, edges and 20-byte faces until -1.
Rasterization is a modern approximation; original fixed-point projection,
per-product articulation, palette shading and timing are not yet reproduced.
"""
import math
import struct

from ..core import GameError


def decode_model(data):
    if not isinstance(data, bytes) or not 2 <= len(data) <= 65536:
        raise GameError('Invalid product model size.')
    at, parts = 0, []
    def take(count):
        nonlocal at
        if at+count > len(data):
            raise GameError('Truncated product model.')
        value = data[at:at+count]
        at += count
        return value
    def word():
        return struct.unpack('<h', take(2))[0]
    while True:
        start = at
        size = word()
        if size == -1:
            break
        if not 0 < size <= 20000 or len(parts) >= 17:
            raise GameError('Invalid product model part.')
        n = word()
        if not 3 <= n <= 200:
            raise GameError('Invalid product vertex count.')
        points = tuple(struct.iter_unpack('<3h', take(n*6)))
        count = word()
        if not 0 <= count <= 600:
            raise GameError('Invalid product edge count.')
        edges = tuple(struct.iter_unpack('<BB', take(count*2)))
        if any(not 1 <= index <= n for edge in edges for index in edge):
            raise GameError('Product edge references a missing vertex.')
        count = word()
        if not 0 <= count <= 256:
            raise GameError('Invalid product face count.')
        faces = []
        for _ in range(count):
            record = take(20)
            end = record.find(b'\xff')
            if end == -1:
                end = 20
            if end < 3 or any(not 1 <= index <= n for index in record[:end]):
                raise GameError('Invalid product face.')
            faces.append(tuple(index-1 for index in record[:end]))
        if at-start-2 != size:
            raise GameError('Product part length disagrees with its record.')
        parts.append((points, tuple(faces)))
    if at != len(data) or not parts:
        raise GameError('Invalid product model terminator.')
    return tuple(parts)


def draw_model(target, parts, angle):
    """Bounded painter rendering into the original 114x115 model viewport."""
    radius = max(math.sqrt(x*x+y*y+z*z) for points, _ in parts for x, y, z in points) or 1
    scale = 49/radius
    ca, sa, ct, st = math.cos(angle), math.sin(angle), math.cos(.55), math.sin(.55)
    polygons = []
    for points, faces in parts:
        rotated = []
        for x, y, z in points:
            x, z = x*ca-z*sa, x*sa+z*ca
            y, z = y*ct-z*st, y*st+z*ct
            rotated.append((x*scale, y*scale, z*scale))
        for face in faces:
            vertices = [rotated[i] for i in face]
            a, b, c = vertices[:3]
            u, v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
            normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            length = math.sqrt(sum(n*n for n in normal)) or 1
            shade = int(65+155*abs((normal[0]*.25-normal[1]*.45+normal[2]*.86)/length))
            polygons.append((sum(p[2] for p in vertices)/len(vertices),
                             [(63+p[0], 112-p[1]) for p in vertices], (shade//5, shade//2, shade)))
    for _, vertices, color in sorted(polygons, key=lambda p:p[0]):
        for y in range(max(55, math.ceil(min(p[1] for p in vertices))), min(170, math.ceil(max(p[1] for p in vertices)))):
            cuts = []
            for a, b in zip(vertices, vertices[1:]+vertices[:1]):
                if min(a[1], b[1]) <= y+.5 < max(a[1], b[1]):
                    cuts.append(a[0]+(y+.5-a[1])*(b[0]-a[0])/(b[1]-a[1]))
            cuts.sort()
            for left, right in zip(cuts[::2], cuts[1::2]):
                left, right = max(6, math.ceil(left)), min(120, math.ceil(right))
                if right > left:
                    at = (y*320+left)*3
                    target.rgb[at:at+(right-left)*3] = bytes(color)*(right-left)
