"""Island map rendering with Pillow (safe in worker threads).

Every block is drawn in its real colours: the top face of the block's own item icon is warped into a square texture,
and its average colour is used when zoomed out. Terrain gets terrace shading (a block lower than its north / west
neighbour sits in shadow), the sea is coloured by depth with the seabed showing through the shallows, and placed
objects are tinted with the average colour of their icon.
"""
import os
import random
import struct

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import pokopia_extras as px
import pokopia_island as pi
import pokopia_save as ps

TEX = 16                 # texture size of one block in detailed tiles
TILE = 32 * TEX          # one chunk per tile
# top face of the block cube in a 72 x 72 item icon: upper-left, lower-left, lower-right, upper-right
_QUAD = ((12.5, 12.5), (19.0, 31.0), (62.0, 22.5), (45.0, 9.0))
SEA_IDS = (349, 389)
LIQUID_STYLE = {   # block id -> (shallow colour, deep colour)
    349: ((96, 214, 214), (18, 74, 148)), 389: ((96, 214, 214), (18, 74, 148)),
    383: ((110, 200, 236), (34, 108, 186)), 384: ((168, 232, 228), (88, 178, 196)),
    388: ((150, 128, 88), (92, 72, 46)), 386: ((255, 150, 40), (226, 72, 20)),
}
FALLBACK = {   # blocks without an icon of their own
    pi.BEDROCK: (64, 64, 72), 21: (122, 84, 56), 24: (110, 74, 50), 44: (102, 70, 46), 172: (86, 58, 40),
    369: (122, 84, 56), 283: (120, 60, 40),
}
SUN = 1.0


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _ramp(stops, n=256):
    out = []
    for v in range(n):
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= v <= p1:
                out.append(_lerp(c0, c1, (v - p0) / max(1, p1 - p0)))
                break
        else:
            out.append(stops[-1][1] if v > stops[-1][0] else stops[0][1])
    return out


def _lut_rgb(gray, ramp):
    return Image.merge('RGB', tuple(gray.point([c[i] for c in ramp]) for i in range(3)))


def _hash_color(bid):
    h = (bid * 2654435761) & 0xFFFFFFFF
    return 110 + (h & 63), 116 + (h >> 8 & 63), 84 + (h >> 16 & 47)


class Look:
    """Colours and textures of blocks and objects, from the item icons in data/icons/items."""

    def __init__(self):
        self.icons = px.Icons()
        self._tex, self._col, self._icol, self._iimg = {}, {}, {}, {}
        self._shaded = {}

    def _icon(self, item):
        if item in self._iimg:
            return self._iimg[item]
        im = None
        path = self.icons.item_path(item, fallback=False) if item else None
        if path:
            try:
                im = Image.open(path).convert('RGBA')
            except Exception:
                im = None
        self._iimg[item] = im
        return im

    def texture(self, bid, size=TEX):
        """size x size RGB top texture of a block (None for liquids)."""
        bid &= pi.ID_MASK
        if size != TEX:
            key = (bid, size)
            if key not in self._tex:
                t = self.texture(bid)
                self._tex[key] = t.resize((size, size), Image.LANCZOS) if t is not None else None
            return self._tex[key]
        if bid in self._tex:
            return self._tex[bid]
        tex = None
        item, kind = pi.block_item(bid), pi.block_kind(bid)
        if kind != pi.K_LIQUID:
            icon = self._icon(item) if item else None
            if icon is not None and icon.size == (72, 72):
                cx = sum(p[0] for p in _QUAD) / 4
                cy = sum(p[1] for p in _QUAD) / 4
                q = []
                for x, y in _QUAD:
                    q += [x + (cx - x) * 0.14, y + (cy - y) * 0.14]
                t = icon.transform((TEX * 2, TEX * 2), Image.QUAD, q, Image.BICUBIC)
                bg = Image.new('RGB', t.size, self.color(bid, from_tex=False))
                bg.paste(t, mask=t.getchannel('A'))
                tex = bg.resize((TEX, TEX), Image.LANCZOS)
            else:
                c = FALLBACK.get(bid) or _hash_color(bid)
                tex = Image.new('RGB', (TEX, TEX), c)
                rnd = random.Random(bid)
                px_ = tex.load()
                for yy in range(TEX):
                    for xx in range(TEX):
                        f = 0.9 + rnd.random() * 0.2
                        px_[xx, yy] = tuple(min(255, int(v * f)) for v in c)
        self._tex[bid] = tex
        return tex

    def color(self, bid, from_tex=True):
        """Average top colour of a block."""
        bid &= pi.ID_MASK
        key = (bid, from_tex)
        if key in self._col:
            return self._col[key]
        c = None
        kind = pi.block_kind(bid)
        if kind == pi.K_LIQUID:
            c = LIQUID_STYLE.get(bid, LIQUID_STYLE[389])[0]
        elif bid in FALLBACK:
            c = FALLBACK[bid]
        else:
            icon = self._icon(pi.block_item(bid)) if kind else None
            if icon is not None and icon.size == (72, 72):
                # average of the top face area
                cx = sum(p[0] for p in _QUAD) / 4
                cy = sum(p[1] for p in _QUAD) / 4
                crop = icon.crop((int(cx - 9), int(cy - 4), int(cx + 9), int(cy + 4))).convert('RGB')
                c = crop.resize((1, 1), Image.BOX).getpixel((0, 0))
            if c is None:
                c = _hash_color(bid)
        self._col[key] = c
        return c

    def item_color(self, item):
        """Average colour of an item's icon (objects are tinted with it)."""
        if item in self._icol:
            return self._icol[item]
        c = (150, 160, 170)
        icon = self._icon(item) if item else None
        if icon is not None:
            a = icon.getchannel('A').point(lambda v: 255 if v > 160 else 0)
            rgb = icon.convert('RGB')
            if a.getbbox():
                # mean over opaque pixels
                hist_n = sum(a.histogram()[255:])
                if hist_n:
                    r = sum(i * n for i, n in enumerate(ImageChops.multiply(rgb.getchannel('R'), a).histogram())) / hist_n
                    g = sum(i * n for i, n in enumerate(ImageChops.multiply(rgb.getchannel('G'), a).histogram())) / hist_n
                    b = sum(i * n for i, n in enumerate(ImageChops.multiply(rgb.getchannel('B'), a).histogram())) / hist_n
                    c = (int(r), int(g), int(b))
        self._icol[item] = c
        return c

    def table(self):
        """bytes: 3 per block id, the average colours (for fast whole-image colouring)."""
        return [bytes(self.color(b)) for b in range(2048)]


LOOK = None


def look():
    global LOOK
    if LOOK is None:
        LOOK = Look()
    return LOOK


# ---------------------------------------------------------------------------------------------------- shading
def _region_bytes(arr, W, x0, z0, x1, z1):
    if x0 == 0 and x1 == W:
        return arr[z0 * W:z1 * W]
    out = bytearray()
    for z in range(z0, z1):
        out += arr[z * W + x0:z * W + x1]
    return out


def _region_ids(arr, W, x0, z0, x1, z1):
    out = []
    for z in range(z0, z1):
        out.extend(arr[z * W + x0:z * W + x1])
    return out


def shade_layers(isl, x0, z0, x1, z1):
    """Height-based layers for an image-pixel region [x0, x1) x [z0, z1) (with its 1-pixel border computed from
    real neighbours). Returns dict of L images the size of the region."""
    W, H = isl.width, isl.height
    ax0, az0, ax1, az1 = max(0, x0 - 1), max(0, z0 - 1), min(W, x1 + 1), min(H, z1 + 1)
    w, h = ax1 - ax0, az1 - az0
    top = Image.frombytes('L', (w, h), bytes(_region_bytes(isl.top_h, W, ax0, az0, ax1, az1)))
    flo = Image.frombytes('L', (w, h), bytes(_region_bytes(isl.floor_h, W, ax0, az0, ax1, az1)))
    nodata = top.point(lambda v: 255 if v == 255 else 0)
    depth = ImageChops.subtract(top, flo).point(lambda v: 0 if v > 200 else v)
    water = depth.point(lambda v: 255 if v else 0)
    # depth for colouring: smoothed so the sea floor's bumps do not show as blotches
    sdepth = ImageChops.lighter(depth.filter(ImageFilter.BoxBlur(2)), depth.point(lambda v: min(v, 3)))
    land = ImageChops.subtract(ImageChops.invert(water), nodata)
    # neighbours (north = row above, west = column to the left); edges repeat themselves
    def nb(img, dx, dz):
        o = ImageChops.offset(img, dx, dz)
        if dz > 0:
            o.paste(img.crop((0, 0, w, dz)), (0, 0))
        if dx > 0:
            o.paste(img.crop((0, 0, dx, h)), (0, 0))
        if dz < 0:
            o.paste(img.crop((0, h + dz, w, h)), (0, h + dz))
        if dx < 0:
            o.paste(img.crop((w + dx, 0, w, h)), (w + dx, 0))
        return o
    g = flo.point(lambda v: 0 if v == 255 else v)
    gn, gw = nb(g, 0, 1), nb(g, 1, 0)
    # (neighbour - me): positive = neighbour higher = shadow on me
    sh_n = ImageChops.subtract(gn, g, 1.0, 0)
    sh_w = ImageChops.subtract(gw, g, 1.0, 0)
    li_n = ImageChops.subtract(g, gn, 1.0, 0)
    li_w = ImageChops.subtract(g, gw, 1.0, 0)
    dark = ImageChops.add(sh_n.point(lambda v: min(255, v * 46 + (18 if v else 0))),
                          sh_w.point(lambda v: min(255, v * 22)))
    light = ImageChops.add(li_n.point(lambda v: min(255, v * 26)), li_w.point(lambda v: min(255, v * 12)))
    # gentle altitude tint: higher ground a little brighter
    alt = g.point(lambda v: max(0, min(60, (v - pi.SEA_LEVEL) * 2)))
    light = ImageChops.add(light, alt)
    dark = ImageChops.multiply(dark.point(lambda v: min(150, v)), land)
    light = ImageChops.multiply(light.point(lambda v: min(90, v)), land)
    # shore: land touching water, water touching land
    wet = ImageChops.multiply(water.filter(ImageFilter.MaxFilter(3)), land)
    foam = ImageChops.multiply(land.filter(ImageFilter.MaxFilter(3)), water)
    out = dict(nodata=nodata, depth=depth, sdepth=sdepth, water=water, land=land, dark=dark, light=light, wet=wet, foam=foam,
               near=land.filter(ImageFilter.BoxBlur(3)))
    cx0, cz0 = x0 - ax0, z0 - az0
    box = (cx0, cz0, cx0 + (x1 - x0), cz0 + (z1 - z0))
    return {k: v.crop(box) for k, v in out.items()}


def _liquid_colour(depth, top_ids_img, near):
    """RGB water colour from depth (and closeness to land) for the sea; other liquids by id."""
    sea = _lut_rgb(depth.point(lambda v: min(255, v * 22)),
                   _ramp([(0, (110, 224, 222)), (40, (64, 190, 214)), (90, (36, 140, 200)), (160, (24, 98, 170)),
                          (255, (16, 66, 138))]))
    # brighter right next to the shore
    sea = Image.composite(Image.blend(sea, Image.new('RGB', sea.size, (180, 240, 236)), 0.35), sea,
                          near.point(lambda v: min(255, v * 2)))
    return sea


def render_region(isl, x0, z0, x1, z1):
    """RGBA image of a region at one pixel per block (transparent where there is no island)."""
    L = look()
    W = isl.width
    w, h = x1 - x0, z1 - z0
    lay = shade_layers(isl, x0, z0, x1, z1)
    table = L.table()
    ground = Image.frombytes('RGB', (w, h), b''.join(map(table.__getitem__, _region_ids(isl.floor_id, W, x0, z0, x1, z1))))
    # terrace shading
    ground = Image.composite(Image.new('RGB', (w, h), (12, 16, 22)), ground, lay['dark'])
    ground = Image.composite(Image.new('RGB', (w, h), (255, 252, 236)), ground, lay['light'])
    ground = Image.composite(Image.blend(ground, Image.new('RGB', (w, h), (40, 34, 26)), 0.18), ground, lay['wet'])
    # liquids
    depth = lay['depth']
    wcol = _liquid_colour(lay['sdepth'], None, lay['near'])
    tops = _region_ids(isl.top_id, W, x0, z0, x1, z1)
    other = [b for b in set(tops) if b in LIQUID_STYLE and b not in SEA_IDS]
    for b in other:
        mask = Image.frombytes('L', (w, h), bytes(255 if t == b else 0 for t in tops))
        sh, dp = LIQUID_STYLE[b]
        col = _lut_rgb(depth.point(lambda v: min(255, v * 40)), _ramp([(0, sh), (255, dp)]))
        wcol = Image.composite(col, wcol, mask)
    # shallow water shows the ground below
    see = depth.point(lambda v: {1: 120, 2: 70, 3: 34}.get(v, 0))
    wcol = Image.composite(ground, wcol, see)
    wcol = Image.composite(Image.blend(wcol, Image.new('RGB', (w, h), (240, 252, 250)), 0.55), wcol, lay['foam'])
    img = Image.composite(wcol, ground, lay['water'])
    img = img.convert('RGBA')
    img.putalpha(ImageChops.invert(lay['nodata']))
    return img


def render_base(isl):
    return render_region(isl, 0, 0, isl.width, isl.height)


# ---------------------------------------------------------------------------------------------------- detail tiles
_RIPPLE = None


def _ripple():
    global _RIPPLE
    if _RIPPLE is None:
        import math
        im = Image.new('L', (TEX * 4, TEX * 4))
        p = im.load()
        for y in range(TEX * 4):
            for x in range(TEX * 4):
                v = math.sin(x * 0.42 + math.sin(y * 0.31) * 2.2) + math.sin(y * 0.57 + x * 0.12)
                p[x, y] = max(0, min(255, int(128 + v * 34)))
        _RIPPLE = im
    return _RIPPLE


def render_tile(isl, tx, tz, tex=TEX):
    """RGBA detail tile (32 * tex square) for the chunk at image-chunk coords (tx, tz): one textured square per block."""
    L = look()
    TEX, TILE = tex, 32 * tex
    W = isl.width
    x0, z0 = tx * 32, tz * 32
    x1, z1 = min(W, x0 + 32), min(isl.height, z0 + 32)
    lay = shade_layers(isl, x0, z0, x1, z1)
    img = Image.new('RGB', (TILE, TILE))
    fid = isl.floor_id
    for z in range(z0, z1):
        row = z * W
        for x in range(x0, x1):
            p = row + x
            if isl.top_h[p] == 255:
                continue
            t = L.texture(fid[p], TEX)
            if t is not None:
                img.paste(t, ((x - x0) * TEX, (z - z0) * TEX))
    big = lambda im: im.resize((im.width * TEX, im.height * TEX), Image.NEAREST).crop((0, 0, TILE, TILE))
    dark, light = lay['dark'], lay['light']
    img = Image.composite(Image.new('RGB', img.size, (12, 16, 22)), img, big(dark.point(lambda v: v * 0.85)))
    img = Image.composite(Image.new('RGB', img.size, (255, 252, 236)), img, big(light.point(lambda v: v * 0.8)))
    # crisp terrace lines: a dark line along the north / west edge of a block below its neighbour
    dr = ImageDraw.Draw(img)
    top = isl.floor_h
    for z in range(z0, z1):
        row = z * W
        for x in range(x0, x1):
            p = row + x
            h = top[p]
            if h == 255:
                continue
            X, Z = (x - x0) * TEX, (z - z0) * TEX
            if z > 0:
                hn = top[p - W]
                if hn != 255 and hn > h and isl.top_h[p] == h:
                    a = min(150, 70 + (hn - h) * 25)
                    dr.rectangle((X, Z, X + TEX - 1, Z + max(0, TEX // 8 - 1)), fill=_dim(img.getpixel((X + TEX // 4, Z + TEX // 8)), a))
            if x > 0:
                hw = top[p - 1]
                if hw != 255 and hw > h and isl.top_h[p] == h:
                    a = min(120, 50 + (hw - h) * 20)
                    dr.rectangle((X, Z, X + max(0, TEX // 8 - 1), Z + TEX - 1), fill=_dim(img.getpixel((X + TEX // 8, Z + TEX // 4)), a))
    # water
    water = big(lay['water'])
    if water.getbbox():
        depth = lay['depth']
        wcol = big(render_region(isl, x0, z0, x1, z1).convert('RGB'))
        rip = _ripple() if TEX == 16 else _ripple().resize((TEX * 4, TEX * 4), Image.BILINEAR)
        tiled = Image.new('L', (TILE, TILE))
        for yy in range(0, TILE, rip.height):
            for xx in range(0, TILE, rip.width):
                tiled.paste(rip, (xx, yy))
        lit = Image.blend(wcol, Image.new('RGB', wcol.size, (235, 250, 255)), 0.16)
        wcol = Image.composite(lit, wcol, tiled.point(lambda v: max(0, v - 150) * 3))
        alpha = big(depth.point(lambda v: {1: 150, 2: 200, 3: 230}.get(v, 245) if v else 0))
        img = Image.composite(wcol, img, ImageChops.multiply(alpha, water))
        foam = big(lay['foam']).filter(ImageFilter.GaussianBlur(max(1, TEX // 5))).point(lambda v: min(255, v * 2))
        img = Image.composite(Image.new('RGB', img.size, (236, 250, 248)), img,
                              ImageChops.multiply(foam, water).point(lambda v: min(110, v // 2)))
    out = img.convert('RGBA')
    out.putalpha(big(ImageChops.invert(lay['nodata'])))
    return out


def _dim(c, a):
    f = 1 - a / 255
    return tuple(int(v * f) for v in c[:3])


# ---------------------------------------------------------------------------------------------------- objects
FENCE_WORDS = ('fencing', 'fence', 'railing', 'handrail', 'harbor pole', 'enclosure', 'brick border', 'hedge')
ROOF_WORDS = ('roof',)
FLAT_WORDS = ('path', 'walkway', 'stepping stones', 'bridge planks', 'grate flooring', 'railway track', 'rug', 'mat')
PLANT_WORDS = ('grass', 'flowers', 'shoots', 'vines', 'sprout', 'stem', 'seaweed', 'fern', 'mushroom', 'moss')


def object_style(o):
    """'fence', 'roof', 'flat', 'plant', 'struct' (part of a building with no item), 'big' or 'item'."""
    if not o.item:
        return 'struct'
    n = ps.item_name(o.item).lower()
    if any(k in n for k in FENCE_WORDS) and o.w * o.dp == 1:
        return 'fence'
    if any(k in n for k in ROOF_WORDS):
        return 'roof'
    if any(k in n for k in FLAT_WORDS):
        return 'flat'
    if any(k in n for k in PLANT_WORDS) and o.w * o.dp == 1:
        return 'plant'
    if o.w * o.dp >= 6:
        return 'big'
    return 'item'


def render_objects(isl):
    """RGBA image, one pixel per block: placed objects tinted with their icon colour (for mid zoom)."""
    L = look()
    img = Image.new('RGBA', (isl.width, isl.height), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for o in sorted(isl.objects, key=lambda o: o.y + o.h):
        if o.y > isl.cut or isl.crosses_cut(o):
            continue
        x0, z0, x1, z1 = o.box
        c = L.item_color(o.item) if o.item else (150, 146, 140)
        st = object_style(o)
        a = {'plant': 150, 'flat': 170, 'struct': 215, 'roof': 235}.get(st, 225)
        dr.rectangle((x0 - isl.x0, z0 - isl.z0, x1 - isl.x0, z1 - isl.z0), fill=c + (a,))
    return img


HEIGHT_RAMP = _ramp([(0, (40, 60, 150)), (30, (40, 110, 200)), (31, (40, 170, 190)), (33, (70, 190, 110)),
                     (38, (160, 210, 70)), (44, (240, 200, 60)), (52, (240, 130, 50)), (62, (220, 60, 70)),
                     (80, (200, 80, 200)), (127, (250, 250, 255)), (255, (250, 250, 255))])


def render_heights(isl, x0, z0, x1, z1):
    """RGBA height map of a region: colour by ground height, every other level a little darker so each step shows."""
    W = isl.width
    w, h = x1 - x0, z1 - z0
    g = Image.frombytes('L', (w, h), bytes(_region_bytes(isl.floor_h, W, x0, z0, x1, z1)))
    col = _lut_rgb(g, HEIGHT_RAMP)
    odd = g.point(lambda v: 40 if v % 2 and v != 255 else 0)
    col = Image.composite(Image.new('RGB', (w, h), (0, 0, 0)), col, odd)
    out = col.convert('RGBA')
    out.putalpha(g.point(lambda v: 0 if v == 255 else 175))
    return out


class IslandView:
    """What the map page keeps per island: the editable model plus rendered images."""

    def __init__(self, isl):
        self.isl = isl
        self.base = render_base(isl)
        self.objects = render_objects(isl)
        from collections import Counter
        self.top = Counter(o.item for o in isl.objects if o.item).most_common(8)

    def refresh_top(self):
        from collections import Counter
        self.top = Counter(o.item for o in self.isl.objects if self.isl.zone_at(o.x, o.z) is self.isl.zones[0]
                           and o.item).most_common(8)


def load_island(path, area):
    isl = pi.load(path, area)
    v = IslandView(isl)
    v.refresh_top()
    return v
