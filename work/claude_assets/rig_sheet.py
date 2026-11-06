"""Turn raw/poses.png into one animation rig per pet state.

The six figures come from one image, so they already agree on proportions,
colour and line weight. Only the eye outlines are measured by hand; the mascot
and the head top behind it are handled automatically.
Coordinates are pixels in raw/poses.png.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

from cutout import key_out, place_on_canvas, split_figures
from motion import Rig

ORDER = ['work', 'cheer', 'think', 'ask', 'sleep', 'stand']
SIZE, FOOT, TOP = 512, 486, 50
LASH = (92, 44, 30)
SS = 4

EYES = {
    'work': {
        'polys': [[(167, 241), (178, 224), (200, 219), (214, 225), (222, 238), (225, 255), (216, 266), (203, 266), (188, 258), (178, 248)],
                  [(259, 233), (266, 219), (285, 213), (305, 216), (329, 228), (315, 247), (300, 255), (284, 262), (270, 258), (262, 246)]],
        'arcs': [((170, 243), (226, 248)), ((260, 236), (327, 232))],
    },
    'think': {
        'polys': [[(1169, 175), (1180, 160), (1200, 150), (1216, 150), (1228, 161), (1226, 183), (1217, 198), (1205, 201), (1190, 195), (1178, 185)],
                  [(1263, 190), (1266, 172), (1280, 160), (1298, 161), (1314, 175), (1331, 197), (1312, 209), (1296, 210), (1278, 209), (1268, 202)]],
        'arcs': [((1174, 178), (1230, 174)), ((1265, 188), (1331, 198))],
    },
    'ask': {
        'polys': [[(162, 731), (172, 716), (200, 708), (215, 711), (223, 724), (223, 742), (214, 752), (202, 756), (186, 750), (175, 741)],
                  [(260, 721), (268, 709), (282, 704), (298, 707), (315, 716), (329, 726), (313, 744), (298, 749), (282, 753), (266, 746)]],
        'arcs': [((166, 733), (224, 733)), ((262, 728), (327, 730))],
    },
    'stand': {
        'polys': [[(1174, 711), (1186, 696), (1204, 686), (1222, 683), (1234, 690), (1239, 702), (1238, 720), (1228, 733), (1216, 735), (1200, 731), (1188, 722)],
                  [(1279, 698), (1288, 688), (1302, 683), (1320, 687), (1336, 698), (1350, 711), (1332, 726), (1316, 732), (1298, 735), (1284, 728), (1278, 712)]],
        'arcs': [((1180, 712), (1240, 712)), ((1278, 712), (1343, 712))],
    },
}
NECK = {'work': (262, 295), 'cheer': (748, 232), 'think': (1248, 262), 'ask': (262, 775), 'sleep': (775, 810), 'stand': (1265, 770)}


def as_image(data):
    return Image.fromarray(np.clip(data + 0.5, 0, 255).astype(np.uint8), 'RGBA')


def mask_of(size, points, blur=0.9):
    mask = Image.new('L', (size[0] * SS, size[1] * SS), 0)
    ImageDraw.Draw(mask).polygon([(x * SS, y * SS) for x, y in points], fill=255)
    return mask.resize(size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur))


def arc_shape(start, end, sag, weight=4.6):
    u = np.linspace(-1, 1, 40)
    xs = (start[0] + end[0]) / 2 + u * (end[0] - start[0]) / 2
    ys = start[1] + (end[1] - start[1]) * (u + 1) / 2 + sag * (1 - u * u)
    half = weight * (1 - u * u) ** 0.6 / 2 + 0.5
    return [(x, y - h) for x, y, h in zip(xs, ys, half)] + [(x, y + h) for x, y, h in zip(xs[::-1], ys[::-1], half[::-1])]


def skin_near(data, spec):
    """Sample bare skin between the eyes, away from lashes and blush."""
    (a, b), (c, d) = spec['arcs']
    x, y = int((b[0] + c[0]) / 2), int((b[1] + c[1]) / 2)
    return tuple(int(v) for v in np.median(data[y - 4:y + 5, x - 4:x + 5, :3].reshape(-1, 3), axis=0))


def eye_faces(data, spec, offset):
    """Build half-closed and closed faces from one open-eyed crop."""
    ox, oy = offset
    image = as_image(data)
    polys = [[(x - ox, y - oy) for x, y in poly] for poly in spec['polys']]
    arcs = [((a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy)) for a, b in spec['arcs']]
    skin = skin_near(data, {'arcs': arcs})

    r, g, b = data[..., 0], data[..., 1], data[..., 2]
    hair = (r > 225) & (g > 120) & (g < 195) & (b < 165)

    def cover_mask(poly):
        # Grow past the lash and eye rim, but never paint over strands of hair.
        tight = mask_of(image.size, poly, blur=0.0)
        wide = np.asarray(tight.filter(ImageFilter.MaxFilter(9))).astype(np.float64)
        wide = np.where(hair, 0.0, wide)
        keep = np.maximum(wide, np.asarray(tight).astype(np.float64))
        return Image.fromarray(keep.astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(1.0))

    def covered():
        out = image.copy()
        for poly in polys:
            out.paste(Image.new('RGBA', out.size, skin + (255,)), (0, 0), cover_mask(poly))
        return out

    closed = covered()
    for start, end in arcs:
        closed.paste(Image.new('RGBA', closed.size, LASH + (255,)), (0, 0), mask_of(closed.size, arc_shape(start, end, 11), blur=0.3))
    half = covered()
    for poly in polys:
        xs, ys = zip(*poly)
        box = (int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1)
        patch = image.crop(box)
        region = mask_of(image.size, poly).crop(box)
        height = round((box[3] - box[1]) * 0.56)
        size = (patch.width, height)
        half.paste(patch.resize(size, Image.LANCZOS), (box[0], box[3] - height), region.resize(size, Image.LANCZOS))
    return {'half': np.asarray(half).astype(np.float64), 'closed': np.asarray(closed).astype(np.float64)}


def split_mascot(crop):
    """Return (figure without mascot, mascot layer, y of the head top)."""
    height, width = crop.shape[:2]
    r, g, b, a = (crop[..., i] for i in range(4))
    region = np.zeros((height, width), bool)
    region[:int(height * 0.3)] = True
    colour = region & (r > 165) & (g < 132) & (b < 112) & (a > 128)
    labels, count = ndimage.label(colour)
    largest = 1 + int(np.argmax(ndimage.sum(colour, labels, index=np.arange(1, count + 1))))
    core = labels == largest
    hair = (g > 140) & (r > 205)
    core = ndimage.binary_dilation(core, iterations=5) & region & ~hair & (a > 20)
    core = ndimage.binary_fill_holes(core)
    core = ndimage.binary_dilation(ndimage.binary_opening(core, iterations=2), iterations=1)
    ys, xs = np.nonzero(core)
    left, right, bottom = xs.min(), xs.max(), ys.max()

    mascot = crop.copy()
    mascot[..., 3] *= core
    base = crop.copy()
    base[..., 3] *= ~core

    solid = base[..., 3] > 128
    columns = [x for x in list(range(max(0, left - 70), left - 8, 4)) + list(range(right + 9, min(width, right + 72), 4)) if solid[:, x].any()]
    edges = [int(np.argmax(solid[:, x])) for x in columns]
    curve = np.poly1d(np.polyfit(columns, edges, 2))
    # Tilt the fit so it meets the real outline exactly at both ends of the gap.
    a_x, b_x = max(0, left - 9), min(width - 1, right + 9)
    a_err = int(np.argmax(solid[:, a_x])) - curve(a_x)
    b_err = int(np.argmax(solid[:, b_x])) - curve(b_x)

    def edge_at(x):
        return float(curve(x) + a_err + (b_err - a_err) * (x - a_x) / max(1, b_x - a_x))

    contour = np.median(crop[(crop[..., 3] > 230) & ~ndimage.binary_erosion(crop[..., 3] > 230, iterations=2)][:, :3], axis=0)
    seam = min(height - 5, bottom + 10)
    # Sample below the mascot's legs, then smooth along the row to avoid streaks.
    row = base[seam:seam + 4, :, :3].mean(axis=0)
    row = np.dstack([ndimage.median_filter(row[:, i], size=15) for i in range(3)])[0]
    for x in range(a_x, b_x + 1):
        edge = edge_at(x)
        for y in range(max(0, int(edge) - 3), seam):
            inside = np.clip(y - edge + 0.5, 0.0, 1.0)
            line = np.clip(1.0 - abs(y - (edge + 1.2)) / 2.4, 0.0, 1.0)
            fade = np.clip((y - (seam - 12)) / 12.0, 0.0, 1.0)
            fill = row[x] * (1 - fade) + base[y, x, :3] * fade if base[y, x, 3] > 200 else row[x]
            base[y, x, :3] = fill * (1 - line) + contour * line
            base[y, x, 3] = 255.0 * inside
        base[:max(0, int(edge) - 3), x, 3] = 0.0
    return base, mascot, edge_at((left + right) / 2)


def build(path):
    cut = key_out(Image.open(path))
    figures = dict(zip(ORDER, split_figures(cut)))
    scale = (FOOT - TOP) / max(box[3] - box[1] for box, _ in figures.values())
    rigs = {}
    for name, (box, crop) in figures.items():
        base, mascot, head_top = split_mascot(crop)
        faces = {'open': base}
        if name in EYES:
            faces.update(eye_faces(base, EYES[name], box[:2]))
        placed = {key: place_on_canvas(value, scale, SIZE, FOOT)[0] for key, value in faces.items()}
        layer, left, top = place_on_canvas(mascot, scale, SIZE, FOOT)

        def to_canvas(x, y, box=box, left=left, top=top):
            return (x - box[0]) * scale + left, (y - box[1]) * scale + top

        neck = to_canvas(*NECK[name])
        rig = Rig(placed, neck=neck, feet_y=FOOT, body_half=74, head_bottom=neck[1], head_top=head_top * scale + top, mascot=layer)
        rig.at = to_canvas
        rig.scale = scale
        rigs[name] = rig
    return rigs


def hair_mean(cut):
    rgb = cut[cut[..., 3] > 200][:, :3]
    return rgb[(rgb[:, 0] > 220) & (rgb[:, 1] > 130) & (rgb[:, 1] < 205) & (rgb[:, 2] < 170) & (rgb[:, 2] > 70)].mean(axis=0)


def match_colour(cut, reference):
    """Pull the hair of one sheet towards another, in place, and return the gain used."""
    gain = hair_mean(reference) / hair_mean(cut)
    # Only strong oranges drift: a global gain would tint cream cloth and skin pink.
    top, low = cut[..., :3].max(axis=2), cut[..., :3].min(axis=2)
    saturation = (top - low) / np.maximum(top, 1.0)
    weight = np.clip((saturation - 0.26) / 0.18, 0.0, 1.0)[..., None]
    weight = weight * ((cut[..., 0:1] > cut[..., 1:2]) & (cut[..., 1:2] > cut[..., 2:3]) & (cut[..., 0:1] > 200))
    cut[..., :3] = (cut[..., :3] * (1.0 + (gain - 1.0) * weight)).clip(0, 255)
    return gain


def build_walk(path, reference_path, head_scale=0.745):
    """Rigs for a drawn walk cycle, colour-matched to the pose sheet."""
    cut = key_out(Image.open(path))
    gain = match_colour(cut, key_out(Image.open(reference_path)))
    rigs = []
    for box, crop in split_figures(cut):
        base, mascot, head_top = split_mascot(crop)
        layer, left, top = place_on_canvas(mascot, head_scale, SIZE, FOOT)
        face = place_on_canvas(base, head_scale, SIZE, FOOT)[0]
        height, width = crop.shape[:2]
        neck = (0.66 * width * head_scale + left, 0.52 * height * head_scale + top)
        rigs.append(Rig({'open': face}, neck=neck, feet_y=FOOT, body_half=60, head_bottom=neck[1],
                        head_top=head_top * head_scale + top, mascot=layer))
    return rigs, gain
