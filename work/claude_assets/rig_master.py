"""Turn the generated still into animation layers.

All painting happens at the full source resolution and is then scaled down, so
the repairs stay crisp. Coordinates below are pixels in raw/master.png.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from cutout import fit_canvas, key_out

SKIN = (254, 228, 214)
LASH = (122, 68, 52)
CONTOUR = (152, 67, 33)
HAIR = (243, 176, 130)
EYE_LEFT = [(452, 516), (470, 478), (498, 460), (530, 455), (553, 458), (570, 470), (584, 498),
            (585, 530), (572, 552), (530, 560), (498, 554), (476, 544)]
EYE_RIGHT = [(665, 498), (678, 470), (700, 455), (735, 456), (762, 466), (782, 490), (793, 518),
             (772, 544), (748, 554), (705, 560), (672, 552), (660, 530)]
ARC_LEFT = ((462, 508), (584, 508), 28)
ARC_RIGHT = ((660, 508), (782, 508), 28)
MOUTH = (598, 548, 646, 572)
MASCOT = (524, 54, 730, 190)
SS = 3


def polygon_mask(size, polygons, blur=1.2):
    mask = Image.new('L', (size[0] * SS, size[1] * SS), 0)
    pen = ImageDraw.Draw(mask)
    for points in polygons:
        pen.polygon([(x * SS, y * SS) for x, y in points], fill=255)
    return mask.resize(size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur))


def arc_shape(start, end, sag, weight=8.5):
    """A tapered lid line. Positive sag curves down, negative curves up."""
    u = np.linspace(-1, 1, 40)
    xs = (start[0] + end[0]) / 2 + u * (end[0] - start[0]) / 2
    ys = start[1] + sag * (1 - u * u)
    half = weight * (1 - u * u) ** 0.6 / 2 + 0.8
    return [(x, y - h) for x, y, h in zip(xs, ys, half)] + [(x, y + h) for x, y, h in zip(xs[::-1], ys[::-1], half[::-1])]


def stamp(image, shape, colour):
    image.paste(Image.new('RGBA', image.size, colour + (255,)), (0, 0), polygon_mask(image.size, [shape], blur=0.4))


def covered(image):
    out = image.copy()
    out.paste(Image.new('RGBA', out.size, SKIN + (255,)), (0, 0), polygon_mask(out.size, [EYE_LEFT, EYE_RIGHT]))
    return out


def closed_eyes(image, sag=1.0):
    out = covered(image)
    for start, end, depth in (ARC_LEFT, ARC_RIGHT):
        stamp(out, arc_shape(start, end, depth * sag), LASH)
    return out


def half_eyes(image):
    """Squash each eye towards its lower lid so the real art is reused."""
    out = covered(image)
    for points in (EYE_LEFT, EYE_RIGHT):
        xs, ys = zip(*points)
        box = (min(xs), min(ys), max(xs), max(ys))
        patch = image.crop(box)
        mask = polygon_mask(image.size, [points]).crop(box)
        height = round((box[3] - box[1]) * 0.56)
        size = (patch.width, height)
        out.paste(patch.resize(size, Image.LANCZOS), (box[0], box[3] - height), mask.resize(size, Image.LANCZOS))
    return out


def happy_face(image):
    out = closed_eyes(image, sag=-0.8)
    pen_mask = Image.new('L', (image.width * SS, image.height * SS), 0)
    ImageDraw.Draw(pen_mask).ellipse([v * SS for v in (592, 540, 652, 566)], fill=255)
    out.paste(Image.new('RGBA', out.size, SKIN + (255,)), (0, 0), pen_mask.resize(out.size, Image.LANCZOS))
    left, top, right, bottom = MOUTH
    mouth = [(left, top)] + [(left + (right - left) * t, top + (bottom - top) * np.sin(np.pi * t)) for t in np.linspace(0, 1, 24)] + [(right, top)]
    stamp(out, [(x - 2, y - 2 if y == top else y + 2) for x, y in mouth], CONTOUR)
    stamp(out, mouth, (226, 112, 108))
    return out


def split_mascot(image):
    """Lift the mascot off and rebuild the head top it was hiding."""
    pixels = np.asarray(image).astype(np.float64)
    left, top, right, bottom = MASCOT
    region = np.zeros(pixels.shape[:2], bool)
    region[top:bottom, left:right] = True
    r, g, b = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    mascot_colour = (r > 165) & (g < 125) & (b < 100)
    dark = (r + g + b) < 200
    core = region & (mascot_colour | dark) & (pixels[..., 3] > 30)
    from scipy import ndimage
    core = ndimage.binary_dilation(ndimage.binary_closing(core, iterations=3), iterations=4) & region
    layer = pixels.copy()
    layer[..., 3] *= core
    base = pixels.copy()
    base[..., 3] *= ~core

    # Fit the visible head-top arc on both sides and redraw the hidden part.
    alpha = base[..., 3] > 128
    samples = [(x, np.argmax(alpha[:, x])) for x in list(range(440, left - 8, 6)) + list(range(right + 8, 815, 6))]
    xs, ys = zip(*samples)
    curve = np.poly1d(np.polyfit(xs, ys, 2))
    edge = [(x, float(curve(x))) for x in range(left - 12, right + 13, 4)]
    out = Image.fromarray(base.clip(0, 255).astype(np.uint8), 'RGBA')
    fill = edge + [(right + 12, 260), (left - 12, 260)]
    stamp(out, fill, HAIR)
    stamp(out, [(x, y - 3) for x, y in edge] + [(x, y + 4) for x, y in edge[::-1]], CONTOUR)
    original = Image.fromarray(pixels.clip(0, 255).astype(np.uint8), 'RGBA')
    below = Image.new('L', out.size, 0)
    ImageDraw.Draw(below).rectangle((0, 192, out.width, out.height), fill=255)
    out.paste(original, (0, 0), below)
    return out, Image.fromarray(layer.clip(0, 255).astype(np.uint8), 'RGBA')


def build(path, size=512, foot=486, top_margin=62):
    cut = key_out(Image.open(path))
    still = Image.fromarray(np.clip(cut + 0.5, 0, 255).astype(np.uint8), 'RGBA')
    base, mascot = split_mascot(still)
    layers = {'open': base, 'half': half_eyes(base), 'closed': closed_eyes(base), 'happy': happy_face(base)}
    alpha = cut[..., 3] > 8
    ys, xs = np.nonzero(alpha)
    x0, y0 = xs.min(), ys.min()
    box = (x0, y0, xs.max() + 1, ys.max() + 1)
    _, scale = fit_canvas(cut, size, foot=foot, top_margin=top_margin)

    def place(image):
        data = np.asarray(image).astype(np.float64).copy()
        # Keep every layer on the same crop, so they stay registered.
        data[y0, x0, 3] = max(data[y0, x0, 3], 9)
        data[box[3] - 1, box[2] - 1, 3] = max(data[box[3] - 1, box[2] - 1, 3], 9)
        canvas, _ = fit_canvas(data, size, scale=scale, foot=foot)
        return canvas

    faces = {name: place(layer) for name, layer in layers.items()}
    width = round((box[2] - box[0]) * scale)
    height = round((box[3] - box[1]) * scale)
    left, top = (size - width) // 2, foot - height

    def to_canvas(x, y):
        return (x - x0) * scale + left, (y - y0) * scale + top

    landmarks = dict(neck=to_canvas(622, 600), feet_y=foot, body_half=78, head_bottom=to_canvas(622, 600)[1],
                     head_top=to_canvas(622, 175)[1])
    return faces, place(mascot), landmarks
